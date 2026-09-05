"""Build a Kling-ready camera-movement prompt from a character spec.

Implements the two rules from the AI Video Bootcamp Kling toolkit:

  1. "Always start your prompt with the camera angle and build from there."
     -> compose() always emits the movement lead first. That is the inverse of
        an image prompt, which leads with core realism triggers.

  2. "Always create your images in a way that will complement the camera
     movement... Think ahead!"
     -> check_compatibility() reports what the still is missing for the move,
        and image_defaults() says how to frame it.

Usage:
    python tools/build_motion.py --list
    python tools/build_motion.py --movement orbit-360 --spec temp/resources/characters/x.json
    python tools/build_motion.py --movement dolly-in --subject "a tired mechanic" --no-write

Standard library only. No API keys, no network - you paste the result into Kling.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
BANK_PATH = TOOLS / "motion_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"

WATER = ("water", "sea", "ocean", "lake", "river", "pool", "underwater", "waves")
ATMOSPHERE = ("fog", "mist", "smoke", "haze", "dust", "steam", "cloud")
PORTAL = ("mirror", "window", "door", "portal", "gateway", "archway")
OBSTACLE = ("tree", "wall", "door", "pillar", "corner", "rock", "column", "curtain")
HEIGHT = ("sky", "cliff", "roof", "mountain", "tower", "aerial", "balcony",
          "hill", "above", "overlooking", "stairs", "ceiling")
FOREGROUND = ("crowd", "market", "people", "trees", "branches", "tents", "doorway",
              "foreground", "traffic", "passers")
BEHIND = ("behind", "away", "walking", "back to", "from the back", "turns away")
TIGHT_SHOTS = ("portrait", "selfie", "product-demo")


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _text(spec, *fields):
    """Lower-cased haystack from the named spec fields, extras included."""
    parts = []
    for field in fields:
        value = spec.get(field)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
    return " ".join(parts).lower()


def _any(haystack, needles):
    return any(needle in haystack for needle in needles)


# Detection lives here, not in the JSON: it is logic, not vocabulary.
DETECTORS = {
    "subject": lambda s: bool(str(s.get("subject", "")).strip()),
    "environment": lambda s: bool(str(s.get("setting", "")).strip()),
    "face": lambda s: s.get("shot") != "environmental",
    "space": lambda s: s.get("shot") not in TIGHT_SHOTS,
    "shoulder": lambda s: _any(_text(s, "action", "extra", "subject"), BEHIND),
    "water": lambda s: _any(_text(s, "setting", "action", "extra"), WATER),
    "atmosphere": lambda s: _any(_text(s, "setting", "action", "extra"), ATMOSPHERE),
    "portal": lambda s: _any(_text(s, "setting", "action", "extra"), PORTAL),
    "obstacle": lambda s: _any(_text(s, "setting", "action", "extra"), OBSTACLE),
    "height": lambda s: _any(_text(s, "setting", "action", "extra"), HEIGHT),
    "foreground": lambda s: _any(_text(s, "setting", "action", "extra"), FOREGROUND),
    "object": lambda s: bool(str(s.get("action", "")).strip()),
    "second_subject": lambda s: _any(
        _text(s, "subject", "action"), ("two ", "couple", "pair", "both", "together")
    ),
}


def validate_movement(bank, key):
    """Return an error message for an unknown movement, or None."""
    if key and key not in bank["movements"]:
        return "Unknown movement '{}'. Run --list to see all {}.".format(
            key, len(bank["movements"])
        )
    return None


def requirements_for(bank, key):
    return list(bank["movements"][key].get("requires", []))


def check_compatibility(bank, key, spec):
    """What the still is missing for this move - the 'think ahead' rule as code.

    Returns a list of {requirement, label, fix}. Empty means the pairing works.
    """
    warnings = []
    for name in requirements_for(bank, key):
        detector = DETECTORS.get(name)
        if detector is None or detector(spec):
            continue
        meta = bank["requirements"].get(name, {})
        warnings.append({
            "requirement": name,
            "label": meta.get("label", name),
            "fix": meta.get("fix", ""),
        })
    return warnings


def image_defaults(bank, key):
    """Shot and composition this movement wants the still to use."""
    return dict(bank["movements"][key].get("image_hints", {}))


def apply_image_hints(bank, key, spec):
    """Fill shot/composition from the movement where the spec is silent.

    Precedence copies build_prompt.apply_purpose(): the movement is a default
    provider, never an override. An explicit choice always wins.
    """
    hints = image_defaults(bank, key)
    merged = dict(spec)
    if hints.get("shot") and not merged.get("shot"):
        merged["shot"] = hints["shot"]
    if hints.get("composition"):
        overrides = dict(merged.get("overrides", {}))
        if "composition" not in overrides:
            overrides["composition"] = list(hints["composition"])
            merged["overrides"] = overrides
    return merged


def hint_conflicts(bank, key, spec):
    """Explicit spec choices that disagree with the movement. Inform, don't fix."""
    hints = image_defaults(bank, key)
    name = bank["movements"][key]["name"]
    notes = []
    wanted, actual = hints.get("shot"), spec.get("shot")
    if wanted and actual and actual != wanted:
        notes.append("{} works best with a '{}' shot; you have set '{}'".format(
            name, wanted, actual))
    return notes


