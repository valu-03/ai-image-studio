"""Insights view — which vocabulary actually correlates with good results.

This is the payoff for rating. The realism linter only knows whether a term is
present; this knows whether it worked.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import history as hist  # noqa: E402

from .. import tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel, set_empty_hint  # noqa: E402


class InsightsView(QWidget):
    learned_toggled = pyqtSignal(bool)
    status = pyqtSignal(str)

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or T.PALETTES[T.DEFAULT_THEME]
        self.setup_ui()

    def setup_ui(self):
        self.summary = Badge("no data", "neutral")
        self.min_count = QSpinBox(minimum=1, maximum=20, value=1)
        self.min_count.setToolTip("Hide terms with fewer than this many rated samples")
        self.min_count.valueChanged.connect(self.reload)

        self.learned = QCheckBox("Prefer terms that rated well when composing")
        self.learned.toggled.connect(self.learned_toggled)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        controls = QHBoxLayout()
        controls.setSpacing(T.SPACE["sm"])
        controls.addWidget(self.summary)
        controls.addWidget(MutedLabel("Min samples"))
        controls.addWidget(self.min_count)
        controls.addWidget(refresh)
        controls.addStretch(1)

        self.tree = QTreeWidget()
        set_empty_hint(self.tree, "Rate a few generations (1-5 stars) and the words that go with good results show up here.", "insights")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["TERM", "AVG RATING", "SAMPLES"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 380)

        self.hint = MutedLabel(
            "Rate your generations and this table stops being empty. It is the only thing "
            "here that measures whether a phrase actually worked, rather than whether it "
            "was present."
        )

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("What actually works"))
        card.body.addWidget(self.hint)
        card.body.addLayout(controls)
        card.body.addWidget(self.learned)
        card.body.addWidget(self.tree, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)

        self.reload()

    def set_palette_tokens(self, palette):
        self._palette = palette
        self.reload()

    def reload(self):
        entries = hist.load()
        rated = [e for e in entries if e.get("rating") is not None]
        self.tree.clear()

        if not rated:
            self.summary.set_status("neutral", "0 rated")
            root = QTreeWidgetItem(["Nothing rated yet", "", ""])
            self.tree.addTopLevelItem(root)
            return

        self.summary.set_status("accent", "{} rated".format(len(rated)))
        stats = hist.term_stats(entries)
        minimum = self.min_count.value()

        for layer in hist.LAYERS:
            rows = [(t, s) for t, s in stats[layer].items() if s["n"] >= minimum]
            if not rows:
                continue
            rows.sort(key=lambda r: (-r[1]["mean"], -r[1]["n"]))
            parent = QTreeWidgetItem([layer.upper(), "", ""])
            parent.setForeground(0, QBrush(QColor(self._palette["text_muted"])))
            self.tree.addTopLevelItem(parent)
            for term, stat in rows:
                child = QTreeWidgetItem([term, "{:.2f}".format(stat["mean"]), str(stat["n"])])
                if stat["mean"] >= 4:
                    colour = self._palette["success"]
                elif stat["mean"] <= 2:
                    colour = self._palette["error"]
                else:
                    colour = self._palette["text"]
                for column in range(3):
                    child.setForeground(column, QBrush(QColor(colour)))
                child.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
                child.setTextAlignment(2, Qt.AlignmentFlag.AlignRight)
                parent.addChild(child)
            parent.setExpanded(True)

        self.status.emit("Insights from {} rated generation(s)".format(len(rated)))
