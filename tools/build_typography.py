"""Compose the type layer of a static ad - what leads, how much of the frame
the words get, where they sit, the lockup, and the order the eye reads them in.

Usage:
    python tools/build_typography.py --list
    python tools/build_typography.py --dominance image-led --ratio editorial \
                                     --zone upper-left --lockup corner-quiet \
                                     --reading-order headline-product-logo
    python tools/build_typography.py --dominance type-led --ratio poster --overrides
    python tools/build_typography.py --ratio editorial --headline "Sleep is not a luxury"

WHAT THIS IS FOR. Every other toolkit in this app describes the PHOTOGRAPH. A
static ad is a photograph with an advert laid over it, and until this bank
existed a repo-wide grep for typography, headline, logo, lockup or type
hierarchy found nothing about text inside an image anywhere - "logo" had zero
hits in tools/ at all. So the app could art-direct the picture and not one word
of the thing that makes it an advert.

THE CHECK THAT EARNS ITS KEEP. The commonest way a layout dies is that
everything is loud, so nothing leads. That is hard to detect from words - but a
contradiction between the two decisions that express it is not. Asking for the
type to lead while giving it a tenth of the frame is a flat hierarchy stated
twice, and compose_typography() refuses it by name rather than quietly picking
one. Same shape build_color.py uses to refuse --mood and --film-look together.

WORD COUNTS ARE REAL. Image models garble long strings: a three-word headline
renders cleanly far more often than a twelve-word one, and a legal line never
renders legibly at all. Each ratio carries its own `max_words`, and passing
--headline checks yours against it. Anything longer belongs in a typesetting
tool over a clean plate, not in a generation prompt.

Like build_capture.py this composes across SEVERAL of build_prompt.py's layers
at once - today every phrase lands on `composition`, but the bank declares the
layer per group rather than assuming, so a future phrase about type CONTRAST
can land on `colour` without changing this file. `--overrides` prints JSON keyed
by layer, ready for spec["overrides"].

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "typography_bank.json"

# The order phrases are emitted in - the order a reader of the prompt meets the
# decisions, broadest first. Not the order they were typed, so the same
# selection always composes to the same string.
GROUP_ORDER = ["dominance", "ratio", "zone", "lockup", "reading_order", "restraint"]

GROUP_ARGS = {
    "dominance": "dominance",
    "ratio": "ratio",
    "zone": "zone",
    "lockup": "lockup",
    "reading_order": "reading-order",
    "restraint": "restraint",
}


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def groups(bank):
    return bank.get("groups", {})


def options(bank, group):
    return groups(bank).get(group, {}).get("options", {})


def layer_of(bank, group, key):
    """The realism_lint layer this option strengthens.

    An option may override its group's default, the same rule
    build_capture.py follows - a group layer is a default, not a claim about
    every option in it.
    """
    group_cfg = groups(bank).get(group, {})
    option = group_cfg.get("options", {}).get(key, {})
    return option.get("layer") or group_cfg.get("layer")


def max_words(bank, ratio):
    """How many words of headline this ratio can carry, or None."""
    return options(bank, "ratio").get(ratio or "", {}).get("max_words")


def compatible_ratios(bank, dominance):
    """The ratios that can honestly express this dominance."""
    return bank.get("compatibility", {}).get(dominance or "", [])


class TypographyError(ValueError):
    """An unknown key, a dominance that contradicts its ratio, two options that
    would be set on top of each other, or a headline too long to render."""


def check_contradiction(bank, dominance, ratio):
    """The flat-hierarchy check, stated as the contradiction it really is."""
    if not dominance or not ratio:
        return None
    allowed = compatible_ratios(bank, dominance)
    if allowed and ratio not in allowed:
        dom_label = options(bank, "dominance")[dominance]["label"]
        ratio_label = options(bank, "ratio")[ratio]["label"]
        return (
            "'{}' contradicts '{}' - that is a flat hierarchy stated twice. "
            "Pick one of: {}.".format(
                dom_label, ratio_label,
                ", ".join(options(bank, "ratio")[r]["label"] for r in allowed))
        )
    return None


def check_conflicts(bank, picked):
    """Named pairs that are individually fine and together are not.

    Checked by name from the bank, never inferred: `top-left` puts the mark
    exactly where `upper-left` puts the headline, and nothing about either
    phrase says so on its own.
    """
    chosen = {"{}:{}".format(group, key) for group, key in picked}
    out = []
    for pair in bank.get("conflicts", {}).get("pairs", []):
        if set(pair) <= chosen:
            left, right = pair
            out.append("'{}' and '{}' would be set on top of each other.".format(left, right))
    return out


def check_headline(bank, ratio, headline):
    """Is this headline short enough for the ratio to render it?"""
    if not headline:
        return None
    cap = max_words(bank, ratio)
    if cap is None:
        return None
    count = len(headline.split())
    if count > cap:
        return (
            "a {}-word headline at '{}' - that ratio carries {}. Image models "
            "garble long strings; cut it, or typeset it later over a clean "
            "plate.".format(count, options(bank, "ratio")[ratio]["label"], cap)
        )
    return None


def compose_typography(bank, dominance=None, ratio=None, zone=None, lockup=None,
                       reading_order=None, restraint=(), headline=None):
    """(phrases_by_layer, warnings). Raises TypographyError on a contradiction.

    A contradiction raises rather than warns because it is not a matter of
    taste: the two values cannot both be true of one layout, so there is no
    composed answer to hand back. A headline that is too long only warns - the
    layout is still coherent, you just have copy to cut.
    """
    picked = []
    singles = [("dominance", dominance), ("ratio", ratio), ("zone", zone),
               ("lockup", lockup), ("reading_order", reading_order)]
    for group, key in singles:
        if not key:
            continue
        if key not in options(bank, group):
            raise TypographyError(
                "Unknown {} option '{}'. See --list.".format(group, key))
        picked.append((group, key))
    for key in restraint:
        if key not in options(bank, "restraint"):
            raise TypographyError(
                "Unknown restraint option '{}'. See --list.".format(key))
        picked.append(("restraint", key))

    if not picked:
        raise TypographyError(
            "Give at least one of --dominance, --ratio, --zone, --lockup, "
            "--reading-order or --restraint.")

    contradiction = check_contradiction(bank, dominance, ratio)
    if contradiction:
        raise TypographyError(contradiction)

    warnings = list(check_conflicts(bank, picked))
    too_long = check_headline(bank, ratio, headline)
    if too_long:
        warnings.append(too_long)

    # Bank order, not argument order - within a group as well as between them.
    # The stackable `restraint` group used to come out in whatever order it was
    # typed, so --restraint one-idea --restraint no-legal and the same two
    # reversed composed to two different strings. That is a seed-stability bug
    # in slow motion: the same selection has to produce the same prompt, or
    # nothing downstream can be compared with anything.
    by_layer = {}
    chosen = {(group, key) for group, key in picked}
    for group in GROUP_ORDER:
        for key in options(bank, group):
            if (group, key) not in chosen:
                continue
            layer = layer_of(bank, group, key)
            by_layer.setdefault(layer, []).append(options(bank, group)[key]["phrase"])
    return by_layer, warnings


def phrase_for(by_layer):
    """The flat, comma-joined phrase - what a GUI Applies as free text."""
    return ", ".join(phrase for phrases in by_layer.values() for phrase in phrases)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose the type layer of a static ad - hierarchy, zone, "
                    "lockup and reading order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--dominance", help="what leads the frame (see --list)")
    p.add_argument("--ratio", help="how much of the frame the type gets (see --list)")
    p.add_argument("--zone", help="where the type sits (see --list)")
    p.add_argument("--lockup", help="where the logo sits (see --list)")
    p.add_argument("--reading-order", dest="reading_order",
                   help="the path the eye takes (see --list)")
    p.add_argument("--restraint", action="append", default=[],
                   help="a copy-discipline rule, repeatable (see --list)")
    p.add_argument("--headline", help="your actual headline - checked against the ratio's word cap")
    p.add_argument("--overrides", action="store_true",
                   help="print JSON keyed by build_prompt layer, for spec['overrides']")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for group in GROUP_ORDER:
            cfg = groups(bank)[group]
            print("{}  (--{}{})".format(
                cfg["label"].upper(), GROUP_ARGS[group],
                "" if cfg.get("exclusive") else ", repeatable"))
            print("  {}".format(cfg["note"]))
            for key, option in cfg["options"].items():
                cap = option.get("max_words")
                tail = "  [{} words max]".format(cap) if cap else ""
                print("  {:<22} {}{}".format(key, option["label"], tail))
                print("  {:<22} -> {}".format("", option["note"]))
            print()
        print("WHAT AGREES WITH WHAT")
        for dominance, ratios in bank.get("compatibility", {}).items():
            if dominance == "note":
                continue
            print("  {:<22} {}".format(dominance, ", ".join(ratios)))
        return 0

    try:
        by_layer, warnings = compose_typography(
            bank, dominance=args.dominance, ratio=args.ratio, zone=args.zone,
            lockup=args.lockup, reading_order=args.reading_order,
            restraint=args.restraint, headline=args.headline)
    except TypographyError as exc:
        sys.exit(str(exc))

    if args.overrides:
        print(json.dumps(by_layer, indent=2))
    else:
        print(phrase_for(by_layer))
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
