"""Images category — everything that produces a still.

A thin container. Compose builds and generates one image; Variants samples
several from one prompt; Relight and Macro insert each derive several from one
PHOTO you already have. Every view keeps its own logic; this only groups them.

The last two were planned for Look, and cannot live there: a Look toolkit
builds one PHRASE you Apply into a Compose field, and these two build whole
shot lists from a base spec plus a reference image. See
ui/views/batch_shots.py for the full argument.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from .compose import ComposeView
from .macro_insert import MacroInsertView
from .relight import RelightView
from .variants import VariantsView


class ImagesView(QWidget):
    # MainWindow connects `view.status` for each entry in `self.views`, and the
    # entry for "images" is this container - so without forwarding, every
    # status message Compose and Variants emit (validation errors, "a
    # character needs a name", autofill summaries, "invalid shot preset") goes
    # nowhere. Same forwarding CatsView does for its custom-prompt sub-tab.
    status = pyqtSignal(str)

    def __init__(self, bank, palette=None, parent=None):
        super().__init__(parent)
        self.compose = ComposeView(bank)
        self.variants = VariantsView(bank)
        self.relight = RelightView(palette)
        self.macro = MacroInsertView(palette)
        self._children = (self.compose, self.variants, self.relight, self.macro)
        for child in self._children:
            child.status.connect(self.status)

        self.tabs = QTabWidget()
        for child, label in zip(self._children,
                                ("Compose", "Variants", "Relight", "Macro insert")):
            self.tabs.addTab(child, label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(self.tabs)

    def show_compose(self):
        self.tabs.setCurrentIndex(0)

    def show_variants(self):
        self.tabs.setCurrentIndex(1)

    def show_relight(self):
        self.tabs.setCurrentIndex(2)

    def show_macro(self):
        self.tabs.setCurrentIndex(3)

    def set_palette_tokens(self, palette):
        # Only the two new views own a GateTree, which colours its rows from
        # whatever palette it was last handed - Compose and Variants have no
        # such method and must not be called blindly.
        for child in (self.relight, self.macro):
            child.set_palette_tokens(palette)
