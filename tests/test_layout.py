"""Layout gate: overlapping text, clipped labels, images that escape their card.

Every other quality rule in this project is a linter rather than an opinion, and
layout was the last thing still being judged by squinting at a screenshot. This
walks all seven sections and their sub-tabs, in both themes, at the declared
minimum window size and at the default one, and asserts three things that are
mechanically checkable:

  1. no two widgets in the same layout overlap   (a layout that overlaps its own
     items is drawing text on top of text)
  2. no non-wrapping label is narrower than its text  (that is a clipped label)
  3. no ImagePreview escapes its parent's content box

Plus the icon-table subset check: assets.ICONS and make_icons.ICON_NAMES are two
hand-maintained tables with nothing cross-checking them, and assets.icon()
returns an empty QIcon rather than raising - which is exactly how the nav icons
came out blank once before.

Offscreen; reads the real character folder but never writes to it.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox, QLabel,
    QLineEdit, QPushButton, QStackedLayout, QTabWidget, QWidget)

import make_icons  # noqa: E402
from ui import assets  # noqa: E402
from ui.main_window import NAV_ITEMS, MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402
from ui.widgets import ImagePreview  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


app = QApplication(sys.argv)
theme = ThemeManager(app)


# --------------------------------------------------------------------------- #
# The three inspections
# --------------------------------------------------------------------------- #
def layout_overlaps(root):
    """[(parent, a, b)] for widgets that share a layout and intersect."""
    found = []
    for parent in root.findChildren(QWidget):
        layout = parent.layout()
        # A stacked layout puts every page at the same geometry on purpose.
        if layout is None or isinstance(layout, QStackedLayout):
            continue
        items = []
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None and widget.isVisible() and not widget.size().isEmpty():
                items.append(widget)
        for i, first in enumerate(items):
            for second in items[i + 1:]:
                if first.geometry().intersects(second.geometry()):
                    found.append((parent, first, second))
    return found


def clipped_labels(root):
    """Labels too narrow for their own text, which is how text collides."""
    bad = []
    for label in root.findChildren(QLabel):
        if not label.isVisible() or label.wordWrap() or not label.text().strip():
            continue
        if label.pixmap() is not None and not label.pixmap().isNull():
            continue
        # 2px of slack: Qt's own width rounding is not worth a failure.
        if label.sizeHint().width() > label.width() + 2:
            bad.append(label)
    return bad


def escaped_previews(root):
    """Image previews drawn outside the box their parent gives them."""
    out = []
    for preview in root.findChildren(ImagePreview):
        parent = preview.parentWidget()
        if not preview.isVisible() or parent is None:
            continue
        if not parent.contentsRect().contains(preview.geometry()):
            out.append((preview, parent))
    return out


def in_scroll_area(widget):
    """True when a widget is the scrolled content of a QAbstractScrollArea.

    Such content is meant to be bigger than the thing showing it, so the
    containment rule below does not apply to it.
    """
    node = widget
    while node is not None:
        if isinstance(node.parentWidget(), QAbstractScrollArea):
            return True
        if node.parentWidget() is not None and node.parentWidget().objectName() == \
                "qt_scrollarea_viewport":
            return True
        node = node.parentWidget()
    return False


def overflowing(root):
    """Layout items placed outside the widget whose layout placed them.

    Qt does this when the items' minimum sizes cannot fit the space available -
    which is how a card ends up with its contents spilling past its own border.
    """
    out = []
    for parent in root.findChildren(QWidget):
        layout = parent.layout()
        if layout is None or isinstance(layout, QStackedLayout):
            continue
        if in_scroll_area(parent):
            continue
        box = parent.contentsRect().adjusted(-2, -2, 2, 2)   # 2px of slack
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is None or not widget.isVisible() or widget.size().isEmpty():
                continue
            if not box.contains(widget.geometry()):
                out.append((parent, widget))
    return out


CONTROLS = (QLineEdit, QComboBox, QAbstractSpinBox, QPushButton)


def crushed(root):
    """Controls given less height than they need to draw themselves.

    This is the signature of a layout that ran out of room: Qt does not refuse,
    it shares the shortfall out and violates every minimum at once. The Cats
    story form asked for 700px of a 537px page and came out with each field 9px
    tall, its text sliced through the middle - and none of the checks above saw
    it, because nothing overlapped and nothing was too NARROW.

    A combo's or spin box's internal editor is exempt: it is the style's own
    child, sized by the style rather than by any layout here.
    """
    out = []
    for widget in root.findChildren(QWidget):
        if not widget.isVisible() or widget.size().isEmpty():
            continue
        if isinstance(widget, CONTROLS):
            if isinstance(widget.parentWidget(), (QComboBox, QAbstractSpinBox)):
                continue
            need = widget.minimumSizeHint().height()
        elif isinstance(widget, QLabel) and widget.text().strip() and not widget.wordWrap():
            if widget.pixmap() is not None and not widget.pixmap().isNull():
                continue
            need = widget.sizeHint().height()
        else:
            continue
        if need > 0 and widget.height() + 2 < need:
            out.append((widget, widget.height(), need))
    return out


def unwrapped(root):
    """Wrapping labels given fewer lines than their text needs.

    minimumSizeHint is no use for these - a wrapping label reports the height it
    would need at its minimum width - so ask heightForWidth at the width it
    actually got. This is how a paragraph loses its last line silently.
    """
    out = []
    for label in root.findChildren(QLabel):
        if not label.isVisible() or not label.wordWrap() or not label.text().strip():
            continue
        need = label.heightForWidth(label.width())
        if need > 0 and label.height() + 2 < need:
            out.append((label, label.height(), need))
    return out


def sub_tabs(view):
    """Every sub-tab of a section view, or [None] when it has none."""
    tabs = getattr(view, "tabs", None)
    if isinstance(tabs, QTabWidget):
        return list(range(tabs.count()))
    return [None]


# --------------------------------------------------------------------------- #
print("--- icon tables agree ---")
missing = sorted(make_icons.ICON_NAMES - set(assets.ICONS))
check("every generated icon is registered", not missing, ", ".join(missing))
blank = []
for name in sorted(assets.ICONS):
    for active in (False, True):
        if assets.icon(name, active=active).isNull():
            blank.append("{}{}".format(name, "-active" if active else ""))
check("no registered icon is blank", not blank, ", ".join(blank))
check("the app mark exists", "app" in assets.ICONS)
check("the app mark renders", not assets.icon("app").pixmap(64, 64).isNull())


# --------------------------------------------------------------------------- #
SIZES = [("minimum", 1100, 700), ("default", 1440, 900)]

for theme_name in ("dark", "light"):
    theme.apply(theme_name)
    win = MainWindow(theme)
    win.show()
    app.processEvents()

    for size_name, width, height in SIZES:
        win.resize(width, height)
        app.processEvents()

        overlaps = clipped = escaped = spilled = squashed = cut = 0
        worst = []
        spills = []
        squashes = []
        for key, label in NAV_ITEMS:
            win.go_to(key)
            view = win.views[key]
            for tab_index in sub_tabs(view):
                if tab_index is not None:
                    view.tabs.setCurrentIndex(tab_index)
                app.processEvents()

                for parent, a, b in layout_overlaps(view):
                    overlaps += 1
                    if len(worst) < 4:
                        worst.append("{}/{}: {} x {}".format(
                            label, type(parent).__name__,
                            type(a).__name__, type(b).__name__))
                for widget in clipped_labels(view):
                    clipped += 1
                    if len(worst) < 4:
                        worst.append("{}: clipped {!r}".format(
                            label, widget.text()[:40]))
                for preview, parent in escaped_previews(view):
                    escaped += 1
                    if len(worst) < 4:
                        worst.append("{}: preview outside {}".format(
                            label, type(parent).__name__))
                for parent, widget in overflowing(view):
                    spilled += 1
                    if len(spills) < 4:
                        spills.append("{}: {} spills out of {}".format(
                            label, type(widget).__name__, type(parent).__name__))
                for widget, got, need in crushed(view):
                    squashed += 1
                    if len(squashes) < 4:
                        squashes.append("{}: {} {}px of {}px {!r}".format(
                            label, type(widget).__name__, got, need,
                            widget.text()[:24] if hasattr(widget, "text") else ""))
                for widget, got, need in unwrapped(view):
                    cut += 1
                    if len(squashes) < 4:
                        squashes.append("{}: paragraph {}px of {}px {!r}".format(
                            label, got, need, widget.text()[:24]))

        tag = "{} {}".format(theme_name, size_name)
        check("{} - nothing overlaps".format(tag), overlaps == 0,
              "{} overlap(s)  {}".format(overlaps, "; ".join(worst)))
        check("{} - no clipped label".format(tag), clipped == 0,
              "{} clipped  {}".format(clipped, "; ".join(worst)))
        check("{} - previews stay in their cards".format(tag), escaped == 0,
              "{} escaped".format(escaped))
        check("{} - nothing spills out of its card".format(tag), spilled == 0,
              "{} spill(s)  {}".format(spilled, "; ".join(spills)))
        check("{} - no control is crushed below its minimum".format(tag), squashed == 0,
              "{} crushed  {}".format(squashed, "; ".join(squashes)))
        check("{} - no paragraph loses a line".format(tag), cut == 0,
              "{} cut  {}".format(cut, "; ".join(squashes)))

    win.close()
    app.processEvents()


# --------------------------------------------------------------------------- #
print("--- the compose columns share space sensibly ---")
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()
widths = {}
for size_name, width, height in [("minimum", 1100, 700), ("default", 1440, 900),
                                 ("wide", 1920, 1080)]:
    win.resize(width, height)
    for _ in range(4):
        app.processEvents()
    widths[size_name] = win.compose_view.prompt_view.width()

check("the prompt is usable at the minimum window", widths["minimum"] >= 230,
      "{}px".format(widths["minimum"]))
check("the prompt is comfortable at the default", widths["default"] >= 400,
      "{}px".format(widths["default"]))
# The regression this guards: the form column took every spare pixel and the
# prompt stayed narrow no matter how wide the window got.
check("extra width goes to the prompt, not the form",
      widths["wide"] > widths["default"] > widths["minimum"], str(widths))
check("the form column is capped",
      win.compose_view.splitter.sizes()[0] <= 420,
      str(win.compose_view.splitter.sizes()))
win.close()
app.processEvents()

print("--- the variants grid is even, whatever shape the images are ---")
from PyQt6.QtGui import QColor, QImage  # noqa: E402

from ui.views.variants import COLUMNS, VariantsView  # noqa: E402
from ui.widgets import ResultCard  # noqa: E402

import build_prompt as bp  # noqa: E402
import tempfile  # noqa: E402

theme.apply("dark")
shapes = {}
tmp = Path(tempfile.mkdtemp(prefix="aivs-layout-"))
for name, (w, h) in {"1-1": (512, 512), "9-16": (288, 512), "16-9": (512, 288)}.items():
    image = QImage(w, h, QImage.Format.Format_RGB32)
    image.fill(QColor("#334155"))
    path = tmp / "{}.png".format(name)
    image.save(str(path))
    shapes[name] = str(path)

bank = bp.load_bank()


def grid_widths(assignment, count=6, width=1180):
    view = VariantsView(bank)
    view.resize(width, 700)
    view.show()
    for index in range(count):
        card = ResultCard(index, "seed {}".format(index + 1))
        card.seed = index + 1
        view.cards[index] = card
        view.grid.addWidget(card, index // COLUMNS, index % COLUMNS)
    app.processEvents()
    for index, shape in enumerate(assignment):
        view.cards[index].preview.load(shapes[shape])
    for _ in range(6):
        app.processEvents()
    widths = [c.geometry().width() for _, c in sorted(view.cards.items())]
    view.close()
    app.processEvents()
    return widths


# The case that used to crash outright: six portrait images in a resizable
# scroll area drove the size hint up without ever converging.
portrait = grid_widths(["9-16"] * 6)
check("six 9:16 images do not run away", max(portrait) - min(portrait) <= 2, str(portrait))

# The case behind the report: one wider image made its whole column wider, and
# seeds 3 and 6 are the two cards in column index 2.
mixed = grid_widths(["9-16", "1-1", "16-9", "1-1", "9-16", "16-9"])
check("mixed aspect ratios stay even", max(mixed) - min(mixed) <= 2, str(mixed))

partial = grid_widths(["1-1", "1-1", "1-1"], count=6)
check("half-finished batch stays even", max(partial) - min(partial) <= 2, str(partial))

check("the hint no longer follows the pixmap",
      ImagePreview().sizeHint() == ImagePreview().minimumSize())

import shutil  # noqa: E402

shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL LAYOUT CHECKS PASSED")
