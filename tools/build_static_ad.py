"""Build a static (non-video) product ad: a studio composite, a lifestyle
composite, or both.

Usage:
    python tools/build_static_ad.py --product "LumaWash shampoo, 250ml amber bottle" \\
        --reference temp/resources/images/lumawash-product.png
    python tools/build_static_ad.py --spec temp/resources/characters/ada.json \\
        --product "..." --reference temp/resources/images/lumawash-product.png \\
        --presenter-reference temp/resources/characters/ada-ref.png --mode lifestyle
    python tools/build_static_ad.py --list

AI Video Bootcamp Phase 3, "Avatar Product Images & Wise Chat": an avatar
holding the product toward camera, the label "sharp, readable and consistent" -
the `lifestyle` mode here. `studio` mode reuses tools/style_bank.json's own
existing `studio-lighting` style rather than inventing vocabulary for a
technique the course never taught as a paired ad-type (see static_ad_bank.json's
own `source` field for the honest caveat).

No timing, no beats - see tools/build_ad.py for the video/timed version this
deliberately does not import beat_timings()/product_starts_at() from. The
product photo rides as a plain reference image, not a lock_identity/lock_scene
clause: packaging/label fidelity is carried by the reference image itself
(Nano Banana Pro's own multi-image conditioning), the same way ads.py's
existing `product_reference` already works.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import build_style as bstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "static_ad_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def modes(bank):
    return bank.get("modes", {})


def validate_mode(bank, mode):
    """Return an error message for an unknown mode, or None. "both" is not a
    bank key - it means every mode, so it is always valid."""
    if mode and mode != "both" and mode not in modes(bank):
        return "Unknown mode '{}'. Available: both, {}".format(mode, ", ".join(modes(bank)))
    return None


def _mode_spec(bank, style_bank, mode_cfg, base_spec, product, setting=None):
    """One composite's character spec.

    Studio has no presenter - `subject` becomes the product itself, and the
    style is overridden to the reused `studio-lighting` look. Lifestyle keeps
    the presenter's own subject/wardrobe and states the exact label-accuracy
    instruction from the source lesson either way - a mislabelled product
    fails a studio shot exactly as badly as a lifestyle one.
    """
    spec = dict(base_spec)
    spec.pop("variation", None)
    spec["shot"] = spec.get("shot") or mode_cfg.get("shot")

    extra = list(spec.get("extra", []))
    extra.append(bank.get("label_accuracy_phrase", ""))

    if mode_cfg.get("presenter"):
        spec.setdefault("subject", "a person")
        spec["action"] = spec.get("action") or "holding {} toward the camera".format(product)
        spec["setting"] = setting or spec.get("setting") or mode_cfg.get("example_setting", "")
    else:
        spec["subject"] = product
        for field in ("wardrobe", "action", "setting"):
            spec.pop(field, None)
        style_phrase, _warnings = bstyle.compose_style(style_bank, style=mode_cfg.get("style"))
        overrides = dict(spec.get("overrides", {}))
        overrides["style"] = style_phrase
        spec["overrides"] = overrides

    spec["extra"] = extra
    return spec


def compose_static_ad(bank, style_bank, image_bank, base_spec, product,
                       product_reference, mode="both", presenter_reference=None,
                       setting=None):
    """Product brief -> a list of shot dicts, one per mode requested.

    Each shot carries `references` - the ordered list generate_image.py's
    repeatable --reference should receive: the presenter first (only when
    that mode uses one and a presenter_reference was given), then the product
    photo always last - the same order ads.py already builds for its own
    presenter+product pairing.
    """
    wanted = list(modes(bank)) if mode == "both" else [mode]
    shots = []
    for key in wanted:
        cfg = modes(bank)[key]
        spec = _mode_spec(bank, style_bank, cfg, base_spec, product, setting=setting)
        spec["slug"] = "{}-{}".format(bp.slugify(base_spec.get("slug") or product or "ad"), key)
        prompt, layers = bp.compose(image_bank, spec)
        references = []
        if cfg.get("presenter") and presenter_reference:
            references.append(presenter_reference)
        references.append(product_reference)
        shots.append({
            "mode": key,
            "label": cfg["label"],
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
            "references": references,
        })
    return shots


def write_static_ad(base_spec, product, shots):
    """Write the whole batch to temp/outputs/prompts/: a readable .txt and a
    .json sibling static_ad_lint.py's CLI reads. Returns the .txt path."""
    slug = bp.slugify(base_spec.get("slug") or product or "ad")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = OUT_DIR / "static-ad-{}-{}.txt".format(slug, stamp)
    json_path = OUT_DIR / "static-ad-{}-{}.json".format(slug, stamp)

    blocks = []
    for shot in shots:
        blocks.append("=== {} ({})\nreferences: {}\n{}\n".format(
            shot["label"], shot["mode"], ", ".join(shot["references"]), shot["prompt"]))
    txt_path.write_text("\n".join(blocks), encoding="utf-8")
    json_path.write_text(json.dumps({"product": product, "shots": shots}, indent=2), encoding="utf-8")
    return txt_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a static (non-video) product ad: studio, lifestyle, or both.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a presenter character spec JSON (lifestyle mode only)")
    p.add_argument("--product", help="what is being sold, naming the exact label text")
    p.add_argument("--reference", dest="product_reference", help="path to the product photo")
    p.add_argument("--presenter-reference",
                    help="path to the presenter's reference image (lifestyle mode; locks identity)")
    p.add_argument("--mode", default="both", help="studio, lifestyle, or both (default)")
    p.add_argument("--setting",
                    help="lifestyle mode: where the product is shown (defaults to the "
                         "lesson's own kitchen example)")
    p.add_argument("--list", action="store_true", help="print every mode and exit")
    p.add_argument("--no-write", action="store_true", help="print only, do not write files")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompts")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for key, cfg in modes(bank).items():
            print("  {:<12} {}".format(key, cfg["label"]))
            print("               presenter: {}".format("yes" if cfg.get("presenter") else "no"))
        return 0

    error = validate_mode(bank, args.mode)
    if error:
        sys.exit(error)
    if not args.product:
        sys.exit("Give --product \"...\" (name it exactly, including the label text).")
    if not args.product_reference:
        sys.exit("Give --reference <path to the product photo>.")

    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        base_spec = json.loads(path.read_text(encoding="utf-8"))
    else:
        base_spec = {"seed": 0}
    if args.seed is not None:
        base_spec["seed"] = args.seed

    image_bank = bp.load_bank()
    style_bank = bstyle.load_bank()
    shots = compose_static_ad(
        bank, style_bank, image_bank, base_spec, args.product, args.product_reference,
        mode=args.mode, presenter_reference=args.presenter_reference, setting=args.setting)

    for shot in shots:
        print("=== {} ({})".format(shot["label"], shot["mode"]))
        print("references: {}".format(", ".join(shot["references"])))
        print(shot["prompt"])
        print()

    if not args.no_write:
        path = write_static_ad(base_spec, args.product, shots)
        print("[static-ad] {}".format(path), file=sys.stderr)
        print("[next]      python tools/static_ad_lint.py --static-ad {}".format(
            str(path).replace(".txt", ".json")), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
