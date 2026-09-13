"""Compose a reusable voice-blueprint phrase - a named vocal-delivery style
from the course's "Consistent Character Voices" lesson, filled with an
accent, or your own typed text.

Usage:
    python tools/build_voice.py --list
    python tools/build_voice.py --style confident --accent "Australian accent"
    python tools/build_voice.py --custom "a gravelly, world-weary baritone, unhurried"

The course's core rule this tool exists to support: define a character's
voice ONCE with specific traits, then copy that EXACT text into every prompt
for that character - even a small wording change shifts the tone a model
produces. This composer has no opinion on where the result is used (this app
has no per-line dialogue field of its own); it just gives you a stable,
copyable block of text to paste into whatever prompt needs the character to
speak.

`--style` fills the picked template's one `{accent}` slot - leave `--accent`
blank and it falls back to "a neutral accent" rather than reading oddly.
`--custom` always wins entirely, same precedence as every other builder in
this project - typed text is used exactly as written.

This is NOT one of realism_lint.py's 8 gated photorealism layers - there is
no DETECT keyword requirement here, the same way persona/posing/composition
technique phrases carry no such requirement either.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent / "voice_bank.json"

FALLBACK_ACCENT = "neutral accent"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def styles(bank):
    return bank.get("styles", {})


class VoiceError(ValueError):
    """An unknown style key was asked for, or nothing resolved to a phrase."""


def compose_voice(bank, style=None, accent=None, custom=None):
    """(phrase, warnings). `warnings` is always [] - there is nothing here
    that can conflict with anything else the way lighting's quality x source
    can. `custom` beats `style` entirely. Raises VoiceError for an unknown
    style key or if neither `style` nor `custom` is given.
    """
    custom = (custom or "").strip()
    if custom:
        return custom, []

    if not style:
        raise VoiceError("Give --style (see --list) or --custom text.")

    cfg = styles(bank).get(style)
    if not cfg:
        raise VoiceError("Unknown style '{}'. See --list.".format(style))

    accent_text = (accent or "").strip() or FALLBACK_ACCENT
    phrase = cfg["phrase_template"].format(accent=accent_text)
    return phrase, []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a reusable voice-blueprint phrase - a named vocal "
                    "style filled with an accent, or your own text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--style", help="a bank key (see --list)")
    p.add_argument("--accent", help="e.g. \"Australian accent\", \"soft Irish accent\"")
    p.add_argument("--custom", help="typed voice-blueprint text - beats --style/--accent")
    p.add_argument("--list", action="store_true", help="print every style and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("STYLES")
        for key, cfg in styles(bank).items():
            print("  {:<28} {}".format(key, cfg["label"]))
            print("  {:<28} {}".format("", cfg["when"]))
        return 0

    try:
        phrase, warnings = compose_voice(
            bank, style=args.style, accent=args.accent, custom=args.custom)
    except VoiceError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
