"""History view — every logged generation, and what changed between any two."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import history as hist  # noqa: E402

from .. import tokens as T  # noqa: E402
from ..widgets import Card, ImagePreview, MutedLabel, StarRating, TitleLabel  # noqa: E402

COLUMNS = ["Rating", "Score", "Seed", "Character", "When", "Image"]


class HistoryView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or T.PALETTES[T.DEFAULT_THEME]
        self._filter = ""
        self.entries = []
        self.setup_ui()

    def setup_ui(self):
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.table.itemSelectionChanged.connect(self.on_selection)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        self.diff_button = QPushButton("Diff selected")
        self.diff_button.setToolTip("Select exactly two rows to compare their prompts")
        self.diff_button.clicked.connect(self.show_diff)
        self.diff_button.setEnabled(False)

        buttons = QHBoxLayout()
        buttons.setSpacing(T.SPACE["sm"])
        buttons.addWidget(refresh)
        buttons.addWidget(self.diff_button)
        buttons.addStretch(1)

        self.rating = StarRating()
        self.rating.rated.connect(self.rate_selected)
        buttons.addWidget(MutedLabel("Rate selected:"))
        buttons.addWidget(self.rating)

        table_card = Card()
        table_card.body.setSpacing(T.SPACE["sm"])
        table_card.body.addWidget(TitleLabel("Generation history"))
        table_card.body.addLayout(buttons)
        table_card.body.addWidget(self.table, 1)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setProperty("class", "mono")
        self.detail.setPlaceholderText(
            "Select a row to see its prompt, or two rows and press Diff selected."
        )
        self.preview = ImagePreview("No image for this entry")
        self.preview.setMaximumHeight(260)

        detail_card = Card()
        detail_card.body.setSpacing(T.SPACE["sm"])
        detail_card.body.addWidget(TitleLabel("Detail"))
        detail_card.body.addWidget(self.preview)
        detail_card.body.addWidget(self.detail, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("history_table_detail")
        splitter.addWidget(table_card)
        splitter.addWidget(detail_card)
        splitter.setSizes([640, 520])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.reload()

    def set_filter(self, text):
        self._filter = (text or "").strip().lower()
        self.reload()

    def set_palette_tokens(self, palette):
        self._palette = palette
        self.reload()

    def reload(self):
        self.entries = list(reversed(hist.load()))
        if self._filter:
            needle = self._filter
            self.entries = [
                e for e in self.entries
                if needle in (e.get("slug", "") + e.get("subject", "") + e.get("prompt", "")).lower()
            ]
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            rating = entry.get("rating")
            stars = ("★" * rating + "☆" * (5 - rating)) if rating else "—"
            values = [
                stars,
                "{}/8".format(entry.get("score", "?")),
                str(entry.get("seed", 0)),
                entry.get("slug") or entry.get("subject", "")[:48],
                entry.get("ts", "")[5:16].replace("T", " "),
                Path(entry.get("image", "")).name if entry.get("image") else "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0 and rating:
                    key = "success" if rating >= 4 else ("error" if rating <= 2 else "warning")
                    item.setForeground(QBrush(QColor(self._palette[key])))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.status.emit("{} entries".format(len(self.entries)))

    def selected_entries(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        return [self.entries[row] for row in rows if 0 <= row < len(self.entries)]

    def on_selection(self):
        chosen = self.selected_entries()
        self.diff_button.setEnabled(len(chosen) == 2)
        if len(chosen) == 1:
            entry = chosen[0]
            self.rating.set_value(entry.get("rating") or 0)
            self.detail.setPlainText(
                "id     {id}\nseed   {seed}   score {score}/8   rating {rating}\n"
                "shot   {shot}\nnote   {note}\n\n{prompt}".format(
                    id=entry["id"], seed=entry.get("seed"), score=entry.get("score"),
                    rating=entry.get("rating") or "-", shot=entry.get("shot") or "-",
                    note=entry.get("note") or "-", prompt=entry.get("prompt", ""),
                )
            )
            image = entry.get("image")
            if image and Path(image).exists():
                self.preview.load(image)
            else:
                self.preview.clear_image()

    def show_diff(self):
        chosen = self.selected_entries()
        if len(chosen) != 2:
            return
        older, newer = chosen[1], chosen[0]
        removed, added = hist.diff_prompts(older.get("prompt", ""), newer.get("prompt", ""))
        lines = [
            "--- {}  rating {}".format(older["id"], older.get("rating") or "-"),
            "+++ {}  rating {}".format(newer["id"], newer.get("rating") or "-"),
            "",
        ]
        lines += ["  - " + segment for segment in removed]
        lines += ["  + " + segment for segment in added]
        if not removed and not added:
            lines.append("  (identical segments)")
        self.detail.setPlainText("\n".join(lines))

    def rate_selected(self, value):
        chosen = self.selected_entries()
        if len(chosen) != 1:
            self.status.emit("Select exactly one row to rate")
            return
        hist.rate(chosen[0]["id"], value)
        self.reload()
        self.status.emit("Rated {}/5".format(value))
