"""Capture category - film stock, lens artefacts, exposure and the evidence
that a person was holding the camera.

  Library   every option, browsable, grouped by what it is
  Build     tick what you want, see the composed phrase, apply it to Compose

WHAT THIS ADDS THAT NOTHING ELSE DID. Every other toolkit in Look describes the
SUBJECT and the scene - how it is lit, framed, posed, graded. None of them
describe the CAPTURE, and a repo-wide grep found no bank naming chromatic
aberration, halation, veiling glare, vignetting, ISO, shutter speed or a single
film stock. Output therefore topped out at "well-lit studio photograph": clean,
plausible, and with nothing in it that says a physical camera was involved.

Unlike Lighting or Colour, a selection here spans SEVERAL of build_prompt's
layers at once - a stock strengthens `grain`, an artefact strengthens `lens`,
white balance strengthens `lighting`. So this view emits `capture_applied` with
the overrides dict rather than one phrase, and MainWindow merges it into the
spec's own overrides.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
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

import build_capture as bcap  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

EMPTY_HINT = ("Pick a film stock, or tick a lens artefact, exposure property or "
              "piece of handheld evidence.")

NO_STOCK_LABEL = "(no film stock)"

# The groups that are ticked rather than picked from a combo.
CHECK_GROUPS = ("optics", "exposure", "evidence")


class CaptureView(QWidget):
    """Emits `status`; `capture_applied(dict)` on Apply - a {layer: [phrase]}
    mapping, not a flat string, because one selection can strengthen several
    of build_prompt's layers at once."""

    status = pyqtSignal(str)
    capture_applied = pyqtSignal(dict)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bcap.load_bank()
        self._palette = palette or {}
        self._overrides = {}
        self._has_result = False
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
        self.library.setHeaderLabels(["GROUP", "OPTION", "WHAT IT IS"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_option)

        use_button = QPushButton("Use this")
        use_button.clicked.connect(lambda: self._use_library_option(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Film stock, optics, exposure, evidence"))
        card.body.addWidget(MutedLabel(
            "The properties of the camera rather than of the subject. Real artefacts are "
            "faint - every phrase here is deliberately hedged, and stacking more than about "
            "four of them starts to read as a filter rather than a photograph. Double-click "
            "one, or select it and press \"Use this\", to turn it on over on Build."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        # Film stock is a combo, not checkboxes: the bank marks it exclusive
        # because two stocks in one prompt contradict each other.
        self.stock_combo = QComboBox()
        self.stock_combo.addItem(NO_STOCK_LABEL, "")
        for key, option in bcap.options(self.bank, "film_stock").items():
            self.stock_combo.addItem(option["label"], key)
        self.stock_combo.currentIndexChanged.connect(self.rebuild_compose)
        self.stock_combo.setToolTip(
            "One stock at most - naming two contradicts itself. A stock implies a whole "
            "grain structure and colour response in two words.")

        form = Card()
        form.body.addWidget(TitleLabel("Build a capture phrase"))
        form.body.addWidget(MutedLabel(
            "What the camera did, as opposed to what it was pointed at."))
        form.body.addWidget(MutedLabel("Film stock (at most one):"))
        form.body.addWidget(self.stock_combo)

        self.checks = {}
        for group in CHECK_GROUPS:
            cfg = bcap.groups(self.bank)[group]
            form.body.addWidget(MutedLabel("{} (stack freely):".format(cfg["label"])))
            column = QVBoxLayout()
            column.setSpacing(T.SPACE["xs"])
            for key, option in cfg["options"].items():
                box = QCheckBox(option["label"])
                box.setToolTip(option["note"])
                box.toggled.connect(self.rebuild_compose)
                self.checks[key] = (group, box)
                column.addWidget(box)
            form.body.addLayout(column)

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
        self.layers_label = MutedLabel("")
        self.layers_label.setWordWrap(True)
        self.warning_label = MutedLabel("")
        self.warning_label.setWordWrap(True)
        self.status_badge = Badge("empty", "neutral")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.status_badge)
        header.addStretch(1)
        result.body.addLayout(header)
        result.body.addWidget(self.composed)
        result.body.addWidget(self.layers_label)
        result.body.addWidget(self.warning_label)
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
        AsNeeded, never Off."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- library ------------------------------------------------------------ #
    def rebuild_library(self):
        self.library.clear()
        for group, cfg in bcap.groups(self.bank).items():
            for key, option in cfg["options"].items():
                item = QTreeWidgetItem(
                    self.library, [cfg["label"], option["label"], option["note"]])
                item.setData(0, Qt.ItemDataRole.UserRole, (group, key))
        self.library.setColumnWidth(0, 130)
        self.library.setColumnWidth(1, 180)

    def _use_library_option(self, item):
        if item is None:
            self.status.emit("Pick an option first")
            return
        group, key = item.data(0, Qt.ItemDataRole.UserRole)
        if group == "film_stock":
            index = self.stock_combo.findData(key)
            if index >= 0:
                self.stock_combo.setCurrentIndex(index)
        elif key in self.checks:
            self.checks[key][1].setChecked(True)
        self.tabs.setCurrentIndex(1)

    # -- compose ------------------------------------------------------------ #
    def _selection(self):
        picked = {group: [] for group in CHECK_GROUPS}
        for key, (group, box) in self.checks.items():
            if box.isChecked():
                picked[group].append(key)
        return self.stock_combo.currentData() or None, picked

    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        stock, picked = self._selection()
        try:
            overrides, warnings = bcap.compose_capture(
                self.bank, film_stock=stock, optics=picked["optics"],
                exposure=picked["exposure"], evidence=picked["evidence"])
        except bcap.CaptureError:
            self._has_result = False
            self._overrides = {}
            self.composed.setText(EMPTY_HINT)
            self.layers_label.setText("")
            self.warning_label.setText("")
            self.status_badge.set_status("neutral", "empty")
            self.apply_button.setEnabled(False)
            return

        self._has_result = True
        self._overrides = overrides
        self.composed.setText(bcap.phrase_for(overrides))
        # Naming the layers is the point of this view existing separately: it
        # is the only toolkit whose one selection lands on several of them.
        self.layers_label.setText(
            "Strengthens: " + ", ".join(sorted(overrides)))
        self.warning_label.setText(" ".join(warnings))
        self.status_badge.set_status("warning" if warnings else "success",
                                     "busy" if warnings else "ready")
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
        self.capture_applied.emit(dict(self._overrides))
        self.status.emit("Applied to Compose")

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
