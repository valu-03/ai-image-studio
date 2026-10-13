"""Face detail, lived-in evidence and timed video beats, through the real MainWindow.

test_face_detail.py / test_evidence_bank.py / test_motion.py cover the tools
directly; this is the wiring a user actually touches:

  * Compose's "Face micro-detail" toggle is on by default, follows the shot
    (no pores at full body), adds nothing to a product, keeps 8/8, and the
    toggles are preferences - load_spec() never flips them;
  * "Lived-in details (auto)" adds evidence for the subject's kind, and an
    explicit pick from Look > Evidence REPLACES it rather than stacking;
  * an explicit pick survives a save/load round-trip, an auto pick is never
    frozen into one;
  * Videos' Timing / Ends on fields reach the Kling prompt and its gate.

Offscreen, no network.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_EMPTY = Path(tempfile.gettempdir()) / "aivs-evidence-gui-empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_HISTORY_FILE",
                      str(Path(tempfile.gettempdir()) / "aivs-evidence-gui-history.jsonl"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


win = MainWindow(ThemeManager(app))
win.show()
app.processEvents()
cv = win.compose_view
ed = cv.editor


import build_prompt as bp  # noqa: E402


def resolved():
    """The overrides compose() will actually use - the details are flags on
    the form's spec and are resolved at compose time."""
    return bp.apply_subject_detail(ed.spec()).get("overrides") or {}


def prompt_for(spec):
    ed.load_spec(spec)
    cv.rebuild()
    return cv.prompt_text()


print("=== FACE MICRO-DETAIL ===")
check("on by default", ed.face_detail.isChecked())
check("lived-in details off by default", not ed.lived_in.isChecked())
portrait = prompt_for({"subject": "a woman in her thirties", "seed": 2, "shot": "portrait"})
check("a portrait gets zonal skin detail", resolved().get("face_detail"), str(resolved()))
check("...and it is in the prompt", resolved()["face_detail"][0] in cv.prompt_text())
check("and still scores 8/8", cv.passing, cv.lint.badge.text())
wide = prompt_for({"subject": "a woman in her thirties", "seed": 2, "shot": "environmental"})
check("a wide shot asks for no pores", "pore" not in " ".join(resolved()["face_detail"]))
close = prompt_for({"subject": "a woman in her thirties", "seed": 2,
                    "shot_custom": "extreme close-up headshot on a Canon EOS R5"})
check("an extreme close-up gets pore-level detail",
      any(k in " ".join(resolved()["face_detail"]) for k in ("pore", "peach fuzz", "eyebrow", "eyelash", "iris")),
      str(resolved()["face_detail"]))
prompt_for({"subject": "a 250ml amber shampoo bottle on marble", "seed": 2, "shot": "product-demo"})
check("a product gets no face detail", "face_detail" not in resolved())
ed.face_detail.setChecked(False)
prompt_for({"subject": "a woman in her thirties", "seed": 2, "shot": "portrait"})
check("off means off", "face_detail" not in resolved() and "face_detail" not in ed.spec())
check("load_spec does not flip a toggle back on", not ed.face_detail.isChecked())
ed.face_detail.setChecked(True)

# Variants copies the form's spec and changes the shot or seed; the details
# must follow the VARIANT, not the form (a full-body angle must not carry a
# close-up's pores, and two seeds must not share one set of details).
base = {"subject": "a woman in her thirties", "seed": 2,
        "shot_custom": "extreme close-up headshot on a Canon EOS R5"}
prompt_for(base)
wide_variant = dict(ed.spec(), shot="environmental", shot_custom="")
wide_detail = bp.apply_subject_detail(wide_variant)["overrides"]["face_detail"][0]
check("a Variants angle gets its own shot's tier, not the form's", "pore" not in wide_detail, wide_detail)
seeds = {bp.apply_subject_detail(dict(ed.spec(), seed=s))["overrides"]["face_detail"][0] for s in range(6)}
check("Variants seeds get different details", len(seeds) > 1, str(len(seeds)))

print()
print("=== LIVED-IN EVIDENCE ===")
ed.lived_in.setChecked(True)
prompt_for({"subject": "a ginger tabby cat on a sofa", "seed": 3})
auto = resolved().get("evidence_auto", [""])[0]
check("auto picks animal evidence for a cat",
      auto and any(word in auto for word in ("fur", "whisker", "nose", "paws", "hairs")), auto)
check("auto evidence reaches the prompt", auto and auto in cv.prompt_text())