def subject_clause(spec):
    parts = [str(spec.get("subject", "")).strip()]
    action = str(spec.get("action", "")).strip()
    if action:
        parts.append(action)
    # Comma-joined: "a woman with freckles, leaning against the counter" reads as
    # one subject, where a space-join runs the two clauses together.
    return ", ".join(p for p in parts if p)


DEFAULT_NEGATIVES = ["no warped face", "no floating limbs", "no distorted hands",
                    "no text artifacts", "no blurry edges", "no extra fingers"]
DEFAULT_STYLE_PRESETS = ["shot on a DSLR with an 85mm lens, natural color grading"]


def negative_tail(bank):
    """The standing "what to avoid" guard every Kling prompt carries.

    These are the specific artifact classes a video model actually fails on -
    warped faces, floating limbs, extra fingers - not a vague "high quality"
    plea. Bank-sourced so it is data, not code, the same way the image side's
    negatives live in prompt_bank.json rather than in realism_lint.py.
    """
    return ", ".join(bank.get("negatives") or DEFAULT_NEGATIVES)


def style_preset(bank, seed=0):
    """A concrete camera + colour-grade phrase, cycled by seed.

    "Cinematic lighting" and "professional" are exactly the vague style words
    that give a model nothing to work with - a named camera and a named grade
    do. Cycles rather than picks randomly, the same reproducible-by-seed
    pattern build_sound.accent_for() already uses for the same reason: two
    neighbouring scenes should not draw the same one by chance.
    """
    presets = bank.get("style_presets") or DEFAULT_STYLE_PRESETS
    return presets[int(seed) % len(presets)]


def compose(bank, key, spec, detail=None):
    """Spec + movement -> (prompt, parts). The camera lead is ALWAYS first."""
    movement = bank["movements"][key]
    requires = requirements_for(bank, key)
    setting = str(spec.get("setting", "")).strip()

    segments = [movement["lead"]]

    if "subject" in requires:
        clause = subject_clause(spec)
        if clause:
            segments[0] = movement["lead"] + " " + clause
        if setting:
            segments.append("in " + setting)
    elif setting:
        segments[0] = movement["lead"] + " " + setting

    segments.append(detail or movement.get("detail", ""))

    mood = str(spec.get("mood", "")).strip()
    if mood:
        segments.append(mood + " tone")

    extra = spec.get("extra") or []
    if extra:
        segments.append(", ".join(str(e) for e in extra))

    # A named camera and grade, not "cinematic lighting" - keyed off the
    # movement itself so the same movement always gets the same preset.
    segments.append(style_preset(bank, seed=sum(ord(c) for c in key)) + ", natural motion")
    segments.append(negative_tail(bank))

    prompt = ", ".join(s for s in segments if s)
    parts = {
        "lead": movement["lead"],
        "movement": key,
        "name": movement["name"],
        "category": movement["category"],
        "requires": requires,
    }
    return prompt, parts


