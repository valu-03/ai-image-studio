"""Audit tools/typography_bank.json against the gate it is meant to strengthen.

Usage:
    python tools/typography_lint.py
    python tools/typography_lint.py --quiet     # exit code only

THE FAILURE THIS EXISTS TO CATCH. tools/story_bank.json once carried four
phrases that read exactly like fur vocabulary - "visible individual fur
strands", "whisker detail", "wet nose texture", "natural animal anatomy" - and
realism_lint could not see a single one of them. Deleting all four changed the
scene's 8/8 by nothing. Vocabulary a bank can write but the gate cannot detect
is decoration, and it is invisible decoration: everything still passes, so
nothing ever complains.

This bank was two phrases away from the same fate. `lockup.none` and
`restraint.no-legal` were first written as "no brand logo in the frame" and "no
small print or legal line in the frame" - both perfectly sensible English, both
completely invisible, because realism_lint.is_negated() correctly refuses to
score a layer key sitting inside a negation. They lead with the positive half
now, and this file is what would have caught them.

Four checks, per phrase, never assumed:

    detectable    visible to the layer it claims to strengthen
    clean         trips no banned term and no soft warn term
    positive      its detected keyword is not sitting inside a negation
    restrained    hedged rather than absolute, where intensity is a thing the
                  option HAS (a group may opt out with "restraint": false)

`positive` is this bank's own check and does not appear in capture_lint.py,
because capture describes artefacts that are present while typography
constantly wants to say what is ABSENT - no logo, no small print, no competing
subhead. That is exactly the shape that goes silently undetected.

Standard library only. No API keys, no network.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import build_typography as bt  # noqa: E402
import realism_lint as rl  # noqa: E402

HEDGES = ("generous", "roughly", "about", "small", "quiet", "single", "kept",
          "deliberate", "clear", "limited", "subordinate", "supporting")


def audit(bank=None, image_bank=None):
    """[{group, key, layer, detectable, clean, positive, restrained, ...}] -
    one row per option, in bank order."""
    bank = bank or bt.load_bank()
    image_bank = image_bank or bp.load_bank()
    rows = []
    for group in bt.GROUP_ORDER:
        cfg = bt.groups(bank)[group]
        for key, option in cfg["options"].items():
            phrase = option["phrase"].lower()
            layer = bt.layer_of(bank, group, key)
            keys = rl.DETECT[layer]["keys"] if layer in rl.DETECT else []
            hits = rl.layer_hits(keys, phrase)
            # Present-but-negated: the keyword IS in the phrase, and is not
            # being asked for. This is the failure mode the docstring names.
            raw = [k for k in keys if rl._key_positions(k, phrase)]
            negated_only = bool(raw) and not hits

            banned, _ = rl.find_terms(phrase, image_bank["banned"])
            warn, _ = rl.find_terms(phrase, image_bank["warn"])
            # Option first, then group, then the default - the same
            # precedence layer_of() uses. A group flag would have exempted
            # lockup's three real placements along with its one binary option.
            wants_restraint = option.get("restraint", cfg.get("restraint", True))
            restrained = (not wants_restraint) or any(w in phrase for w in HEDGES)

            detail = []
            if negated_only:
                detail.append("only matches inside a negation - lead with the positive half")
            elif not hits:
                detail.append("invisible to the {} layer".format(layer))
            if banned:
                detail.append("banned: " + ", ".join(banned))
            if warn:
                detail.append("warn: " + ", ".join(warn))
            if not restrained:
                detail.append("no hedging word - reads as absolute")

            rows.append({
                "group": group, "key": key, "layer": layer,
                "detectable": bool(hits), "clean": not banned and not warn,
                "positive": not negated_only, "restrained": restrained,
                "hit": hits[0] if hits else None,
                "detail": "; ".join(detail),
            })
    return rows


def check_compatibility(bank=None):
    """Every compatibility entry names real keys, and every dominance has at
    least one ratio it can honestly be expressed at.

    A dominance with an empty or misspelled ratio list would make
    compose_typography() refuse every combination containing it - a bank typo
    that presents as 'this option is simply broken'.
    """
    bank = bank or bt.load_bank()
    ratios = set(bt.options(bank, "ratio"))
    problems = []
    for dominance in bt.options(bank, "dominance"):
        allowed = bt.compatible_ratios(bank, dominance)
        if not allowed:
            problems.append("'{}' has no compatible ratio at all".format(dominance))
            continue
        unknown = [r for r in allowed if r not in ratios]
        if unknown:
            problems.append("'{}' names unknown ratios: {}".format(
                dominance, ", ".join(unknown)))
    # ...and every ratio must be reachable from at least one dominance, or it
    # is an option nobody can ever legally pick.
    reachable = {r for d in bt.options(bank, "dominance")
                 for r in bt.compatible_ratios(bank, d)}
    for ratio in ratios:
        if ratio not in reachable:
            problems.append("ratio '{}' is unreachable from any dominance".format(ratio))
    return problems


def check_conflicts(bank=None):
    """Every named conflict pair refers to options that actually exist."""
    bank = bank or bt.load_bank()
    problems = []
    for pair in bank.get("conflicts", {}).get("pairs", []):
        for token in pair:
            group, _, key = token.partition(":")
            if key not in bt.options(bank, group):
                problems.append("conflict pair names a missing option: '{}'".format(token))
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Audit typography_bank.json against realism_lint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--quiet", action="store_true", help="exit code only")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    rows = audit()
    bad = [r for r in rows
           if not (r["detectable"] and r["clean"] and r["positive"] and r["restrained"])]
    structural = check_compatibility() + check_conflicts()

    if not args.quiet:
        for row in rows:
            ok = row["detectable"] and row["clean"] and row["positive"] and row["restrained"]
            print("  {} {:<34} {:<12} {}".format(
                "[ok] " if ok else "[BAD]",
                "{}:{}".format(row["group"], row["key"]), row["layer"],
                'sees "{}"'.format(row["hit"]) if ok else row["detail"]))
        print()
        for problem in structural:
            print("  [BAD] {}".format(problem))
        print("{}/{} options clean{}.".format(
            len(rows) - len(bad), len(rows),
            "" if not structural else ", {} structural problem(s)".format(len(structural))))

    return 1 if (bad or structural) else 0


if __name__ == "__main__":
    raise SystemExit(main())
