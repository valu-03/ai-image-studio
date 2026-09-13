"""Generate a real ElevenLabs sound effect from a prompt.

Usage:
    python tools/generate_sound.py --text "torch flame crackling in a temple hallway"
    python tools/generate_sound.py --text "..." --duration 3 --out torch.mp3
    python tools/generate_sound.py --text "..." --dry-run
    python tools/generate_sound.py --text "a sword" --force     # skip the sound_lint gate

Needs ELEVENLABS_API_KEY in .env.                 ->  https://elevenlabs.io/app/settings/api-keys

ElevenLabs' sound-generation endpoint is synchronous - one POST, audio bytes straight
back - unlike the image/video providers this project also talks to, which are all
submit-then-poll. So this module has no job/poll machinery at all.

By default a prompt must pass tools/sound_lint.py (the same gate the Sound tab's
Compose form already scores against) before a generation is spent - the same
"score before you spend a generation" discipline realism_lint.py enforces for
images. Pass --force / force=True to generate anyway; the score is still reported.

This module owns the shared ElevenLabs transport (headers, the binary-response POST,
error parsing, multipart encoding, saving audio) that tools/generate_speech.py and
tools/elevenlabs_voices.py both import rather than duplicate - the same relationship
generate_video.py already has with generate_image.py.

Key values are never printed, logged, or written to temp/. Standard library only.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402  (shared transport: env, User-Agent, error parsing)
import sound_lint as sl  # noqa: E402

OUT_DIR = ROOT / "temp" / "outputs" / "sound"

KEY_VAR = "ELEVENLABS_API_KEY"
WHERE = "https://elevenlabs.io/app/settings/api-keys"
BASE = "https://api.elevenlabs.io"
TIMEOUT = 120
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# ElevenLabs' documented range for sound-generation's optional duration parameter.
MIN_DURATION = 0.5
MAX_DURATION = 22.0


class GenerationError(Exception):
    """Carries the exit code the CLI should return."""

    def __init__(self, message, code=3):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Shared transport - every ElevenLabs call in this project goes through this.
# --------------------------------------------------------------------------- #
def headers(key, content_type="application/json"):
    h = {"xi-api-key": key, "User-Agent": gi.USER_AGENT}
    if content_type:
        h["Content-Type"] = content_type
    return h


def _send(url, data, hdrs, method="POST"):
    """POST/DELETE and return (status, content_type, raw_bytes).

    Unlike generate_image.py's _send, this never assumes the body is JSON - a
    successful ElevenLabs response IS audio bytes, not a parsed object.
    """
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with gi.open_with_retry(request, TIMEOUT, url) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_AUDIO_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        content_type = (exc.headers.get("Content-Type", "") if exc.headers else "")
        raw = exc.read()
        status = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach {}: {}".format(url, exc.reason))
    return status, content_type, raw


def get_json(url, hdrs):
    request = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with gi.open_with_retry(request, TIMEOUT, url) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach {}: {}".format(url, exc.reason))
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, None


def api_error(raw, fallback_status=None):
    """The human-readable message out of an ElevenLabs error body.

    ElevenLabs' error shape is `{"detail": {"status": "...", "message": "..."}}`
    or plainly `{"detail": "..."}` - neither matches generate_image.py's error
    fields exactly, so this is its own small parser rather than a bent reuse.
    """
    text = (raw or b"")
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:400] or "HTTP {}".format(fallback_status)
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        return detail.get("message") or detail.get("status") or json.dumps(detail)[:400]
    if isinstance(detail, str):
        return detail
    return gi.describe_api_error(payload, text)


def build_multipart(fields, files):
    """(content_type, body_bytes) for a multipart/form-data request.

    Only tools/elevenlabs_voices.py's clone_voice() needs this - voice samples
    are files, and ElevenLabs' /v1/voices/add takes them as a real upload, not
    base64 in a JSON body the way Kie's reference images are sent.
    """
    boundary = "----AIVideoStudio{}".format(uuid.uuid4().hex)
    parts = []
    for name, value in fields.items():
        if value is None:
            continue
        parts.append((
            "--{}\r\nContent-Disposition: form-data; name=\"{}\"\r\n\r\n{}\r\n"
        ).format(boundary, name, value).encode("utf-8"))
    for field_name, filename, data, mime in files:
        parts.append((
            "--{}\r\nContent-Disposition: form-data; name=\"{}\"; filename=\"{}\"\r\n"
            "Content-Type: {}\r\n\r\n"
        ).format(boundary, field_name, filename, mime).encode("utf-8") + data + b"\r\n")
    parts.append("--{}--\r\n".format(boundary).encode("utf-8"))
    return "multipart/form-data; boundary={}".format(boundary), b"".join(parts)


def save_audio(data, content_type, out_dir, prefix, out_name=None):
    ext = ".mp3"
    if "wav" in content_type:
        ext = ".wav"
    elif "ogg" in content_type:
        ext = ".ogg"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = out_name or "{}-{}{}".format(prefix, datetime.now().strftime("%Y%m%d-%H%M%S"), ext)
    if not Path(name).suffix:
        name += ext
    path = out_dir / name
    path.write_bytes(data)
    return path


def missing_key_error(dry_run):
    key = gi.env_value(KEY_VAR)
    if key or dry_run:
        return key, None
    return key, GenerationError(
        "{} not set in {} - cannot reach ElevenLabs.\nGet a key at {}".format(
            KEY_VAR, gi.ENV_PATH, WHERE), 1)


# --------------------------------------------------------------------------- #
# Sound effects
# --------------------------------------------------------------------------- #
def score_effect(text):
    """(passed, got, total, results) against sound_lint - the same gate the
    Sound tab's Compose form already scores against."""
    bank = sl.load_bank()
    results = sl.lint(bank, text)
    got, total = sl.score(results)
    return got == total, got, total, results


