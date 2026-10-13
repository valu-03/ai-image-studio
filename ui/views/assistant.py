"""Assistant category - the three ways this app helps with a prompt.

Chat is the running conversation (AdvisorView); Prompt tools is the set of
one-shot helpers (BriefView: idea -> spec, upgrade a prompt, critique an
image, reverse-engineer a photo). Both feed the Images Compose form; grouping
them means the rail says "ask for help" once, not twice.

Prompt Bank (PromptBankContainer) is the user's own library: every prompt they
supply, saved exactly as given with its example images, split into Image and
Video. It replaced Anatomy (built-in templates split into teaching slots). It
feeds Compose nothing and calls no model - it keeps prompts, it does not judge
them.

Thin container, like ImagesView - MainWindow reaches in for `self.advisor_view`
and `self.brief_view`.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from ..widgets import MutedLabel
from .advisor import AdvisorView
from .brief_view import BriefView
from .prompt_bank import PromptBankContainer


class AssistantView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.advisor = AdvisorView(bank)
        self.brief = BriefView(bank)
        self.prompt_bank = PromptBankContainer()
        self.advisor.status.connect(self.status)
        self.brief.status.connect(self.status)
        self.prompt_bank.status.connect(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.advisor, "Chat")
        self.tabs.addTab(self.brief, "Prompt tools")
        self.tabs.addTab(self.prompt_bank, "Prompt Bank")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        # Kept to three lines at the minimum window width on purpose: a fourth
        # wrapped line here costs the tab pages ~20px of height, which is
        # enough to tip BriefView's image card into an overlap at 1100x700.
        # tests/test_layout.py catches that; the eye does not.
        layout.addWidget(MutedLabel(
            "Ask the in-app expert for help. Chat is a conversation; Prompt tools "
            "are one-shot helpers; Prompt Bank keeps your own prompts and their examples."))
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
