"""Style category - the course's 24-look Style Reference Library.

  Library   the styles, browsable, split Photoreal / Stylised
  Build     pick a style or type your own, apply the result to Compose

A style is one whole look, so there are no techniques to stack (unlike
Lighting or Colour). Photoreal styles sit fine next to the realism vocabulary
the rest of the prompt carries; stylised ones (anime, oil painting) fight it -
the Result card warns before you Apply. Apply writes into
spec["overrides"]["style"], which build_prompt.free_overrides() folds into the
free trailing segment.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
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

import build_style as bstyle  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

EMPTY_HINT = "Pick a style, or type your own look."
AUTO_LABEL = "(none - type your own below)"


class StyleView(QWidget):
    """Emits `status`; `style_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    style_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bstyle.load_bank()
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
        self.library.setHeaderLabels(["GROUP", "STYLE", "WHAT IT'S FOR"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_style)

        use_button = QPushButton("Use this style")
        use_button.clicked.connect(lambda: self._use_library_style(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("24 visual styles"))
        card.body.addWidget(MutedLabel(
            "From the course's Style Reference Library. Photoreal styles keep the "
            "realistic look; stylised ones (anime, oil painting) do not - and say so "
            "when you pick them. Double-click one, or select it and press \"Use this "
            "style\", to load it on the Build tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.style_combo = QComboBox()
        self.style_combo.addItem(AUTO_LABEL, "")
        for key, cfg in bstyle.photoreal(self.bank).items():
            self.style_combo.addItem("{} (photoreal)".format(cfg["label"]), key)
        for key, cfg in bstyle.stylised(self.bank).items():
            self.style_combo.addItem("{} (stylised)".format(cfg["label"]), key)
        self.style_combo.currentIndexChanged.connect(self.rebuild_compose)
        self.style_combo.setToolTip(
            "A named look, or leave it as-is and type your own below - typed text "
            "always wins over a picked style.")

        self.custom_field = QLineEdit()
        self.custom_field.setPlaceholderText(
            "or type your own style, e.g. \"sun-bleached super-8 home movie look\"")
        self.custom_field.textChanged.connect(self.rebuild_compose)

        self.composed = MutedLabel("")
        self.composed.setProperty("class", "mono")
        self._has_result = False
        self.status_badge = Badge("empty", "neutral")

        self.warning_note = MutedLabel("")
        self.warning_note.hide()

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        form = Card()
        form.body.addWidget(TitleLabel("Build a style phrase"))
        form.body.addWidget(MutedLabel(
            "Pick a style, or type your own. It goes at the end of the image prompt."))
        form.body.addWidget(self.style_combo)
        form.body.addWidget(self.custom_field)

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.status_badge)
        header.addStretch(1)
        result.body.addLayout(header)
        result.body.addWidget(self.composed)
        result.body.addWidget(self.warning_note)
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
        """A resizable QScrollArea never shrinks its content below its own
        minimum - it clips silently with the bar off. AsNeeded, never Off."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- library ------------------------------------------------------------ #
    def rebuild_library(self):
        self.library.clear()
        for group, label in (("photoreal", "Photoreal"), ("stylised", "Stylised")):
            for key, cfg in self.bank.get(group, {}).items():
                item = QTreeWidgetItem(self.library, [label, cfg["label"], cfg["when"]])
                item.setData(0, Qt.ItemDataRole.UserRole, key)
        self.library.setColumnWidth(0, 90)
        self.library.setColumnWidth(1, 150)

    def _use_library_style(self, item):
        if item is None:
            self.status.emit("Pick a style first")
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        index = self.style_combo.findData(key)
        if index >= 0:
            self.style_combo.setCurrentIndex(index)
        self.custom_field.clear()
        self.tabs.setCurrentIndex(1)

    # -- compose -------------------------------------------------------------#
    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        style = self.style_combo.currentData() or None
        custom = self.custom_field.text().strip()

        try:
            phrase, warnings = bstyle.compose_style(self.bank, style=style, custom=custom)
        except bstyle.StyleError:
            self._has_result = False
            self.composed.setText(EMPTY_HINT)
            self.status_badge.set_status("neutral", "empty")
            self.warning_note.hide()
            self.apply_button.setEnabled(False)
            return

        self._has_result = True
        self.composed.setText(phrase)
        if warnings:
            self.status_badge.set_status("warning", "stylised")
            self.warning_note.setText("Heads up: this " + warnings[0])
            self.warning_note.show()
        else:
            self.status_badge.set_status("success", "ready")
            self.warning_note.hide()
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
        self.style_applied.emit(self.composed.text().strip())
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
