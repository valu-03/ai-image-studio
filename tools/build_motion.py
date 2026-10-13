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
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
BANK_PATH = TOOLS / "motion_bank.json"
# Kept apart from motion_bank.json (hash-pinned by test_story.py): the
# locked-off movement, real-motion lines and the phone look, measured from a
# viral one-take cat clip. load_bank() merges its movements in.
REALISM_PATH = TOOLS / "video_realism_bank.json"
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
    """motion_bank.json, plus video_realism_bank.json's movements (the
    locked-off camera) and that bank itself under "realism"."""
    with BANK_PATH.open(encoding="utf-8") as fh:
        bank = json.load(fh)
    realism = load_realism()
    bank["movements"].update(realism.get("movements", {}))
    bank["realism"] = realism
    return bank


def load_realism():
    with REALISM_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _subject_kind(subject):
    """'human', 'animal', 'object' or 'place' - build_evidence's reading."""
    sys.path.insert(0, str(TOOLS))
    import build_evidence as bev
    return bev.subject_kind(bev.load_bank(), subject)


def real_motion_line(bank, subject, movement=None):
    """How things really move, for this subject and camera - or "".

    Planted weight, follow-through, real-time speed with a ramp, and a
    background that holds: what a measured viral one-take clip has and a
    generated clip usually lacks (video_realism_bank.json `source`). A place
    has no body to plant, so it gets only the tempo and background lines.
    A still camera says the background does not move at all; a moving one
    says it stays solid as the camera passes.
    """
    cfg = (bank.get("realism") or load_realism()).get("real_motion")
    if not cfg:
        return ""
    kind = _subject_kind(subject)
    still = movement in (bank.get("realism") or {}).get("static_movements", [])
    parts = [cfg["planted"].get(kind, ""), cfg["follow_through"].get(kind, ""), cfg["tempo"],
             cfg["background_still"] if still else cfg["background_moving"]]
    return ", ".join(p for p in parts if p)


def phone_style(bank):
    """The ordinary-phone style line that replaces the cinema-camera presets."""
    return (bank.get("realism") or load_realism()).get("phone_style", "")


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
DEFAULT_AVATAR_GUARD = ["no identity drift between cuts", "no plastic skin, no beauty filter",
                        "no overacting, exaggerated expressions or repetitive gestures",
                        "no frozen avatar pauses",
                        "no gimbal-smooth or dolly-smooth camera moves - keep it handheld",
                        "no generated captions, UI or subtitles"]


def negative_tail(bank):
    """The standing "what to avoid" guard every Kling prompt carries.

    These are the specific artifact classes a video model actually fails on -
    warped faces, floating limbs, extra fingers - not a vague "high quality"
    plea. Bank-sourced so it is data, not code, the same way the image side's
    negatives live in prompt_bank.json rather than in realism_lint.py.
    """
    return ", ".join(bank.get("negatives") or DEFAULT_NEGATIVES)


def avatar_guard_tail(bank):
    """An OPT-IN extra guard, on top of negative_tail(), for a clip that puts
    an avatar through multiple cuts (e.g. Kling's own Auto multi-shot) or
    carries dialogue - failure modes negative_tail()'s per-frame artifact list
    does not cover: the character looking like someone else after a cut, or a
    performance that reads as staged rather than natural. Community-sourced
    (Seedance avatar-ad prompt craft, see motion_bank.json's own `source`
    field) - never appended unless asked for, unlike negative_tail()."""
    return ", ".join(bank.get("avatar_guard") or DEFAULT_AVATAR_GUARD)


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


