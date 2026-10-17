"""Opt-in skin features for a person - freckles, a beauty mark, redness, ...

Usage:
    python tools/build_skin_features.py --feature freckles --shot portrait
    python tools/build_skin_features.py --feature freckles --feature redness \
        --subject "a man in his forties" --shot-custom "full body shot"
    python tools/build_skin_features.py --list

THE IDEA. Freckles used to turn up in prompts nobody asked for them in - not
from the builder, but from the AI helpers, which were shown freckled worked
examples. Now a skin feature is a choice: ticked on Compose's Subject tab,
saved with the character as spec["skin_features"] (a list of keys), and off
by default. The AI helpers are told not to invent any of them.

Three rules:
  * People only. A cat has no freckles to give, and an object has no face.
  * Scaled by distance, with the same tiers as face detail
    (build_face_detail.shot_tier). A tier set to null in the bank skips the
    feature: freckles on a full-body frame are detail no lens resolves.
  * The user's own words win. A Subject that already says "freckles" is not
    told so twice.

Lands in spec["overrides"]["skin_features"], a non-layer override that
build_prompt.free_overrides() appends to the free trailing segment, so it adds
to the bank's texture picks and can never lower a realism score.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import build_evidence as be  # noqa: E402
import build_face_detail as bfd  # noqa: E402

BANK_PATH = TOOLS / "skin_features_bank.json"

_FACE_BANK = None


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _face_bank():
    global _FACE_BANK
    if _FACE_BANK is None:
        _FACE_BANK = bfd.load_bank()
    return _FACE_BANK


def labels(bank):
    """[(key, label)] in bank order - the order the chips are shown in."""
    return [(key, cfg["label"]) for key, cfg in bank["features"].items()]


def in_bank_order(bank, keys):
    """The known keys of `keys`, in bank order, each once. Unknown keys drop."""
    wanted = set(keys or [])
    return [key for key in bank["features"] if key in wanted]


def compose_skin_features(bank, keys, subject="", shot="", shot_custom="", kind=None):
    """(phrase, skipped). phrase is "" when nothing applies.

    `skipped` lists (key, reason) for each picked feature that was left out,
    so a caller can say why rather than go quiet.
    """
    keys = in_bank_order(bank, keys)
    if not keys:
        return "", []
    kind = kind or be.subject_kind(be.load_bank(), subject)
    if kind != "human":
        return "", [(key, "not a person") for key in keys]
    tier = bfd.shot_tier(_face_bank(), shot, shot_custom)
    text = str(subject or "").lower()
    phrases, skipped = [], []
    for key in keys:
        cfg = bank["features"][key]
        if any(word in text for word in cfg["detect"]):
            skipped.append((key, "already in the Subject"))
        elif not cfg.get(tier):
            skipped.append((key, "too small to see in a {} shot".format(tier)))
        else:
            phrases.append(cfg[tier])
    return ", ".join(phrases), skipped


def for_spec(bank, spec, kind=None):
    """compose_skin_features() read straight off a build_prompt spec dict."""
    return compose_skin_features(bank, spec.get("skin_features", []), spec.get("subject", ""),
                                 spec.get("shot", ""), spec.get("shot_custom", ""), kind)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Opt-in skin features for a person, scaled to the shot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--feature", action="append", default=[],
                   help="a feature key (repeatable); see --list")
    p.add_argument("--subject", default="a person")
    p.add_argument("--shot", default="", help="a shot preset key")
    p.add_argument("--shot-custom", default="", help="a typed shot, read by keyword")
    p.add_argument("--list", action="store_true", help="print every feature and exit")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for key, cfg in bank["features"].items():
            print("{} - {}".format(key, cfg["label"]))
            for tier in bfd.TIERS:
                print("  {:5}  {}".format(tier, cfg.get(tier) or "(skipped)"))
        return 0

    unknown = [key for key in args.feature if key not in bank["features"]]
    if unknown:
        print("Unknown feature(s): {}. Use --list.".format(", ".join(unknown)), file=sys.stderr)
        return 2
    phrase, skipped = compose_skin_features(bank, args.feature, args.subject,
                                            args.shot, args.shot_custom)
    for key, reason in skipped:
        print("[skipped {}: {}]".format(key, reason), file=sys.stderr)
    if phrase:
        print(phrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
