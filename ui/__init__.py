"""UI layer for AI Video Studio — built to pyqt6_system_prompt.md.

tokens.py       design tokens (palette, 4px spacing grid, radius, type scale)
assets.py       asset configuration table — every path and icon the UI loads
theme.py        ThemeManager — builds a complete QSS sheet per palette
widgets.py      reusable components (Card, Badge, NavButton, StarRating, ...)
workers.py      QRunnable / QThreadPool generation, so the UI never blocks
spec_editor.py  the character spec form
lint_panel.py   live realism scoring
views/          the five canvas views behind the navigation rail
main_window.py  the shell: rail + top bar + QStackedWidget

No module here composes or scores a prompt, or talks to an image API directly —
that all lives in tools/.
"""
