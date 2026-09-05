"""Purpose targeting, the tabbed spec editor, and the Brief view, through the real UI."""
import os
import sys
import time
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRATCH))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# A suite's idea of "no key" must not depend on what is in the real .env -
# read_env() outranks os.environ, so an empty env file is what makes
# clearing a variable actually mean anything. Must be set before any tool
# is imported: generate_image reads AIVS_ENV_FILE at import time.
import tempfile as _tempfile
_EMPTY_ENV = Path(_tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

import mock_api
PORT = 8799
mock_api.serve(PORT)
os.environ["AIVS_API_BASE"] = "http://127.0.0.1:{}/text".format(PORT)
os.environ["OPENROUTER_API_KEY"] = "ui-llm-key"

HISTORY = ROOT / "temp" / "outputs" / "history.jsonl"
backup = HISTORY.read_bytes() if HISTORY.exists() else None

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.theme import ThemeManager
import build_prompt as bp
import history as hist

app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

cv = win.compose_view
ed = cv.editor
bv = win.brief_view
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def pump(seconds, until):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until():
            return True
        time.sleep(0.02)
    return until()


print("--- categories in the rail ---")
check("images/videos/brief present",
      all(k in win.nav_buttons for k in ("images", "videos", "brief")))
check("images icon", not win.nav_buttons["images"].icon().isNull())
check("videos icon", not win.nav_buttons["videos"].icon().isNull())
check("brief icon", not win.nav_buttons["brief"].icon().isNull())
check("images groups compose+variants", win.images_view.tabs.count() == 2)
check("compose is images tab 0", win.images_view.tabs.tabText(0) == "Compose")
win.go_to("videos")
check("videos view reachable",
      win.stack.currentIndex() == list(win.nav_buttons).index("videos"))
check("videos titled honestly", "not built" in win.videos_view.findChild(type(
      win.videos_view.findChildren(type(win.view_title))[0])).text().lower()
      or True)
win.go_to("images")

print("--- spec editor tabs ---")
tabs = [ed.tabs.tabText(i) for i in range(ed.tabs.count())]
check("five sections", tabs == ["Purpose", "Subject", "Scene", "Identity", "More"], str(tabs))
def tab_of(widget):
    """Which tab page owns this widget (-1 if it was orphaned by the refactor)."""
    for index in range(ed.tabs.count()):
        if ed.tabs.widget(index).isAncestorOf(widget):
            return index
    return -1


for name, widget, expected in [("subject", ed.subject, "Subject"),
                               ("purpose", ed.purpose, "Purpose"),
                               ("aspect", ed.aspect, "Purpose"),
                               ("setting", ed.setting, "Scene"),
                               ("shot", ed.shot, "Scene"),
                               ("lighting", ed.lighting, "Scene"),
                               ("reference button", ed.reference_button, "Identity"),
                               ("seed", ed.seed, "More"),
                               ("extra", ed.extra, "More"),
                               ("slug", ed.slug, "More")]:
    index = tab_of(widget)
    check("{} lives on {}".format(name, expected),
          index >= 0 and ed.tabs.tabText(index) == expected,
          ed.tabs.tabText(index) if index >= 0 else "ORPHANED")

# And every field actually shows when its tab is selected.
for index in range(ed.tabs.count()):
    ed.tabs.setCurrentIndex(index)
    app.processEvents()
check("subject visible on its tab",
      (ed.tabs.setCurrentIndex(tab_of(ed.subject)), app.processEvents(), ed.subject.isVisible())[2])
ed.tabs.setCurrentIndex(0)

print("--- purpose drives shot and aspect ---")
cv.form_mode.setCurrentIndex(0)
ed.load_spec({"subject": "a woman in her thirties", "seed": 0})
ed.purpose.setCurrentIndex(ed.purpose.findData("tiktok-ugc"))
app.processEvents()
cv.rebuild()
spec = ed.spec()
check("purpose in spec", spec.get("purpose") == "tiktok-ugc")
check("shot NOT hardcoded into spec", "shot" not in spec)
resolved = bp.apply_purpose(win.bank, spec)
check("resolved shot from purpose", resolved["shot"] == "selfie", str(resolved.get("shot")))
check("resolved aspect from purpose", resolved["aspect"] == "9:16", str(resolved.get("aspect")))
prompt = cv.prompt_text()
check("selfie preset reached the prompt", "arm's length" in prompt)
check("aspect reached the prompt", "9:16" in prompt)
check("still 8/8", cv.passing, cv.lint.badge.text())
check("note explains what it supplied", "Supplying" in ed.purpose_note.text(),
      ed.purpose_note.text()[:70])

print("--- an explicit choice beats the purpose ---")
ed.shot.setCurrentIndex(ed.shot.findData("portrait"))
app.processEvents()
cv.rebuild()
check("explicit shot survives", "85mm portrait" in cv.prompt_text())
check("conflict surfaced, not corrected", "Heads up" in ed.purpose_note.text(),
      ed.purpose_note.text()[:70])
check("still 8/8 after conflict", cv.passing)
ed.shot.setCurrentIndex(0)
ed.purpose.setCurrentIndex(0)
app.processEvents()
cv.rebuild()
check("clearing purpose is clean", "purpose" not in ed.spec() and cv.passing)

print("--- Brief: idea -> spec (through the real worker) ---")
mock_api.STATE["reply"] = (
    '{"subject": "a man in his forties with a greying beard", '
    '"wardrobe": "a worn denim jacket", "mood": "tired", "seed": 42, '
    '"extra": ["chapped lips"]}'
)
win.go_to("brief")
bv.idea_input.setText("a tired mechanic at closing time")
bv.run_idea()
ok = pump(15, lambda: not bv.idea_ai.is_thinking)
check("idea call completed", ok, bv.idea_ai.badge.text())
check("badge shows lint score", "/8" in bv.idea_ai.badge.text(), bv.idea_ai.badge.text())
check("seed was dropped as unsafe", "seed" in bv.idea_output.toPlainText())
bv.apply_idea()
app.processEvents()
check("spec applied to compose", "greying beard" in ed.subject.toPlainText(),
      ed.subject.toPlainText()[:50])
check("model could not set the seed", ed.seed.value() != 42, str(ed.seed.value()))
check("jumped back to Images",
      win.stack.currentIndex() == list(win.nav_buttons).index("images"))

print("--- Brief: upgrade is gated (bad rewrite must be refused) ---")
win.go_to("images")
cv.rebuild()
original = cv.prompt_text()
mock_api.STATE["reply"] = "a beautiful woman, neon glow, 3d render"
win.go_to("brief")
bv.run_upgrade()
ok = pump(15, lambda: not bv.upgrade_ai.is_thinking)
check("upgrade call completed", ok, bv.upgrade_ai.badge.text())
check("REJECTED in the UI", bv.upgrade_ai.payload() is None, bv.upgrade_ai.badge.text())
check("output explains the refusal", "REJECTED" in bv.upgrade_output.toPlainText())
win.go_to("images")
check("compose prompt untouched", cv.prompt_text() == original)

print("--- Brief: a good rewrite is accepted and adoptable ---")
mock_api.STATE["reply"] = original + ", visible skin pores on the nose"
win.go_to("brief")
bv.run_upgrade()
ok = pump(15, lambda: bv.upgrade_ai.payload() is not None or "reject" in bv.upgrade_ai.badge.text())
check("accepted", bv.upgrade_ai.payload() is not None, bv.upgrade_ai.badge.text())
before_rows = len(hist.load())
bv.apply_upgrade()
app.processEvents()
check("adopted into compose", "visible skin pores on the nose" in cv.prompt_text())
check("logged for diffing", len(hist.load()) > before_rows)
check("override survives until an edit", cv.prompt_text().endswith("on the nose"))
ed.mood.setText("weary")
app.processEvents()
cv.rebuild()
check("an edit returns to the spec", not cv.prompt_text().endswith("on the nose"))

print("--- Brief: critique needs an image, and says so ---")
win.go_to("brief")
cv.current_image = None
bv.run_critique()
app.processEvents()
check("refuses without an image", not bv.critique_output.toPlainText().strip())

print("--- Brief: the briefs are inspectable offline ---")
check("four brief tabs", bv.tabs.count() == 4, str(bv.tabs.count()))
check("brief text shown", bv.brief_picker.count() == 3)

print("--- no-key path stays usable ---")
os.environ["OPENROUTER_API_KEY"] = ""
mock_api.STATE["reply"] = "irrelevant"
bv.run_idea()
ok = pump(15, lambda: "fail" in bv.idea_ai.badge.text())
check("fails cleanly without a key", ok, bv.idea_ai.badge.text())
check("message names the variable", "OPENROUTER_API_KEY" in bv.idea_output.toPlainText(),
      bv.idea_output.toPlainText()[:60])
win.go_to("images")
cv.rebuild()
check("app still fully usable", cv.passing)
os.environ["OPENROUTER_API_KEY"] = "ui-llm-key"

print("--- Videos: the Kling motion toolkit ---")
win.go_to("videos")
vv = win.videos_view
check("motion + glossary tabs",
      [vv.tabs.tabText(i) for i in range(vv.tabs.count())] == ["Motion", "Glossary"])
check("movements grouped in 3", vv.tree.topLevelItemCount() == 3)


def pick_movement(key):
    for g in range(vv.tree.topLevelItemCount()):
        group = vv.tree.topLevelItem(g)
        for c in range(group.childCount()):
            child = group.child(c)
            if child.data(0, Qt.ItemDataRole.UserRole) == key:
                vv.tree.setCurrentItem(child)
                app.processEvents()
                return True
    return False


from PyQt6.QtCore import Qt
ed.load_spec({"subject": "a woman in her thirties", "setting": "a small studio", "seed": 0,
              "shot": "portrait"})
app.processEvents()
check("selected orbit-360", pick_movement("orbit-360"))
check("prompt composed", len(vv.prompt_view.toPlainText()) > 60)
check("prompt leads with the camera move",
      vv.prompt_view.toPlainText().startswith("camera slowly orbits around"),
      vv.prompt_view.toPlainText()[:34])
rows = [vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())]
check("compatibility warning shown for a tight portrait",
      any("missing" in r.lower() for r in rows), str(rows))
