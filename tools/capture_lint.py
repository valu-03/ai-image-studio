"""Audit tools/capture_bank.json against the gate it is meant to strengthen.

Usage:
    python tools/capture_lint.py
    python tools/capture_lint.py --quiet     # exit code only

THE FAILURE THIS EXISTS TO CATCH. tools/story_bank.json once carried four
phrases that read exactly like fur vocabulary - "visible individual fur
strands", "whisker detail", "wet nose texture", "natural animal anatomy" - and
realism_lint could not see a single one of them. Deleting all four changed the
scene's 8/8 by nothing. Vocabulary a bank can write but the gate cannot detect
is decoration, and it is invisible decoration: everything still passes, so
nothing ever complains.

Three checks, per phrase, never assumed:

    detectable    the phrase is visible to the layer it claims to strengthen
    clean         it trips no banned term and no soft warn term
    restrained    it is hedged ("faint", "subtle", "slight", ...) rather than
                  absolute - a shouted artefact is a filter, not a photograph

`clean` matters more here than for most banks: film-stock language sits close
to the "cinematic masterpiece" / "award-winning" vocabulary prompt_bank.json's
warn list exists to catch, and a bank that shipped one of those words would be
teaching the app to write them.

Standard library only. No API keys, no network.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_capture as bc  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

# A real artefact is faint. One of these words must appear, so the bank cannot
# drift toward "heavy halation, extreme vignetting" one well-meaning edit at a
# time.
HEDGES = ("faint", "subtle", "slight", "mild", "gentle", "gently", "natural",
          "fine", "just", "marginally", "one or two", "a degree or two",
          "softly", "soft", "restrained", "crisp", "pronounced", "around")

# ...but only where intensity is a thing the option HAS. A group may opt out
# with "restraint": false. The `evidence` group does: a crop is imperfect or it
# is not, and on-camera flash falls off hard by definition - that hardness is
# the look. Scoping the rule to where it means something is the honest move;
# deleting it to reach 19/19 would have been the other one.


def audit(bank=None, image_bank=None):
    """[{group, key, layer, detectable, clean, restrained, detail}] - one row
    per option, in bank order."""
    bank = bank or bc.load_bank()
    image_bank = image_bank or bp.load_bank()
    rows = []
    for group, cfg in bc.groups(bank).items():
        for key, option in cfg["options"].items():
            phrase = option["phrase"].lower()
            layer = bc.layer_of(bank, group, key)
            hits = rl.layer_hits(rl.DETECT[layer]["keys"], phrase) if layer in rl.DETECT else []
            banned, _ = rl.find_terms(phrase, image_bank["banned"])
            warn, _ = rl.find_terms(phrase, image_bank["warn"])
            detail = []
            if not hits:
                detail.append("invisible to the {} layer".format(layer))
            if banned:
                detail.append("banned: " + ", ".join(banned))
            if warn:
                detail.append("warn: " + ", ".join(warn))
            wants_restraint = cfg.get("restraint", True)
            restrained = (not wants_restraint) or any(word in phrase for word in HEDGES)
            if not restrained:
                detail.append("no hedging word - reads as absolute")
            rows.append({
                "group": group, "key": key, "layer": layer,
                "detectable": bool(hits), "clean": not banned and not warn,
                "restrained": restrained,
                "hit": hits[0] if hits else None,
                "detail": "; ".join(detail),
            })
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Audit capture_bank.json against realism_lint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--quiet", action="store_true", help="exit code only")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    rows = audit()
    bad = [r for r in rows if not (r["detectable"] and r["clean"] and r["restrained"])]

    if not args.quiet:
        for row in rows:
            ok = row["detectable"] and row["clean"] and row["restrained"]
            print("  {} {:<24} {:<12} {}".format(
                "[ok] " if ok else "[BAD]", row["key"], row["layer"],
                'sees "{}"'.format(row["hit"]) if ok else row["detail"]))
        print()
        print("{}/{} options clean.".format(len(rows) - len(bad), len(rows)))

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
