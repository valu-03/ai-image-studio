"""Color Grading category - mood-to-palette presets and film-look references
from the course's own cheat sheet, plus opt-in colour techniques.

  Library   the 12 moods and 10 film looks, browsable, a TYPE column
            distinguishing them
  Compose   pick a look or type your own, stack techniques on top, apply the
            result to Compose

Nothing here replaces Compose's own colour combo (ui/spec_editor.py, new -
mirrors the Lighting combo exactly); this is the deeper tool behind an "Open
Color Grading" link next to it, the same relationship every prior section
has to its own combo.
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

import build_color as bcol  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

AUTO_LABEL = "(none - type your own below)"


class ColorGradingView(QWidget):
    """Emits `status`; `color_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    color_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bcol.load_bank()
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
        self.library.setHeaderLabels(["TYPE", "LOOK", "PALETTE"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_look)

        use_button = QPushButton("Use this look")
        use_button.clicked.connect(lambda: self._use_library_look(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Moods and film looks"))
        card.body.addWidget(MutedLabel(
            "12 named moods and 10 film-reference looks, straight from the course's own "
            "Mood → Color → Prompt cheat sheet. Double-click one, or select it and "
            "press \"Use this look\", to load it on the Compose tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        # One combo covering both moods and film looks - they're two named
        # recipes of the same kind, not a fast/deep-path split, so they
        # share one picker rather than two separate ones.
        self.look_combo = QComboBox()
        self.look_combo.addItem(AUTO_LABEL, ("", ""))
        for key, cfg in bcol.moods(self.bank).items():
            self.look_combo.addItem("{} (mood)".format(cfg["label"]), ("mood", key))
        for key, cfg in bcol.film_looks(self.bank).items():
            self.look_combo.addItem("{} (film look)".format(cfg["label"]), ("film_look", key))
        self.look_combo.currentIndexChanged.connect(self.rebuild_compose)
        self.look_combo.setToolTip(
            "A named mood or film look, or leave it as-is and type your own below - typed "
            "text always wins over a picked look.")

        self.custom_field = QLineEdit()
        self.custom_field.setPlaceholderText(
            "or type your own colour-grading text, e.g. \"sun-bleached pastel grade\"")
        self.custom_field.textChanged.connect(self.rebuild_compose)

        self.technique_checks = {}
        techniques_col = QVBoxLayout()
        techniques_col.setSpacing(T.SPACE["xs"])
        for key, cfg in bcol.techniques(self.bank).items():
            box = QCheckBox(cfg["label"])
            box.setToolTip(cfg["note"])
            box.toggled.connect(self.rebuild_compose)
            self.technique_checks[key] = box
            techniques_col.addWidget(box)

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
        form.body.addWidget(TitleLabel("Build a colour-grading phrase"))
        form.body.addWidget(MutedLabel("Pick a mood or film look, or type your own below."))
        form.body.addWidget(self.look_combo)
        form.body.addWidget(self.custom_field)
        form.body.addWidget(MutedLabel("Techniques (optional, stack freely):"))
        form.body.addLayout(techniques_col)

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
        for key, cfg in bcol.moods(self.bank).items():
            item = QTreeWidgetItem(self.library, ["Mood", cfg["label"], cfg["note"]])
            item.setData(0, Qt.ItemDataRole.UserRole, ("mood", key))
        for key, cfg in bcol.film_looks(self.bank).items():
            item = QTreeWidgetItem(self.library, ["Film look", cfg["label"], cfg["note"]])
            item.setData(0, Qt.ItemDataRole.UserRole, ("film_look", key))
        self.library.setColumnWidth(0, 90)
        self.library.setColumnWidth(1, 150)

    def _use_library_look(self, item):
        if item is None:
            self.status.emit("Pick a look first")
            return
        kind, key = item.data(0, Qt.ItemDataRole.UserRole)
        index = self.look_combo.findData((kind, key))
        if index >= 0:
            self.look_combo.setCurrentIndex(index)
        self.custom_field.clear()
        self.tabs.setCurrentIndex(1)

    # -- compose -------------------------------------------------------------#
    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        kind, key = self.look_combo.currentData() or ("", "")
        mood = key if kind == "mood" else None
        film_look = key if kind == "film_look" else None
        custom = self.custom_field.text().strip()
        picked_techniques = [k for k, box in self.technique_checks.items() if box.isChecked()]

        try:
            phrase, _warnings = bcol.compose_color(
                self.bank, mood=mood, film_look=film_look, custom=custom,
                techniques_=picked_techniques)
        except bcol.ColorError:
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
        self.color_applied.emit(text)
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
