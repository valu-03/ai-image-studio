"""Face (or coat) micro-detail, scaled to how close the shot is.

Usage:
    python tools/build_face_detail.py --shot portrait --subject "a woman in her thirties"
    python tools/build_face_detail.py --shot-custom "extreme close-up beauty portrait" --seed 2
    python tools/build_face_detail.py --shot environmental --subject "a ginger tabby cat"
    python tools/build_face_detail.py --list

THE IDEA. The user-supplied FULL FACE prompt is the best skin-realism writing in
this project - pore-level skin per zone, sebaceous texture, peach fuzz, iris
fibres, "never a single uniform skin tone", natural asymmetry - but only the
Macro Insert workflow could reach it. This brings it to every person (and pet)
in Compose, with one rule the source prompt did not need because it was always
an extreme close-up: SCALE BY DISTANCE.

    close  extreme close-up / headshot   pore-level, per zone, iris, brows
    mid    close-up / portrait / medium  zonal tone, subsurface warmth, asymmetry
    wide   medium-wide / full body       asymmetry and tone only - NO pores

Pores in a full-body frame are detail the camera physically cannot resolve, and
asking for them makes the model over-sharpen the face into a render. The tier is
read from the shot preset, or from keywords in a typed shot (shot_tier()).

Human close-tier phrases are keyed into macro_insert_bank.json and animal tiers
into pet_realism_bank.json - never copied. An object or place has no face, so
face_detail() returns "" for those.

Lands in spec["overrides"]["face_detail"], a non-layer override that
build_prompt.free_overrides() appends to the free trailing segment - it adds
texture keywords on top of the bank's own texture picks rather than replacing
them, so it cannot lower a realism score or disturb history.weights().

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import build_evidence as be  # noqa: E402

BANK_PATH = TOOLS / "face_detail_bank.json"
MACRO_PATH = TOOLS / "macro_insert_bank.json"
PET_PATH = TOOLS / "pet_realism_bank.json"

TIERS = ("close", "mid", "wide")


def _load(path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_bank():
    """The face-detail bank with the two banks it keys into attached, so one
    object is enough to resolve any tier."""
    bank = _load(BANK_PATH)
    bank["_macro"] = _load(MACRO_PATH)
    bank["_pet"] = _load(PET_PATH)
    return bank


def _has(text, needle):
    # Word-bounded, but a hyphen counts as a boundary: "extreme close" has to
    # match inside "extreme close-up".
    return re.search(r"(?<!\w){}(?!\w)".format(re.escape(needle)), text) is not None


def shot_tier(bank, shot="", shot_custom=""):
    """'close', 'mid' or 'wide' for a shot preset key or a typed shot.

    A typed shot is read by keyword, close before wide before mid: "extreme
    close-up" contains "close-up", and "medium-wide" contains "medium", so the
    more specific tier has to be asked first. A preset with no entry, or no
    shot at all, falls to the bank's default.
    """
    cfg = bank["shot_tiers"]
    custom = str(shot_custom or "").lower()
    if custom:
        for tier in ("close", "wide", "mid"):
            if any(_has(custom, word) for word in cfg["keywords"][tier]):
                return tier
        return cfg["default"]
    return cfg["presets"].get(shot or "", cfg["default"])


def species_of(bank, subject):
    text = str(subject or "").lower()
    for species, words in bank["animal"]["species_words"].items():
        if any(_has(text, word) for word in words):
            return species
    return None


def human_pool(bank, tier):
    """Every phrase the human `tier` can draw from, sources resolved."""
    cfg = bank["human"][tier]
    pool = []
    for ref in cfg.get("from", []):
        texture = bank["_macro"]["inserts"][ref["insert"]]["overrides"]["texture"]
        pool.extend([texture[ref["index"]]] if "index" in ref else texture)
    pool.extend(cfg.get("phrases", []))
    # A source listed twice (the eye's lash phrase is also full-face's) must
    # not be drawn twice.
    return list(dict.fromkeys(pool))


def animal_pool(bank, tier, species):
    """Coat/face phrases from pet_realism_bank.json for this species and tier.
    Only groups both the tier asks for AND the species carries - a dog has no
    `face` group (slit pupils are feline)."""
    pet = bank["_pet"]
    allowed = pet["species"].get(species, {}).get("groups", [])
    pool = []
    for group in bank["animal"][tier]["groups"]:
        if group in allowed:
            pool.extend(pet["groups"][group]["phrases"])
    return pool


def face_detail(bank, subject="", shot="", shot_custom="", seed=0, kind=None):
    """(phrase, tier, kind). phrase is "" when the subject has no face to detail.

    Picks are reproducible by seed and emitted in pool order, so the same
    spec always composes the same prompt.
    """
    kind = kind or be.subject_kind(be.load_bank(), subject)
    tier = shot_tier(bank, shot, shot_custom)
    if kind == "human":
        pool, count = human_pool(bank, tier), bank["human"][tier]["pick"]
    elif kind == "animal":
        species = species_of(bank, subject)
        if not species:
            return "", tier, kind
        pool, count = animal_pool(bank, tier, species), bank["animal"][tier]["pick"]
    else:
        return "", tier, kind
    count = min(count, len(pool))
    chosen = set(random.Random("face:{}:{}:{}".format(kind, tier, seed)).sample(pool, count))
    return ", ".join(p for p in pool if p in chosen), tier, kind


def for_spec(bank, spec):
    """face_detail() read straight off a build_prompt spec dict."""
    return face_detail(bank, spec.get("subject", ""), spec.get("shot", ""),
                       spec.get("shot_custom", ""), spec.get("seed", 0))


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Face or coat micro-detail, scaled to the shot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--subject", default="a person")
    p.add_argument("--shot", default="", help="a shot preset key")
    p.add_argument("--shot-custom", default="", help="a typed shot, read by keyword")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--list", action="store_true", help="print every tier's pool and exit")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for tier in TIERS:
            print("HUMAN {} - {} (picks {})".format(
                tier.upper(), bank["human"][tier]["label"], bank["human"][tier]["pick"]))
            for phrase in human_pool(bank, tier):
                print("  - " + phrase)
            print()
        return 0

    phrase, tier, kind = face_detail(bank, args.subject, args.shot, args.shot_custom, args.seed)
    if not phrase:
        print("(no face detail for this subject: {})".format(kind), file=sys.stderr)
        return 0
    print(phrase)
    print("[{} tier, {}]".format(tier, kind), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
