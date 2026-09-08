"""Posing category - named poses grouped by shot type, plus opt-in posing
realism techniques stacked on top.

  Library   the named poses (weight on the back leg, S-curve, mid-gesture,
            ...), grouped by category, browsable
  Compose   pick a pose or type your own, stack realism techniques on top
            (or type one more of your own beyond the five), apply the
            result to Compose

Posing is NOT one of realism_lint.py's 8 gated photorealism layers - it is
descriptive spec content like wardrobe/setting/mood, so nothing here is
scored against the 8/8 gate the way Lighting/Composition phrases are.

Nothing here replaces Compose's own Action field (ui/spec_editor.py); this
is the deeper tool behind an "Open Posing" link next to it, the same
relationship Lighting/Composition's own sections already have to their combos.
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

import build_posing as bpo  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

NO_POSE_LABEL = "(none - type your own below)"


class PosingView(QWidget):
    """Emits `status`; `posing_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    posing_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bpo.load_bank()
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
        self.library.setColumnCount(3)
        self.library.setHeaderLabels(["CATEGORY", "POSE", "WHY"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_pose)

        use_button = QPushButton("Use this pose")
        use_button.clicked.connect(lambda: self._use_library_pose(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Named poses, by category"))
        card.body.addWidget(MutedLabel(
            "Portrait, editorial, headshot, group and candid - the standard vocabulary a "
            "working photographer directs a subject with. Double-click one, or select it "
            "and press \"Use this pose\", to load it on the Compose tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        # Editable, same pattern Lighting's deep-path pickers now use: a pose
        # is a tested starting point, not a closed world - type your own and
        # it is used exactly as typed rather than rejected as a typo.
        self.pose_combo = QComboBox(editable=True)
        self.pose_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.pose_combo.addItem(NO_POSE_LABEL, "")
        for key, cfg in bpo.poses(self.bank).items():
            self.pose_combo.addItem("{} ({})".format(cfg["label"], cfg["category"]), key)
        self.pose_combo.currentTextChanged.connect(self.rebuild_compose)
        self.pose_combo.setToolTip(
            "Pick a named pose, or leave it as-is and type your own - typed text is used "
            "exactly as written, the same rule every editable field in this app follows.")

        self.technique_checks = {}
        techniques_col = QVBoxLayout()
        techniques_col.setSpacing(T.SPACE["xs"])
        for key, cfg in bpo.techniques(self.bank).items():
            box = QCheckBox(cfg["label"])
            box.setToolTip(cfg["note"])
            box.toggled.connect(self.rebuild_compose)
            self.technique_checks[key] = box
            techniques_col.addWidget(box)

        self.technique_custom = QLineEdit()
        self.technique_custom.setPlaceholderText(
            "or type one more posing phrase, e.g. \"weight rocked slightly forward\"")
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
        form.body.addWidget(TitleLabel("Build a posing phrase"))
        form.body.addWidget(MutedLabel("Pick a named pose, or type your own below."))
        form.body.addWidget(self.pose_combo)
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
        for key, cfg in bpo.poses(self.bank).items():
            item = QTreeWidgetItem(self.library, [cfg["category"], cfg["label"], cfg["note"]])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
        self.library.setColumnWidth(0, 90)
        self.library.setColumnWidth(1, 160)

    def _use_library_pose(self, item):
        if item is None:
            self.status.emit("Pick a pose first")
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        index = self.pose_combo.findData(key)
        if index >= 0:
            self.pose_combo.setCurrentIndex(index)
        self.tabs.setCurrentIndex(1)

    # -- compose -------------------------------------------------------------#
    @staticmethod
    def _resolved(combo):
        """The current value of an editable combo - the underlying bank key
        if the typed/picked text names a listed item, else the raw typed
        text as-is. Mirrors ui/spec_editor.py's own `_listed()` helper and
        LightingView's own `_resolved()`."""
        text = combo.currentText().strip()
        if not text or text == NO_POSE_LABEL:
            return ""
        data = combo.currentData()
        if data:
            return data
        index = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        return combo.itemData(index) if index >= 0 else text

    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        pose = self._resolved(self.pose_combo) or None
        picked_techniques = [key for key, box in self.technique_checks.items() if box.isChecked()]

        try:
            phrase, _warnings = bpo.compose_posing(
                self.bank, pose=pose, techniques_=picked_techniques,
                technique_custom=self.technique_custom.text())
        except bpo.PosingError:
            self.composed.setText("")
            self.status_badge.set_status("neutral", "pick something")
            self.apply_button.setEnabled(False)
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
        self.posing_applied.emit(text)
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
