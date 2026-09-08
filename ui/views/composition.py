"""Composition category - the seven named framing geometries (already in
Compose's own combo) plus opt-in, physically-grounded techniques stacked on
top of one.

  Library   the seven guides (rule of thirds, phi grid, diagonals, ...),
            browsable, reused straight from prompt_bank.json - not duplicated
  Compose   pick a guide or type your own framing text, stack realism
            techniques on top (or type one more of your own beyond the
            seven), apply the result to Compose

Nothing here replaces Compose's own composition combo (ui/spec_editor.py);
this is the deeper tool behind an "Open Composition" link next to it, the
same relationship Lighting's own section already has to that combo.
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

import build_composition as bc  # noqa: E402
import build_prompt as bp  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

NO_GUIDE_LABEL = "(none - type your own below)"


class CompositionView(QWidget):
    """Emits `status`; `composition_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    composition_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.image_bank = bp.load_bank()
        self.bank = bc.load_bank()
        self._palette = palette or {}
        self.setup_ui()
        self.rebuild_library()
        self.rebuild_compose()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_compose_tab(), "Compose")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _build_library_tab(self):
        self.library = QTreeWidget()
        self.library.setColumnCount(2)
        self.library.setHeaderLabels(["GEOMETRY", "WHEN TO REACH FOR IT"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_guide)

        use_button = QPushButton("Use this geometry")
        use_button.clicked.connect(lambda: self._use_library_guide(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("The seven named geometries"))
        card.body.addWidget(MutedLabel(
            "The same guides Compose's own Scene tab already offers - browsable here "
            "with what each one does to the frame. Double-click one, or select it and "
            "press \"Use this geometry\", to load it on the Compose tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.guide_combo = QComboBox()
        self.guide_combo.addItem(NO_GUIDE_LABEL, "")
        for key, cfg in bp.guides(self.image_bank).items():
            self.guide_combo.addItem(cfg["label"], key)
        self.guide_combo.currentIndexChanged.connect(self.rebuild_compose)
        self.guide_combo.setToolTip(
            "A named geometry, or leave it on the first option and type your own "
            "framing instruction below - typed text always wins over a picked guide.")

        self.custom_field = QLineEdit()
        self.custom_field.setPlaceholderText(
            "or type your own framing instruction, e.g. \"framed low, looking up at the subject\"")
        self.custom_field.textChanged.connect(self.rebuild_compose)

        self.technique_checks = {}
        techniques_col = QVBoxLayout()
        techniques_col.setSpacing(T.SPACE["xs"])
        for key, cfg in bc.techniques(self.bank).items():
            box = QCheckBox(cfg["label"])
            box.setToolTip(cfg["note"])
            box.toggled.connect(self.rebuild_compose)
            self.technique_checks[key] = box
            techniques_col.addWidget(box)

        self.technique_custom = QLineEdit()
        self.technique_custom.setPlaceholderText(
            "or type one more realism phrase, e.g. \"the horizon kept low in the frame\"")
        self.technique_custom.textChanged.connect(self.rebuild_compose)

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
        self.status_badge = Badge("pick something", "neutral")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        form = Card()
        form.body.addWidget(TitleLabel("Build a composition phrase"))
        form.body.addWidget(MutedLabel("Pick a named geometry, or type your own below."))
        form.body.addWidget(self.guide_combo)
        form.body.addWidget(self.custom_field)
        form.body.addWidget(MutedLabel("Realism techniques (optional, stack freely):"))
        form.body.addLayout(techniques_col)
        form.body.addWidget(self.technique_custom)

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.status_badge)
        header.addStretch(1)
        result.body.addLayout(header)
        result.body.addWidget(self.composed)
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
        for key, cfg in bp.guides(self.image_bank).items():
            item = QTreeWidgetItem(self.library, [cfg["label"], cfg["note"]])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
        self.library.setColumnWidth(0, 160)

    def _use_library_guide(self, item):
        if item is None:
            self.status.emit("Pick a geometry first")
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        index = self.guide_combo.findData(key)
        if index >= 0:
            self.guide_combo.setCurrentIndex(index)
        self.custom_field.clear()
        self.tabs.setCurrentIndex(1)

    # -- compose -------------------------------------------------------------#
    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        guide = self.guide_combo.currentData() or None
        custom = self.custom_field.text().strip()
        picked_techniques = [key for key, box in self.technique_checks.items() if box.isChecked()]

        try:
            phrase, _warnings = bc.compose_composition(
                self.image_bank, self.bank, guide=guide, custom=custom,
                techniques_=picked_techniques,
                technique_custom=self.technique_custom.text())
        except bc.CompositionError as exc:
            self.composed.setText("")
            self.status_badge.set_status("neutral", "pick something")
            self.apply_button.setEnabled(False)
            self._error = str(exc)
            return

        self.composed.setText(phrase)
        self.status_badge.set_status("success", "ready")
        self.apply_button.setEnabled(True)

    def copy_composed(self):
        text = self.composed.text().strip()
        if not text:
            self.status.emit("Nothing composed yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    def apply_to_compose(self):
        text = self.composed.text().strip()
        if not text:
            self.status.emit("Nothing composed yet")
            return
        self.composition_applied.emit(text)
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
