"""The Auto-fill button, driven through the real window against the mock model.

test_autofill.py covers brief.autofill_spec() directly. This covers the wiring
around it - the worker, the badge, the suggestion row and the Apply button -
because that is where the interesting bugs were, and every one of them passed
the unit tests:

  * spec() substitutes "a person" when the subject box is empty, and every
    "is this field filled?" test read that as a real answer. The model's subject
    was therefore rejected on an empty form - the field that most needed it.
  * The same placeholder was sent to the model as something it must not change.
  * apply_partial() wrote the placeholder back into the box, so after one press
    the subject really did read "a person".
  * The idea line was used as the brief and then thrown away.

They only show up when the form starts EMPTY, which every unit test happened
not to do.

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

_EMPTY = Path(_tempfile.gettempdir()) / "aivs-autofill-gui-empty.env"
_EMPTY.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ.setdefault("AIVS_ENV_FILE", str(_EMPTY))

import mock_api  # noqa: E402

PORT = 8812
mock_api.serve(PORT)
os.environ["AIVS_API_BASE"] = "http://127.0.0.1:{}/text".format(PORT)
os.environ["OPENROUTER_API_KEY"] = "autofill-gui-key"
os.environ["AIVS_POLL_INTERVAL"] = "0"

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

HISTORY = ROOT / "temp" / "outputs" / "history.jsonl"
backup = HISTORY.read_bytes() if HISTORY.exists() else None

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
cv = win.compose_view
ed = cv.editor


def pump(seconds=10, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return until() if until else True


def settled():
    return cv.autofill_button.isEnabled() and not cv.autofill_badge.is_thinking


FULL_REPLY = json.dumps({
    "subject": "MODEL SUBJECT",
    "wardrobe": "a green apron",
    "setting": "a closed cafe at night",
    "action": "wiping the counter",
    "mood": "worn out",
    "shot": "environmental",
    "extra": ["the hat brim shades her eyes"],
    "lighting": "harsh midday sunlight",
    "composition_guide": "golden-spiral",
    "seed": 4242,
})

print("--- what you typed survives; the blanks get filled ---")
mock_api.STATE["reply"] = FULL_REPLY
ed.load_spec({"subject": "MY OWN SUBJECT", "mood": "MY OWN MOOD", "seed": 3})
cv.idea.setText("")
cv.run_autofill()
check("the worker finished", pump(10, until=settled), cv.autofill_badge.badge.text())

spec = ed.spec()
check("my subject survived", spec["subject"] == "MY OWN SUBJECT", spec["subject"])
check("my mood survived", spec["mood"] == "MY OWN MOOD", spec["mood"])
check("blanks were filled", spec.get("wardrobe") == "a green apron", str(spec.get("wardrobe")))
check("the model cannot move the seed", ed.seed.value() == 3, str(ed.seed.value()))
check("badge reports a score", "/8" in cv.autofill_badge.badge.text(), cv.autofill_badge.badge.text())

print("--- an EMPTY form is where the placeholder bugs lived ---")
ed.load_spec({})
cv.idea.setText("")
cv.run_autofill()
pump(10, until=settled)
check("the model's subject is accepted on an empty form",
      ed.spec()["subject"] == "MODEL SUBJECT", ed.spec()["subject"])
check("the box holds it, not the placeholder",
      ed.subject.toPlainText().strip() == "MODEL SUBJECT", repr(ed.subject.toPlainText()))

print("--- composition and lighting are suggested, never applied ---")
check("the suggestion row is showing", cv.suggestion_row.isVisible())
check("composition untouched", ed.composition_guide() == "", repr(ed.composition_guide()))
check("lighting untouched", ed.lighting_value() == "", repr(ed.lighting_value()))
check("the caption names both",
      "golden-spiral" in cv.suggestion_label.text()
      and "harsh midday sunlight" in cv.suggestion_label.text(),
      cv.suggestion_label.text())

cv.apply_suggestions()
app.processEvents()
check("Apply puts the guide in", ed.composition_guide() == "golden-spiral",
      ed.composition_guide())
check("Apply puts the light in", ed.lighting_value() == "harsh midday sunlight",
      ed.lighting_value())
check("the row hides again", not cv.suggestion_row.isVisible())
cv.rebuild()
check("and the prompt still passes 8/8", cv.passing, cv.lint.badge.text())

print("--- the idea line is never lost ---")
mock_api.STATE["reply"] = json.dumps({"mood": "calm"})
ed.load_spec({})
cv.idea.setText("a tired barista closing up late")
cv.run_autofill()
pump(10, until=settled)
check("it becomes the subject when the model gives none",
      ed.spec()["subject"] == "a tired barista closing up late", ed.spec()["subject"])

mock_api.STATE["reply"] = FULL_REPLY
ed.load_spec({})
cv.idea.setText("a tired barista closing up late")
cv.run_autofill()
pump(10, until=settled)
check("but the model's fuller subject wins when it gives one",
      ed.spec()["subject"] == "MODEL SUBJECT", ed.spec()["subject"])

print("--- failures are reported, never crashed on ---")
mock_api.STATE["reply"] = "I'd rather not do that."
ed.load_spec({"subject": "STILL MINE"})
cv.idea.setText("")
cv.run_autofill()
pump(10, until=lambda: settled() and cv.autofill_badge.badge.text() == "failed")
check("the badge says failed", cv.autofill_badge.badge.text() == "failed", cv.autofill_badge.badge.text())
check("the button comes back", cv.autofill_button.isEnabled())
check("the form is untouched", ed.spec()["subject"] == "STILL MINE", ed.spec()["subject"])

print("--- one press at a time ---")
mock_api.STATE["reply"] = json.dumps({"wardrobe": "a coat"})
cv.run_autofill()
check("disabled while it runs", not cv.autofill_button.isEnabled())
pump(10, until=settled)
check("enabled again after", cv.autofill_button.isEnabled())

if backup is not None:
    HISTORY.write_bytes(backup)
elif HISTORY.exists():
    HISTORY.unlink()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL AUTOFILL GUI CHECKS PASSED")
