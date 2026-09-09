"""Advisor - a real conversation with the built-in AI Video Studio expert.

Built on tools/advisor.py: every other AI feature in this app is one-shot
(BriefView's four tabs, Compose's autofill, Ads' draft-copy, Cats' write-
story), this is the one exception - a running back-and-forth - but the same
rule still holds. Nothing here decides whether a suggested spec is good; it
renders what advisor.py already judged. Context-aware for free: `self.context`
is the exact same `() -> (prompt, image)` callable MainWindow already wires
into BriefView, so a live realism score can be folded into every turn with no
new plumbing.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import advisor as advisor_tool  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Card, ImagePreview, MutedLabel, TitleLabel  # noqa: E402
from ..workers import LlmTask  # noqa: E402

GREETING = (
    "Describe the avatar you want and I'll fill in every section for you - "
    "subject, lighting, composition, colour grade, posing and camera angle - "
    "ready to apply in one click. Or just ask: which section to open, which "
    "technique to stack, what your current prompt is missing. I can also look "
    "at a photo if you attach one."
)

# How each technique section is named in the badge's summary line. The keys
# are tools/advisor.py's own SECTION_NAMES; the labels match the nav rail so
# "+ Color Grading" points at something the user can actually go and open.
SECTION_LABELS = {
    "lighting": "Lighting",
    "composition": "Composition",
    "color": "Color Grading",
    "posing": "Posing",
    "camera_angle": "Camera Angle",
}


class _Bubble(QFrame):
    """One message in the transcript - a word-wrapping label in a small
    rounded frame, styled by role. The same proven, low-risk shape (a
    wrapping QLabel inside a scroll area) already used everywhere else in
    this app, not a new delegate or model/view widget."""

    def __init__(self, role, text, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setProperty("bubbleRole", role)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE["sm"], T.SPACE["xs"], T.SPACE["sm"], T.SPACE["xs"])
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)


class AdvisorView(QWidget):
    """Emits `status`, `spec_suggested(dict)` - reusing BriefView's exact
    signal name/shape, so MainWindow wires it identically - and
    `sections_suggested(dict)`, `{section: composed phrase}` for the five
    technique sections, routed by MainWindow to the same
    `SpecEditor.set_X_override()` methods each section's own Apply button
    already calls."""

    status = pyqtSignal(str)
    spec_suggested = pyqtSignal(dict)
    sections_suggested = pyqtSignal(dict)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.bank = bank
        self.pool = QThreadPool(self)
        # One at a time, on purpose: a conversation is inherently ordered (a
        # turn is answered in light of the one before it), unlike BriefView's
        # 4 independent one-shot tabs, which is why that pool runs 2. send()'s
        # own busy-guard already refuses a second turn while one is in flight;
        # this is the same invariant enforced at the pool too.
        self.pool.setMaxThreadCount(1)
        self.context = None          # set by the controller: () -> (prompt, image)
        self.history = []            # [{"role": ..., "content": ...}, ...] - text only
        self._pending_image = ""
        self._busy = False
        self._suggested_spec = None
        self._section_suggestions = {}
        self.setup_ui()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.transcript_layout = QVBoxLayout()
        self.transcript_layout.setSpacing(T.SPACE["sm"])
        self.transcript_layout.setContentsMargins(0, 0, 0, 0)
        self.transcript_layout.addStretch(1)
        transcript_host = QWidget()
        transcript_host.setLayout(self.transcript_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidget(transcript_host)
        self._add_bubble("assistant", GREETING)

        self.attach_preview = ImagePreview("")
        self.attach_preview.setMaximumHeight(90)
        self.attach_preview.hide()
        self.clear_attach_button = QPushButton("Remove")
        self.clear_attach_button.setProperty("class", "ghost")
        self.clear_attach_button.clicked.connect(self.clear_attachment)
        self.clear_attach_button.hide()
        attach_row = QHBoxLayout()
        attach_row.setSpacing(T.SPACE["sm"])
        attach_row.addWidget(self.attach_preview, 1)
        attach_row.addWidget(self.clear_attach_button)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Ask about lighting, composition, colour, posing, camera angle…")
        self.input.returnPressed.connect(self.send)

        attach_button = QPushButton("Choose photo…")
        attach_button.setIcon(assets.icon("folder"))
        attach_button.setIconSize(assets.ICON_SIZE)
        attach_button.clicked.connect(self.choose_attachment)

        self.send_button = QPushButton("Send")
        self.send_button.setProperty("class", "primary")
        self.send_button.setIcon(assets.icon("generate"))
        self.send_button.setIconSize(assets.ICON_SIZE)
        self.send_button.clicked.connect(self.send)

        input_row = QHBoxLayout()
        input_row.setSpacing(T.SPACE["sm"])
        input_row.addWidget(self.input, 1)
        input_row.addWidget(attach_button)
        input_row.addWidget(self.send_button)

        self.suggestion_badge = AiSuggestionBadge("Thinking…")
        self.suggestion_badge.apply_requested.connect(self.apply_suggestion)

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Ask the Studio"))
        card.body.addWidget(MutedLabel(
            "A running conversation, not a one-shot helper - it remembers what "
            "you've already said, and it knows your current prompt's real score. "
            "Describe an avatar and it fills in the character spec plus all five "
            "technique sections; one Apply button below writes the lot into "
            "Compose, with the real score shown first - the same \"the model "
            "suggests, the gate decides\" rule as everywhere else in this app."
        ))
        card.body.addWidget(self.scroll, 1)
        card.body.addLayout(attach_row)
        card.body.addLayout(input_row)
        card.body.addWidget(self.suggestion_badge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)

    # -- transcript ---------------------------------------------------------#
    def _add_bubble(self, role, text):
        bubble = _Bubble(role, text)
        self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, bubble)
        return bubble

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # -- attachment -----------------------------------------------------------#
    def choose_attachment(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach a photo", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        self._pending_image = path
        self.attach_preview.load(path)
        self.attach_preview.show()
        self.clear_attach_button.show()

    def clear_attachment(self):
        self._pending_image = ""
        self.attach_preview.clear_image()
        self.attach_preview.hide()
        self.clear_attach_button.hide()

    # -- sending -------------------------------------------------------------#
    def send(self):
        # Belt and braces against a turn overlapping another: disabling the
        # Send button alone left a hole open behind it - the QLineEdit's own
        # returnPressed isn't gated by the button's enabled state, so pressing
        # Enter twice quickly (before the first reply lands) used to dispatch
        # two turns at once. A conversation is inherently ordered - a turn
        # depends on knowing the prior reply - so a second turn while one is
        # still in flight is refused outright, not merely made rare.
        if self._busy:
            self.status.emit("Wait for the current reply first")
            return

        message = self.input.text().strip()
        if not message:
            self.status.emit("Say something first")
            return

        image = self._pending_image
        self._add_bubble("user", message)
        if image:
            self._add_bubble("user", "[attached: {}]".format(Path(image).name))
        self.input.clear()
        self.clear_attachment()
        self._scroll_to_bottom()

        context_prompt = None
        if self.context:
            context_prompt, _image = self.context()

        self._busy = True
        self.input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.suggestion_badge.thinking("Thinking…")
        task = LlmTask("advisor_chat", self.bank, list(self.history), message,
                       image or None, context_prompt)
        # `message` is bound into the callback via the lambda default rather
        # than read back from a shared `self.*` attribute at completion time -
        # the busy-guard above already makes two turns overlap impossible, but
        # this removes the hazard at the source instead of only fencing it off.
        task.signals.finished.connect(
            lambda action, result, sent=message: self.on_finished(action, result, sent))
        task.signals.failed.connect(self.on_failed)
        task.signals.done.connect(self._on_turn_done)
        self.pool.start(task)

    def _on_turn_done(self, _a):
        self._busy = False
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input.setFocus()

    # -- results ---------------------------------------------------------------#
    def on_finished(self, _action, result, sent_message):
        reply = result["reply"]
        self._add_bubble("assistant", reply)
        self._scroll_to_bottom()
        # The plain message, never the context-decorated version chat() sent -
        # the note is per-turn app context, not something the user said.
        self.history.append({"role": "user", "content": sent_message})
        self.history.append({"role": "assistant", "content": reply})

        suggestion = result.get("suggestion")
        sections = result.get("sections") or {}
        self._suggested_spec = suggestion["spec"] if suggestion else None
        self._section_suggestions = dict(sections)

        # Visible whenever there is ANYTHING to apply - a turn that proposes
        # only technique sections (the subject was already settled earlier in
        # the conversation) has plenty to apply and used to show nothing at
        # all, because the badge was gated on the core spec alone.
        if suggestion or sections:
            parts = []
            status = "success"
            if suggestion:
                parts.append("{}/8 {}".format(
                    suggestion["score"], "ready" if suggestion["passed"] else "needs work"))
                status = "success" if suggestion["passed"] else "warning"
            if sections:
                parts.append("+ " + ", ".join(
                    SECTION_LABELS.get(name, name) for name in sections))
            self.suggestion_badge.ready(
                {"spec": self._suggested_spec, "sections": self._section_suggestions},
                " · ".join(parts), status=status)
        else:
            self.suggestion_badge.reset()
        self.status.emit("Advisor replied")

    def on_failed(self, _action, reason):
        self._add_bubble("assistant", "Something went wrong: " + reason)
        self._scroll_to_bottom()
        self.suggestion_badge.fail("failed")
        self.status.emit(reason)

    # -- applying -------------------------------------------------------------#
    def apply_suggestion(self):
        """One button, everything the advisor proposed this turn.

        The core spec and the five technique sections go together on purpose -
        "describe the avatar, get every section filled in" is one action from
        the user's side, so splitting it across two buttons would only make
        them press both every time.
        """
        if self._suggested_spec:
            self.spec_suggested.emit(dict(self._suggested_spec))
        if self._section_suggestions:
            self.sections_suggested.emit(dict(self._section_suggestions))
        if self._suggested_spec or self._section_suggestions:
            self.status.emit("Applied to Compose")

    # -- theming / lifecycle ----------------------------------------------------#
    def set_palette_tokens(self, palette):
        pass

    def refresh(self):
        pass
