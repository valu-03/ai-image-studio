"""Compose a posing phrase - a named pose (or your own typed text), plus
opt-in realism techniques stacked on top.

Usage:
    python tools/build_posing.py --list
    python tools/build_posing.py --pose weight-back-leg
    python tools/build_posing.py --pose "leaning against a doorway, arms crossed"
    python tools/build_posing.py --pose s-curve --technique relaxed-hands --technique negative-space-limbs

`--pose` accepts EITHER a bank key (see --list) OR your own literal text - the
bank's entries are tested starting points, not a closed world, the same rule
build_lighting.py's deep path and ui/spec_editor.py's own editable combos
already follow. A value that matches a bank key uses that entry's phrase;
anything else is used exactly as typed, never rejected as a typo.

A base pose is the recommended starting point but is NOT required - a stack of
`--technique` cues, or a single `--technique-custom` phrase, composes on its
own. Only a wholly empty call (no pose, no technique, no custom text) is
refused.

`--technique` (repeatable) stacks a posing-realism cue on top of either a
picked or typed pose - opt-in, additive, never required: asymmetrical-weight,
relaxed-hands, soft-eyed-expression, negative-space-limbs, relaxed-posture.
`--technique-custom` adds one more free-text phrase beyond that list.

Posing is NOT one of realism_lint.py's 8 gated photorealism layers - it is
descriptive spec content like wardrobe/setting/mood, so there is no
conflicts list and no DETECT keyword requirement here. The composed phrase
is meant to be typed straight into Compose's own Posing field (ui/spec_editor.py)
- see CompositionView's own precedent, PosingView.apply_to_compose() /
SpecEditor.set_action_override().

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "posing_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def poses(bank):
    """{key: entry} flattened across every category, each tagged with it."""
    flat = {}
    for category, entries in bank.get("poses", {}).items():
        for key, cfg in entries.items():
            flat[key] = dict(cfg, category=category)
    return flat


def techniques(bank):
    return bank.get("techniques", {})


class PosingError(ValueError):
    """An unknown technique key was asked for, or nothing at all was given (no
    pose, no technique, no custom text) - the caller made a mistake, not
    something to silently drop. `pose` itself is never strict - see _resolve()
    - and a pose is not required as long as something else was supplied."""


def _resolve(table, value):
    """The bank entry's phrase if `value` names one, else `value` itself as
    literal text - a pose is a suggestion, not a closed world. Mirrors
    build_lighting.py's own _resolve()."""
    cfg = table.get(value)
    return cfg["phrase"] if cfg else value


def compose_posing(bank, pose=None, techniques_=(), technique_custom=None):
    """(phrase, warnings). `warnings` is always [] today - kept for
    interface parity with compose_lighting()/compose_composition() - poses
    are picked one at a time and no technique fights a pose or another
    technique, so there is nothing to warn about.

    A base pose is recommended but not required: a technique stack or a single
    `technique_custom` phrase composes on its own. Raises PosingError for an
    unknown technique key, or if nothing at all was supplied (no pose, no
    technique, no custom text).
    """
    parts = []

    if pose:
        parts.append(_resolve(poses(bank), pose))

    for name in techniques_:
        cfg = techniques(bank).get(name)
        if not cfg:
            raise PosingError("Unknown technique '{}'. See --list.".format(name))
        parts.append(cfg["phrase"])
    if technique_custom and technique_custom.strip():
        parts.append(technique_custom.strip())

    if not parts:
        raise PosingError(
            "Give a pose, a technique, or your own text - nothing was provided.")

    return ", ".join(parts), []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a posing phrase - a named pose, or your own typed "
                    "instruction, plus opt-in realism techniques.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--pose", help="a bank key (see --list) or your own text")
    p.add_argument("--technique", action="append", default=[],
                    help="a posing-realism cue to stack on top, repeatable (see --list)")
    p.add_argument("--technique-custom", help="one more free-text posing phrase to stack on top")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("POSES")
        by_category = {}
        for key, cfg in poses(bank).items():
            by_category.setdefault(cfg["category"], []).append((key, cfg))
        for category, items in by_category.items():
            print("  [{}]".format(category))
            for key, cfg in items:
                print("    {:<24} {}".format(key, cfg["label"]))
                print("                             {}".format(cfg["note"]))
        print("\nTECHNIQUES")
        for key, cfg in techniques(bank).items():
            print("  {:<24} {}".format(key, cfg["note"]))
        return 0

    try:
        phrase, warnings = compose_posing(
            bank, pose=args.pose, techniques_=args.technique,
            technique_custom=args.technique_custom)
    except PosingError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
