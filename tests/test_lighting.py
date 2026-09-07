"""Custom lighting input, end to end through the real UI."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# Before MainWindow is imported: it reads AIVS_SETTINGS_APP at import time to
# pick which QSettings key it opens. Without this every GUI test read AND
# WROTE the user's real saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
# This suite's own variant-build step below used to write straight into the
# REAL history.jsonl (no redirect existed) and then delete exactly the rows
# it added back out - fine as long as nothing crashed in between, but a
# crash between the write and that cleanup would have left fake rows
# permanently mixed into the user's real log. Redirect instead of trusting
# the cleanup to always run.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(tempfile.gettempdir()) / "aivs-lighting-history.jsonl"))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.theme import ThemeManager

app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

cv = win.compose_view
ed = cv.editor
cv.form_mode.setCurrentIndex(0)
# A FIXED spec, not whichever character happens to be first in the user's
# real library - `library.setCurrentRow(0); load_selected()` used to load
# that, and a real saved character can legitimately score below 8/8 for
# reasons that have nothing to do with lighting (a shot_custom naming no
# camera device, say - tools/README.md documents that as the gate working
# correctly). This suite is about the lighting override specifically, so it
# needs a base spec guaranteed to be 8/8 on every other layer.
ed.load_spec({"subject": "a woman in her thirties", "seed": 0})

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("--- combo is editable ---")
check("editable", ed.lighting.isEditable())
n_before = ed.lighting.count()

print("--- custom lighting flows into the prompt ---")
ed.lighting.setCurrentText("firelight from a wood stove")
app.processEvents()
cv.rebuild()
spec = ed.spec()
check("override captured",
      spec["overrides"]["lighting"][0] == "firelight from a wood stove",
      str(spec["overrides"]["lighting"]))
check("shadows appended", spec["overrides"]["lighting"][1] == "realistic shadows")
prompt = cv.prompt_text()
check("custom text in prompt", "firelight from a wood stove" in prompt)
check("no bank source leaked", "soft window light" not in prompt)
check("still 8/8", cv.passing, cv.lint.badge.text())
check("list did not grow", ed.lighting.count() == n_before, str(ed.lighting.count()))

print("--- detailed form too ---")
cv.form_mode.setCurrentIndex(1)
cv.rebuild()
check("custom text in detailed", "firelight from a wood stove" in cv.prompt_text())
check("detailed still 8/8", cv.passing, cv.lint.badge.text())
cv.form_mode.setCurrentIndex(0)
cv.rebuild()

print("--- typing edits trigger a rebuild (text, not index) ---")
ed.lighting.setCurrentText("candlelight only")
app.processEvents()
cv.rebuild()
check("rebuild picked up new text", "candlelight only" in cv.prompt_text())

print("--- round-trips through save/load ---")
saved = ed.spec()
ed.load_spec({"subject": "someone else", "seed": 0})
check("cleared on load", ed.lighting_value() == "", repr(ed.lighting_value()))
ed.load_spec(saved)
check("custom source restored", ed.lighting_value() == "candlelight only", ed.lighting_value())
cv.rebuild()
check("restored into prompt", "candlelight only" in cv.prompt_text())

print("--- preset sources still work ---")
ed.lighting.setCurrentIndex(ed.lighting.findData("golden hour sunlight"))
app.processEvents()
cv.rebuild()
check("preset selected", ed.spec()["overrides"]["lighting"][0] == "golden hour sunlight")
check("preset 8/8", cv.passing)

print("--- (auto) means no override ---")
ed.lighting.setCurrentIndex(0)
app.processEvents()
cv.rebuild()
check("auto has no override", "overrides" not in ed.spec())
check("auto still 8/8", cv.passing)

print("--- blank text is treated as auto ---")
ed.lighting.setCurrentText("   ")
app.processEvents()
check("blank -> auto", "overrides" not in ed.spec())

print("--- variants view inherits the custom source ---")
ed.lighting.setCurrentText("a single bare bulb overhead")
app.processEvents()
bundle_spec, _, _ = win.current_spec_bundle()
check("bundle carries custom",
      bundle_spec["overrides"]["lighting"][0] == "a single bare bulb overhead")
win.variants_view.count.setValue(3)
win.variants_view.build_variants()
check("3 variants built", len(win.variants_view.cards) == 3)
import history as hist
recent = hist.load()[-3:]
check("all variants use it",
      all("a single bare bulb overhead" in e["prompt"] for e in recent))
check("all variants 8/8", all(e["score"] == 8 for e in recent),
      str([e["score"] for e in recent]))

# don't leave test rows in the (isolated) log
if hist.HISTORY.exists():
    hist.HISTORY.unlink()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL LIGHTING CHECKS PASSED")
sys.exit(0)
