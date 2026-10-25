"""Local API - lets Skit Studio use this app's image engine and Look while it is open.

The same idea as VoiceStudio's local API on port 3900: while AI Video Studio
runs, a small HTTP server on 127.0.0.1 answers Skit Studio (or any loopback
caller). Skit Studio sends its scene prompt and reference sheets; this app adds
the Look (the phrases the Look tab builds), generates through the same
generate_image.generate() the Compose tab uses, and records the result in
History tagged "Skit Studio".

Routes (all JSON unless noted):
  GET  /api/v1/health             app, version, which image keys are set
  GET  /api/v1/look/options       every Look list (lighting, camera, style, ...)
  GET  /api/v1/look/current       the Look phrases currently on the Compose form
  POST /api/v1/look/compose       Look choices -> phrases (the Build tabs' tools)
  POST /api/v1/prompt             {prompt, look} -> the finished prompt, no spend
                                  (for pasting into Google Flow or any other tool)
  POST /api/v1/images             {prompt, look, references, aspect, ...} -> {id}
  GET  /api/v1/images/<id>        {state, stage, error, file}
  GET  /api/v1/images/<id>/file   the image bytes

Loopback only. An optional bearer token (AIVS_LOCAL_API_TOKEN) is required
when set. Spending: the caller's own approval gate is the yes - Skit Studio
shows its estimate and waits for Approve before it ever calls /images.

Run headless (no window) with:  python tools/local_api.py --serve
"""
import argparse
import base64
import hmac
import json
import mimetypes
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_camera_angle as bca  # noqa: E402
import build_capture as bcap  # noqa: E402
import build_color as bcol  # noqa: E402
import build_composition as bcomp  # noqa: E402
import build_evidence as bev  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_posing as bpos  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_style as bst  # noqa: E402
import generate_image as gi  # noqa: E402
import history  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = "AI Video Studio"
VERSION = 1
DEFAULT_PORT = 8785
PORT_VAR = "AIVS_LOCAL_API_PORT"
TOKEN_VAR = "AIVS_LOCAL_API_TOKEN"
# Same ceiling as ui/workers.py MAX_CONCURRENCY - Kie throttles past it.
MAX_JOBS = 3
KEEP_JOBS = 200
# A still plus up to three reference sheets, base64'd, is a few MB; refuse anything silly.
MAX_BODY = 40 * 1024 * 1024
REF_DIR = ROOT / "temp" / "outputs" / "local_api"
HISTORY_NOTE = "Skit Studio"

# Prompt order: style leads (it sets the whole medium), the rest follow the
# scene in the order a photographer would describe a shot.
LOOK_KEYS = ("style", "lighting", "camera", "composition", "posing", "color",
             "capture", "evidence")


class LookError(ValueError):
    """A Look choice the bank does not know, named by its part."""


# --------------------------------------------------------------------------- #
# Look
# --------------------------------------------------------------------------- #
def _labels(table, phrase_field="phrase"):
    return [{"key": key, "label": cfg.get("label", key),
             "phrase": cfg.get(phrase_field, "")}
            for key, cfg in table.items()]


def look_options():
    """Every list the Look tab offers, as {part: {field: [{key, label, phrase}]}}."""
    light = bl.load_bank()
    main = bp.load_bank()
    comp = bcomp.load_bank()
    cam = bca.load_bank()
    col = bcol.load_bank()
    pos = bpos.load_bank()
    sty = bst.load_bank()
    cap = bcap.load_bank()
    evi = bev.load_bank()
    styles = [dict(item, group=cfg["group"])
              for item, cfg in zip(_labels(bst.all_styles(sty), "keywords"),
                                   bst.all_styles(sty).values())]
    return {
        "lighting": {
            "setups": _labels(bl.setups(light)),
            "directions": _labels(bl.directions(light)),
            "qualities": _labels(bl.qualities(light)),
            "sources": _labels(bl.sources(light)),
            "techniques": _labels(bl.techniques(light)),
        },
        "composition": {
            "guides": _labels(bp.guides(main)),
            "techniques": _labels(bcomp.techniques(comp)),
        },
        "camera": {
            "verticals": _labels(bca.verticals(cam)),
            "sides": _labels(bca.sides(cam)),
            "sizes": _labels(bca.sizes(cam)),
        },
        "color": {
            "moods": _labels(bcol.moods(col)),
            "film_looks": _labels(bcol.film_looks(col)),
            "techniques": _labels(bcol.techniques(col)),
        },
        "posing": {
            "poses": _labels(bpos.poses(pos)),
            "techniques": _labels(bpos.techniques(pos)),
        },
        "style": {"styles": styles},
        "capture": {group: _labels(bcap.options(cap, group))
                    for group in bcap.groups(cap)},
        "evidence": {kind: _labels(bev.options(evi, kind))
                     for kind in evi.get("kinds", {})},
    }


