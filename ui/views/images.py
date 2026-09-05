"""Images category — everything that produces a still.

A thin container: Compose builds and generates one image, Variants samples
several. Both views keep their own logic; this only groups them.
"""

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from .compose import ComposeView
from .variants import VariantsView


class ImagesView(QWidget):
    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.compose = ComposeView(bank)
        self.variants = VariantsView(bank)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.compose, "Compose")
        self.tabs.addTab(self.variants, "Variants")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(self.tabs)

    def show_compose(self):
        self.tabs.setCurrentIndex(0)

    def show_variants(self):
        self.tabs.setCurrentIndex(1)