win.go_to("evidence")
ev = win.evidence_view
check("Look > Evidence is reachable", win.look_view.tabs.currentWidget() is ev)
ev.tabs.setCurrentIndex(1)
ev.set_kind("animal")
ev.checks[("animal", "bent-whisker")].setChecked(True)
app.processEvents()
check("Build composes the ticked detail", "whisker bent" in ev.composed.text(), ev.composed.text())
ev.apply_to_compose()
app.processEvents()
cv.rebuild()
overrides = resolved()
check("apply routed back to Images", win.stack.currentWidget() is win.images_view)
check("an explicit pick replaces the auto pick, never stacks with it",
      overrides.get("evidence") and "evidence_auto" not in overrides, str(overrides))
check("the pick is in the prompt", "whisker bent" in cv.prompt_text())
check("and the prompt still scores 8/8", cv.passing, cv.lint.badge.text())

saved = ed.spec()
ed.set_evidence_override("")
ed.load_spec(saved)
check("an explicit pick survives save/load",
      (ed.spec().get("overrides") or {}).get("evidence") == saved["overrides"]["evidence"])
ed.set_evidence_override("")
ed.lived_in.setChecked(False)
ed.load_spec({"subject": "a man", "seed": 0, "overrides": {"evidence_auto": ["stale auto"]}})
check("a saved AUTO pick is never resurrected as an explicit one",
      "stale auto" not in cv.prompt_text() and not (ed.spec().get("overrides") or {}).get("evidence"))

print()
print("=== MATCH LIGHT TO THE SCENE ===")
check("on by default", ed.match_light.isChecked())
prompt_for({"subject": "a woman in her thirties", "seed": 4,
            "setting": "a cocktail bar at night, wooden counter"})
check("the spec carries the flag", ed.spec().get("scene_lighting") is True)
check("the note names the scene's source", "pendant lamps" in ed.light_note.text(),
      ed.light_note.text())
check("the prompt names it too", "pendant lamps over the bar" in cv.prompt_text())
check("the auto pick never lights a bar at night with daylight",
      not any(t in cv.prompt_text() for t in ("golden hour sunlight", "harsh midday sunlight",
                                               "soft natural daylight", "overcast daylight")))
check("still 8/8", cv.passing, cv.lint.badge.text())
ed.lighting.setCurrentText("harsh midday sunlight")
app.processEvents()
cv.rebuild()
check("an explicit pick that fights the setting gets a heads-up",
      ed.light_note.text().startswith("Heads up"), ed.light_note.text())
check("...and is still used", "harsh midday sunlight" in cv.prompt_text())
ed.lighting.setCurrentIndex(0)
win.go_to("lighting")
app.processEvents()
check("the Lighting section shows what Compose takes from the scene",
      "pendant lamps" in win.lighting_view.scene_note.text(), win.lighting_view.scene_note.text())
win.go_to("images")
ed.match_light.setChecked(False)
cv.rebuild()
check("off: no flag, no scene light in the prompt",
      "scene_lighting" not in ed.spec() and "pendant lamps" not in cv.prompt_text())
ed.match_light.setChecked(True)

print()
print("=== WEIGHT & CONTACT, MATERIALS IN THIS SCENE ===")
import build_material as bmt  # noqa: E402

check("both on by default", ed.contact_detail.isChecked() and ed.material_detail.isChecked())
prompt_for({"subject": "a woman in her thirties", "seed": 1,
            "action": "sitting on a sofa holding a coffee mug", "wardrobe": "a wool sweater"})
check("the spec carries both flags",
      ed.spec().get("contact_detail") is True and ed.spec().get("material_detail") is True)
check("the note names what was picked up",
      "sofa" in ed.physical_note.text() and "wool" in ed.physical_note.text(), ed.physical_note.text())
check("the prompt gets the cushion", "cushion dipping" in cv.prompt_text())
check("...and the knit", "fuzzy halo" in cv.prompt_text())
check("still 8/8", cv.passing, cv.lint.badge.text())
generic = bmt.generic_phrase(bmt.load_bank())
ed.lighting.setCurrentText("soft window light, " + generic)
app.processEvents()
cv.rebuild()
check("Lighting's generic material sentence is replaced by the specific lines",
      generic not in cv.prompt_text() and "soft window light" in cv.prompt_text())