def _list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def compose_look(choices):
    """Look choices -> ({part: phrase}, warnings).

    Each part takes the same fields its Build tab does, e.g.
    {"lighting": {"setup": "rembrandt"}, "style": {"style": "anime-manga"}}.
    A plain string for a part is used as the phrase itself. Parts left out or
    empty are simply not in the result. Raises LookError naming the part.
    """
    phrases, warnings = {}, []
    choices = dict(choices or {})
    for part in LOOK_KEYS:
        pick = choices.get(part)
        if not pick:
            continue
        if isinstance(pick, str):
            phrases[part] = pick.strip()
            continue
        if part == "capture" and isinstance(pick, list):
            phrases[part] = ", ".join(_list(pick))
            continue
        if not isinstance(pick, dict):
            raise LookError("{}: expected an object or a phrase".format(part))
        try:
            phrase, notes = _compose_part(part, pick)
        except ValueError as exc:
            raise LookError("{}: {}".format(part, exc)) from exc
        if phrase:
            phrases[part] = phrase
        warnings.extend("{}: {}".format(part, note) for note in notes)
    return phrases, warnings


def _compose_part(part, pick):
    custom = str(pick.get("custom") or "").strip()
    if part == "lighting":
        return bl.compose_lighting(
            bl.load_bank(), pick.get("setup") or None, pick.get("direction") or None,
            pick.get("quality") or None, pick.get("source") or None,
            _list(pick.get("techniques")), custom or None)
    if part == "composition":
        return bcomp.compose_composition(
            bp.load_bank(), bcomp.load_bank(), pick.get("guide") or None, custom or None,
            _list(pick.get("techniques")))
    if part == "camera":
        return bca.compose_camera_angle(
            bca.load_bank(), pick.get("vertical") or None, pick.get("side") or None,
            pick.get("size") or None, custom or None)
    if part == "color":
        return bcol.compose_color(
            bcol.load_bank(), pick.get("mood") or None, pick.get("film_look") or None,
            custom or None, _list(pick.get("techniques")))
    if part == "posing":
        return bpos.compose_posing(
            bpos.load_bank(), pick.get("pose") or None, _list(pick.get("techniques")),
            custom or None)
    if part == "style":
        return bst.compose_style(bst.load_bank(), pick.get("style") or None, custom or None)
    if part == "capture":
        by_layer, notes = bcap.compose_capture(
            bcap.load_bank(), pick.get("film_stock") or None, _list(pick.get("optics")),
            _list(pick.get("exposure")), _list(pick.get("evidence")))
        return bcap.phrase_for(by_layer), notes
    if part == "evidence":
        return bev.compose_evidence(
            bev.load_bank(), pick.get("kind") or "animal", _list(pick.get("details")),
            custom)
    raise LookError("unknown part")


def clean_phrases(phrases):
    """{part: str} for the known parts, capture lists flattened, blanks dropped."""
    clean = {}
    for part in LOOK_KEYS:
        value = (phrases or {}).get(part)
        if isinstance(value, (list, tuple)):
            value = ", ".join(_list(value))
        value = str(value or "").strip()
        if value:
            clean[part] = value
    return clean


def assemble_prompt(base, phrases):
    """Scene prompt + Look. Style opens the prompt, the rest follow the scene.

    A trailing "No text..." sentence in `base` stays last, so the look never
    lands after the instruction the model should read as the final word.
    """
    phrases = clean_phrases(phrases)
    base = str(base or "").strip()
    tail = ""
    match = re.search(r"\s*(No text[^.]*\.?)\s*$", base)
    if match:
        tail = match.group(1)
        base = base[:match.start()].rstrip()
    parts = []
    if phrases.get("style"):
        parts.append(phrases["style"].rstrip(".") + ".")
    if base:
        parts.append(base if base.endswith(".") else base + ".")
    rest = [phrases[key].rstrip(".") for key in LOOK_KEYS[1:] if phrases.get(key)]
    if rest:
        parts.append("; ".join(rest) + ".")
    if tail:
        parts.append(tail)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Image jobs
