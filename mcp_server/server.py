"""AI Image Studio MCP server - lets Codex, Claude or any MCP client use the Images and Look sections.

    python mcp_server/server.py                 # stdio

Register it:

    codex:   [mcp_servers.ai-image-studio] in ~/.codex/config.toml
             command = python, args = ["<project>/mcp_server/server.py"]
    claude:  claude mcp add ai-image-studio -- python "<project>/mcp_server/server.py"

A thin client of the Local API (tools/local_api.py, http://127.0.0.1:8785 by default;
AIVS_LOCAL_API_PORT to change, AIVS_LOCAL_API_TOKEN sent when set). It holds no image
logic: the open app's Look, the Images tab's free realism switches and its paid Refine
all run inside AI Image Studio, and every image lands in its History. The app must be
open with the Local API on (Settings), or run headless: python tools/local_api.py --serve

Spending: image_generate costs Kie credits (Nano Banana Pro, ~24 credits = ~$0.12 per
try; Refine adds up to 2 more tries). It refuses to run until `approved=True`, which an
agent may only pass after the user said yes to the price it showed.
"""

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import generate_image as gi  # noqa: E402  (.env reader, for the port and token)

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

CREDITS_PER_TRY = 24      # tools/pricing.json nano-banana-pro
CREDIT_USD = 0.005
MAX_REFINE = 2
LOOK_PARTS = ("style", "lighting", "camera", "composition", "posing", "color", "capture", "evidence")

INSTRUCTIONS = """You drive AI Image Studio's image engine: its Look section (lighting, camera,
composition, posing, color, style, capture, evidence) and its Images section (the free realism
switches that make a prompt read as a real photo, and the paid Refine that retries the weak
layer). Start with avs_status. Build the look with look_options / look_compose (or use the
Look currently applied in the app with look="current"), preview the finished prompt with
prompt_preview (free), then image_generate. image_generate spends Kie credits: show the user
the price it reports and only call it again with approved=True after an explicit yes.
Then image_wait gives the saved file path."""

mcp = _Server("ai-image-studio", instructions=INSTRUCTIONS)


def base_url():
    url = os.environ.get("AVS_URL") or gi.env_value("AVS_URL")
    if url:
        return url.rstrip("/")
    return "http://127.0.0.1:{}".format(gi.env_value("AIVS_LOCAL_API_PORT") or 8785)