def assemble_template(bank, shot_type, subject, action, camera_movement, style):
    """[SHOT TYPE] + [SUBJECT] + [ACTION] + [STYLE] + [CAMERA MOVEMENT] -> one
    prompt - the hands-on template, as an alternative to compose()'s own
    bank-driven assembly.

    Camera movement always opens the assembled text, whatever order the six
    fields are shown in on screen: motion_lint.leads_with_camera() is the
    Kling toolkit's own rule ("always start your prompt with the camera
    angle"), and it fails the moment anything else leads. Reuses
    subject_clause() for the subject+action join rather than duplicating it -
    the two are the same "who, doing what" pairing either way. Always closes
    with negative_tail(bank) - the same standing artifact guard compose()
    appends, so a hand-edited prompt is no less protected than an auto-composed
    one.
    """
    segments = [
        str(camera_movement or "").strip(),
        str(shot_type or "").strip(),
        subject_clause({"subject": subject, "action": action}),
        str(style or "").strip(),
        negative_tail(bank),
    ]
    return ", ".join(s for s in segments if s)


def write_prompt(spec, prompt, key):
    """Write to temp/outputs/prompts/ and return the path."""
    sys.path.insert(0, str(TOOLS))
    import build_prompt as bp

    slug = bp.slugify(spec.get("slug") or spec.get("subject", "shot"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "motion-{}-{}-{}.txt".format(key, slug, stamp)
    path.write_text(prompt + "\n", encoding="utf-8")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Build a Kling camera-movement prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--movement", help="movement key; see --list")
    p.add_argument("--spec", help="character spec JSON")
    p.add_argument("--subject", help="subject, when no --spec is given")
    p.add_argument("--setting", help="where it happens")
    p.add_argument("--action", help="what they are doing")
    p.add_argument("--detail", help="override the movement's motion detail")
    p.add_argument("--list", action="store_true", help="list every movement")
    p.add_argument("--no-write", action="store_true", help="print only")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    bank = load_bank()

    if args.list:
        for category in ("core", "niche", "combo"):
            rows = [(k, m) for k, m in bank["movements"].items()
                    if m["category"] == category]
            print("")
            print("{} ({})".format(category.upper(), len(rows)))
            for key, movement in rows:
                print("  {:24} {:42} needs: {}".format(
                    key, movement["name"],
                    ", ".join(movement.get("requires", [])) or "-"))
        return 0

    if not args.movement:
        sys.exit("Give --movement <key>, or --list to see them all.")
    error = validate_movement(bank, args.movement)
    if error:
        sys.exit(error)

    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        spec = json.loads(path.read_text(encoding="utf-8"))
    else:
        spec = {}
    for field in ("subject", "setting", "action"):
        value = getattr(args, field, None)
        if value:
            spec[field] = value
    if not spec.get("subject") and not spec.get("setting"):
        sys.exit("Give --spec, or at least --subject / --setting.")

    prompt, _ = compose(bank, args.movement, spec, args.detail)
    print(prompt)

    for note in hint_conflicts(bank, args.movement, spec):
        print("[note]    {}".format(note), file=sys.stderr)
    for warning in check_compatibility(bank, args.movement, spec):
        print("[missing] {} - {}".format(warning["label"], warning["fix"]), file=sys.stderr)

    if not args.no_write:
        out = write_prompt(spec, prompt, args.movement)
        print("[written] {}".format(out), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
