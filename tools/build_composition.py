"""Compose a composition phrase - a named guide (or typed custom text), plus
opt-in realism techniques stacked on top.

Usage:
    python tools/build_composition.py --list
    python tools/build_composition.py --guide rule-of-thirds
    python tools/build_composition.py --custom "framed low, looking up at the subject"
    python tools/build_composition.py --guide diagonals --technique lead-room --technique negative-space

The seven named geometries (rule of thirds, phi grid, diagonals, triangle,
golden ratio, golden spiral, harmonic armature) are NOT duplicated into this
bank - they already live in tools/prompt_bank.json's composition_guides and
are read straight from there via build_prompt.guides(), so there is exactly
one place that owns them. `--custom` free text always beats a picked `--guide`
- the same precedence build_prompt.apply_composition_guide() already enforces
at generation time; this function just previews the same result.

`--technique` (repeatable) stacks realism cues on top of either a guide or
custom text - opt-in, additive, never required: negative-space, lead-room,
depth-layering, framing-device, visual-balance, scale-contrast,
pattern-repetition. `--technique-custom` adds one more free-text phrase
beyond that list - the seven are tested starting points, not a closed world.

Unlike lighting's quality x source, the seven guides are already mutually
exclusive by construction (one combo, one pin), and no technique here fights
a guide or another technique - so there is no conflicts list and this tool
never warns, only refuses outright bad input.

The composed phrase is meant to be typed straight into Compose's own
composition combo (ui/spec_editor.py) as custom text - see
CompositionView.apply_to_compose() / SpecEditor.set_composition_override().

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
BANK_PATH = TOOLS_DIR / "composition_bank.json"

sys.path.insert(0, str(TOOLS_DIR))

import build_prompt as bp  # noqa: E402


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def techniques(bank):
    return bank.get("techniques", {})


class CompositionError(ValueError):
    """An unknown key was asked for, or neither a guide nor custom text was
    given - the caller made a mistake, not something to silently drop."""


def compose_composition(main_bank, comp_bank, guide=None, custom=None, techniques_=(),
                         technique_custom=None):
    """(phrase, warnings). Raises CompositionError for an unknown guide/
    technique key, or if neither `guide` nor `custom` resolves to anything.

    `warnings` is always [] today - kept for interface parity with
    compose_lighting() (tools/build_lighting.py) and to leave room for a
    future contradiction check. There is none yet: the seven guides are
    already mutually exclusive by construction, and none of this bank's
    techniques fights a guide or each other.
    """
    parts = []
    custom = (custom or "").strip()

    if custom:
        parts.append(custom)
    elif guide:
        cfg = bp.guides(main_bank).get(guide)
        if not cfg:
            raise CompositionError("Unknown guide '{}'. See --list.".format(guide))
        parts.append(cfg["phrase"])

    if not parts:
        raise CompositionError("Give --guide or --custom text.")

    for name in techniques_:
        cfg = techniques(comp_bank).get(name)
        if not cfg:
            raise CompositionError("Unknown technique '{}'. See --list.".format(name))
        parts.append(cfg["phrase"])
    if technique_custom and technique_custom.strip():
        parts.append(technique_custom.strip())

    return ", ".join(parts), []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a composition phrase - a named guide, or your own "
                    "typed framing instruction, plus opt-in realism techniques.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--guide", help="a named geometry, e.g. rule-of-thirds (see --list)")
    p.add_argument("--custom", help="typed framing text - beats --guide if both are given")
    p.add_argument("--technique", action="append", default=[],
                    help="a realism cue to stack on top, repeatable (see --list)")
    p.add_argument("--technique-custom", help="one more free-text realism phrase to stack on top")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    main_bank = bp.load_bank()
    comp_bank = load_bank()

    if args.list:
        print("GUIDES")
        for key, cfg in bp.guides(main_bank).items():
            print("  {:<20} {}".format(key, cfg["label"]))
            print("                       {}".format(cfg["note"]))
        print("\nTECHNIQUES")
        for key, cfg in techniques(comp_bank).items():
            print("  {:<20} {}".format(key, cfg["note"]))
        return 0

    try:
        phrase, warnings = compose_composition(
            main_bank, comp_bank, guide=args.guide, custom=args.custom,
            techniques_=args.technique, technique_custom=args.technique_custom)
    except CompositionError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
