"""Activity category - what you learn from what you made.

History is the log of every generation; What works is the term-to-rating
correlation that log feeds. One is the raw record, the other the payoff -
they belong together, below the sections that make things.

Thin container - MainWindow reaches in for `self.history_view` and
`self.insights_view`.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from ..widgets import MutedLabel
from .history_view import HistoryView
from .insights import InsightsView


class ActivityView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.history = HistoryView(palette)
        self.insights = InsightsView(palette)
        self.history.status.connect(self.status)
        self.insights.status.connect(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.history, "History")
        self.tabs.addTab(self.insights, "What works")
        self.tabs.currentChanged.connect(self._reload_current)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(MutedLabel(
            "Every generation you've run, and what the ratings say works. "
            "Rate your results and this is where it pays off."))
        layout.addWidget(self.tabs)

    def show_history(self):
        self.tabs.setCurrentIndex(0)

    def show_insights(self):
        self.tabs.setCurrentIndex(1)

    def _reload_current(self, *_):
        self.tabs.currentWidget().reload()

    def refresh(self):
        self._reload_current()

    def set_palette_tokens(self, palette):
        self.history.set_palette_tokens(palette)
        self.insights.set_palette_tokens(palette)