ed.material_detail.setChecked(False)
cv.rebuild()
check("...and comes back when the materials toggle is off", generic in cv.prompt_text())
ed.lighting.setCurrentIndex(0)
ed.contact_detail.setChecked(False)
for box in (ed.snapshot, ed.background_life, ed.moment):
    box.setChecked(False)
cv.rebuild()
check("off: no flags, nothing added",
      "contact_detail" not in ed.spec() and "material_detail" not in ed.spec()
      and "cushion dipping" not in cv.prompt_text() and not ed.physical_note.text())
ed.load_spec({"subject": "a man", "seed": 0})
check("the toggles are preferences - load_spec() never flips them",
      not ed.contact_detail.isChecked() and not ed.material_detail.isChecked())
ed.contact_detail.setChecked(True)
ed.material_detail.setChecked(True)
for box in (ed.snapshot, ed.background_life, ed.moment):
    box.setChecked(True)

print()
print("=== PHONE SNAPSHOT, UNSTAGED BACKGROUND, THE MOMENT ===")
check("all three on by default... and back on",
      ed.snapshot.isChecked() and ed.background_life.isChecked() and ed.moment.isChecked())
prompt_for({"subject": "a chubby ginger street cat", "seed": 4,
            "action": "sitting next to an empty metal bowl, staring at it",
            "setting": "a busy shopping street pavement, overcast day"})
spec_now = ed.spec()
check("the spec carries the three flags",
      all(spec_now.get(f) is True for f in ("snapshot", "background_life", "moment")))
check("the note names the place and the moment",
      "Background: street" in ed.physical_note.text() and "Moment: stare" in ed.physical_note.text(),
      ed.physical_note.text())
text = cv.prompt_text()
check("the phone camera replaces any cinema camera", "iPhone-style photo" in text
      and not any(w in text for w in ("ARRI", "RED V-Raptor", "Sony Venice", "Hasselblad")))
check("a street cat is a cat: no skin or pores, coat detail present",
      "skin pores" not in text and "fur" in text)
check("still 8/8 (judged as an animal)", cv.passing, cv.lint.badge.text())
ed.shot.setCurrentText("portrait")
app.processEvents()
cv.rebuild()
check("a chosen shot wins: no phone line", "phone held low" not in cv.prompt_text()
      and "passer-by who crouched" not in cv.prompt_text())
ed.shot.setCurrentIndex(0)

print()
print("=== VIDEOS: TIMED BEATS ===")
vv = win.videos_view
win.go_to("videos")
# Timed "0-3s:" beats and their gate checks belong to the tagged template.
vv.write_as.setCurrentIndex(vv.write_as.findData("tagged"))
ed.load_spec({"subject": "a woman in a cafe", "seed": 0,
              "action": "lifts the cup, then glances up at the lens"})
movement_item = None
for i in range(vv.tree.topLevelItemCount()):
    parent = vv.tree.topLevelItem(i)
    if parent.childCount():
        movement_item = parent.child(0)
        break
vv.tree.setCurrentItem(movement_item)
app.processEvents()
check("picking a movement drafts the timing from the Action",
      "0-" in vv.timing_field.toPlainText() and "glances up" in vv.timing_field.toPlainText(),
      vv.timing_field.toPlainText())
check("and an end state", bool(vv.ends_on_field.text().strip()))
check("the beats reach the Kling prompt", "ENDS ON:" in vv.prompt and "0-" in vv.prompt, vv.prompt[:160])
names = [vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())]
check("the gate shows the beat checks", "Beats cover the clip" in names, str(names))
vv.duration.setValue(8)
app.processEvents()
bad = [vv.checks.topLevelItem(i) for i in range(vv.checks.topLevelItemCount())
       if vv.checks.topLevelItem(i).text(1) == "Beats cover the clip"]
check("lengthening the clip flags beats that no longer cover it",
      bad and bad[0].text(0) == "!", bad[0].text(2) if bad else "")
vv.draft_timing()
app.processEvents()
good = [vv.checks.topLevelItem(i) for i in range(vv.checks.topLevelItemCount())
        if vv.checks.topLevelItem(i).text(1) == "Beats cover the clip"]
check("redrafting fits the new length", good and good[0].text(0) == "OK", good[0].text(2) if good else "")
vv.timing_field.setPlainText("")
vv.ends_on_field.setText("")
app.processEvents()
check("clearing the timing gives the plain untimed prompt back",
      "ENDS ON" not in vv.prompt and vv.checks.topLevelItemCount() >= 7)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL EVIDENCE GUI CHECKS PASSED")
