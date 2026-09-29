"""Giving the app a key from inside the app, and the controls that used to freeze.

Until now the only way to supply a key was to hand-write a .env file next to the
source - which the frozen .exe does not even sit beside, so for anyone running
the built app there was no way at all. Settings takes a key now.

THREE THINGS THIS PROTECTS.

A key is a secret. `write_env_value()` never returns or logs the value, the input
is EchoMode.Password, and the status line says the VARIABLE was saved, never the
key. This suite asserts the secret does not appear in any message.

The writer must agree with the reader. read_env() strips quotes and skips
comments, so the writer lives in the same module rather than in the GUI, and it
REWRITES rather than appends - a second KIE_API_KEY=... line would leave
read_env() preferring whichever came last, which looks exactly like an expired
key.

Re-check must reach further than two badges. Compose's Vision QC checkbox and
Coherence button were the app's only pre-disabled controls, and both decided ONCE
at construction - so adding a key and pressing "Re-check .env" refreshed two
badges in Settings and left these dead until the app was restarted.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_ASSUME_YES", "1")

# A scratch .env this suite owns outright, so nothing here can touch a real key.
ENV_FILE = Path(tempfile.gettempdir()) / "aivs-keyentry.env"
ENV_FILE.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(ENV_FILE)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication, QLineEdit  # noqa: E402

import ask_llm as al  # noqa: E402
import generate_image as gi  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

fails = []
SECRET = "sk-do-not-leak-me-0123456789"


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== write_env_value() AGREES WITH read_env() ===")
scratch = Path(tempfile.gettempdir()) / "aivs-keyentry-scratch.env"
scratch.write_text("# a comment\nOTHER=keepme\nKIE_API_KEY=old\n", encoding="utf-8")
gi.write_env_value("KIE_API_KEY", "fresh", scratch)
text = scratch.read_text(encoding="utf-8")
check("the variable is replaced", "KIE_API_KEY=fresh" in text, repr(text))
check("...not appended beside the old one - read_env would prefer the last",
      text.count("KIE_API_KEY") == 1, repr(text))
check("comments survive", "# a comment" in text)
check("other variables survive", "OTHER=keepme" in text)

gi.write_env_value("NEW_VAR", "v", scratch)
check("a brand-new variable is added", "NEW_VAR=v" in
      scratch.read_text(encoding="utf-8"))
gi.write_env_value("NEW_VAR", "", scratch)
after = scratch.read_text(encoding="utf-8")
check("an empty value REMOVES it rather than leaving NEW_VAR=",
      "NEW_VAR" not in after, repr(after))
check("the writer returns a path, never the secret",
      isinstance(gi.write_env_value("X", "y", scratch), Path))
scratch.unlink()


print()
print("=== SETTINGS TAKES A KEY, AND DOES NOT SHOW IT ===")
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
sv = win.settings_view

messages = []
sv.status.connect(messages.append)

check("there is a key input", hasattr(sv, "key_input"))
check("...and it is masked", sv.key_input.echoMode() == QLineEdit.EchoMode.Password,
      str(sv.key_input.echoMode()))
check("there is a Get-a-key button", hasattr(sv, "get_key_button"))
check("...pointing at the provider's own page",
      sv.get_key_button.toolTip().startswith("http"), sv.get_key_button.toolTip())

sv.save_key()
check("saving with an empty box does nothing but ask",
      messages and "Paste a key" in messages[-1], str(messages[-1:]))

variable = gi.PROVIDERS[sv.provider.currentText()]["key"]
sv.key_input.setText(SECRET)
sv.save_key()
check("the key reaches .env", gi.env_value(variable) == SECRET)
check("the box is cleared afterwards", sv.key_input.text() == "")
check("the status names the VARIABLE, not the key",
      variable in messages[-1] and SECRET not in messages[-1], messages[-1])
check("...and the secret appears in NO message this suite has seen",
      not any(SECRET in m for m in messages), str(len(messages)))
check("the badge flips to set - that is the real confirmation",
      "set" in sv.key_badge.text(), sv.key_badge.text())


print()
print("=== RE-CHECK NOW REACHES THE CONTROLS THAT USED TO FREEZE ===")
# Both need a TEXT-model key, which is a different variable from the image one.
gi.write_env_value(al.KEY_VAR, "", ENV_FILE)
os.environ.pop(al.KEY_VAR, None)
win.compose_view.refresh_key_state()
check("with no text key, Vision QC is disabled",
      not win.compose_view.vision_qc_checkbox.isEnabled())
check("...and Coherence too", not win.compose_view.coherence_button.isEnabled())
check("...and the tooltip says where to get one",
      al.KEY_URL in win.compose_view.coherence_button.toolTip(),
      win.compose_view.coherence_button.toolTip()[:70])
check("...and points at Settings, which can now take it",
      "Settings" in win.compose_view.coherence_button.toolTip())

gi.write_env_value(al.KEY_VAR, "a-text-key", ENV_FILE)
check("the signal exists for Settings to emit", hasattr(sv, "keys_changed"))
sv.keys_changed.emit()
check("emitting it enables Vision QC without a restart",
      win.compose_view.vision_qc_checkbox.isEnabled())
check("...and Coherence", win.compose_view.coherence_button.isEnabled())
check("...and restores the real tooltip rather than the excuse",
      "optional everywhere" in win.compose_view.vision_qc_checkbox.toolTip(),
      win.compose_view.vision_qc_checkbox.toolTip()[:60])

gi.write_env_value(al.KEY_VAR, "", ENV_FILE)
sv.keys_changed.emit()
check("removing the key disables them again - the state is recomputed, not latched",
      not win.compose_view.coherence_button.isEnabled())


print()
print("=== THE KEY NEVER REACHED A LOG OR A WIDGET ===")
from PyQt6.QtWidgets import QLabel  # noqa: E402
leaked = [lb.text() for lb in win.findChildren(QLabel) if SECRET in lb.text()]
check("no label anywhere shows it", not leaked, str(leaked))
check("the input itself is empty by now", sv.key_input.text() == "")
check("...and .env is the only place it lives",
      SECRET in ENV_FILE.read_text(encoding="utf-8"))


print()
win.close()
app.processEvents()
del win
try:
    ENV_FILE.unlink()
except OSError:
    pass

if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL KEY ENTRY CHECKS PASSED")
