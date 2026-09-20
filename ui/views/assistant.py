"""Assistant category - the three ways this app helps with a prompt.

Chat is the running conversation (AdvisorView); Prompt tools is the set of
one-shot helpers (BriefView: idea -> spec, upgrade a prompt, critique an
image, reverse-engineer a photo). Both feed the Images Compose form; grouping
them means the rail says "ask for help" once, not twice.

Anatomy (AnatomyView) is the odd one out and deliberately so: it teaches the
SHAPE of a prompt rather than writing one. It feeds Compose nothing, calls no
model, and answers a different question - "what are the parts of a prompt like
this, and which ones have I actually filled in?" It belongs here because it is
help with a prompt; it stays read-only because the moment it offered to fix a
prompt it would stop teaching.

Thin container, like ImagesView - MainWindow reaches in for `self.advisor_view`
and `self.brief_view`.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from ..widgets import MutedLabel
from .advisor import AdvisorView
from .anatomy import AnatomyView
from .brief_view import BriefView


class AssistantView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.advisor = AdvisorView(bank)
        self.brief = BriefView(bank)
        self.anatomy = AnatomyView()
        self.advisor.status.connect(self.status)
        self.brief.status.connect(self.status)
        self.anatomy.status.connect(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.advisor, "Chat")
        self.tabs.addTab(self.brief, "Prompt tools")
        self.tabs.addTab(self.anatomy, "Anatomy")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        # Kept to three lines at the minimum window width on purpose: a fourth
        # wrapped line here costs the tab pages ~20px of height, which is
        # enough to tip BriefView's image card into an overlap at 1100x700.
        # tests/test_layout.py catches that; the eye does not.
        layout.addWidget(MutedLabel(
            "Ask the in-app expert for help. Chat is a conversation; Prompt tools "
            "are one-shot helpers; Anatomy teaches the shape of a prompt."))
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
