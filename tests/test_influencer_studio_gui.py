"""Influencer Studio, through the real MainWindow - roster CRUD, reference-
image handling, and Apply to Compose.

Every test runs against a temp roster folder: assets.PERSONAS_DIR is
repointed before the window is built, so nothing here can touch a real saved
persona (same isolation tests/test_library.py already uses for
assets.CHARACTERS_DIR). Every QMessageBox is monkeypatched to answer a fixed
way rather than trusted to draw - a real modal with nothing offscreen to
click it is a hang, not a failure (see CLAUDE.md's own documented lesson).

One real bug lives in here as a named regression: New (blank) after loading
a real persona used to leave the previously-picked Age/Hair/Eye chip visibly
checked and its phrase still in the composed sentence - Qt's exclusive
QButtonGroup refuses `setChecked(False)` on its own currently-checked button.
Confirmed to fail against the pre-fix code (git stash -- ui/views/
influencer_studio.py) before passing after.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# Must be set before any tool is imported: .env outranks os.environ, so
# without an empty env file a real key would decide what "no key" means, and
# refresh_credits() would fire a real network call at MainWindow construction.
_EMPTY = Path(tempfile.gettempdir()) / "aivs-influencer-gui-empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ.setdefault("AIVS_ENV_FILE", str(_EMPTY))
os.environ.setdefault("AIVS_ASSUME_YES", "1")
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(tempfile.gettempdir()) / "aivs-influencer-gui-history.jsonl"))
# MainWindow reads AIVS_SETTINGS_APP at import time - without this the GUI
# test would read AND WRITE the user's real saved provider/model/theme/geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from ui import assets  # noqa: E402

REAL_DIR = assets.PERSONAS_DIR
REAL_BEFORE = sorted(p.name for p in REAL_DIR.glob("*.json")) if REAL_DIR.exists() else []
TEMP_DIR = Path(tempfile.mkdtemp(prefix="aivs-personas-"))
assets.PERSONAS_DIR = TEMP_DIR
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def stems():
    return sorted(p.stem for p in TEMP_DIR.glob("*.json"))


def rows(view):
    return [view.roster.item(i).text() for i in range(view.roster.count())]


def select(view, stem):
    for index in range(view.roster.count()):
        if view.roster.item(index).text() == stem:
            view.roster.setCurrentRow(index)
            return True
    return False


def fill_zoe(view):
    view.name_field.setText("Zoe")
    view.gender_combo.setCurrentIndex(view.gender_combo.findData("woman"))
    view.age_buttons["25-30"].setChecked(True)
    view.style_buttons["luxury"].setChecked(True)
    view.style_buttons["lifestyle"].setChecked(True)
    view.hair_buttons["blonde"].setChecked(True)
    view.eye_buttons["blue"].setChecked(True)
    view.details_field.setPlainText("a small nose stud")


app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

view = win.influencer_studio_view

print("--- Build tab composes live from structured picks ---")
fill_zoe(view)
app.processEvents()
composed = view.composed.text()
check("name leads the sentence", composed.startswith("Zoe,"), composed)
check("gender + age range appear", "a woman in their late twenties" in composed, composed)
check("hair + eye color appear", "blonde hair and blue eyes" in composed, composed)
check("both style tags appear", "elevated" in composed and "lifestyle-editorial" in composed,
      composed)
check("free-text details appear, appended as typed", composed.endswith("a small nose stud"),
      composed)

print()
print("--- Save to roster writes the structured dict, not just the composed text ---")
view.save_persona()
app.processEvents()
check("one file on disk", stems() == ["zoe"], str(stems()))
check("roster row shows it", rows(view) == ["zoe"], str(rows(view)))
check("real folder untouched", assets.PERSONAS_DIR == TEMP_DIR)
saved = json.loads((TEMP_DIR / "zoe.json").read_text(encoding="utf-8"))
check("saved dict carries every structured field", saved.get("name") == "Zoe"
      and saved.get("gender") == "woman" and saved.get("age_range") == "25-30"
      and set(saved.get("style_tags", [])) == {"luxury", "lifestyle"}
      and saved.get("hair_color") == "blonde" and saved.get("eye_color") == "blue",
      str(saved))
check("no reference_images key holds anything (none were added)",
      saved.get("reference_images") == [], str(saved.get("reference_images")))

print()
print("--- New (blank) actually clears the exclusive chip groups ---")
print("    (regression: Qt refuses setChecked(False) on an exclusive group's")
print("    own currently-checked button - confirmed to fail pre-fix)")
view.new_persona()
app.processEvents()
check("name cleared", view.name_field.text() == "", repr(view.name_field.text()))
check("no age chip stays checked", view._picked_single(view.age_buttons) is None,
      view._picked_single(view.age_buttons))
check("no hair chip stays checked", view._picked_single(view.hair_buttons) is None,
      view._picked_single(view.hair_buttons))
check("no eye chip stays checked", view._picked_single(view.eye_buttons) is None,
      view._picked_single(view.eye_buttons))
check("no style chips stay checked", view._picked_style_tags() == [],
      str(view._picked_style_tags()))
check("a blank form shows the empty hint, not a green 'a person.'",
      "Describe the persona" in view.composed.text()
      and not view.apply_button.isEnabled(), view.composed.text())
check("nothing written to disk by New alone", stems() == ["zoe"], str(stems()))
check("roster selection cleared", view.roster.currentRow() == -1, str(view.roster.currentRow()))

print()
print("--- Load restores every field, not just the composed text ---")
select(view, "zoe")
view.load_selected()
app.processEvents()
check("name restored", view.name_field.text() == "Zoe", view.name_field.text())
check("gender restored", view.gender_combo.currentData() == "woman",
      view.gender_combo.currentData())
check("age chip restored", view._picked_single(view.age_buttons) == "25-30",
      view._picked_single(view.age_buttons))
check("style chips restored", set(view._picked_style_tags()) == {"luxury", "lifestyle"},
      str(view._picked_style_tags()))
check("hair chip restored", view._picked_single(view.hair_buttons) == "blonde",
      view._picked_single(view.hair_buttons))
check("eye chip restored", view._picked_single(view.eye_buttons) == "blue",
      view._picked_single(view.eye_buttons))
check("details restored", view.details_field.toPlainText() == "a small nose stud",
      repr(view.details_field.toPlainText()))
check("composed text matches what was saved", view.composed.text() == composed,
      view.composed.text())

print()
print("--- Reference images: cap at 8, thumbnails track the list, remove works ---")
check("starts empty", view._reference_images == [])
view.add_reference_images(["img{}.png".format(i) for i in range(5)])
app.processEvents()
check("5 accepted", len(view._reference_images) == 5, str(view._reference_images))
check("5 thumbnails built (plus the trailing stretch)",
      view.reference_row.count() == 6, str(view.reference_row.count()))
view.add_reference_images(["img{}.png".format(i) for i in range(5, 10)])
app.processEvents()
check("capped at 8, not 10", len(view._reference_images) == 8, str(view._reference_images))
check("the 5 already-added stay, only 3 more fit",
      view._reference_images[:5] == ["img{}.png".format(i) for i in range(5)],
      str(view._reference_images))
view.remove_reference_image("img0.png")
app.processEvents()
check("remove drops exactly one", len(view._reference_images) == 7
      and "img0.png" not in view._reference_images, str(view._reference_images))

print()
print("--- Reference images are never wired into identity-lock ---")
check("SpecEditor.reference() is untouched by anything Influencer Studio did",
      win.compose_view.editor.reference() == "", repr(win.compose_view.editor.reference()))

print()
print("--- Apply to Compose lands the composed text in Subject, nothing else ---")
select(view, "zoe")
view.load_selected()
app.processEvents()
before_ref = win.compose_view.editor.reference()
view.apply_to_compose()
app.processEvents()
check("Subject now holds the composed persona description",
      win.compose_view.editor.subject.toPlainText() == view.composed.text(),
      win.compose_view.editor.subject.toPlainText())
check("nav routed to Images", win.view_title.text() == "Images", win.view_title.text())
check("reference/lock_identity still untouched",
      win.compose_view.editor.reference() == before_ref == "",
      repr(win.compose_view.editor.reference()))
check("no lock_identity key in the spec", "lock_identity" not in win.compose_view.editor.spec())

print()
print("--- Rename and Delete (mirrors the character library's own CRUD) ---")
QInputDialog.getText = staticmethod(lambda *a, **k: ("Zoe Chen", True))
select(view, "zoe")
view.rename_persona()
app.processEvents()
check("file renamed", "zoe-chen" in stems() and "zoe" not in stems(), str(stems()))

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
select(view, "zoe-chen")
view.delete_persona()
app.processEvents()
check("file deleted", stems() == [], str(stems()))
check("roster row removed too", rows(view) == [], str(rows(view)))

print()
print("--- Empty-selection CRUD is a status message, not a crash ---")
view.roster.setCurrentRow(-1)
view.rename_persona()
view.delete_persona()
check("survived an empty selection", True)

shutil.rmtree(TEMP_DIR, ignore_errors=True)
assets.PERSONAS_DIR = REAL_DIR
real_after = sorted(p.name for p in REAL_DIR.glob("*.json")) if REAL_DIR.exists() else []
check("real persona folder untouched", real_after == REAL_BEFORE,
      "{} -> {}".format(REAL_BEFORE, real_after))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL INFLUENCER STUDIO GUI CHECKS PASSED")
sys.exit(0)
