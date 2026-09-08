"""Brief view — the three text-model helpers, one tab each.

Built on tools/brief.py, which holds the six-part briefs from bootcamp lesson 1
and, crucially, the validation gates. Nothing here decides whether a rewrite is
acceptable; it renders what brief.py already judged.
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import brief as brief_tool  # noqa: E402
import history as hist  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Card, ImagePreview, MutedLabel, TitleLabel  # noqa: E402
from ..workers import LlmTask  # noqa: E402


class BriefView(QWidget):
    """Emits `spec_suggested` and `prompt_upgraded` back to the Compose view."""

    spec_suggested = pyqtSignal(dict)
    prompt_upgraded = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.bank = bank
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.context = None          # set by the controller: () -> (prompt, image)
        self._suggested = None
        self._upgraded = None
        self._analyzed_spec = None
        self._analyze_path = ""
        self.setup_ui()

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_idea_tab(), "Idea → Spec")
        self.tabs.addTab(self._build_upgrade_tab(), "Upgrade prompt")
        self.tabs.addTab(self._build_critique_tab(), "Critique image")
        self.tabs.addTab(self._build_analyze_tab(), "Analyze a photo")
        self.tabs.addTab(self._build_briefs_tab(), "The briefs")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    # -- tab 1: idea -> spec ------------------------------------------------ #
    def _build_idea_tab(self):
        self.idea_input = QLineEdit()
        self.idea_input.setPlaceholderText("a tired barista closing up late")
        self.idea_input.returnPressed.connect(self.run_idea)

        self.idea_button = QPushButton("Draft a character")
        self.idea_button.setProperty("class", "primary")
        self.idea_button.setIcon(assets.icon("generate"))
        self.idea_button.setIconSize(assets.ICON_SIZE)
        self.idea_button.clicked.connect(self.run_idea)

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(self.idea_input, 1)
        row.addWidget(self.idea_button)

        # One shared shape for "call the model, offer to apply what came back" -
        # this tab and Upgrade below each built their own badge+button pair
        # independently before.
        self.idea_ai = AiSuggestionBadge("Drafting…")
        self.idea_ai.apply_requested.connect(self.apply_idea)
        self.idea_output = QPlainTextEdit()
        self.idea_output.setReadOnly(True)
        self.idea_output.setProperty("class", "mono")
        self.idea_output.setPlaceholderText(
            "The drafted spec appears here. Unknown fields are dropped before you "
            "ever see them, and the result is linted like any other prompt."
        )

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("One line in, a character spec out"))
        card.body.addWidget(MutedLabel(
            "Describe someone in a sentence. The model fills subject, wardrobe, "
            "setting, action and mood — never the camera, lighting or grain terms, "
            "which the app owns."
        ))
        card.body.addLayout(row)
        card.body.addWidget(self.idea_ai)
        card.body.addWidget(self.idea_output, 1)
        return self._wrap(card)

    # -- tab 2: upgrade ----------------------------------------------------- #
    def _build_upgrade_tab(self):
        self.upgrade_button = QPushButton("Rewrite the current prompt")
        self.upgrade_button.setProperty("class", "primary")
        self.upgrade_button.setIcon(assets.icon("generate"))
        self.upgrade_button.setIconSize(assets.ICON_SIZE)
        self.upgrade_button.clicked.connect(self.run_upgrade)

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(self.upgrade_button)
        row.addStretch(1)

        self.upgrade_ai = AiSuggestionBadge("Rewriting…")
        self.upgrade_ai.apply_requested.connect(self.apply_upgrade)
        self.upgrade_output = QPlainTextEdit()
        self.upgrade_output.setReadOnly(True)
        self.upgrade_output.setProperty("class", "mono")
        self.upgrade_output.setPlaceholderText("The rewrite appears here.")

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Make this prompt way more detailed"))
        card.body.addWidget(MutedLabel(
            "The gate still applies: a rewrite that falls below 8/8 or smuggles in a "
            "banned term is rejected and your prompt is kept. The model suggests — "
            "the realism check decides."
        ))
        card.body.addLayout(row)
        card.body.addWidget(self.upgrade_ai)
        card.body.addWidget(self.upgrade_output, 1)
        return self._wrap(card)

    # -- tab 3: critique ---------------------------------------------------- #
    def _build_critique_tab(self):
        self.critique_button = QPushButton("Why doesn't this look real?")
        self.critique_button.setProperty("class", "primary")
        self.critique_button.setIcon(assets.icon("generate"))
        self.critique_button.setIconSize(assets.ICON_SIZE)
        self.critique_button.clicked.connect(self.run_critique)

        # No apply/accept step here - a critique is a diagnosis, not a spec or
        # a prompt - but the same thinking/done visual language as the two
        # tabs beside it, via AiSuggestionBadge.set_status().
        self.critique_ai = AiSuggestionBadge("Diagnosing…")
        self.critique_preview = ImagePreview("Generate an image first")
        self.critique_preview.setMaximumHeight(260)
        self.critique_output = QPlainTextEdit()
        self.critique_output.setReadOnly(True)
        self.critique_output.setPlaceholderText(
            "The verdict, the realism layers that are letting it down, and phrases "
            "to fix them."
        )

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Diagnose a disappointing image"))
        card.body.addWidget(MutedLabel(
            "Sends the image and its prompt together. The answer always names a "
            "realism layer to strengthen — never a different model."
        ))
        card.body.addWidget(self.critique_preview)
        card.body.addWidget(self.critique_button)
        card.body.addWidget(self.critique_ai)
        card.body.addWidget(self.critique_output, 1)
        return self._wrap(card)

    # -- tab 4: analyze any photo --------------------------------------------#
    def _build_analyze_tab(self):
        self.analyze_preview = ImagePreview("Choose a photo to analyze")
        self.analyze_preview.setMaximumHeight(260)

        choose_button = QPushButton("Choose photo…")
        choose_button.setIcon(assets.icon("folder"))
        choose_button.setIconSize(assets.ICON_SIZE)
        choose_button.clicked.connect(self.choose_analyze_image)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setProperty("class", "primary")
        self.analyze_button.setIcon(assets.icon("generate"))
        self.analyze_button.setIconSize(assets.ICON_SIZE)
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.run_analyze)

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(choose_button)
        row.addWidget(self.analyze_button)
        row.addStretch(1)

        # Apply here means "load the reverse-engineered spec into Compose" -
        # the analysis text itself is read, not applied to anything.
        self.analyze_ai = AiSuggestionBadge("Analyzing…")
        self.analyze_ai.apply_requested.connect(self.apply_analysis)
        self.analyze_output = QPlainTextEdit()
        self.analyze_output.setReadOnly(True)
        self.analyze_output.setPlaceholderText(
            "The verdict - what's good, what's off, what would improve it - and the "
            "spec reverse-engineered from what's actually in the photo."
        )

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Any photo in, an analysis and a prompt out"))
        card.body.addWidget(MutedLabel(
            "Not one this app made - any local photo. The model's read is never the "
            "final prompt: it's recomposed from this app's own vocabulary and scored "
            "by the same realism check as everything else, so it may come back below "
            "8/8 if the photo doesn't map cleanly onto all 8 layers - that's the gate "
            "working, not a bug."
        ))
        card.body.addWidget(self.analyze_preview)
        card.body.addLayout(row)
        card.body.addWidget(self.analyze_ai)
        card.body.addWidget(self.analyze_output, 1)
        return self._wrap(card)

    # -- tab 5: the briefs themselves --------------------------------------- #
    def _build_briefs_tab(self):
        self.brief_picker = QTabWidget()
        for name, builder in [("Idea", brief_tool.idea_brief),
                              ("Upgrade", brief_tool.upgrade_brief),
                              ("Critique", brief_tool.critique_brief),
                              ("Analyze", brief_tool.analyze_photo_brief)]:
            view = QPlainTextEdit(builder(self.bank))
            view.setReadOnly(True)
            view.setProperty("class", "mono")
            self.brief_picker.addTab(view, name)

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("What the model is actually told"))
        card.body.addWidget(MutedLabel(
            "Each brief is built from the six parts in bootcamp lesson 1 — Purpose, "
            "Role, Structure, Tone, Constraints, Examples. Edit them in tools/brief.py."
        ))
        card.body.addWidget(self.brief_picker, 1)
        return self._wrap(card)

    def _wrap(self, card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)
        return page

    # -- running ------------------------------------------------------------ #
    def _start(self, action, ai_badge, button, *args):
        ai_badge.thinking()
        button.setEnabled(False)
        task = LlmTask(action, self.bank, *args)
        task.signals.finished.connect(self.on_finished)
        task.signals.failed.connect(self.on_failed)
        task.signals.done.connect(lambda _a, b=button: b.setEnabled(True))
        self.pool.start(task)

    def run_idea(self):
        idea = self.idea_input.text().strip()
        if not idea:
            self.status.emit("Describe the character in a line first")
            return
        self._start("idea", self.idea_ai, self.idea_button, idea)

    def run_upgrade(self):
        prompt, _ = self.context() if self.context else ("", "")
        if not prompt:
            self.status.emit("Compose a prompt first")
            return
        self._start("upgrade", self.upgrade_ai, self.upgrade_button, prompt)

    def run_critique(self):
        prompt, image = self.context() if self.context else ("", "")
        if not image:
            self.status.emit("Generate an image first — there is nothing to critique")
            return
        self.critique_preview.load(image)
        self._start("critique", self.critique_ai, self.critique_button, prompt, image)

    def choose_analyze_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a photo to analyze", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        self._analyze_path = path
        self.analyze_preview.load(path)
        self.analyze_button.setEnabled(True)

    def run_analyze(self):
        if not self._analyze_path:
            self.status.emit("Choose a photo first")
            return
        self._start("analyze_image", self.analyze_ai, self.analyze_button, self._analyze_path)

    def refresh_context(self):
        _, image = self.context() if self.context else ("", "")
        if image:
            self.critique_preview.load(image)

    # -- results ------------------------------------------------------------ #
    def on_finished(self, action, result):
        if action == "idea":
            self._suggested = result["spec"]
            lines = [json.dumps(result["spec"], indent=2, ensure_ascii=False)]
            if result.get("dropped"):
                lines.append("\nDropped (not part of a spec): " + ", ".join(result["dropped"]))
            self.idea_output.setPlainText("\n".join(lines))
            passed = result["passed"]
            # A drafted character is always applicable - the score is a hint
            # to review, not a hard gate the way Upgrade's acceptance is.
            self.idea_ai.ready(
                result["spec"],
                "{}/8 {}".format(result["score"], "ready" if passed else "needs work"),
                status="success" if passed else "warning",
            )
            self.status.emit("Drafted a character — review it, then apply")

        elif action == "upgrade":
            if result["accepted"]:
                self._upgraded = result["prompt"]
                self.upgrade_output.setPlainText(result["prompt"])
                self.upgrade_ai.ready(result["prompt"], result["reason"][:48])
            else:
                self._upgraded = None
                self.upgrade_output.setPlainText(
                    "REJECTED — your prompt is unchanged.\n\n{}\n\n"
                    "What it proposed:\n{}".format(
                        result["reason"], result.get("candidate", "")))
                self.upgrade_ai.fail(result["reason"][:48])
            self.status.emit(result["reason"])

        elif action == "critique":
            lines = [result.get("verdict", "")]
            if result.get("failing_layers"):
                lines.append("\nWeakest layers: " + ", ".join(result["failing_layers"]))
            for fix in result.get("fixes", []):
                lines.append("  • " + fix)
            self.critique_output.setPlainText("\n".join(lines).strip())
            weak = len(result.get("failing_layers", []))
            self.critique_ai.set_status(
                "warning" if weak else "success", "{} weak layer(s)".format(weak))
            self.status.emit("Critique complete")

        else:  # analyze_image
            self._analyzed_spec = result["spec"]
            lines = [result.get("analysis", ""), "",
                    json.dumps(result["spec"], indent=2, ensure_ascii=False)]
            if result.get("dropped"):
                lines.append("\nDropped (not part of a spec): " + ", ".join(result["dropped"]))
            self.analyze_output.setPlainText("\n".join(lines))
            passed = result["passed"]
            self.analyze_ai.ready(
                result["spec"],
                "{}/8 {}".format(result["score"], "ready" if passed else "needs work"),
                status="success" if passed else "warning",
            )
            self.status.emit("Analysis complete — review it, then apply")

    def on_failed(self, action, reason):
        ai_badge = {"idea": self.idea_ai, "upgrade": self.upgrade_ai,
                    "critique": self.critique_ai, "analyze_image": self.analyze_ai}[action]
        ai_badge.fail("failed")
        output = {"idea": self.idea_output, "upgrade": self.upgrade_output,
                  "critique": self.critique_output,
                  "analyze_image": self.analyze_output}[action]
        output.setPlainText(reason)
        self.status.emit(reason)

    # -- applying ----------------------------------------------------------- #
    def apply_idea(self):
        if self._suggested:
            self.spec_suggested.emit(dict(self._suggested))
            self.status.emit("Applied to Compose")

    def apply_upgrade(self):
        if not self._upgraded:
            return
        self.prompt_upgraded.emit(self._upgraded)
        self.status.emit("Upgraded prompt is now the working prompt")

    def apply_analysis(self):
        if self._analyzed_spec:
            self.spec_suggested.emit(dict(self._analyzed_spec))
            self.status.emit("Applied to Compose")
