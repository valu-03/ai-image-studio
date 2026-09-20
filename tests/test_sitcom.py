"""The `sitcom` format: a locked cast, a five-stage curve, five audio layers,
and a post - end to end, and without touching the two formats that came first.

The assertion this file exists to protect is the last section: `story` and
`trade` must score exactly what they scored before any of this was added. A
third format that quietly re-tunes the other two is worse than no third format.
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_pet_sound as bps  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_social as bsoc  # noqa: E402
import build_sound as bsd  # noqa: E402
import build_story as bs  # noqa: E402
import safety_lint as sfl  # noqa: E402
import social_lint as socl  # noqa: E402
import sound_lint as sl  # noqa: E402
import story_lint as stl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bs.load_bank()
image_bank = bp.load_bank()

SCRIPT = {
    "hook": {"caption": "He has done this before.",
             "lead_action": "clutching a tiny rubber phone to his chest",
             "foil_action": "watching from the arm of the sofa"},
    "tantrum": {"caption": "Full body. No notes.",
                "lead_action": "rolling onto his back with all four paws going",
                "foil_action": "sitting completely still"},
    "discipline": {"caption": "Bap.",
                   "lead_action": "frozen mid-roll",
                   "foil_action": "delivering one soft cartoon-like paw tap, claws in"},
    "reset": {"caption": "Suddenly an angel.",
              "lead_action": "sitting bolt upright with paws tucked",
              "foil_action": "staring levelly"},
    "lecture": {"caption": "And STAY off the phone.",
                "lead_action": "shrinking slightly",
                "foil_action": "lecturing in short stern bursts"},
}


def story(cast="kitten_and_mother", script=None, seconds=15):
    return bs.compose_story(bank, {"seed": 3}, fmt="sitcom", cast=cast,
                            script=script if script is not None else SCRIPT,
                            seconds=seconds, reference="scene-1.png",
                            image_bank=image_bank)


print("=== the format is declared, and declares everything it needs ===")
cfg = bs.format_cfg(bank, "sitcom")
check("sitcom is a format", bool(cfg), str(list(bs.formats(bank))))
check("it owns five beats", len(cfg["beats"]) == 5, str(list(cfg["beats"])))
check("the curve arc is the five stages in order",
      cfg["arcs"]["curve"]["beats"] == ["hook", "tantrum", "discipline", "reset", "lecture"])
check("it declares its own action recipe",
      bs.action_recipe(bank, "sitcom").get("fields") == ["lead_action", "foil_action"])
check("the camera is locked off", bool(bs.locked_camera(bank, "sitcom")))
check("its source names itself as user-supplied, not course material",
      "NOT AI Video Bootcamp" in cfg.get("source", ""))
check("trade now declares its recipe too, so nothing is hardcoded",
      bs.action_recipe(bank, "trade").get("fields") == ["task", "mishap"])

print()
print("=== timing: 15s at 3s a stage is lossless ===")
for seconds in range(10, 16):
    scenes = story(seconds=seconds)
    total = round(sum(s["edit_seconds"] for s in scenes), 2)
    check("{}s -> {} scenes, {}s kept".format(seconds, len(scenes), total),
          len(scenes) == 5 and abs(total - seconds) <= 0.5,
          "{} scenes".format(len(scenes)))
scenes = story()
check("every clip is a legal Kling length",
      all(3 <= s["clip_seconds"] <= 15 and s["clip_seconds"] == int(s["clip_seconds"])
          for s in scenes))
check("15s generates exactly 15s", sum(s["clip_seconds"] for s in scenes) == 15,
      str(sum(s["clip_seconds"] for s in scenes)))

print()
print("=== the cast reaches the prompt ===")
scenes = story()
first = scenes[0]["spec"]
check("two cats ride ONE subject string starting with 'two'",
      first["subject"].startswith("two "), first["subject"][:40])
check("the scale sentence rides spec['extra']",
      any("quarter the size" in e for e in first["extra"]))
check("both actions joined with 'while'", " while " in first["action"], first["action"][:60])
check("every still still scores 8/8 with the cast in it",
      all(s["passed"] for s in scenes),
      str([(s["n"], s["score"]) for s in scenes if not s["passed"]]))
check("scenes 2..N lock to scene 1",
      all(s["spec"].get("lock_identity") for s in scenes[1:]))
check("scene 1 does NOT", not scenes[0]["spec"].get("lock_identity"))

print()
print("=== the whole gate passes, for both casts ===")
for cast in ("kitten_and_mother", "tommy"):
    rows = stl.lint(bank, story(cast), fmt="sitcom", seconds=15)
    got, total = stl.score(rows)
    check("'{}' scores {}/{}".format(cast, got, total), got == total,
          str([label for _k, label, ok, _d in rows if not ok]))
check("the format is judged by 16 checks", len(stl.checks_for(bank, "sitcom")) == 16,
      str(len(stl.checks_for(bank, "sitcom"))))

print()
print("=== each new check fails when you break exactly its thing ===")


def gate(cast="kitten_and_mother", script=None, spec_patch=None):
    scenes = story(cast, script)
    for scene in scenes:
        if spec_patch:
            scene["spec"].update(spec_patch)
    return {key: passed for key, _l, passed, _d
            in stl.lint(bank, scenes, fmt="sitcom", seconds=15)}

# cast: strip a member out of the subject.
check("cast fails when a character vanishes from the subject",
      not gate(spec_patch={"subject": "one ginger kitten alone"})["cast"])
# scale: keep both cats, drop the size sentence.
check("scale fails when the size gap is not stated",
      not gate(spec_patch={"extra": ["visible individual fur strands"]})["scale"])
# captions: blank one.
no_caption = {k: dict(v) for k, v in SCRIPT.items()}
no_caption["reset"]["caption"] = ""
check("captions fails when a scene has none", not gate(script=no_caption)["captions"])
# safety: unsoftened staging.
unsafe = {k: dict(v) for k, v in SCRIPT.items()}
unsafe["discipline"]["foil_action"] = "swatting the kitten off the table"
check("safety fails on unsoftened contact", not gate(script=unsafe)["safety"])
unsafe2 = {k: dict(v) for k, v in SCRIPT.items()}
unsafe2["hook"]["lead_action"] = "batting a knife off the kitchen counter"
check("safety fails on a hazard prop", not gate(script=unsafe2)["safety"])

print()
print("=== the solo cast relaxes only what it must, and says so ===")
rows = {key: detail for key, _l, _p, detail
        in stl.lint(bank, story("tommy"), fmt="sitcom", seconds=15)}
check("scale explains its trivial pass", "nothing to be in scale with" in rows["scale"],
      rows["scale"])
check("pair explains its trivial pass", "one character on screen" in rows["pair"],
      rows["pair"])
check("cast still holds the solo cat to its token", "tabby" in rows["cast"], rows["cast"])
check("tommy's foil is offscreen",
      bs.cast_members(bank, "tommy")[1].get("offscreen") is True)
check("and is excluded from the on-screen members",
      len(bs.cast_members(bank, "tommy", onscreen_only=True)) == 1)

print()
print("=== five audio layers, every one gated ===")
sound_bank = sl.load_bank()
pet_bank = bps.load_bank()
scenes = story()
sheets = bsd.story_sound(
    sound_bank, scenes, subject="the kitten",
    extra_for=lambda i, s: bps.extra_layers(pet_bank, sound_bank, s.get("beat", ""), seed=i))
by_beat = {scenes[i]["beat"]: sheets[i]["layers"] for i in range(len(scenes))}
check("the discipline beat has 5 layers", len(by_beat["discipline"]) == 5,
      str([l["layer"] for l in by_beat["discipline"]]))
check("the reset beat has 5 layers", len(by_beat["reset"]) == 5,
      str([l["layer"] for l in by_beat["reset"]]))
check("a plain beat has 4", len(by_beat["hook"]) == 4,
      str([l["layer"] for l in by_beat["hook"]]))
check("every layer of every beat passes sound_lint",
      all(layer["passed"] for sheet in sheets for layer in sheet["layers"]),
      str([l["text"] for s in sheets for l in s["layers"] if not l["passed"]][:2]))
check("the vocal layer sits right after ambience",
      [l["layer"] for l in by_beat["hook"]][:2] == ["ambience", "vocal"])
check("the snap comes from sound_bank's transition theme, not a copy",
      bps.snap_for(sound_bank, 0, pet_bank) in
      [r["text"] for r in sl.by_theme(sound_bank, "transition")])
check("the offscreen foil gets hand sounds, not cat sounds",
      "hand" in bps.vocal_for(pet_bank, "discipline", "foil", 0, offscreen=True))

# Real bug, caught by hand rather than by this suite the first time: `who`
# defaulted to "lead" everywhere and nothing ever overrode it, so the foil's
# own vocabulary - the warning chirrup, the stern lecture - was composed into
# the bank and never once reachable. story_bank's own `must_do` says the FOIL
# acts on discipline ("one economical correction from the foil") and on
# lecture ("the mother says her piece" - the caption is her line), so those
# two beats must default to the foil's voice, not the kitten's.
foil_lines = set()
for beat, rows in pet_bank["vocalisations"]["foil"].items():
    foil_lines.update(rows)
lead_lines = set()
for beat, rows in pet_bank["vocalisations"]["lead"].items():
    lead_lines.update(rows)
check("voice_for_beat defaults discipline and lecture to the foil",
      bps.voice_for_beat(pet_bank, "discipline") == "foil"
      and bps.voice_for_beat(pet_bank, "lecture") == "foil")
check("...and hook/tantrum/reset stay the lead's",
      all(bps.voice_for_beat(pet_bank, b) == "lead"
          for b in ("hook", "tantrum", "reset")))
check("extra_layers actually plays the foil on discipline (no who= override)",
      next(l for l in by_beat["discipline"] if l["layer"] == "vocal")["text"] in foil_lines)
check("extra_layers actually plays the foil on lecture",
      next(l for l in by_beat["lecture"] if l["layer"] == "vocal")["text"] in foil_lines)
check("and the lead still owns the hook", not lead_lines.isdisjoint(
      {next(l for l in by_beat["hook"] if l["layer"] == "vocal")["text"]}))

print()
print("=== every premise composes a passing post ===")
social_bank = bsoc.load_bank()
bad = []
for key, row in bs.premises(bank).items():
    pack = bsoc.compose_social(social_bank, row["seed"], ["And STAY off the phone."],
                               short=row["short"])
    got, total = socl.score(socl.lint(social_bank, pack))
    if got != total:
        bad.append(key)
check("all 50 premises give a 6/6 pack", not bad, str(bad[:4]))
check("every premise carries a short form",
      all(r["short"] and r["seed"] for r in bs.premises(bank).values()))
check("the short form is shorter than the seed",
      all(len(r["short"]) <= len(r["seed"]) for r in bs.premises(bank).values()))

pack = bsoc.compose_social(social_bank, "the kitten will not hand over the tiny phone",
                           ["And STAY off the phone."], short="the tiny phone")
check("the hashtag conflict is recorded, not resolved away",
      "Four at most" in social_bank["hashtag_conflict"]["course_advice"])
check("and the linter reports it on a PASS",
      "Four at most" in dict(
          (k, d) for k, _l, _p, d in socl.lint(social_bank, pack))["tag_count"])
check("a duplicated hashtag is caught",
      not socl.check_hashtag_form(social_bank, {"hashtags": ["#cat", "#cat"]})[0])
check("a malformed hashtag is caught",
      not socl.check_hashtag_form(social_bank, {"hashtags": ["cat dog"]})[0])
check("claim language is caught",
      not socl.check_no_claims(social_bank, {"caption": "guaranteed to go viral",
                                             "titles": []})[0])

print()
print("=== THE OTHER TWO FORMATS ARE UNTOUCHED ===")
# The assertion this file exists for.
story_scenes = bs.compose_story(
    bank, {"subject": "a ginger tabby cat", "setting": "a kitchen at night", "seed": 1},
    fmt="story", arc="classic", seconds=30, reference="r.png", image_bank=image_bank,
    script={k: {"caption": "c{}".format(i), "narration": "n{}".format(i),
                "action": "doing thing {}".format(i)}
            for i, k in enumerate(bs.scene_keys(bank, "classic", 30, 5, "story"))})
rows = stl.lint(bank, story_scenes, fmt="story", seconds=30, arc="classic",
                image_bank=image_bank)
got, total = stl.score(rows)
check("story still scores 13/13", (got, total) == (13, 13),
      "{}/{} {}".format(got, total, [l for _k, l, ok, _d in rows if not ok]))

trade_scenes = bs.compose_story(
    bank, {"subject": "two cats - a grey tabby and a ginger tom", "seed": 1},
    fmt="trade", arc="shift", seconds=20, trade="construction", reference="r.png",
    image_bank=image_bank,
    script={k: {"task": "task {}".format(i), "mishap": "mishap {}".format(i)}
            for i, k in enumerate(bs.scene_keys(bank, "shift", 20, 10, "trade"))})
rows = stl.lint(bank, trade_scenes, fmt="trade", seconds=20, arc="shift",
                image_bank=image_bank)
got, total = stl.score(rows)
check("trade still scores 12/12", (got, total) == (12, 12),
      "{}/{} {}".format(got, total, [l for _k, l, ok, _d in rows if not ok]))
check("trade's task/mishap join still reads 'until'",
      " until " in trade_scenes[0]["spec"]["action"], trade_scenes[0]["spec"]["action"][:40])
check("neither runs the safety gate",
      "safety" not in stl.checks_for(bank, "story")
      and "safety" not in stl.checks_for(bank, "trade"))
check("DEFAULT_CHECKS excludes all four new checks",
      not set(stl.DEFAULT_CHECKS) & {"cast", "scale", "captions", "safety"},
      str(sorted(set(stl.DEFAULT_CHECKS) & {"cast", "scale", "captions", "safety"})))
check("story and trade sheets still have exactly three layers",
      all(len(sheet["layers"]) == 3
          for sheet in bsd.story_sound(sound_bank, story_scenes, subject="the cat")))

print()
print("=== the latent bugs this format surfaced are fixed ===")
# cut_between read the top-level cuts map, so trade had to duplicate it.
check("cut_between reads the FORMAT's cuts map",
      bs.cut_between(bank, scenes[0], scenes[1]) == "hard cut")
check("and the sitcom's own J cut is reachable",
      bs.cut_between(bank, {"beat": "tantrum", "format": "sitcom"},
                     {"beat": "discipline"}, fmt="sitcom") == "J cut")
# check_shot_repeats read bank["beats"], so a format's own beats were invisible.
double = bs.compose_story(bank, {"seed": 3}, fmt="sitcom", cast="kitten_and_mother",
                          arc="double", seconds=18, reference="r.png",
                          image_bank=image_bank, script=SCRIPT)
check("a repeated beat is visible to check_shot_repeats",
      len([s for s in double if s["beat"] == "tantrum"]) == 2,
      str([s["beat"] for s in double]))

print()
print("=== the CLI: --cast and --premise actually exist ===")
# Real bug, caught by hand: I built apply_cast()/casts()/premises() into the
# library and wrote "python tools/build_story.py --format sitcom --cast
# tommy --premise <seed>" into my own plan's verification section, but never
# added --cast or --premise to argparse. The command in the plan could not
# run.
TOOL = ROOT / "tools" / "build_story.py"


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--format", "sitcom", "--cast", "tommy", "--premise", "screentime", "--no-write"])
check("the exact command from the plan's verification section runs",
      p.returncode == 0, (p.stdout + p.stderr)[:200])
check("and the premise note prints",
      "the kitten will not hand over the tiny phone" in p.stderr, p.stderr[:160])

p = run(["--format", "sitcom", "--cast", "kitten_and_mother", "--no-write"])
check("the pair cast runs with no --subject at all", p.returncode == 0, p.stderr[:160])

p = run(["--format", "sitcom", "--no-write"])
check("no --spec/--subject/--cast still exits with a clear error",
      p.returncode != 0 and "--cast" in p.stderr, p.stderr[:160])

p = run(["--format", "sitcom", "--cast", "not-a-real-cast", "--no-write"])
check("an unknown --cast is rejected", p.returncode != 0, p.stderr[:160])

p = run(["--list"])
check("--list names the casts", "kitten_and_mother" in p.stdout and "tommy" in p.stdout)
check("--list names the premises", "screentime" in p.stdout, p.stdout[-400:])

print()
print("=== the GUI switches formats cleanly ===")
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
from ui.views.cats import CatsView  # noqa: E402

view = CatsView(image_bank)
view.resize(1100, 820)
view.show()
app.processEvents()
check("a Social tab exists",
      "Social" in [view.tabs.tabText(i) for i in range(view.tabs.count())])
view.format.setCurrentIndex(view.format.findData("sitcom"))
app.processEvents()
check("the arcs rebuilt to the sitcom's own",
      [view.arc.itemData(i) for i in range(view.arc.count())] == ["curve", "tight", "double"])
check("clip length followed the format", view.clip.value() == 3, str(view.clip.value()))
check("runtime followed the format", view.seconds.value() == 15, str(view.seconds.value()))
check("the Cast row is shown", view.form_rows["Cast"][1].isVisible())
check("the Premise row is shown", view.form_rows["Premise"][1].isVisible())
check("the Job row is hidden", not view.form_rows["Job"][1].isVisible())
check("the cast label is plural", view.form_rows["The cat"][0].text() == "The cats")
check("five scenes planned", len(view.scenes) == 5, str(len(view.scenes)))
check("the sitcom scene gets five sound layers on the discipline beat",
      len(view._scene_sound_layers(2)) == 5,
      str([l["layer"] for l in view._scene_sound_layers(2)]))

# Real bug, caught by hand rather than by this suite the first time:
# base_spec() unconditionally set spec["subject"] = "a cat" whenever the
# Subject field was blank, and apply_cast() in build_story.py only fills that
# key when it is ABSENT or falsy - "a cat" is neither. So through the actual
# GUI, with the field left blank exactly as its own placeholder instructs, the
# cast's subject was dead: every sitcom episode silently composed as a single
# generic cat, and the "Two cats in frame"/"The cast turns up" checks failed
# on a brand-new story before a user had typed anything. Direct calls to
# bs.compose_story() never caught this because they never went through
# base_spec() at all.
check("with the Subject field left blank, the cast fills it in",
      view.subject.text() == "" and
      view.scenes[0]["spec"]["subject"].startswith("two ginger cats"),
      repr(view.scenes[0]["spec"]["subject"][:50]))
gate = {k: ok for k, _l, ok, _d in stl.lint(view.story_bank, view.scenes, fmt="sitcom",
                                            seconds=view.seconds.value())}
check("...and the pair/cast/scale checks pass on that blank-field story",
      gate["pair"] and gate["cast"] and gate["scale"], str(gate))

view.cast.setCurrentIndex(view.cast.findData("tommy"))
app.processEvents()
check("switching cast re-fills the still-blank subject",
      view.scenes[0]["spec"]["subject"].startswith("a slender adult grey mackerel tabby"),
      repr(view.scenes[0]["spec"]["subject"][:50]))
view.subject.setText("a plain orange cat")
app.processEvents()
check("a hand-typed subject overrides the cast",
      view.scenes[0]["spec"]["subject"] == "a plain orange cat",
      repr(view.scenes[0]["spec"]["subject"]))
view.subject.setText("")
app.processEvents()
view.premise.setCurrentIndex(1)
app.processEvents()
check("picking a premise fills the Idea box", bool(view.idea.text()), view.idea.text()[:40])
check("and the post composes", "HASHTAGS" in view.social_box.toPlainText())
check("the post's gate has six rows", view.social_gate.tree.topLevelItemCount() == 6,
      str(view.social_gate.tree.topLevelItemCount()))

view.format.setCurrentIndex(view.format.findData("trade"))
app.processEvents()
check("switching back to trade hides the Cast row",
      not view.form_rows["Cast"][1].isVisible())
check("and shows the Job row", view.form_rows["Job"][1].isVisible())
check("and trade scenes get three sound layers again",
      len(view._scene_sound_layers(0)) == 3,
      str([l["layer"] for l in view._scene_sound_layers(0)]))

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL SITCOM CHECKS PASSED")

sys.exit(1 if fails else 0)
