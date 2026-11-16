"""AI Image Studio MCP server - lets Claude Code, Codex, Gemini CLI, Cursor or any MCP client
use the Images and Look sections.

    python mcp_server/server.py            # stdio MCP server (what a client launches)
    python mcp_server/server.py --check    # self-test: start the engine, print its status

Register it with every client found on this PC (uses this Python, absolute paths):

    python mcp_server/install.py

or by hand - always with the full path to python and to this file:

    claude:  claude mcp add --scope user ai-image-studio -- <python> <project>/mcp_server/server.py
    codex:   [mcp_servers.ai-image-studio] in ~/.codex/config.toml
             command = "<python>", args = ["<project>/mcp_server/server.py"]
    others:  {"mcpServers": {"ai-image-studio": {"command": "<python>", "args": ["<server.py>"]}}}

A thin client of the Local API (tools/local_api.py). While the desktop app is open it uses
the app's API (http://127.0.0.1:8785, AIVS_LOCAL_API_PORT to change, AIVS_LOCAL_API_TOKEN
sent when set), so look="current" reads the Look on screen. When the app is closed it starts
a private copy of the same engine inside this process, on a free port with its own random
token, so it never takes the app's port and the app can still be opened later. AIVS_URL points
it at a Local API somewhere else instead (no private engine is started for a remote URL).

Spending: image_generate costs Kie credits (Nano Banana Pro, ~24 credits = ~$0.12 per try;
Refine adds up to 2 more tries). It refuses to run until `approved=True`, which an agent may
only pass after the user said yes to the price it showed.
"""

import asyncio
import base64
import contextlib
import json
import mimetypes
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Union

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import generate_image as gi  # noqa: E402  (.env reader, for the port and token)

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    try:
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError:
        sys.stderr.write("AI Image Studio MCP: the 'mcp' package is missing for {}.\n"
                         "Install it with:  \"{}\" -m pip install \"mcp>=1.2\"\n"
                         .format(sys.executable, sys.executable))
        raise SystemExit(1)

APP = "AI Image Studio"
CREDITS_PER_TRY = 24      # tools/pricing.json nano-banana-pro
CREDIT_USD = 0.005
MAX_REFINE = 2
# Codex stops a tool call after 60 s by default, so one image_wait call returns before that
# and says to call again; a client with a longer limit can pass a bigger timeout_seconds.
WAIT_DEFAULT = 45
WAIT_MAX = 1800
APP_CHECK_TTL = 10.0      # seconds a "the app is (not) open" answer is trusted
LOOK_PARTS = ("style", "lighting", "camera", "composition", "posing", "color", "capture", "evidence")
DONE_STATES = ("done", "failed", "cancelled")

INSTRUCTIONS = """You drive AI Image Studio's image engine: its Look section (lighting, camera,
composition, posing, color, style, capture, evidence) and its Images section (the free realism
switches that make a prompt read as a real photo, and the paid Refine that retries the weak
layer). Start with avs_status. Build the look with look_options / look_compose (or use the
Look currently applied in the app with look="current"), preview the finished prompt with
prompt_preview (free), then image_generate. image_generate spends Kie credits: show the user
the price it reports and only call it again with approved=True after an explicit yes.
Then call image_wait until the job is done; it returns the saved file path."""

mcp = _Server("ai-image-studio", instructions=INSTRUCTIONS)


def log(message):
    """stdout carries the MCP protocol, so anything for a human goes to stderr."""
    sys.stderr.write("[ai-image-studio] {}\n".format(message))
    sys.stderr.flush()


