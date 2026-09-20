"""Cats / Custom Prompt tab - a hand-written prompt in, adapted by conversation.

Every other Cats tab BUILDS a prompt, scene by scene, from story_bank.json's
beats and prompt_bank.json's realism layers (build_story.compose_story ->
build_prompt.compose). This tab does the opposite: the user already has a
fully-written shot description (like the GoPro-selfie cat example this was
built from) and wants it split into its parts, then adapted - by a change
instruction, by a reference image, or both - until it is ready to generate.

Nothing here touches build_story.py's beat/arc engine. This is one shot, not
a story in scenes, and it is deliberately a separate tab rather than folded
into Story/Scenes for that reason.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import history as hist  # noqa: E402
import realism_lint as rl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Card, GateTree, MutedLabel, ResultCard, TitleLabel  # noqa: E402
from ..workers import LlmTask  # noqa: E402


def assemble_prompt(subject, background, style):
    """Subject/Background/Style & Atmosphere -> one prompt, in the exact
    three-part shape this tab was built from. A plain deterministic join, not
    an LLM round-trip - the user is already watching the text change as they
    type, and a second network call to re-render it would only add lag.
    """
    return "Subject: {}\n\nBackground: {}\n\nStyle & Atmosphere: {}".format(
        (subject or "").strip(), (background or "").strip(), (style or "").strip())


class CustomPromptTab(QWidget):
    """Paste a prompt -> Subject/Background/Style, editable and re-adaptable.

    Emits `custom_generate_requested` with (prompt, references) - references
    is always empty: the reference image here informs the wording only (the
    user's own choice), it never doubles as a generation identity-lock the
    way Compose's reference does.
    """

    custom_generate_requested = pyqtSignal(str, list)
    status = pyqtSignal(str)

    # Same enum SpecEditor's own aspect combo offers - one list stated once
    # would be nice, but that combo lives on a QWidget this tab has no
    # reason to depend on for six literal strings.
    ASPECT_OPTIONS = ["", "1:1", "4:5", "3:2", "16:9", "9:16"]

    def __init__(self, bank, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bank                 # the image/realism bank (prompt_bank.json)
        self._palette = palette or {}
        self._reference_path = ""
        self.current_image = None
        self.entry_id = None
        self._score = 0
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setup_ui()
        self.rebuild_preview()

    # -- construction -------------------------------------------------------- #
    def setup_ui(self):
        left = self._build_left()
        right = self._build_right()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(320)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setWidget(right)
        right_scroll.setMinimumWidth(320)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("cats_custom_left_right")
        split.addWidget(left_scroll)
        split.addWidget(right_scroll)
        split.setChildrenCollapsible(False)
        split.setSizes([420, 460])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(split)

    def _build_left(self):
        self.paste_box = QPlainTextEdit()
        self.paste_box.setPlaceholderText(
            "Paste a full prompt here - e.g. \"Subject: ... Background: ... "
            "Style & Atmosphere: ...\"")
        self.paste_box.setFixedHeight(140)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setIcon(assets.icon("brief"))
        self.analyze_button.setIconSize(assets.ICON_SIZE)
        self.analyze_button.setToolTip(
            "Splits the pasted prompt into Subject / Background / Style & "
            "Atmosphere below. Uses OpenRouter; if a reference image is set, "
            "it may sharpen a vague detail but never invents beyond what it "
            "shows.")
        self.analyze_button.clicked.connect(self.analyze)
        self.analyze_badge = AiSuggestionBadge("Analyzing…")
        self.analyze_badge.set_status("neutral", "not run")

        paste_card = Card()
        paste_card.body.addWidget(TitleLabel("Paste a prompt"))
        paste_card.body.addWidget(self.paste_box)
        analyze_row = QHBoxLayout()
        analyze_row.addWidget(self.analyze_button)
        analyze_row.addWidget(self.analyze_badge)
        analyze_row.addStretch(1)
        paste_card.body.addLayout(analyze_row)

        # Shared by both Analyze and Refine below - a reference image is an
        # input to this whole tab, not a control scoped to one step. "This is
        # what the prompt is based on" applies just as much to the first pass
        # as to a later change.
        self.reference_button = QPushButton("Choose reference image…")
        self.reference_button.setProperty("class", "ghost")
        self.reference_button.clicked.connect(self.choose_reference)
        self.reference_clear = QPushButton("Clear")
        self.reference_clear.setProperty("class", "ghost")
        self.reference_clear.clicked.connect(self.clear_reference)
        self.reference_label = MutedLabel(
            "No reference image - analysis and changes go by text alone.")

        reference_card = Card()
        reference_card.body.addWidget(TitleLabel("Reference image"))
        ref_row = QHBoxLayout()
        ref_row.addWidget(self.reference_button)
        ref_row.addWidget(self.reference_clear)
        ref_row.addStretch(1)
        reference_card.body.addLayout(ref_row)
        reference_card.body.addWidget(self.reference_label)

        self.subject_box = QPlainTextEdit()
        self.background_box = QPlainTextEdit()
        self.style_box = QPlainTextEdit()

        fields_card = Card()
        fields_card.body.addWidget(TitleLabel("Subject / Background / Style"))
        for label, box in (("Subject", self.subject_box),
                           ("Background", self.background_box),
                           ("Style & Atmosphere", self.style_box)):
            fields_card.body.addWidget(MutedLabel(label))
            box.setFixedHeight(80)
            box.textChanged.connect(self.rebuild_preview)
            fields_card.body.addWidget(box)

        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(paste_card)
        layout.addWidget(reference_card)
        layout.addWidget(fields_card)
        return left

    def _build_right(self):
        self.full_prompt_view = QPlainTextEdit()
        self.full_prompt_view.setReadOnly(True)
        self.full_prompt_view.setProperty("class", "mono")
        self.full_prompt_view.setFixedHeight(120)
        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_prompt)

        preview_card = Card()
        head = QHBoxLayout()
        head.addWidget(TitleLabel("Full prompt"))
        head.addStretch(1)
        head.addWidget(copy_button)
        preview_card.body.addLayout(head)
        preview_card.body.addWidget(self.full_prompt_view)
        preview_card.body.addWidget(TitleLabel("Realism check"))
        self.gate = GateTree()
        self.gate.tree.setMinimumHeight(76)
        preview_card.body.addWidget(self.gate, 1)

        self.instruction = QLineEdit(placeholderText="tell me what to change")
        self.instruction.returnPressed.connect(self.refine)
        self.refine_button = QPushButton("Apply change")
        self.refine_button.clicked.connect(self.refine)
        self.refine_badge = AiSuggestionBadge("Adapting…")
        self.refine_badge.set_status("neutral", "not run")

        refine_card = Card()
        refine_card.body.addWidget(TitleLabel("Refine"))
        refine_card.body.addWidget(self.instruction)
        refine_card.body.addWidget(MutedLabel(
            "Leave this blank and just set a reference image above to adapt "
            "the prompt to match it - the instruction and the image both "
            "work on their own."))
        apply_row = QHBoxLayout()
        apply_row.addWidget(self.refine_button)
        apply_row.addWidget(self.refine_badge)
        apply_row.addStretch(1)
        refine_card.body.addLayout(apply_row)

        self.aspect = QComboBox()
        self.aspect.setEditable(True)
        self.aspect.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.aspect.addItems(self.ASPECT_OPTIONS)
        self.aspect.setToolTip("Leave blank for the provider's default aspect.")

        self.generate_button = QPushButton("Generate the still")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.setEnabled(False)
        self.generate_button.setToolTip(
            "Enabled once the realism check passes - the same 8/8, no-banned-"
            "terms gate every other prompt in the app has to clear first.")
        self.generate_button.clicked.connect(self.request_generate)

        self.result = ResultCard(0, "")
        self.result.rated.connect(self.rate_result)

        generate_card = Card()
        generate_card.body.addWidget(TitleLabel("Generate"))
        aspect_row = QHBoxLayout()
        aspect_row.addWidget(MutedLabel("Aspect"))
        aspect_row.addWidget(self.aspect)
        aspect_row.addStretch(1)
        generate_card.body.addLayout(aspect_row)
        generate_card.body.addWidget(self.generate_button)
        generate_card.body.addWidget(self.result)

        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(preview_card)
        layout.addWidget(refine_card)
        layout.addWidget(generate_card)
        return right

    # -- reference image ------------------------------------------------------ #
    def choose_reference(self):
        start = str(assets.IMAGES_DIR if assets.IMAGES_DIR.exists() else ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a reference image", start, "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self._reference_path = path
            self.reference_label.setText("Reference: " + Path(path).name)

    def clear_reference(self):
        self._reference_path = ""
        self.reference_label.setText(
            "No reference image - analysis and changes go by text alone.")

    # -- analyze --------------------------------------------------------------- #
    def analyze(self):
        text = self.paste_box.toPlainText().strip()
        if not text:
            self.status.emit("Paste a prompt first")
            return
        self.analyze_badge.thinking()
        self.analyze_button.setEnabled(False)
        task = LlmTask("analyze_custom_prompt", self.bank, text, self._reference_path or None)
        task.signals.finished.connect(self.on_analyzed)
        task.signals.failed.connect(self.on_analyze_failed)
        task.signals.done.connect(lambda _a: self.analyze_button.setEnabled(True))
        self.pool.start(task)

    def on_analyzed(self, _action, result):
        self._fill_fields(result.get("fields") or {})
        self.analyze_badge.set_status("success", "split into 3 parts")
        if result.get("dropped"):
            self.status.emit("Ignored: " + ", ".join(result["dropped"]))

    def on_analyze_failed(self, _action, reason):
        self.analyze_badge.set_status("danger", "failed")
        self.status.emit(reason[:160])

    # -- refine ------------------------------------------------------------- #
    def refine(self):
        instruction = self.instruction.text().strip()
        if not instruction and not self._reference_path:
            self.status.emit("Say what to change, or set a reference image, first")
            return
        fields = {
            "subject": self.subject_box.toPlainText(),
            "background": self.background_box.toPlainText(),
            "style": self.style_box.toPlainText(),
        }
        self.refine_badge.thinking()
        self.refine_button.setEnabled(False)
        task = LlmTask("refine_custom_prompt", self.bank, fields, instruction,
                       self._reference_path or None)
        task.signals.finished.connect(self.on_refined)
        task.signals.failed.connect(self.on_refine_failed)
        task.signals.done.connect(lambda _a: self.refine_button.setEnabled(True))
        self.pool.start(task)

    def on_refined(self, _action, result):
        self._fill_fields(result.get("fields") or {})
        self.refine_badge.set_status("success", "updated")
        self.instruction.clear()
        if result.get("dropped"):
            self.status.emit("Ignored: " + ", ".join(result["dropped"]))

    def on_refine_failed(self, _action, reason):
        self.refine_badge.set_status("danger", "failed")
        self.status.emit(reason[:160])

    def _fill_fields(self, fields):
        for key, box in (("subject", self.subject_box),
                         ("background", self.background_box),
                         ("style", self.style_box)):
            box.blockSignals(True)
            box.setPlainText(fields.get(key, box.toPlainText()))
            box.blockSignals(False)
        self.rebuild_preview()

    # -- the gate -------------------------------------------------------------- #
    def rebuild_preview(self):
        prompt = assemble_prompt(
            self.subject_box.toPlainText(), self.background_box.toPlainText(),
            self.style_box.toPlainText())
        self.full_prompt_view.setPlainText(prompt)
        checks = rl.checks_for(prompt, self.bank)
        self.gate.set_checks(checks)
        self._score = sum(1 for c in checks if c["passed"])
        self.generate_button.setEnabled(self.gate.all_passed())

    def copy_prompt(self):
        text = self.full_prompt_view.toPlainText()
        if not text.strip():
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied")

    # -- generation -------------------------------------------------------------- #
    def request_generate(self):
        if not self.gate.all_passed():
            self.status.emit("Fix the realism check first")
            return
        prompt = self.full_prompt_view.toPlainText()
        spec = {}
        aspect = self.aspect.currentText().strip()
        if aspect:
            spec["aspect"] = aspect
        self.entry_id = hist.append(spec, prompt, {}, self._score, True, detailed=False)
        self.result.preview.clear_image()
        self.result.set_status("accent", "generating…")
        self.generate_button.setEnabled(False)
        # No reference: this tab's reference image informs the wording only,
        # never the generation identity-lock (the user's own choice).
        self.custom_generate_requested.emit(prompt, [])

    # -- batch feedback - the contract MainWindow._batch.target must have ----- #
    def set_busy(self, busy, total=0):
        self.generate_button.setEnabled(not busy and self.gate.all_passed())

    def set_progress(self, completed, total):
        pass   # one job at a time here - nothing to show beyond the busy state

    def on_item_finished(self, index, path):
        self.current_image = str(path)
        self.result.set_image(path)
        self.result.set_status("success", "ready")
        self.result.set_caption(Path(path).name)
        if self.entry_id:
            hist.rate(self.entry_id, None, image=str(path))
        self.generate_button.setEnabled(self.gate.all_passed())
        self.status.emit("Saved {}".format(Path(path).name))

    def on_item_failed(self, index, reason):
        self.result.set_status("danger", "failed")
        self.generate_button.setEnabled(self.gate.all_passed())
        self.status.emit(reason[:160])

    def rate_result(self, _index, value):
        if not self.entry_id:
            self.status.emit("Nothing to rate yet")
            return
        hist.rate(self.entry_id, value, image=str(self.current_image or ""))
        self.status.emit("Rated {}/5".format(value))

    # -- theming ---------------------------------------------------------------- #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.gate.set_palette_tokens(self._palette)
