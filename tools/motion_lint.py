"""Score a Kling video prompt against the rules from the bootcamp toolkit.

The video counterpart to realism_lint.py, and deliberately the same contract:
a score, named fixes, and exit code 1 on failure, so workflows and the GUI can
gate on either without special-casing.

The rules come from the Kling toolkit PDF, not from taste:

  1. Leads with a camera movement  - "always start your prompt with the camera
     angle... this way Kling recognizes it immediately"
  2. Names a subject or a scene    - "if there is no character in your scene...
     Kling will get confused"
  3. One dominant movement         - unless it is a declared combo; dolly-in
     plus dolly-out is the classic failure
  4. Describes motion              - a still prompt sent to a video model
  5. No contradictions             - underwater in a kitchen
  6. One action, not a chain       - "walking while talking while eating"
     confuses a video model the same way two competing movements do; a
     combo movement's own lead/detail text is exempt (see chains_actions)
  7. Negative guard present        - every prompt built through compose() or
     assemble_template() appends negative_tail(bank) unconditionally; this
     rule catches a prompt that lost that guard some other way (a hand edit,
     or a future path that forgets to call it) instead of assuming it never
     can. The image side has checked this since the beginning
     (realism_lint.negatives_present) - video never did, until now.
  8-10. Only when the prompt carries timed beats ("0-2s: ...; ENDS ON: ..."):
     the beats cover the clip with no gaps, each beat is one action, and an
     end state is stated - see beat_checks(). A prompt without beats is
     scored on rules 1-7 exactly as before.

Usage:
    python tools/motion_lint.py temp/outputs/prompts/motion-orbit-360-x.txt
    echo "a woman standing in a kitchen" | python tools/motion_lint.py -
    python tools/motion_lint.py <file> --movement orbit-360 --spec <spec.json>

Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import build_motion as bm

ROOT = Path(__file__).resolve().parent.parent

MOTION_VERBS = (
    "orbit", "dolly", "track", "pan", "tilt", "crane", "push", "pull", "zoom",
    "descend", "rise", "rising", "follow", "moves", "moving", "passes", "plummet",
    "spiral", "peek", "emerges", "falls", "circling", "sweeping", "widening",
    "retreat", "approach", "travel", "glide", "drift",
)

# Movement families that cannot coexist in one shot.
CONTRADICTIONS = [
    (("dolly in", "push in", "pushes in", "zoom in"),
     ("dolly out", "pull out", "pulls out", "zoom out", "pulling back"),
     "pushing in and pulling out at once"),
    (("underwater", "beneath the surface", "descends into the water"),
     ("desert", "kitchen", "office", "bedroom"),
     "underwater in a dry setting"),
    (("top-down", "bird's eye", "from above", "looking down"),
     ("low-angle", "looking up from below"),
     "shooting from above and below at once"),
    (("static camera", "camera holds still", "locked off"),
     ("tracking", "orbits", "dolly", "crane"),
     "a static camera that also moves"),
]


def leads_with_camera(text, bank):
    """Rule 1: does the prompt open with a known camera lead?

    Checked against the first ~90 characters, since the lead is by definition
    the opening clause.
    """
    head = text.lower().lstrip()[:90]
    for key, movement in bank["movements"].items():
        if head.startswith(movement["lead"].lower()):
            return key
    # A still camera named plainly - "Static shot, the cat..." - is a camera
    # lead too. The user's own 150k-view prompt opens exactly like that and
    # used to fail here (video_realism_bank.json `static_leads`).
    for lead in _static_leads(bank):
        if re.match(re.escape(lead) + r"(?!\w)", head):
            return "static"
    # Fall back to a looser check: an opening clause that names camera motion.
    opening = head.split(",")[0]
    if "camera" in opening and _any_word(opening, MOTION_VERBS):
        return "generic"
    return None


def _static_leads(bank):
    return (bank.get("realism") or {}).get("static_leads", [])


def subject_moves(text, bank):
    """Does the text say what the SUBJECT does - reach, grab, kick, slide...?

    Word starts, so "reach" covers "reaches" and "reaching", "slid" covers
    "sliding". Under a still camera this is the motion: the camera does
    nothing by design."""
    stems = (bank.get("realism") or {}).get("subject_motion_verbs", [])
    lower = text.lower()
    return any(re.search(r"\b" + re.escape(stem), lower) for stem in stems)


def _any_word(text, needles):
    return any(needle in text for needle in needles)


def count_movements(text, bank):
    """Which known leads appear anywhere - more than one is usually a mistake."""
    lower = text.lower()
    found = []
    for key, movement in bank["movements"].items():
        if movement["category"] == "combo":
            continue
        lead = movement["lead"].lower()
        # Use the distinctive tail of the lead, so "camera" alone never matches.
        distinctive = lead.replace("camera ", "").replace("cinematic ", "").strip()
        if len(distinctive) > 8 and distinctive in lower:
            found.append(key)
    return found


def contradictions(text):
    lower = text.lower()
    hits = []
    for group_a, group_b, label in CONTRADICTIONS:
        if _any_word(lower, group_a) and _any_word(lower, group_b):
            hits.append(label)
    return hits


# "Walking while talking while eating" confuses a video model as much as two
# competing camera movements do - one action at a time, same as one movement
# at a time. "and then"/"as well as" catch a chained second action; a bare
# "then" is too common in legitimate camera-timing phrases ("pushes in, then
# holds") to use as a marker without false-positiving on those.
CHAIN_MARKERS = (" while ", " and then ", " as well as ")


def chains_actions(text, bank=None, movement=None):
    """Rule 6: one SUBJECT action at a time - not one camera move at a time.

    A combo movement (the Kling toolkit's own "Crane Down + Orbit" category)
    legitimately describes one continuous camera technique with exactly this
    phrasing - "descending while circling" is not the chained subject action
    the rule exists to catch. Strip the movement's own lead/detail text before
    checking, so the camera clause is exempt and a genuinely chained subject
    action ("walking while talking while eating") still fails regardless of
    which movement carries it.
    """
    body = text.lower()
    if bank and movement:
        move = bank["movements"].get(movement, {})
        for phrase in (move.get("lead", ""), move.get("detail", "")):
            phrase = phrase.strip().lower()
            if phrase and phrase in body:
                body = body.replace(phrase, "", 1)
    return any(marker in body for marker in CHAIN_MARKERS)


def negatives_present(text, bank):
    """Rule 7: did the standing artifact guard actually reach the prompt?

    Unlike the image side's negatives_present() - which has to detect a "no
    X" pattern because a prompt could phrase it any number of ways - a Kling
    prompt's negative tail is always the bank's own literal, comma-joined
    phrase list (negative_tail() in build_motion.py). So this checks for the
    literal terms rather than a phrasing pattern; anything less exact would
    also accept a prompt that merely mentions "warped" in passing.
    """
    lower = text.lower()
    negatives = bank.get("negatives") or bm.DEFAULT_NEGATIVES
    missing = [n for n in negatives if n.lower() not in lower]
    return not missing, missing


def beat_checks(text, bank=None, movement=None, seconds=None):
    """Rules 8-10, only for a prompt that carries timed beats ("0-2s: ...").

    Conditional on purpose: a prompt with no beats is judged exactly as it
    always was, so every existing prompt keeps its 7/7. Once beats ARE
    present they are a promise about the whole clip, and three things have to
    hold for the model to have nothing left to improvise:

      8. The beats cover the clip - start at 0, no gaps, no overlaps, and end
         at the clip length when it is known. A gap is seconds the model
         fills on its own; that is the drift this exists to stop.
      9. One action per beat - chains_actions() per beat, the rule 6 test
         applied where it matters now.
     10. An end state - "ENDS ON: ..." names the final pose, so the last
         beat has somewhere to land instead of trailing off.
    """
    beats = bm.parse_beats(text)
    if not beats:
        return []
    checks = []

    problems = []
    if beats[0][0] != 0:
        problems.append("starts at {}s, not 0s".format(beats[0][0]))
    for (_s1, end1, _a1), (start2, _e2, _a2) in zip(beats, beats[1:]):
        if start2 > end1:
            problems.append("gap {}-{}s".format(end1, start2))
        elif start2 < end1:
            problems.append("overlap at {}s".format(start2))
    for start, end, _action in beats:
        if end <= start:
            problems.append("{}-{}s runs backwards".format(start, end))
    if seconds and beats[-1][1] != int(seconds):
        problems.append("ends at {}s, the clip is {}s".format(beats[-1][1], int(seconds)))
    checks.append((
        "Beats cover the clip",
        not problems,
        "{} beats, 0-{}s".format(len(beats), beats[-1][1]) if not problems
        else "; ".join(problems),
    ))

    chained = [start for start, _end, action in beats
               if chains_actions(" " + action + " ", bank, movement)]
    checks.append((
        "One action per beat",
        not chained,
        "each beat is one action" if not chained
        else "the beat at {}s chains actions - split it".format(
            ", ".join("{}s".format(s) for s in chained)),
    ))

    ends = bm.has_end_state(text)
    checks.append((
        "States where it ends",
        ends,
        "end state given" if ends
        else 'add "ENDS ON: <the final pose>" so the clip does not drift',
    ))
    return checks


def lint(text, bank, movement=None, spec=None, seconds=None, negatives=True):
    """Return (checks, warnings). checks is a list of (name, ok, detail).

    `negatives=False` makes the negative guard optional: the user chose to
    leave it out (their viral prompt had none), so its row passes and says so.

    `seconds` is the clip length, when known; it only matters to a prompt
    with timed beats (see beat_checks()).
    """
    lower = text.lower()
    checks = []

    lead = leads_with_camera(text, bank)
    checks.append((
        "Leads with a camera movement",
        bool(lead),
        'opens with "{}"'.format(text.strip()[:38]) if lead
        else "start with the camera move, e.g. \"camera slowly orbits around...\"",
    ))

    has_subject = bool(re.search(r"\b(a|an|the)\s+\w+", lower)) and len(lower.split()) > 6
    checks.append((
        "Names a subject or scene",
        has_subject,
        "subject described" if has_subject else "say who or what is in the shot",
    ))

    found = count_movements(text, bank)
    is_combo = bool(movement) and bank["movements"].get(movement, {}).get("category") == "combo"
    single = len(found) <= 1 or is_combo
    checks.append((
        "One dominant movement",
        single,
        "combo movement" if is_combo and len(found) > 1
        else ("single move" if single
              else "two moves compete: {}".format(", ".join(found[:3]))),
    ))

    moves = _any_word(lower, MOTION_VERBS)
    # A still camera does nothing by design - there, the subject's own
    # movement is the motion the prompt has to describe.
    still = lead == "static" or (lead in (bank.get("realism") or {}).get("static_movements", []))
    if not moves and still and subject_moves(text, bank):
        moves = True
    checks.append((
        "Describes motion",
        moves,
        "motion described" if moves
        else ("say what the subject does" if still else "add what the camera actually does"),
    ))

    clashes = contradictions(text)
    checks.append((
        "No contradictions",
        not clashes,
        "consistent" if not clashes else "; ".join(clashes),
    ))

    chained = chains_actions(text, bank, movement)
    checks.append((
        "One action, not a chain",
        not chained,
        "single action" if not chained
        else "split this into separate shots - one action per prompt",
    ))

    guarded, missing_negatives = negatives_present(text, bank)
    checks.append((
        "Negative guard present",
        guarded or not negatives,
        "artifact guard present" if guarded
        else ("optional - left out by choice" if not negatives
              else "append: " + ", ".join(missing_negatives)),
    ))

    checks.extend(beat_checks(text, bank, movement, seconds))

    warnings = []
    if movement and spec is not None:
        for item in bm.check_compatibility(bank, movement, spec):
            warnings.append("the still needs {} - {}".format(item["label"], item["fix"]))

    return checks, warnings


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a Kling video prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("prompt_file", help="path to a prompt .txt, or - for stdin")
    p.add_argument("--movement", help="movement key, to also check the still")
    p.add_argument("--spec", help="character spec JSON, to also check the still")
    p.add_argument("--seconds", type=int, help="clip length, to check timed beats cover it")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if args.prompt_file == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.prompt_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        text = path.read_text(encoding="utf-8")

    if not text.strip():
        sys.exit("Empty prompt.")

    bank = bm.load_bank()
    spec = None
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            spec = json.loads(path.read_text(encoding="utf-8"))

    if args.movement and bm.validate_movement(bank, args.movement):
        sys.exit(bm.validate_movement(bank, args.movement))

    checks, warnings = lint(text, bank, args.movement, spec, args.seconds)
    score = sum(1 for _, ok, _ in checks if ok)

    print("Motion score: {}/{}".format(score, len(checks)))
    for name, ok, detail in checks:
        print("  [{}] {:<30} {}".format("ok " if ok else "!! ", name, detail))

    if warnings:
        print("")
        print("The still does not support this move:")
        for warning in warnings:
            print("  [img] {}".format(warning))

    ok = score == len(checks)
    print("")
    print("PASS - ready for Kling." if ok else "FAIL - fix the items above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
