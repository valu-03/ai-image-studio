"""Compose a visual-style phrase - a named look from the course's Style
Reference Library, or your own typed text.

Usage:
    python tools/build_style.py --list
    python tools/build_style.py --style 35mm-film
    python tools/build_style.py --style film-noir
    python tools/build_style.py --custom "sun-bleached super-8 home movie look"

A style is one named pick (or `--custom`, which always wins). There are no
techniques to stack - a style already IS the whole look, unlike lighting or
colour where cues layer.

The course's own rule: the style keywords go at the END of the prompt, after
the scene description. This composer just returns the keyword phrase; it lands
in spec["overrides"]["style"], which build_prompt.free_overrides() folds into
the free trailing segment (not one of the eight realism layers).

Styles split into two groups:
  photoreal - describe a real camera / film / lighting look, compatible with
              the realism vocabulary the prompt already carries (35mm film,
              film noir, golden hour, ...).
  stylised  - deliberately not photographic (anime, oil painting, watercolour).
              These FIGHT the eight realism layers the rest of the prompt is
              built from - "visible skin pores" next to "visible brush
              strokes" - so the image comes out a confused hybrid.
              compose_style() returns a warning for these; the Style section
              shows it before applying.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent / "style_bank.json"

STYLISED_WARNING = (
    "stylised look - it fights the realism vocabulary the prompt already "
    "carries, so the image comes out a hybrid. Use it only when you want a "
    "deliberately non-photographic result."
)


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def photoreal(bank):
    return bank.get("photoreal", {})


def stylised(bank):
    return bank.get("stylised", {})


def all_styles(bank):
    """{key: entry} across both groups, each tagged with its group."""
    flat = {}
    for group in ("photoreal", "stylised"):
        for key, cfg in bank.get(group, {}).items():
            flat[key] = dict(cfg, group=group)
    return flat


class StyleError(ValueError):
    """An unknown style key was asked for, or nothing resolved to a phrase."""


def compose_style(bank, style=None, custom=None):
    """(phrase, warnings). `custom` beats `style`. Raises StyleError for an
    unknown key or if neither is given. `warnings` carries the stylised note
    when a stylised style is picked - never for `custom` (typed text is used
    exactly as written, judged by nothing)."""
    custom = (custom or "").strip()
    if custom:
        return custom, []

    if not style:
        raise StyleError("Give --style (see --list) or --custom text.")

    cfg = all_styles(bank).get(style)
    if not cfg:
        raise StyleError("Unknown style '{}'. See --list.".format(style))

    warnings = [STYLISED_WARNING] if cfg["group"] == "stylised" else []
    return cfg["keywords"], warnings


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a visual-style phrase - a named look or your own text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--style", help="a bank key (see --list)")
    p.add_argument("--custom", help="typed style text - beats --style")
    p.add_argument("--list", action="store_true", help="print every style and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for group, heading in (("photoreal", "PHOTOREAL (passes the realism gate)"),
                               ("stylised", "STYLISED (skips the realism gate on purpose)")):
            print(heading)
            for key, cfg in bank.get(group, {}).items():
                print("  {:<22} {}".format(key, cfg["label"]))
                print("  {:<22} {}".format("", cfg["look"]))
            print()
        return 0

    try:
        phrase, warnings = compose_style(bank, style=args.style, custom=args.custom)
    except StyleError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
