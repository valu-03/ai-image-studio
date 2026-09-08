"""Compose a lighting phrase - a named setup, or direction + quality + source.

Usage:
    python tools/build_lighting.py --list
    python tools/build_lighting.py --setup rembrandt
    python tools/build_lighting.py --direction split --quality hard --source direct-sun
    python tools/build_lighting.py --setup loop --technique catchlights --technique falloff

Two paths to a phrase:

    FAST   --setup <name>          a pre-vetted, hand-written recipe. Can never
                                    contradict itself - see lighting_bank.json's
                                    own `setups` entries.
    DEEP   --direction/--quality/--source, any subset               the way a
                                    working photographer actually thinks. Checked
                                    against the bank's `conflicts` list - a
                                    combination that fights itself (hard light
                                    from an overcast sky) is reported, never
                                    silently composed.

`--technique` (repeatable) stacks realism cues on top of either path - opt-in,
additive, never required: catchlights, colour-temperature, motivated-source,
falloff, subsurface-translucency, specularity, fill-ratio.

The result is meant for spec["overrides"]["lighting"] - the exact override slot
ui/spec_editor.py's own lighting combo already writes to, so nothing about how
Compose consumes it needs to change.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "lighting_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def directions(bank):
    return bank.get("directions", {})


def qualities(bank):
    return bank.get("qualities", {})


def sources(bank):
    """{key: entry} flattened across natural/artificial, each tagged with its category."""
    flat = {}
    for category, entries in bank.get("sources", {}).items():
        for key, cfg in entries.items():
            flat[key] = dict(cfg, category=category)
    return flat


def setups(bank):
    return bank.get("setups", {})


def techniques(bank):
    return bank.get("realism_techniques", {})


def find_conflict(bank, quality, source):
    """The reason string if `quality` + `source` fight each other, else None."""
    if not quality or not source:
        return None
    for entry in bank.get("conflicts", []):
        if entry.get("quality") == quality and entry.get("source") == source:
            return entry.get("reason", "")
    return None


class LightingError(ValueError):
    """An unknown key was asked for - the caller gave a typo, not a phrase."""


def compose_lighting(bank, setup=None, direction=None, quality=None, source=None,
                      techniques_=()):
    """(phrase, warnings). Raises LightingError for an unknown key - never
    silently drops a typo the way a missing dict lookup would.

    `setup` is the fast path and is exclusive with direction/quality/source -
    a setup is already a complete, self-consistent phrase; mixing it with a
    separate direction/quality/source pick would just contradict the setup's
    own choices with no way to tell which one should win.
    """
    parts = []
    warnings = []

    if setup:
        if direction or quality or source:
            raise LightingError(
                "--setup is a complete recipe on its own - combine --technique "
                "with it, not --direction/--quality/--source.")
        cfg = setups(bank).get(setup)
        if not cfg:
            raise LightingError("Unknown setup '{}'. See --list.".format(setup))
        parts.append(cfg["phrase"])
    else:
        if direction:
            cfg = directions(bank).get(direction)
            if not cfg:
                raise LightingError("Unknown direction '{}'. See --list.".format(direction))
            parts.append(cfg["phrase"])
        if quality:
            cfg = qualities(bank).get(quality)
            if not cfg:
                raise LightingError("Unknown quality '{}'. See --list.".format(quality))
            parts.append(cfg["phrase"])
        if source:
            cfg = sources(bank).get(source)
            if not cfg:
                raise LightingError("Unknown source '{}'. See --list.".format(source))
            parts.append(cfg["phrase"])
        if not parts:
            raise LightingError(
                "Give --setup, or at least one of --direction/--quality/--source.")
        conflict = find_conflict(bank, quality, source)
        if conflict:
            warnings.append(conflict)

    for name in techniques_:
        cfg = techniques(bank).get(name)
        if not cfg:
            raise LightingError("Unknown technique '{}'. See --list.".format(name))
        parts.append(cfg["phrase"])

    return ", ".join(parts), warnings


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a lighting phrase - a named setup, or direction + quality + source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--setup", help="a named recipe, e.g. rembrandt (see --list)")
    p.add_argument("--direction", help="e.g. loop, rembrandt, split, rim (see --list)")
    p.add_argument("--quality", choices=["hard", "soft"])
    p.add_argument("--source", help="e.g. golden-hour, tungsten, direct-sun (see --list)")
    p.add_argument("--technique", action="append", default=[],
                    help="a realism cue to stack on top, repeatable (see --list)")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("SETUPS")
        for key, cfg in setups(bank).items():
            print("  {:<14} {}".format(key, cfg["label"]))
            print("                 {}".format(cfg["teaches"]))
        print("\nDIRECTIONS")
        for key, cfg in directions(bank).items():
            print("  {:<14} {}".format(key, cfg["note"]))
        print("\nQUALITIES")
        for key, cfg in qualities(bank).items():
            print("  {:<14} {}".format(key, cfg["note"]))
        print("\nSOURCES")
        for key, cfg in sources(bank).items():
            print("  {:<18} ({})  {}".format(key, cfg["category"], cfg["note"]))
        print("\nTECHNIQUES")
        for key, cfg in techniques(bank).items():
            print("  {:<20} {}".format(key, cfg["note"]))
        return 0

    try:
        phrase, warnings = compose_lighting(
            bank, setup=args.setup, direction=args.direction, quality=args.quality,
            source=args.source, techniques_=args.technique)
    except LightingError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
