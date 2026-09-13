"""Live realism score — the same gate tools/realism_lint.py enforces on the CLI.

Row colours come from the active palette, so the panel re-renders on a theme
switch rather than keeping light-theme colours on a dark background.
"""

import sys
from pathlib import Path

from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QHBoxLayout, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import realism_lint as rl  # noqa: E402  (path set above)

from . import tokens as T  # noqa: E402
from .widgets import Badge, MutedLabel  # noqa: E402


class LintPanel(QWidget):
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or T.PALETTES[T.DEFAULT_THEME]
        self._text = ""
        self._bank = None
        self.score = 0
        self.passed = False

        self.badge = Badge("—", "neutral")
        self.verdict = MutedLabel("")

        header = QHBoxLayout()
        header.setSpacing(T.SPACE["sm"])
        header.addWidget(self.badge)
        header.addWidget(self.verdict, 1)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        # Qt QSS has no text-transform, so the uppercase header the design
        # tokens call for is set here.
        self.tree.setHeaderLabels(["", "LAYER", "DETAIL"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 28)
        self.tree.setColumnWidth(1, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addLayout(header)
        layout.addWidget(self.tree)

    def set_palette_tokens(self, palette):
        self._palette = palette
        if self._bank is not None:
            self.update_result(self._text, self._bank)

    def _row(self, mark, layer, detail, color_key):
        item = QTreeWidgetItem([mark, layer, detail])
        brush = QBrush(QColor(self._palette[color_key]))
        for column in range(3):
            item.setForeground(column, brush)
        self.tree.addTopLevelItem(item)

    def update_result(self, text, bank):
        """Re-run the linter and repaint. Returns True when the prompt passes."""
        self._text, self._bank = text, bank
        self.tree.clear()

        present, missing, banned, warns, negatives_present = rl.lint(text.lower(), bank)

        for _, cfg, hit in present:
            self._row("✓", cfg["label"], '"{}"'.format(hit), "success")
        for _, cfg, _ in missing:
            self._row("!", cfg["label"], cfg["fix"], "warning")
        for term in banned:
            self._row("✗", "Banned term", '"{}" breaks realism'.format(term), "error")
        for term in warns:
            self._row("~", "Soft warning", '"{}" does little on its own'.format(term), "warning")
        if not negatives_present:
            self._row("!", "Negative block", "append: " + ", ".join(bank["negatives"]), "warning")

        score = len(present)
        passed = score == 8 and not banned
        self.score, self.passed = score, passed
        self.badge.set_status("success" if passed else "danger", "{}/8".format(score))
        self.verdict.setText(
            "Ready to generate." if passed else "Fix the flagged items before generating."
        )
        return passed

    def show_checks(self, checks):
        """Render a pre-built check list (e.g. tools/vision_lint.py's output)
        rather than running realism_lint itself - a different scorer's data,
        reusing this same tree/badge/verdict shell so the two panels look
        consistent without update_result needing to change at all.
        """
        self.tree.clear()
        for item in checks:
            mark = "✓" if item["passed"] else "✗"
            color_key = "success" if item["passed"] else "error"
            detail = item["ok_text"] if item["passed"] else item["fix"]
            self._row(mark, item["label"], detail, color_key)

        total = len(checks)
        score = sum(1 for item in checks if item["passed"])
        passed = total > 0 and score == total
        self.score, self.passed = score, passed
        self.badge.set_status("success" if passed else "danger", "{}/{}".format(score, total))
        self.verdict.setText(
            "Matches the spec." if passed else "The model flagged some mismatches.")
