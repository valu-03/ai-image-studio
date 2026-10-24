"""Prompt Bank - your own prompts, saved exactly as you gave them, with their example images.

Replaced the Anatomy tab (built-in templates split into teaching slots). This
holds no templates and has no opinions: every entry is a prompt the user
supplied, stored byte for byte by tools/saved_prompts.py, shown read-only and
copied back out unchanged. Split into Image and Video, like Anatomy was.

  list    every saved prompt of this kind, newest first
  view    the selected prompt in full, exactly as saved
  Add...  paste a prompt and title it - saved verbatim into this kind
  images  the prompt's example images as thumbnails: drag to reorder (saved to
          order.txt), double-click to open, right-click to rename
  Copy    the exact saved text (read from the file, never from the view widget,
          which normalises line endings for display)
  Add images...  attach more examples to the selected prompt (straight copies)
  Rename / Delete   Delete asks first, like the character library

Storage is temp/resources/prompt_bank/ - user data, never deleted unasked.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import saved_prompts as sp  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Card, MutedLabel, TitleLabel, set_empty_hint  # noqa: E402

KIND_LABELS = {"image": "Image", "video": "Video"}
THUMB = 112
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp *.tif *.tiff *.heic *.avif)"


def choose_images(parent):
    paths, _ = QFileDialog.getOpenFileNames(parent, "Choose example images", "", IMAGE_FILTER)
    return paths


class ThumbList(QListWidget):
    """A horizontal row of example-image thumbnails you can drag into a new order.

    Qt's own InternalMove in icon mode just repositions icons freely on the
    canvas and never reorders the rows, so the drop is handled here: dropped
    onto another thumbnail the two swap places; dropped in a gap it is
    re-inserted there. `order_changed` reports the new order by file name.
    """

    order_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Movement.Snap)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QSize(THUMB, THUMB))
        self.setGridSize(QSize(THUMB + 20, THUMB + 38))
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFixedHeight(THUMB + 62)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def names(self):
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

    def move_item(self, source, target):
        """Move the row at `source` to `target` and report the new order."""
        if not (0 <= source < self.count()):
            return False
        target = max(0, min(target, self.count() - 1))
        if target == source:
            return False
        item = self.takeItem(source)
        self.insertItem(target, item)
        self.setCurrentItem(item)
        self.order_changed.emit(self.names())
        return True

    def swap_items(self, a, b):
        """Swap the rows at `a` and `b` (each takes the other's place) and report the new order."""
        if not (0 <= a < self.count() and 0 <= b < self.count()) or a == b:
            return False
        low, high = min(a, b), max(a, b)
        high_item = self.takeItem(high)
        low_item = self.takeItem(low)
        self.insertItem(low, high_item)
        self.insertItem(high, low_item)
        self.setCurrentRow(b)
        self.order_changed.emit(self.names())
        return True

    def drop_row(self, x, source):
        """The row a thumbnail dropped at horizontal position `x` should land on.

        Read from the thumbnails' own positions, not from itemAt(): itemAt()
        is None in the gaps between thumbnails and in the empty space after
        the last one, which is exactly where people drop. Dropping past an
        item's centre means "after it"; the result is a final row index, so
        it accounts for the dragged item no longer being where it started.
        """
        centres = [self.visualItemRect(self.item(i)).center().x() for i in range(self.count())]
        slot = sum(1 for c in centres if x > c)       # insertion slot 0..count
        return slot - 1 if slot > source else slot

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        source = self.currentRow()
        # Dropped ON a thumbnail: the two swap places (nothing else moves).
        # Dropped in a gap or the empty space after the last one: land there
        # and the rest shift along (drop_row).
        over = self.itemAt(event.position().toPoint())
        if over is not None:
            self.swap_items(source, self.row(over))
        else:
            self.move_item(source, self.drop_row(event.position().x(), source))
        # THE BUG THIS AVOIDS: reporting MoveAction back to Qt makes its drag
        # code "finish the move" by deleting the selected item from the list
        # - which, after move_item(), is the very thumbnail just dropped, so
        # it vanished (the files were fine; the strip lost it). The move is
        # fully done above, so tell Qt there is nothing left for it to do.
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()


class AddPromptDialog(QDialog):
    """Paste a prompt and give it a title. The text box is plain text, so
    what is pasted is what is saved - no rich-text conversion."""

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add {} prompt".format(KIND_LABELS[kind].lower()))
        self.resize(640, 480)
        self.title_field = QLineEdit(placeholderText="a title, e.g. Active volcano infographic")
        self.text_field = QPlainTextEdit()
        self.text_field.setPlaceholderText("Paste the prompt here - it is saved exactly as pasted.")
        self.images = []
        self.images_label = MutedLabel("No example images yet - optional.")
        images_button = QPushButton("Choose example images…")
        images_button.setProperty("class", "ghost")
        images_button.clicked.connect(self._choose)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(MutedLabel("Title"))
        layout.addWidget(self.title_field)
        layout.addWidget(MutedLabel("Prompt"))
        layout.addWidget(self.text_field, 1)
        images_row = QHBoxLayout()
        images_row.addWidget(images_button)
        images_row.addWidget(self.images_label, 1)
        layout.addLayout(images_row)
        layout.addWidget(buttons)

    def _choose(self):
        picked = choose_images(self)
        if picked:
            self.images = list(picked)
            self.images_label.setText("{} example image(s): {}".format(
                len(self.images), ", ".join(Path(p).name for p in self.images)))


class PromptBankView(QWidget):
    """One kind's list + viewer. Emits `status`."""

    status = pyqtSignal(str)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setup_ui()
        self.reload()

    def setup_ui(self):
        self.list = QListWidget()
        set_empty_hint(self.list, "No saved prompts yet. Prompts you keep from the other sections collect here.", "save")
        self.list.setAlternatingRowColors(True)
        self.list.currentItemChanged.connect(self._on_selected)
        self.count_label = MutedLabel("")

        add_button = QPushButton("Add…")
        add_button.setProperty("class", "primary")
        add_button.clicked.connect(self.add_dialog)
        self.rename_button = QPushButton("Rename")
        self.rename_button.setProperty("class", "ghost")
        self.rename_button.clicked.connect(self.rename_dialog)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setProperty("class", "ghost")
        self.delete_button.clicked.connect(self.delete_selected)

        left = Card()
        left.body.addWidget(TitleLabel("{} prompts".format(KIND_LABELS[self.kind])))
        left.body.addWidget(self.count_label)
        left.body.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(add_button)
        row.addStretch(1)
        left.body.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(T.SPACE["sm"])
        row2.addWidget(self.rename_button)
        row2.addWidget(self.delete_button)
        row2.addStretch(1)
        left.body.addLayout(row2)
        left.setMinimumWidth(240)

        self.title_label = TitleLabel("No prompt selected")
        self.title_label.setWordWrap(True)
        self.meta_label = MutedLabel("")
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setMinimumHeight(60)
        self.viewer.setProperty("class", "mono")
        self.viewer.setPlaceholderText(
            "Your saved prompts appear here exactly as you gave them. Add one with "
            "\"Add…\", or give a prompt to Claude and ask for it to be saved.")
        self.copy_button = QPushButton("Copy prompt")
        self.copy_button.setIcon(assets.icon("copy"))
        self.copy_button.setIconSize(assets.ICON_SIZE)
        self.copy_button.clicked.connect(self.copy_selected)
        self.add_images_button = QPushButton("Add images…")
        self.add_images_button.setProperty("class", "ghost")
        self.add_images_button.clicked.connect(self.add_images_dialog)

        # Example images: a draggable row of thumbnails (ThumbList). Fixed
        # icon size on purpose - never let a scaled pixmap drive a size hint
        # (CLAUDE.md, ImagePreview).
        self.thumbs = ThumbList()
        self.thumbs.order_changed.connect(self._save_order)
        self.thumbs.itemDoubleClicked.connect(self._open_image_item)
        self.thumbs.customContextMenuRequested.connect(self._image_menu)

        right = Card()
        right.body.addWidget(self.title_label)
        right.body.addWidget(self.meta_label)
        right.body.addWidget(self.viewer, 1)
        right.body.addWidget(self.thumbs)
        copy_row = QHBoxLayout()
        copy_row.setSpacing(T.SPACE["sm"])
        copy_row.addWidget(self.copy_button)
        copy_row.addWidget(self.add_images_button)
        copy_row.addStretch(1)
        right.body.addLayout(copy_row)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(left, 2)
        layout.addWidget(right, 5)

    # -- data --------------------------------------------------------------- #
    def reload(self, select_path=None):
        current = select_path or self.selected_path()
        self.list.blockSignals(True)
        self.list.clear()
        rows = sp.entries(self.kind)
        for row in rows:
            item = QListWidgetItem("{}\n{:%d %b %Y, %H:%M}{}".format(
                row["title"], row["saved"],
                "  ·  {} image{}".format(row["images"], "" if row["images"] == 1 else "s")
                if row["images"] else ""))
            item.setData(Qt.ItemDataRole.UserRole, str(row["path"]))
            item.setToolTip(row["title"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.count_label.setText(
            "{} saved".format(len(rows)) if rows else "Nothing saved yet.")
        target = 0
        if current:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.ItemDataRole.UserRole) == str(current):
                    target = i
        if self.list.count():
            self.list.setCurrentRow(target)
        self._on_selected(self.list.currentItem(), None)

    def selected_path(self):
        item = self.list.currentItem() if hasattr(self, "list") else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_selected(self, item, _previous):
        has = item is not None
        for button in (self.copy_button, self.rename_button, self.delete_button,
                       self.add_images_button):
            button.setEnabled(has)
        if not has:
            self.title_label.setText("No prompt selected")
            self.meta_label.setText("")
            self.viewer.setPlainText("")
            self._show_images([])
            return
        entry = Path(item.data(Qt.ItemDataRole.UserRole))
        text = sp.read(entry)
        pictures = sp.images(entry)
        self.title_label.setText(entry.name)
        # The image hint rides this line rather than a row of its own: at the
        # 1100x700 floor the card has no spare height for one more label.
        self.meta_label.setText("{} characters · saved exactly as given · {} example image{}{}".format(
            len(text), len(pictures), "" if len(pictures) == 1 else "s",
            " - drag to reorder, double-click to open, right-click to rename" if pictures else ""))
        self.meta_label.setWordWrap(True)
        self.viewer.setPlainText(text)
        self._show_images(pictures)

    def _show_images(self, paths):
        self.thumbs.clear()
        for path in paths:
            pixmap = QPixmap(str(path))
            icon = QIcon(pixmap.scaled(
                THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)) if not pixmap.isNull() else QIcon()
            item = QListWidgetItem(icon, path.stem)
            item.setData(Qt.ItemDataRole.UserRole, path.name)
            item.setToolTip("{} - drag to reorder, double-click to open, right-click to "
                            "rename".format(path.name))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.thumbs.addItem(item)
        self.thumbs.setVisible(bool(paths))

    def _image_path(self, name):
        entry = self.selected_path()
        return Path(entry) / name if entry and name else None

    def _open_image_item(self, item):
        path = self._image_path(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _image_menu(self, pos):
        item = self.thumbs.itemAt(pos)
        if item is None:
            return
        row = self.thumbs.row(item)
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        rename_action = menu.addAction("Rename…")
        menu.addSeparator()
        left_action = menu.addAction("Move left")
        right_action = menu.addAction("Move right")
        left_action.setEnabled(row > 0)
        right_action.setEnabled(row < self.thumbs.count() - 1)
        chosen = menu.exec(self.thumbs.viewport().mapToGlobal(pos))
        if chosen is open_action:
            self._open_image_item(item)
        elif chosen is rename_action:
            self.rename_image_dialog(item)
        elif chosen is left_action:
            self.thumbs.setCurrentRow(row)
            self.thumbs.move_item(row, row - 1)
        elif chosen is right_action:
            self.thumbs.setCurrentRow(row)
            self.thumbs.move_item(row, row + 1)

    def _save_order(self, names):
        entry = self.selected_path()
        if not entry:
            return
        try:
            sp.set_order(entry, names)
        except sp.PromptBankError as exc:
            self.status.emit(str(exc))
            self._show_images(sp.images(entry))   # put the strip back as saved
            return
        self.status.emit("Image order saved")

    def rename_image(self, name, new_name):
        """Rename one example image (extension kept). Returns the new path, or None."""
        path = self._image_path(name)
        if not path:
            return None
        try:
            target = sp.rename_image(path, new_name)
        except sp.PromptBankError as exc:
            self.status.emit(str(exc))
            return None
        self._show_images(sp.images(self.selected_path()))
        self.status.emit("Renamed image to " + target.name)
        return target

    def rename_image_dialog(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        text, ok = QInputDialog.getText(
            self, "Rename image", "New name (the extension is kept):", text=Path(name).stem)
        if ok:
            self.rename_image(name, text)

    # -- actions ------------------------------------------------------------ #
    def add_prompt(self, title, text, images=()):
        """Save verbatim (with any example images) and select it. Returns the
        prompt's folder, or None on refusal."""
        try:
            path = sp.add(self.kind, title, text, images)
        except sp.PromptBankError as exc:
            self.status.emit(str(exc))
            return None
        self.reload(select_path=path)
        self.status.emit("Saved to your Prompt Bank: " + path.name)
        return path

    def add_dialog(self):
        dialog = AddPromptDialog(self.kind, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_prompt(dialog.title_field.text(), dialog.text_field.toPlainText(),
                            dialog.images)

    def attach_images(self, paths):
        """Copy example images into the selected prompt. Returns the new paths."""
        entry = self.selected_path()
        if not entry or not paths:
            return []
        try:
            copied = sp.attach(entry, paths)
        except sp.PromptBankError as exc:
            self.status.emit(str(exc))
            return []
        self.reload(select_path=entry)
        self.status.emit("Added {} example image(s)".format(len(copied)))
        return copied

    def add_images_dialog(self):
        if self.selected_path():
            self.attach_images(choose_images(self))

    def copy_selected(self):
        path = self.selected_path()
        if not path:
            self.status.emit("Pick a prompt first")
            return
        # From the file, not the viewer - the viewer normalises line endings.
        QGuiApplication.clipboard().setText(sp.read(path))
        self.status.emit("Copied: " + Path(path).name)

    def rename_selected(self, new_title):
        path = self.selected_path()
        if not path:
            return None
        try:
            target = sp.rename(path, new_title)
        except sp.PromptBankError as exc:
            self.status.emit(str(exc))
            return None
        self.reload(select_path=target)
        self.status.emit("Renamed to " + target.name)
        return target

    def rename_dialog(self):
        path = self.selected_path()
        if not path:
            return
        text, ok = QInputDialog.getText(self, "Rename prompt", "New title:", text=Path(path).name)
        if ok:
            self.rename_selected(text)

    def delete_selected(self):
        path = self.selected_path()
        if not path:
            return
        answer = QMessageBox.question(
            self, "Delete prompt",
            "Delete \"{}\" and its example images from your Prompt Bank? This cannot "
            "be undone.".format(Path(path).name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        sp.delete(path)
        self.reload()
        self.status.emit("Deleted " + Path(path).name)

    def refresh(self):
        """Pick up prompts saved from outside the app (e.g. by Claude) while it is open."""
        self.reload()


class PromptBankContainer(QWidget):
    """Image and Video, one PromptBankView each."""

    status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = PromptBankView("image")
        self.video = PromptBankView("video")
        self.tabs = QTabWidget()
        for view, label in ((self.image, "Image prompts"), (self.video, "Video prompts")):
            view.status.connect(self.status)
            self.tabs.addTab(view, label)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def refresh(self):
        self.tabs.currentWidget().refresh()