def call(method, path, body=None, timeout=60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    token = gi.env_value("AIVS_LOCAL_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base_url() + "/api/v1" + path, data=data, headers=headers, method=method)
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
        raise RuntimeError("AI Image Studio's Local API is not answering at {} ({}). Open the app "
                           "(Settings > Local API on) or run `python tools/local_api.py --serve`."
                           .format(base_url(), exc.reason))


def _look(look):
    """"current" (the app's applied Look), "none", or {part: choice or phrase}."""
    if look in (None, "", "none"):
        return None
    if look == "current" or isinstance(look, dict):
        return look
    raise ValueError("look must be 'current', 'none' or an object of Look parts")


def _realism(realism):
    if realism in (None, False):
        return None
    return {} if realism is True else realism


def _price(refine):
    tries = 1 + max(0, min(MAX_REFINE, int(refine or 0)))
    credits = CREDITS_PER_TRY * tries
    return {"tries": tries, "kie_credits": credits, "usd": round(credits * CREDIT_USD, 2),
            "note": "worst case - a good first try stops Refine early" if tries > 1 else "one image"}


@mcp.tool()
def avs_status() -> dict:
    """Is AI Image Studio up? Version, which image keys it has, whether a Look is applied,
    the realism switches it knows and whether Refine is available (needs its OpenRouter key)."""
    return call("GET", "/health")


@mcp.tool()
def look_options(part: Optional[str] = None) -> dict:
    """Every choice the Look section offers, as {part: {field: [{key, label, phrase}]}}.
    part narrows it to one of: style, lighting, camera, composition, posing, color, capture,
    evidence (the full list is long). Pass the keys to look_compose."""
    options = call("GET", "/look/options")
    if part:
        if part not in options:
            raise ValueError("part must be one of: " + ", ".join(options))
        return {part: options[part]}
    return options


@mcp.tool()
def look_current() -> dict:
    """The Look phrases currently applied on the app's Compose form (empty strings when unset)."""
    return call("GET", "/look/current")


@mcp.tool()
def look_compose(choices: dict) -> dict:
    """Look choices -> the phrases the Build tabs would write, without spending anything.
    choices: {part: {field: key}} using keys from look_options, e.g.
    {"lighting": {"setup": "rembrandt"}, "camera": {"vertical": "low-angle"},
     "style": {"style": "photoreal"}}; a plain string for a part is used as the phrase itself."""
    return call("POST", "/look/compose", choices)


@mcp.tool()
def prompt_preview(prompt: str, look: Optional[object] = "current", realism: Optional[object] = None) -> dict:
    """The finished prompt exactly as image_generate would send it - free, nothing generated.
    look: "current" | "none" | {part: choice}. realism: the Images section's switches - true for
    all of them, or {"subject", "action", "setting", "shot", "species", "kind", "phone", "fill",
    "<switch>": false to turn one off}. Also good for pasting into Google Flow or any tool."""
    return call("POST", "/prompt", {"prompt": prompt, "look": _look(look), "realism": _realism(realism)})


@mcp.tool()
def image_generate(prompt: str, look: Optional[object] = "current", realism: Optional[object] = None,
                   refine: int = 0, aspect: str = "9:16", resolution: Optional[str] = None,
                   references: Optional[list] = None, tag: str = "Codex",
                   approved: bool = False) -> dict:
    """Generate one image through AI Image Studio (Nano Banana Pro on Kie). PAID.
    Without approved=True it only returns the price and the finished prompt - show both to the
    user and call again with approved=True after they say yes.
    refine: 0-2 paid retries; the vision critique names the weak layer, it is strengthened, and
    the best attempt is kept. references: local image file paths (character sheets etc.).
    aspect: 9:16 | 16:9 | 1:1 | 4:5 ... resolution: 1K | 2K | 4K. Returns {id}; then image_wait."""
    price = _price(refine)
    body = {"prompt": prompt, "look": _look(look), "realism": _realism(realism),
            "refine": max(0, min(MAX_REFINE, int(refine or 0))), "aspect": aspect, "tag": tag[:80]}
    if resolution:
        body["resolution"] = resolution
    if not approved:
        preview = call("POST", "/prompt", {k: body[k] for k in ("prompt", "look", "realism")})
        return {"approved": False, "price": price, "prompt": preview.get("prompt"),
                "warnings": preview.get("warnings"),
                "next": "Show the user the price and prompt; call again with approved=True after a yes."}
    refs = []
    for item in references or []:
        path = Path(item)
        if not path.is_file():
            raise ValueError("reference not found: {}".format(item))
        refs.append({"name": path.name, "b64": base64.b64encode(path.read_bytes()).decode("ascii"),
                     "mime": mimetypes.guess_type(path.name)[0] or "image/png"})
    body["references"] = refs
    out = call("POST", "/images", body)
    out["price"] = price
    return out


@mcp.tool()
def image_get(image_id: str) -> dict:
    """An image job: state (queued/running/done/failed/cancelled), stage, error, file (the saved
    path), attempts and the chosen one with its critique, and the realism report."""
    return call("GET", "/images/{}".format(image_id))


@mcp.tool()
def image_wait(image_id: str, timeout_seconds: int = 600) -> dict:
    """Wait for an image job to finish (done, failed or cancelled) and return it."""
    end = time.time() + max(5, min(1800, timeout_seconds))
    while True:
        job = call("GET", "/images/{}".format(image_id))
        if job.get("state") in ("done", "failed", "cancelled") or time.time() > end:
            return job
        time.sleep(2)


@mcp.tool()
def image_cancel(image_id: str) -> dict:
    """Stop an image job before its next Refine retry (the try already running still finishes)."""
    return call("POST", "/images/{}/cancel".format(image_id))


if __name__ == "__main__":
    mcp.run()
