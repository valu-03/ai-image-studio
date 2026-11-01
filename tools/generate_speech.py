"""Generate real speech from text with an ElevenLabs voice.

Usage:
    python tools/generate_speech.py --text "Your hair gets greasy 5 hours after washing it."
    python tools/generate_speech.py --text "..." --voice <voice_id> --out beat1.mp3
    python tools/generate_speech.py --text "..." --dry-run

Needs ELEVENLABS_API_KEY in .env.                 ->  https://elevenlabs.io/app/settings/api-keys

Synchronous, like tools/generate_sound.py: one POST, audio bytes straight back. All
transport (headers, error parsing, saving) is reused from generate_sound.py rather
than duplicated - the two only differ in which endpoint and body they send.

There is no content gate here the way sound_lint gates an effect prompt - spoken
text is not a layered prompt tools/realism_lint.py-style rules could score. The
safeguard for TTS is cost, not quality: `estimate_cost()` reports the character
count before a real call is made, the same "say what a batch will cost" rule
every other generation in this project already follows.

Key values are never printed, logged, or written to temp/. Standard library only.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402
import generate_sound as gs  # noqa: E402  (shared ElevenLabs transport)
import pricing as _pricing  # noqa: E402  (PRICING_PATH/load_pricing - one seeded pricing.json)

OUT_DIR = ROOT / "temp" / "outputs" / "voice"

DEFAULT_MODEL = "eleven_multilingual_v2"
MODEL_VAR = "ELEVENLABS_TTS_MODEL"
VOICE_VAR = "ELEVENLABS_VOICE_ID"


def default_voice():
    return gi.env_value(VOICE_VAR) or None


def default_model():
    return gi.env_value(MODEL_VAR) or DEFAULT_MODEL


def estimate_cost(text, pricing=None):
    """(characters, credits, confidence) - what ElevenLabs actually bills TTS on.

    Reads pricing.json's `elevenlabs.text_to_speech` block through
    generate_video.py's own PRICING_PATH/load_pricing() rather than a second,
    hardcoded constant - one seeded file, one AIVS_PRICING_FILE test seam, same
    as every other cost estimate in this project.
    """
    characters = len(text or "")
    pricing = pricing or _pricing.load_pricing()
    cfg = (pricing.get("elevenlabs") or {}).get("text_to_speech", {})
    credits = round(characters * float(cfg.get("credits_per_unit", 1)))
    confidence = (pricing.get("elevenlabs") or {}).get("confidence", "estimated")
    return characters, credits, confidence


def generate_speech(text, voice_id=None, model_id=None, out_name=None,
                     dry_run=False, on_stage=None, base=None, voice_settings=None):
    """Text -> saved audio path, spoken by a chosen (or default) voice.

    `voice_id` falls back to ELEVENLABS_VOICE_ID in .env, then to whatever the
    caller passes as None all the way through - the GUI resolves that last
    case against the account's own voice list, since a hardcoded fallback id
    here could point at a voice that does not exist on a given account.
    """
    def stage(message):
        if on_stage:
            on_stage(message)

    if not (text or "").strip():
        return None, gs.GenerationError("Nothing to speak - the text is empty.", 3)

    voice = voice_id or default_voice()
    if not voice and not dry_run:
        return None, gs.GenerationError(
            "No voice chosen and no {} set in .env. Pick a voice first (Sound -> Voices "
            "lists the account's own).".format(VOICE_VAR), 3)

    key, error = gs.missing_key_error(dry_run)
    if error:
        return None, error

    body = {"text": text, "model_id": model_id or default_model()}
    if voice_settings:
        body["voice_settings"] = dict(voice_settings)

    url = "{}/v1/text-to-speech/{}".format(
        (base or gs.BASE).rstrip("/"), voice or "unset-voice")
    hdrs = gs.headers(key or "DRY-RUN")

    if dry_run:
        return None, None

    stage("Generating speech...")
    try:
        status, content_type, raw = gs._send(url, json.dumps(body).encode("utf-8"), hdrs)
    except RuntimeError as exc:
        return None, gs.GenerationError(str(exc), 3)

    if status >= 400 or not content_type.startswith("audio/"):
        return None, gs.GenerationError(
            "ElevenLabs error {}: {}".format(status, gs.api_error(raw, status)), 3)
    if not raw:
        return None, gs.GenerationError("ElevenLabs returned no audio.", 4)

    return gs.save_audio(raw, content_type, OUT_DIR, "voice", out_name), None


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Generate speech from text with an ElevenLabs voice.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--text", required=True, help="what to say")
    p.add_argument("--voice", help="voice_id; falls back to ELEVENLABS_VOICE_ID in .env")
    p.add_argument("--model", help="override the TTS model id for this call")
    p.add_argument("--out", help="output filename inside temp/outputs/voice/")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument(
        "--dry-run", action="store_true",
        help="describe the request without sending it or needing a key",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    base = args.base_url or gi.env_value("AIVS_API_BASE") or gs.BASE
    characters, credits, confidence = estimate_cost(args.text)
    print("characters: {}  (~{} credits, {})".format(characters, credits, confidence),
          file=sys.stderr)

    if args.dry_run:
        voice = args.voice or default_voice() or "(none set)"
        print("Would POST {}/v1/text-to-speech/{}".format(base, voice))
        print("model: {}".format(args.model or default_model()))
        return 0

    path, error = generate_speech(
        args.text, voice_id=args.voice, model_id=args.model, out_name=args.out, base=base,
        on_stage=lambda message: print(message, file=sys.stderr),
    )
    if error:
        print(str(error), file=sys.stderr)
        return error.code

    print("[voice] {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
