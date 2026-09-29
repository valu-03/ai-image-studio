"""The sixteen shortcuts that existed and could not be found, and the guides.

THE SHORTCUTS WERE ALL INVISIBLE. They were registered with addAction(), which
binds the key and shows nothing, and ui/theme.py had styled a QMenuBar since
before there was one to style. The menus are generated from the SAME list the
shortcuts come from, which is the point: the previous hardcoded copy of the nav
shortcuts drifted out of step every time a section was added, and build_actions'
own comment says so.

THE GUIDES WERE WRITTEN AND UNREACHABLE. workflows/*.md is sixteen files of real
onboarding with zero references from any code path, and it was not bundled into
the .exe either - so for anyone running the built app it did not exist at all.

ONE SENTENCE, THREE SURFACES. ui/hints.py holds the description of each rail
section; the rail tooltip, the Go menu's status tip and the section's own intro
line all read it, so they cannot disagree.

THE MENU BAR COSTS VERTICAL SPACE, and that is the subtle part. At 33px it took
enough off the canvas to compress Compose's character-library card until its
buttons overlapped by one to three pixels at the 1100x700 minimum - caught by
test_layout.py, not by reading. Raising the window minimum would have pushed the
app past what a 1366x768 laptop can display, so the chrome gave the pixels back
instead. This suite pins the bar's height so a future style change cannot
quietly reintroduce the overlap.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_ASSUME_YES", "1")

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-menu-empty.env"
_EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.hints import NAV_HINTS  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow, NAV_ITEMS  # noqa: E402
from ui.views.guides import (  # noqa: E402
    GuidesDialog, guide_files, guides_dir, title_for,
)

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.resize(1100, 700)
win.show()
for _ in range(6):
    app.processEvents()

bar = win.menuBar()
menus = {a.menu().title(): a.menu() for a in bar.actions() if a.menu()}


print("=== THERE IS A MENU BAR, AND IT HOLDS EVERY SHORTCUT ===")
check("five menus, File first",
      [a.menu().title() for a in bar.actions() if a.menu()]
      == ["&File", "&Go", "&Compose", "&View", "&Help"],
      str(sorted(menus)))
entries = {}
for title, menu in menus.items():
    for action in menu.actions():
        entries[action.text()] = action.shortcut().toString()
check("every shortcut in the app is reachable from a menu",
      len(entries) == 22, "{} entries: {}".format(len(entries), sorted(entries)))
check("...and none of them is a dead key",
      all(seq for seq in entries.values()),
      str([k for k, v in entries.items() if not v]))


print()
print("=== THE GO MENU IS GENERATED FROM NAV_ITEMS, NOT COPIED ===")
go = [a.text() for a in menus["&Go"].actions()]
check("one entry per rail section, in rail order",
      go == [label for _k, label in NAV_ITEMS[:10]], str(go))
keys = [a.shortcut().toString() for a in menus["&Go"].actions()]
check("Ctrl+1..9 then Ctrl+0 - the tenth cannot be Ctrl+10",
      keys == ["Ctrl+{}".format((i + 1) % 10) for i in range(10)], str(keys))
check("every Go entry carries the section's own sentence as a status tip",
      all(a.statusTip() for a in menus["&Go"].actions()))
check("...and it is hints.py's sentence, not a second copy",
      [a.statusTip() for a in menus["&Go"].actions()]
      == [NAV_HINTS[k] for k, _l in NAV_ITEMS[:10]])

# Triggering a menu entry must actually navigate - a menu of dead labels would
# pass every check above.
# THE BUG THIS FOUND. QAction.triggered passes a `checked` bool, and a lambda
# with one defaulted parameter still ACCEPTS one positional argument - so
# `lambda k=key: self.go_to(k)` was called as go_to(False), matched no route
# and no nav button, and returned silently. Ctrl+1..Ctrl+0 had never
# navigated, for as long as they had existed, because nothing ever triggered
# one. Every entry is exercised now, not just one.
for index, (key, label) in enumerate(NAV_ITEMS[:10]):
    menus["&Go"].actions()[index].trigger()
    app.processEvents()
    check("triggering {!r} actually goes there".format(label),
          win.stack.currentWidget() is win.views[key],
          type(win.stack.currentWidget()).__name__)
menus["&Go"].actions()[0].trigger()
app.processEvents()

# And the silence that hid it.
win.go_to("no-such-section")
check("an unknown section no longer fails silently",
      "no-such-section" in win.statusBar().currentMessage(),
      win.statusBar().currentMessage()[:60])
check("...and says it is a bug rather than blaming the user",
      "not something you did" in win.statusBar().currentMessage())


print()
print("=== THE RAIL SAYS WHAT EACH SECTION IS FOR ===")
check("every rail button has a tooltip - NavButton never set one before",
      all(b.toolTip() for b in win.nav_buttons.values()),
      str([k for k, b in win.nav_buttons.items() if not b.toolTip()]))
check("...and it is the same sentence the menu uses",
      all(win.nav_buttons[k].toolTip() == NAV_HINTS[k] for k, _l in NAV_ITEMS))
check("hints.py covers every rail key, so none can be silently empty",
      {k for k, _l in NAV_ITEMS} <= set(NAV_HINTS),
      str({k for k, _l in NAV_ITEMS} - set(NAV_HINTS)))


print()
print("=== THE GUIDES ARE THERE AND THEY RENDER ===")
files = guide_files()
check("the guides folder is found", guides_dir().exists(), str(guides_dir()))
check("all seventeen guides are listed", len(files) == 17, str(len(files)))
check("README comes first - it is the index the others assume",
      files[0].name == "README.md", files[0].name)
check("each one's title is read from its own first heading",
      all(title_for(p) for p in files))
check("...rather than from a table that could drift",
      title_for(files[1]).lower() != files[1].stem.replace("-", " ").lower(),
      title_for(files[1]))

dialog = GuidesDialog(win)
check("the dialog lists every guide", dialog.list.count() == len(files))
check("the new static-ad guide is picked up with no code change",
      any(p.name == "creative-static-ad.md" for p in files),
      str([p.name for p in files]))
dialog.list.setCurrentRow(1)
rendered = dialog.view.toPlainText()
check("selecting one renders it", len(rendered) > 500, str(len(rendered)))
check("...as rendered text, not raw markdown",
      "##" not in rendered and "**" not in rendered, rendered[:60])
check("the first-run guide is among them",
      any(p.name == "ai-creator-workflow.md" for p in files))
dialog.close()

spec = (ROOT / "AIVideoStudio.spec").read_text(encoding="utf-8")
check("the frozen build bundles workflows/, or the .exe has no guides at all",
      '("workflows", "workflows")' in spec)


print()
print("=== THE MENU BAR DOES NOT COST THE LAYOUT ITS PIXELS ===")
# 33px was enough to overlap Compose's library buttons at the 1100x700 minimum.
check("the bar is trimmed, not generous", bar.height() <= 27, str(bar.height()))
check("...and the window minimum is unchanged, so small laptops still fit",
      (win.minimumWidth(), win.minimumHeight()) == (1100, 700),
      str((win.minimumWidth(), win.minimumHeight())))


print()
print("=== SEVEN SECTIONS THAT SAID NOTHING NOW INTRODUCE THEMSELVES ===")
from PyQt6.QtWidgets import QLabel  # noqa: E402
for key, label in NAV_ITEMS:
    view = win.views[key]
    texts = [lb.text() for lb in view.findChildren(QLabel)]
    has_intro = any(NAV_HINTS[key] == t for t in texts)
    # Images and Ads are the two exceptions, and deliberately: both are dense
    # containers with no vertical room at the 700px floor, and both still carry
    # the sentence on the rail button and in the Go menu.
    if key in ("images", "ads"):
        check("{}: intro deliberately omitted (no room at the minimum size)"
              .format(label), not has_intro)
    elif key in ("look", "assistant", "activity"):
        check("{}: had its own intro already, left alone".format(label), True)
    else:
        check("{}: introduces itself".format(label), has_intro,
              str(texts[:2]))


print()
win.close()
app.processEvents()
del win

if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL MENU AND GUIDES CHECKS PASSED")