# --------------------------------------------------------------------------- #
class Jobs:
    """In-memory job table. Jobs live as long as the app does."""

    def __init__(self, on_image=None):
        self.lock = threading.Lock()
        self.items = {}
        self.pool = ThreadPoolExecutor(max_workers=MAX_JOBS, thread_name_prefix="aivs-api")
        self.on_image = on_image

    def get(self, job_id):
        with self.lock:
            job = self.items.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id, **fields):
        with self.lock:
            self.items[job_id].update(fields)

    def submit(self, request):
        job_id = uuid.uuid4().hex[:12]
        with self.lock:
            if len(self.items) >= KEEP_JOBS:
                finished = [k for k, v in self.items.items()
                            if v["state"] in ("done", "failed")]
                for key in finished[:len(self.items) - KEEP_JOBS + 1]:
                    del self.items[key]
            self.items[job_id] = {"id": job_id, "state": "queued", "stage": "",
                                  "error": "", "file": "", "prompt": request["prompt"],
                                  "tag": request.get("tag", ""), "created": time.time()}
        self.pool.submit(self._run, job_id, request)
        return job_id

    def _run(self, job_id, request):
        self._update(job_id, state="running", stage="Starting...")
        refs = []
        try:
            REF_DIR.mkdir(parents=True, exist_ok=True)
            for n, ref in enumerate(request.get("references") or []):
                path = REF_DIR / "{}-ref{}.png".format(job_id, n)
                path.write_bytes(base64.b64decode(ref.get("b64", "")))
                refs.append(path)
            path, error = gi.generate(
                request.get("provider") or "kie", request["prompt"],
                out_name="skit-{}.png".format(job_id), references=refs,
                model=request.get("model") or None,
                on_stage=lambda message: self._update(job_id, stage=message),
                spec=request.get("spec") or {})
            if error is not None:
                self._update(job_id, state="failed", error=str(error), stage="")
            else:
                self._update(job_id, state="done", file=str(path), stage="Done")
                record_history(request, path)
        except Exception as exc:  # a bad reference or a disk error, never a crash
            self._update(job_id, state="failed", error=str(exc), stage="")
        finally:
            for ref in refs:
                try:
                    ref.unlink()
                except OSError:
                    pass
        if self.on_image:
            try:
                self.on_image(self.get(job_id))
            except Exception:
                pass

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def record_history(request, path):
    """One History row, scored by the same realism gate as any other prompt."""
    prompt = request["prompt"]
    bank = bp.load_bank()
    kind = bev.subject_kind(bev.load_bank(), request.get("base") or prompt)
    present, _missing, banned, _warn, _neg = rl.lint(prompt, bank, kind=kind)
    layers = {name: [hit] for name, _cfg, hit in present}
    spec = {"subject": (request.get("base") or prompt)[:300],
            "slug": request.get("tag") or "skit-studio", "seed": 0,
            "aspect": (request.get("spec") or {}).get("aspect", "")}
    history.append(spec, prompt, layers, len(present),
                   len(present) == 8 and not banned, image=str(path), note=HISTORY_NOTE)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def parse_prompt_request(body, current_look):
    """{prompt, look} -> (base, finished prompt, phrases, warnings). Raises ValueError."""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    base = str(body.get("prompt") or "").strip()
    if not base:
        raise ValueError("prompt is required")
    look = body.get("look")
    if look == "current":
        phrases, warnings = clean_phrases(current_look()), []
    elif isinstance(look, dict):
        phrases, warnings = compose_look(look)
    elif look in (None, "", "none"):
        phrases, warnings = {}, []
    else:
        raise ValueError("look must be 'current', an object, or null")
    phrases = clean_phrases(phrases)
    return base, assemble_prompt(base, phrases), phrases, warnings


def parse_image_request(body, current_look):
    """Validated /images body -> request dict for Jobs.submit. Raises ValueError."""
    base, prompt, phrases, warnings = parse_prompt_request(body, current_look)
    provider = body.get("provider") or "kie"
    if provider not in gi.PROVIDERS:
        raise ValueError("unknown provider: {}".format(provider))
    refs = body.get("references") or []
    if not isinstance(refs, list) or any(not isinstance(r, dict) or not r.get("b64")
                                         for r in refs):
        raise ValueError("references must be a list of {name, b64}")
    spec = {key: str(body[key]) for key in ("aspect", "resolution", "output_format")
            if body.get(key)}
    return {"base": base, "prompt": prompt, "look": phrases,
            "warnings": warnings, "provider": provider, "model": body.get("model"),
            "references": refs, "spec": spec, "tag": str(body.get("tag") or "")[:80]}


