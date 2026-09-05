"""Custom lighting input, end to end through the real UI."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

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
cv.library.setCurrentRow(0)
cv.load_selected()

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

# don't leave test rows in the log
remaining = hist.load()[:-3]
hist.save_all(remaining)
if not remaining and hist.HISTORY.exists():
    hist.HISTORY.unlink()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL LIGHTING CHECKS PASSED")
sys.exit(0)
