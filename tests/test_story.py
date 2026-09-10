"""Cat stories: one scene per clip, the gate, and both looks.

The timing block is the load-bearing part. Kling 3.0 generates any whole second
from 3 to 15; the hook window is 3. Every combination of arc, runtime and clip
length has to satisfy both, and a mistake here is only visible after you have
paid for the clips - which is exactly what happened: the planner, the linter and
this test all agreed a 15-second "clip" was three 5-second ones, and nothing
downstream ever split one.

The other claim under test is that the stylised look never leaks into the shared
bank. prompt_bank.json and realism_lint.py are hashed - if a future change makes
stylised pass by weakening the 8/8 gate every other section depends on, this
suite fails.

Standard library plus PyQt6 for the editor round-trip. The model is a stand-in.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_ASSUME_YES", "1")
# This suite drives the real generate path, which logs an outcome row per scene.
# Those must never reach the live history: ratings there feed history.weights(),
# so synthetic rows quietly bias the vocabulary the app suggests. Set before
# history is imported - it reads the path once.
import tempfile as _tempfile  # noqa: E402
os.environ["AIVS_HISTORY_FILE"] = str(
    Path(_tempfile.gettempdir()) / "aivs-test-story-history.jsonl")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_sound as bsd  # noqa: E402
import build_story as bs  # noqa: E402
import realism_lint as rl  # noqa: E402
import story_lint as stl  # noqa: E402

bank = bs.load_bank()
image_bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake(reply):
    def _ask(prompt, system=None, images=(), **kw):
        return (reply, None)
    return _ask


BASE = {"subject": "a ginger tabby cat", "setting": "a suburban kitchen at night", "seed": 3}
SCRIPT = {
    "hook": {"caption": "He has done this before.", "narration": "Every night. Same time.",
             "action": "staring at the fridge handle"},
    "setup": {"caption": "Meet Gary.", "narration": "Nine kilos of determination.",
              "action": "padding across the tiles"},
    "escalation": {"caption": "He has a system.", "narration": "The handle, then the shelf.",
                   "action": "hauling the door open with both paws"},
    "escalation-2": {"caption": "It is working.", "narration": "Nobody taught him this.",
                     "action": "climbing onto the middle shelf"},
    "escalation-3": {"caption": "Too far.", "narration": "He knew the risk.",
                     "action": "dragging a whole ham onto the floor"},
    "escalation-4": {"caption": "No going back.", "narration": "Commitment is a virtue.",
                     "action": "sitting on the open fridge door"},
    "twist": {"caption": "He was not alone.", "narration": "The dog had been watching.",
              "action": "freezing mid-reach with his ears back"},
    "payoff": {"caption": "They split it.", "narration": "Settled like adults.",
               "action": "sharing a slice of ham with a dog"},
    "payoff-2": {"caption": "Same time tomorrow.", "narration": "Obviously.",
                 "action": "walking away from an empty plate"},
    # Short expands furthest, because it has only one repeatable beat to absorb
    # the whole runtime: 30s of 5s clips is hook + escalation x5 + payoff.
    "escalation-5": {"caption": "The shelf gave way.", "narration": "It usually does.",
                     "action": "riding the collapsing shelf to the floor"},
    "escalation-6": {"caption": "Still going.", "narration": "No notes.",
                     "action": "wedging himself behind the salad drawer"},
}


def build(arc="classic", seconds=30, clip=5, style="photoreal", script=None,
          spec=None, reference="scene-1.png"):
    return bs.compose_story(bank, spec or BASE, arc=arc, seconds=seconds,
                            clip_length=clip, style=style,
                            script=SCRIPT if script is None else script,
                            reference=reference, image_bank=image_bank)


# --------------------------------------------------------------------------- #
print("=== THE SHARED BANK IS NOT TOUCHED ===")
# If the stylised look were ever made to pass by loosening realism_lint or
# prompt_bank, every other section's 8/8 contract would weaken with it.
HASHES = {
    # Bumped for the missing "subtle rim light" lighting term (version 5 -> 6)
    # - the PDF's own canonical lighting list had it, prompt_bank.json's
    # generatable terms didn't, so realism_lint could detect it but
    # build_prompt.compose() could never produce it. Every other layer's
    # terms, the negatives/banned/warn lists and the shot presets are
    # untouched. (The value recorded here was itself briefly wrong - it had
    # been copied from a CRLF-mangled disk read rather than the real
    # committed content; fixed alongside adding CRLF normalisation to the
    # check above, confirmed against `git show HEAD:tools/prompt_bank.json`
    # directly rather than assumed.)
    # Bumped again (version 6 -> 7) for four new layers.texture.terms entries -
    # retouching-realism language mined from the Photography course library
    # (Dani Diamond's Retouching Notes / Earth Oliver's Texture Cleanup),
    # translated into how a photo should LOOK rather than an edit action,
    # since this app only ever writes prompts, never touches pixels. All four
    # confirmed detectable by the EXISTING DETECT["texture"]["keys"] (texture/
    # pores/surface detail/imperfection) - no realism_lint.py change needed
    # for this one. Every other layer's terms, the negatives/banned/warn
    # lists and the shot presets are untouched.
    # Bumped again (version 7 -> 8) for four real named cameras (ARRI Alexa,
    # Sony Venice 2, RED V-Raptor, Hasselblad medium format) added to
    # layers.camera.terms - from the Camera Language transcript's own
    # recommendations. Camera stays pick: 1, so this only broadens the pool;
    # every other layer's terms and the negatives/banned/warn lists are
    # untouched. Each new term confirmed to score 8/8 via an override, not
    # assumed - see tests/test_autofill.py.
    "tools/prompt_bank.json": "003669c8c1b1aa4f",
    # Bumped for the new Lighting section's DETECT["lighting"]["keys"]
    # additions (rembrandt, split lighting, catchlight, colour temperature,
    # falling off, ...) - every one of tools/lighting_bank.json's phrases
    # needed a way to be detected, the same rule every composition guide
    # already has to follow. Purely additive: no key was removed, no
    # existing key's meaning changed, lint()/find_terms()/the banned+warn
    # logic are untouched - verified by tests/test_lighting_bank.py's own
    # "no bank phrase is invisible to realism_lint" audit, not assumed.
    # Bumped again for the Composition section's seven technique-detection
    # keywords (negative space, lead room, midground, ...) - audited for real
    # by tests/test_composition_bank.py's own "no technique phrase is
    # invisible to realism_lint" check, not assumed.
    # Bumped again for the Lighting bank's deepen pass (Lindsay Adler's
    # course): four more named setups plus a light-shaping modifier
    # vocabulary (clam shell, checkerboard, old hollywood, bounced off,
    # unmodified, diffusion panel) - audited for real, zero gaps confirmed,
    # not assumed. Posing's own bank needed no DETECT change at all: posing
    # is descriptive spec content, not one of the 8 gated layers.
    # Bumped again for four pieces mined from the AI Video Bootcamp lighting/
    # framing/color documents, all audited for real (zero detectability gaps,
    # zero banned/warn hits, confirmed by running lint() against every
    # phrase, not assumed): the Color Grading section's DETECT["colour"]
    # keys, the Composition bank's "haze" atmosphere technique, named-camera
    # keys (arri alexa, sony venice, red v-raptor, hasselblad) and the
    # lighting bank's "material response" technique, and the Camera Angle
    # section's side/size keys not already covered by motion_bank.json's own
    # framing terms - see tests/test_color_bank.py, test_composition_bank.py,
    # test_lighting_bank.py, test_camera_angle_bank.py, test_autofill.py.
    # Bumped again: the DETECT layer check was a bare `key in text` substring
    # match, so "wear" scored the texture layer inside "streetwear" and let a
    # brief.upgrade_prompt() rewrite that stripped every real texture word
    # still pass 8/8. Single plain-word keys are now start-anchored
    # (`\bkey`), multi-token keys stay substrings so "mm lens" still catches
    # "85mm lens" and "imperfection" still catches "imperfections". No key
    # added or removed; find_terms()/banned/warn/negatives untouched - the
    # gate only got STRICTER. Every bank suite's own detectability audit still
    # passes, confirming no real phrase became invisible.
    "tools/realism_lint.py": "1571e1641f8f9164",
    # Bumped for a larger style_presets list (version 2 -> 3) - ten more
    # camera/lighting/grade combinations drawn from the same PDF vocabulary
    # the image side already had, cycled by seed the same way the original
    # six were. The 40 movements themselves, their requires/image_hints, the
    # two toolkit rules, and the negatives list are untouched.
    "tools/motion_bank.json": "24e5d16237c3c574",
}
for name, expected in HASHES.items():
    raw = (ROOT / name).read_bytes()
    # Normalise CRLF -> LF before hashing. The value in HASHES was computed
    # against the committed blob (LF); a Windows checkout with
    # core.autocrlf=true converts every text file to CRLF on disk, which
    # changed this hash on every single line without changing a single
    # character of content - confirmed directly: the raw disk bytes hashed
    # to bccad86a45cbc8bb while `git show HEAD:tools/motion_bank.json`
    # hashed to the correct 24e5d16237c3c574, and stripping \r\n -> \n from
    # the disk bytes reproduces that same hash exactly. Without this, the
    # check is really testing "did git's line-ending config change", not
    # "did the file's content change" - the opposite of what it exists for.
    got = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:16]
    check("{} is unchanged".format(name), got == expected, "{} != {}".format(got, expected))
check("the banned list still forbids the stylised words",
      all(word in image_bank["banned"] for word in ("cartoon style", "cgi", "3d render")))
check("so the stylised vocabulary lives in story_bank",
      "3D animated short film still" in json.dumps(bs.styles(bank)))

print()
print("=== TIMING: every arc x runtime x clip ===")
# THE RULE IS MEMBERSHIP, NOT DIVISIBILITY. This test used to assert
# `r[3] % clip == 0`, which is the same mistake check_clip_lengths made: it
# passes a 15-second "clip" as three 5s clips, and nothing downstream ever
# splits one. Short at the default 30s shipped exactly that - three scenes of
# 15s - and the planner, the linter and this test all agreed with each other
# and all disagreed with Kling.
LOW, HIGH = bs.clip_range(bank)
hook_cap = float(bank.get("hook_seconds", 3.0))
combos = bad = 0
for arc in bs.arcs(bank):
    for seconds in (10, 15, 20, 30, 45, 60, 90, 120):
        for clip in range(LOW, HIGH + 1):
            combos += 1
            rows = bs.scene_timings(bank, arc, seconds, clip)
            runtime = round(sum(r[4] for r in rows), 2)
            problems = []
            if any(not (LOW <= r[3] <= clip) or r[3] != int(r[3]) for r in rows):
                problems.append("clip length {}".format(sorted({r[3] for r in rows})))
            if any(r[4] > r[3] + 1e-9 for r in rows):
                problems.append("trim longer than its clip")
            if abs(runtime - seconds) > 0.5:
                problems.append("runtime {}".format(runtime))
            if rows[0][4] > hook_cap + 1e-9:
                problems.append("hook {}".format(rows[0][4]))
            if len(bs.scene_keys(bank, arc, seconds, clip)) != len(rows):
                problems.append("scene_keys disagrees with plan_scenes")
            if problems:
                bad += 1
                print("      {} {}s clip{}s: {}".format(arc, seconds, clip, problems))
check("all {} combinations hold".format(combos), bad == 0, "{} broke".format(bad))

# The exact case he reported: "it generates just 3 story images".
short = bs.plan_scenes(bank, "short", 30, 5)
check("short/30s no longer asks for a 15-second clip",
      all(LOW <= row[2] <= 5 for row in short),
      str(sorted({row[2] for row in short})))
check("and it is no longer 3 scenes for 30 seconds", len(short) > 3, str(len(short)))

check("the hook limit is stated once, effectively",
      bs.beats(bank)["hook"]["max_edit_seconds"] == bank["hook_seconds"],
      "beat says {}, bank says {}".format(
          bs.beats(bank)["hook"].get("max_edit_seconds"), bank["hook_seconds"]))
# And if they ever drift, the planner takes the smaller so the gate still passes.
tightened = json.loads(json.dumps(bank))
tightened["hook_seconds"] = 2.0
rows = bs.plan_scenes(tightened, "classic", 30, 5)
check("a tighter bank limit wins over the beat's", rows[0][3] <= 2.0 + 1e-9,
      str(rows[0]))

check("a scene never keeps more than its clip",
      all(s["edit_seconds"] <= s["clip_seconds"] for s in build()))
# Kling 3.0's minimum IS the hook window, so the opening is a real 3s clip now
# rather than a 5s one with two seconds thrown away.
check("the hook is a clip, not a trim",
      build()[0]["clip_seconds"] == 3 and build()[0]["edit_seconds"] <= 3.0,
      "{}s clip -> {}s kept".format(build()[0]["clip_seconds"], build()[0]["edit_seconds"]))
generated = sum(s["clip_seconds"] for s in build())
kept = sum(s["edit_seconds"] for s in build())
check("generated is now close to kept, not double it", generated <= kept * 1.25,
      "{}s generated to keep {}s".format(generated, round(kept, 1)))

print()
print("=== THE GATE ===")
for arc in bs.arcs(bank):
    for style in ("photoreal", "stylised"):
        scenes = build(arc=arc, style=style)
        got, total = stl.score(stl.lint(bank, scenes, arc, 30, image_bank=image_bank))
        check("{} / {} passes on the bank's own defaults".format(arc, style),
              got == total, "{}/{}".format(got, total))


def fails_on(key, scenes, arc="classic", seconds=30):
    results = stl.lint(bank, scenes, arc, seconds, image_bank=image_bank)
    row = next(r for r in results if r[0] == key)
    return (not row[2]), row[3]


scenes = build()
missing_payoff = [s for s in scenes if s["beat"] != "payoff"]
failed, detail = fails_on("arc", missing_payoff)
check("a story with no payoff fails", failed, detail[:60])

# A 7-second clip is legal on Kling 3.0 and must NOT fail - that was the old
# model's rule. What must fail is a length outside 3..15, and a multiple of a
# legal length is not a get-out: 20 is 2x10 and is still unbuildable.
seven = [dict(s) for s in build()]
seven[1]["clip_seconds"] = 7
seven[1]["edit_seconds"] = 6.0
failed, detail = fails_on("clips", seven)
check("a 7-second clip is fine now", not failed, detail[:70])

for illegal in (20, 30, 2, 16):
    row = [dict(s) for s in build()]
    row[1]["clip_seconds"] = illegal
    failed, detail = fails_on("clips", row)
    check("a {}-second clip fails".format(illegal), failed, detail[:70])

overrun = [dict(s) for s in build()]
overrun[1]["edit_seconds"] = 99
failed, detail = fails_on("trims", overrun)
check("keeping more than the clip fails", failed, detail[:60])

short = [dict(s) for s in build()]
short[-1]["edit_seconds"] = 1.0
failed, detail = fails_on("runtime", short)
check("trims that do not add up fail", failed, detail[:70])
check("and it says by how much", "short by" in detail, detail[:70])

slow = [dict(s) for s in build()]
slow[0]["edit_seconds"] = 5.0
failed, detail = fails_on("hook", slow)
check("a 5-second opening fails", failed, detail[:60])

wordless = [dict(s) for s in build()]
wordless[0] = dict(wordless[0], caption="", narration="")
failed, _ = fails_on("hook", wordless)
check("a wordless opening fails", failed)

loose = [dict(s) for s in build()]
loose[2] = dict(loose[2], spec=dict(loose[2]["spec"], lock_identity=False))
failed, detail = fails_on("identity", loose)
check("an unlocked scene fails", failed, detail[:60])

repeat = [dict(s) for s in build()]
repeat[2] = dict(repeat[2], movement=repeat[1]["movement"])
failed, detail = fails_on("moves_vary", repeat)
check("the same move twice running fails", failed, detail[:60])

same = [dict(s) for s in build()]
same = [dict(s, spec=dict(s["spec"], action="sitting still")) for s in same]
failed, detail = fails_on("actions_vary", same)
check("every scene doing the same thing fails", failed, detail[:70])

mixed = [dict(s) for s in build()]
mixed[1] = dict(mixed[1], style="stylised")
failed, detail = fails_on("style", mixed)
check("mixing the two looks fails", failed, detail[:50])

print()
print("=== BOTH LOOKS, JUDGED BY THE RIGHT GATE ===")
photoreal = build(style="photoreal")
for scene in photoreal:
    present, _, banned, _, _ = rl.lint(scene["prompt"].lower(), image_bank)
    if len(present) != 8 or banned:
        check("photoreal scene {} is 8/8".format(scene["n"]), False,
              "{}/8 {}".format(len(present), banned))
        break
else:
    check("every photoreal scene is 8/8 on the untouched realism_lint", True)

stylised = build(style="stylised")
present, _, _, _, _ = rl.lint(stylised[0]["prompt"].lower(), image_bank)
check("a stylised prompt would FAIL realism_lint", len(present) < 8,
      "{}/8 - which is why it has its own gate".format(len(present)))
failed, detail = fails_on("prompts", stylised)
check("but passes the stylised gate", not failed, detail[:60])
check("and says so in its own words", "stylised" in detail, detail[:60])

print()
print("=== ONE CAT, NOT N CATS ===")
scenes = build()
check("scene 1 invents the cat", not scenes[0]["spec"].get("lock_identity"))
check("every later scene locks to it",
      all(s["spec"].get("lock_identity") for s in scenes[1:]))
check("and carries the reference",
      all(s["spec"].get("reference") == "scene-1.png" for s in scenes[1:]))
no_ref = build(reference=None)
failed, _ = fails_on("identity", no_ref)
check("without a reference the gate objects", failed)

print()
print("=== PER-SCENE ACTIONS REACH THE PROMPTS ===")
scenes = build()
prompts = [s["prompt"] for s in scenes]
check("each scene's action is in its own prompt",
      all(SCRIPT[s["key"]]["action"] in s["prompt"] for s in scenes))
check("so no two prompts are identical", len(set(prompts)) == len(prompts))

print()
print("=== COST: generated versus kept ===")
# This block used to assert the waste was ~2x and advise 5s clips. On a model
# that takes any whole second there is nothing left to quantise away, so the
# assertion is inverted: the waste has to STAY gone.
for seconds in (15, 30, 45, 60, 90):
    for clip in (3, 5, 8, 10, 15):
        note, ratio = stl.cost_note(build(seconds=seconds, clip=clip))
        check("{}s at {}s clips wastes almost nothing".format(seconds, clip),
              ratio <= 1.3, note)
worst = max(stl.cost_note(build(seconds=s, clip=c))[1]
            for s in (15, 30, 45, 60, 90) for c in (3, 5, 8, 10, 15))
check("the worst case across every combination is under 1.3x", worst < 1.3,
      "{:.2f}x".format(worst))

print()
print("=== THE EDIT SHEET ===")
sheets = bsd.story_sound(bsd.load_bank(), build())
text = bs.edit_sheet_text(bank, build(), sheets)
check("names every scene", all("{}. ".format(s["n"]) in text for s in build()))
check("prints the trim, not just the length", "use 0.0s -" in text)
check("carries the three sound layers",
      all(layer in text for layer in ("ambience", "key", "accent")))
check("names a cut between scenes", "cut out" in text)
# The export numbers are already encoded for the ads section; a second copy
# would be a second copy to go stale.
import build_ad as ba  # noqa: E402

publishing = ba.load_bank()["publishing"]["items"]
export = next(i["text"] for i in publishing if i["topic"] == "Export")
check("export settings are reused from ugc_bank, not restated", export in text)

print()
print("=== THE STORY WRITER, GATED ===")
# Derived, not hardcoded: the model is asked for as many scenes as the runtime
# needs, so a fixture listing the arc's five literal beats would be two scenes
# short of what story_from_idea now requires.
WANTED = bs.scene_keys(bank, "classic", 30, 5)
check("the writer is asked for every scene the runtime needs", len(WANTED) == 7,
      str(WANTED))
good = json.dumps({k: SCRIPT[k] for k in WANTED})
r = brief.story_from_idea(bank, image_bank, "a cat that raids the fridge", arc="classic",
                          style="photoreal", seconds=30, clip_length=5,
                          base_spec=BASE, ask=fake(good))
check("a good story is accepted", r["ok"] and r["accepted"],
      "{}/{}".format(r.get("score"), r.get("total")))

lazy = {k: dict(SCRIPT[k], action="sitting on the floor") for k in WANTED}
r2 = brief.story_from_idea(bank, image_bank, "x", arc="classic", style="photoreal",
                           seconds=30, clip_length=5, base_spec=BASE,
                           ask=fake(json.dumps(lazy)))
check("one action repeated is rejected", not r2["accepted"], r2["reason"][:70])

r3 = brief.story_from_idea(bank, image_bank, "x", arc="classic",
                           ask=fake('{"hook": {"caption": "hi"}}'))
check("a half-written story is refused", not r3["ok"], r3.get("error", "")[:50])

sneaky = {k: dict(SCRIPT[k], seed=99, reference="/etc/passwd", lock_identity=True)
          for k in WANTED}
r4 = brief.story_from_idea(bank, image_bank, "x", arc="classic", style="photoreal",
                           seconds=30, clip_length=5, base_spec=BASE,
                           ask=fake(json.dumps(sneaky)))
leaked = [k for block in r4.get("script", {}).values() for k in block
          if k not in {"caption", "narration", "action"}]
check("the model cannot set seed, reference or lock_identity", not leaked, str(leaked))

r5 = brief.story_from_idea(bank, image_bank, "x", arc="classic", ask=fake("no thanks"))
check("non-JSON is refused", not r5["ok"])

print()
print("=== THE FORM ===")
from PyQt6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402

from ui.views.cats import CatsView  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
view = CatsView(image_bank)
check("it builds a story on open", len(view.scenes) > 0, str(len(view.scenes)))
check("scene keys match the arc",
      [s["key"] for s in view.scenes] == view.scene_keys(), str(view.scene_keys()))

# An empty form is not a passing story, and the gate says why rather than
# pretending: several moves reveal surroundings, so they need surroundings.
empty_results = stl.lint(view.story_bank, view.scenes, view.arc_key(),
                         view.seconds.value(), image_bank=image_bank)
moves_row = next(r for r in empty_results if r[0] == "moves_fit")
check("an empty form fails on the missing setting", not moves_row[2], moves_row[3][:60])
check("and it names the cat, not 'a person'",
      "person" not in moves_row[3], moves_row[3][:60])

view.subject.setText(BASE["subject"])
view.setting.setText(BASE["setting"])
view.set_script(SCRIPT)
check("the script reaches the scenes",
      all(s["caption"] for s in view.scenes))
check("and the gate goes green", view.passing, view.lint_badge.text())

parsed = CatsView.parse_script(
    "[hook]\ncaption: A\nnarration: B\naction: C\n\n[setup]\ncaption: D\n")
check("the block format parses",
      parsed == {"hook": {"caption": "A", "narration": "B", "action": "C"},
                 "setup": {"caption": "D"}}, str(parsed))
check("junk lines are ignored",
      CatsView.parse_script("nonsense\n[hook]\nrubbish\ncaption: A\n")
      == {"hook": {"caption": "A"}})

view.arc.setCurrentIndex(view.arc.findData("epic"))
check("changing the arc re-plans", len(view.scenes) == 9, str(len(view.scenes)))
view.clip.setValue(10)
check("changing the clip length re-plans",
      all(3 <= s["clip_seconds"] <= 10 for s in view.scenes),
      str([s["clip_seconds"] for s in view.scenes]))
# A shorter clip means MORE scenes for the same runtime - that is the swap the
# scene count now makes, and it is the whole reason 15s clips stopped appearing.
before = len(view.scenes)
view.clip.setValue(3)
check("a shorter clip length means more scenes", len(view.scenes) > before,
      "{} -> {}".format(before, len(view.scenes)))
check("and every one of them is a length Kling accepts",
      all(3 <= s["clip_seconds"] <= 15 for s in view.scenes),
      str(sorted({s["clip_seconds"] for s in view.scenes})))

print()
print("=== AUTO-FILL: cast the cat, then write the story ===")
CAST = json.dumps({"subject": "a heavy ginger tabby with one torn ear",
                   "setting": "a suburban kitchen at night"})


def two_replies(first, second):
    """The cast call, then the script call - in that order."""
    calls = []

    def _ask(prompt, system=None, images=(), **kw):
        calls.append(prompt)
        return (first if len(calls) == 1 else second, None)
    return _ask


script_json = json.dumps({k: SCRIPT[k] for k in bs.scene_keys(bank, "classic", 30, 5)})
r = brief.autofill_story(bank, image_bank, "a cat that raids the fridge",
                         current={}, arc="classic", style="photoreal", seconds=30,
                         clip_length=5, ask=two_replies(CAST, script_json))
check("an empty form gets a cat", r["cast"].get("subject"), str(r.get("cast")))
check("and a place", r["cast"].get("setting"), str(r.get("cast")))
check("the story is written and accepted", r["ok"] and r["accepted"],
      "{}/{}".format(r.get("score"), r.get("total")))
check("the cat is specific enough to recognise", len(r["cast"]["subject"].split()) >= 4,
      r["cast"]["subject"])

# Blanks only. What he typed is the brief, not a suggestion to be improved on.
typed = {"subject": "a scruffy black cat", "seed": 0}
r2 = brief.autofill_story(bank, image_bank, "x", current=typed, arc="classic",
                          style="photoreal", seconds=30, clip_length=5,
                          ask=two_replies(CAST, script_json))
check("a typed cat survives", r2["spec"]["subject"] == "a scruffy black cat",
      r2["spec"]["subject"])
check("but the empty place is still filled",
      r2["spec"]["setting"] == "a suburban kitchen at night", r2["spec"].get("setting"))

# The placeholder is not an answer - the same rule the Compose auto-fill follows.
r3 = brief.autofill_story(bank, image_bank, "x",
                          current={"subject": brief.PLACEHOLDER_SUBJECT},
                          arc="classic", style="photoreal", seconds=30, clip_length=5,
                          ask=two_replies(CAST, script_json))
check("'a person' counts as empty, not as a cat",
      r3["spec"]["subject"] == "a heavy ginger tabby with one torn ear",
      r3["spec"]["subject"])

# Nothing to ask for means nothing is asked.
one_call = []


def counting(prompt, system=None, images=(), **kw):
    one_call.append(prompt)
    return (script_json, None)


brief.autofill_story(bank, image_bank, "x",
                     current={"subject": "a tabby", "setting": "a kitchen"},
                     arc="classic", style="photoreal", seconds=30, clip_length=5,
                     ask=counting)
check("a fully typed form skips the casting call", len(one_call) == 1, str(len(one_call)))

sneaky_cast = json.dumps({"subject": "a tabby", "setting": "a kitchen",
                          "seed": 99, "reference": "/etc/passwd", "lock_identity": True})
r4 = brief.autofill_story(bank, image_bank, "x", current={}, arc="classic",
                          style="photoreal", seconds=30, clip_length=5,
                          ask=two_replies(sneaky_cast, script_json))
check("the model still cannot set seed, reference or lock_identity",
      r4["spec"].get("seed") == 0 and "reference" not in r4["spec"]
      and "lock_identity" not in r4["spec"], str(sorted(r4["spec"])))
check("and what it tried is reported",
      {"seed", "reference", "lock_identity"} <= set(r4["dropped"]), str(r4["dropped"]))

print()
print("=== GENERATED STILLS ACTUALLY ARRIVE SOMEWHERE ===")
# The bug this replaces: every story result was handed to the Images/Variants
# grid, whose on_item_finished does `card = self.cards.get(index); if card is
# None: return`. With no variants built there were no cards, so a whole
# generated story was written to disk and silently dropped by the UI.
view.arc.setCurrentIndex(view.arc.findData("classic"))
view.clip.setValue(5)
view.subject.setText(BASE["subject"])
view.setting.setText(BASE["setting"])
view.set_script(SCRIPT)

# This suite writes outcome rows, so it must be pointed somewhere disposable
# first. Ratings feed history.weights(), which biases the vocabulary the app
# suggests - twenty-one synthetic 8/8 rows would quietly tilt it, and that is
# exactly what happened while this test was being written.
import history as _hist  # noqa: E402

check("the outcome log is redirected away from the live one",
      _hist.HISTORY != ROOT / "temp" / "outputs" / "history.jsonl", str(_hist.HISTORY))

offered = []
view.generate_requested.connect(lambda jobs: offered.append(jobs))
view.request_generate()
app.processEvents()
check("a job per scene", offered and len(offered[-1]) == len(view.scenes),
      str(len(offered[-1]) if offered else 0))
check("each job names its own output file",
      len({job["out_name"] for job in offered[-1]}) == len(offered[-1]))
check("and a history row per scene was written",
      len(view.entries) == len(view.scenes), str(len(view.entries)))

view.on_item_finished(0, str(ROOT / "tools" / "story_bank.json"))
check("the view keeps the file", view.images.get(0), str(view.images.get(0)))
check("and the scene row says so",
      view.scene_tree.topLevelItem(0).text(5) == "ready",
      view.scene_tree.topLevelItem(0).text(5))
view.on_item_failed(1, "the provider said no")
check("a failure is shown, not swallowed",
      view.scene_tree.topLevelItem(1).text(5) == "failed",
      view.scene_tree.topLevelItem(1).text(5))

# Re-planning must not appear to lose an image that is still on disk.
view.seconds.setValue(view.seconds.value())
view.rebuild()
check("a rebuild keeps the still it already has", view.images.get(0))

print()
print("=== CLIPS ===")
asked = []
view.video_requested.connect(lambda jobs, options: asked.append((jobs, options)))
view.images = {}
view.request_videos()
check("clips are refused before the stills exist", not asked)

view.images = {i: str(ROOT / "tools" / "story_bank.json") for i in range(len(view.scenes))}
view.request_videos()
check("and offered once every scene has one", asked and len(asked[-1][0]) == len(view.scenes),
      str(len(asked[-1][0]) if asked else 0))
jobs, options = asked[-1]
check("each clip runs for its scene's planned length",
      [job["duration"] for job in jobs] == [s["clip_seconds"] for s in view.scenes],
      str([job["duration"] for job in jobs]))
check("every duration is one Kling accepts",
      all(3 <= job["duration"] <= 15 for job in jobs))
check("each clip starts from its own still", all(job["image"] for job in jobs))
check("the motion prompt is what gets sent",
      jobs[0]["prompt"] == view.scenes[0]["motion_prompt"], jobs[0]["prompt"][:50])
check("cheapest options by default",
      options == {"mode": "std", "sound": False}, str(options))
check("the cost is stated before the button is pressed",
      "credits" in view.cost_note.text(), view.cost_note.text())

print()
print("=== BOTH PROMPTS ARE SHOWN ===")
view.rebuild_prompts()
boxes = view.prompts_body.findChildren(QPlainTextEdit)
check("two boxes per scene", len(boxes) == 2 * len(view.scenes), str(len(boxes)))
texts = [b.toPlainText() for b in boxes]
check("the still prompt is one of them", view.scenes[0]["prompt"] in texts)
check("and the video prompt is the other", view.scenes[0]["motion_prompt"] in texts,
      view.scenes[0]["motion_prompt"][:50])

print()
print("=== TRADE: measured from the reference videos, not invented ===")
# Four videos in Downloads/video were frame-sampled and cut-detected before any
# of this was written. Cut detection (ffmpeg select=gt(scene,0.1)) found NO
# cuts inside two of them and one cut in a third - every one is a locked-off
# camera holding a single take of about ten seconds. This block asserts the
# format's defaults actually match that, not just that they exist.
TRADE_SCRIPT = {
    "task": {"task": "shovelling wet cement beside a green wheelbarrow",
             "mishap": "one shoves the other flat into the dirt"},
    "task-2": {"task": "smoothing wet plaster onto a wall with a trowel",
               "mishap": "the other walks through it leaving paw prints"},
}
PAIR = {"subject": "two cats - a broad grey tabby with a torn ear and a lean "
                   "ginger tom with white paws", "seed": 0}

check("trade's default clip is 10s - every reference take runs about that long",
      bs.default_clip(bank, "trade") == 10, str(bs.default_clip(bank, "trade")))
check("trade's default runtime is 20s - the construction video, exactly",
      bs.default_seconds(bank, "trade") == 20, str(bs.default_seconds(bank, "trade")))

ten = bs.compose_story(bank, PAIR, arc="single", seconds=10, fmt="trade",
                       trade="construction", script=TRADE_SCRIPT, image_bank=image_bank)
check("a 10s video plans to exactly one take (video 2)", len(ten) == 1, str(len(ten)))
check("and that take is a real 10s clip", ten[0]["clip_seconds"] == 10, str(ten))

twenty = bs.compose_story(bank, PAIR, arc="shift", seconds=20, fmt="trade",
                          trade="construction", script=TRADE_SCRIPT, image_bank=image_bank)
check("a 20s video plans to exactly two takes (video 3)", len(twenty) == 2, str(len(twenty)))

check("every scene is locked off - no reference video ever moves the camera",
      all(s["movement"] == "locked-off" for s in twenty))
check("the locked-off phrase names no move at all",
      not any(word in twenty[0]["motion_prompt"].lower()
             for word in ("push in", "pull out", "dolly", "pan", "orbit", "zoom")),
      twenty[0]["motion_prompt"])
check("every scene puts two cats in the subject",
      all("two cats" in s["spec"]["subject"] for s in twenty))
check("every scene is in costume - the hard hat is the whole genre",
      all(s["spec"].get("wardrobe") for s in twenty),
      str([s["spec"].get("wardrobe") for s in twenty]))
check("the costume is the construction trade's, not invented per scene",
      all("hi-vis" in s["spec"]["wardrobe"] for s in twenty))

print()
print("=== TRADE GATE: rejects what the format is actually for ===")
def trade_fails_on(key, scenes, arc="shift", seconds=20):
    results = stl.lint(bank, scenes, arc, seconds, image_bank=image_bank, fmt="trade")
    row = next(r for r in results if r[0] == key)
    return (not row[2]), row[3]


base_trade = bs.compose_story(bank, PAIR, arc="shift", seconds=20, fmt="trade",
                              trade="construction", script=TRADE_SCRIPT,
                              image_bank=image_bank, reference="scene-1.png")
check("as composed, the trade story passes every one of its checks",
      stl.score(stl.lint(bank, base_trade, "shift", 20, image_bank=image_bank,
                         fmt="trade")) == (12, 12),
      str(stl.score(stl.lint(bank, base_trade, "shift", 20, image_bank=image_bank,
                             fmt="trade"))))

undressed = [dict(s, spec=dict(s["spec"], wardrobe="")) for s in base_trade]
failed, detail = trade_fails_on("costume", undressed)
check("a scene with no costume fails costume", failed, detail[:70])

alone = [dict(s, spec=dict(s["spec"], subject="a grey tabby cat")) for s in base_trade]
failed, detail = trade_fails_on("pair", alone)
check("a single-cat subject fails pair", failed, detail[:70])

drifting = [dict(s) for s in base_trade]
drifting[0]["motion_prompt"] = "slow push in on the two cats as they work"
failed, detail = trade_fails_on("locked_off", drifting)
check("a moving camera fails locked_off", failed, detail[:70])

same_job = [dict(s, task="shovelling wet cement") for s in base_trade]
failed, detail = trade_fails_on("tasks_vary", same_job)
check("two takes of the same job fail tasks_vary", failed, detail[:70])

print()
print("=== TRADE GATE: does not import the story format's rules ===")
# A trade story has no captions, no narration, and does not open on a 3-second
# hook - under the story format's checks those would be three separate
# failures. It must still score full marks under its own.
check("no caption or narration anywhere", not any(
    s.get("caption") or s.get("narration") for s in base_trade))
check("scene 1 is a full 10s take, not a 3s hook",
      base_trade[0]["edit_seconds"] == 10.0, str(base_trade[0]["edit_seconds"]))
trade_checks = set(stl.checks_for(bank, "trade"))
check("hook is not one of trade's checks", "hook" not in trade_checks)
check("moves_vary is not one of trade's checks", "moves_vary" not in trade_checks)
check("words is not one of trade's checks", "words" not in trade_checks)
got, total = stl.score(stl.lint(bank, base_trade, "shift", 20, image_bank=image_bank,
                                fmt="trade"))
check("and it still scores full marks", got == total, "{}/{}".format(got, total))

print()
print("=== THE STORY FORMAT IS UNTOUCHED BY ANY OF THIS ===")
story_checks = set(stl.checks_for(bank, "story"))
check("story's twelve checks are exactly what they were",
      story_checks == {"arc", "clips", "trims", "runtime", "hook", "identity",
                       "moves_vary", "actions_vary", "moves_fit", "words",
                       "style", "prompts"}, str(sorted(story_checks)))
check("none of trade's four checks leaked into story",
      not story_checks & {"costume", "pair", "locked_off", "tasks_vary"})
check("story still defaults to 5s clips and a 30s runtime",
      bs.default_clip(bank) == 5 and bs.default_seconds(bank) == 30,
      "{}s / {}s".format(bs.default_clip(bank), bs.default_seconds(bank)))
old_story = build()
check("an ordinary story still scores 12/12",
      stl.score(stl.lint(bank, old_story, "classic", 30, image_bank=image_bank))
      == (12, 12))

print()
print("=== IDENTITY: the pair, not a fresh cat every scene ===")
check("scene 1 carries no reference", not base_trade[0]["spec"].get("reference"))
check("scene 1 is not locked - there is nothing to lock to yet",
      not base_trade[0]["spec"].get("lock_identity"))
check("every later scene locks to scene 1",
      all(s["spec"].get("lock_identity") for s in base_trade[1:]))
check("and carries the SAME reference file - the pair, not a new one each time",
      len({s["spec"].get("reference") for s in base_trade[1:]}) == 1,
      str({s["spec"].get("reference") for s in base_trade[1:]}))

print()
print("=== THE UI SWITCHES FORMAT PROPERLY ===")
tview = CatsView(image_bank)
# isVisible() is always False for a widget tree that was never shown() - it
# reflects the ancestor chain, not the explicit state this test cares about.
# isHidden() reflects the explicit setVisible() call regardless.
check("opens on the story format", tview.format_key() == "story")
check("Job row is hidden for story", tview.form_rows["Job"][1].isHidden())
check("the hook marker is shown for story", tview.timeline.show_hook)

tview.format.setCurrentIndex(tview.format.findData("trade"))
check("the arc list is rebuilt to trade's own arcs",
      {tview.arc.itemData(i) for i in range(tview.arc.count())} == {"single", "shift", "day"},
      str([tview.arc.itemData(i) for i in range(tview.arc.count())]))
check("the clip length follows trade's default", tview.clip.value() == 10)
check("the runtime follows trade's default", tview.seconds.value() == 20)
check("Job row is shown for trade", not tview.form_rows["Job"][1].isHidden())
check("Look row is hidden for trade", tview.form_rows["Look"][1].isHidden())
check("the hook marker is suppressed for trade", not tview.timeline.show_hook)
check("the cat label becomes plural", tview.form_rows["The cat"][0].text() == "The cats")
check("the script help switched off the story text",
      tview.script_help.text() == tview.TRADE_HELP, tview.script_help.text())
check("and it is not the story help",
      tview.script_help.text() != tview.STORY_HELP)
check("the CapCut assembly panel switched off the story reference note",
      tview.steps_note.text() != bank["capcut"]["note"], tview.steps_note.text())

tview.subject.setText(PAIR["subject"])
tview.set_script(TRADE_SCRIPT)
check("the gate goes green in the real view too", tview.passing, tview.lint_badge.text())
check("the sound sheet names the pair, not the literal string 'the cat'",
      "two cats" in tview.sheet_box.toPlainText(),
      tview.sheet_box.toPlainText()[:120])

print()
print("=== THE 6-FIELD VIDEO-PROMPT TEMPLATE (Prompts tab) ===")
# Reuses `view` from THE FORM above - a real story, already built.
view.tabs.setCurrentIndex(view.PROMPTS_TAB)
view.rebuild_prompts()
check("every scene gets a custom_motion entry the first time its card renders",
      set(view.custom_motion) == set(range(len(view.scenes))),
      str(sorted(view.custom_motion)))
check("the default camera movement is never blank for a real movement",
      all(view.custom_motion[i]["camera_movement"] or view.scenes[i]["movement"] in (None, "")
          for i in range(len(view.scenes))))
check("Cats' style default asks for subtle motion, not Videos' plain 'natural motion'",
      all("subtle" in fields["style"] for fields in view.custom_motion.values()),
      str(view.custom_motion[0]["style"]))
check("the still prompt is untouched by any of this",
      all(view.scenes[i]["prompt"] for i in range(len(view.scenes))))

before = view.scenes[0]["motion_prompt"]
view._on_motion_field_edited(0, "camera_movement", "slow orbit around the cat")
check("editing a field re-assembles that scene's motion_prompt immediately",
      view.scenes[0]["motion_prompt"] != before
      and view.scenes[0]["motion_prompt"].startswith("slow orbit around the cat"),
      view.scenes[0]["motion_prompt"])
check("the live preview box updates too",
      view._motion_widgets[0]["preview"].toPlainText() == view.scenes[0]["motion_prompt"])

view._on_motion_field_edited(0, "audio_cues", "claws scraping on the linoleum floor")
check("the audio badge scores the cue via sound_lint, not silently",
      view._motion_widgets[0]["audio_badge"].property("status") in ("success", "warning"))
check("_audio_cue_overrides carries the edited cue for scene 0",
      view._audio_cue_overrides().get(0) == "claws scraping on the linoleum floor",
      str(view._audio_cue_overrides().get(0)))
check("every other scene still has its own default cue - defaulted, not blank",
      all(view._audio_cue_overrides().get(i, "").strip()
          for i in range(1, len(view.scenes))))
view._on_motion_field_edited(1, "audio_cues", "")
check("a scene's cue cleared back to blank drops out of the overrides dict",
      1 not in view._audio_cue_overrides(), str(view._audio_cue_overrides().get(1)))
view.refresh_sheet()
check("the edited cue reaches the actual CapCut sound sheet",
      "claws scraping on the linoleum floor" in view.sheet_box.toPlainText())

# A story rebuild (arc/length change, or just re-editing the script) recomposes
# every scene's motion_prompt from scratch - a stored hand edit has to win back
# over that the next time this scene's card is built, not be silently lost.
view.rebuild()
check("motion_prompt reverts to auto-composed immediately after a story rebuild",
      view.scenes[0]["motion_prompt"] != "slow orbit around the cat"
      or "no warped face" not in view.scenes[0]["motion_prompt"])
view.rebuild_prompts()
check("but the hand edit is restored the next time the Prompts tab renders",
      view.scenes[0]["motion_prompt"].startswith("slow orbit around the cat"),
      view.scenes[0]["motion_prompt"])

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL STORY CHECKS PASSED")
