"""UI polish gate: accessibility names, keyboard reach, readable status, empty states.

Each of these was a finding from an audit of the real window, fixed once and
kept fixed here:
  - 125 inputs, combos and icon-only buttons had no accessible name, so a
    screen reader announced "combo box" with nothing after it;
  - the credits balance was a QLabel clickable by mouse only;
  - the status bar printed full local paths and deep links, cutting off the
    part that said what to do;
  - tab labels were elided to "Purp...", "Subj...";
  - empty lists were blank boxes that did not say what belongs there.
Offscreen; uses its own settings key, never the user's.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
if "QT_QPA_FONTDIR" not in os.environ and _FONTS.is_dir():
    os.environ["QT_QPA_FONTDIR"] = str(_FONTS)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QAbstractSpinBox, QApplication, QComboBox, QLineEdit,
    QPlainTextEdit, QPushButton, QTabBar, QTextEdit)

from ui import theme as theme_mod  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402
from ui.widgets import status_line  # noqa: E402

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

print("--- every control has a name a screen reader can say ---")
kinds = (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit)
unnamed = []
for widget in win.findChildren(kinds):
    if isinstance(widget.parentWidget(), (QComboBox, QAbstractSpinBox)):
        continue
    if isinstance(widget, QAbstractButton) and widget.text().strip():
        continue
    if not widget.accessibleName():
        unnamed.append("{} tip={!r}".format(type(widget).__name__, widget.toolTip()[:30]))
check("no unnamed control", not unnamed, "; ".join(unnamed[:5]))
check("the rail items are named", all(b.accessibleName() for b in win.nav_buttons.values()))

print("--- keyboard ---")
def policy(widget):
    """focusPolicy() as a plain int: PyQt6 hands back an int here, not the enum."""
    value = widget.focusPolicy()
    return int(getattr(value, "value", value))


check("the credits balance is a real button", isinstance(win.credits_badge, QPushButton))
check("...that the keyboard can reach",
      policy(win.credits_badge) != Qt.FocusPolicy.NoFocus.value)
# The rail is an exclusive QButtonGroup: Qt makes only the CHECKED item a Tab
# stop and the arrow keys move between items - the radio-group pattern.
checked = [b for b in win.nav_buttons.values() if b.isChecked()]
check("Tab reaches the current rail item (arrows move between items)",
      len(checked) == 1 and policy(checked[0]) != Qt.FocusPolicy.NoFocus.value)

print("--- tabs show whole labels ---")
elided = [bar for bar in win.findChildren(QTabBar) if bar.elideMode() != Qt.TextElideMode.ElideNone]
check("no tab bar elides its labels", not elided, str(len(elided)))
check("a too-narrow bar scrolls instead", all(bar.usesScrollButtons() for bar in win.findChildren(QTabBar)))

print("--- the status bar is one readable line ---")
raw = ("ELEVENLABS_API_KEY not set in C:\\Users\\Someone\\My Projects\\AI Video Studio\\.env - "
       "cannot reach ElevenLabs.\nGet a key at https://elevenlabs.io/app/settings/api-keys")
check("first line only, path shortened to the file",
      status_line(raw) == "ELEVENLABS_API_KEY not set in .env - cannot reach ElevenLabs.", status_line(raw))
check("a link shows as its site", status_line("See https://kie.ai/docs/x for help") == "See kie.ai for help")
check("fractions and scores are left alone", status_line("Score 8/8 - ready") == "Score 8/8 - ready")
check("long text is capped", len(status_line("x" * 400)) <= 160)
win.show_status(raw)
check("a view's message reaches the bar shortened", win.statusBar().currentMessage() == status_line(raw))
check("...with the whole message on the tooltip", win.statusBar().toolTip() == raw)

print("--- empty lists say what goes there ---")
for name, view in (("character library", win.compose_view.library),
                   ("history", win.history_view.table)):
    check("{} carries an empty-state hint".format(name), getattr(view, "_empty_hint", None) is not None)
check("the character library hint names the action that fills it",
      "Save character" in win.compose_view.library._empty_hint.text)

print("--- Compose generation options say what they are ---")
c = win.compose_view
check("provider/resolution/format show their own names",
      [c.gen_provider.itemText(0), c.gen_resolution.itemText(0), c.gen_output_format.itemText(0)]
      == ["Provider", "Resolution", "Format"])
check("...and still mean 'use Settings'", c.provider_override() is None and c.options_override() == {})

print("--- appearance settings ---")
sv = win.settings_view
sv.text_size.setCurrentIndex(sv.text_size.count() - 1)
app.processEvents()
check("Text size changes the sheet", theme.text_scale == sv.text_size.currentData())
check("...and is remembered", float(win.settings.value("text_scale")) == theme.text_scale)
sv.text_size.setCurrentIndex(0)
sv.reduce_motion.setChecked(True)
check("Reduce motion switches animation off", theme_mod.REDUCED_MOTION and theme_mod.motion_ms(220) == 0)
check("...and is remembered", win.settings.value("reduce_motion") == "true")
sv.reduce_motion.setChecked(False)
check("...and back on", not theme_mod.REDUCED_MOTION)

print("--- the theme switch repaints theme colours ---")
theme.apply("light")
app.processEvents()
check("theme.color follows the applied palette",
      theme_mod.color("primary").name().upper() == theme.palette["primary"].upper())
theme.apply("dark")

win.settings.remove("text_scale")
win.settings.remove("reduce_motion")
win.close()
app.processEvents()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL UI POLISH CHECKS PASSED")
