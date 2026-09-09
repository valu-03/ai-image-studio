"""Compose a persona's Subject description from structured picks - name,
gender, age range, hair/eye colour and aesthetic style tags.

Usage:
    python tools/build_persona.py --list
    python tools/build_persona.py --name Zoe --gender woman --age-range 25-30 \\
        --hair-color blonde --eye-color blue --style luxury --style lifestyle \\
        --details "a small nose stud, always carries a film camera"

Every field is optional, and an unrecognised key is simply dropped rather than
raising - there is no invalid *combination* here the way an over-specified
lighting/colour pick can be (compose_lighting()'s LightingError, compose_color()'s
ColorError). Gender and age default to a plain, neutral fallback so
compose_persona() always returns something usable, the same "a person"
SpecEditor.PLACEHOLDER_SUBJECT already falls back to when its own Subject box
is empty.

Deliberately NOT here: any attractiveness, face-shape or body-shape control. A
face or build is free-text prose in `--details`, the same way every other
descriptive spec field in this app already works - not a slider tuned toward
an idealised standard.

Persona is NOT one of realism_lint.py's 8 gated photorealism layers - it is
descriptive spec content like wardrobe/setting/mood, so there is no
`DETECT` keyword requirement here. The composed sentence is meant to be typed
straight into Compose's own Subject field (ui/spec_editor.py) - see
PosingView's own precedent, InfluencerStudioView.apply_to_compose() /
SpecEditor.set_subject_override().

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "persona_bank.json"

FALLBACK_GENDER_PHRASE = "a person"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def genders(bank):
    return bank.get("genders", {})


def age_ranges(bank):
    return bank.get("age_ranges", {})


def style_tags(bank):
    return bank.get("style_tags", {})


def hair_colors(bank):
    return bank.get("hair_colors", {})


def eye_colors(bank):
    return bank.get("eye_colors", {})


def compose_persona(bank, name=None, gender=None, age_range=None,
                     style_tags_=(), hair_color=None, eye_color=None, details=None):
    """One flowing Subject sentence from whatever picks are given.

    Unrecognised keys for gender/age_range/hair_color/eye_color are treated as
    "not given" rather than raising - a suggestion (the Advisor's own
    `sections` schema follows the same rule) or a stale saved persona field
    should degrade gracefully, not blow up the whole compose. Unrecognised
    `style_tags_` entries are filtered out, not smuggled through as literal
    text - style is chosen from the bank's own vocabulary, not typed.
    """
    gender_cfg = genders(bank).get(gender or "")
    gender_phrase = gender_cfg["phrase"] if gender_cfg else FALLBACK_GENDER_PHRASE

    sentence = gender_phrase

    age_cfg = age_ranges(bank).get(age_range or "")
    if age_cfg:
        sentence += " " + age_cfg["phrase"]

    features = []
    hair_cfg = hair_colors(bank).get(hair_color or "")
    if hair_cfg:
        features.append(hair_cfg["phrase"])
    eye_cfg = eye_colors(bank).get(eye_color or "")
    if eye_cfg:
        features.append(eye_cfg["phrase"])
    if features:
        sentence += ", with " + " and ".join(features)

    table = style_tags(bank)
    picked = [table[key]["phrase"] for key in style_tags_ if key in table]
    if picked:
        joined = ", ".join(picked)
        article = "an" if joined[:1].lower() in "aeiou" else "a"
        sentence += ", styled with {} {} aesthetic".format(article, joined)

    sentence = sentence.strip()
    if not sentence.endswith("."):
        sentence += "."

    parts = []
    if name and name.strip():
        parts.append(name.strip() + ",")
    parts.append(sentence)
    result = " ".join(parts).strip()

    if details and details.strip():
        result += " " + details.strip()

    return result


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a persona's Subject description from structured picks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--name", help="the persona's name, optional")
    p.add_argument("--gender", help="a bank key (see --list)")
    p.add_argument("--age-range", help="a bank key (see --list)")
    p.add_argument("--style", action="append", default=[],
                    help="an aesthetic style tag to stack on, repeatable (see --list)")
    p.add_argument("--hair-color", help="a bank key (see --list)")
    p.add_argument("--eye-color", help="a bank key (see --list)")
    p.add_argument("--details", help="free-text description appended as-is")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for title, table in [
            ("GENDERS", genders(bank)), ("AGE RANGES", age_ranges(bank)),
            ("STYLE TAGS", style_tags(bank)), ("HAIR COLORS", hair_colors(bank)),
            ("EYE COLORS", eye_colors(bank)),
        ]:
            print(title)
            for key, cfg in table.items():
                print("  {:<20} {}".format(key, cfg["label"]))
        return 0

    result = compose_persona(
        bank, name=args.name, gender=args.gender, age_range=args.age_range,
        style_tags_=args.style, hair_color=args.hair_color, eye_color=args.eye_color,
        details=args.details,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