def generate_effect(text, duration_seconds=None, prompt_influence=0.3, out_name=None,
                     dry_run=False, force=False, on_stage=None, base=None):
    """Effect prompt -> saved audio path. Returns (path, error); one is None.

    Gated on sound_lint by default: a prompt that names an object rather than
    an event, asks for music/speech, or runs long is refused before a
    generation is spent. `force=True` skips the gate deliberately - the score
    is still computed and reported through the error path if it fails, so a
    forced call is never silent about what it overrode.
    """
    def stage(message):
        if on_stage:
            on_stage(message)

    passed, got, total, results = score_effect(text)
    if not passed and not force:
        failures = "; ".join(d for _, _, ok, d in results if not ok)
        return None, GenerationError(
            "This effect prompt scores {}/{} on sound_lint: {}\nFix it, or generate with "
            "force=True (--force on the CLI) to send it anyway.".format(got, total, failures), 3)

    key, error = missing_key_error(dry_run)
    if error:
        return None, error

    body = {"text": text}
    if duration_seconds is not None:
        clamped = max(MIN_DURATION, min(MAX_DURATION, float(duration_seconds)))
        body["duration_seconds"] = clamped
    if prompt_influence is not None:
        body["prompt_influence"] = max(0.0, min(1.0, float(prompt_influence)))

    url = "{}/v1/sound-generation".format((base or BASE).rstrip("/"))
    hdrs = headers(key or "DRY-RUN")

    if dry_run:
        return None, None

    stage("Generating effect...")
    try:
        status, content_type, raw = _send(url, json.dumps(body).encode("utf-8"), hdrs)
    except RuntimeError as exc:
        return None, GenerationError(str(exc), 3)

    if status >= 400 or not content_type.startswith("audio/"):
        return None, GenerationError(
            "ElevenLabs error {}: {}".format(status, api_error(raw, status)), 3)
    if not raw:
        return None, GenerationError("ElevenLabs returned an empty sound effect.", 4)

    return save_audio(raw, content_type, OUT_DIR, "sfx", out_name), None


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Generate a real ElevenLabs sound effect.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--text", required=True, help="the effect prompt")
    p.add_argument("--duration", type=float, help="seconds (0.5-22); left to the model if unset")
    p.add_argument("--prompt-influence", type=float, default=0.3,
                    help="0-1, how literally to follow the prompt (default 0.3)")
    p.add_argument("--out", help="output filename inside temp/outputs/sound/")
    p.add_argument("--force", action="store_true", help="generate even if sound_lint fails")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument("--dry-run", action="store_true",
                    help="score and describe the request without sending it or needing a key")
    return p.parse_args(argv)


def _resolve_base(base):
    return base or gi.env_value("AIVS_API_BASE") or BASE


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    base = _resolve_base(args.base_url)

    passed, got, total, results = score_effect(args.text)
    print("sound_lint: {}/{}".format(got, total), file=sys.stderr)
    for _, label, ok, detail in results:
        if not ok:
            print("  [gate] {}: {}".format(label, detail), file=sys.stderr)

    if args.dry_run:
        print("Would POST {}/v1/sound-generation".format(base))
        print("text: {}".format(args.text))
        if args.duration:
            print("duration_seconds: {}".format(args.duration))
        print("prompt_influence: {}".format(args.prompt_influence))
        return 0 if (passed or args.force) else 3

    path, error = generate_effect(
        args.text, duration_seconds=args.duration, prompt_influence=args.prompt_influence,
        out_name=args.out, force=args.force, base=base,
        on_stage=lambda message: print(message, file=sys.stderr),
    )
    if error:
        print(str(error), file=sys.stderr)
        return error.code

    print("[sound] {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
