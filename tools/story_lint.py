"""Score a cat story before a single clip is generated.

Usage:
    python tools/story_lint.py --story temp/outputs/stories/x.json
    python tools/story_lint.py --story x.json --arc classic --seconds 30

Exit code 0 when the story passes every check; 1 otherwise - the same contract
as realism_lint.py, motion_lint.py, ad_lint.py and sound_lint.py.

Three of these checks exist because the mistake they catch is invisible until
you have already paid for the clips:

**A clip is 3 to 15 whole seconds.** A plan asking for 20 cannot be generated at
all, and you find out at the provider. This check used to accept any MULTIPLE of
a legal length, on the theory that a long scene was "two clips" - but nothing
downstream ever split one, so a 15-second scene was one image, one motion prompt
and one impossible request. Membership in the range, nothing cleverer.

**The hook is 3 seconds.** That is the window, not a proportion of the video, so
it is capped no matter how long the story runs.

**Style is per story, not per scene.** A photoreal cut next to a stylised one
looks like a mistake rather than a choice, and the two are judged by different
gates - so a mixed story is not even scoreable.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import build_story as bs  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _scene_keys(scenes):
    return [s.get("beat", s.get("key", "")) for s in scenes]


def check_arc(bank, scenes, arc, seconds=None, clip_length=None, fmt=None):
    """The beats the chosen arc asks for, in the order it asks for them.

    Compared against the EXPANDED sequence, not the arc's literal beat list: a
    repeatable beat is repeated to fill the runtime, so a 30-second classic is
    seven scenes rather than five and both are correct.
    """
    expected = list(bs.beat_sequence(bank, arc, seconds, clip_length, fmt))
    actual = _scene_keys(scenes)
    if actual == expected:
        return True, "{} scenes, in order".format(len(actual))
    shape = [k for k in bs.arcs(bank, fmt).get(arc, {}).get("beats", [])]
    missing = [k for k in shape if k not in actual]
    if missing:
        return False, "missing: {}".format(", ".join(sorted(set(missing))))
    return False, "out of order: {}".format(" -> ".join(actual))


def check_clip_lengths(bank, scenes):
    """You cannot generate a 20-second clip."""
    low, high = bs.clip_range(bank)
    bad = []
    for scene in scenes:
        clip = scene.get("clip_seconds", 0)
        if not clip or clip != int(clip) or not (low <= clip <= high):
            bad.append("scene {} asks for {}s".format(scene.get("n"), clip))
    if bad:
        return False, "{}. Kling makes whole clips of {} to {} seconds.".format(
            "; ".join(bad), low, high)
    return True, "every clip is {}-{}s, which is a real length".format(low, high)


def check_trims(bank, scenes):
    """A scene cannot keep more than the clip it came from."""
    bad = [
        "scene {} keeps {:.1f}s of a {}s clip".format(
            s.get("n"), s.get("edit_seconds", 0), s.get("clip_seconds", 0))
        for s in scenes
        if s.get("edit_seconds", 0) > s.get("clip_seconds", 0) + 1e-6
    ]
    if bad:
        return False, "; ".join(bad)
    return True, "every trim fits its clip"


def check_runtime(bank, scenes, seconds):
    """The trims have to add up to the video you said you were making."""
    total = round(sum(s.get("edit_seconds", 0) for s in scenes), 2)
    target = float(seconds or bank.get("default_seconds", 30))
    if abs(total - target) <= 0.5:
        return True, "{:.1f}s of a {:.0f}s target".format(total, target)
    short = target - total
    return False, ("the trims add up to {:.1f}s, not {:.0f}s - {} {:.1f}s".format(
        total, target, "short by" if short > 0 else "over by", abs(short)))


def check_hook(bank, scenes):
    """The window is 3 seconds however long the clip is."""
    cap = float(bank.get("hook_seconds", 3.0))
    if not scenes:
        return False, "no scenes"
    first = scenes[0]
    kept = first.get("edit_seconds", 0)
    if kept > cap + 0.05:
        return False, ("the opening runs {:.1f}s; trim it to {:.0f}s. The clip can "
                       "be 5s - just do not keep all of it.".format(kept, cap))
    if not (first.get("caption") or first.get("narration")):
        return False, "the opening has no words - this is the shot that keeps people"
    return True, "opens in {:.1f}s".format(kept)


def check_identity(bank, scenes):
    """The same animal in every scene, not a new one per shot.

    For `trade` the subject is a PAIR, and one reference image carries both -
    so this check is unchanged and still means what it says.
    """
    if len(scenes) < 2:
        return True, "single scene"
    unlocked = [s.get("n") for s in scenes[1:] if not s.get("spec", {}).get("lock_identity")]
    if unlocked:
        return False, ("scene(s) {} are not locked to scene 1, so they will be "
                       "different cats".format(", ".join(str(n) for n in unlocked)))
    return True, "every scene locked to scene 1"


def check_moves_vary(bank, scenes):
    """Two identical moves in a row read as one long drift, not two shots."""
    repeats = []
    for earlier, later in zip(scenes, scenes[1:]):
        move = earlier.get("movement")
        if move and move == later.get("movement"):
            repeats.append("scenes {} and {} both {}".format(
                earlier.get("n"), later.get("n"), move))
    if repeats:
        return False, "; ".join(repeats) + " - vary the camera or the cut disappears"
    return True, "no move repeats back to back"


def check_actions_vary(bank, scenes):
    """Different scenes have to show different things happening.

    The brief tells the model every scene's action must differ; without this
    check that instruction was unenforced, and a story of five identical actions
    scored full marks. A story where the cat does the same thing five times is
    one shot repeated, which is exactly where people scroll.
    """
    actions = [(s.get("n"), (s.get("spec", {}).get("action") or "").strip().lower())
               for s in scenes]
    described = [(n, a) for n, a in actions if a]
    if len(described) < 2:
        return True, "too few actions to compare"
    if len(described) < len(actions):
        blank = [str(n) for n, a in actions if not a]
        return False, "scene(s) {} say nothing about what happens".format(", ".join(blank))

    seen = {}
    repeats = []
    for n, action in described:
        if action in seen:
            repeats.append("scenes {} and {}".format(seen[action], n))
        else:
            seen[action] = n
    if repeats:
        return False, ("{} show the same action - that is one shot repeated, "
                       "not a story".format("; ".join(repeats)))
    return True, "{} distinct actions".format(len(seen))


def check_shot_repeats(bank, scenes):
    """A repeated beat (escalation, most often) should not frame the same
    shot every time it recurs. Only compares scenes sharing the SAME beat
    key - two DIFFERENT beats sharing a shot category (setup and escalation
    are both "environmental" by design) is not this check's business, only
    a beat repeating against itself with no visual change is.

    Only checked when the beat actually defines more than one `shots` option
    to rotate through (shot_for() in build_story.py). A beat with a single
    fixed shot - payoff's pull-out movements need the same wide frame every
    time, so it has none - has nothing it could have varied, and flagging it
    anyway would punish a beat for a movement choice that requires the
    repetition, not for forgetting to vary it.
    """
    beats = bank.get("beats", {})
    repeats = []
    for earlier, later in zip(scenes, scenes[1:]):
        beat_key = earlier.get("beat")
        if not beat_key or beat_key != later.get("beat"):
            continue
        if len(beats.get(beat_key, {}).get("shots") or []) < 2:
            continue
        shot = (earlier.get("spec") or {}).get("shot")
        if shot and shot == (later.get("spec") or {}).get("shot"):
            repeats.append("scenes {} and {} ({}) both frame a {} shot".format(
                earlier.get("n"), later.get("n"), beat_key, shot))
    if repeats:
        return False, "; ".join(repeats) + " - vary the frame or the repeat reads as padding"
    return True, "every repeated beat varies its shot"


def check_moves_fit(bank, scenes):
    """Reuses build_motion's own 'think ahead' rule rather than restating it."""
    labels = bank.get("requirement_labels", {})
    trouble = []
    for scene in scenes:
        for warning in scene.get("warnings", []) or []:
            label = labels.get(warning["requirement"], warning["label"])
            trouble.append("scene {} needs {}".format(scene.get("n"), label))
    if trouble:
        return False, "; ".join(trouble[:3]) + ("" if len(trouble) <= 3 else
                                                " (+{} more)".format(len(trouble) - 3))
    return True, "every move suits its still"