def compose(bank, key, spec, detail=None, avatar_guard=False, real_motion=False, phone=False):
    """Spec + movement -> (prompt, parts). The camera lead is ALWAYS first.

    `real_motion=True` adds real_motion_line() before the style; `phone=True`
    swaps the cinema-camera style preset for phone_style(). Both off by
    default, so existing callers get the prompt they always got.

    `avatar_guard=True` appends avatar_guard_tail(bank) as one more segment,
    on top of the standing negative_tail(bank) - opt-in, off by default, for
    an avatar clip going through multiple cuts (e.g. Auto multi-shot) or
    carrying dialogue. See avatar_guard_tail()'s own docstring for why.
    """
    movement = bank["movements"][key]
    requires = requirements_for(bank, key)
    setting = str(spec.get("setting", "")).strip()

    segments = [movement["lead"]]

    clause = subject_clause(spec)
    if "subject" in requires:
        if clause:
            segments[0] = movement["lead"] + " " + clause
        if setting:
            segments.append("in " + setting)
    elif setting:
        segments[0] = movement["lead"] + " " + setting
        # A move that frames the place still has to say who is in it - this
        # used to drop the Subject and Action entirely ("wide static camera
        # watching a back alley", and no cats).
        if clause:
            segments.append(clause)
    elif clause:
        segments[0] = movement["lead"] + " " + clause

    segments.append(detail or movement.get("detail", ""))

    mood = str(spec.get("mood", "")).strip()
    if mood:
        segments.append(mood + " tone")

    extra = spec.get("extra") or []
    if extra:
        segments.append(", ".join(str(e) for e in extra))

    if real_motion:
        segments.append(real_motion_line(bank, spec.get("subject", ""), key))
    # A named camera and grade, not "cinematic lighting" - keyed off the
    # movement itself so the same movement always gets the same preset.
    style = phone_style(bank) if phone else style_preset(bank, seed=sum(ord(c) for c in key))
    segments.append(style + ", natural motion")
    segments.append(negative_tail(bank))
    if avatar_guard:
        segments.append(avatar_guard_tail(bank))

    prompt = ", ".join(s for s in segments if s)
    parts = {
        "lead": movement["lead"],
        "movement": key,
        "name": movement["name"],
        "category": movement["category"],
        "requires": requires,
    }
    return prompt, parts


# --------------------------------------------------------------------------- #
# Timed beats and an end state
# --------------------------------------------------------------------------- #
# What separates "the clip I imagined" from "the clip that came back" is almost
# never appearance - the first frame already fixes that - it is TIMING and
# ENDPOINT. One untimed action lets the model choose the pace: it finishes
# early, then invents motion to fill the remaining seconds. A time-coded beat
# line plus a stated final pose leaves it nothing to improvise. Each beat is
# still ONE action (motion_lint checks that per beat), so the one-action rule
# holds - the beats happen in sequence, not at once.
BEAT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*s\s*:\s*")
END_RE = re.compile(r"ends on\s*:\s*", re.IGNORECASE)
# Splits a single Action field into the actions it already chains in order.
# " then " is a sequence, which is exactly what a beat line is - so here it is
# the separator, never the chain marker motion_lint warns about.
SEQUENCE_SPLIT = re.compile(r"\s*(?:;|,?\s+and then\s+|,?\s+then\s+|,?\s+before\s+|,?\s+after that\s+)\s*",
                            re.IGNORECASE)
DEFAULT_HOLD = "settles and holds the final position"
MAX_DRAFT_BEATS = 3


def _num(value):
    value = float(value)
    return int(value) if value.is_integer() else value


def format_beats(beats):
    """[(start, end, action), ...] -> "0-2s: a; 2-4s: b"."""
    return "; ".join("{}-{}s: {}".format(_num(start), _num(end), str(action).strip())
                     for start, end, action in beats if str(action).strip())


def parse_beats(text):
    """Every "0-2s: action" beat in `text`, in order, as (start, end, action).

    Shared by the Videos tab (reading the Timing box) and motion_lint (reading
    a finished prompt), so the two can never disagree about what a beat is. A
    beat's action runs to the next beat, an "ENDS ON:" marker, or the end of
    the text, trimmed of separators.
    """
    text = str(text or "")
    matches = list(BEAT_RE.finditer(text))
    beats = []
    for i, match in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():stop]
        end = END_RE.search(body)
        if end:
            body = body[:end.start()]
        beats.append((_num(match.group(1)), _num(match.group(2)), body.strip(" ;,.\n\t")))
    return beats


