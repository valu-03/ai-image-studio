"""Anatomy tab - the prompt SKELETON, taught and checked.

Two halves, one for each direction:

  Skeleton   pick a template and read its slots in order - what each one does,
             WHY it matters, and a worked example. This is the half you read to
             write your own prompt from scratch, and its two Copy buttons hand
             you the same shape as text: empty, or with the examples in place.
  Check      paste a prompt you already have and see which slots it fills and
             which it leaves empty.

Every word of vocabulary and every detection decision comes from
tools/prompt_anatomy.py - this view composes no phrases and owns no keyword
list of its own. A slot that maps onto one of the eight gated realism layers
is detected by tools/realism_lint.py's own DETECT table, so this tab and the
8/8 gate on the Images tab can never disagree about what counts as (say)
camera language.

Nothing here writes to Compose. An empty slot is a decision not yet made, not
an error, and this tab says so rather than offering to "fix" a prompt.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import prompt_anatomy as pa  # noqa: E402

from .. import tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

EMPTY_HINT = "Paste a prompt above and press Check."


class AnatomyView(QWidget):
    """Emits `status`. Read-only: nothing here reaches Compose."""

    status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bank = pa.load_bank()

        self.picker = QComboBox()
        # A QComboBox sizes itself to its longest item by default, and the
        # longest template label here ran the whole Assistant tab widget's
        # minimum width up past its siblings' - which squeezed BriefView's own
        # card until its preview and buttons overlapped at the minimum window
        # size (caught by tests/test_layout.py, not by eye). Cap the width it
        # asks for and let the popup be as wide as it likes.
        self.picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.picker.setMinimumContentsLength(24)
        for key, cfg in pa.templates(self.bank).items():
            self.picker.addItem("{}  ({} slots)".format(cfg["label"], len(cfg["slots"])), key)
        self.picker.currentIndexChanged.connect(self._on_template_changed)

        self.summary = MutedLabel("")
        self.summary.setWordWrap(True)

        self.skeleton_body = QVBoxLayout()
        self.skeleton_body.setSpacing(T.SPACE["sm"])
        skeleton_holder = QWidget()
        skeleton_holder.setLayout(self.skeleton_body)
        skeleton_scroll = QScrollArea()
        skeleton_scroll.setWidgetResizable(True)
        skeleton_scroll.setWidget(skeleton_holder)

        # Reading the skeleton is half of it; the other half is having the
        # shape in front of you while you write. Both buttons put text on the
        # clipboard and nothing else - this tab still writes to no other view.
        self.copy_blank = QPushButton("Copy structure")
        self.copy_blank.setToolTip(
            "Copy the empty skeleton - every slot as a heading with its job as "
            "the placeholder. Paste it anywhere and fill it in.")
        self.copy_blank.clicked.connect(lambda: self._copy(False))
        self.copy_filled = QPushButton("Copy worked example")
        self.copy_filled.setToolTip(
            "Copy the same skeleton with this template's worked examples "
            "already in place, to edit down rather than write up.")
        self.copy_filled.clicked.connect(lambda: self._copy(True))

        skeleton_page = QWidget()
        skeleton_layout = QVBoxLayout(skeleton_page)
        skeleton_layout.setContentsMargins(0, 0, 0, 0)
        skeleton_layout.setSpacing(T.SPACE["sm"])
        copy_row = QHBoxLayout()
        copy_row.addWidget(self.copy_blank)
        copy_row.addWidget(self.copy_filled)
        copy_row.addStretch(1)
        skeleton_layout.addLayout(copy_row)
        skeleton_layout.addWidget(skeleton_scroll, 1)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Paste any prompt here - your own, or one you found - and press Check.")
        self.check_button = QPushButton("Check")
        self.check_button.clicked.connect(self.run_check)
        self.coverage = Badge("")
        self.result_body = QVBoxLayout()
        self.result_body.setSpacing(T.SPACE["sm"])
        result_holder = QWidget()
        result_holder.setLayout(self.result_body)
        result_scroll = QScrollArea()
        result_scroll.setWidgetResizable(True)
        result_scroll.setWidget(result_holder)

        check_page = QWidget()
        check_layout = QVBoxLayout(check_page)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.setSpacing(T.SPACE["sm"])
        check_layout.addWidget(self.input, 1)
        row = QHBoxLayout()
        row.addWidget(self.check_button)
        row.addWidget(self.coverage)
        row.addStretch(1)
        check_layout.addLayout(row)
        check_layout.addWidget(result_scroll, 2)

        self.tabs = QTabWidget()
        self.tabs.addTab(skeleton_page, "Skeleton")
        self.tabs.addTab(check_page, "Check a prompt")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(MutedLabel(
            "The shape of a prompt, not its words. Read the skeleton to write your "
            "own; paste one in to see which slots it already fills."))
        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Template"))
        picker_row.addWidget(self.picker, 1)
        layout.addLayout(picker_row)
        layout.addWidget(self.summary)
        layout.addWidget(self.tabs, 1)

        self._on_template_changed()

    # ---------------------------------------------------------------- helpers
    def current_template(self):
        return self.picker.currentData()

    def scaffold_text(self, filled):
        """The current template as pasteable text. Composed by the tool, not here."""
        name = self.current_template()
        if not name:
            return ""
        return "\n".join(pa.scaffold_lines(self.bank, name, filled=filled))

    def _copy(self, filled):
        text = self.scaffold_text(filled)
        if not text:
            return
        QApplication.clipboard().setText(text)
        label = pa.templates(self.bank)[self.current_template()]["label"]
        self.status.emit("Copied the {} {} - paste it anywhere.".format(
            label, "worked example" if filled else "structure"))

    def _clear(self, box):
        """Empty a layout, leaving nothing behind that can still paint.

        deleteLater() alone is not enough: it only schedules deletion, so the
        widget stays a child of the holder with its old geometry until the
        event loop gets round to it, and can still draw over the new content.
        setParent(None) takes it out of the tree immediately.
        """
        while box.count():
            item = box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # ----------------------------------------------------------------- render
    def _on_template_changed(self):
        name = self.current_template()
        if not name:
            return
        cfg = pa.templates(self.bank)[name]
        self.summary.setText(cfg["summary"])

        self._clear(self.skeleton_body)
        for index, slot in enumerate(pa.slots(self.bank, name), 1):
            card = Card()
            # Card builds its own QVBoxLayout in __init__ and exposes it as
            # `.body`. Calling QVBoxLayout(card) here instead created a SECOND
            # layout, which Qt refuses to install - so every label added to it
            # was orphaned and the cards rendered as empty rounded boxes. That
            # was the "no text" bug; always add into card.body.
            body = card.body
            body.setSpacing(T.SPACE["xs"])
            body.addWidget(TitleLabel("{}. {}".format(index, slot["label"])))
            for prefix, text in (("does", slot["does"]), ("why", slot["why"]),
                                 ("e.g.", slot["example"])):
                line = MutedLabel("{}   {}".format(prefix, text))
                line.setWordWrap(True)
                body.addWidget(line)
            body.addWidget(MutedLabel("detected by " + pa.slot_origin(slot)))
            self.skeleton_body.addWidget(card)
        self.skeleton_body.addStretch(1)
        self._clear(self.result_body)
        self.coverage.setText("")
        self.result_body.addWidget(MutedLabel(EMPTY_HINT))
        self.result_body.addStretch(1)

    def run_check(self):
        text = self.input.toPlainText().strip()
        self._clear(self.result_body)
        if not text:
            self.coverage.setText("")
            self.result_body.addWidget(MutedLabel(EMPTY_HINT))
            self.result_body.addStretch(1)
            self.status.emit("Paste a prompt to check.")
            return

        name = self.current_template()
        rows = pa.analyse(self.bank, name, text)
        filled, total = pa.coverage(rows)
        self.coverage.setText("{}/{} slots".format(filled, total))

        for slot, present, hit in rows:
            card = Card()
            body = card.body  # see _on_template_changed - never QVBoxLayout(card)
            body.setSpacing(T.SPACE["xs"])
            mark = "filled" if present else "empty"
            body.addWidget(TitleLabel("{}  -  {}".format(slot["label"], mark)))
            if present:
                body.addWidget(MutedLabel("found \"{}\"".format(hit)))
            else:
                for prefix, value in (("does", slot["does"]), ("why", slot["why"]),
                                      ("e.g.", slot["example"])):
                    line = MutedLabel("{}   {}".format(prefix, value))
                    line.setWordWrap(True)
                    body.addWidget(line)
            self.result_body.addWidget(card)

        note = MutedLabel(
            "Empty slots are not errors - they are decisions you have not made yet.")
        note.setWordWrap(True)
        self.result_body.addWidget(note)
        self.result_body.addStretch(1)
        self.status.emit("{}: {}/{} slots filled".format(
            pa.templates(self.bank)[name]["label"], filled, total))

    def refresh(self):
        return None
