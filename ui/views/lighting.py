"""Lighting category - a real photographic taxonomy, not a single flat combo.

  Library   the named setups (Rembrandt, split, loop, ...), browsable
  Compose   pick a setup (fast) or direction + quality + source (deep),
            stack realism techniques on top, apply the result to Compose

The deep path's three pickers, and the technique list, are all editable - a
bank entry is a tested starting point, not a closed world; type your own and
it is used exactly as typed. See tools/build_lighting.py's docstring.

Two paths to a phrase - see tools/build_lighting.py's own docstring for why.
Nothing here replaces Compose's own lighting combo (ui/spec_editor.py); this
is the deeper tool behind an "Open Lighting" link next to it, the same
relationship Videos' standalone Audio Cue field already has to Sound.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
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

import build_lighting as bl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

AUTO_LABEL = "(build from direction + quality + source)"


class LightingView(QWidget):
    """Emits `status`; `lighting_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    lighting_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bl.load_bank()
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
        self.library.setHeaderLabels(["SETUP", "WHEN TO REACH FOR IT"])
        self.library.setRootIsDecorated(False)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self._use_library_setup)

        use_button = QPushButton("Use this setup")
        use_button.clicked.connect(lambda: self._use_library_setup(self.library.currentItem()))

        card = Card()
        card.body.addWidget(TitleLabel("Named lighting setups"))
        card.body.addWidget(MutedLabel(
            "The recipes a working photographer would call by name. Double-click one, "
            "or select it and press \"Use this setup\", to load it on the Compose tab."))
        card.body.addWidget(self.library, 1)
        card.body.addWidget(use_button)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.setup_combo = QComboBox()
        self.setup_combo.addItem(AUTO_LABEL, "")
        for key, cfg in bl.setups(self.bank).items():
            self.setup_combo.addItem(cfg["label"], key)
        self.setup_combo.currentIndexChanged.connect(self.rebuild_compose)
        self.setup_combo.setToolTip(
            "A named setup is a complete, pre-vetted recipe - pick one, or build your "
            "own from the three pickers below.")

        # Editable, like Compose's own shot/lighting/composition combos: the
        # bank's entries are tested starting points, not a closed world - type
        # your own direction/quality/source and it is used exactly as typed
        # rather than rejected as a typo. See build_lighting.py's docstring.
        self.direction_combo = QComboBox(editable=True)
        self.direction_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.direction_combo.addItem("(none)", "")
        for key, cfg in bl.directions(self.bank).items():
            self.direction_combo.addItem(cfg["label"], key)
        self.quality_combo = QComboBox(editable=True)
        self.quality_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.quality_combo.addItem("(none)", "")
        for key, cfg in bl.qualities(self.bank).items():
            self.quality_combo.addItem(cfg["label"], key)
        self.quality_combo.setToolTip(
            "Hard or soft, or type your own - conflict-checking against source "
            "only applies when this is left on hard/soft.")
        self.source_combo = QComboBox(editable=True)
        self.source_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.source_combo.addItem("(none)", "")
        for key, cfg in bl.sources(self.bank).items():
            self.source_combo.addItem("{} ({})".format(cfg["label"], cfg["category"]), key)
        for combo in (self.direction_combo, self.quality_combo, self.source_combo):
            # Editable combos must watch text, not index - typed text never
            # moves the index. Same rule ui/spec_editor.py's own combos follow.
            combo.currentTextChanged.connect(self.rebuild_compose)

        deep_row = QGridLayout()
        deep_row.setHorizontalSpacing(T.COLUMN_GAP)
        deep_row.setVerticalSpacing(T.SPACE["sm"])
        deep_row.addWidget(QLabel("Direction"), 0, 0)
        deep_row.addWidget(self.direction_combo, 1, 0)
        deep_row.addWidget(QLabel("Quality"), 0, 1)
        deep_row.addWidget(self.quality_combo, 1, 1)
        deep_row.addWidget(QLabel("Source"), 0, 2)
        deep_row.addWidget(self.source_combo, 1, 2)

        self.technique_checks = {}
        techniques_col = QVBoxLayout()
        techniques_col.setSpacing(T.SPACE["xs"])
        for key, cfg in bl.techniques(self.bank).items():
            box = QCheckBox(cfg["label"])
            box.setToolTip(cfg["note"])
            box.toggled.connect(self.rebuild_compose)
            self.technique_checks[key] = box
            techniques_col.addWidget(box)

        self.technique_custom = QLineEdit()
        self.technique_custom.setPlaceholderText(
            "or type one more realism phrase, e.g. \"a hint of lens flare from the source\"")
        self.technique_custom.textChanged.connect(self.rebuild_compose)

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
        self.warning_badge = Badge("no conflicts", "success")
        self.warning_note = MutedLabel("")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        form = Card()
        form.body.addWidget(TitleLabel("Build a lighting phrase"))
        form.body.addWidget(MutedLabel("Pick a named setup, or build your own below."))
        form.body.addWidget(self.setup_combo)
        form.body.addWidget(MutedLabel("Direction + quality + source (used when the setup "
                                       "above is left on \"build from...\"):"))
        form.body.addLayout(deep_row)
        form.body.addWidget(MutedLabel("Realism techniques (optional, stack freely):"))
        form.body.addLayout(techniques_col)
        form.body.addWidget(self.technique_custom)

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.warning_badge)
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
        for key, cfg in bl.setups(self.bank).items():
            item = QTreeWidgetItem(self.library, [cfg["label"], cfg["teaches"]])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
        self.library.setColumnWidth(0, 160)

    def _use_library_setup(self, item):
        if item is None:
            self.status.emit("Pick a setup first")
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        index = self.setup_combo.findData(key)
        if index >= 0:
            self.setup_combo.setCurrentIndex(index)
        self.tabs.setCurrentIndex(1)

    @staticmethod
    def _resolved(combo):
        """The current value of an editable combo - the underlying bank key
        if the typed/picked text names a listed item, else the raw typed
        text as-is. Mirrors ui/spec_editor.py's own `_listed()` helper: an
        editable combo's index never moves when text is typed rather than
        picked, so currentData() alone would miss a typed value entirely,
        and a typed value that happens to match a listed label still has to
        resolve to that item's key rather than being sent through as text
        that happens to equal the label.
        """
        text = combo.currentText().strip()
        if not text or text == "(none)":
            return ""
        data = combo.currentData()
        if data:
            return data
        index = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        return combo.itemData(index) if index >= 0 else text

    # -- compose -------------------------------------------------------------#
    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        setup = self.setup_combo.currentData() or None
        deep_active = not setup
        for combo in (self.direction_combo, self.quality_combo, self.source_combo):
            combo.setEnabled(deep_active)

        direction = self._resolved(self.direction_combo) or None if deep_active else None
        quality = self._resolved(self.quality_combo) or None if deep_active else None
        source = self._resolved(self.source_combo) or None if deep_active else None
        picked_techniques = [key for key, box in self.technique_checks.items() if box.isChecked()]

        try:
            phrase, warnings = bl.compose_lighting(
                self.bank, setup=setup, direction=direction, quality=quality,
                source=source, techniques_=picked_techniques,
                technique_custom=self.technique_custom.text())
        except bl.LightingError as exc:
            self.composed.setText("")
            self.warning_badge.set_status("neutral", "pick something")
            self.warning_note.setText(str(exc))
            self.apply_button.setEnabled(False)
            return

        self.composed.setText(phrase)
        self.apply_button.setEnabled(True)
        if warnings:
            self.warning_badge.set_status("warning", "{} conflict(s)".format(len(warnings)))
            self.warning_note.setText(" ".join(warnings))
        else:
            self.warning_badge.set_status("success", "no conflicts")
            self.warning_note.setText("")

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
        self.lighting_applied.emit(text)
        self.status.emit("Applied to Compose")

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}

    def refresh(self):
        pass
