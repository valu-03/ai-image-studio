"""Build a layered, photorealistic image prompt from a character spec.

Implements the eight realism layers from the AI Video Bootcamp Phase 2 cheat-sheet
(lesson 20) using the vocabulary in tools/prompt_bank.json.

Usage:
    python tools/build_prompt.py --spec temp/resources/characters/<slug>.json
    python tools/build_prompt.py --spec <path> --detailed
    python tools/build_prompt.py --subject "a woman in her thirties" --shot selfie
    python tools/build_prompt.py --spec <path> --seed 3      # different word choices

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "prompt_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"

LAYER_ORDER = ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def pick(rng, terms, count, weights=None):
    """Pick `count` terms, preserving the bank's ordering for readability.

    With `weights` (term -> multiplier from history.py), selection is biased
    toward terms that have rated well, using Efraimidis-Spirakis weighted
    sampling without replacement. Unweighted, every term is equally likely.
    """
    count = min(count, len(terms))
    if not weights:
        chosen = rng.sample(range(len(terms)), count)
    else:
        keyed = []
        for index, term in enumerate(terms):
            weight = max(1e-6, float(weights.get(term, 1.0)))
            # random() ** (1/w): larger weight -> key nearer 1 -> picked first.
            keyed.append((rng.random() ** (1.0 / weight), index))
        keyed.sort(reverse=True)
        chosen = [index for _, index in keyed[:count]]
    return [terms[i] for i in sorted(chosen)]


def custom_shot(spec):
    """Free-text shot description, or "" — see apply_custom_shot()."""
    return str(spec.get("shot_custom") or "").strip()


def custom_guide(spec):
    """Free-text composition description, or "" — see apply_composition_guide()."""
    return str(spec.get("composition_guide_custom") or "").strip()


def select_layers(bank, spec, rng, weights=None):
    """Choose the vocabulary for each of the eight layers.

    Precedence: spec["overrides"] > shot preset > weighted pick from the bank.
    """
    layers = bank["layers"]
    # A custom shot suppresses the preset entirely: the two are alternatives,
    # and the typed one is the more explicit of them.
    preset = {} if custom_shot(spec) else bank["shot_presets"].get(spec.get("shot", ""), {})
    overrides = spec.get("overrides", {})
    selected = {}

    for name in LAYER_ORDER:
        if name in overrides:
            value = overrides[name]
            selected[name] = [value] if isinstance(value, str) else list(value)
            continue
        if name in preset:
            value = preset[name]
            selected[name] = [value] if isinstance(value, str) else list(value)
            continue
        cfg = layers[name]
        # `always` terms are appended only when we chose the layer ourselves —
        # an override or preset is taken as authoritative.
        selected[name] = (
            pick(rng, cfg["terms"], cfg.get("pick", 2), weights) + cfg.get("always", [])
        )

    selected["camera"] = apply_custom_shot(bank, spec, selected["camera"])
    selected["composition"] = apply_composition_guide(bank, spec, selected["composition"])
    return selected, preset


def guides(bank):
    """The composition guides table: key -> {label, phrase, note}."""
    return bank.get("composition_guides", {}).get("guides", {})


def apply_custom_shot(bank, spec, chosen):
    """Put a typed shot description in the camera slot, replacing the bank's.

    The pin-vs-replace rule this project already uses for lighting: camera is
    `pick: 1`, so an explicit value can simply take the slot without throwing
    anything away. (Composition is `pick: 2`, which is why a guide pins instead.)

    An explicit `overrides["camera"]` still wins — it is the lower-level, more
    deliberate control, and nothing should silently outrank it.
    """
    phrase = custom_shot(spec)
    if not phrase or "camera" in spec.get("overrides", {}):
        return chosen
    return [phrase]


def apply_composition_guide(bank, spec, chosen):
    """Pin the chosen framing geometry to the front of the composition layer.

    A guide is a *pin*, not a replacement. Lighting is `pick: 1`, so an explicit
    source can simply take the slot; composition is `pick: 2`, and replacing the
    whole layer would throw away half of it. So the guide takes the first slot,
    the terms already chosen fill the rest, and the layer keeps its normal
    length — which is what keeps the linter's composition check scoring.

    That last point is what makes free text safe here: whatever is typed, a bank
    term still occupies the remaining slot, so a custom composition can never
    cost the prompt its composition layer. A custom *shot* has no such
    protection, because replacing is the correct move for a `pick: 1` layer.

    It is applied last on purpose: it therefore outranks a shot preset and a
    movement's image hint, both of which are defaults, and matches the rule used
    everywhere else — an explicit choice wins.
    """
    # Typed text beats a picked guide: it is the more specific of the two, and
    # the editor only ever sends one of them anyway.
    named = guides(bank).get(spec.get("composition_guide", ""))
    phrase = custom_guide(spec) or (named["phrase"] if named else "")
    if not phrase:
        return chosen
    keep = bank["layers"]["composition"].get("pick", 2) - 1
    # Drop any term the guide already says, so "rule of thirds" cannot appear twice.
    rest = [t for t in chosen if t not in phrase and phrase not in t]
    return [phrase] + rest[:max(0, keep)]


# Prepended when a prompt must reproduce an existing face rather than invent
# one. This is the whole mechanism behind character consistency.
LOCK_COMPACT = (
    "the exact same person as in the reference image — identical face, bone structure, "
    "eye colour, hairline, skin tone and distinguishing marks"
)
LOCK_DETAILED = (
    "The subject is the exact same person as in the reference image: identical facial "
    "structure, eye colour, hairline, skin tone and distinguishing marks. Only the scene, "
    "wardrobe, pose and camera change — the face must not be restyled, idealised or "
    "made younger."
)
LOCK_TAIL = "identity locked to the reference image"


def apply_variation(spec):
    """Fold spec['variation'] over the base spec for a new shot of one character.

    The identity fields (subject, and anything the variation does not name)
    survive untouched — that is what keeps the character the same person.
    """
    variation = spec.get("variation")
    if not variation:
        return spec
    merged = dict(spec)
    merged.pop("variation", None)
    for key, value in variation.items():
        if value:
            merged[key] = value
    merged["lock_identity"] = True
    return merged


def subject_clause(spec):
    """The 'what am I actually looking at' part, assembled from the spec."""
    parts = [spec.get("subject", "a person")]
    if spec.get("wardrobe"):
        parts.append("wearing " + spec["wardrobe"])
    if spec.get("action"):
        parts.append(spec["action"])
    if spec.get("setting"):
        parts.append("in " + spec["setting"])
    if spec.get("mood"):
        parts.append(spec["mood"] + " expression")
    return ", ".join(parts)


def build_compact(bank, spec, selected, preset):
    segments = []
    head = ", ".join(selected["core"]) + " of "
    if spec.get("lock_identity"):
        head += LOCK_COMPACT + ", "
    segments.append(head + subject_clause(spec))
    for name in ["camera", "lens", "lighting", "texture", "colour", "composition", "grain"]:
        segments.append(", ".join(selected[name]))

    extra = list(preset.get("extra", [])) + list(spec.get("extra", []))
    if extra:
        segments.append(", ".join(extra))

    if spec.get("lock_identity"):
        segments.append(LOCK_TAIL)
    segments.append(", ".join(bank["negatives"]))
    return ", ".join(segments)


def build_detailed(bank, spec, selected, preset):
    core = ", ".join(selected["core"])
    sentences = [
        "{core} of {subject}.".format(core=core[0].upper() + core[1:], subject=subject_clause(spec)),
    ]
    if spec.get("lock_identity"):
        sentences.append(LOCK_DETAILED)
    sentences += [
        "Captured as if on {camera}, {lens}, producing authentic optical depth with natural "
        "lens falloff and gentle edge softness while the subject stays razor-sharp.".format(
            camera=", ".join(selected["camera"]), lens=", ".join(selected["lens"])
        ),
        "The scene is lit by {lighting}, with light wrap, bounce light and soft ambient "
        "occlusion giving the subject dimensional depth and grounded presence.".format(
            lighting=", ".join(selected["lighting"])
        ),
        "Surfaces carry real-world micro-texture including {texture} — nothing looks "
        "airbrushed or artificially clean.".format(texture=", ".join(selected["texture"])),
        "Color grading is {colour}, neutral and photographic with true whites and natural "
        "skin tones, avoiding oversaturation or artificial HDR.".format(
            colour=", ".join(selected["colour"])
        ),
        "The framing follows {composition}, giving clear separation between the subject and "
        "the environment.".format(composition=", ".join(selected["composition"])),
        "There is {grain} and subtle sensor noise in the shadows; highlights roll off "
        "smoothly with no clipping and blacks retain detail instead of crushing.".format(
            grain=", ".join(selected["grain"])
        ),
    ]

    extra = list(preset.get("extra", [])) + list(spec.get("extra", []))
    if extra:
        sentences.append("Additional direction: {}.".format(", ".join(extra)))

    sentences.append(
        "It should be visually indistinguishable from a real photograph: {}.".format(
            ", ".join(bank["negatives"])
        )
    )
    return " ".join(sentences)


def validate_shot(bank, shot):
    """Return an error message for an unknown shot preset, or None."""
    if shot and shot not in bank["shot_presets"]:
        return "Unknown shot '{}'. Available: {}".format(shot, ", ".join(bank["shot_presets"]))
    return None


def validate_purpose(bank, purpose):
    """Return an error message for an unknown purpose, or None."""
    if purpose and purpose not in bank.get("purposes", {}):
        return "Unknown purpose '{}'. Available: {}".format(
            purpose, ", ".join(bank.get("purposes", {}))
        )
    return None


def validate_guide(bank, guide):
    """Return an error message for an unknown composition guide, or None."""
    if guide and guide not in guides(bank):
        return "Unknown composition guide '{}'. Available: {}".format(
            guide, ", ".join(guides(bank))
        )
    return None


def apply_purpose(bank, spec):
    """Fill `shot` and `aspect` from the stated purpose where the spec is silent.

    Purpose is a *default provider*, never an override: an explicit choice always
    wins, otherwise picking a purpose would quietly discard a deliberate one.
    """
    purpose = bank.get("purposes", {}).get(spec.get("purpose", ""))
    if not purpose:
        return spec
    merged = dict(spec)
    for field in ("shot", "aspect"):
        # A typed shot is an explicit choice, so the purpose must not fill the
        # preset slot behind it — that preset would then supply camera, lens and
        # composition terms the user never asked for.
        if field == "shot" and custom_shot(merged):
            continue
        if not merged.get(field) and purpose.get(field):
            merged[field] = purpose[field]
    return merged


def purpose_conflicts(bank, spec):
    """Explicit choices that disagree with the stated purpose. Inform, don't fix."""
    purpose = bank.get("purposes", {}).get(spec.get("purpose", ""))
    if not purpose:
        return []
    label = purpose.get("label", spec.get("purpose"))
    notes = []
    if purpose.get("shot") and custom_shot(spec):
        notes.append("{} expects the {} shot; you have typed your own".format(
            label, purpose["shot"]))
    for field in ("shot", "aspect"):
        wanted, actual = purpose.get(field), spec.get(field)
        if wanted and actual and actual != wanted:
            notes.append(
                "{} expects {} {}; you have set {}".format(label, field, wanted, actual)
            )
    return notes


