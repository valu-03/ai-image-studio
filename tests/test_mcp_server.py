"""mcp_server/server.py over real stdio, the way Claude Code, Codex or any MCP client runs it.

The server is launched as a subprocess from an unrelated folder with the app closed, so it
has to start its private engine itself. Kie is mock_api; the .env, History and outputs are
throwaway, so nothing real is read, spent or logged. Also checks mcp_server/install.py's
config writers on a fake home folder.
"""
import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "mcp_server"))

import mock_api  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("  SKIP mcp is not installed (pip install -r requirements.txt)")
    sys.exit(0)

MOCK_PORT = free_port()
mock_api.serve(MOCK_PORT)
TMP = Path(tempfile.mkdtemp(prefix="aivs-mcp-"))
ENV_FILE = TMP / ".env"
ENV_FILE.write_text("KIE_API_KEY=fake-kie\nAIVS_API_BASE=http://127.0.0.1:{}\n"
                    "AIVS_LOCAL_API_PORT={}\n".format(MOCK_PORT, free_port()), encoding="utf-8")
ENV = dict(os.environ, AIVS_ENV_FILE=str(ENV_FILE), AIVS_HISTORY_FILE=str(TMP / "history.jsonl"),
           AIVS_OUTPUTS_DIR=str(TMP / "outputs"), AIVS_POLL_INTERVAL="0.05", PYTHONUTF8="1")
for var in ("AIVS_URL", "AVS_URL", "AIVS_LOCAL_API_TOKEN"):
    ENV.pop(var, None)

EXPECTED = {"avs_status", "look_options", "look_current", "look_compose", "prompt_preview",
            "image_generate", "image_get", "image_wait", "image_cancel"}


def field(obj, name):
    """mcp 2.x names fields in snake_case, 1.x in camelCase."""
    camel = name.split("_")[0] + "".join(w.title() for w in name.split("_")[1:])
    return getattr(obj, name, None) if hasattr(obj, name) else getattr(obj, camel, None)


def data(result):
    """A tool result's JSON, whichever way this mcp version returns it."""
    if field(result, "structured_content"):
        payload = field(result, "structured_content")
        return payload.get("result", payload) if set(payload) == {"result"} else payload
    return json.loads(result.content[0].text)


async def session_checks():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "mcp_server" / "server.py")],
                                   env=ENV, cwd=str(TMP))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            check("server names itself", field(init, "server_info").name == "ai-image-studio",
                  field(init, "server_info").name)
            check("instructions reach the client", "approved=True" in (init.instructions or ""))

            tools = {t.name: t for t in (await session.list_tools()).tools}
            check("all nine tools listed", set(tools) == EXPECTED, str(sorted(tools)))
            look_schema = json.dumps(field(tools["prompt_preview"], "input_schema"))
            check("look accepts a string or an object", '"string"' in look_schema
                  and '"object"' in look_schema)
            check("no Skit Studio left in the tool text",
                  "skit" not in json.dumps([t.description for t in tools.values()]).lower())

            status = data(await session.call_tool("avs_status", {}))
            check("app closed -> private engine", "started by this MCP server"
                  in status.get("engine", ""), status.get("engine", ""))
            check("status sees the Kie key", (status.get("providers") or {}).get("kie") is True)

            options = data(await session.call_tool("look_options", {"part": "lighting"}))
            check("look_options narrows to one part", list(options) == ["lighting"])

            preview = data(await session.call_tool("prompt_preview", {
                "prompt": "A woman reads on a train.", "look": "none", "realism": True}))
            check("prompt_preview returns a prompt", "train" in (preview.get("prompt") or ""))

            unapproved = data(await session.call_tool("image_generate", {
                "prompt": "A cat on a windowsill.", "look": "none"}))
            check("unapproved generate only prices it", unapproved.get("approved") is False
                  and unapproved["price"]["kie_credits"] == 24)

            job = data(await session.call_tool("image_generate", {
                "prompt": "A cat on a windowsill.", "look": "none", "approved": True}))
            check("approved generate returns an id", bool(job.get("id")), str(job)[:200])
            done = data(await session.call_tool("image_wait", {"image_id": job.get("id", ""),
                                                               "timeout_seconds": 30}))
            check("image_wait finishes", done.get("state") == "done" and done.get("finished"),
                  str(done.get("state")) + " " + str(done.get("error")))
            saved = Path(done.get("file") or "")
            check("image saved in the throwaway outputs", saved.is_file()
                  and TMP in saved.resolve().parents, str(saved))
            rows = (TMP / "history.jsonl").read_text(encoding="utf-8").splitlines()
            note = json.loads(rows[-1]).get("note", "") if rows else ""
            check("history row is tagged Local API", note == "Local API", note)

            missing = await session.call_tool("image_get", {"image_id": "0123abcd"})
            check("unknown image is a tool error, not a crash", field(missing, "is_error"))


print("MCP server over stdio")
asyncio.run(asyncio.wait_for(session_checks(), 120))

print("Installer")
import install  # noqa: E402

block = install.codex_block()
check("codex block has absolute python and server",
      json.dumps(str(install.PYTHON)) in block and json.dumps(str(install.SERVER)) in block)
old = ('model = "x"\n\n[mcp_servers.ai-image-studio]\ncommand = "old"\n\n'
       '[mcp_servers.ai-image-studio.env]\nA = "1"\n\n[mcp_servers.other]\ncommand = "keep"\n')
stripped = install.strip_codex(old)
check("codex strip removes only our tables", "old" not in stripped and 'A = "1"' not in stripped
      and '[mcp_servers.other]' in stripped and 'model = "x"' in stripped, stripped)

home = TMP / "home"
cursor = home / ".cursor"
cursor.mkdir(parents=True)
(cursor / "mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}),
                                 encoding="utf-8")
install.JSON_CLIENTS["cursor"] = ("Cursor", cursor / "mcp.json", cursor)
install.do_json("cursor", uninstall=False)
written = json.loads((cursor / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]
check("json client keeps other servers", "other" in written and
      written.get("ai-image-studio", {}).get("args") == [str(install.SERVER)])
install.do_json("cursor", uninstall=True)
written = json.loads((cursor / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]
check("json uninstall removes only ours", list(written) == ["other"])
install.JSON_CLIENTS["cursor"] = ("Cursor", home / "none" / "mcp.json", home / "none")
check("a client that is not installed is skipped",
      install.do_json("cursor", False).startswith("skipped") and not (home / "none").exists())

print()
print("FAILED: " + ", ".join(fails) if fails else "all MCP checks passed")
sys.exit(1 if fails else 0)
