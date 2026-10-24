"""Screenshots of every section and sub-tab, both themes, minimum and default size.

    python tests/screenshot_all.py <out_dir>            every section
    python tests/screenshot_all.py <out_dir> images     only sections whose key contains "images"

Not a test (run_all.py does not run it): the before/after evidence for UI work,
taken the same way test_layout.py walks the window - offscreen, the real fonts,
a throwaway settings key, so the user's saved state is never read or written.
One PNG per (theme, size, section, tab path), named so they sort together.
"""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
if "QT_QPA_FONTDIR" not in os.environ and _FONTS.is_dir():
    os.environ["QT_QPA_FONTDIR"] = str(_FONTS)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Screenshots")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from ui.main_window import NAV_ITEMS, MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

SIZES = [("min", 1100, 700), ("default", 1440, 900)]


def tab_paths(view):
    """Every reachable (nested) tab combination, as in test_layout.py."""
    tabs = getattr(view, "tabs", None)
    if not isinstance(tabs, QTabWidget):
        return [[]]
    paths = []
    for i in range(tabs.count()):
        for sub in tab_paths(tabs.widget(i)):
            paths.append([(tabs, i)] + sub)
    return paths


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "tab"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out = Path(argv[0])
    only = argv[1].lower() if len(argv) > 1 else ""
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    theme = ThemeManager(app)
    count = 0
    for theme_name in ("dark", "light"):
        theme.apply(theme_name)
        win = MainWindow(theme)
        win.show()
        app.processEvents()
        for size_name, width, height in SIZES:
            win.resize(width, height)
            app.processEvents()
            for n, (key, label) in enumerate(NAV_ITEMS, 1):
                if only and only not in key.lower():
                    continue
                win.go_to(key)
                view = win.views[key]
                for path in tab_paths(view):
                    for tw, idx in path:
                        tw.setCurrentIndex(idx)
                    # go_to() moves the checked rail item, not focus: without
                    # this the item focused at launch keeps its focus ring in
                    # every shot, which no click-driven session would show.
                    if app.focusWidget() is not None:
                        app.focusWidget().clearFocus()
                    for _ in range(3):
                        app.processEvents()
                    tabs ="_".join(slug(tw.tabText(idx)) for tw, idx in path) or "main"
                    name = "{}_{}_{:02d}-{}_{}.png".format(theme_name, size_name, n, slug(label), tabs)
                    win.grab().save(str(out / name))
                    count += 1
        win.close()
        app.processEvents()
    print("{} screenshots -> {}".format(count, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
