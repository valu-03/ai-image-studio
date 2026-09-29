"""The shape shared by Relight and Macro insert: a batch of shots derived from
one photo you already have.

WHY THIS IS NOT A `Look` TOOLKIT. The rebuild plan said to add these two
"following ui/views/capture.py's pattern exactly (build a phrase, Apply to
Compose, set_*_override on SpecEditor)". They cannot be built that way, because
neither tool produces a phrase:

  * `build_relight.compose_relight_set()` and
    `build_macro_insert.compose_macro_set()` each return a LIST of whole shot
    dicts - {"index", "spec", "prompt", "layers", ...} - not a string.
  * Both need a REFERENCE PHOTO and a BASE SPEC to mean anything at all.
    Nothing in Look takes either; a Look toolkit composes from its own bank and
    knows nothing about the open character.
  * Both set spec-level flags - `lock_scene` for relight, `lock_identity` plus
    a feature-scoped `preserve` line for the inserts - and no
    `set_*_override()` can carry a flag. They write a whole spec, not a field.
  * Both have their own multi-check linter (relight_lint's 5 checks,
    macro_insert_lint's 9). No Look toolkit has one: those are scored only by
    the shared 8-layer gate, after the phrase lands in Compose.

So there is no single phrase to Apply and no field to receive it. Putting them
in Look would also contradict Look's own promise to the user, printed at the
top of that section: "Each one builds a phrase you Apply into the Images
prompt."

They belong in IMAGES, whose docstring already says "everything that produces a
still". Compose builds one, Variants samples several from one prompt, and these
two derive several from one PHOTO. They reuse the plumbing Variants already
established - `spec_provider` set by the controller - plus an `image_provider`
for the reference, wired to `ComposeView.current_image`, so "re-light the shot
I just made" needs no file picking at all.

WHAT THIS BASE CLASS IS FOR. The two views differ in their bank, their linter
and one rule about when a reference is required; everything else - the set
picker, the reference row, the shot tree, the prompt pane, the gate, the
handoff - is identical, and writing it twice would mean fixing every future
layout bug twice. Subclasses fill in the hooks marked below.

NEITHER VIEW SPENDS MONEY. They compose, score and hand off to the clipboard or
to temp/outputs/prompts/, the same decision StaticAdView made and for the same
reason: `confirm_spend` currently guards 3 of 6 paid paths, and adding more
unconfirmed ones is its own piece of work rather than a rider on this one.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, GateTree, MutedLabel, TitleLabel  # noqa: E402

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp);;All files (*)"


class BatchShotView(QWidget):
    """Emits `status`. Subclasses set the class attributes and the four hooks."""

    status = pyqtSignal(str)

    # -- subclass contract -------------------------------------------------- #
    TITLE = ""
    INTRO = ""
    SET_LABEL = "Set"
    #: Column heading for the middle column of the shot tree.
    SHOT_COLUMN = "Shot"
    EMPTY_HINT = "Pick a set and press Compose."

    def load_bank(self):
        raise NotImplementedError

    def set_options(self):
        """[(key, label, note)] for the set combo."""
        raise NotImplementedError

    def compose_shots(self, base_spec, reference, set_key):
        """-> a list of shot dicts, each with "index", "prompt", "spec"."""
        raise NotImplementedError

    def lint_shots(self, shots, set_key):
        """-> [(key, label, passed, detail)], this tool's own linter."""
        raise NotImplementedError

    def write_shots(self, base_spec, shots):
        """-> the path the batch was written to."""
        raise NotImplementedError

    def shot_label(self, shot):
        raise NotImplementedError

    def reference_problem(self, set_key):
        """A sentence explaining why this set cannot run yet, or ""."""
        if not self._reference:
            return "This set derives from an existing photo, so it needs a reference."
        return ""

    # ----------------------------------------------------------------------- #
    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = self.load_bank()
        self.image_bank = bp.load_bank()
        self._palette = palette or {}
        self._reference = ""
        self._shots = []
        self._rows = []
        # Set by MainWindow, exactly as VariantsView.spec_provider is.
        self.spec_provider = None
        self.image_provider = None
        self.setup_ui()
        self.refresh_gate()

    # -- construction ------------------------------------------------------- #
    def setup_ui(self):
        self.set_combo = QComboBox()
        for key, label, note in self.set_options():
            self.set_combo.addItem(label, key)
            self.set_combo.setItemData(
                self.set_combo.count() - 1, note, Qt.ItemDataRole.ToolTipRole)
        self.set_combo.currentIndexChanged.connect(self.refresh_gate)
        self.set_note = MutedLabel("")

        self.reference_label = MutedLabel("")
        use_open = QPushButton("Use the open image")
        use_open.setProperty("class", "ghost")
        use_open.clicked.connect(self.use_open_image)
        browse = QPushButton("Choose a file…")
        browse.setProperty("class", "ghost")
        browse.setIcon(assets.icon("folder"))
        browse.setIconSize(assets.ICON_SIZE)
        browse.clicked.connect(self.choose_reference)
        clear = QPushButton("Clear")
        clear.setProperty("class", "ghost")
        clear.clicked.connect(lambda: self.set_reference(""))

        reference_row = QHBoxLayout()
        reference_row.setSpacing(T.SPACE["sm"])
        reference_row.addWidget(use_open)
        reference_row.addWidget(browse)
        reference_row.addWidget(clear)
        reference_row.addStretch(1)

        self.compose_button = QPushButton("Compose the batch")
        self.compose_button.setProperty("class", "primary")
        self.compose_button.clicked.connect(self.compose)

        form = Card()
        form.body.addWidget(TitleLabel(self.TITLE))
        form.body.addWidget(MutedLabel(self.INTRO))
        form.body.addWidget(MutedLabel("{}:".format(self.SET_LABEL)))
        form.body.addWidget(self.set_combo)
        form.body.addWidget(self.set_note)
        form.body.addWidget(MutedLabel("Reference photo:"))
        form.body.addWidget(self.reference_label)
        form.body.addLayout(reference_row)
        form.body.addWidget(self.compose_button)

        # -- shots ---------------------------------------------------------- #
        self.shot_tree = QTreeWidget()
        self.shot_tree.setHeaderLabels(["#", self.SHOT_COLUMN, "Realism"])
        self.shot_tree.setRootIsDecorated(False)
        self.shot_tree.setColumnWidth(0, 32)
        self.shot_tree.setColumnWidth(1, 220)
        self.shot_tree.currentItemChanged.connect(self.show_selected_prompt)

        self.prompt_label = QLabel(self.EMPTY_HINT)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setProperty("class", "mono")

        copy_one = QPushButton("Copy this prompt")
        copy_one.setProperty("class", "ghost")
        copy_one.setIcon(assets.icon("copy"))
        copy_one.setIconSize(assets.ICON_SIZE)
        copy_one.clicked.connect(self.copy_selected)
        copy_all = QPushButton("Copy all")
        copy_all.setProperty("class", "ghost")
        copy_all.setIcon(assets.icon("copy"))
        copy_all.setIconSize(assets.ICON_SIZE)
        copy_all.clicked.connect(self.copy_all)
        self.save_button = QPushButton("Save the batch")
        self.save_button.setProperty("class", "ghost")
        self.save_button.setIcon(assets.icon("save"))
        self.save_button.setIconSize(assets.ICON_SIZE)
        self.save_button.clicked.connect(self.save_batch)

        actions = QHBoxLayout()
        actions.setSpacing(T.SPACE["sm"])
        actions.addWidget(copy_one)
        actions.addWidget(copy_all)
        actions.addWidget(self.save_button)
        actions.addStretch(1)

        self.count_badge = Badge("0 shots", "neutral")
        shots_card = Card()
        shots_header = QHBoxLayout()
        shots_header.addWidget(TitleLabel("Shots"))
        shots_header.addWidget(self.count_badge)
        shots_header.addStretch(1)
        shots_card.body.addLayout(shots_header)
        shots_card.body.addWidget(self.shot_tree, 1)
        shots_card.body.addWidget(self.prompt_label)
        shots_card.body.addLayout(actions)

        # -- gate ----------------------------------------------------------- #
        self.gate = GateTree()
        self.gate.set_palette_tokens(self._palette)
        self.gate_badge = Badge("0/0", "neutral")
        gate_card = Card()
        gate_header = QHBoxLayout()
        gate_header.addWidget(TitleLabel("Batch gate"))
        gate_header.addWidget(self.gate_badge)
        gate_header.addStretch(1)
        gate_card.body.addLayout(gate_header)
        gate_card.body.addWidget(MutedLabel(
            "This tool's own checks, on top of the eight-layer realism gate every "
            "shot is scored against individually above."))
        gate_card.body.addWidget(self.gate, 1)

        body = QWidget()
        inner = QVBoxLayout(body)
        inner.setContentsMargins(0, T.SPACE["md"], 0, 0)
        inner.setSpacing(T.COLUMN_GAP)
        inner.addWidget(form)
        inner.addWidget(shots_card)
        inner.addWidget(gate_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self.set_reference("")

    # -- reference ---------------------------------------------------------- #
    def current_set(self):
        return self.set_combo.currentData() or ""

    def set_reference(self, path):
        self._reference = str(path or "")
        self.reference_label.setText(
            Path(self._reference).name if self._reference
            else "None chosen. These shots derive from a photo you already have.")
        self.refresh_gate()

    def use_open_image(self):
        """The image Compose last produced - the usual case, and no file picking."""
        path = self.image_provider() if self.image_provider else None
        if not path:
            self.status.emit("No open image yet — generate one in Compose first")
            return
        self.set_reference(str(path))
        self.status.emit("Reference set to " + Path(str(path)).name)

    def choose_reference(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose the source photo", "", IMAGE_FILTER)
        if path:
            self.set_reference(path)

    def base_spec(self):
        return dict(self.spec_provider()[0]) if self.spec_provider else {}

    # -- compose ------------------------------------------------------------ #
    def compose(self):
        # A REFUSAL CLEARS. Leaving the previous batch on screen was a false
        # green: switch from a set that composed to one that cannot, press
        # Compose, and the old four prompts stayed visible under a gate whose
        # rows are recomputed for the NEW set - so the view showed 9/9 for a
        # batch it had just declined to build. Every early return below drops
        # the stale shots first.
        problem = self.reference_problem(self.current_set())
        if problem:
            self._discard(problem)
            return
        base = self.base_spec()
        if not base.get("subject"):
            self._discard("Write a subject in Compose first — these shots inherit it")
            return
        try:
            self._shots = self.compose_shots(base, self._reference, self.current_set())
        except (KeyError, ValueError) as exc:     # a bank/set mismatch, not a crash
            self._discard("Could not compose the batch: {}".format(exc))
            return
        self.refresh_shots()
        self.refresh_gate()
        self.status.emit("Composed {} shots".format(len(self._shots)))

    def _discard(self, message):
        """Drop any previous batch, then say why nothing was composed."""
        self._shots = []
        self.refresh_shots()
        self.refresh_gate()
        self.status.emit(message)

    def refresh_shots(self):
        self.shot_tree.clear()
        for shot in self._shots:
            present, _missing, banned, _warn, _neg = rl.lint(
                shot["prompt"].lower(), self.image_bank)
            score = "{}/8{}".format(len(present), " !" if banned else "")
            item = QTreeWidgetItem(
                self.shot_tree,
                [str(shot["index"]), self.shot_label(shot), score])
            item.setData(0, Qt.ItemDataRole.UserRole, shot)
        self.count_badge.set_status(
            "success" if self._shots else "neutral",
            "{} shot{}".format(len(self._shots), "" if len(self._shots) == 1 else "s"))
        if self.shot_tree.topLevelItemCount():
            self.shot_tree.setCurrentItem(self.shot_tree.topLevelItem(0))
        else:
            self.prompt_label.setText(self.EMPTY_HINT)

    def show_selected_prompt(self, item=None, _previous=None):
        item = item or self.shot_tree.currentItem()
        shot = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.prompt_label.setText(shot["prompt"] if shot else self.EMPTY_HINT)

    # -- gate --------------------------------------------------------------- #
    def refresh_gate(self):
        cfg = dict(self.set_options_by_key().get(self.current_set(), {}))
        self.set_note.setText(cfg.get("note", ""))
        if not self._shots:
            self._rows = []
            self.gate.set_checks([])
            self.gate_badge.set_status("neutral", "0/0")
            problem = self.reference_problem(self.current_set())
            self.gate.detail.setText(problem or self.EMPTY_HINT)
            return
        results = self.lint_shots(self._shots, self.current_set())
        self._rows = list(results)
        self.gate.set_checks([
            {"key": key, "label": label, "passed": passed,
             "fix": detail, "ok_text": detail}
            for key, label, passed, detail in results
        ])
        got = sum(1 for _k, _l, passed, _d in results if passed)
        total = len(results)
        self.gate_badge.set_status("success" if got == total else "danger",
                                   "{}/{}".format(got, total))

    def set_options_by_key(self):
        return {key: {"label": label, "note": note}
                for key, label, note in self.set_options()}

    @property
    def passing(self):
        return bool(self._rows) and all(row[2] for row in self._rows)

    # -- handoff ------------------------------------------------------------ #
    def selected_shot(self):
        item = self.shot_tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def copy_selected(self):
        shot = self.selected_shot()
        if not shot:
            self.status.emit("Compose the batch first")
            return
        QGuiApplication.clipboard().setText(shot["prompt"])
        self.status.emit("Prompt copied")

    def copy_all(self):
        if not self._shots:
            self.status.emit("Compose the batch first")
            return
        blocks = ["=== {}. {}\n{}".format(s["index"], self.shot_label(s), s["prompt"])
                  for s in self._shots]
        QGuiApplication.clipboard().setText("\n\n".join(blocks))
        self.status.emit("{} prompts copied".format(len(self._shots)))

    def save_batch(self):
        if not self._shots:
            self.status.emit("Compose the batch first")
            return
        path = self.write_shots(self.base_spec(), self._shots)
        self.status.emit("Saved to " + str(path))

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.gate.set_palette_tokens(self._palette)
