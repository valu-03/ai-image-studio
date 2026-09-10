"""StyleView through the real MainWindow: a picked style reaches the Images
prompt, a photoreal one keeps 8/8, a stylised one warns that it will fight
the realism vocabulary the prompt still carries.

tests/test_style_bank.py covers build_style / style_bank directly; this is the
wiring - the Look tab, the style_applied signal, set_style_override, and the
free-override fallthrough in build_prompt, end to end.

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

_EMPTY = Path(tempfile.gettempdir()) / "aivs-style-gui-empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_HISTORY_FILE",
                      str(Path(tempfile.gettempdir()) / "aivs-style-gui-history.jsonl"))

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
sv = win.style_view
cv = win.compose_view
cv.editor.load_spec({"subject": "a woman in her thirties", "seed": 1})
cv.rebuild()

print("=== Style lives in Look as the sixth tab ===")
check("go_to('style') routes into Look",
      (win.go_to("style") or True)
      and win.stack.currentWidget() is win.look_view
      and win.look_view.tabs.currentWidget() is sv)
check("Look has six toolkit tabs",
      [win.look_view.tabs.tabText(i) for i in range(win.look_view.tabs.count())]
      == ["Lighting", "Composition", "Camera", "Color", "Posing", "Style"])

print()
print("=== a photoreal style: applies, prompt updated, still 8/8 ===")
sv.tabs.setCurrentIndex(1)  # Build
idx = sv.style_combo.findData("film-noir")
sv.style_combo.setCurrentIndex(idx)
app.processEvents()
check("photoreal style shows 'ready', no warning",
      sv._has_result and sv.warning_note.isHidden(), sv.status_badge.text())
sv.apply_to_compose()
app.processEvents()
cv.rebuild()   # the live app rebuilds on a debounce timer; force it here
check("apply routed back to Images/Compose",
      win.stack.currentWidget() is win.images_view)
check("the style phrase is in the composed prompt",
      "film noir" in cv.prompt_text().lower(), cv.prompt_text()[-120:])
check("the prompt still scores 8/8", cv.passing, cv.lint.badge.text())
check("it rode in overrides['style']",
      cv.editor.spec().get("overrides", {}).get("style"), str(cv.editor.spec().get("overrides")))

print()
print("=== a stylised style: warns that it will fight the realism vocabulary ===")
win.go_to("style")
sv.tabs.setCurrentIndex(1)
sv.style_combo.setCurrentIndex(sv.style_combo.findData("oil-painting"))
app.processEvents()
check("stylised style shows the warning note",
      not sv.warning_note.isHidden() and "fights the realism" in sv.warning_note.text(),
      sv.warning_note.text())
check("badge reads 'stylised'", "stylised" in sv.status_badge.text(),
      sv.status_badge.text())
sv.apply_to_compose()
app.processEvents()
cv.rebuild()
prompt = cv.prompt_text().lower()
check("oil painting is in the prompt", "oil painting" in prompt)
check("the prompt is now a hybrid - painting words next to realism words "
      "(exactly what the warning is about)",
      "oil painting" in prompt and "realistic" in prompt, prompt[-160:])

print()
print("=== clearing the style restores 8/8 ===")
win.go_to("style")
sv.tabs.setCurrentIndex(1)
sv.style_combo.setCurrentIndex(0)   # (none)
app.processEvents()
sv.custom_field.setText("")
app.processEvents()
check("Build shows the empty hint, Apply disabled",
      not sv._has_result and not sv.apply_button.isEnabled())
cv.editor.set_style_override("")
cv.rebuild()
check("prompt is 8/8 again with no style", cv.passing, cv.lint.badge.text())

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL STYLE GUI CHECKS PASSED")