def has_end_state(text):
    """Does `text` state an end state - an "ENDS ON:" marker with words after it?
    Presence only: inside a finished prompt the end state runs straight into
    the style segment with nothing to mark where it stops, so its exact
    extent is not recoverable and nothing here pretends otherwise."""
    match = END_RE.search(str(text or ""))
    return bool(match) and bool(re.search(r"\w", text[match.end():match.end() + 40]))


def split_timing_text(text):
    """One free-text field -> (beats, end_state).

    For the compact single-line form Cats' scene cards use:
    "0-3s: stalks the toy; 3-5s: pounces ENDS ON: sitting proudly beside it".
    Everything after "ENDS ON:" is the end state; beats are read from the rest.
    """
    text = str(text or "")
    match = END_RE.search(text)
    end_state = text[match.end():].strip(" ;,.\n") if match else ""
    return parse_beats(text[:match.start()] if match else text), end_state


def split_beats(action, seconds):
    """Draft a 2-3 beat timeline from one Action field and a clip length.

    A first draft for the user to edit, not a decision: clauses the action
    already sequences ("lifts the cup, then glances up") become beats, the
    whole seconds are shared out with the last beat absorbing the remainder,
    and a single action gets a closing hold beat - the hold is what stops the
    model inventing new motion once the action is done.
    """
    seconds = max(1, int(seconds))
    clauses = [c.strip(" ,.") for c in SEQUENCE_SPLIT.split(str(action or "")) if c.strip(" ,.")]
    if not clauses:
        return []
    # About two seconds per beat is the shortest a beat can be and still read;
    # past that, the overflow joins the last beat rather than being dropped.
    limit = max(MAX_DRAFT_BEATS, min(5, seconds // 2))
    if len(clauses) > limit:
        clauses = clauses[:limit - 1] + [", then ".join(clauses[limit - 1:])]
    if len(clauses) == 1 and seconds >= 3:
        clauses.append(DEFAULT_HOLD)
    count = min(len(clauses), seconds)
    clauses = clauses[:count]
    # The action gets the bulk; a closing hold only needs about a second or two.
    if clauses[-1] == DEFAULT_HOLD:
        hold = max(1, seconds // 4)
        cuts = [0, seconds - hold, seconds]
    else:
        step = seconds / count
        cuts = [0] + [int(round(step * i)) for i in range(1, count)] + [seconds]
    return [(cuts[i], cuts[i + 1], clauses[i]) for i in range(count)]


def default_end_state(action=""):
    return "the motion settled, holding still in the final position"


def assemble_template(bank, shot_type, subject, action, camera_movement, style,
                      avatar_guard=False, beats=None, end_state="", real_motion="",
                      negatives=True):
    """[SHOT TYPE] + [SUBJECT] + [ACTION] + [STYLE] + [CAMERA MOVEMENT] -> one
    prompt - the hands-on template, as an alternative to compose()'s own
    bank-driven assembly.

    `beats` ([(start, end, action), ...]) and `end_state` are optional and
    land after the subject, before the style - "what happens when, and where
    it stops". The camera still leads, so motion_lint rule 1 holds. Callers
    that pass neither get byte-for-byte the prompt they always got.
    `real_motion` (a real_motion_line()) lands after them, before the style.
    `negatives=False` leaves negative_tail() out - optional, like the
    user's own viral prompt, which had none.

    Camera movement always opens the assembled text, whatever order the six
    fields are shown in on screen: motion_lint.leads_with_camera() is the
    Kling toolkit's own rule ("always start your prompt with the camera
    angle"), and it fails the moment anything else leads. Reuses
    subject_clause() for the subject+action join rather than duplicating it -
    the two are the same "who, doing what" pairing either way. Always closes
    with negative_tail(bank) - the same standing artifact guard compose()
    appends, so a hand-edited prompt is no less protected than an auto-composed
    one. `avatar_guard=True` appends avatar_guard_tail(bank) too - opt-in, off
    by default, same as compose()'s own `avatar_guard` param.
    """
    timing = format_beats(beats or [])
    end_state = str(end_state or "").strip().rstrip(".")
    segments = [
        str(camera_movement or "").strip(),
        str(shot_type or "").strip(),
        # With beats, the beats ARE the action - saying it once untimed in
        # front of them invites the model to do it twice.
        subject_clause({"subject": subject, "action": "" if timing else action}),
        timing,
        "ENDS ON: " + end_state if end_state else "",
        str(real_motion or "").strip(),
        str(style or "").strip(),
        negative_tail(bank) if negatives else "",
    ]
    if avatar_guard:
        segments.append(avatar_guard_tail(bank))
    return ", ".join(s for s in segments if s)


# --------------------------------------------------------------------------- #
# The one-take story
# --------------------------------------------------------------------------- #
# Written the way the user's own 150k-view prompt is: a short camera opening,
# then the beats as plain sentences in order with time words ("initially...
# Suddenly... soon after..."), closing on "Subtle, fluid motion." No comma
# list, no "0-3s:" codes, no negatives unless asked for. The tagged template
# above stays for anyone who prefers it.


def story_beats(text, action=""):
    """The beats as plain actions, in order.

    Timing lines may be "0-3s: ..." beats (seconds dropped) or plain lines,
    one per beat. With neither, the Action is the one beat."""
    timed = parse_beats(text)
    if timed:
        return [a for _s, _e, a in timed if a]
    lines = [ln.strip(" -*\t") for ln in str(text or "").splitlines()]
    lines = [ln for ln in lines if ln and not END_RE.match(ln)]
    if lines:
        return lines
    action = str(action or "").strip()
    return [action] if action else []


def _sentence(text):
    text = str(text or "").strip().rstrip(".,;")
    return text[:1].upper() + text[1:] + "." if text else ""


def _starts_with_time_word(text, words):
    lower = text.lower()
    return any(re.match(r"{}\b".format(re.escape(w)), lower) for w in words)


def story_lead(bank, movement_key):
    """The short opening for a movement: "Static shot" for a still camera,
    else the movement's own lead."""
    story = (bank.get("realism") or {}).get("story", {})
    lead = story.get("leads", {}).get(movement_key)
    if lead:
        return lead
    movement = bank["movements"].get(movement_key, {})
    return movement.get("lead", "")


def assemble_story(bank, movement_key, subject, beats, end_state="", style="",
                   close=True, negatives=False, avatar_guard=False, real_motion="",
                   opening=None):
    """One-take story prompt: opening, beats as ordered sentences, close.

    The first beat gets "Initially", the middle ones alternate "Then" /
    "Soon after", the last gets "Finally" - unless a beat already opens with
    a time word ("Suddenly, a hand enters..."), which is kept as typed. A
    single beat gets no time word at all.
    """
    story = (bank.get("realism") or {}).get("story", {})
    words = story.get("time_words", [])
    middle = story.get("middle", ["Then"])
    beats = [str(b).strip().rstrip(".") for b in beats if str(b).strip()]

    opening = str(opening).strip() if opening else story_lead(bank, movement_key)
    subject = str(subject or "").strip().rstrip(".")
    sentences = [_sentence(", ".join(x for x in (opening, subject) if x))]
    for i, beat in enumerate(beats):
        if len(beats) == 1 or _starts_with_time_word(beat, words):
            sentences.append(_sentence(beat))
            continue
        if i == 0:
            word = story.get("first", "Initially")
        elif i == len(beats) - 1:
            word = story.get("last", "Finally")
        else:
            word = middle[(i - 1) % len(middle)]
        sentences.append(_sentence("{}, {}".format(word, beat)))
    end_state = str(end_state or "").strip().rstrip(".")
    if end_state:
        sentences.append(_sentence("It ends on " + end_state))
    for extra in (real_motion, style):
        sentences.append(_sentence(extra))
    if close and story.get("close"):
        sentences.append(_sentence(story["close"]))
    if negatives:
        sentences.append(_sentence(negative_tail(bank)))
    if avatar_guard:
        sentences.append(_sentence(avatar_guard_tail(bank)))
    return " ".join(x for x in sentences if x)


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
    p.add_argument("--avatar-guard", action="store_true",
                   help="append the opt-in avatar/multi-cut guard (identity drift, "
                        "overacting, frozen pauses, ...) - see avatar_guard_tail()")
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

    prompt, _ = compose(bank, args.movement, spec, args.detail, avatar_guard=args.avatar_guard)
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
