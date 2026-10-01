"""Compose view — spec in, linted prompt out, generated image beside it."""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ask_llm as al  # noqa: E402
import build_prompt as bp  # noqa: E402
import generate_image as gi  # noqa: E402
import history as hist  # noqa: E402
import midjourney_export as mx  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..lint_panel import LintPanel  # noqa: E402
from ..spec_editor import SpecEditor  # noqa: E402
from ..widgets import (  # noqa: E402
    AiSuggestionBadge, Card, ImagePreview, MutedLabel, StarRating, TitleLabel)
from ..workers import CoherenceTask, LlmTask, VisionQcTask  # noqa: E402


class ComposeView(QWidget):
    """Emits `generate_requested` with (prompt, references) for the controller."""

    generate_requested = pyqtSignal(str, list)
    upscale_requested = pyqtSignal(str)
    refine_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.bank = bank
        self.passing = False
        self.entry_id = None
        self.current_image = None
        self.use_learned = False
        self._filter = ""
        self._override_prompt = None
        self.last_layers = {}
        self._suggestions = {}
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setup_ui()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.editor = SpecEditor(self.bank)

        autofill_card = self.build_autofill_card()

        self.library = QListWidget()
        self.library.setAlternatingRowColors(True)
        self.library.setMaximumHeight(110)
        self.library.itemActivated.connect(self.load_selected)
        self.library.setToolTip("Double-click a saved character to load it")

        load_button = QPushButton("Load")
        load_button.setIcon(assets.icon("folder"))
        load_button.setIconSize(assets.ICON_SIZE)
        load_button.clicked.connect(self.load_selected)
        save_button = QPushButton("Save character")
        save_button.setIcon(assets.icon("save"))
        save_button.setIconSize(assets.ICON_SIZE)
        save_button.clicked.connect(self.save_spec)

        # Vertical, not a row: "Load" + "Save character" side by side needed
        # 358px and the column's floor gives this card about 259px - a row
        # elided "Save character" down to roughly "Save char...". Stacked, each
        # button gets the column's full width, which comfortably fits either
        # label on its own.
        library_buttons = QVBoxLayout()
        library_buttons.setSpacing(T.SPACE["xs"])
        library_buttons.addWidget(load_button)
        library_buttons.addWidget(save_button)

        # Five buttons will not fit one row in this column, so the editing
        # actions get their own, quieter group - stacked for the same reason
        # as library_buttons above (New alone fit, but Rename/Delete did not).
        new_button = QPushButton("New")
        new_button.setProperty("class", "ghost")
        new_button.clicked.connect(self.new_character)
        rename_button = QPushButton("Rename")
        rename_button.setProperty("class", "ghost")
        rename_button.clicked.connect(self.rename_character)
        delete_button = QPushButton("Delete")
        delete_button.setProperty("class", "danger")
        delete_button.clicked.connect(self.delete_character)

        # New+Rename together still fit one row (193px of ~259 available);
        # only Delete needs to drop to its own - one extra row of height
        # instead of two, since library_card's height is tight too.
        new_rename_row = QHBoxLayout()
        new_rename_row.setSpacing(T.SPACE["sm"])
        new_rename_row.addWidget(new_button)
        new_rename_row.addWidget(rename_button)

        crud_buttons = QVBoxLayout()
        crud_buttons.setSpacing(T.SPACE["xs"])
        crud_buttons.addLayout(new_rename_row)
        crud_buttons.addWidget(delete_button)

        # The same three actions on the list itself. F2/Delete are scoped to the
        # widget, not the window, so they cannot fire while typing in the form.
        self.library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.show_library_menu)
        for sequence, slot in (("F2", self.rename_character),
                               ("Delete", self.delete_character)):
            shortcut = QShortcut(QKeySequence(sequence), self.library)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(slot)

        library_card = Card()
        library_card.body.setSpacing(T.SPACE["sm"])
        library_card.body.addWidget(TitleLabel("Character library"))
        library_card.body.addWidget(self.library)
        library_card.body.addLayout(library_buttons)
        library_card.body.addLayout(crud_buttons)

        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        # AsNeeded, not Off - same reasoning as below_preview_scroll further
        # down: the editor's own minimum runs 27px past this column at the
        # 1100px floor, and with the bar off that 27px was cut off the right
        # of every field rather than scrolled to.
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_scroll.setWidget(self.editor)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(T.COLUMN_GAP)
        left_layout.addWidget(autofill_card)
        left_layout.addWidget(library_card)
        left_layout.addWidget(editor_scroll, 1)

        # --- middle: prompt + realism ------------------------------------- #
        self.form_mode = QComboBox()
        self.form_mode.addItem("Compact", False)
        self.form_mode.addItem("Detailed", True)
        self.form_mode.currentIndexChanged.connect(self.schedule_rebuild)

        shuffle = QPushButton("Reshuffle")
        shuffle.setProperty("class", "ghost")
        shuffle.setIcon(assets.icon("shuffle"))
        shuffle.setIconSize(assets.ICON_SIZE)
        shuffle.setToolTip("Bump the seed — new vocabulary, same character")
        shuffle.clicked.connect(self.reshuffle)

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_prompt)

        # Form label + combo on one row, Reshuffle + Copy each on their own -
        # all four on one row needed 503px and the prompt column's floor gives
        # this card about 238px, eliding both buttons down to roughly a third
        # of their label. Neither button even fits paired with the other at
        # that floor, so each gets its own row rather than a shared one.
        # Opt-in, and off by default, because build_prompt.anatomy_guard_tail()
        # is: "no distorted hands" is noise on a shot with no person in it. The
        # label says BODY rather than "anatomy" because the thing it prevents is
        # the sixth finger, and nobody scanning this row reads "anatomy" as that.
        self.anatomy_guard = QCheckBox("Body guard")
        self.anatomy_guard.setToolTip(
            "Append: no warped face, no distorted hands or extra fingers, no "
            "floating or extra limbs, no duplicated figures, no morphing. "
            "Leave it off for shots with nobody in them.")
        self.anatomy_guard.toggled.connect(self.schedule_rebuild)

        controls = QHBoxLayout()
        controls.setSpacing(T.SPACE["sm"])
        controls.addWidget(QLabel("Form"))
        controls.addWidget(self.form_mode)
        controls.addWidget(self.anatomy_guard)
        controls.addStretch(1)

        self.prompt_view = QPlainTextEdit()
        self.prompt_view.setReadOnly(True)
        self.prompt_view.setProperty("class", "mono")
        self.prompt_view.setPlaceholderText("The composed prompt appears here.")

        prompt_card = Card()
        prompt_card.body.setSpacing(T.SPACE["sm"])
        prompt_card.body.addWidget(TitleLabel("Prompt"))
        prompt_card.body.addLayout(controls)
        prompt_card.body.addWidget(shuffle)
        prompt_card.body.addWidget(copy_button)
        prompt_card.body.addWidget(self.prompt_view, 1)

        self.lint = LintPanel({})
        lint_card = Card()
        lint_card.body.setSpacing(T.SPACE["sm"])
        lint_card.body.addWidget(TitleLabel("Realism check"))
        lint_card.body.addWidget(self.lint, 1)

        # Two more, OPTIONAL checks - Vision QC (the returned IMAGE against
        # the spec) and Coherence (a semantic read of the PROMPT TEXT,
        # catching keyword salad realism_lint's regex gate can't). Both are
        # advisory: AND, not OR - neither can override a realism_lint
        # failure, and failing either never blocks Generate. Sharing one
        # tabbed area rather than three simultaneously-visible full panels:
        # three stacked LintPanels crushed the realism panel itself below its
        # own minimum at the app's minimum window size. Realism check stays
        # always visible above, since it is the mandatory gate; these two are
        # supplementary, so only one needs to be on screen at a time.
        self.vision_qc_checkbox = QCheckBox("Run after generating")
        self.vision_qc_checkbox.setToolTip(
            "Asks a vision-capable text model to check the returned image "
            "against this spec - lighting, composition, wardrobe, and (with a "
            "reference set) whether the character still looks like the same "
            "one. Uses {}, same as Brief - optional everywhere.".format(al.KEY_VAR))
        # Kept so refresh_key_state() can put it back when a key appears.
        self._vision_tip = self.vision_qc_checkbox.toolTip()
        self.vision_lint = LintPanel({})
        vision_tab = QWidget()
        vision_tab_layout = QVBoxLayout(vision_tab)
        vision_tab_layout.setContentsMargins(0, 0, 0, 0)
        vision_tab_layout.setSpacing(T.SPACE["xs"])
        vision_tab_layout.addWidget(self.vision_qc_checkbox)
        vision_tab_layout.addWidget(self.vision_lint, 1)

        self.coherence_button = QPushButton("Check coherence")
        self.coherence_button.setProperty("class", "ghost")
        self.coherence_button.setToolTip(
            "Asks a text model whether this prompt reads as one coherent "
            "scene, not a list of trigger words stitched together - "
            "realism_lint checks structure, this checks sense. Uses {}, "
            "same as Brief.".format(al.KEY_VAR))
        self._coherence_tip = self.coherence_button.toolTip()
        self.coherence_button.clicked.connect(self.request_coherence_check)
        self.refresh_key_state()
        self.coherence_lint = LintPanel({})
        coherence_tab = QWidget()
        coherence_tab_layout = QVBoxLayout(coherence_tab)
        coherence_tab_layout.setContentsMargins(0, 0, 0, 0)
        coherence_tab_layout.setSpacing(T.SPACE["xs"])
        coherence_tab_layout.addWidget(self.coherence_button)
        coherence_tab_layout.addWidget(self.coherence_lint, 1)

        # Each tab scrolls - the same fix, for the same reason, as
        # below_preview_scroll further down this file. Tabbing these two (see
        # the note above) bought enough room at the time, but only just: this
        # card's natural height still exceeds what it is given at the 700px
        # minimum window, and a QVBoxLayout with nothing left to shrink crushes
        # its children rather than clipping cleanly.
        #
        # It stayed invisible because Qt's offscreen platform with no fonts
        # installed reports a 12px line box for a 12px font, while any real
        # typeface reports 14 - so every height this app derives from a font
        # was measured 2px short per line locally, and the card appeared to
        # fit. CI with fonts-dejavu-core installed is what finally measured it
        # honestly: the gate badge, whose policy is Fixed, came out 16px tall
        # of the 22px it asked for. Scrolling makes the overflow visible as a
        # scrollbar instead of silently squashing the panel.
        def _scrolled(inner):
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            area.setFrameShape(QScrollArea.Shape.NoFrame)
            area.setWidget(inner)
            return area

        secondary_checks = QTabWidget()
        secondary_checks.addTab(_scrolled(vision_tab), "Vision QC")
        secondary_checks.addTab(_scrolled(coherence_tab), "Coherence")
        lint_card.body.addWidget(secondary_checks, 1)

        middle = QSplitter(Qt.Orientation.Vertical)
        middle.setObjectName("compose_prompt_lint")
        middle.addWidget(prompt_card)
        middle.addWidget(lint_card)
        middle.setSizes([300, 320])

        # --- right: image + rating ---------------------------------------- #
        self.preview = ImagePreview("No image yet.\nGenerate, or drop one in with Set reference.")

        # Short labels, real tooltips: a user screenshot showed every button in
        # this column - "Generate image" included - cut off mid-word at a
        # narrow width this session's own offscreen tests never reproduced
        # (see CLAUDE.md's font/geometry-restore notes). Shortening every
        # label here is a cheap, unconditional safety margin regardless of
        # whatever produced that width.
        self.generate_button = QPushButton("Generate")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.clicked.connect(self.request_generate)

        # Every long-running path needs a way out. workers.WorkerPool.
        # cancel() already did the work; only Variants exposed it, so a slow
        # run left the form disabled with no recourse but to wait.
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "danger")
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip(
            "Stop waiting on this generation. Requests already sent to the provider "
            "still finish and may still be billed; anything queued is dropped.")

        # What the next press will cost, before it is pressed. Settings says
        # of its resolution picker that "the estimate on the generate button
        # follows this" - it does now. `cost_provider` is set by MainWindow,
        # the only object that knows the provider, model and account options.
        self.cost_provider = None
        self.cost_note = MutedLabel("")

        self.rating = StarRating()
        self.rating.setEnabled(False)
        self.rating.rated.connect(self.apply_rating)

        # Bootcamp Phase 2 (Upscaling to 4K with Nanobanana PRO): "REMEMBER you
        # need to UPSCALE before you animate!" - the app had no upscale path at
        # all. Not a new provider call: tools/upscale_image.py is generate()
        # with this image as the sole reference and a fixed instruction prompt,
        # so it needs an image already on screen and nothing else.
        self.upscale_button = QPushButton("Upscale")
        self.upscale_button.setProperty("class", "ghost")
        self.upscale_button.setToolTip(
            "Upscale to 4K. Preserves composition, lighting and identity; adds "
            "micro-detail. Do this before sending the still to Videos.")
        self.upscale_button.setEnabled(False)
        self.upscale_button.clicked.connect(self.request_upscale)

        # The manual loop this app has always required: generate -> notice
        # it's off -> figure out which realism layer is weak -> re-prompt by
        # hand. This automates the last two steps, capped and opt-in - never
        # automatic, since each retry is a real paid generation. Needs an
        # image on screen to critique (the just-generated one, or a loaded
        # one) and OPENROUTER_API_KEY for the critique step; a missing key
        # is reported after the fact (same as every other AI helper here),
        # not pre-disabled, since nothing else in this view pre-checks a key.
        self.refine_button = QPushButton("Refine")
        self.refine_button.setProperty("class", "ghost")
        self.refine_button.setToolTip(
            "Refine until real: critiques the result and retries up to 2 more "
            "times, strengthening whichever realism layer looks weak. Needs an "
            "image and an OpenRouter key. Each retry is a real paid generation.")
        self.refine_button.setEnabled(False)
        self.refine_button.clicked.connect(self.request_refine)

        # Midjourney has no official API - this is a pure text reformat, not a
        # new provider, the same spirit as Cats' "Copy sound cue" button: hand
        # you something to paste in yourself. It started out next to the
        # prompt's own "Copy" button, but that row was already at its exact
        # width limit - even a 23px icon-only button pushed the "Form" label
        # below its own text width. This column is vertical, not horizontal,
        # and has the room a labelled button actually needs.
        self.copy_mj_button = QPushButton("Copy (MJ)")
        self.copy_mj_button.setProperty("class", "ghost")
        self.copy_mj_button.setIcon(assets.icon("copy"))
        self.copy_mj_button.setIconSize(assets.ICON_SIZE)
        self.copy_mj_button.setToolTip(
            "Copy for Midjourney: this prompt, reformatted with Midjourney's own "
            "--ar/--style/--no/--v syntax - paste it into Midjourney yourself.")
        self.copy_mj_button.clicked.connect(self.copy_midjourney_prompt)

        # The reference controls live in the editor's Identity tab; this is the
        # read-out so you can see the lock state next to the result.
        self.reference_label = MutedLabel("No reference image — the face is invented each time.")

        # Caption above the stars, not beside them: side by side, the caption is
        # clipped in this column at any window size.
        rating_row = QVBoxLayout()
        rating_row.setSpacing(T.SPACE["xs"])
        rating_row.addWidget(MutedLabel("How did it turn out?"))
        rating_row.addWidget(self.rating)

        # Provider/model/resolution/format were global-only, in Settings - the
        # one thing in this whole view that was not a per-shot choice, when
        # every SpecEditor field already is. "(use Settings)" leaves today's
        # behaviour exactly unchanged; picking anything else overrides it for
        # this generation only.
        USE_SETTINGS = "(use Settings)"
        self.gen_provider = QComboBox()
        self.gen_provider.addItem(USE_SETTINGS, "")
        for name in sorted(gi.PROVIDERS):
            self.gen_provider.addItem(name, name)
        self.gen_provider.setToolTip("Override the provider for this generation only.")

        self.gen_model = QLineEdit()
        self.gen_model.setPlaceholderText(USE_SETTINGS)
        self.gen_model.setToolTip("Override the model for this generation only.")

        self.gen_resolution = QComboBox()
        self.gen_resolution.addItem(USE_SETTINGS, "")
        for option in gi.KIE_RESOLUTIONS:
            self.gen_resolution.addItem(option, option)
        self.gen_resolution.setToolTip("Override the resolution for this generation only.")

        self.gen_output_format = QComboBox()
        self.gen_output_format.addItem(USE_SETTINGS, "")
        for option in gi.KIE_OUTPUT_FORMATS:
            self.gen_output_format.addItem(option, option)
        self.gen_output_format.setToolTip("Override the image format for this generation only.")

        # One packed row, not a form - the same shape Videos' own duration/
        # aspect/mode/sound row already uses successfully in an equally
        # narrow column. A four-row QFormLayout here crushed every field in
        # this view below its minimum height at the 700px floor; captions
        # live in tooltips instead of a label column.
        #
        # Every one of these MUST be able to compress. A QComboBox reports its
        # widest item as its minimum width by default, so "(use Settings)" x3
        # pinned this row's minimum at ~438px inside a column whose content
        # area is ~190px at its floor - and because the row lives in a
        # QScrollArea with the horizontal bar off, that 250px overhang was not
        # squeezed, wrapped or scrolled to. It was silently CLIPPED, taking the
        # right-hand side of every button underneath it off-screen with it
        # (the buttons were 462px wide inside a 188px viewport). Nothing in
        # test_layout.py could see it: the widgets all had their full
        # requested geometry, they were simply drawn outside the visible area.
        for combo in (self.gen_provider, self.gen_resolution, self.gen_output_format):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(6)
            combo.setMinimumWidth(56)
        self.gen_model.setMinimumWidth(56)

        # 2x2, not 1x4: even compressed to 56px each, four across still needed
        # 236px of a 188px viewport. Two across needs 116px and fits with room
        # to spare, at the cost of one extra row of height in a box that
        # already scrolls vertically.
        options_row = QGridLayout()
        options_row.setSpacing(T.SPACE["xs"])
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.addWidget(self.gen_provider, 0, 0)
        options_row.addWidget(self.gen_model, 0, 1)
        options_row.addWidget(self.gen_resolution, 1, 0)
        options_row.addWidget(self.gen_output_format, 1, 1)
        options_row.setColumnStretch(0, 1)
        options_row.setColumnStretch(1, 1)

        # Stacked, not a shared row: side by side in this column's 230-460px
        # width, "Generate image" elided to a few characters - the crushed-
        # below-minimum layout check does not catch a QPushButton eliding its
        # own text (only QLabel wrapping and widget-vs-widget overlap), so
        # this was only visible in an actual screenshot, not the test gate.
        # 2x2 as well, for height this time rather than width: stacked 1x4 the
        # primary "Generate" button fell below the fold of the scroll area
        # holding it, so the main action of the whole view needed a scroll to
        # reach. Two rows of two keeps it on screen.
        buttons_col = QGridLayout()
        buttons_col.setSpacing(T.SPACE["xs"])
        buttons_col.setContentsMargins(0, 0, 0, 0)
        buttons_col.addWidget(self.upscale_button, 0, 0)
        buttons_col.addWidget(self.copy_mj_button, 0, 1)
        buttons_col.addWidget(self.refine_button, 1, 0)
        buttons_col.addWidget(self.generate_button, 1, 1)
        buttons_col.addWidget(self.cancel_button, 2, 0)
        buttons_col.addWidget(self.cost_note, 2, 1)
        buttons_col.setColumnStretch(0, 1)
        buttons_col.setColumnStretch(1, 1)

        # Everything below the preview, in a QScrollArea - not because four
        # buttons is an intrinsically bad idea, but because two earlier
        # attempts at fitting them by trimming spacing alone (first to "sm",
        # then to "xs") only shrank the visible symptom instead of fixing the
        # cause: at the 700px minimum window this card's total natural height
        # genuinely exceeds what it is given, and a QVBoxLayout with nothing
        # left to shrink does not clip cleanly - past a point it pushes
        # consecutive widgets into outright overlap (confirmed directly with
        # QRect.intersects(), the same check test_layout.py's own overlap
        # scan uses - which never caught it, because that scan only walks
        # each QWidget's own direct layout items; a widget added via
        # addLayout() inside a widget's layout is invisible to it, not a
        # QWidget of its own). A QScrollArea makes the card scroll instead of
        # silently overlapping - the same fix Settings already uses for a
        # page of stacked cards that cannot all fit at once.
        below_preview = QWidget()
        below_preview_col = QVBoxLayout(below_preview)
        below_preview_col.setContentsMargins(0, 0, 0, 0)
        below_preview_col.setSpacing(T.SPACE["md"])
        below_preview_col.addLayout(rating_row)
        below_preview_col.addWidget(self.reference_label)
        below_preview_col.addWidget(MutedLabel("Generation options"))
        below_preview_col.addLayout(options_row)
        below_preview_col.addLayout(buttons_col)

        below_preview_scroll = QScrollArea()
        below_preview_scroll.setWidgetResizable(True)
        # AsNeeded, never Off. A resizable QScrollArea will not shrink its
        # content below that content's own minimum size - it clips instead,
        # and with the bar off there is no scrollbar, no overlap and no
        # elision to reveal it, so the missing 274px were invisible to every
        # automated check this project has. If a future control in here
        # regresses the minimum again, a scrollbar says so out loud.
        below_preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        below_preview_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        below_preview_scroll.setWidget(below_preview)

        right_card = Card()
        right_card.body.setSpacing(T.SPACE["md"])
        right_card.body.addWidget(TitleLabel("Result"))
        right_card.body.addWidget(self.preview, 1)
        right_card.body.addWidget(below_preview_scroll)

        # Floors for all three, or the splitter falls back to an even split when
        # the window is small and hands the prompt a 237px column. They sum to
        # 810, which fits the 836px the canvas has at the 1100px minimum window.
        left.setMinimumWidth(300)
        # A form column has a natural width; without a ceiling the splitter
        # hands it the slack and starves the prompt, which is the column that
        # actually benefits from being wide.
        left.setMaximumWidth(420)
        middle.setMinimumWidth(260)
        # 230 starved this column: the result card holds four buttons, four
        # override controls, the rating and two paragraphs, and at 230 the
        # requested sizes below scaled it down to ~219px of which ~190 is
        # usable - not enough for two controls side by side, so everything
        # inside stacked and the primary Generate button fell below the fold.
        right_card.setMinimumWidth(258)
        right_card.setMaximumWidth(460)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("compose_form_prompt_result")
        splitter.addWidget(left)
        splitter.addWidget(middle)
        splitter.addWidget(right_card)
        splitter.setChildrenCollapsible(False)
        # Sizes must sit inside the min/max above: setSizes overrides a
        # maximum rather than clamping to it, so asking for 500 here would have
        # quietly defeated the 420 ceiling. Spare width goes to the prompt.
        # These are scaled proportionally when they do not fit (they sum to
        # 1150 against the 838px canvas a 1100px window has), so the RATIO is
        # what actually decides the result card's width, not the floor - which
        # is why the result column came out at ~219px while its floor said 230.
        splitter.setSizes([300, 330, 262])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        self.splitter = splitter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self.rebuild)
        self.editor.changed.connect(self.schedule_rebuild)
        # Keep the reference caption bound to editor state rather than to the
        # one code path that happens to set it.
        self.editor.changed.connect(self.update_reference_label)

        self.reload_library()

    # -- auto-fill ---------------------------------------------------------- #
    def build_autofill_card(self):
        """One press: the model completes the form around what you have typed."""
        self.idea = QLineEdit()
        self.idea.setPlaceholderText("a line about them (optional)")
        self.idea.returnPressed.connect(self.run_autofill)

        self.autofill_button = QPushButton("Auto-fill")
        self.autofill_button.setProperty("class", "primary")
        self.autofill_button.setIcon(assets.icon("generate"))
        self.autofill_button.setIconSize(assets.ICON_SIZE)
        self.autofill_button.setToolTip(
            "Fills every empty field from OpenRouter. Anything you have already "
            "typed is left alone and used as the brief."
        )
        self.autofill_button.clicked.connect(self.run_autofill)
        # Set-only (never .ready()/.thinking()) - autofill mutates the form
        # fields directly, there is no separate payload to Apply, so this is
        # only ever driven through set_status(), the same as Brief's Critique
        # tab. Still AiSuggestionBadge, not a bare Badge, so every "the model
        # is thinking" indicator in the app looks and behaves identically.
        self.autofill_badge = AiSuggestionBadge()
        self.autofill_badge.set_status("neutral", "not run")

        top = QHBoxLayout()
        top.setSpacing(T.SPACE["sm"])
        top.addWidget(self.idea, 1)
        top.addWidget(self.autofill_button)

        # Lighting and composition are opt-in by an earlier decision, so the
        # model may propose them but never apply them. This row is the whole
        # mechanism for that, and it stays hidden until there is something in it.
        self.suggestion_label = MutedLabel("")
        self.suggestion_apply = QPushButton("Use these")
        self.suggestion_apply.setProperty("class", "ghost")
        self.suggestion_apply.clicked.connect(self.apply_suggestions)
        # Stacked, not side by side: this column is 330px and the caption beside
        # a button wrapped to six lines.
        self.suggestion_row = QWidget()
        suggestion_layout = QVBoxLayout(self.suggestion_row)
        suggestion_layout.setContentsMargins(0, 0, 0, 0)
        suggestion_layout.setSpacing(T.SPACE["xs"])
        suggestion_layout.addWidget(self.suggestion_label)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.suggestion_apply)
        button_row.addStretch(1)
        suggestion_layout.addLayout(button_row)
        self.suggestion_row.setVisible(False)

        card = Card()
        card.body.setSpacing(T.SPACE["sm"])
        card.body.addWidget(TitleLabel("Auto-fill"))
        card.body.addLayout(top)
        card.body.addWidget(self.autofill_badge)
        card.body.addWidget(self.suggestion_row)
        return card

    def run_autofill(self):
        current = self.editor.spec()
        idea = self.idea.text().strip()
        if idea:
            # A typed line is the strongest statement of intent, so it becomes
            # the subject when there is not one already.
            current = dict(current)
            if current.get("subject") in ("", "a person"):
                current["subject"] = idea
            else:
                current.setdefault("extra", [])
                current["extra"] = list(current["extra"]) + [idea]

        self.autofill_badge.thinking("thinking…")
        self.autofill_button.setEnabled(False)
        task = LlmTask("autofill", self.bank, current)
        task.signals.finished.connect(self.on_autofilled)
        task.signals.failed.connect(self.on_autofill_failed)
        task.signals.done.connect(lambda _a: self.autofill_button.setEnabled(True))
        self.pool.start(task)

    def on_autofilled(self, _action, result):
        filled = self.editor.apply_partial(result.get("spec") or {}, fill_blanks_only=True)

        # The model's subject is better than the one-liner and wins when it
        # gives one. When it does not, the line still belongs in the form -
        # otherwise what you typed disappears and the subject stays empty.
        idea = self.idea.text().strip()
        if idea and not self.editor.subject.toPlainText().strip():
            self.editor.subject.setPlainText(idea)
            filled = sorted(set(filled) | {"subject"})

        self._suggestions = result.get("suggestions") or {}
        self.show_suggestions()

        passed = result.get("passed")
        self.autofill_badge.set_status(
            "success" if passed else "warning",
            "{}/8 {}".format(result.get("score", 0), "ready" if passed else "needs work"),
        )
        if filled:
            self.status.emit("Filled {} — your own fields were left alone".format(
                ", ".join(filled)))
        else:
            self.status.emit("Nothing to fill — every field already had a value")

    def on_autofill_failed(self, _action, reason):
        self.autofill_badge.set_status("danger", "failed")
        self.status.emit(reason[:160])

    def show_suggestions(self):
        """Render the held-back lighting/composition proposal, if there is one."""
        if not self._suggestions:
            self.suggestion_row.setVisible(False)
            return
        parts = [str(v) for v in self._suggestions.values()]
        self.suggestion_label.setText(
            "Also suggests " + " · ".join(parts) + ". Not applied — these stay yours.")
        self.suggestion_row.setVisible(True)

    def apply_suggestions(self):
        """Only here does a suggested guide or light source reach the form."""
        if not self._suggestions:
            return
        guide = self._suggestions.get("composition_guide")
        if guide:
            index = self.editor.composition.findData(guide)
            if index >= 0:
                self.editor.composition.setCurrentIndex(index)
        lighting = self._suggestions.get("lighting")
        if lighting:
            self.editor.lighting.setCurrentText(lighting)
        self._suggestions = {}
        self.suggestion_row.setVisible(False)
        self.status.emit("Applied the suggestion — change it any time")

    # -- library ----------------------------------------------------------- #
    def reload_library(self, select_stem=None):
        """Repopulate the list. `select_stem` survives the clear().

        Without it every CRUD action would leave nothing selected, because
        clear() drops the selection along with the rows.
        """
        self.library.clear()
        assets.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(assets.CHARACTERS_DIR.glob("*.json")):
            if self._filter and self._filter not in path.stem.lower():
                continue
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.library.addItem(item)
        if select_stem:
            for row in range(self.library.count()):
                if self.library.item(row).text() == select_stem:
                    self.library.setCurrentRow(row)
                    break

    def set_filter(self, text):
        self._filter = (text or "").strip().lower()
        self.reload_library()

    def load_selected(self):
        item = self.library.currentItem()
        if item is None:
            self.status.emit("Select a character in the library first")
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Could not load character", "{}\n\n{}".format(path, exc))
            return
        spec.setdefault("slug", path.stem)
        self.editor.load_spec(spec)
        self.update_reference_label()
        self.status.emit("Loaded {}".format(path.name))

    def save_spec(self):
        spec = self.editor.spec()
        slug = bp.slugify(spec.get("slug") or spec.get("subject", "avatar"))
        path = assets.CHARACTERS_DIR / "{}.json".format(slug)

        if path.exists():
            answer = QMessageBox.question(
                self,
                "Overwrite character?",
                "{} already exists.\n\nOverwriting replaces an identity that later shots may "
                "depend on. Overwrite?".format(path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        spec["slug"] = slug
        assets.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.reload_library(select_stem=slug)
        self.status.emit("Saved {}".format(path.name))

    # -- library CRUD ------------------------------------------------------ #
    # Character specs are the one thing under temp/resources/ the user invests
    # in, so every destructive action here is explicit and confirmed.

    def character_path(self, stem):
        return assets.CHARACTERS_DIR / "{}.json".format(stem)

    def safe_slug(self, text):
        """slugify(), hardened for use as a filename.

        slugify truncates to 40 chars *after* stripping, so it can still hand
        back a trailing hyphen; and Windows reserved device names survive it
        intact, which makes for a file that is a nuisance to remove.
        """
        slug = bp.slugify(text).strip("-")
        reserved = slug.lower() in {"con", "prn", "aux", "nul"}
        if reserved or (slug[:3].lower() in {"com", "lpt"} and slug[3:].isdigit()):
            slug += "-character"
        return slug or "untitled"

    def free_slug(self, base):
        """`base`, `base-2`, `base-3`... - the first that is not taken."""
        if not self.character_path(base).exists():
            return base
        for suffix in range(2, 1000):
            candidate = "{}-{}".format(base, suffix)
            if not self.character_path(candidate).exists():
                return candidate
        return "{}-{}".format(base, "copy")

    def selected_path(self, action):
        item = self.library.currentItem()
        if item is None:
            self.status.emit("Select a character to {} first".format(action))
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def show_library_menu(self, point):
        menu = QMenu(self.library)
        menu.addAction("Load", self.load_selected)
        menu.addAction("New...", self.new_character)
        menu.addAction("Rename...", self.rename_character)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_character)
        menu.exec(self.library.mapToGlobal(point))

    def new_character(self):
        """Blank or a copy of what is on screen - the user picks each time."""
        box = QMessageBox(self)
        box.setWindowTitle("New character")
        box.setText(
            "Start from nothing, or copy the character currently in the form?\n\n"
            "Nothing is written to disk until you press Save."
        )
        blank = box.addButton("Blank", QMessageBox.ButtonRole.AcceptRole)
        duplicate = box.addButton("Duplicate current", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(blank)
        box.exec()

        clicked = box.clickedButton()
        if clicked is blank:
            self.editor.load_spec({})
            self.library.setCurrentRow(-1)
            self.status.emit("New character - fill in the subject, then Save")
        elif clicked is duplicate:
            spec = self.editor.spec()
            source = self.safe_slug(spec.get("slug") or spec.get("subject", "avatar"))
            # Advance the slug, or Save would silently overwrite the original.
            spec["slug"] = self.free_slug(source)
            self.editor.load_spec(spec)
            self.library.setCurrentRow(-1)
            self.status.emit(
                "Copied as '{}' - edit it, then Save".format(spec["slug"]))

    def rename_character(self):
        path = self.selected_path("rename")
        if path is None:
            return
        name, ok = QInputDialog.getText(self, "Rename character", "New name:", text=path.stem)
        if not ok:
            return
        slug = self.safe_slug(name)
        if not name.strip():
            self.status.emit("A character needs a name")
            return
        if slug == path.stem:
            return
        target = self.character_path(slug)
        if target.exists():
            QMessageBox.warning(
                self, "Name already taken",
                "{} already exists. Renaming onto it would replace an identity that later "
                "shots may depend on.".format(target.name),
            )
            return

        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            # The stem and the `slug` field are two copies of one identity;
            # load_selected() falls back to the stem, so they must not drift.
            spec["slug"] = slug
            target.write_text(
                json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            path.unlink()
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Could not rename character",
                                "{}\n\n{}".format(path, exc))
            return

        self.reload_library(select_stem=slug)
        if self.editor.spec().get("slug") == path.stem:
            self.editor.slug.setText(slug)
        self.status.emit("Renamed to {}".format(target.name))

    def delete_character(self):
        path = self.selected_path("delete")
        if path is None:
            return
        answer = QMessageBox.question(
            self, "Delete character?",
            "{} will be removed from disk.\n\nLater shots that reuse this identity will "
            "have nothing to load, and this cannot be undone.".format(path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Could not delete character",
                                "{}\n\n{}".format(path, exc))
            return
        self.reload_library()
        self.status.emit("Deleted {}".format(path.name))

    # -- reference (character consistency) --------------------------------- #
    # The controls live in the editor's Identity tab; these remain as the
    # programmatic entry points the rest of the app and the tests use.
    def choose_reference(self):
        self.editor.choose_reference()

    def clear_reference(self):
        self.editor.set_reference("")
        self.status.emit("Reference cleared")

    def update_reference_label(self):
        reference = self.editor.reference()
        if reference:
            self.reference_label.setText("Identity locked to " + Path(reference).name)
        else:
            self.reference_label.setText(
                "No reference image — the face is invented each time."
            )

    # -- prompt ------------------------------------------------------------ #
    def schedule_rebuild(self):
        self._timer.start()

    def set_learned(self, enabled):
        self.use_learned = bool(enabled)
        self.schedule_rebuild()

    def rebuild(self):
        # Any edit invalidates a model-supplied prompt — the spec is the truth.
        self._override_prompt = None
        spec = self.editor.spec()
        for error in (bp.validate_purpose(self.bank, spec.get("purpose")),
                      bp.validate_shot(self.bank, spec.get("shot"))):
            if error:
                self.status.emit(error)
                return
        weights = hist.weights() if self.use_learned else None
        prompt, layers = bp.compose(
            self.bank, spec, detailed=bool(self.form_mode.currentData()), weights=weights,
            anatomy_guard=self.anatomy_guard.isChecked(),
        )
        self.prompt_view.setPlainText(prompt)
        self.passing = self.lint.update_result(prompt, self.bank, layers)
        self.last_layers = layers
        self.status.emit(
            "{} words · {}".format(len(prompt.split()), "PASS" if self.passing else "needs work")
        )

    def reshuffle(self):
        self.editor.seed.setValue((self.editor.seed.value() + 1) % 10000)

    def prompt_text(self):
        return self.prompt_view.toPlainText()

    # -- per-generation overrides -------------------------------------------- #
    # "(use Settings)" is index 0 / empty data on all four, so leaving them
    # alone is indistinguishable from before this existed.
    def provider_override(self):
        return self.gen_provider.currentData() or None

    def model_override(self):
        return self.gen_model.text().strip() or None

    def options_override(self):
        options = {}
        if self.gen_resolution.currentData():
            options["resolution"] = self.gen_resolution.currentData()
        if self.gen_output_format.currentData():
            options["output_format"] = self.gen_output_format.currentData()
        return options

    # -- results handed back from the Brief view ---------------------------- #
    def apply_suggested_spec(self, spec):
        """Merge a model-drafted spec over the form: the fields the draft names
        are overwritten, the fields it leaves out keep your values. Used by
        both Brief's idea->spec (a fresh draft, meant to fill the form) and the
        Advisor (an iterative tweak - "make her older" returns just `subject`,
        and only that changes)."""
        self.editor.apply_partial(spec)
        self.status.emit("Applied the drafted character — review it before generating")

    def use_upgraded_prompt(self, prompt):
        """Adopt a rewrite that already passed the gate in brief.py.

        It sticks until the next edit, at which point the spec wins again — the
        spec, not a one-off rewrite, is what the app can reproduce.

        The pending rebuild has to be CANCELLED first. `schedule_rebuild()`
        arms a 180ms single-shot timer, and `rebuild()` opens by clearing
        `_override_prompt` — so an edit made less than 180ms before Apply left
        a timer that fired straight afterwards and silently reverted the
        rewrite the user had just adopted. It showed up as
        `tests/test_newui.py` failing "adopted into compose" on roughly half of
        full-suite runs and never standalone, which reads like flakiness but is
        a real race: the same timing exists when a person edits a field and
        clicks Apply quickly, and there the prompt just quietly changes back.
        Confirmed pre-existing by stashing every other change in this branch
        and reproducing it on the untouched tree.
        """
        self._timer.stop()
        self._override_prompt = prompt
        self.prompt_view.setPlainText(prompt)
        self.passing = self.lint.update_result(prompt, self.bank)
        hist.append(self.editor.spec(), prompt, getattr(self, "last_layers", {}),
                    self.lint.score, self.passing,
                    bool(self.form_mode.currentData()))
        self.status.emit("Using the rewritten prompt — logged, so you can diff it")

    def copy_prompt(self):
        from PyQt6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(self.prompt_text())
        self.status.emit("Prompt copied to clipboard")

    def copy_midjourney_prompt(self):
        from PyQt6.QtGui import QGuiApplication

        prompt = self.prompt_text()
        if not prompt.strip():
            self.status.emit("Nothing to copy yet — build a prompt first")
            return
        text = mx.to_midjourney(self.bank, self.editor.spec(), prompt)
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Midjourney-formatted prompt copied to clipboard")

    def confirm_if_failing(self, question):
        if self.passing:
            return True
        answer = QMessageBox.question(
            self,
            "Prompt has not passed",
            question + "\n\nThe realism check is the workflow's quality gate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # -- generation -------------------------------------------------------- #
    def request_generate(self):
        if not self.confirm_if_failing("Generate from a prompt that hasn't passed?"):
            return
        spec = self.editor.spec()
        prompt = self.prompt_text()
        self.entry_id = hist.append(
            spec, prompt, getattr(self, "last_layers", {}),
            self.lint.score, self.passing, bool(self.form_mode.currentData()),
        )
        self.rating.set_value(0)
        self.rating.setEnabled(False)
        references = [self.editor.reference()] if self.editor.reference() else []
        self.generate_requested.emit(prompt, references)

    def request_upscale(self):
        if not self.current_image:
            self.status.emit("Generate or load an image first")
            return
        self.upscale_requested.emit(str(self.current_image))

    def request_refine(self):
        if not self.current_image:
            self.status.emit("Generate or load an image first")
            return
        self.refine_requested.emit()

    def refresh_key_state(self):
        """Re-evaluate the two controls that need a text-model key.

        Both used to decide ONCE, in setup_ui, and stay that way for the life
        of the window - so adding a key and pressing Settings' "Re-check .env"
        refreshed two badges over there and left these disabled until the app
        was restarted. They are the only two pre-disabled controls in the app,
        which is why this is a method rather than a broadcast.
        """
        ready = bool(gi.env_value(al.KEY_VAR))
        for widget, enabled_tip in (
                (self.vision_qc_checkbox, self._vision_tip),
                (self.coherence_button, self._coherence_tip)):
            widget.setEnabled(ready)
            widget.setToolTip(enabled_tip if ready else (
                "No {} set - add one in Settings, or get one at {}.".format(
                    al.KEY_VAR, al.KEY_URL)))

    def update_cost_note(self):
        """What one more generation would cost. Silent with no provider set,
        so the view still stands up alone in a test."""
        if self.cost_provider is None:
            return
        self.cost_note.setText(self.cost_provider())

    def set_busy(self, busy):
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText("Generating…" if busy else "Generate")
        self.cancel_button.setEnabled(busy)
        self.upscale_button.setEnabled(not busy and bool(self.current_image))
        self.refine_button.setEnabled(not busy and bool(self.current_image))

    def set_refining(self, busy):
        """Distinct from set_busy(): the refine loop can take several minutes
        (up to 3 generations plus 3 critiques), so Generate/Upscale stay
        disabled the same way, but the label says what is actually happening."""
        self.set_busy(busy)
        self.refine_button.setText("Refining…" if busy else "Refine")

    def show_image(self, path):
        self.current_image = path
        if self.preview.load(path):
            self.rating.setEnabled(True)
            self.upscale_button.setEnabled(True)
            self.refine_button.setEnabled(True)
            if self.entry_id:
                hist.rate(self.entry_id, None, image=str(path))
            self.status.emit("Saved {}".format(Path(path).name))
            self._maybe_run_vision_qc(path)
        else:
            self.status.emit("Could not display {}".format(path))

    def _maybe_run_vision_qc(self, path):
        """Opt-in, and never blocks or fails the generation it is checking -
        a missing key, a network error or a malformed reply all just leave
        the panel empty, the same as if the checkbox had been off."""
        if not self.vision_qc_checkbox.isChecked():
            return
        task = VisionQcTask(str(path), self.editor.spec(),
                            reference_path=self.editor.reference())
        task.signals.finished.connect(self._on_vision_qc_finished)
        task.signals.failed.connect(self._on_vision_qc_failed)
        self.pool.start(task)

    def _on_vision_qc_finished(self, checks, score, total):
        self.vision_lint.show_checks(checks)
        if self.entry_id:
            hist.record_vision_qc(self.entry_id, {
                "score": score, "total": total, "checks": checks})

    def _on_vision_qc_failed(self, reason):
        self.status.emit("Vision QC unavailable: {}".format(reason[:160]))

    def request_coherence_check(self):
        prompt = self.prompt_text()
        if not prompt.strip():
            self.status.emit("Nothing to check yet - build a prompt first")
            return
        self.coherence_button.setEnabled(False)
        task = CoherenceTask(prompt)
        task.signals.finished.connect(self._on_coherence_finished)
        task.signals.failed.connect(self._on_coherence_failed)
        task.signals.done.connect(self._on_coherence_done)
        self.pool.start(task)

    def _on_coherence_done(self):
        self.coherence_button.setEnabled(bool(gi.env_value(al.KEY_VAR)))

    def _on_coherence_finished(self, checks, score, total):
        self.coherence_lint.show_checks(checks)

    def _on_coherence_failed(self, reason):
        self.status.emit("Coherence check unavailable: {}".format(reason[:160]))

    def apply_rating(self, value):
        if not self.entry_id:
            self.status.emit("Nothing to rate yet — generate first")
            return
        hist.rate(self.entry_id, value, image=str(self.current_image or ""))
        self.status.emit("Rated {}/5 — this now shapes future prompts".format(value))
