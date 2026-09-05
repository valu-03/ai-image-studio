"""AI Video Studio — desktop front end for the avatar workflow.

Run:
    python gui.py

A shell over tools/, not a reimplementation of it: prompts are composed by
build_prompt.compose() and scored by realism_lint.lint(), so the GUI and the CLI
can never disagree about what a good prompt is.
"""

import sys

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from ui import assets
from ui.main_window import MainWindow
from ui.theme import ThemeManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Video Studio")
    app.setOrganizationName("AI Video Studio")
    # Set on the application, not the window: this is what the taskbar and the
    # alt-tab switcher read, and it then applies to any dialog too.
    app.setWindowIcon(assets.icon("app"))

    theme = ThemeManager(app)
    settings = QSettings("AI Video Studio", "Studio")
    theme.apply(settings.value("theme") or ThemeManager.detect())

    window = MainWindow(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
