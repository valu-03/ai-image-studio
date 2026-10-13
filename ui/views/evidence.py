"""Evidence category - lived-in details that each have a cause.

  Library   every detail, browsable, grouped by subject kind
  Build     pick a kind, tick up to three details (or type your own), apply

WHAT THIS ADDS. Capture describes the camera's evidence - a tilted horizon,
flash falloff. This describes the SUBJECT's: a dent on the nose from sunglasses
just taken off, hairs shed on the cushion it slept on, a ring where the bottle
stood wet. A generated image is too clean and nothing in it has a history;
random imperfection reads as noise, an imperfection with a cause reads as a
moment that really happened. See tools/evidence_bank.json.

Apply emits `evidence_applied(str)`; MainWindow hands it to
SpecEditor.set_evidence_override(), which rides it in spec["overrides"]
["evidence"] - a non-layer override build_prompt appends to the free tail, so
it can only ever add to a prompt's realism score, never cost it a layer. An
explicit selection here outranks Compose's "Lived-in details (auto)" toggle.
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

import build_evidence as bev  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

EMPTY_HINT = "Tick up to three details, or type your own."


class EvidenceView(QWidget):
    """Emits `status`; `evidence_applied(str)` on Apply."""

    status = pyqtSignal(str)
    evidence_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bev.load_bank()
        self._palette = palette or {}
        self._has_result = False
        self.setup_ui()
        self.rebuild_library()
        self.on_kind_changed()

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
        self.library.setHeaderLabels(["KIND", "DETAIL", "WHY IT WORKS"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_option)

        use_button = QPushButton("Use this")
        use_button.clicked.connect(lambda: self._use_library_option(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Lived-in evidence"))
        card.body.addWidget(MutedLabel(
            "Small details that only exist because something happened before the photo: "
            "the reason a real picture feels real. Two or three is plenty - past that it "
            "reads as clutter. Double-click one, or select it and press \"Use this\"."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.kind_combo = QComboBox()
        for kind, cfg in self.bank["kinds"].items():
            self.kind_combo.addItem(cfg["label"], kind)
        self.kind_combo.currentIndexChanged.connect(self.on_kind_changed)

        form = Card()
        form.body.addWidget(TitleLabel("Build lived-in details"))
        form.body.addWidget(MutedLabel(
            "Evidence, not imperfection: every detail has a cause."))
        form.body.addWidget(MutedLabel("The subject is a:"))
        form.body.addWidget(self.kind_combo)

        # One column of checkboxes per kind, only the current kind's shown -
        # ticks survive switching kind and back, rather than being rebuilt.
        self.checks = {}
        self.kind_columns = {}
        for kind, cfg in self.bank["kinds"].items():
            holder = QWidget()
            column = QVBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(T.SPACE["xs"])
            for key, option in cfg["options"].items():
                box = QCheckBox(option["label"])
                box.setToolTip("{}\n\n{}".format(option["phrase"], option["note"]))
                box.toggled.connect(self.rebuild_compose)
                self.checks[(kind, key)] = box
                column.addWidget(box)
            self.kind_columns[kind] = holder
            form.body.addWidget(holder)

        self.custom_field = QLineEdit(
            placeholderText="your own, with its cause - e.g. \"a price sticker half peeled off\"")
        self.custom_field.textChanged.connect(self.rebuild_compose)
        form.body.addWidget(MutedLabel("Your own detail (optional):"))
        form.body.addWidget(self.custom_field)

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
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
        """AsNeeded, never Off - see CLAUDE.md on QScrollArea clipping."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- library ------------------------------------------------------------ #
    def rebuild_library(self):
        self.library.clear()
        for kind, cfg in self.bank["kinds"].items():
            for key, option in cfg["options"].items():
                item = QTreeWidgetItem(self.library, [cfg["label"], option["label"], option["note"]])
                item.setToolTip(1, option["phrase"])
                item.setData(0, Qt.ItemDataRole.UserRole, (kind, key))
        self.library.setColumnWidth(0, 120)
        self.library.setColumnWidth(1, 200)

    def _use_library_option(self, item):
        if item is None:
            self.status.emit("Pick a detail first")
            return
        kind, key = item.data(0, Qt.ItemDataRole.UserRole)
        self.set_kind(kind)
        self.checks[(kind, key)].setChecked(True)
        self.tabs.setCurrentIndex(1)

    # -- compose ------------------------------------------------------------ #
    def kind(self):
        return self.kind_combo.currentData()

    def set_kind(self, kind):
        index = self.kind_combo.findData(kind)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)

    def on_kind_changed(self):
        for kind, holder in self.kind_columns.items():
            holder.setVisible(kind == self.kind())
        self.rebuild_compose()

    def selected(self):
        kind = self.kind()
        return [key for (k, key), box in self.checks.items() if k == kind and box.isChecked()]

    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        try:
            phrase, warnings = bev.compose_evidence(
                self.bank, self.kind(), self.selected(), self.custom_field.text())
        except bev.EvidenceError:
            self._has_result = False
            self.composed.setText(EMPTY_HINT)
            self.warning_label.setText("")
            self.status_badge.set_status("neutral", "empty")
            self.apply_button.setEnabled(False)
            return
        self._has_result = True
        self.composed.setText(phrase)
        self.warning_label.setText(" ".join(warnings))
        self.status_badge.set_status("warning" if warnings else "success",
                                     "trimmed" if warnings else "ready")
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
        self.evidence_applied.emit(self.composed.text().strip())
        self.status.emit("Applied to Compose")

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
