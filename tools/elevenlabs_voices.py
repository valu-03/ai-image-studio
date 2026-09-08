"""List, clone and delete ElevenLabs voices.

Usage:
    python tools/elevenlabs_voices.py --list
    python tools/elevenlabs_voices.py --clone --name "Narrator" --sample take1.wav \
        --sample take2.wav --consent
    python tools/elevenlabs_voices.py --delete <voice_id>
    python tools/elevenlabs_voices.py --list --dry-run

Needs ELEVENLABS_API_KEY in .env.                 ->  https://elevenlabs.io/app/settings/api-keys

Reuses tools/generate_sound.py's transport (headers, error parsing, multipart
encoding) - the same relationship generate_speech.py has to it.

Cloning a real person's voice without their consent is the one genuine misuse
risk anywhere in this project's ElevenLabs integration - unlike a prompt that
comes back merely bad, a clone made without the right to make it has a
real-world consequence for someone who is not the user of this app. clone_voice()
therefore REFUSES to run without an explicit `consented=True` argument, enforced
in this module - not only as a GUI checkbox a script could bypass, but as a
condition the function itself checks and will not skip.

Key values are never printed, logged, or written to temp/. Standard library only.
"""

import argparse
import json
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_sound as gs  # noqa: E402  (shared ElevenLabs transport)

# ElevenLabs' documented limit for Instant Voice Cloning samples.
MAX_SAMPLES = 25


def list_voices(dry_run=False, base=None):
    """([{voice_id, name, category}], error). Returns (voices, error); one is None."""
    key, error = gs.missing_key_error(dry_run)
    if error:
        return None, error
    if dry_run:
        return [], None

    url = "{}/v1/voices".format((base or gs.BASE).rstrip("/"))
    try:
        status, payload = gs.get_json(url, gs.headers(key, content_type=None))
    except RuntimeError as exc:
        return None, gs.GenerationError(str(exc), 3)
    if status >= 400 or not isinstance(payload, dict):
        return None, gs.GenerationError(
            "ElevenLabs error {}: {}".format(status, "could not list voices"), 3)

    voices = []
    for entry in payload.get("voices", []):
        voices.append({
            "voice_id": entry.get("voice_id", ""),
            "name": entry.get("name", "(unnamed)"),
            "category": entry.get("category", ""),
        })
    return voices, None


def _read_samples(paths):
    files = []
    for path in paths:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.exists():
            raise FileNotFoundError("Voice sample not found: {}".format(candidate))
        mime = mimetypes.guess_type(candidate.name)[0] or "audio/mpeg"
        files.append(("files", candidate.name, candidate.read_bytes(), mime))
    return files


def clone_voice(name, sample_paths, description=None, consented=False,
                 dry_run=False, base=None):
    """(voice_id, error). Refuses without `consented=True` - see module docstring.

    Never bypassed by a keyword default: the caller must pass consented=True
    explicitly on every single call, including from the GUI's own handler.
    """
    if not consented:
        return None, gs.GenerationError(
            "clone_voice() requires consented=True - you must have the right to clone this "
            "voice. Pass --consent on the CLI, or check the consent box in the GUI.", 3)
    if not (name or "").strip():
        return None, gs.GenerationError("A cloned voice needs a name.", 3)
    sample_paths = list(sample_paths or [])
    if not sample_paths:
        return None, gs.GenerationError("Give at least one audio sample to clone from.", 3)
    if len(sample_paths) > MAX_SAMPLES:
        return None, gs.GenerationError(
            "{} samples given; ElevenLabs accepts at most {}.".format(
                len(sample_paths), MAX_SAMPLES), 3)

    key, error = gs.missing_key_error(dry_run)
    if error:
        return None, error

    try:
        files = _read_samples(sample_paths)
    except FileNotFoundError as exc:
        return None, gs.GenerationError(str(exc), 3)

    if dry_run:
        return None, None

    fields = {"name": name}
    if description:
        fields["description"] = description
    content_type, body = gs.build_multipart(fields, files)
    url = "{}/v1/voices/add".format((base or gs.BASE).rstrip("/"))
    hdrs = gs.headers(key, content_type=content_type)

    try:
        status, response_type, raw = gs._send(url, body, hdrs)
    except RuntimeError as exc:
        return None, gs.GenerationError(str(exc), 3)

    if status >= 400:
        return None, gs.GenerationError(
            "ElevenLabs error {}: {}".format(status, gs.api_error(raw, status)), 3)
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, AttributeError):
        return None, gs.GenerationError("Voice cloned, but the response was unreadable.", 3)

    voice_id = payload.get("voice_id")
    if not voice_id:
        return None, gs.GenerationError(
            "ElevenLabs accepted the clone but returned no voice_id.", 3)
    return voice_id, None


def delete_voice(voice_id, dry_run=False, base=None):
    """(ok, error)."""
    key, error = gs.missing_key_error(dry_run)
    if error:
        return False, error
    if dry_run:
        return True, None

    url = "{}/v1/voices/{}".format((base or gs.BASE).rstrip("/"), voice_id)
    try:
        status, _, raw = gs._send(url, None, gs.headers(key, content_type=None), method="DELETE")
    except RuntimeError as exc:
        return False, gs.GenerationError(str(exc), 3)
    if status >= 400:
        return False, gs.GenerationError(
            "ElevenLabs error {}: {}".format(status, gs.api_error(raw, status)), 3)
    return True, None


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="List, clone and delete ElevenLabs voices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--list", action="store_true")
    p.add_argument("--clone", action="store_true")
    p.add_argument("--name", help="name for a cloned voice")
    p.add_argument("--sample", action="append", default=[], help="audio sample (repeatable)")
    p.add_argument("--description", help="optional description for a cloned voice")
    p.add_argument("--consent", action="store_true",
                    help="confirms you have the right to clone this voice")
    p.add_argument("--delete", help="voice_id to delete")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    base = args.base_url or gs.gi.env_value("AIVS_API_BASE") or gs.BASE

    if args.clone:
        if not args.name:
            sys.exit("--clone needs --name.")
        voice_id, error = clone_voice(
            args.name, args.sample, description=args.description,
            consented=args.consent, dry_run=args.dry_run, base=base)
        if error:
            print(str(error), file=sys.stderr)
            return error.code
        if args.dry_run:
            print("Would clone '{}' from {} sample(s).".format(args.name, len(args.sample)))
            return 0
        print("[voice] {}".format(voice_id))
        return 0

    if args.delete:
        ok, error = delete_voice(args.delete, dry_run=args.dry_run, base=base)
        if error:
            print(str(error), file=sys.stderr)
            return error.code
        print("deleted" if not args.dry_run else "would delete: {}".format(args.delete))
        return 0

    voices, error = list_voices(dry_run=args.dry_run, base=base)
    if error:
        print(str(error), file=sys.stderr)
        return error.code
    if args.dry_run:
        print("Would GET {}/v1/voices".format(base))
        return 0
    for voice in voices:
        print("{:<24} {:<10} {}".format(voice["voice_id"], voice["category"], voice["name"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