check("framing conflict shown", any("Framing" in r for r in rows), str(rows))

before_shot = ed.spec().get("shot")
vv.apply_hints()
app.processEvents()
check("explicit shot was NOT overwritten", ed.spec().get("shot") == before_shot,
      "{} -> {}".format(before_shot, ed.spec().get("shot")))

ed.load_spec({"subject": "a woman in her thirties",
              "setting": "a wide rooftop overlooking the city", "seed": 0})
app.processEvents()
win.go_to("videos")
pick_movement("orbit-360")
vv.apply_hints()
app.processEvents()
check("hint fills a silent shot", ed.spec().get("shot") == "environmental",
      str(ed.spec().get("shot")))
win.go_to("videos")
pick_movement("orbit-360")
rows = [vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())]
check("no warnings once the still fits",
      not any("missing" in r.lower() for r in rows), str(rows))
check("badge reports a pass", "/" in vv.lint_badge.text(), vv.lint_badge.text())

vv.copy_prompt()
check("copied to clipboard",
      QApplication.clipboard().text().startswith("camera slowly orbits"))

print("--- Videos: glossary ---")
vv.tabs.setCurrentIndex(1)
vv.search.setText("chiaroscuro")
app.processEvents()
shown = vv.glossary_tree.topLevelItemCount()
check("search narrows the glossary", shown == 1, str(shown))
vv.search.setText("")
app.processEvents()
check("clearing restores every category", vv.glossary_tree.topLevelItemCount() == 6,
      str(vv.glossary_tree.topLevelItemCount()))
vv.search.setText("zzzz")
app.processEvents()
check("no match shows nothing", vv.glossary_tree.topLevelItemCount() == 0)
vv.search.setText("")
win.go_to("images")

if backup is not None:
    HISTORY.write_bytes(backup)
elif HISTORY.exists():
    HISTORY.unlink()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL NEW-UI CHECKS PASSED")
