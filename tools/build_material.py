"""Material response: how the things in THIS scene react to light.

Usage:
    python tools/build_material.py --list
    python tools/build_material.py --subject "a woman holding a coffee mug" --wardrobe "a wool sweater"
    python tools/build_material.py --subject "a perfume bottle" --setting "on a marble counter"

THE PROBLEM. Everything in a generated image tends to reflect light the same
way - one smooth, even sheen - so glass, ceramic, wool and toast all look made
of the same stuff. lighting_bank.json has a single generic technique for this
("crisp highlights on metal, soft catchlight on glass, matte absorption on
fabric"), the same words whatever is actually in the picture, and nothing at
all for food. This names the materials the scene really contains and the one
thing each does with light: glass bends what is behind it, a glaze holds a
rounded highlight, a cold glass beads with condensation, knit gets a fuzzy
halo, melted cheese an oil sheen.

HOW. material_bank.json lists materials with whole-word keywords; Subject,
Wardrobe, Setting and Action are read together, earliest mention first, at
most `max_phrases`. `excludes` drops a contradicting match (iced coffee gets
condensation, never rising steam). No match gives nothing - a phrase about a
material that is not there is worse than none.

Lands in spec["overrides"]["material"] via build_prompt.apply_physical() - a
non-layer override, appended to the free tail. When something matched,
apply_physical() also takes the generic lighting technique out of an explicit
lighting choice (generic_phrase() below), so the prompt never says it twice.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_contact as bct  # noqa: E402
import build_lighting as blt  # noqa: E402

BANK_PATH = Path(__file__).resolve().parent / "material_bank.json"
TEXT_FIELDS = ("subject", "wardrobe", "setting", "action")


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def generic_phrase(bank):
    """lighting_bank.json's one-size-fits-all material sentence, or ""."""
    key = bank.get("generic_technique", "")
    return blt.techniques(blt.load_bank()).get(key, {}).get("phrase", "")


def read_materials(bank, spec):
    """(phrase, matched keys) for a spec - earliest mention first, excludes applied.

    A `weak` match (a bowl, a cup - a shape, not a material) is kept only
    when nothing stronger matched, so "a metal bowl" is metal alone. Two
    keys sharing one phrase (a mug and a plate) say it once.
    """
    materials = bank.get("materials", {})
    keys = bct.mentioned(materials, bct.spec_text(spec, TEXT_FIELDS))
    dropped = {x for k in keys for x in materials[k].get("excludes", [])}
    keys = [k for k in keys if k not in dropped]
    if any(not materials[k].get("weak") for k in keys):
        keys = [k for k in keys if not materials[k].get("weak")]
    unique, phrases = [], []
    for key in keys:
        if materials[key]["phrase"] not in phrases:
            unique.append(key)
            phrases.append(materials[key]["phrase"])
    limit = int(bank.get("max_phrases", 2))
    return ", ".join(phrases[:limit]), unique[:limit]


def without_generic(text, generic):
    """`text` with the generic sentence and its joining comma removed."""
    if not generic or generic not in text:
        return text
    for joined in (", " + generic, generic + ", ", generic):
        if joined in text:
            return text.replace(joined, "", 1).strip()
    return text


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose material response - how the things in this scene react to light.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--subject", default="")
    p.add_argument("--wardrobe", default="")
    p.add_argument("--setting", default="")
    p.add_argument("--action", default="")
    p.add_argument("--list", action="store_true", help="print every material and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()
    if args.list:
        for key, cfg in bank["materials"].items():
            print("  {:<12} {}".format(key, ", ".join(cfg["keywords"])))
            print("  {:<12} -> {}".format("", cfg["phrase"]))
        return 0
    spec = {"subject": args.subject, "wardrobe": args.wardrobe, "setting": args.setting,
            "action": args.action}
    phrase, _keys = read_materials(bank, spec)
    if not phrase:
        print("(no material recognised - nothing added)", file=sys.stderr)
        return 0
    print(phrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
