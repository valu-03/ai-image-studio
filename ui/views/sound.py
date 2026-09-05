"""Sound category - ElevenLabs sound-effect prompts.

  Library   the course's 100 example prompts, by theme
  Compose   build one prompt and score it
  Scenes    the three-layer sheet for the story open in the Cats tab

The three layers are the part that matters. One effect on its own sounds like a
sound effect; ambience under a key effect under an accent sounds like a place.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_sound as bsd  # noqa: E402
import sound_lint as sl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402


class SoundView(QWidget):
    """Emits `status`; reads the current story through `context`."""

    status = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bsd.load_bank()
        self._palette = palette or {}
        self.context = None          # set by the controller: () -> [scene dicts]
        self.setup_ui()
        self.reload_library()
        self.rebuild()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_compose_tab(), "Compose")
        self.tabs.addTab(self._build_scenes_tab(), "Scenes")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _build_library_tab(self):
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the 100 examples…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload_library)

        self.theme_filter = QComboBox()
        self.theme_filter.addItem("Every theme", "")
        for key, cfg in sl.themes(self.bank).items():
            self.theme_filter.addItem(cfg["label"], key)
            self.theme_filter.setItemData(
                self.theme_filter.count() - 1, cfg["note"], Qt.ItemDataRole.ToolTipRole)
        self.theme_filter.currentIndexChanged.connect(self.reload_library)

        self.library = QTreeWidget()
        self.library.setColumnCount(2)
        self.library.setHeaderLabels(["#", "PROMPT"])
        self.library.setRootIsDecorated(True)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self.copy_example)

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(lambda: self.copy_example(self.library.currentItem()))

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(self.search, 1)
        row.addWidget(self.theme_filter)
        row.addWidget(copy_button)

        card = Card()
        card.body.addWidget(TitleLabel("100 example prompts"))
        card.body.addWidget(MutedLabel(
            "Verbatim from the course. Double-click to copy one. They are also this "
            "section's test fixture: if the linter ever rejects one of these, the "
            "linter is wrong about it, not the other way round."))
        card.body.addLayout(row)
        card.body.addWidget(self.library, 1)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.source = QLineEdit(placeholderText="torch flame")
        self.action = QLineEdit(placeholderText="crackling")
        self.place = QLineEdit(placeholderText="a temple hallway")
        self.treatment = QLineEdit(placeholderText="comedic echo")
        for field in (self.source, self.action, self.place, self.treatment):
            field.textChanged.connect(self.rebuild_compose)

        self.composed = QLineEdit()
        self.composed.setReadOnly(True)
        self.composed.setProperty("class", "mono")

        self.compose_badge = Badge("0/4", "neutral")
        self.compose_tree = QTreeWidget()
        self.compose_tree.setColumnCount(3)
        self.compose_tree.setHeaderLabels(["", "CHECK", "DETAIL"])
        self.compose_tree.setRootIsDecorated(False)
        self.compose_tree.setAlternatingRowColors(True)
        self.compose_tree.setMaximumHeight(160)

        self.compose_advice = MutedLabel("")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        form = Card()
        form.body.addWidget(TitleLabel("Build one"))
        form.body.addWidget(MutedLabel(self.bank.get("pattern", {}).get("shape", "")))
        for label, widget in [("Source", self.source), ("Action", self.action),
                              ("Where", self.place), ("How", self.treatment)]:
            line = QHBoxLayout()
            caption = QLabel(label)
            caption.setMinimumWidth(70)
            line.addWidget(caption)
            line.addWidget(widget, 1)
            form.body.addLayout(line)

        out_row = QHBoxLayout()
        out_row.addWidget(self.composed, 1)
        out_row.addWidget(copy_button)
        form.body.addLayout(out_row)

        gate = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Will this work?"))
        header.addWidget(self.compose_badge)
        header.addStretch(1)
        gate.body.addLayout(header)
        gate.body.addWidget(self.compose_tree)
        gate.body.addWidget(self.compose_advice)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(form)
        layout.addWidget(gate, 1)
        return page

    def _build_scenes_tab(self):
        self.theme_for_scenes = QComboBox()
        for key, cfg in sl.themes(self.bank).items():
            self.theme_for_scenes.addItem(cfg["label"], key)
        index = self.theme_for_scenes.findData("comedy")
        if index >= 0:
            self.theme_for_scenes.setCurrentIndex(index)
        self.theme_for_scenes.currentIndexChanged.connect(self.rebuild)

        self.scene_tree = QTreeWidget()
        self.scene_tree.setColumnCount(3)
        self.scene_tree.setHeaderLabels(["SCENE", "LAYER", "PROMPT"])
        self.scene_tree.setAlternatingRowColors(True)

        copy_all = QPushButton("Copy the whole sheet")
        copy_all.setIcon(assets.icon("copy"))
        copy_all.setIconSize(assets.ICON_SIZE)
        copy_all.clicked.connect(self.copy_sheet)

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(QLabel("Accent theme"))
        row.addWidget(self.theme_for_scenes)
        row.addStretch(1)
        row.addWidget(copy_all)

        self.scene_note = MutedLabel("")

        card = Card()
        card.body.addWidget(TitleLabel("Sound for the open story"))
        card.body.addWidget(MutedLabel(
            "Three layers per scene. Ambience runs under everything and should never "
            "be noticed; the key effect lands on the frame where the action happens; "
            "the accent punctuates the cut. Never two accents in one scene."))
        card.body.addLayout(row)
        card.body.addWidget(self.scene_note)
        card.body.addWidget(self.scene_tree, 1)
        return self._wrap(card)

    def _wrap(self, card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)
        return page

    # -- library ----------------------------------------------------------- #
    def reload_library(self):
        needle = self.search.text().strip().lower()
        theme = self.theme_filter.currentData() or ""
        self.library.clear()
        shown = 0
        for key, cfg in sl.themes(self.bank).items():
            if theme and key != theme:
                continue
            rows = [e for e in sl.by_theme(self.bank, key)
                    if not needle or needle in e["text"].lower()]
            if not rows:
                continue
            parent = QTreeWidgetItem(self.library, ["", cfg["label"]])
            parent.setToolTip(1, cfg["note"])
            parent.setExpanded(True)
            for entry in rows:
                child = QTreeWidgetItem(parent, [str(entry["n"]), entry["text"]])
                child.setData(0, Qt.ItemDataRole.UserRole, entry["text"])
                shown += 1
        self.library.setColumnWidth(0, 44)
        self.library.setColumnWidth(1, 460)
        if needle or theme:
            self.status.emit("{} of 100 examples".format(shown))

    def copy_example(self, item=None):
        if item is None:
            self.status.emit("Pick an example first")
            return
        text = item.data(0, Qt.ItemDataRole.UserRole)
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    # -- compose ----------------------------------------------------------- #
    def rebuild_compose(self):
        if not hasattr(self, "compose_tree"):
            return
        source = self.source.text().strip()
        action = self.action.text().strip()
        if not source and not action:
            self.composed.setText("")
            self.compose_tree.clear()
            self.compose_badge.set_status("neutral", "0/4")
            self.compose_advice.setText("")
            return

        text = bsd.compose(self.bank, source, action,
                           self.place.text().strip() or None,
                           self.treatment.text().strip() or None)
        self.composed.setText(text)

        results = sl.lint(self.bank, text)
        got, total = sl.score(results)
        self.compose_tree.clear()
        for _, label, passed, detail in results:
            row = QTreeWidgetItem(self.compose_tree, ["", label, detail])
            row.setText(0, "OK" if passed else "!")
            row.setForeground(0, QColor(self._palette.get(
                "success" if passed else "error", "#34D399" if passed else "#F87171")))
        self.compose_tree.setColumnWidth(0, 30)
        self.compose_tree.setColumnWidth(1, 180)
        self.compose_badge.set_status("success" if got == total else "danger",
                                      "{}/{}".format(got, total))
        notes = sl.advice(self.bank, text)
        self.compose_advice.setText(" ".join(notes))

    def copy_composed(self):
        text = self.composed.text().strip()
        if not text:
            self.status.emit("Nothing composed yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    # -- the story's sheet -------------------------------------------------- #
    def scenes(self):
        return list(self.context() or []) if self.context else []

    def sheets(self):
        theme = "comedy"
        if hasattr(self, "theme_for_scenes"):
            theme = self.theme_for_scenes.currentData() or "comedy"
        return bsd.story_sound(self.bank, self.scenes(), theme=theme)

    def rebuild(self):
        if not hasattr(self, "scene_tree"):
            return
        scenes = self.scenes()
        self.scene_tree.clear()
        if not scenes:
            self.scene_note.setText(
                "No story open. Build one in Cats, then come back - this sheet is "
                "generated from its scenes.")
            return

        sheets = self.sheets()
        failing = 0
        for sheet in sheets:
            parent = QTreeWidgetItem(
                self.scene_tree, ["{}. {}".format(sheet["n"], sheet["label"]), "", ""])
            parent.setExpanded(True)
            for layer in sheet["layers"]:
                child = QTreeWidgetItem(parent, ["", layer["label"], layer["text"]])
                child.setToolTip(1, "{}\n\n{}".format(layer["role"], layer["note"]))
                if not layer["passed"]:
                    failing += 1
                    child.setForeground(2, QColor(
                        self._palette.get("error", "#F87171")))
                    child.setToolTip(2, "; ".join(layer["failures"]))
        self.scene_tree.setColumnWidth(0, 150)
        self.scene_tree.setColumnWidth(1, 110)
        self.scene_note.setText(
            "{} scenes, {} prompts{}.".format(
                len(sheets), len(sheets) * 3,
                "" if not failing else " - {} need work".format(failing)))

    def copy_sheet(self):
        sheets = self.sheets()
        if not sheets:
            self.status.emit("No story open")
            return
        QGuiApplication.clipboard().setText(bsd.sheet_text(sheets))
        self.status.emit("Sound sheet copied - {} prompts".format(len(sheets) * 3))

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.rebuild_compose()
        self.rebuild()

    def refresh(self):
        self.rebuild()