def check_words(bank, scenes):
    """The confirmed format: a narration line and a caption per scene."""
    missing = []
    for scene in scenes:
        gaps = [name for name in ("narration", "caption") if not (scene.get(name) or "").strip()]
        if gaps:
            missing.append("scene {} has no {}".format(scene.get("n"), " or ".join(gaps)))
    if missing:
        return False, "; ".join(missing[:3]) + ("" if len(missing) <= 3 else
                                                " (+{} more)".format(len(missing) - 3))
    return True, "narration and caption on every scene"


def check_one_style(bank, scenes):
    used = {s.get("style") for s in scenes if s.get("style")}
    if len(used) <= 1:
        return True, "{} throughout".format(next(iter(used), "unset"))
    return False, "mixed styles: {} - pick one".format(", ".join(sorted(used)))


def style_of(scenes):
    for scene in scenes:
        if scene.get("style"):
            return scene["style"]
    return ""


def check_prompts(bank, scenes, image_bank=None):
    """Each style is judged by the gate that fits it.

    Photoreal delegates to realism_lint, untouched. Stylised cannot: every word
    of that look is on realism_lint's banned list, and correctly so - so it is
    judged against the style's own `expects` block instead.
    """
    image_bank = image_bank or bp.load_bank()
    style = style_of(scenes)
    cfg = bs.styles(bank).get(style, {})

    if cfg.get("gate") == "realism_lint" or not cfg:
        weak = []
        for scene in scenes:
            present, _, banned, _, _ = rl.lint((scene.get("prompt") or "").lower(), image_bank)
            if len(present) < 8 or banned:
                weak.append("scene {} {}/8{}".format(
                    scene.get("n"), len(present),
                    " banned: " + ", ".join(banned) if banned else ""))
        if weak:
            return False, "; ".join(weak[:3])
        return True, "every scene 8/8 on realism_lint"

    expects = cfg.get("expects", {})
    weak = []
    for scene in scenes:
        text = (scene.get("prompt") or "").lower()
        got = [name for name, keys in expects.items() if any(k in text for k in keys)]
        if len(got) < len(expects):
            lost = [n for n in expects if n not in got]
            weak.append("scene {} missing {}".format(scene.get("n"), ", ".join(lost)))
    if weak:
        return False, "; ".join(weak[:3])
    return True, "every scene carries the full {} look".format(style)


