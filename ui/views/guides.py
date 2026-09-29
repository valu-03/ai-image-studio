"""The guides that were already written, finally reachable from inside the app.

workflows/*.md is sixteen files of real onboarding - ai-creator-workflow.md is
literally the missing first-run tour - and until now it had ZERO references from
any code path. It was documentation for whoever browsed the repo, which is not
the person who most needs it. It was also not bundled into the .exe, so for
anyone running the built app it did not exist at all.

A dialog rather than an eleventh rail section, for the reason NAV_ITEMS'
own comment gives: Ctrl+1..0 is generated from NAV_ITEMS[:10], so an eleventh
section would be the only one in the app with no shortcut. It opens from the
Help menu and from Ctrl+/ .

QTextBrowser.setMarkdown() does the rendering. That is Qt's own parser, so
there is no Markdown dependency and no hand-rolled formatter to get wrong -
the same "use the toolkit's own facility" call the rest of this UI makes.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

ROOT = Path(__file__).resolve().parent.parent.parent

from ..widgets import MutedLabel, TitleLabel  # noqa: E402
from .. import tokens as T  # noqa: E402

#: Where the guides live when running from source. The frozen build copies
#: `workflows` in via AIVideoStudio.spec's `datas`, next to `tools` and
#: `assets`, so sys._MEIPASS is checked first exactly as assets.py does.
def guides_dir():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "workflows"
        if bundled.exists():
            return bundled
    return ROOT / "workflows"


def guide_files():
    """Every guide, README first - it is the index the others assume."""
    folder = guides_dir()
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.md"), key=lambda p: (p.name != "README.md", p.name))
    return files


def title_for(path):
    """The guide's own first heading, falling back to its filename.

    Reading the title out of the file rather than keeping a table of them is
    what stops the menu drifting from the documents, the same reasoning
    build_actions() applies to NAV_ITEMS.
    """
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("-", " ").capitalize()


class GuidesDialog(QDialog):
    """A list of the workflow guides, and the selected one rendered."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guides")
        self.resize(900, 620)

        self.list = QListWidget()
        self.list.setMaximumWidth(260)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)

        self._paths = guide_files()
        for path in self._paths:
            item = QListWidgetItem(title_for(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(path.name)
            self.list.addItem(item)
        self.list.currentRowChanged.connect(self.show_guide)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        header = QVBoxLayout()
        header.addWidget(TitleLabel("Guides"))
        header.addWidget(MutedLabel(
            "The workflows this app was built around. Start with "
            "“The AI creator workflow” if this is your first time."))

        split = QHBoxLayout()
        split.setSpacing(T.COLUMN_GAP)
        split.addWidget(self.list)
        split.addWidget(self.view, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE["md"], T.SPACE["md"],
                                  T.SPACE["md"], T.SPACE["md"])
        layout.setSpacing(T.SPACE["md"])
        layout.addLayout(header)
        layout.addLayout(split, 1)
        layout.addLayout(footer)

        if self._paths:
            self.list.setCurrentRow(0)
        else:
            self.view.setPlainText(
                "No guides found. They live in workflows/*.md next to the app.")

    def show_guide(self, row):
        if row < 0 or row >= len(self._paths):
            return
        path = self._paths[row]
        try:
            self.view.setMarkdown(path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.view.setPlainText("Could not read {}:\n{}".format(path.name, exc))
