"""Camera Angle category - vertical position, side, and shot size, the
three independent axes the Camera Language lesson teaches as foundational,
each composable on its own or combined with the others.

  Library   the six verticals, six sides, and eight sizes, browsable
  Compose   three independent combos, live composed phrase, apply the
            result to Compose

Nothing here replaces Compose's own Shot field (ui/spec_editor.py); Apply to
Compose writes the composed phrase in as typed custom shot text, replacing
the camera slot exactly like typing any other custom shot already does -
see build_camera_angle.py's own docstring for the honest tradeoff that
follows from that (a pure angle phrase with no camera language can score
the camera realism layer at 0/8; that's the gate working, not a bug).
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

EMPTY_HINT = "Pick a vertical, side or size — or type your own angle."


class CameraAngleView(QWidget):
    """Emits `status`; `angle_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    angle_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bca.load_bank()
        self._palette = palette or {}
        self.setup_ui()
        self.rebuild_library()
        self.rebuild_compose()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_compose_tab(), "Build")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _build_library_tab(self):
        self.library = QTreeWidget()
        self.library.setColumnCount(3)
        self.library.setHeaderLabels(["AXIS", "OPTION", "WHAT IT DOES"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_option)

        use_button = QPushButton("Use this option")
        use_button.clicked.connect(lambda: self._use_library_option(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Vertical, side, and size"))
        card.body.addWidget(MutedLabel(
            "Three independent axes - combine any of them on the Build tab. "
            "Angle sets where the viewer stands; side sets the relationship to the "
            "subject; size sets what the viewer is meant to read. Double-click one, "
            "or select it and press \"Use this option\", to set it on the Build tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.vertical_combo = QComboBox()
        self.vertical_combo.addItem("(none)", "")
        for key, cfg in bca.verticals(self.bank).items():
            self.vertical_combo.addItem(cfg["label"], key)
        self.side_combo = QComboBox()
        self.side_combo.addItem("(none)", "")
        for key, cfg in bca.sides(self.bank).items():
            self.side_combo.addItem(cfg["label"], key)
        self.size_combo = QComboBox()
        self.size_combo.addItem("(none)", "")
        for key, cfg in bca.sizes(self.bank).items():
            self.size_combo.addItem(cfg["label"], key)
        for combo in (self.vertical_combo, self.side_combo, self.size_combo):
            combo.currentIndexChanged.connect(self.rebuild_compose)

        axes_row = QGridLayout()
        axes_row.setHorizontalSpacing(T.COLUMN_GAP)
        axes_row.setVerticalSpacing(T.SPACE["sm"])
        axes_row.addWidget(QLabel("Vertical"), 0, 0)
        axes_row.addWidget(self.vertical_combo, 1, 0)
        axes_row.addWidget(QLabel("Side"), 0, 1)
        axes_row.addWidget(self.side_combo, 1, 1)
        axes_row.addWidget(QLabel("Size"), 0, 2)
        axes_row.addWidget(self.size_combo, 1, 2)

        self.custom_field = QLineEdit()
        self.custom_field.setPlaceholderText(
            "or type your own, e.g. \"shot from a drone, looking straight down\" - beats the axes above")
        self.custom_field.textChanged.connect(self.rebuild_compose)

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
        self._has_result = False
        self.status_badge = Badge("empty", "neutral")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        form = Card()
        form.body.addWidget(TitleLabel("Build a camera-angle phrase"))
        form.body.addWidget(MutedLabel("Combine any of the three axes, or type your own below."))
        form.body.addLayout(axes_row)
        form.body.addWidget(self.custom_field)

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.status_badge)
        header.addStretch(1)
        result.body.addLayout(header)
        result.body.addWidget(self.composed)
        result.body.addWidget(MutedLabel(
            "This replaces the Shot field's camera slot, same as typing any custom shot - "
            "a pure angle phrase with no camera language can score the camera check 0/8. "
            "That's the gate working, not a bug."))
        actions = QHBoxLayout()
        actions.setSpacing(T.SPACE["sm"])
        actions.addWidget(copy_button)
        actions.addWidget(self.apply_button)
        actions.addStretch(1)
        result.body.addLayout(actions)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(form)
        layout.addWidget(result)
        return self._scrolled(body)

    def _wrap(self, card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)
        return self._scrolled(page)

    def _scrolled(self, widget):
        """See CLAUDE.md - a resizable QScrollArea never shrinks its content
        below that content's own minimum, it clips silently with the bar off.
        AsNeeded, never Off, on every page in this view from day one."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- library ------------------------------------------------------------ #
    def rebuild_library(self):
        self.library.clear()
        for axis, combo, items in [
                ("Vertical", "vertical_combo", bca.verticals(self.bank)),
                ("Side", "side_combo", bca.sides(self.bank)),
                ("Size", "size_combo", bca.sizes(self.bank))]:
            for key, cfg in items.items():
                item = QTreeWidgetItem(self.library, [axis, cfg["label"], cfg["note"]])
                item.setData(0, Qt.ItemDataRole.UserRole, (combo, key))
        self.library.setColumnWidth(0, 70)
        self.library.setColumnWidth(1, 130)

    def _use_library_option(self, item):
        if item is None:
            self.status.emit("Pick an option first")
            return
        combo_name, key = item.data(0, Qt.ItemDataRole.UserRole)
        combo = getattr(self, combo_name)
        index = combo.findData(key)
        if index >= 0:
            combo.setCurrentIndex(index)
        self.tabs.setCurrentIndex(1)

    # -- compose -------------------------------------------------------------#
    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        vertical = self.vertical_combo.currentData() or None
        side = self.side_combo.currentData() or None
        size = self.size_combo.currentData() or None
        custom = self.custom_field.text().strip()

        try:
            phrase, _warnings = bca.compose_camera_angle(
                self.bank, vertical=vertical, side=side, size=size, custom=custom)
        except bca.CameraAngleError:
            self._has_result = False
            self.composed.setText(EMPTY_HINT)
            self.status_badge.set_status("neutral", "empty")
            self.apply_button.setEnabled(False)
            return

        self._has_result = True
        self.composed.setText(phrase)
        self.status_badge.set_status("success", "ready")
        self.apply_button.setEnabled(True)

    def copy_composed(self):
        if not self._has_result:
            self.status.emit("Nothing composed yet")
            return
        QGuiApplication.clipboard().setText(self.composed.text().strip())
        self.status.emit("Copied: " + self.composed.text().strip())

    def apply_to_compose(self):
        if not self._has_result:
            self.status.emit("Nothing composed yet")
            return
        self.angle_applied.emit(self.composed.text().strip())
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