# --------------------------------------------------------------------------- #
# The trade format's own four
#
# These exist because the reference videos in Downloads/video are made of four
# things the story format never asks for: a costume, two animals in frame, a
# camera that does not move, and a different job every take. Take any one away
# and it stops being this genre.
# --------------------------------------------------------------------------- #
def check_costume(bank, scenes):
    """An undressed cat is just a cat video."""
    bare = [str(s.get("n")) for s in scenes
            if not (s.get("spec", {}).get("wardrobe") or "").strip()]
    if bare:
        return False, ("scene(s) {} have no costume - the hard hat and the hi-vis are "
                       "the whole genre".format(", ".join(bare)))
    return True, "every scene is in uniform"


PAIR_WORDS = ("two ", "three ", "pair", "couple", "both", "together")


def check_pair(bank, scenes):
    """Two cats in frame, because the comedy is the relationship.

    Deliberately the same words build_motion's `second_subject` detector looks
    for, so a subject that satisfies this satisfies that too rather than the two
    disagreeing about what "two cats" means.
    """
    alone = []
    for scene in scenes:
        text = "{} {}".format(scene.get("spec", {}).get("subject", ""),
                              scene.get("spec", {}).get("action", "")).lower()
        if not any(word in text for word in PAIR_WORDS):
            alone.append(str(scene.get("n")))
    if alone:
        return False, ("scene(s) {} put one animal in frame - this format is two of "
                       "them working".format(", ".join(alone)))
    return True, "two in frame throughout"


DRIFT_WORDS = ("push in", "pull out", "dolly", "orbit", "tracking", "pan ", "tilt",
               "zoom", "crane", "handheld", "drift", "arc around", "fly")


def check_locked_off(bank, scenes):
    """The camera holds still. Every reference video does, without exception."""
    moving = []
    for scene in scenes:
        text = (scene.get("motion_prompt") or "").lower()
        found = [word.strip() for word in DRIFT_WORDS if word in text]
        if found:
            moving.append("scene {} ({})".format(scene.get("n"), ", ".join(found[:2])))
    if moving:
        return False, ("{} - the camera moves. This format holds one frame and lets "
                       "the action happen inside it".format("; ".join(moving[:3])))
    return True, "the camera never moves"


def check_tasks_vary(bank, scenes):
    """Two takes of the same job is padding, the same as a repeated action."""
    tasks = [(s.get("n"), (s.get("task") or "").strip().lower()) for s in scenes]
    named = [(n, t) for n, t in tasks if t]
    if len(named) < 2:
        return True, "too few tasks to compare"
    if len(named) < len(tasks):
        blank = [str(n) for n, t in tasks if not t]
        return False, "scene(s) {} name no job".format(", ".join(blank))
    seen, repeats = {}, []
    for n, task in named:
        if task in seen:
            repeats.append("scenes {} and {}".format(seen[task], n))
        else:
            seen[task] = n
    if repeats:
        return False, "{} do the same job".format("; ".join(repeats))
    return True, "{} different jobs".format(len(seen))


