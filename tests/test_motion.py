"""The Kling motion toolkit: the bank, the two PDF rules, and the gate."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_motion as bm
import build_prompt as bp
import motion_lint as ml
import realism_lint as rl

bank = bm.load_bank()
image_bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


SPECS = [
    {"subject": "a woman in her thirties", "setting": "a wide rooftop at dusk overlooking the city, mist rolling in",
     "action": "walking away from camera toward the edge", "mood": "calm"},
    {"subject": "a man with a beard", "setting": "a misty lake at dawn, trees on the far bank",
     "action": "wading into the water", "mood": "still"},
    {"subject": "a child", "setting": "a crowded market with tents and people, a doorway behind",
     "action": "holding a small brass key on the ground", "mood": "curious"},
]

print("=== bank integrity ===")
# 40 from the Kling toolkit (motion_bank.json) + the locked-off camera that
# load_bank() merges in from video_realism_bank.json.
check("41 movements (40 toolkit + locked-off)", len(bank["movements"]) == 41
      and "locked-off" in bank["movements"], str(len(bank["movements"])))
counts = {}
for movement in bank["movements"].values():
    counts[movement["category"]] = counts.get(movement["category"], 0) + 1
check("31 core / 6 niche / 4 combo",
      counts == {"core": 31, "niche": 6, "combo": 4}, str(counts))

missing_fields = [k for k, m in bank["movements"].items()
                  if not all(m.get(f) for f in ("name", "does", "lead", "example", "category"))]
check("every movement is complete", not missing_fields, str(missing_fields[:5]))

unknown = set()
for movement in bank["movements"].values():
    unknown |= set(movement.get("requires", [])) - set(bank["requirements"])
check("every requirement is defined", not unknown, str(sorted(unknown)))

undetected = set(bank["requirements"]) - set(bm.DETECTORS)
check("every requirement is detectable", not undetected, str(sorted(undetected)))

hint_shots = {m.get("image_hints", {}).get("shot") for m in bank["movements"].values()}
hint_shots.discard(None)
check("hint shots are real presets",
      hint_shots <= set(image_bank["shot_presets"]), str(hint_shots))

print()
print("=== RULE 1: always start with the camera angle ===")
bad = []
for key in bank["movements"]:
    for index, spec in enumerate(SPECS):
        prompt, _ = bm.compose(bank, key, spec)
        if ml.leads_with_camera(prompt, bank) is None:
            bad.append((key, index))
check("all 40 x 3 prompts lead with a camera move", not bad,
      "{} failures {}".format(len(bad), bad[:4]))

empty = [k for k in bank["movements"] if not bm.compose(bank, k, SPECS[0])[0].strip()]
check("no movement composes an empty prompt", not empty, str(empty[:5]))

print()
print("=== the motion gate ===")
good, _ = bm.compose(bank, "orbit-360", SPECS[0])
checks, _ = ml.lint(good, bank, "orbit-360", SPECS[0])
check("a good prompt passes", all(ok for _, ok, _ in checks),
      str([n for n, ok, _ in checks if not ok]))

checks, _ = ml.lint("a woman standing in a kitchen, warm light", bank)
by_name = {n: ok for n, ok, _ in checks}
check("no camera lead is caught", not by_name["Leads with a camera movement"])
check("no motion is caught", not by_name["Describes motion"])

checks, _ = ml.lint(
    "cinematic slow dolly in toward a man, then the camera pulls out to reveal the room",
    bank)
by_name = {n: ok for n, ok, _ in checks}
check("push-in + pull-out is caught", not by_name["No contradictions"])

checks, _ = ml.lint(
    "camera slowly orbits around a man while the camera smoothly tracking behind him", bank)
by_name = {n: ok for n, ok, _ in checks}
check("two competing moves are caught", not by_name["One dominant movement"])

checks, _ = ml.lint(
    "camera cranes down and slowly orbits around a warrior on a battlefield, descending while circling",
    bank, "combo-crane-orbit")
by_name = {n: ok for n, ok, _ in checks}
check("a declared combo is allowed two moves", by_name["One dominant movement"])

checks, _ = ml.lint(
    "camera slowly descends from above the surface into the kitchen underwater, bubbles rising",
    bank)
by_name = {n: ok for n, ok, _ in checks}
check("underwater in a kitchen is caught", not by_name["No contradictions"])

print()
print("=== RULE 2: think ahead - the still must support the move ===")
tight = {"subject": "a woman", "setting": "a room", "shot": "portrait"}
warnings = bm.check_compatibility(bank, "orbit-360", tight)
check("orbit on a tight portrait warns about space",
      any(w["requirement"] == "space" for w in warnings), str([w["requirement"] for w in warnings]))

dry = {"subject": "a woman", "setting": "a bright apartment kitchen"}
warnings = bm.check_compatibility(bank, "dive-underwater", dry)
check("underwater with no water warns",
      any(w["requirement"] == "water" for w in warnings), str([w["requirement"] for w in warnings]))

faceless = {"setting": "an empty street"}
warnings = bm.check_compatibility(bank, "over-shoulder", faceless)
check("over-the-shoulder with no subject warns",
      any(w["requirement"] == "subject" for w in warnings), str([w["requirement"] for w in warnings]))

facing = {"subject": "a woman", "setting": "a street", "action": "smiling at the camera"}
warnings = bm.check_compatibility(bank, "track-behind", facing)
check("tracking behind a face-on shot warns",
      any(w["requirement"] == "shoulder" for w in warnings), str([w["requirement"] for w in warnings]))

good_pair = {"subject": "a woman", "setting": "a wide rooftop overlooking the city",
             "action": "walking away from camera", "shot": "environmental"}
check("a compatible pairing produces no warnings",
      bm.check_compatibility(bank, "track-behind", good_pair) == [],
      str(bm.check_compatibility(bank, "track-behind", good_pair)))

check("warnings carry a fix",
      all(w["fix"] for w in bm.check_compatibility(bank, "orbit-360", tight)))

print()
print("=== precedence: hints fill gaps, explicit choices win ===")
silent = {"subject": "a woman", "seed": 0}
merged = bm.apply_image_hints(bank, "orbit-360", silent)
check("hint fills a silent shot", merged.get("shot") == "environmental", str(merged.get("shot")))
check("hint fills composition",
      merged.get("overrides", {}).get("composition") == ["natural framing"],
      str(merged.get("overrides")))

explicit = {"subject": "a woman", "seed": 0, "shot": "portrait"}
merged = bm.apply_image_hints(bank, "orbit-360", explicit)
check("explicit shot survives", merged.get("shot") == "portrait", str(merged.get("shot")))
notes = bm.hint_conflicts(bank, "orbit-360", explicit)
check("the conflict is reported", len(notes) == 1, str(notes))
check("reported, not corrected", merged.get("shot") == "portrait")

own = {"subject": "a woman", "seed": 0, "overrides": {"composition": ["rule of thirds"]}}
merged = bm.apply_image_hints(bank, "orbit-360", own)
check("an explicit composition override survives",
      merged["overrides"]["composition"] == ["rule of thirds"], str(merged["overrides"]))

print()
print("=== the 6-field template: assemble_template() ===")
text = bm.assemble_template(
    bank, "close-up shot", "a ginger tabby cat", "staring at the fridge handle",
    "camera slowly pushes in, tension building", "shot on a DSLR, natural color grading")
check("camera movement opens the text regardless of argument/field order",
      text.startswith("camera slowly pushes in"), text[:60])
check("every field's own text survives somewhere in the assembly",
      all(part in text for part in
          ("close-up shot", "a ginger tabby cat", "staring at the fridge handle",
           "camera slowly pushes in", "shot on a DSLR, natural color grading")))
check("the standing negative guard is always appended",
      all(term in text for term in bank["negatives"]), text[-120:])
checks, _ = ml.lint(text, bank)
check("the assembled template passes every motion check",
      all(ok for _, ok, _ in checks), str([n for n, ok, _ in checks if not ok]))

blank = bm.assemble_template(bank, "", "", "", "", "")
check("every field blank still only carries the negative guard, no stray commas",
      blank == bm.negative_tail(bank), blank)

print()
print("=== the negative-artifact guard ===")
check("compose() always closes with the negative guard",
      all(bm.compose(bank, key, {"subject": "a woman"})[0].endswith(bm.negative_tail(bank))
          for key in bank["movements"]))
check("negatives is a real, non-empty bank list",
      isinstance(bank.get("negatives"), list) and len(bank["negatives"]) >= 4,
      str(bank.get("negatives")))
check("a bank with no negatives key falls back rather than crashing",
      bm.negative_tail({}) == ", ".join(bm.DEFAULT_NEGATIVES))

print()
print("=== the opt-in avatar/multi-cut guard ===")
check("avatar_guard is a real, non-empty bank list, separate from negatives",
      isinstance(bank.get("avatar_guard"), list) and len(bank["avatar_guard"]) >= 4,
      str(bank.get("avatar_guard")))
check("a bank with no avatar_guard key falls back rather than crashing",
      bm.avatar_guard_tail({}) == ", ".join(bm.DEFAULT_AVATAR_GUARD))

off = bm.compose(bank, "orbit-360", {"subject": "a woman"})[0]
on = bm.compose(bank, "orbit-360", {"subject": "a woman"}, avatar_guard=True)[0]
check("avatar_guard defaults to off - compose() carries none of its terms",
      not any(term in off for term in bank["avatar_guard"]), off[-160:])
check("avatar_guard=True appends every one of its terms",
      all(term in on for term in bank["avatar_guard"]), on[-220:])
check("it comes AFTER the standing negative guard, not instead of it",
      on.index(bm.negative_tail(bank)) < on.index(bm.avatar_guard_tail(bank)), on[-220:])
check("it does not disturb the standing negative guard itself",
      all(term in on for term in bank["negatives"]), on[-220:])

template_off = bm.assemble_template(
    bank, "close-up", "a woman", "talking", "camera pushes in", "natural light")
template_on = bm.assemble_template(
    bank, "close-up", "a woman", "talking", "camera pushes in", "natural light",
    avatar_guard=True)
check("assemble_template() also defaults to off",
      not any(term in template_off for term in bank["avatar_guard"]), template_off[-160:])
check("assemble_template(avatar_guard=True) appends every term",
      all(term in template_on for term in bank["avatar_guard"]), template_on[-220:])

checks, _ = ml.lint(on, bank, "orbit-360", {"subject": "a woman"})
by_name = {n: ok for n, ok, _ in checks}
check("motion_lint still passes a prompt carrying the extra guard - it's untouched by this",
      by_name["Negative guard present"])

TOOL = ROOT / "tools" / "build_motion.py"
p = subprocess.run(
    [sys.executable, str(TOOL), "--movement", "orbit-360", "--subject", "a woman",
     "--no-write", "--avatar-guard"],
    capture_output=True, text=True, cwd=str(ROOT))
check("--avatar-guard exits 0", p.returncode == 0, p.stderr[:160])
check("--avatar-guard reaches the printed prompt",
      all(term in p.stdout for term in bank["avatar_guard"]), p.stdout[-220:])

p = subprocess.run(
    [sys.executable, str(TOOL), "--movement", "orbit-360", "--subject", "a woman", "--no-write"],
    capture_output=True, text=True, cwd=str(ROOT))
check("without the flag, none of the avatar-guard terms print",
      not any(term in p.stdout for term in bank["avatar_guard"]), p.stdout[-160:])

print()
print("=== RULE 7: the negative guard is now checked, not just appended ===")
# Images have checked for this since the beginning (realism_lint.negatives_present);
# video never did, so a prompt that lost the tail some other way would still
# score a clean PASS. This closes that gap.
good, _ = bm.compose(bank, "orbit-360", SPECS[0])
present, missing = ml.negatives_present(good, bank)
check("a normally-composed prompt carries every negative term", present, str(missing))
checks, _ = ml.lint(good, bank, "orbit-360", SPECS[0])
by_name = {n: ok for n, ok, _ in checks}
check("...and the check shows up in lint()'s own output", by_name["Negative guard present"])

stripped = good.replace(bm.negative_tail(bank), "").rstrip(", ")
present, missing = ml.negatives_present(stripped, bank)
check("a prompt with the tail stripped is caught", not present, str(missing))
checks, _ = ml.lint(stripped, bank, "orbit-360", SPECS[0])
by_name = {n: ok for n, ok, _ in checks}
check("...and fails the gate for exactly that reason",
      not by_name["Negative guard present"])

partial = good.replace("no extra fingers", "").replace(", , ", ", ")
present, missing = ml.negatives_present(partial, bank)
check("losing even one negative term is caught, not just all-or-nothing",
      not present and missing == ["no extra fingers"], str(missing))

print()
print("=== concrete style presets, not vague words ===")
check("style_presets is a real, non-empty bank list",
      isinstance(bank.get("style_presets"), list) and len(bank["style_presets"]) >= 3,
      str(bank.get("style_presets")))
check("the preset list was meaningfully enriched, not left at the original 6",
      len(bank["style_presets"]) >= 12, str(len(bank["style_presets"])))
check("every preset is still a concrete phrase, not a duplicate",
      len(set(bank["style_presets"])) == len(bank["style_presets"]),
      str(bank["style_presets"]))
check("no preset uses the vague words the Reddit retrospective warned against",
      not any(word in preset.lower() for preset in bank["style_presets"]
              for word in ("cinematic", "professional", "high quality")),
      str(bank["style_presets"]))
check("style_preset() cycles reproducibly by seed",
      bm.style_preset(bank, seed=0) == bm.style_preset(bank, seed=0)
      and bm.style_preset(bank, seed=len(bank["style_presets"]))
      == bm.style_preset(bank, seed=0))
check("compose()'s own default no longer says the vague 'cinematic lighting'",
      "cinematic lighting" not in bm.compose(bank, "orbit-360", {"subject": "a woman"})[0])

print()
print("=== one action per prompt (RULE from 10,000 AI videos) ===")
chained = bm.assemble_template(
    bank, "", "a cat", "walking while talking while eating",
    "camera slowly pushes in", "natural motion")
checks, _ = ml.lint(chained, bank)
by_name = {n: ok for n, ok, _ in checks}
check("a chained action is caught", not by_name["One action, not a chain"], chained)

single = bm.assemble_template(
    bank, "", "a cat", "staring at the fridge handle",
    "camera slowly pushes in", "natural motion")
checks, _ = ml.lint(single, bank)
by_name = {n: ok for n, ok, _ in checks}
check("a single action passes", by_name["One action, not a chain"], single)

check("a camera direction using 'then' is not falsely flagged",
      not ml.chains_actions("camera pushes in, then holds on the subject's face"))

# Bootcamp PDF audit: the Kling Camera PDF names 4 "combo movements" as a
# legitimate technique (e.g. "Crane Down + Orbit"), and motion_bank.json
# already models them (category "combo") - but their own lead/detail text
# ("descending while circling") tripped this same chain check the moment it
# shipped, rejecting 3 of the app's own 40 sanctioned movements. The check
# must be scoped to the SUBJECT's action, not the camera's.
for key in ("wide-static", "tilt-up-approach", "combo-crane-orbit"):
    cat_spec = {"subject": "a ginger tabby cat", "action": "sitting on a windowsill"}
    text, _ = bm.compose(bank, key, cat_spec)
    checks, _ = ml.lint(text, bank, key, cat_spec)
    by_name = {n: ok for n, ok, _ in checks}
    check("{} (a legitimate combo/compound camera phrase) is not flagged".format(key),
          by_name["One action, not a chain"], text)

chained_through_combo = bm.assemble_template(
    bank, "", "a cat", "walking while talking while eating",
    bank["movements"]["combo-crane-orbit"]["lead"], "natural motion")
checks, _ = ml.lint(chained_through_combo, bank, "combo-crane-orbit")
by_name = {n: ok for n, ok, _ in checks}
check("a genuinely chained SUBJECT action still fails, even through a combo movement",
      not by_name["One action, not a chain"], chained_through_combo)

print()
print("=== hints never break the image score ===")
broken = []
for key in bank["movements"]:
    merged = bm.apply_image_hints(bank, key, {"subject": "a woman in a room", "seed": 0})
    prompt, _ = bp.compose(image_bank, merged)
    present, _, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    if len(present) != 8 or banned:
        broken.append((key, len(present), banned))
check("all 40 movements still yield 8/8 stills", not broken, str(broken[:4]))

print()
print("=== bank versioning ===")
import history as hist
# The version is expected to move whenever the term lists change, so assert the
# machinery rather than the number - pinning the literal makes a correct bump
# look like a regression.
version = image_bank.get("version")
check("prompt_bank carries a version", isinstance(version, int) and version >= 1,
      str(version))
check("history reads the same one", hist.current_bank_version() == version, str(version))
stale = [{"rating": 5, "bank_version": version - 1, "layers": {"core": ["photorealistic"]}}]
fresh, skipped = hist.usable(stale)
check("a stale entry is excluded, not mixed", fresh == [] and skipped == 1,
      "fresh={} skipped={}".format(len(fresh), skipped))
current = [{"rating": 5, "bank_version": version, "layers": {"core": ["photorealistic"]}}]
fresh, skipped = hist.usable(current)
check("a current entry is used", len(fresh) == 1 and skipped == 0)

print()
print("=== glossary ===")
import json
glossary = json.loads((ROOT / "tools" / "glossary.json").read_text(encoding="utf-8"))
check("50 terms", len(glossary["terms"]) == 50, str(len(glossary["terms"])))
cats = {t["category"] for t in glossary["terms"]}
check("every term has a known category", cats <= set(glossary["categories"]), str(cats))
check("every term has a definition", all(t["definition"] for t in glossary["terms"]))

print()
print("=== TIMED BEATS AND AN END STATE ===")
# The gap between "the clip I imagined" and "the clip that came back" is pace
# and endpoint. These pin the rules that make a beat line safe to send.
beat_bank = bm.load_bank()
plain = bm.assemble_template(beat_bank, "close-up shot", "a woman in a cafe", "lifts the cup",
                             "camera slowly pushes in", "shot on 35mm")
check("no beats: the prompt is exactly what it always was",
      plain == bm.assemble_template(beat_bank, "close-up shot", "a woman in a cafe",
                                    "lifts the cup", "camera slowly pushes in", "shot on 35mm",
                                    beats=[], end_state=""))
plain_checks = ml.lint(plain, beat_bank, seconds=5)[0]
check("no beats: still scored on the original seven rules", len(plain_checks) == 7,
      str(len(plain_checks)))

beats = [(0, 2, "lifts the cup and blows across it"), (2, 4, "glances up at the lens"),
         (4, 5, "holds still, half-smiling")]
timed = bm.assemble_template(beat_bank, "close-up shot", "a woman in a cafe", "lifts the cup",
                             "camera slowly pushes in", "shot on 35mm",
                             beats=beats, end_state="still, eyes on camera, steam drifting")
checks = ml.lint(timed, beat_bank, seconds=5)[0]
check("a good timed prompt passes all ten", len(checks) == 10 and all(ok for _, ok, _ in checks),
      str([(n, d) for n, ok, d in checks if not ok]))
check("the camera still leads", timed.startswith("camera slowly pushes in"))
check("beats come before the style and the negative guard",
      timed.index("0-2s:") < timed.index("shot on 35mm") < timed.index("no warped face"))
check("the untimed action is not repeated in front of the beats",
      timed.count("lifts the cup") == 1, timed)
check("parse_beats reads back exactly what format_beats wrote",
      bm.parse_beats(timed) == beats, str(bm.parse_beats(timed)))


def beat_result(name, prompt, seconds=5):
    return next((ok, d) for n, ok, d in ml.lint(prompt, beat_bank, seconds=seconds)[0] if n == name)


gap = timed.replace("2-4s", "3-4s")
check("a gap between beats fails", beat_result("Beats cover the clip", gap)[0] is False,
      beat_result("Beats cover the clip", gap)[1])
overlap = timed.replace("2-4s", "1-4s")
check("overlapping beats fail", beat_result("Beats cover the clip", overlap)[0] is False)
late = timed.replace("0-2s", "1-2s")
check("beats that do not start at 0s fail", beat_result("Beats cover the clip", late)[0] is False)
check("beats that stop short of the clip fail",
      beat_result("Beats cover the clip", timed, seconds=8)[0] is False,
      beat_result("Beats cover the clip", timed, seconds=8)[1])
chained = timed.replace("glances up at the lens", "glances up while talking while eating")
check("a chained beat fails", beat_result("One action per beat", chained)[0] is False)
endless = bm.assemble_template(beat_bank, "close-up shot", "a woman", "", "camera slowly pushes in",
                               "shot on 35mm", beats=beats)
check("beats without an end state fail", beat_result("States where it ends", endless)[0] is False)

drafted = bm.split_beats("lifts the cup, then glances up at the lens", 5)
check("split_beats: a sequenced action becomes one beat per clause",
      [a for _s, _e, a in drafted] == ["lifts the cup", "glances up at the lens"], str(drafted))
check("split_beats: covers exactly 0 to the clip length",
      drafted[0][0] == 0 and drafted[-1][1] == 5
      and all(a[1] == b[0] for a, b in zip(drafted, drafted[1:])), str(drafted))
single = bm.split_beats("turns from the window", 5)
check("split_beats: one action gets a closing hold so the clip cannot drift",
      len(single) == 2 and single[-1][2] == bm.DEFAULT_HOLD, str(single))
for seconds in range(3, 16):
    for action in ("nods", "walks in; sits down; picks up the phone; smiles; waves"):
        d = bm.split_beats(action, seconds)
        if not (d[0][0] == 0 and d[-1][1] == seconds
                and all(a[1] == b[0] and a[0] < a[1] for a, b in zip(d, d[1:]))):
            check("split_beats covers {}s for {!r}".format(seconds, action), False, str(d))
check("split_beats covers every legal clip length (3-15s) with no gaps", True)
check("split_timing_text reads Cats' one-line form",
      bm.split_timing_text("0-3s: stalks the toy; 3-5s: pounces ENDS ON: sitting beside it")
      == ([(0, 3, "stalks the toy"), (3, 5, "pounces")], "sitting beside it"))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL MOTION CHECKS PASSED")
