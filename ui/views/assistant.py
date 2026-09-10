"""Assistant category - the two ways the model helps with a prompt.

Chat is the running conversation (AdvisorView); Prompt tools is the set of
one-shot helpers (BriefView: idea -> spec, upgrade a prompt, critique an
image, reverse-engineer a photo). Both feed the Images Compose form; grouping
them means the rail says "ask for help" once, not twice.

Thin container, like ImagesView - MainWindow reaches in for `self.advisor_view`
and `self.brief_view`.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from ..widgets import MutedLabel
from .advisor import AdvisorView
from .brief_view import BriefView


class AssistantView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.advisor = AdvisorView(bank)
        self.brief = BriefView(bank)
        self.advisor.status.connect(self.status)
        self.brief.status.connect(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.advisor, "Chat")
        self.tabs.addTab(self.brief, "Prompt tools")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(MutedLabel(
            "Ask the in-app expert for help. Chat is a running conversation; "
            "Prompt tools are one-shot helpers. Both hand what they find back "
            "to the Images prompt."))
        layout.addWidget(self.tabs)

    def show_chat(self):
        self.tabs.setCurrentIndex(0)

    def show_tools(self):
        self.tabs.setCurrentIndex(1)

    def refresh(self):
        current = self.tabs.currentWidget()
        if current is self.brief:
            self.brief.refresh_context()
        elif hasattr(current, "refresh"):
            current.refresh()

    def set_palette_tokens(self, palette):
        self.advisor.set_palette_tokens(palette)