# --------------------------------------------------------------------------- #
# Backend: the open app, or a private engine in this process
# --------------------------------------------------------------------------- #
class Backend:
    def __init__(self):
        self.lock = threading.Lock()
        self.private = None          # local_api.LocalApi started by this process
        self.private_token = ""
        self.private_error = ""
        self.app_checked = 0.0
        self.app_up = False
        self.job_base = {}           # image id -> (base url, token) it was created on

    # ------------------------------------------------------------- endpoints
    @staticmethod
    def remote_url():
        url = (os.environ.get("AIVS_URL") or os.environ.get("AVS_URL")
               or gi.env_value("AIVS_URL") or gi.env_value("AVS_URL") or "")
        return url.rstrip("/")

    @staticmethod
    def app_url():
        return "http://127.0.0.1:{}".format(gi.env_value("AIVS_LOCAL_API_PORT") or 8785)

    @staticmethod
    def app_token():
        return gi.env_value("AIVS_LOCAL_API_TOKEN") or ""

    @staticmethod
    def healthy(base, token, timeout=1.0):
        """True only when an AI Image Studio Local API answers there - not any server."""
        headers = {"Authorization": "Bearer " + token} if token else {}
        req = urllib.request.Request(base + "/api/v1/health", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8")).get("app") == APP
        except Exception:
            return False

    def _start_private(self):
        import local_api
        token = secrets.token_urlsafe(24)
        # Port 0: the OS picks a free one, so the desktop app's own port stays free.
        with contextlib.redirect_stdout(sys.stderr):
            api = local_api.start(port=0, token=token)
        base = "http://127.0.0.1:{}".format(api.port)
        for _ in range(60):
            if self.healthy(base, token, timeout=0.5):
                break
            time.sleep(0.05)
        self.private, self.private_token = api, token
        log("app not open - started a private engine on {}".format(base))

    def endpoint(self):
        """(base url, token, where) for the next call. Raises RuntimeError with the reason."""
        remote = self.remote_url()
        if remote:
            return remote, self.app_token(), "remote"
        with self.lock:
            now = time.time()
            if now - self.app_checked > APP_CHECK_TTL:
                self.app_up = self.healthy(self.app_url(), self.app_token())
                self.app_checked = now
            if self.app_up:
                return self.app_url(), self.app_token(), "app"
            if self.private is None:
                try:
                    self._start_private()
                    self.private_error = ""
                except Exception as exc:  # noqa: BLE001 - reported to the agent verbatim
                    self.private_error = "{}: {}".format(type(exc).__name__, exc)
                    log("could not start the engine: " + self.private_error)
                    raise RuntimeError(
                        "AI Image Studio's engine could not start ({}). Run `\"{}\" "
                        "mcp_server/server.py --check` in {} to see the full error."
                        .format(self.private_error, sys.executable, ROOT))
            return "http://127.0.0.1:{}".format(self.private.port), self.private_token, "private"

    def forget_app(self):
        self.app_checked = 0.0

    def stop(self):
        if self.private is not None:
            with contextlib.suppress(Exception):
                self.private.stop()
            self.private = None


BACKEND = Backend()


def request(base, token, method, path, body=None, timeout=60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + "/api/v1" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error")
        except ValueError:
            detail = exc.reason
        raise RuntimeError("AI Image Studio said {}: {}".format(exc.code, detail))
    except urllib.error.URLError as exc:
        BACKEND.forget_app()  # the app may have just closed; re-check on the next call
        raise RuntimeError("AI Image Studio's Local API is not answering at {} ({}). Try again; "
                           "if the app was just closed the next call starts the engine here."
                           .format(base, exc.reason))


def call(method, path, body=None, timeout=60):
    base, token, _where = BACKEND.endpoint()
    return request(base, token, method, path, body, timeout)


def job_call(image_id, method, suffix=""):
    """An image job lives on the engine that made it, even if the app opened since."""
    image_id = str(image_id).strip()
    base, token = BACKEND.job_base.get(image_id) or BACKEND.endpoint()[:2]
    return request(base, token, method, "/images/{}{}".format(image_id, suffix))


async def run(fn, *args, **kwargs):
    """Blocking HTTP off the event loop, so a long wait never stalls the MCP session."""
    return await asyncio.to_thread(fn, *args, **kwargs)


# --------------------------------------------------------------------------- #
# Argument helpers
# --------------------------------------------------------------------------- #
def _look(look):
    """"current" (the app's applied Look), "none", or {part: choice or phrase}."""
    if isinstance(look, str) and look.strip().startswith("{"):
        look = json.loads(look)  # some clients send an object argument as JSON text
    if look in (None, "", "none"):
        return None
    if look == "current" or isinstance(look, dict):
        return look
    raise ValueError("look must be 'current', 'none' or an object of Look parts")


def _realism(realism):
    if isinstance(realism, str):
        text = realism.strip().lower()
        if text in ("", "false", "none", "off"):
            return None
        if text in ("true", "on", "all"):
            return {}
        realism = json.loads(realism)
    if realism in (None, False):
        return None
    return {} if realism is True else realism


def _refine(refine):
    return max(0, min(MAX_REFINE, int(refine or 0)))


def _price(refine):
    tries = 1 + _refine(refine)
    credits = CREDITS_PER_TRY * tries
    return {"tries": tries, "kie_credits": credits, "usd": round(credits * CREDIT_USD, 2),
            "note": "worst case - a good first try stops Refine early" if tries > 1 else "one image"}


def _reference(item):
    path = Path(str(item)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        raise ValueError("reference not found: {} (pass a full path to an image file)".format(item))
    return {"name": path.name, "b64": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mime": mimetypes.guess_type(path.name)[0] or "image/png"}


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
async def avs_status() -> dict:
    """Is AI Image Studio up? Version, which image keys it has, whether a Look is applied,
    the realism switches it knows, whether Refine is available (needs its OpenRouter key), and
    whether this answer came from the open app or the engine this server started itself."""
    def status():
        base, token, where = BACKEND.endpoint()
        out = request(base, token, "GET", "/health")
        out["engine"] = {"app": "the open AI Image Studio app",
                         "private": "started by this MCP server (the app is closed, so "
                                    "look='current' is empty)",
                         "remote": "AIVS_URL " + base}[where]
        out["project"] = str(ROOT)
        if not any((out.get("providers") or {}).values()):
            out["setup"] = ("No image key is set. Add KIE_API_KEY to {} (copy .env.example) "
                            "or in the app's Settings.".format(ROOT / ".env"))
        return out
    return await run(status)


@mcp.tool()
async def look_options(part: Optional[str] = None) -> dict:
    """Every choice the Look section offers, as {part: {field: [{key, label, phrase}]}}.
    part narrows it to one of: style, lighting, camera, composition, posing, color, capture,
    evidence (the full list is long, so ask for one part at a time). Pass the keys to look_compose."""
    options = await run(call, "GET", "/look/options")
    if part:
        if part not in options:
            raise ValueError("part must be one of: " + ", ".join(options))
        return {part: options[part]}
    return options


@mcp.tool()
async def look_current() -> dict:
    """The Look phrases currently applied on the app's Compose form (empty strings when unset,
    and always empty while the app is closed)."""
    return await run(call, "GET", "/look/current")


@mcp.tool()
async def look_compose(choices: dict) -> dict:
    """Look choices -> the phrases the Build tabs would write, without spending anything.
    choices: {part: {field: key}} using keys from look_options, e.g.
    {"lighting": {"setup": "rembrandt"}, "camera": {"vertical": "low-angle"},
     "style": {"style": "photoreal"}}; a plain string for a part is used as the phrase itself."""
    if isinstance(choices, str):
        choices = json.loads(choices)
    return await run(call, "POST", "/look/compose", choices)


@mcp.tool()
async def prompt_preview(prompt: str, look: Union[str, dict, None] = "current",
                         realism: Union[bool, dict, None] = None) -> dict:
    """The finished prompt exactly as image_generate would send it - free, nothing generated.
    look: "current" | "none" | {part: choice}. realism: the Images section's switches - true for
    all of them, or {"subject", "action", "setting", "shot", "species", "kind", "phone", "fill",
    "<switch>": false to turn one off}. Also good for pasting into Google Flow or any tool."""
    body = {"prompt": prompt, "look": _look(look), "realism": _realism(realism)}
    return await run(call, "POST", "/prompt", body)


@mcp.tool()
async def image_generate(prompt: str, look: Union[str, dict, None] = "current",
                         realism: Union[bool, dict, None] = None, refine: int = 0,
                         aspect: str = "9:16", resolution: Optional[str] = None,
                         references: Optional[list[str]] = None, tag: str = "MCP",
                         approved: bool = False) -> dict:
    """Generate one image through AI Image Studio (Nano Banana Pro on Kie). PAID.
    Without approved=True it only returns the price and the finished prompt - show both to the
    user and call again with approved=True after they say yes.
    refine: 0-2 paid retries; the vision critique names the weak layer, it is strengthened, and
    the best attempt is kept. references: full paths to local image files (character sheets etc.).
    aspect: 9:16 | 16:9 | 1:1 | 4:5 ... resolution: 1K | 2K | 4K. Returns {id}; then image_wait."""
    price = _price(refine)
    body = {"prompt": prompt, "look": _look(look), "realism": _realism(realism),
            "refine": _refine(refine), "aspect": aspect, "tag": (tag or "MCP")[:80]}
    if resolution:
        body["resolution"] = resolution
    if not approved:
        preview = await run(call, "POST", "/prompt", {k: body[k] for k in ("prompt", "look", "realism")})
        return {"approved": False, "price": price, "prompt": preview.get("prompt"),
                "warnings": preview.get("warnings"),
                "next": "Show the user the price and prompt; call again with approved=True after a yes."}
    body["references"] = [_reference(item) for item in references or []]

    def submit():
        base, token, _where = BACKEND.endpoint()
        out = request(base, token, "POST", "/images", body)
        if out.get("id"):
            BACKEND.job_base[str(out["id"])] = (base, token)
        return out
    out = await run(submit)
    out["price"] = price
    out["next"] = "Call image_wait with this id until state is done."
    return out


@mcp.tool()
async def image_get(image_id: str) -> dict:
    """An image job: state (queued/running/done/failed/cancelled), stage, error, file (the saved
    path), attempts and the chosen one with its critique, and the realism report."""
    return await run(job_call, image_id, "GET")


@mcp.tool()
async def image_wait(image_id: str, timeout_seconds: int = WAIT_DEFAULT) -> dict:
    """Wait for an image job to finish and return it. Returns early (state still queued or
    running, finished=false) after timeout_seconds - then call image_wait again. The default
    stays under the 60 s tool limit some clients (Codex) use; a generation takes 30 s to a few
    minutes, more with refine."""
    end = time.time() + max(5, min(WAIT_MAX, int(timeout_seconds or WAIT_DEFAULT)))
    while True:
        job = await run(job_call, image_id, "GET")
        if job.get("state") in DONE_STATES:
            job["finished"] = True
            return job
        if time.time() > end:
            job["finished"] = False
            job["next"] = "Still working - call image_wait again with the same id."
            return job
        await asyncio.sleep(2)


@mcp.tool()
async def image_cancel(image_id: str) -> dict:
    """Stop an image job before its next Refine retry (the try already running still finishes)."""
    return await run(job_call, image_id, "POST", "/cancel")


# --------------------------------------------------------------------------- #
def self_check():
    """What a person runs when a client says the server failed: plain text, exit code."""
    print("AI Image Studio MCP server")
    print("  python  : {} ({})".format(sys.executable, sys.version.split()[0]))
    print("  project : {}".format(ROOT))
    try:
        base, token, where = BACKEND.endpoint()
        health = request(base, token, "GET", "/health")
    except Exception as exc:  # noqa: BLE001
        print("  engine  : FAILED - {}".format(exc))
        return 1
    print("  engine  : {} ({})".format(base, where))
    keys = ", ".join(k for k, v in (health.get("providers") or {}).items() if v) or "none"
    print("  keys    : {}{}".format(keys, "" if keys != "none" else
                                    "  <- add KIE_API_KEY to .env to generate images"))
    print("  refine  : {}".format("available" if health.get("refine") else
                                  "off (needs OPENROUTER_API_KEY)"))
    print("OK")
    BACKEND.stop()
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        sys.exit(self_check())
    try:
        mcp.run()
    finally:
        BACKEND.stop()
