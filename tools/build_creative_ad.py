"""Build a static ad from an insight, a strategic idea and two or more
creative routes - one composed shot per route.

Usage:
    python tools/build_creative_ad.py --list
    python tools/build_creative_ad.py --brief temp/resources/briefs/lumawash.json
    python tools/build_creative_ad.py --brief x.json --no-write
    python tools/build_creative_ad.py --example        # print a worked brief

WHAT THIS IS, AND WHAT tools/build_static_ad.py IS. That one builds the two
composites the course teaches - product on a clean background, and a presenter
holding it toward camera. Both are product photographs, which is exactly what
command 8 of tools/creative_direction_bank.json says to push past. This builds
from an IDEA instead: each route carries a `device` - the visual thought - and
the device becomes the subject of the composed prompt, so the product is
load-bearing in the picture rather than placed in it.

THE BRIEF is one JSON object:

    {"product": "LumaWash shampoo, 250ml amber bottle",
     "product_reference": "temp/resources/images/lumawash.png",
     "insight": "...", "idea": "...", "tier": "premium",
     "typography": {"dominance": "image-led", "ratio": "editorial",
                    "zone": "upper-left", "lockup": "corner-quiet",
                    "reading_order": "headline-product-logo",
                    "headline": "Ten minutes back"},
     "routes": [{"key": "absence", "name": "...", "rationale": "...",
                 "device": "...", "tier": "premium"}, ...]}

Every shot is composed through build_prompt.compose(), so the eight-layer
realism gate still applies exactly as it does everywhere else, and the type
direction rides in as `overrides` from build_typography.compose_typography()
rather than as free text - which is what lets creative_ad_lint.py's `hierarchy`
row check it rather than take its word for it.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import build_static_ad as bsa  # noqa: E402
import build_typography as bt  # noqa: E402
import creative_ad_lint as cal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"


class BriefError(ValueError):
    """A brief that cannot be composed - a missing product, no routes, or a
    route naming a territory the bank does not have."""


EXAMPLE = {
    "product": "LumaWash shampoo, 250ml amber bottle",
    "product_reference": "temp/resources/images/lumawash-product.png",
    "insight": "You do not want a cleaner house, you want ten minutes where "
               "nobody needs anything from you",
    "idea": "Sell the ten minutes back, not the work done",
    "tier": "premium",
    "typography": {
        "dominance": "image-led", "ratio": "editorial", "zone": "upper-left",
        "lockup": "corner-quiet", "reading_order": "headline-product-logo",
        "restraint": ["one-idea"], "headline": "Ten minutes back",
    },
    "routes": [
        {"key": "absence", "name": "The clean ring",
         "rationale": "The insight is about time reclaimed, and absence is the "
                      "only territory that can photograph something that is gone",
         "device": "a bathroom shelf photographed at dawn with a single clean "
                   "ring in the dust where the LumaWash bottle stood, everything "
                   "else untouched",
         "tier": "premium"},
        {"key": "ritual", "name": "Fifteen seconds, every night",
         "rationale": "Time returned is only legible against the time already "
                      "spent, so show the habit the product sits inside",
         "device": "the same fifteen seconds at the sink with the LumaWash "
                   "bottle in reach, repeated as a grid of near-identical "
                   "frames across one year",
         "tier": "premium"},
    ],
}


def validate(bank, brief):
    """Raise BriefError on anything that makes composition impossible.

    Deliberately NOT a quality check - creative_ad_lint.py judges whether the
    idea is any good. This only refuses what cannot be built at all.
    """
    if not (brief.get("product") or "").strip():
        raise BriefError("Give a product - name it exactly, including the label text.")
    entries = brief.get("routes") or []
    if not entries:
        raise BriefError(
            "Give at least one route. Command 9 wants two from different "
            "territories; see --list.")
    known = cal.routes(bank)
    for route in entries:
        if route.get("key") not in known:
            raise BriefError(
                "Unknown territory '{}'. Available: {}".format(
                    route.get("key"), ", ".join(sorted(known))))
        if not (route.get("device") or "").strip():
            raise BriefError(
                "Route '{}' has no device - the device IS the idea.".format(route["key"]))
    tier = brief.get("tier")
    if tier and tier not in cal.tiers(bank):
        raise BriefError("Unknown tier '{}'. Available: {}".format(
            tier, ", ".join(sorted(cal.tiers(bank)))))
    return None


def _object_overrides(bank, route):
    """Swap the portrait vocabulary for surface vocabulary, unless the route
    says it carries a person.

    prompt_bank.json is written for portraits: "realistic skin textures" is one
    of its eight core terms and half the texture layer is skin. Composed
    untouched, this builder's own worked example produced "realistic skin
    textures of a bathroom shelf". The replacements live in the bank rather
    than here, and score the same two layers - see its `object_vocabulary`
    note for which keys and why that count.
    """
    if route.get("has_person"):
        return {}
    vocab = bank.get("object_vocabulary", {})
    return {layer: list(vocab[layer]) for layer in ("core", "texture") if vocab.get(layer)}


def _route_spec(static_bank, brief, route, index, type_overrides, object_overrides=None):
    """One route's character spec.

    The DEVICE becomes the subject. That is the whole difference between this
    and build_static_ad.py, where the subject is either the product itself or a
    presenter holding it - both product photographs. The label-accuracy
    instruction from the course lesson still rides along, because a mislabelled
    pack fails a brilliant idea exactly as badly as a dull one.
    """
    spec = dict(brief.get("base_spec") or {})
    spec.pop("variation", None)
    spec["subject"] = route["device"]
    for field in ("wardrobe", "action"):
        spec.pop(field, None)
    spec["seed"] = spec.get("seed", 0) + index
    spec["slug"] = "{}-{}".format(
        bp.slugify(brief.get("product") or "ad"), route["key"])

    extra = list(spec.get("extra", []))
    phrase = static_bank.get("label_accuracy_phrase", "")
    if phrase and phrase not in extra:
        extra.append(phrase)
    spec["extra"] = extra

    overrides = dict(spec.get("overrides", {}))
    # Subject vocabulary REPLACES - a shelf should not also be described as
    # skin. A brief that set its own core/texture override wins over both.
    for layer, phrases in (object_overrides or {}).items():
        overrides.setdefault(layer, list(phrases))
    # Type direction EXTENDS, because it lands on `composition`, which the
    # photograph has its own opinion about and both are true at once.
    for layer, phrases in (type_overrides or {}).items():
        overrides[layer] = list(overrides.get(layer, [])) + list(phrases)
    if overrides:
        spec["overrides"] = overrides
    return spec


def compose_creative_ad(bank, image_bank, brief):
    """Brief -> (shots, warnings). One shot per route, composed and gated.

    Type direction is resolved ONCE and applied to every route, because a
    campaign whose routes each carry a different hierarchy is not a campaign.
    """
    validate(bank, brief)
    static_bank = bsa.load_bank()

    type_overrides, warnings = {}, []
    typo = brief.get("typography") or {}
    if typo:
        type_overrides, warnings = bt.compose_typography(
            bt.load_bank(),
            dominance=typo.get("dominance"), ratio=typo.get("ratio"),
            zone=typo.get("zone"), lockup=typo.get("lockup"),
            reading_order=typo.get("reading_order"),
            restraint=typo.get("restraint", ()), headline=typo.get("headline"))

    shots = []
    reference = brief.get("product_reference")
    for index, route in enumerate(brief["routes"]):
        spec = _route_spec(static_bank, brief, route, index, type_overrides,
                           _object_overrides(bank, route))
        prompt, layers = bp.compose(image_bank, spec)
        shots.append({
            "route": route["key"],
            "name": route.get("name", route["key"]),
            "tier": route.get("tier") or brief.get("tier"),
            "device": route["device"],
            "rationale": route.get("rationale", ""),
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
            "references": [reference] if reference else [],
        })
    return shots, warnings


def build(bank, image_bank, brief):
    """The whole artefact creative_ad_lint.py reads: the brief plus its shots."""
    shots, warnings = compose_creative_ad(bank, image_bank, brief)
    ad = dict(brief)
    ad["shots"] = shots
    return ad, warnings


def write_creative_ad(ad):
    """Write a readable .txt and the .json creative_ad_lint.py's CLI reads."""
    slug = bp.slugify(ad.get("product") or "ad")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = OUT_DIR / "creative-ad-{}-{}.txt".format(slug, stamp)
    json_path = OUT_DIR / "creative-ad-{}-{}.json".format(slug, stamp)

    blocks = ["INSIGHT   {}".format(ad.get("insight", "")),
              "IDEA      {}".format(ad.get("idea", "")),
              "TIER      {}".format(ad.get("tier", "-")), ""]
    for shot in ad["shots"]:
        blocks.append("=== {} ({})".format(shot["name"], shot["route"]))
        if shot["rationale"]:
            blocks.append("why: {}".format(shot["rationale"]))
        if shot["references"]:
            blocks.append("references: {}".format(", ".join(shot["references"])))
        blocks.append(shot["prompt"])
        blocks.append("")
    txt_path.write_text("\n".join(blocks), encoding="utf-8")
    json_path.write_text(json.dumps(ad, indent=2), encoding="utf-8")
    return txt_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a static ad from an insight, an idea and two or more routes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--brief", help="path to a brief JSON (see the module docstring)")
    p.add_argument("--product", help="override the brief's product")
    p.add_argument("--insight", help="override the brief's insight")
    p.add_argument("--idea", help="override the brief's strategic idea")
    p.add_argument("--tier", help="mass, premium or luxury")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompts")
    p.add_argument("--list", action="store_true", help="print every territory and tier, then exit")
    p.add_argument("--example", action="store_true", help="print a worked brief JSON and exit")
    p.add_argument("--no-write", action="store_true", help="print only, do not write files")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = cal.load_bank()

    if args.example:
        print(json.dumps(EXAMPLE, indent=2))
        return 0

    if args.list:
        print("TERRITORIES  (a route names one)")
        for key, cfg in cal.routes(bank).items():
            print("  {:<26} {}".format(key, cfg["label"]))
            print("  {:<26} {}".format("", cfg["asks"]))
            print("  {:<26} e.g. {}".format("", cfg["example_device"]))
            print("  {:<26} suits: {}".format("", ", ".join(cfg["tiers"])))
        print()
        print("TIERS  (recorded, never scored - see command 7)")
        for key, note in cal.tiers(bank).items():
            print("  {:<26} {}".format(key, note))
        return 0

    if not args.brief:
        sys.exit("Give --brief <path to a brief JSON>, or --example to see one.")
    path = Path(args.brief)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Brief not found: {}".format(path))
    brief = json.loads(path.read_text(encoding="utf-8"))

    for field, value in (("product", args.product), ("insight", args.insight),
                         ("idea", args.idea), ("tier", args.tier)):
        if value:
            brief[field] = value
    if args.seed is not None:
        base = dict(brief.get("base_spec") or {})
        base["seed"] = args.seed
        brief["base_spec"] = base

    try:
        ad, warnings = build(bank, bp.load_bank(), brief)
    except (BriefError, bt.TypographyError) as exc:
        sys.exit(str(exc))

    for shot in ad["shots"]:
        print("=== {} ({})".format(shot["name"], shot["route"]))
        print(shot["prompt"])
        print()
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)

    if not args.no_write:
        path = write_creative_ad(ad)
        print("[creative-ad] {}".format(path), file=sys.stderr)
        print("[next]        python tools/creative_ad_lint.py --ad {}".format(
            str(path).replace(".txt", ".json")), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
