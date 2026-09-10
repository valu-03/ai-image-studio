"""Compose a colour-grading phrase - a named mood, a named film look, or your
own typed text, plus opt-in techniques stacked on top.

Usage:
    python tools/build_color.py --list
    python tools/build_color.py --mood epic-heroic
    python tools/build_color.py --film-look dune
    python tools/build_color.py --custom "sun-bleached pastel grade"
    python tools/build_color.py --mood dark-moody --technique accent-echo

`--mood` and `--film-look` are two complete, named recipes - giving both at
once is refused, there's no way to tell which one should win (unlike
Lighting's setup vs deep path, these aren't a fast/deep split of the same
thing). `--custom` always wins over either, same precedence Composition's
guide/custom split already uses.

`--technique` (repeatable) stacks a colour technique on top of whichever base
you picked - opt-in, additive, never required: accent-echo, warm-cool-contrast.

Some of this bank's source material is deliberately vivid rather than
photographically restrained (neon cyberpunk, hot pink Barbie) - unlike every
other bank so far, its phrases were checked against banned/warn, not just
detectability, before shipping (see tests/test_color_bank.py).

The result is meant for spec["overrides"]["colour"] - "colour" is one of
build_prompt.py's eight LAYER_ORDER names, so select_layers() places it
directly; ui/spec_editor.py's own "Colour grade" combo writes to the same
slot. (An override for a name that ISN'T a layer - "style" - is folded into
the free extra segment by build_prompt.free_overrides() instead.)

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "color_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def moods(bank):
    return bank.get("moods", {})


def film_looks(bank):
    return bank.get("film_looks", {})


def techniques(bank):
    return bank.get("techniques", {})


class ColorError(ValueError):
    """An unknown key was asked for, mood+film_look were both given, or
    nothing at all resolved to a phrase."""


def compose_color(bank, mood=None, film_look=None, custom=None, techniques_=()):
    """(phrase, warnings). `warnings` is always [] - a mood/film_look is one
    complete pick, techniques don't fight each other or a pick, so there's
    nothing to warn about. Raises ColorError for an unknown key, for
    mood+film_look given together, or if nothing resolves at all.
    """
    custom = (custom or "").strip()
    parts = []

    if custom:
        parts.append(custom)
    elif mood and film_look:
        raise ColorError(
            "--mood and --film-look are two complete recipes - give one or the "
            "other, not both. Combine --technique with whichever you pick.")
    elif mood:
        cfg = moods(bank).get(mood)
        if not cfg:
            raise ColorError("Unknown mood '{}'. See --list.".format(mood))
        parts.append(cfg["phrase"])
    elif film_look:
        cfg = film_looks(bank).get(film_look)
        if not cfg:
            raise ColorError("Unknown film look '{}'. See --list.".format(film_look))
        parts.append(cfg["phrase"])

    if not parts:
        raise ColorError("Give --mood, --film-look, or --custom text.")

    for name in techniques_:
        cfg = techniques(bank).get(name)
        if not cfg:
            raise ColorError("Unknown technique '{}'. See --list.".format(name))
        parts.append(cfg["phrase"])

    return ", ".join(parts), []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a colour-grading phrase - a named mood, a named "
                    "film look, or your own text, plus opt-in techniques.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mood", help="a bank key (see --list)")
    p.add_argument("--film-look", help="a bank key (see --list)")
    p.add_argument("--custom", help="typed colour-grading text - beats --mood/--film-look")
    p.add_argument("--technique", action="append", default=[],
                    help="a colour technique to stack on top, repeatable (see --list)")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("MOODS")
        for key, cfg in moods(bank).items():
            print("  {:<20} {}".format(key, cfg["label"]))
            print("                       {}".format(cfg["note"]))
        print("\nFILM LOOKS")
        for key, cfg in film_looks(bank).items():
            print("  {:<20} {}".format(key, cfg["label"]))
            print("                       {}".format(cfg["note"]))
        print("\nTECHNIQUES")
        for key, cfg in techniques(bank).items():
            print("  {:<20} {}".format(key, cfg["note"]))
        return 0

    try:
        phrase, warnings = compose_color(
            bank, mood=args.mood, film_look=args.film_look, custom=args.custom,
            techniques_=args.technique)
    except ColorError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