def compose(bank, spec, detailed=False, weights=None):
    """Spec -> (prompt text, chosen layer terms).

    The single entry point for anything that needs a prompt — the CLI below and
    gui.py both call this, so prompt logic lives in exactly one place.
    `weights` biases vocabulary toward terms that have rated well (history.py).
    """
    spec = apply_purpose(bank, spec)
    spec = apply_variation(spec)
    rng = random.Random(spec.get("seed", 0))
    selected, preset = select_layers(bank, spec, rng, weights)
    prompt = (
        build_detailed(bank, spec, selected, preset)
        if detailed
        else build_compact(bank, spec, selected, preset)
    )
    if spec.get("aspect"):
        joiner = " Aspect ratio {}." if detailed else ", aspect ratio {}"
        prompt += joiner.format(spec["aspect"])
    return prompt, selected


def write_prompt(spec, prompt):
    """Write a prompt to temp/outputs/prompts/ and return the path."""
    slug = slugify(spec.get("slug") or spec.get("subject", "avatar"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "avatar-{}-{}.txt".format(slug, stamp)
    out_path.write_text(prompt + "\n", encoding="utf-8")
    return out_path


def slugify(text):
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:40] or "untitled"


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a layered photorealistic prompt from a character spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON in temp/resources/characters/")
    p.add_argument("--subject", help="subject description (used when no --spec is given)")
    p.add_argument("--wardrobe", help="what they are wearing")
    p.add_argument("--setting", help="where they are")
    p.add_argument("--action", help="what they are doing")
    p.add_argument("--mood", help="expression / mood")
    p.add_argument(
        "--shot",
        help="shot preset: portrait, selfie, talking-head, product-demo, environmental",
    )
    p.add_argument(
        "--purpose",
        help="what the image is for: tiktok-ugc, instagram-post, youtube-thumbnail, "
             "website-hero, ad-creative, character-ref. Sets shot and aspect unless "
             "you set them yourself.",
    )
    p.add_argument(
        "--shot-custom", dest="shot_custom",
        help="your own shot description instead of a preset, e.g. \"close-up "
             "iPhone-style photo\". Takes the camera slot; suppresses the preset.",
    )
    p.add_argument(
        "--composition-guide", dest="composition_guide",
        help="optional framing geometry: rule-of-thirds, phi-grid, diagonals, triangle, "
             "golden-ratio, golden-spiral, harmonic-armature. Pins the first composition "
             "slot; the bank fills the rest.",
    )
    p.add_argument(
        "--composition-custom", dest="composition_guide_custom",
        help="your own framing instruction instead of a named guide, e.g. \"framed to "
             "include the sky and the water behind her\". Pinned the same way.",
    )
    p.add_argument(
        "--list-guides", action="store_true",
        help="print the composition guides and what each one does, then exit",
    )
    p.add_argument("--slug", help="output filename slug (defaults to the spec slug or subject)")
    p.add_argument("--detailed", action="store_true", help="emit the long paragraph form")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompt")
    p.add_argument("--no-write", action="store_true", help="print only, do not write a file")
    p.add_argument(
        "--variants", type=int, default=1,
        help="build N prompts from consecutive seeds, for side-by-side comparison",
    )
    p.add_argument(
        "--learned", action="store_true",
        help="bias vocabulary toward terms that rated well in temp/outputs/history.jsonl",
    )
    p.add_argument(
        "--lock-identity", action="store_true",
        help="prepend the reference-image identity lock (for consistent characters)",
    )
    p.add_argument("--log", action="store_true", help="record each prompt in history.jsonl")
    return p.parse_args(argv)


def spec_from_args(args):
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        with path.open(encoding="utf-8") as fh:
            spec = json.load(fh)
    else:
        if not args.subject:
            sys.exit("Give either --spec <path> or --subject \"...\". See --help.")
        spec = {}

    for field in ["subject", "wardrobe", "setting", "action", "mood", "shot", "slug",
                  "purpose", "composition_guide", "shot_custom",
                  "composition_guide_custom"]:
        value = getattr(args, field, None)
        if value:
            spec[field] = value
    if args.seed is not None:
        spec["seed"] = args.seed
    if args.lock_identity:
        spec["lock_identity"] = True
    return spec


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if getattr(args, "list_guides", False):
        for key, guide in guides(bank).items():
            print("{:<18} {}".format(key, guide["label"]))
            print("{:<18} {}".format("", guide["note"]))
        return 0

    spec = spec_from_args(args)

    for error in (validate_purpose(bank, spec.get("purpose")),
                  validate_shot(bank, spec.get("shot")),
                  validate_guide(bank, spec.get("composition_guide"))):
        if error:
            sys.exit(error)

    for note in purpose_conflicts(bank, spec):
        print("[note]    {}".format(note), file=sys.stderr)

    weights = None
    if args.learned:
        import history

        weights = history.weights()
        print(
            "[learned] biasing on {} rated term(s)".format(len(weights)), file=sys.stderr
        )

    # `.get("seed", 0)` still returns None when the spec file literally has
    # "seed": null (not merely omits it), and None + index is a TypeError.
    base_seed = spec.get("seed") or 0
    for index in range(max(1, args.variants)):
        variant = dict(spec, seed=base_seed + index)
        prompt, layers = compose(bank, variant, detailed=args.detailed, weights=weights)

        if args.variants > 1:
            print("\n=== seed {} ===".format(variant["seed"]))
        print(prompt)

        if args.log:
            import history
            import realism_lint

            present, _, banned, _, _ = realism_lint.lint(prompt.lower(), bank)
            entry_id = history.append(
                variant, prompt, layers, len(present),
                len(present) == 8 and not banned, args.detailed,
            )
            print("[logged]  {}".format(entry_id), file=sys.stderr)

        if not args.no_write:
            out_path = write_prompt(variant, prompt)
            print("[written] {}".format(out_path), file=sys.stderr)

    if not args.no_write and args.variants == 1:
        print("[next]    python tools/realism_lint.py <that file>", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
