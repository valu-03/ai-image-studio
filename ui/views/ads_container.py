"""Ads category - the video advert and the static advert, side by side.

A thin container, exactly like ImagesView, LookView and AnatomyContainer: it
builds the children, exposes them (`self.video`, `self.static`), and anything
that needs one reaches in.

WHY THE STATIC AD IS A TAB AND NOT AN ELEVENTH RAIL SECTION. `Ctrl+1..9` then
`Ctrl+0` is generated from `NAV_ITEMS[:10]` in main_window.py, because
QKeySequence cannot parse a multi-digit token - an eleventh rail entry would be
the only section in the app with no keyboard shortcut. Both halves are also the
same job at two lengths, which is the argument for one section rather than two.

`MainWindow` keeps `self.ads_view = self.ads_container.video`, so every
existing `win.ads_view` reference, signal wire and test keeps working and the
five-beat flow is untouched.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from .ads import AdsView
from .static_ad import StaticAdView


class AdsContainer(QWidget):
    """Emits `status` (forwarded from whichever child emitted it)."""

    status = pyqtSignal(str)

    def __init__(self, bank, palette=None, parent=None):
        super().__init__(parent)
        self.video = AdsView(bank, palette)
        self.static = StaticAdView(palette)
        self._children = (self.video, self.static)
        for child in self._children:
            child.status.connect(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.video, "Video ad")
        self.tabs.addTab(self.static, "Static ad")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(self.tabs)

    # -- the setters MainWindow's redirect table calls ---------------------- #
    def show_video(self):
        self.tabs.setCurrentIndex(0)

    def show_static(self):
        self.tabs.setCurrentIndex(1)

    def refresh(self):
        current = self.tabs.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()

    def set_palette_tokens(self, palette):
        for child in self._children:
            child.set_palette_tokens(palette)
