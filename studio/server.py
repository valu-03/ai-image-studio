"""FastAPI backend for the one-page photo studio.

Spending happens only in POST /api/photos (Make) and POST /api/photos/{id}/fix
(Fix); no GET route ever spends. Realism comes from photography only: saved
files are exactly what the provider returned.

    python -m studio.server --port 8791 [--static web/dist]
"""

import argparse
import base64
import binascii
import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import build_evidence as bev  # noqa: E402
import generate_image as gi  # noqa: E402
import giveaways  # noqa: E402
import history  # noqa: E402
import local_api  # noqa: E402
import look_cards  # noqa: E402
import pricing  # noqa: E402
from studio import compose_spec  # noqa: E402
from studio.state import LookState  # noqa: E402

KEY_NAMES = ("KIE_API_KEY", "HIGGSFIELD_API_KEY_ID", "HIGGSFIELD_API_KEY_SECRET",
             "OPENROUTER_API_KEY")
PROVIDER_VAR = "STUDIO_PROVIDER"
LOCAL_API_VAR = "STUDIO_LOCAL_API"
PAGE_NOTE = "Studio"
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
AVOID_LAST = 5
MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF8", b"BM")


def _bad(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def _validate_reference(b64):
    """Decoded bytes, or a 400 in plain words - before anything is spent."""
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        _bad("That reference file couldn't be read. Pick a PNG, JPEG or WebP photo.")
    if len(data) > MAX_REFERENCE_BYTES:
        _bad("That reference is bigger than 20 MB. Pick a smaller photo.")
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        _bad("HEIC photos aren't supported. Export it as a JPEG or PNG and try again.")
    ok = any(data.startswith(m) for m in MAGIC) or \
        (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    if not ok:
        _bad("That reference isn't a picture we can use. Pick a PNG, JPEG or WebP photo.")
    return data


def _fake_ask(prompt, images=(), model=None, **_):
    """Canned vision reply for tests and screenshots (STUDIO_FAKE_ASK=1)."""
    keys = re.findall(r"^- (\w+):", prompt, flags=re.M)
    reply = {k: {"seen": i == 0, "where": "in the background" if i == 0 else ""}
             for i, k in enumerate(keys)}
    return json.dumps(reply), None


def create_app(static_dir, state):
    jobs_lock = threading.Lock()
    metas = {}
    session_seed = int(time.time()) % 100000
    app = FastAPI(title="AI Image Studio - photo studio")
    app.state.ask = _fake_ask if os.environ.get("STUDIO_FAKE_ASK") == "1" else None
    # The desktop shell reports the Skit Studio connection here.
    app.state.local_api = {"running": False, "error": ""}

    # ---------------------------------------------------------------- helpers
    def avoid_states():
        out = []
        for entry in history.recent(60):
            if entry.get("note") == PAGE_NOTE:
                cards = (entry.get("look") or {}).get("cards")
                if cards:
                    out.append(cards)
            if len(out) >= AVOID_LAST:
                break
        return out

    def reset_state(kind):
        state.reset(kind, session_seed, avoid=avoid_states(),
                    weights=history.card_weights())

    def look_payload():
        snap = state.snapshot()
        return {"kind": snap["kind"], "cards": snap["cards"], "touched": snap["touched"],
                "overrides": snap.get("overrides", {})}

    def image_url(path):
        return "/files/" + Path(path).name

    def in_images_dir(path):
        try:
            return Path(path).resolve().parent == gi.OUT_DIR.resolve()
        except OSError:
            return False

    def run_check(image_path, kind, reference):
        ref_path = None
        try:
            if reference:
                fd, ref_path = tempfile.mkstemp(suffix=".png", prefix="studio-ref-")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(reference)
            return giveaways.check(image_path, kind, reference_path=ref_path,
                                   ask=app.state.ask)
        except Exception as exc:  # a check must never take the photo down
            return None, "The picture check couldn't run: {}".format(exc)
        finally:
            if ref_path:
                try:
                    os.unlink(ref_path)
                except OSError:
                    pass

    def on_image(job):
        """Runs in the job thread once generation ended: check a finished photo."""
        with jobs_lock:
            meta = metas.get(job["id"])
        if meta is None:
            return
        if job["state"] == "done":
            found, error = run_check(job["file"], meta["kind"], meta["reference"])
            meta["giveaways"], meta["check_error"] = found, error or ""
        meta["finished"] = True

    jobs = local_api.Jobs(on_image=on_image)

    def submit_page_job(text, provider, reference, kind, cards, extra):
        """Build, register and submit one job; 409 if one is already running."""
        merged_look = dict(look_cards.to_look(cards, kind))
        merged_look.update(state.snapshot().get("overrides", {}))
        body = {"prompt": text, "look": merged_look,
                "realism": {"subject": text}, "refine": 0,
                "tag": "page-{}".format(session_seed), "provider": provider}
        if reference:
            body["references"] = [{"name": "reference.png",
                                   "b64": base64.b64encode(reference).decode()}]
        try:
            request = local_api.parse_image_request(body, state.current_phrases)
        except ValueError as exc:
            _bad(str(exc))
        if extra:
            request["prompt"] = local_api.insert_before_tail(request["prompt"], extra)
        request["history_note"] = PAGE_NOTE
        request["studio_look"] = {"kind": kind, "cards": dict(cards)}
        with jobs_lock:
            if any(not m["finished"] for m in metas.values()):
                return JSONResponse({"error": "busy"}, status_code=409)
            job_id = jobs.submit(request)
            metas[job_id] = {"finished": False, "kind": kind, "cards": dict(cards),
                             "text": text, "provider": provider, "reference": reference,
                             "giveaways": None, "check_error": ""}
        return {"id": job_id}

    def chosen_provider(requested):
        provider = requested or gi.env_value(PROVIDER_VAR) or gi.DEFAULT_PROVIDER
        if provider not in gi.PROVIDERS:
            _bad("Unknown provider: {}".format(provider))
        return provider

    # ------------------------------------------------------------------ look
    @app.get("/api/cards")
    def get_cards(kind: str = Query(...)):
        try:
            return look_cards.cards(kind)
        except ValueError as exc:
            _bad(str(exc))

    @app.post("/api/describe")
    def describe(body: dict):
        text = str(body.get("text") or "")
        kind = bev.subject_kind(bev.load_bank(), text)
        if kind != state.kind:
            reset_state(kind)
        return {"kind": kind}

    @app.get("/api/look")
    def get_look():
        return look_payload()

    @app.put("/api/look")
    def put_look(body: dict):
        try:
            state.set_card(str(body.get("card") or ""), str(body.get("option") or ""))
        except ValueError as exc:
            _bad(str(exc))
        return look_payload()

    @app.get("/api/look/options")
    def get_look_options():
        return local_api.look_options()

    @app.post("/api/look/compose")
    def post_look_compose(body: dict):
        choices = body.get("choices")
        if choices is None:
            part = str(body.get("part") or "")
            pick = body.get("pick") or {}
            choices = {part: pick} if part else {}
        try:
            phrases, warnings = local_api.compose_look(choices)
        except local_api.LookError as exc:
            _bad(str(exc))
        if body.get("apply"):
            for part_key in choices:
                if part_key in local_api.LOOK_KEYS:
                    state.set_override(part_key, phrases.get(part_key, ""))
        return {"phrases": phrases, "warnings": warnings, "look": look_payload()}

    @app.put("/api/look/override")
    def put_look_override(body: dict):
        part = str(body.get("part") or "")
        if part not in local_api.LOOK_KEYS:
            _bad("Unknown Look part: {}".format(part))
        state.set_override(part, str(body.get("phrase") or ""))
        return look_payload()

    # --------------------------------------------------------------- compose
    @app.get("/api/compose/options")
    def get_compose_options():
        return compose_spec.compose_options()

    @app.post("/api/compose/preview")
    def post_compose_preview(body: dict):
        form = body.get("form") if isinstance(body.get("form"), dict) else body
        return compose_spec.build_spec_and_preview(
            form, state.snapshot().get("overrides")
        )

    # ----------------------------------------------------------------- price
    @app.get("/api/price")
    def get_price(provider: str = "kie"):
        return pricing.photo_price(chosen_provider(provider))

    # ---------------------------------------------------------------- photos
    @app.post("/api/photos")
    def make_photo(body: dict):
        form = body.get("form") if isinstance(body.get("form"), dict) else None
        if form is not None and not body.get("text"):
            subj = str(form.get("subject") or "").strip()
            if not subj:
                _bad("Describe the subject first.")
            preview = compose_spec.build_spec_and_preview(
                form, state.snapshot().get("overrides")
            )
            text = preview["prompt"]
        else:
            text = str(body.get("text") or "").strip()
        if not text:
            _bad("Describe the photo first.")
        provider = chosen_provider(body.get("provider"))
        reference = None
        if body.get("reference_b64"):
            if not gi.PROVIDERS[provider].get("references"):
                _bad("{} can't use a reference photo. Switch provider or remove it.".format(
                    gi.PROVIDERS[provider]["label"]))
            reference = _validate_reference(body["reference_b64"])
        kind = bev.subject_kind(bev.load_bank(), text)
        if kind != state.kind:
            reset_state(kind)
        snap = state.snapshot()
        return submit_page_job(text, provider, reference, kind, snap["cards"], snap["extra"])

    @app.get("/api/photos/{photo_id}")
    def get_photo(photo_id: str):
        job = jobs.get(photo_id)
        with jobs_lock:
            meta = metas.get(photo_id)
        if job is None or meta is None:
            _bad("No such photo.", 404)
        out = {"state": "running", "stage": job["stage"], "error": "", "file_url": None,
               "history_id": None, "giveaways": None, "check_error": ""}
        if job["state"] == "failed" and meta["finished"]:
            out.update(state="error", stage="", error=job["error"])
        elif job["state"] == "done":
            out["file_url"] = image_url(job["file"])
            attempts = job.get("attempts") or []
            if attempts:
                out["history_id"] = attempts[(job.get("chosen") or 1) - 1].get("history_id")
            if meta["finished"]:
                out.update(state="done", stage="Done", giveaways=meta["giveaways"],
                           check_error=meta["check_error"])
            else:
                out["stage"] = "Checking how real it looks..."
        return out

    @app.post("/api/photos/{photo_id}/fix")
    def fix_photo(photo_id: str, body: dict):
        key = str(body.get("giveaway") or "")
        with jobs_lock:
            meta = metas.get(photo_id)
        if meta is None:
            _bad("No such photo.", 404)
        bank = giveaways.load_bank()["giveaways"]
        if key not in bank or not (bank[key]["fix"] or bank[key]["fix_phrase"]):
            _bad("That one can't be fixed automatically.")
        with jobs_lock:
            if any(not m["finished"] for m in metas.values()):
                return JSONResponse({"error": "busy"}, status_code=409)
        kind = meta["kind"]
        if state.kind != kind:
            reset_state(kind)
            for card, option in meta["cards"].items():
                state.set_card(card, option, deliberate=False)
        new_cards, phrase = look_cards.apply_fix(state.snapshot()["cards"], key, kind)
        for card, option in new_cards.items():
            if state.snapshot()["cards"].get(card) != option:
                state.set_card(card, option)
        state.add_extra(phrase)
        snap = state.snapshot()
        return submit_page_job(meta["text"], meta["provider"], meta["reference"], kind,
                               snap["cards"], snap["extra"])

    @app.post("/api/photos/{photo_id}/rate")
    def rate_photo(photo_id: str, body: dict):
        thumb = body.get("thumb")
        if thumb not in history.THUMBS:
            _bad("thumb must be 'up' or 'down'.")
        job = jobs.get(photo_id)
        attempts = (job or {}).get("attempts") or []
        hist_id = attempts[0].get("history_id") if attempts and attempts[0].get("history_id") else photo_id
        entry = history.rate(hist_id, history.THUMBS[thumb])
        if entry is None:
            _bad("No such photo.", 404)
        return {"history_id": entry["id"], "rating": entry["rating"]}

    @app.get("/api/recent")
    def get_recent():
        out = []
        for entry in history.recent(30):
            if not in_images_dir(entry["image"]):
                continue
            out.append({"history_id": entry["id"], "file_url": image_url(entry["image"]),
                        "note": entry.get("note", ""), "rating": entry.get("rating"),
                        "source": "page" if entry.get("note") == PAGE_NOTE else "api"})
        return out

    @app.post("/api/recent/{history_id}/check")
    def check_recent(history_id: str):
        entry = next((e for e in history.recent(200) if e["id"] == history_id), None)
        if entry is None or not in_images_dir(entry["image"]):
            _bad("No such photo.", 404)
        kind = (entry.get("look") or {}).get("kind") or bev.subject_kind(
            bev.load_bank(), entry.get("subject") or entry.get("prompt", ""))
        found, error = run_check(entry["image"], kind, None)
        return {"giveaways": found, "check_error": error or ""}

    @app.get("/files/{name}")
    def get_file(name: str):
        folder = gi.OUT_DIR.resolve()
        path = (folder / name).resolve()
        if path.parent != folder or not path.is_file():
            _bad("Not found.", 404)
        return FileResponse(path)

    # -------------------------------------------------------------- settings
    @app.get("/api/settings")
    def get_settings():
        env = gi.read_env()
        status = app.state.local_api
        return {"keys": {name: bool(gi.env_value(name, env)) for name in KEY_NAMES},
                "provider": gi.env_value(PROVIDER_VAR, env) or gi.DEFAULT_PROVIDER,
                "local_api": {"enabled": gi.env_value(LOCAL_API_VAR, env) != "0",
                              "running": bool(status.get("running")),
                              "error": str(status.get("error") or "")}}

    @app.put("/api/settings/key")
    def put_key(body: dict):
        name = body.get("name")
        if name not in KEY_NAMES:
            _bad("That isn't one of the keys this page can set.")
        gi.write_env_value(name, str(body.get("value") or "").strip())
        return {"name": name, "set": bool(gi.env_value(name))}

    @app.put("/api/settings")
    def put_settings(body: dict):
        if body.get("provider") is not None:
            gi.write_env_value(PROVIDER_VAR, chosen_provider(body["provider"]))
        if body.get("local_api_enabled") is not None:
            gi.write_env_value(LOCAL_API_VAR, "1" if body["local_api_enabled"] else "0")
        return get_settings()

    app.state.jobs = jobs
    app.state.look = state

    if static_dir:
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


def dev_app():
    return create_app(None, LookState())


def main(argv=None):
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--static", help="folder to serve at / (web/dist)")
    args = parser.parse_args(argv)
    static = Path(args.static) if args.static else None
    uvicorn.run(create_app(static, LookState()), host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
