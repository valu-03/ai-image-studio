"""Register the AI Image Studio MCP server with the AI clients on this PC.

    python mcp_server/install.py             # every client found
    python mcp_server/install.py --only claude,codex
    python mcp_server/install.py --print     # show the config, change nothing
    python mcp_server/install.py --uninstall

Every entry uses the Python running this script and absolute paths, so it works from any
folder and on any PC, whatever the project folder is called. Run it with the Python you
installed requirements.txt into (a venv's python works too). Re-running is safe: an existing
ai-image-studio entry is replaced, nothing else in a config is touched, and every file that
gets changed is backed up beside itself first (<name>.bak).

Clients: Claude Code (through its `claude` CLI), Codex (~/.codex/config.toml), Gemini CLI
(~/.gemini/settings.json), Cursor (~/.cursor/mcp.json), Claude Desktop and Windsurf. For
anything else, --print gives the JSON block most MCP clients accept.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

NAME = "ai-image-studio"
ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "server.py"
PYTHON = Path(sys.executable).resolve()
HOME = Path.home()


def entry():
    return {"command": str(PYTHON), "args": [str(SERVER)]}


def appdata():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or HOME / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return HOME / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")


# Clients that keep servers in a JSON file under "mcpServers": (label, file, folder that
# shows the client is installed).
JSON_CLIENTS = {
    "gemini": ("Gemini CLI", HOME / ".gemini" / "settings.json", HOME / ".gemini"),
    "cursor": ("Cursor", HOME / ".cursor" / "mcp.json", HOME / ".cursor"),
    "claude-desktop": ("Claude Desktop", appdata() / "Claude" / "claude_desktop_config.json",
                       appdata() / "Claude"),
    "windsurf": ("Windsurf", HOME / ".codeium" / "windsurf" / "mcp_config.json",
                 HOME / ".codeium" / "windsurf"),
}
CODEX_FILE = HOME / ".codex" / "config.toml"
ALL = ["claude", "codex"] + list(JSON_CLIENTS)


def backup(path):
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


# ----------------------------------------------------------------- Claude Code
def claude_cli():
    return shutil.which("claude") or shutil.which("claude.cmd")


def do_claude(uninstall):
    exe = claude_cli()
    if not exe:
        return "skipped - the `claude` command is not on PATH"
    run = lambda *args: subprocess.run([exe, "mcp", *args], capture_output=True, text=True)  # noqa: E731
    run("remove", NAME, "--scope", "user")
    if uninstall:
        return "removed"
    result = run("add", "--scope", "user", NAME, "--", str(PYTHON), str(SERVER))
    if result.returncode != 0:
        return "FAILED - " + (result.stderr or result.stdout).strip()[:300]
    return "added for every project (user scope)"


# ----------------------------------------------------------------------- Codex
def toml_str(value):
    return json.dumps(value)  # a JSON string is a valid TOML basic string


def codex_block():
    return ("[mcp_servers.{}]\ncommand = {}\nargs = [{}]\n"
            "startup_timeout_sec = 30\ntool_timeout_sec = 120\n"
            .format(NAME, toml_str(str(PYTHON)), toml_str(str(SERVER))))


def strip_codex(text):
    """Remove [mcp_servers.ai-image-studio] and its sub-tables, keep everything else."""
    out, skipping = [], False
    pattern = re.compile(r"^\s*\[\s*mcp_servers\.(\"?){}\1(\s*\]|\.)".format(re.escape(NAME)))
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("["):
            skipping = bool(pattern.match(line))
        if not skipping:
            out.append(line)
    return "".join(out).rstrip() + "\n"


def do_codex(uninstall):
    if not CODEX_FILE.parent.exists() and not shutil.which("codex"):
        return "skipped - Codex is not installed"
    text = CODEX_FILE.read_text(encoding="utf-8") if CODEX_FILE.exists() else ""
    new = strip_codex(text)
    if not uninstall:
        new = (new.rstrip() + "\n\n" if new.strip() else "") + codex_block()
    if new == text:
        return "nothing to change"
    backup(CODEX_FILE)
    CODEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    CODEX_FILE.write_text(new, encoding="utf-8", newline="\n")
    return "removed" if uninstall else "written to {}".format(CODEX_FILE)


# ------------------------------------------------------------- JSON clients
def do_json(key, uninstall):
    label, path, marker = JSON_CLIENTS[key]
    if not marker.exists():
        return "skipped - {} is not installed".format(label)
    raw = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return "skipped - {} is not valid JSON; fix it or add the --print block by hand".format(path)
    servers = data.setdefault("mcpServers", {})
    if uninstall:
        if servers.pop(NAME, None) is None:
            return "nothing to change"
    else:
        servers[NAME] = entry()
    backup(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "removed" if uninstall else "written to {}".format(path)


# --------------------------------------------------------------------------- #
def check_server():
    """Start the server's own self-test so a broken install is caught here, not in a client."""
    result = subprocess.run([str(PYTHON), str(SERVER), "--check"], capture_output=True,
                            text=True, timeout=120, cwd=str(HOME))
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma list of: " + ", ".join(ALL))
    parser.add_argument("--print", action="store_true", help="show the config, change nothing")
    parser.add_argument("--uninstall", action="store_true", help="remove ai-image-studio")
    parser.add_argument("--no-check", action="store_true", help="skip the server self-test")
    args = parser.parse_args(argv)

    if args.print:
        print("Any MCP client (JSON):")
        print(json.dumps({"mcpServers": {NAME: entry()}}, indent=2))
        print("\nCodex (~/.codex/config.toml):\n" + codex_block())
        print("Claude Code:\n  claude mcp add --scope user {} -- \"{}\" \"{}\"".format(NAME, PYTHON, SERVER))
        return 0

    chosen = [c.strip() for c in args.only.split(",")] if args.only else ALL
    unknown = [c for c in chosen if c not in ALL]
    if unknown:
        parser.error("unknown client(s): {} (choose from {})".format(", ".join(unknown), ", ".join(ALL)))

    if not args.uninstall:
        try:
            import mcp  # noqa: F401
        except ImportError:
            print("Installing the 'mcp' package for {} ...".format(PYTHON))
            if subprocess.run([str(PYTHON), "-m", "pip", "install", "mcp>=1.2"]).returncode:
                print("pip failed - run:  \"{}\" -m pip install -r requirements.txt".format(PYTHON))
                return 1
        if not args.no_check:
            ok, output = check_server()
            print(output)
            if not ok:
                print("\nThe server self-test failed, so nothing was registered.")
                return 1
            print()

    for client in chosen:
        if client == "claude":
            label, status = "Claude Code", do_claude(args.uninstall)
        elif client == "codex":
            label, status = "Codex", do_codex(args.uninstall)
        else:
            label, status = JSON_CLIENTS[client][0], do_json(client, args.uninstall)
        print("  {:<15} {}".format(label, status))
    if not args.uninstall:
        print("\nRestart the client (or start a new session) to load '{}'.".format(NAME))
    return 0


if __name__ == "__main__":
    sys.exit(main())
