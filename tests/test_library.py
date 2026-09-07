"""Character library CRUD, through the real view.

Every test runs against a temp directory: assets.CHARACTERS_DIR is repointed
before the window is built, so nothing here can touch the real characters. That
matters more than usual - this suite exercises the project's first delete.

Dialogs are modal, so each one is monkeypatched to answer a fixed way. The point
is what the code does with the answer, not that Qt can draw a message box.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication, QMessageBox

from ui import assets

# Repoint BEFORE MainWindow is imported/constructed - the view reads the global
# at call time, but the real folder must never be a fallback.
REAL_DIR = assets.CHARACTERS_DIR
# What the real folder holds right now. The closing check compares against this
# rather than against a named fixture file: the app has a Delete button, so the
# user is entitled to empty this folder, and a suite that fails because they did
# is testing their data instead of this code.
REAL_BEFORE = sorted(p.name for p in REAL_DIR.glob("*.json")) if REAL_DIR.exists() else []
TEMP_DIR = Path(tempfile.mkdtemp(prefix="aivs-characters-"))
assets.CHARACTERS_DIR = TEMP_DIR

# Same isolation, one level up: MainWindow itself reads AIVS_SETTINGS_APP at
# import time to pick which QSettings key it opens, so this must be set
# before that import too - otherwise the window this suite builds still
# reads/writes the user's real saved provider/model/theme/geometry.
import os  # noqa: E402
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def seed(stem, subject):
    path = TEMP_DIR / "{}.json".format(stem)
    path.write_text(json.dumps(
        {"slug": stem, "subject": subject, "seed": 0}, indent=2) + "\n", encoding="utf-8")
    return path


def stems():
    return sorted(p.stem for p in TEMP_DIR.glob("*.json"))


def rows(view):
    return [view.library.item(i).text() for i in range(view.library.count())]


def select(view, stem):
    for index in range(view.library.count()):
        if view.library.item(index).text() == stem:
            view.library.setCurrentRow(index)
            return True
    return False


seed("ada", "a woman in her thirties with freckles")
seed("bruno", "a man with a greying beard")

app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

cv = win.compose_view
ed = cv.editor
cv.reload_library()

print("--- the library reads the temp folder ---")
check("both characters listed", rows(cv) == ["ada", "bruno"], str(rows(cv)))
check("the real folder is untouched", assets.CHARACTERS_DIR == TEMP_DIR)

print("--- slug hardening ---")
check("trailing hyphen stripped", not cv.safe_slug("hello world -").endswith("-"),
      cv.safe_slug("hello world -"))
check("reserved device name escaped", cv.safe_slug("CON") != "con", cv.safe_slug("CON"))
check("com1 escaped", cv.safe_slug("com1") != "com1", cv.safe_slug("com1"))
check("empty falls back", cv.safe_slug("!!!") == "untitled", cv.safe_slug("!!!"))
check("normal names survive", cv.safe_slug("Ada Lovelace") == "ada-lovelace",
      cv.safe_slug("Ada Lovelace"))

print("--- free_slug finds the first gap ---")
check("takes a free name", cv.free_slug("carla") == "carla")
check("advances past a taken one", cv.free_slug("ada") == "ada-2")
seed("ada-2", "a copy")
check("advances again", cv.free_slug("ada") == "ada-3")
(TEMP_DIR / "ada-2.json").unlink()

print("--- New: blank ---")
select(cv, "ada")
cv.load_selected()
check("loaded ada", "freckles" in ed.spec()["subject"])
QMessageBox.exec = lambda self: setattr(self, "_answer", "blank")
_orig_clicked = QMessageBox.clickedButton
QMessageBox.clickedButton = lambda self: self.buttons()[0]      # "Blank"
cv.new_character()
app.processEvents()
check("subject reset", ed.spec()["subject"] == "a person", ed.spec()["subject"])
check("nothing written to disk", stems() == ["ada", "bruno"], str(stems()))
check("selection cleared", cv.library.currentRow() == -1, str(cv.library.currentRow()))

print("--- New: duplicate advances the slug ---")
select(cv, "ada")
cv.load_selected()
before = (TEMP_DIR / "ada.json").read_bytes()
QMessageBox.clickedButton = lambda self: self.buttons()[1]      # "Duplicate current"
cv.new_character()
app.processEvents()
check("slug advanced", ed.spec().get("slug") == "ada-2", str(ed.spec().get("slug")))
check("subject carried over", "freckles" in ed.spec()["subject"])
check("still nothing on disk", stems() == ["ada", "bruno"], str(stems()))
cv.save_spec()
check("saved under the new name", "ada-2" in stems(), str(stems()))
check("the original is byte-identical",
      (TEMP_DIR / "ada.json").read_bytes() == before)
check("new row is selected", cv.library.currentItem().text() == "ada-2",
      cv.library.currentItem().text())

print("--- New: cancel changes nothing ---")
select(cv, "bruno")
cv.load_selected()
QMessageBox.clickedButton = lambda self: self.buttons()[2]      # "Cancel"
cv.new_character()
app.processEvents()
check("form untouched", "greying beard" in ed.spec()["subject"], ed.spec()["subject"])
check("disk untouched", stems() == ["ada", "ada-2", "bruno"], str(stems()))

print("--- Rename moves the file AND the slug inside it ---")
from PyQt6.QtWidgets import QInputDialog  # noqa: E402
QInputDialog.getText = staticmethod(lambda *a, **k: ("Bruno Rossi", True))
select(cv, "bruno")
cv.rename_character()
app.processEvents()
check("file renamed", "bruno-rossi" in stems() and "bruno" not in stems(), str(stems()))
saved = json.loads((TEMP_DIR / "bruno-rossi.json").read_text(encoding="utf-8"))
check("slug inside matches the stem", saved["slug"] == "bruno-rossi", saved.get("slug"))
check("content preserved", "greying beard" in saved["subject"])
check("renamed row stays selected", cv.library.currentItem().text() == "bruno-rossi",
      cv.library.currentItem().text())

print("--- Rename refuses a collision ---")
warned = {"n": 0}
QMessageBox.warning = staticmethod(lambda *a, **k: warned.__setitem__("n", warned["n"] + 1))
QInputDialog.getText = staticmethod(lambda *a, **k: ("ada", True))
select(cv, "bruno-rossi")
cv.rename_character()
app.processEvents()
check("both files still there", "ada" in stems() and "bruno-rossi" in stems(), str(stems()))
check("the user was warned", warned["n"] == 1, str(warned["n"]))
check("ada was not overwritten",
      "freckles" in json.loads((TEMP_DIR / "ada.json").read_text(encoding="utf-8"))["subject"])

print("--- Rename: cancel and empty names do nothing ---")
QInputDialog.getText = staticmethod(lambda *a, **k: ("whatever", False))
cv.rename_character()
check("cancel is a no-op", stems() == ["ada", "ada-2", "bruno-rossi"], str(stems()))
QInputDialog.getText = staticmethod(lambda *a, **k: ("   ", True))
cv.rename_character()
check("blank name is a no-op", stems() == ["ada", "ada-2", "bruno-rossi"], str(stems()))

print("--- Delete asks first, and No means no ---")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
select(cv, "ada-2")
cv.delete_character()
app.processEvents()
check("declining keeps the file", "ada-2" in stems(), str(stems()))

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
cv.delete_character()
app.processEvents()
check("confirming removes the file", "ada-2" not in stems(), str(stems()))
check("row removed too", "ada-2" not in rows(cv), str(rows(cv)))

print("--- CRUD with nothing selected is a status message, not a crash ---")
cv.library.setCurrentRow(-1)
cv.rename_character()
cv.delete_character()
check("survived an empty selection", True)
check("nothing deleted", stems() == ["ada", "bruno-rossi"], str(stems()))

print("--- the surviving character still composes and passes ---")
select(cv, "ada")
cv.load_selected()
cv.form_mode.setCurrentIndex(0)
cv.rebuild()
check("prompt composed", len(cv.prompt_text()) > 100, str(len(cv.prompt_text())))
check("passes 8/8", cv.passing, cv.lint.badge.text())

print("--- filtering does not break selection restore ---")
cv.set_filter("ada")
check("filtered to one", rows(cv) == ["ada"], str(rows(cv)))
cv.set_filter("")
check("filter cleared", rows(cv) == ["ada", "bruno-rossi"], str(rows(cv)))

QMessageBox.clickedButton = _orig_clicked
shutil.rmtree(TEMP_DIR, ignore_errors=True)
assets.CHARACTERS_DIR = REAL_DIR
real_after = sorted(p.name for p in REAL_DIR.glob("*.json")) if REAL_DIR.exists() else []
check("real character folder untouched", real_after == REAL_BEFORE,
      "{} -> {}".format(REAL_BEFORE, real_after))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL LIBRARY CHECKS PASSED")
sys.exit(0)
