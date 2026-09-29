"""Relight and Macro insert: the last two CLI-only toolkits, and where they landed.

THE PLAN SAID LOOK. They cannot live there, and this suite pins the reasons so
nobody "restores" them to it later. A Look toolkit builds one PHRASE and Applies
it into a Compose field via `set_X_override()`. These two build whole SHOT LISTS
from a base spec plus a reference image, set spec-level flags no setter can
carry (`lock_scene`, `lock_identity`), and each has its own multi-check linter.
They belong in Images, which already means "everything that produces a still".

The two halves that matter most here:

  * The reference rule is not the same for both, and it is not a constant.
    Every relight set needs a reference - a relight with nothing to relight is
    just Compose. Macro's `full-face` CREATES the face, so it needs none, and
    the view asks `build_macro_insert.needs_reference()` rather than hard-coding
    a set name.

  * Relight's 7/8 is correct and must not be "fixed". An angle shot's composed
    phrase takes the camera slot and can name no capture device, so `camera` is
    legitimately missing. `relight_lint` holds lighting-only shots to 8 and
    angle shots to 7; a suite that demanded 8/8 everywhere would be asserting a
    bug into existence.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import build_macro_insert as bmi  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_relight as brl  # noqa: E402
import realism_lint as rl  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.main_window import NAV_ITEMS, SUBVIEW_ROUTES  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


IMAGE_BANK = bp.load_bank()
SUBJECT = "a woman in her thirties with dark wavy hair and light freckles"
REF = "temp/resources/images/source-photo.png"

theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.compose_view.editor.subject.setPlainText(SUBJECT)
win.compose_view.editor.wardrobe.setText("a cream linen shirt")
win.compose_view.editor.setting.setText("a bright apartment kitchen, mid-morning")
rv = win.images_view.relight
mv = win.images_view.macro


print("=== IMAGES GREW TWO TABS AND DID NOT DISTURB THE OTHER TWO ===")
iv = win.images_view
check("four tabs, in working order",
      [iv.tabs.tabText(i) for i in range(iv.tabs.count())]
      == ["Compose", "Variants", "Relight", "Macro insert"],
      str([iv.tabs.tabText(i) for i in range(iv.tabs.count())]))
check("MainWindow still reaches Compose by name", win.compose_view is iv.compose)
check("...and Variants", win.variants_view is iv.variants)
check("the rail is still ten entries", len(NAV_ITEMS) == 10, str(len(NAV_ITEMS)))
check("both are deep-linkable",
      SUBVIEW_ROUTES.get("relight") == ("images", 2)
      and SUBVIEW_ROUTES.get("macro_insert") == ("images", 3))
check("show_relight / show_macro move the tab",
      (iv.show_relight() or iv.tabs.currentIndex()) == 2)
check("...and macro", (iv.show_macro() or iv.tabs.currentIndex()) == 3)
iv.show_compose()

# `==` not `is`: attribute access on a bound method builds a new object each
# time, so `is` would compare two wrappers around the same function.
check("both read the open character through the same provider Variants uses",
      rv.spec_provider == win.current_spec_bundle
      == mv.spec_provider == win.variants_view.spec_provider)
check("both can reach the photo Compose last produced",
      rv.image_provider is not None and mv.image_provider is not None)


print()
print("=== NEITHER VIEW SPENDS MONEY ===")
for name, view in (("Relight", rv), ("Macro insert", mv)):
    check("{} has no generate signal".format(name),
          not [n for n in dir(view) if "generate" in n.lower()],
          str([n for n in dir(view) if "generate" in n.lower()]))


print()
print("=== RELIGHT NEEDS A REFERENCE; WITHOUT ONE IT REFUSES ===")
rv.compose()
check("no reference composes nothing", rv._shots == [], str(len(rv._shots)))
check("...and the gate says why rather than sitting blank",
      "reference" in rv.gate.detail.text().lower(), rv.gate.detail.text()[:70])
check("the badge is not a false green", rv.gate_badge.text() == "0/0", rv.gate_badge.text())
check("passing is False with nothing composed", not rv.passing)

rv.set_reference(REF)
rv.compose()
check("with a reference it composes the set's four shots", len(rv._shots) == 4,
      str(len(rv._shots)))
check("its own five-check gate is green", rv.gate_badge.text() == "5/5", rv.gate_badge.text())
check("...and passing agrees", rv.passing)
check("one tree row per shot", rv.shot_tree.topLevelItemCount() == 4)


print()
print("=== 7/8 ON AN ANGLE SHOT IS THE GATE WORKING ===")
for shot in rv._shots:
    present, missing, banned, _w, _n = rl.lint(shot["prompt"].lower(), IMAGE_BANK)
    names = {n for n, _c, _h in missing}
    has_angle = any(shot.get(k) for k in ("vertical", "side", "size"))
    floor = 7 if has_angle and names <= {"camera"} else 8
    check("shot {} scores at least its floor of {}".format(shot["index"], floor),
          len(present) >= floor and not banned,
          "{}/8 missing {}".format(len(present), sorted(names)))
check("every shot is scene-locked in its own spec",
      all(s["spec"].get("lock_scene") for s in rv._shots))
check("...and none of them locks identity instead",
      not any(s["spec"].get("lock_identity") for s in rv._shots))
check("the reference rides in every spec",
      all(s["spec"].get("reference") == REF for s in rv._shots))


print()
print("=== THE BATCH INHERITS THE OPEN CHARACTER, UNCHANGED ===")
check("every shot carries Compose's subject",
      all(s["spec"].get("subject") == SUBJECT for s in rv._shots))
check("...and its wardrobe and setting - that is what a scene lock means",
      all(s["spec"].get("wardrobe") == "a cream linen shirt"
          and s["spec"].get("setting") == "a bright apartment kitchen, mid-morning"
          for s in rv._shots))

win.compose_view.editor.subject.setPlainText("a man in his fifties with a grey beard")
rv.compose()
check("editing Compose and recomposing follows the new subject",
      all("grey beard" in s["prompt"] for s in rv._shots))
win.compose_view.editor.subject.setPlainText(SUBJECT)
rv.compose()


print()
print("=== MACRO: STAGE ONE NEEDS NO REFERENCE, STAGE TWO DOES ===")
mv.set_combo.setCurrentIndex(mv.set_combo.findData("full-face-only"))
check("the view agrees full-face needs nothing", mv.reference_problem("full-face-only") == "",
      mv.reference_problem("full-face-only"))
mv.compose()
check("it composes the one shot with no reference at all", len(mv._shots) == 1,
      str(len(mv._shots)))
check("...and that shot sets no identity lock - there is nothing yet to lock to",
      not mv._shots[0]["spec"].get("lock_identity"))
check("its nine-check gate is green", mv.gate_badge.text() == "9/9", mv.gate_badge.text())

mv.set_combo.setCurrentIndex(mv.set_combo.findData("inserts-only"))
mv.set_reference("")
mv.compose()
check("inserts with no reference compose nothing", mv._shots == [], str(len(mv._shots)))
check("...and the refusal names the inserts rather than a set",
      all(word in mv.reference_problem("inserts-only") for word in ("eye", "mouth", "cheek")),
      mv.reference_problem("inserts-only")[:80])
# The rule is asked of the tool, not hard-coded - so it stays right if the bank changes.
check("the view's rule agrees with build_macro_insert.needs_reference()",
      bool(bmi.needs_reference(mv.bank, mv._insert_names("inserts-only")))
      == bool(mv.reference_problem("inserts-only")))

mv.set_reference(REF)
mv.compose()
check("with a reference the three inserts compose", len(mv._shots) == 3, str(len(mv._shots)))
check("every insert locks identity to it",
      all(s["spec"].get("lock_identity") and s["spec"].get("reference") == REF
          for s in mv._shots))
check("...and none of them scene-locks", not any(s["spec"].get("lock_scene")
                                                 for s in mv._shots))
check("the gate is green", mv.gate_badge.text() == "9/9", mv.gate_badge.text())


print()
print("=== MACRO HOLDS A STRICT 8/8, UNLIKE RELIGHT ===")
mv.set_combo.setCurrentIndex(mv.set_combo.findData("beauty-macro"))
mv.compose()
check("the full set is four shots", len(mv._shots) == 4, str(len(mv._shots)))
for shot in mv._shots:
    present, missing, banned, _w, _n = rl.lint(shot["prompt"].lower(), IMAGE_BANK)
    check("{} scores a strict 8/8".format(shot["insert"]),
          len(present) == 8 and not banned,
          "{}/8 missing {}".format(len(present), sorted(n for n, _c, _h in missing)))
check("no shot takes the camera slot - that is why it holds 8/8",
      not any(s["spec"].get("shot_custom") for s in mv._shots))


print()
print("=== THE TREE, THE PROMPT PANE AND THE HANDOFF ===")
labels = [mv.shot_tree.topLevelItem(i).text(1)
          for i in range(mv.shot_tree.topLevelItemCount())]
check("the tree labels each shot exactly as the written batch does",
      labels == [bmi.shot_label(s) for s in mv._shots], str(labels[:2]))
check("the realism column is filled per shot",
      all(mv.shot_tree.topLevelItem(i).text(2).endswith("/8")
          for i in range(mv.shot_tree.topLevelItemCount())))
mv.shot_tree.setCurrentItem(mv.shot_tree.topLevelItem(1))
check("selecting a row shows that shot's prompt",
      mv.prompt_label.text() == mv._shots[1]["prompt"])

mv.copy_selected()
check("Copy this prompt copies the selected one",
      app.clipboard().text() == mv._shots[1]["prompt"])
mv.copy_all()
check("Copy all copies every shot", app.clipboard().text().count("===") == 4,
      str(app.clipboard().text().count("===")))
check("...labelled, so a pasted batch is readable",
      bmi.shot_label(mv._shots[0]) in app.clipboard().text())

rv.copy_all()
check("relight's labels survive the same round trip",
      brl.shot_label(rv._shots[0]) in app.clipboard().text())


print()
print("=== A REFUSAL CLEARS THE PREVIOUS BATCH (found by this suite) ===")
# The first implementation returned early WITHOUT dropping the old shots, so
# switching from a set that composes to one that cannot left four stale prompts
# on screen under a gate recomputed for the new set - a green badge over a
# batch the view had just declined to build.
mv.set_combo.setCurrentIndex(mv.set_combo.findData("beauty-macro"))
mv.set_reference(REF)
mv.compose()
check("a good batch is on screen first", len(mv._shots) == 4 and mv.gate_badge.text() == "9/9")
mv.set_reference("")
mv.compose()
check("the refused recompose drops the stale shots", mv._shots == [], str(len(mv._shots)))
check("...the tree empties with them", mv.shot_tree.topLevelItemCount() == 0)
check("...the badge stops claiming 9/9", mv.gate_badge.text() == "0/0", mv.gate_badge.text())
check("...the gate rows go with it", mv.gate.tree.topLevelItemCount() == 0)
check("...and the prompt pane shows the hint again",
      mv.prompt_label.text() == mv.EMPTY_HINT, mv.prompt_label.text()[:50])
check("nothing stale can be copied or saved either", not mv.passing)


print()
print("=== A BATCH THAT WAS NEVER COMPOSED CANNOT BE COPIED OR SAVED ===")
fresh = type(rv)(theme.palette)
fresh.copy_all()
fresh.copy_selected()
fresh.save_batch()
check("an empty view composes, copies and saves nothing without raising",
      fresh._shots == [] and not fresh.passing)
check("...and its prompt pane shows the hint, not a stale prompt",
      fresh.prompt_label.text() == fresh.EMPTY_HINT, fresh.prompt_label.text()[:50])


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL BATCH SHOT GUI CHECKS PASSED")
