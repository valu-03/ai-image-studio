"""SoundView's Compose tab, through the real widget.

tests/test_sound.py covers build_sound.compose() / sound_lint directly and
deliberately imports no PyQt. This covers the wiring around it, where a real
bug lived: filling only Where and How (never Source or Action) left the
Result box empty with just a "0/4" badge and no word about what was missing -
the section looked broken. The composer is unchanged (a sound-effect prompt
genuinely needs a source and an action); the view now says so instead of
going silently blank, and the Generate button no longer starts life enabled
with nothing composed.

Offscreen, no network: list_voices() short-circuits on the empty env file
before it ever builds a request.
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

_EMPTY = Path(tempfile.gettempdir()) / "aivs-sound-gui-empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.views.sound import SoundView  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


v = SoundView({})
v.tabs.setCurrentIndex(1)  # Compose

print("=== an empty form is quiet, not broken ===")
check("nothing composed", v.composed.text() == "")
check("no advice shouted at an untouched form", v.compose_advice.text() == "")
check("Generate starts disabled with nothing composed",
      not v.generate_effect_button.isEnabled())
check("the output box carries a placeholder that explains the fields",
      "Source" in v.composed.placeholderText() and "Action" in v.composed.placeholderText(),
      v.composed.placeholderText())

print()
print("=== Where / How alone explain what is still missing (the reported bug) ===")
v.place.setText("a temple hallway")
check("still nothing composed from a place alone", v.composed.text() == "")
check("advice now names Source and Action",
      "Source and Action" in v.compose_advice.text(), v.compose_advice.text())
check("Generate stays disabled", not v.generate_effect_button.isEnabled())

v.treatment.setText("comedic echo")
check("Where + How still composes nothing", v.composed.text() == "")
check("advice still guides", "Source and Action" in v.compose_advice.text())

print()
print("=== Source alone is enough to compose (partial input still works) ===")
v.source.setText("torch flame")
check("a source composes a prompt", v.composed.text().startswith("torch flame"),
      v.composed.text())
check("the guidance message is gone once something composes",
      "Source and Action" not in v.compose_advice.text(), v.compose_advice.text())

v.action.setText("crackling")
check("source + action compose the full pattern",
      v.composed.text() == "torch flame crackling in a temple hallway with comedic echo",
      v.composed.text())
check("Generate is enabled for a passing prompt", v.generate_effect_button.isEnabled())

print()
print("=== clearing Source and Action brings the guidance back ===")
v.source.setText("")
v.action.setText("")
check("Result empties again", v.composed.text() == "")
check("guidance returns (Where / How are still filled)",
      "Source and Action" in v.compose_advice.text())
check("Generate disabled again", not v.generate_effect_button.isEnabled())

v.place.setText("")
v.treatment.setText("")
check("a wholly empty form goes quiet, no leftover advice",
      v.compose_advice.text() == "")

print()

# SoundView.__init__ starts a VoiceListTask on its own pool; with no key it
# fails fast, but the queued failed->setText call and the pool thread must be
# let go of cleanly or the interpreter aborts on Windows at shutdown (the
# 0xC0000409 in CLAUDE.md). Drain both before exiting.
v._audio_pool.waitForDone(3000)
app.processEvents()

if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL SOUND GUI CHECKS PASSED")
