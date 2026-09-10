"""Look category - the prompt-tuning toolkits, grouped.

Lighting, Composition, Camera, Colour and Pose (Style is added in a later
step) all do the same job: build one phrase and Apply it into the Images
Compose spec. They used to be five separate rail entries; here they are five
tabs of one section, so the rail says "Images, then how it looks" instead of
listing six near-identical things.

A thin container, exactly like ImagesView: each child keeps its own logic and
signals, MainWindow reaches in for `self.lighting_view` etc.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import tokens as T
from ..widgets import MutedLabel
from .camera_angle import CameraAngleView
from .color_grading import ColorGradingView
from .composition import CompositionView
from .lighting import LightingView
from .posing import PosingView
from .style import StyleView

_TABS = ("Lighting", "Composition", "Camera", "Color", "Posing", "Style")


class LookView(QWidget):
    """Emits `status` (forwarded from whichever child emitted it)."""

    status = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.lighting = LightingView(palette)
        self.composition = CompositionView(palette)
        self.camera = CameraAngleView(palette)
        self.color = ColorGradingView(palette)
        self.posing = PosingView(palette)
        self.style = StyleView(palette)
        self._children = (self.lighting, self.composition, self.camera,
                          self.color, self.posing, self.style)

        self.tabs = QTabWidget()
        for child, label in zip(self._children, _TABS):
            child.status.connect(self.status)
            self.tabs.addTab(child, label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(MutedLabel(
            "Tune how the image looks — light, framing, camera angle, colour "
            "and pose. Each one builds a phrase you Apply into the Images prompt."))
        layout.addWidget(self.tabs)

    # -- the setters MainWindow's redirect table calls ---------------------- #
    def show_lighting(self):
        self.tabs.setCurrentIndex(0)

    def show_composition(self):
        self.tabs.setCurrentIndex(1)

    def show_camera(self):
        self.tabs.setCurrentIndex(2)

    def show_color(self):
        self.tabs.setCurrentIndex(3)

    def show_posing(self):
        self.tabs.setCurrentIndex(4)

    def show_style(self):
        self.tabs.setCurrentIndex(5)

    def refresh(self):
        current = self.tabs.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()

    def set_palette_tokens(self, palette):
        for child in self._children:
            child.set_palette_tokens(palette)