def make_handler(jobs, current_look, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, payload):
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self):
            if not token:
                return True
            if hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return True
            self._send(401, {"error": "missing or wrong token"})
            return False

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("request body over {} MB".format(MAX_BODY // (1024 * 1024)))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/v1/health":
                env = gi.read_env()
                providers = {name: not gi.missing_credentials(
                    cfg, *gi.credentials(cfg, env)) for name, cfg in gi.PROVIDERS.items()}
                return self._send(200, {"app": APP, "version": VERSION,
                                        "providers": providers,
                                        "look_current": bool(clean_phrases(current_look()))})
            if path == "/api/v1/look/options":
                return self._send(200, look_options())
            if path == "/api/v1/look/current":
                phrases = clean_phrases(current_look())
                return self._send(200, {key: phrases.get(key, "") for key in LOOK_KEYS})
            match = re.fullmatch(r"/api/v1/images/([0-9a-f]+)(/file)?", path)
            if match:
                job = jobs.get(match.group(1))
                if not job:
                    return self._send(404, {"error": "no such image job"})
                if not match.group(2):
                    return self._send(200, {k: job[k] for k in
                                            ("id", "state", "stage", "error", "file", "prompt")})
                if job["state"] != "done":
                    return self._send(409, {"error": "image not ready"})
                data = Path(job["file"]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type",
                                 mimetypes.guess_type(job["file"])[0] or "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            try:
                body = self._body()
            except (ValueError, UnicodeDecodeError) as exc:
                return self._send(400, {"error": "body is not valid JSON"
                                        if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError))
                                        else str(exc)})
            try:
                if path == "/api/v1/look/compose":
                    phrases, warnings = compose_look(body)
                    return self._send(200, {"phrases": phrases, "warnings": warnings})
                if path == "/api/v1/prompt":
                    _base, prompt, phrases, warnings = parse_prompt_request(body, current_look)
                    return self._send(200, {"prompt": prompt, "look": phrases,
                                            "warnings": warnings})
                if path == "/api/v1/images":
                    request = parse_image_request(body, current_look)
                    job_id = jobs.submit(request)
                    return self._send(202, {"id": job_id, "prompt": request["prompt"],
                                            "warnings": request["warnings"]})
            except ValueError as exc:
                return self._send(400, {"error": str(exc)})
            self._send(404, {"error": "not found"})

    return Handler


class LocalApi:
    """The running server. start() returns it; stop() closes it."""

    def __init__(self, server, jobs, thread):
        self.server, self.jobs, self.thread = server, jobs, thread

    @property
    def port(self):
        return self.server.server_address[1]

    def stop(self):
        # A job still running finishes on its own thread; it must not call back into a
        # window that is closing.
        self.jobs.on_image = None
        self.server.shutdown()
        self.server.server_close()
        self.jobs.shutdown()


def configured_port():
    value = gi.env_value(PORT_VAR) or ""
    try:
        return int(value) if value.strip() else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def start(port=None, current_look=None, on_image=None, token=None):
    """Start serving on 127.0.0.1. Raises OSError if the port is taken."""
    port = configured_port() if port is None else port
    token = gi.env_value(TOKEN_VAR) if token is None else token
    jobs = Jobs(on_image)
    handler = make_handler(jobs, current_look or (lambda: {}), token or "")
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                              name="aivs-local-api")
    thread.start()
    return LocalApi(server, jobs, thread)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--serve", action="store_true",
                        help="run headless until Ctrl+C (no current look - no window)")
    parser.add_argument("--port", type=int, default=None,
                        help="port (default {} or {})".format(PORT_VAR, DEFAULT_PORT))
    parser.add_argument("--options", action="store_true", help="print the Look lists")
    args = parser.parse_args(argv)
    if args.options:
        print(json.dumps(look_options(), indent=2, ensure_ascii=False))
        return 0
    if args.serve:
        api = start(args.port)
        print("AI Video Studio local API on http://127.0.0.1:{}".format(api.port), flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            api.stop()
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