CHECKS = [
    ("arc", "Story shape", check_arc),
    ("clips", "Real clip lengths", check_clip_lengths),
    ("trims", "Trims fit their clips", check_trims),
    ("runtime", "Adds up to the target", check_runtime),
    ("hook", "Opens in 3 seconds", check_hook),
    ("identity", "The same cats throughout", check_identity),
    ("moves_vary", "Camera varies", check_moves_vary),
    ("shot_repeats", "Repeated beats vary their shot", check_shot_repeats),
    ("actions_vary", "Something new each scene", check_actions_vary),
    ("moves_fit", "Moves suit the stills", check_moves_fit),
    ("words", "Narration and captions", check_words),
    ("style", "One style", check_one_style),
    ("prompts", "Stills pass their gate", check_prompts),
    ("costume", "In uniform", check_costume),
    ("pair", "Two cats in frame", check_pair),
    ("locked_off", "The camera holds still", check_locked_off),
    ("tasks_vary", "A different job each take", check_tasks_vary),
]

# Which checks a format is judged by. A format is not scored on rules that
# describe a different one: `trade` has no 3-second hook because it opens on a
# full take, no varying camera because every take is locked off ON PURPOSE, and
# no captions because these videos have none.
DEFAULT_CHECKS = [key for key, _, _ in CHECKS
                  if key not in ("costume", "pair", "locked_off", "tasks_vary")]


def checks_for(bank, fmt=None):
    cfg = bs.format_cfg(bank, fmt)
    wanted = cfg.get("checks") or DEFAULT_CHECKS
    order = {key: index for index, (key, _, _) in enumerate(CHECKS)}
    return [key for key in sorted(set(wanted), key=lambda k: order.get(k, 99))
            if key in order]


def lint(bank, scenes, arc=None, seconds=None, image_bank=None, clip_length=None,
         fmt=None):
    """[(key, label, passed, detail)] - one row per check for THIS format."""
    fmt = fmt or (scenes[0].get("format") if scenes else None)
    wanted = set(checks_for(bank, fmt))
    results = []
    for key, label, fn in CHECKS:
        if key not in wanted:
            continue
        if key == "arc":
            # The clip length is what decides how many times a repeatable beat
            # repeats, so the shape check needs it to know what to expect.
            if clip_length is None and scenes:
                clip_length = max(s.get("clip_seconds", 0) for s in scenes) or None
            passed, detail = fn(bank, scenes,
                                arc or bs.format_cfg(bank, fmt).get("default_arc")
                                or bank.get("default_arc", "classic"),
                                seconds, clip_length, fmt)
        elif key == "runtime":
            passed, detail = fn(bank, scenes, seconds)
        elif key == "prompts":
            passed, detail = fn(bank, scenes, image_bank)
        else:
            passed, detail = fn(bank, scenes)
        results.append((key, label, passed, detail))
    return results


def score(results):
    return sum(1 for _, _, passed, _ in results if passed), len(results)


def cost_note(scenes):
    """Generated seconds versus kept seconds - what the clips actually cost.

    Not a pass/fail: rounding a scene up to a whole second is unavoidable, so a
    small gap is the normal state. It used to sit near 2x because clip lengths
    were quantised to 5 or 10; on a model that takes any whole second it should
    stay close to 1.0, and anything above 1.3 means the plan is buying seconds
    it throws away.
    """
    generated = sum(s.get("clip_seconds", 0) for s in scenes)
    kept = round(sum(s.get("edit_seconds", 0) for s in scenes), 1)
    if not generated:
        return "", 0.0
    ratio = generated / kept if kept else 0
    text = "{}s generated to keep {:.0f}s ({:.2f}x)".format(generated, kept, ratio)
    if ratio >= 1.3:
        text += " - a shorter clip length would buy fewer seconds you discard"
    return text, ratio


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a cat story before generating anything.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--story", required=True, help="path to a story JSON (scenes + arc)")
    p.add_argument("--arc", help="override the arc recorded in the file")
    p.add_argument("--seconds", type=int, help="override the runtime recorded in the file")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    path = Path(args.story)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Story file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))

    bank = bs.load_bank()
    scenes = data.get("scenes", [])
    arc = args.arc or data.get("arc") or bank.get("default_arc", "classic")
    seconds = args.seconds or data.get("seconds")

    results = lint(bank, scenes, arc, seconds)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<26} {}".format("PASS" if passed else "FAIL", label, detail))
    note, _ = cost_note(scenes)
    if note:
        print("cost  {:<26} {}".format("Generated vs kept", note))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
