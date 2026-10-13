"""video_realism_bank.json + build_motion's locked-off camera, real motion and phone look.

Measured from a viral one-take AI cat clip (see the bank's `source`): the
camera never moves, only the animals do, their bodies stay planted, tails and
fur follow through, and the pace is real time with a ramp. What has to hold:

  * the locked-off camera is the Cats trade format's own wording, merged into
    the motion bank without touching the hash-pinned motion_bank.json;
  * real_motion_line() fits the subject's kind and the camera (still vs
    moving background), and none of its phrases trips a motion_lint rule;
  * adding it never costs a lint check on any of the 41 movements;
  * the phone style carries no cinema/film-camera words;
  * compose() no longer drops the Subject on a place-framing move;
  * with the options off, compose() and assemble_template() are unchanged;
  * photoreal Cats clips carry the real-motion line, stylised ones do not;
  * the Videos tab: locked-off listed, both boxes on, both reach the prompt.

Offscreen Qt for the last part, no network.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_motion as bm  # noqa: E402
import build_story as bs  # noqa: E402
import motion_lint as ml  # noqa: E402

BANK = bm.load_bank()
REALISM = bm.load_realism()
CATS = "a ginger cat and a grey cat holding a mouse"
SPEC = {"subject": CATS, "action": "the ginger cat tickles the mouse with a feather",
        "setting": "a back alley by a stained concrete wall"}

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def failed(prompt, key):
    return {name for name, ok, _ in ml.lint(prompt, BANK, key)[0] if not ok}


print("=== THE LOCKED-OFF CAMERA ===")
with (ROOT / "tools" / "motion_bank.json").open(encoding="utf-8") as fh:
    raw = json.load(fh)
check("motion_bank.json itself is untouched (still 40, no locked-off)",
      len(raw["movements"]) == 40 and "locked-off" not in raw["movements"])
check("load_bank() merges it in", "locked-off" in BANK["movements"] and len(BANK["movements"]) == 41)
trade = bs.load_bank()["formats"]["trade"]["camera"]
lock = BANK["movements"]["locked-off"]
check("same lead as the Cats Working-cats takes", lock["lead"] == trade["lead"])
check("...and the same detail, plus who moves", lock["detail"].startswith(trade["detail"]))
prompt, _ = bm.compose(BANK, "locked-off", SPEC)
check("a locked-off prompt passes every motion check", not failed(prompt, "locked-off"),
      str(failed(prompt, "locked-off")))
check("...leads with it and keeps the cats",
      prompt.startswith("locked-off camera holding on " + CATS))

print()
print("=== THE SUBJECT IS NEVER DROPPED ===")
wide, _ = bm.compose(BANK, "wide-static", SPEC)
check("wide static keeps the Subject and Action (it used to drop both)",
      CATS in wide and "tickles the mouse" in wide, wide[:160])
check("...after the place it frames", wide.index("back alley") < wide.index(CATS))
no_setting, _ = bm.compose(BANK, "wide-static", {"subject": CATS})
check("with no Setting the Subject follows the lead", no_setting.startswith(
    BANK["movements"]["wide-static"]["lead"] + " " + CATS))

print()
print("=== REAL MOTION ===")
cat_line = bm.real_motion_line(BANK, CATS, "locked-off")
check("cats get planted bodies, paws and tails", "paws" in cat_line and "tails" in cat_line, cat_line)
check("a still camera: the background does not move", REALISM["real_motion"]["background_still"] in cat_line)
moving = bm.real_motion_line(BANK, CATS, "orbit-360")
check("a moving camera: the background stays solid instead",
      REALISM["real_motion"]["background_moving"] in moving
      and REALISM["real_motion"]["background_still"] not in moving)
human = bm.real_motion_line(BANK, "a woman in her thirties", "handheld")
check("a person gets hair and clothing follow-through", "hair and loose clothing" in human, human)
place = bm.real_motion_line(BANK, "a quiet street at night", "locked-off")
check("a place gets only tempo and background",
      "planted" not in place and REALISM["real_motion"]["tempo"] in place, place)
check("real time, never slow motion", "never slow motion" in cat_line)

phrases = [v for group in ("planted", "follow_through") for v in REALISM["real_motion"][group].values()]
phrases += [REALISM["real_motion"][k] for k in ("tempo", "background_still", "background_moving")]
check("no phrase chains actions (motion_lint rule 6)",
      not [p for p in phrases if any(m in " " + p + " " for m in ml.CHAIN_MARKERS)])
check("no phrase names a camera move a locked-off camera would contradict",
      not [p for p in phrases if any(w in p for w in ("tracking", "orbits", "dolly", "crane"))])

cost = []
for key in BANK["movements"]:
    spec = dict(SPEC)
    before = failed(bm.compose(BANK, key, spec)[0], key)
    after = failed(bm.compose(BANK, key, spec, real_motion=True, phone=True)[0], key)
    if after - before:
        cost.append((key, sorted(after - before)))
check("41 movements: real motion + phone look never cost a lint check", not cost, str(cost[:3]))

print()
print("=== PHONE LOOK ===")
phone = bm.phone_style(BANK)
check("no cinema or film-camera words", not any(
    re.search(r"\b" + w + r"\b", phone.lower())
    for w in ("cinematic", "film", "16mm", "35mm", "dslr", "grade")), phone)
p_on, _ = bm.compose(BANK, "locked-off", SPEC, phone=True)
check("compose(phone=True) swaps the preset for it", phone in p_on and not any(
    preset in p_on for preset in BANK["style_presets"]))

print()
print("=== OFF MEANS UNCHANGED ===")
for key in ("locked-off", "orbit-360", "handheld"):
    check("compose({}) with the options off equals the default".format(key),
          bm.compose(BANK, key, SPEC)[0]
          == bm.compose(BANK, key, SPEC, real_motion=False, phone=False)[0])
args = (BANK, "close-up", CATS, "tickles the mouse", "locked-off camera holding on", "phone")
check("assemble_template() with no real_motion is unchanged",
      bm.assemble_template(*args) == bm.assemble_template(*args, real_motion=""))
check("...and with it, the line lands before the style",
      bm.assemble_template(*args, real_motion=cat_line).index(cat_line)
      < bm.assemble_template(*args, real_motion=cat_line).index(", phone,"))

print()
print("=== CATS CLIPS ===")
story = bs.load_bank()
base = {"subject": "a ginger tabby cat", "action": "steals a sausage off the counter",
        "setting": "a small kitchen"}
real = bs.compose_story(story, base, style="photoreal")
styl = bs.compose_story(story, base, style="stylised")
motions = [sc.get("motion_prompt", "") for sc in real if sc.get("motion_prompt")]
check("photoreal clips carry the real-motion line",
      motions and all("never slow motion" in m for m in motions), str(len(motions)))
check("stylised clips do not", not any("never slow motion" in sc.get("motion_prompt", "") for sc in styl))
trade = bs.compose_story(story, base, style="photoreal", fmt="trade", trade="construction")
check("Working-cats takes (locked off) carry it too, with a still background", all(
    "never slow motion" in sc["motion_prompt"] and REALISM["real_motion"]["background_still"] in sc["motion_prompt"]
    for sc in trade if sc.get("motion_prompt")))

print()
print("=== ONE-TAKE STORY, STATIC SHOT, OPTIONAL NEGATIVES ===")
VIRAL = ("Static shot, the tabby cat is initially reclining on the bed, watching a smartphone held in "
         "its paws. The cat shifts its gaze down toward the ceramic bowl of chips on the mattress, "
         "carefully reaching out with its paw to grab a single chip and eat it with focus. Suddenly, a "
         "human hand enters from out of frame, quickly reaching out to grab the bowl of chips, taking it "
         "away, soon after the same human hand reaches from out of frame and puts one bed a bowl filled "
         "with broccoli and salad. The cat lowers its paw into the new bowl, picks up a broccoli floret, "
         "and inspects it intensely with a disgusted expression. Displeased with the healthier choice, "
         "the cat violently kicks the bowl away, sending it sliding across the sheets. Subtle, fluid "
         "motion.")
checks = ml.lint(VIRAL, BANK, None, seconds=10, negatives=False)[0]
check("the user's 150k-view prompt, verbatim, gets full marks with negatives optional",
      all(ok for _n, ok, _d in checks), str([n for n, ok, _d in checks if not ok]))
check("...it fails only the guard when negatives are required",
      {n for n, ok, _d in ml.lint(VIRAL, BANK, None, seconds=10)[0] if not ok}
      == {"Negative guard present"})
for opener in ("Static shot, a cat", "static wide shot of a street", "Fixed camera, a dog",
               "Tripod shot, a woman", "Locked-off, a man"):
    check("{!r} counts as a camera lead".format(opener), ml.leads_with_camera(opener, BANK) == "static")
check("'Static shots' of a different word do not", ml.leads_with_camera("Statically, a cat", BANK) is None)
check("a still camera needs the SUBJECT to move", not dict(
    (n, ok) for n, ok, _d in ml.lint("Static shot, a cat on a bed in a quiet room.", BANK)[0])
    ["Describes motion"])

beats = bm.story_beats("0-3s: the cat eats a chip\n3-6s: Suddenly, a hand takes the bowl\n"
                       "6-10s: the cat kicks the bowl away")
check("timed beats drop their seconds", beats == ["the cat eats a chip", "Suddenly, a hand takes the bowl",
                                                  "the cat kicks the bowl away"], str(beats))
check("plain lines are beats too", bm.story_beats("one\ntwo\n\nthree") == ["one", "two", "three"])
check("no timing: the Action is the one beat", bm.story_beats("", "strokes the mouse") == ["strokes the mouse"])
story = bm.assemble_story(BANK, "locked-off", "a tabby cat on a bed", beats + ["it walks off"],
                          style=bm.phone_style(BANK))
check("opens 'Static shot, <subject>.'", story.startswith("Static shot, a tabby cat on a bed. "), story[:60])
check("first beat 'Initially', a typed 'Suddenly' kept, last beat 'Finally'",
      "Initially, the cat eats a chip." in story and "Suddenly, a hand takes the bowl." in story
      and "Finally, it walks off." in story, story)
check("a middle beat gets 'Then' or 'Soon after'",
      "Then, the cat kicks the bowl away." in story or "Soon after, the cat kicks the bowl away." in story,
      story)
check("closes on 'Subtle, fluid motion.'", story.endswith("Subtle, fluid motion."))
check("no negatives unless asked", "no warped face" not in story.lower())
check("...and they come as a sentence when asked",
      "No warped face" in bm.assemble_story(BANK, "locked-off", "a cat", ["sits"], negatives=True))
check("one beat gets no time word", "Initially" not in bm.assemble_story(BANK, "locked-off", "a cat", ["sits"]))
check("a moving camera opens on its own lead",
      bm.assemble_story(BANK, "orbit-360", "a cat", ["sits"]).lower().startswith(
          BANK["movements"]["orbit-360"]["lead"].lower()))
full = [n for n, ok, _d in ml.lint(story, BANK, "locked-off", negatives=False)[0] if not ok]
check("an assembled story passes every check", not full, str(full))
tagged_args = (BANK, "close-up", CATS, "tickles", "locked-off camera holding on", "phone")
check("the tagged template is unchanged unless negatives are turned off",
      "no warped face" in bm.assemble_template(*tagged_args)
      and "no warped face" not in bm.assemble_template(*tagged_args, negatives=False))

print()
print("=== THE VIDEOS TAB ===")
_EMPTY = Path(tempfile.gettempdir()) / "aivs-video-realism-empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_HISTORY_FILE",
                      str(Path(tempfile.gettempdir()) / "aivs-video-realism-history.jsonl"))
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow(ThemeManager(app))
win.show()
win.compose_view.editor.load_spec({"subject": CATS, "action": "tickles the mouse with a feather",
                                   "seed": 0})
win.go_to("videos")
app.processEvents()
vv = win.videos_view
item = None
for i in range(vv.tree.topLevelItemCount()):
    parent = vv.tree.topLevelItem(i)
    for j in range(parent.childCount()):
        if parent.child(j).data(0, 256) == "locked-off":   # Qt.ItemDataRole.UserRole
            item = parent.child(j)
check("Locked-off is listed in the movement tree", item is not None)
check("both boxes are on by default", vv.real_motion.isChecked() and vv.phone_look.isChecked())
vv.tree.setCurrentItem(item)
app.processEvents()
check("the default is the one-take story", vv.write_as.currentData() == "story")
check("a still camera opens on 'Static shot'", vv.prompt.startswith("Static shot, "), vv.prompt[:80])
check("negatives are off by default in a story", not vv.negatives.isChecked()
      and "no warped face" not in vv.prompt)
neg_row = [vv.checks.topLevelItem(i) for i in range(vv.checks.topLevelItemCount())
           if vv.checks.topLevelItem(i).text(1) == "Negative guard present"]
check("...and the check says optional, not failed",
      neg_row and neg_row[0].text(0) == "OK" and "optional" in neg_row[0].text(2))
vv.negatives.setChecked(True)
app.processEvents()
check("ticking Negatives adds them", "No warped face" in vv.prompt or "no warped face" in vv.prompt)
vv.negatives.setChecked(False)
vv.timing_field.setPlainText("the ginger cat strokes the mouse with the feather\n"
                             "Suddenly, the mouse wriggles free\nthe grey cat catches it again")
app.processEvents()
check("timing lines become ordered sentences with time words",
      "Initially, the ginger cat strokes" in vv.prompt and "Suddenly, the mouse wriggles free." in vv.prompt
      and "Finally, the grey cat catches it again." in vv.prompt, vv.prompt[:300])
check("...and no second codes", "0-" not in vv.prompt)
vv.timing_field.setPlainText("")
vv.write_as.setCurrentIndex(vv.write_as.findData("tagged"))
app.processEvents()
check("Tagged list switches the negatives back on", vv.negatives.isChecked())
check("the tagged prompt leads with the locked-off camera",
      vv.prompt.startswith("locked-off camera holding on"), vv.prompt[:80])
vv.write_as.setCurrentIndex(vv.write_as.findData("story"))
app.processEvents()
check("the real-motion line reaches the prompt", "never slow motion" in vv.prompt)
check("the Style field is the phone look", vv.style_field.text().startswith(phone))
vv.phone_look.setChecked(False)
app.processEvents()
check("unticking the phone look rewrites Style to a named camera",
      not vv.style_field.text().startswith(phone) and vv.style_field.text())
vv.real_motion.setChecked(False)
app.processEvents()
check("unticking real motion takes the line out", "never slow motion" not in vv.prompt)
vv.real_motion.setChecked(True)
vv.phone_look.setChecked(True)
app.processEvents()
check("the gate is clean on the locked-off prompt",
      all(vv.checks.topLevelItem(i).text(0) in ("OK", "~") for i in range(vv.checks.topLevelItemCount())),
      str([vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())
           if vv.checks.topLevelItem(i).text(0) not in ("OK", "~")]))

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL VIDEO REALISM CHECKS PASSED")
