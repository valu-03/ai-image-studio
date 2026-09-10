"""The Advisor chat, driven through the real window against the mock model.

tests/test_advisor.py covers advisor.chat() directly, against a fake ask=.
This covers the wiring around it - the worker, the busy-guard, and the
transcript/history bookkeeping - because that is where a real bug was found:
sending a second message before the first reply landed (an Enter-key double-
send, not a second click on the already-disabled Send button) dispatched two
concurrent turns and corrupted the transcript's history - a reply got logged
against the WRONG user message, because both turns shared one
`self._last_sent` attribute. That never showed up against advisor.chat()
directly (it takes an explicit `history` argument, so there was nothing to
race) and would never show up in a test that only ever sends one message and
waits for it - which is what every quick manual check happened to do.

Offscreen, no network: the text calls go to tests/mock_api.py.
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# Must be set before any tool is imported: .env outranks os.environ, so without
# an empty env file the developer's real key decides what "no key" means.
import tempfile as _tempfile  # noqa: E402

_EMPTY = Path(_tempfile.gettempdir()) / "aivs-advisor-gui-empty.env"
_EMPTY.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ.setdefault("AIVS_ENV_FILE", str(_EMPTY))

import mock_api  # noqa: E402

PORT = 8813
mock_api.serve(PORT)
os.environ["AIVS_API_BASE"] = "http://127.0.0.1:{}/text".format(PORT)
os.environ["OPENROUTER_API_KEY"] = "advisor-gui-key"
# Redirect, not backup-and-restore: history.py reads AIVS_HISTORY_FILE at
# import time, and a crash between backing up the real log and restoring it
# would have left the user's real history overwritten with test entries.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(_tempfile.gettempdir()) / "aivs-advisor-gui-history.jsonl"))
# MainWindow reads AIVS_SETTINGS_APP at import time to pick which QSettings
# key it opens - without this the GUI test read AND WROTE the user's real
# saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()
av = win.advisor_view


def pump(seconds=10, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return until() if until else True


def settled():
    return not av._busy and av.input.isEnabled()


print("=== a single turn round-trips correctly ===")

mock_api.STATE["reply"] = "Open the Lighting section and try clam-shell."
av.input.setText("how do I get better light")
av.send()
check("busy immediately after send", av._busy)
check("input disabled while a reply is pending", not av.input.isEnabled())
check("send button disabled while a reply is pending", not av.send_button.isEnabled())
pump(until=settled)
check("settles", settled())
check("history has exactly one user+assistant pair", av.history == [
    {"role": "user", "content": "how do I get better light"},
    {"role": "assistant", "content": "Open the Lighting section and try clam-shell."},
])
check("input re-enabled", av.input.isEnabled())
check("send button re-enabled", av.send_button.isEnabled())


print()
print("=== THE BUG: a rapid second send while one is in flight is refused, not raced ===")

mock_api.STATE["reply"] = "reply to A"
av.input.setText("message A")
av.send()
check("busy right after the first send", av._busy)

# The exact shape of the original bug: calling send() again (what an Enter
# keypress in the still-enabled QLineEdit used to do) before the first turn's
# worker has reported back at all.
av.input.setText("message B")
av.send()
check("second send while busy is refused (still only 2 history entries pending)",
      len(av.history) == 2)   # the settled single-turn check above already added 2
check("the refused message is NOT cleared from the box",
      av.input.text() == "message B")

pump(until=settled)
check("settles after the first turn completes", settled())
check("exactly one more pair landed - not two", av.history == [
    {"role": "user", "content": "how do I get better light"},
    {"role": "assistant", "content": "Open the Lighting section and try clam-shell."},
    {"role": "user", "content": "message A"},
    {"role": "assistant", "content": "reply to A"},
])
check("no cross-wired pair (a 'message B' user turn paired with A's reply)",
      not any(t.get("content") == "message B" for t in av.history))

# The refused message is still sitting in the box, exactly as the user left
# it - sending it now must work like any ordinary turn.
mock_api.STATE["reply"] = "reply to B"
av.send()
pump(until=settled)
check("the previously-refused message sends correctly once idle", av.history[-2:] == [
    {"role": "user", "content": "message B"},
    {"role": "assistant", "content": "reply to B"},
])


print()
print("=== a reply carrying a spec shows a real, applied score ===")

good_spec = json.dumps({"subject": "a woman in her thirties"})
mock_api.STATE["reply"] = "Here you go.\n```spec\n" + good_spec + "\n```"
av.input.setText("build me a spec")
av.send()
pump(until=settled)
check("suggestion captured", av._suggested_spec == {"subject": "a woman in her thirties"})
check("badge shows a real 8/8", "8/8" in av.suggestion_badge.badge.text(),
      av.suggestion_badge.badge.text())

applied = {}
av.spec_suggested.connect(lambda spec: applied.setdefault("spec", spec))
av.apply_suggestion()
app.processEvents()
check("apply emits the validated spec",
      applied.get("spec") == {"subject": "a woman in her thirties"})
check("apply routes to the Images tab",
      win.stack.currentWidget() is win.images_view)


print()
print("=== a reply carrying a full autofill fills every section in one click ===")

full_payload = {
    "subject": "a nurse in her forties, dark circles under her eyes",
    "wardrobe": "wrinkled blue scrubs",
    "shot": "portrait",
    "sections": {
        "lighting": {"setup": "old-hollywood"},
        "composition": {"guide": "rule-of-thirds", "techniques": ["lead-room"]},
        "color": {"mood": "melancholy-lonely"},
        "posing": {"pose": "forward-lean", "techniques": ["relaxed-hands"]},
        "camera_angle": {"vertical": "eye-level", "side": "three-quarter",
                         "size": "medium-close-up"},
    },
}
mock_api.STATE["reply"] = "Filled everything in.\n```spec\n" + json.dumps(full_payload) + "\n```"
win.go_to("advisor")
av.input.setText("a tired nurse finishing a night shift")
av.send()
pump(until=settled)

check("core spec captured", av._suggested_spec is not None)
check("all four non-conflicting sections captured (camera_angle drops - a shot preset "
      "was also given)", sorted(av._section_suggestions) ==
      ["color", "composition", "lighting", "posing"], str(sorted(av._section_suggestions)))
check("badge names every section it will apply",
      all(label in av.suggestion_badge.badge.text() for label in
          ("Lighting", "Composition", "Color Grading", "Posing")),
      av.suggestion_badge.badge.text())
check("camera_angle correctly absent from the badge (shot preset wins)",
      "Camera Angle" not in av.suggestion_badge.badge.text())

sections_applied = {}
av.sections_suggested.connect(lambda s: sections_applied.setdefault("sections", s))
av.apply_suggestion()
pump(seconds=1)

check("sections_suggested fired with all four phrases",
      sorted(sections_applied.get("sections", {})) ==
      ["color", "composition", "lighting", "posing"])

editor = win.compose_view.editor
check("lighting landed in the Scene tab's Lighting combo",
      "old hollywood" in editor.lighting.currentText().lower(), editor.lighting.currentText())
check("colour landed in the Scene tab's Colour combo",
      "melancholic" in editor.colour.currentText().lower()
      or "melancholy" in editor.colour.currentText().lower(), editor.colour.currentText())
check("composition landed as custom framing text",
      "rule of thirds" in editor.composition.currentText().lower(),
      editor.composition.currentText())
check("posing landed in the Subject tab's Action field",
      "forward lean" in editor.action.text().lower()
      or "forward-lean" in editor.action.text().lower()
      or "lean toward" in editor.action.text().lower(), editor.action.text())
check("the core spec's own shot preset was left alone (camera_angle never touched it)",
      editor.shot.currentText() == "Portrait" or "portrait" in editor.shot.currentText().lower(),
      editor.shot.currentText())
check("routes to the Images tab", win.stack.currentWidget() is win.images_view)

spec = editor.spec()
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402
bank = win.bank
prompt, _ = bp.compose(bank, dict(spec, seed=0))
present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
check("the fully-autofilled prompt scores 8/8, not paying for the shot/angle "
      "conflict", len(present) == 8 and not banned, "{}/8 banned={}".format(len(present), banned))


print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL ADVISOR GUI CHECKS PASSED")
