"""Videos category - the Kling camera-movement toolkit and the film glossary.

Two tabs:
  Motion    pick a move, get a Kling-ready prompt, see whether your still can
            actually support it
  Glossary  searchable reference for the filmmaking vocabulary

Clips generate for real now, on Kling 3.0 through Kie - the same job API the
images use. Everything still works with no key and no cost too: compose the
prompt, copy it, and paste it into Kling's own interface. The options row is
Kling's documented input, and the line under it says what pressing the button
will cost before you press it.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_motion as bm  # noqa: E402
import build_sound as bsd  # noqa: E402
import generate_video as gv  # noqa: E402
import motion_lint as ml  # noqa: E402
import sound_lint as sl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..hints import NAV_HINTS
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402

CATEGORY_LABELS = {
    "core": "Core movements",
    "niche": "Niche (advanced scenes)",
    "combo": "Combos (layered)",
}


class VideosView(QWidget):
    hints_applied = pyqtSignal(dict)
    video_requested = pyqtSignal(list, dict)
    cancel_requested = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or {}
        self.bank = bm.load_bank()
        self.sound_bank = bsd.load_bank()
        self.glossary = self._load_glossary()
        self.context = None          # set by the controller: () -> spec dict
        self.image_provider = None   # set by the controller: () -> still path or None
        self._still_override = None  # an explicit "Choose still..." pick, or None
        self.movement = None
        self.prompt = ""
        self.setup_ui()

    def _load_glossary(self):
        path = ROOT / "tools" / "glossary.json"
        if not path.exists():
            return {"terms": [], "categories": {}}
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_motion_tab(), "Motion")
        self.tabs.addTab(self._build_glossary_tab(), "Glossary")

        layout = QVBoxLayout(self)
        # The section says what it is for. Seven of the ten rail sections
        # said nothing at all; the sentence is ui/hints.py's, the same one
        # the rail tooltip and the Go menu use, so the three cannot drift.
        layout.addWidget(MutedLabel(NAV_HINTS["videos"]))
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    # -- Motion ------------------------------------------------------------- #
    def _build_motion_tab(self):
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["MOVEMENT"])
        self.tree.setAlternatingRowColors(True)
        self.tree.currentItemChanged.connect(self._on_movement_selected)

        for category, label in CATEGORY_LABELS.items():
            rows = [(k, m) for k, m in self.bank["movements"].items()
                    if m["category"] == category]
            parent = QTreeWidgetItem(["{}  ({})".format(label, len(rows))])
            self.tree.addTopLevelItem(parent)
            for key, movement in rows:
                child = QTreeWidgetItem([movement["name"]])
                child.setData(0, Qt.ItemDataRole.UserRole, key)
                parent.addChild(child)
            parent.setExpanded(category == "core")

        picker = Card()
        picker.body.setSpacing(T.SPACE["sm"])
        picker.body.addWidget(TitleLabel("Camera movement"))
        picker.body.addWidget(MutedLabel(
            "{} moves - the Kling toolkit plus a locked-off camera. Each one declares "
            "what the still has to contain before it will work.".format(
                len(self.bank["movements"]))
        ))
        picker.body.addWidget(self.tree, 1)

        # --- right side --- #
        self.movement_title = TitleLabel("Pick a movement")
        self.movement_does = MutedLabel("")

        # The hands-on template: [SHOT TYPE] + [SUBJECT] + [ACTION] + [STYLE] +
        # [CAMERA MOVEMENT] + [AUDIO CUES], replacing the old read-only prompt.
        # Picking a movement prefills every field (see _prefill_from_movement);
        # editing any of them just re-assembles the preview below - refresh()
        # itself never overwrites what you have typed.
        self.shot_type = QLineEdit(placeholderText="e.g. close-up shot")
        self.subject_field = QLineEdit(placeholderText="who or what is in frame")
        self.action_field = QLineEdit(placeholderText="what they are doing")
        self.style_field = QLineEdit(placeholderText="a named camera + colour grade, e.g. \"shot on 35mm film, teal and orange grade\"")
        self.camera_movement_field = QLineEdit(placeholderText="the camera move")
        for field in (self.shot_type, self.subject_field, self.action_field,
                     self.style_field, self.camera_movement_field):
            field.textChanged.connect(self.refresh)

        # WHAT HAPPENS WHEN, AND WHERE IT STOPS. The first frame already fixes
        # how the clip looks; what it does not fix is pace and endpoint. One
        # untimed action lets Kling choose both - it finishes early and invents
        # motion to fill the rest. A beat per line ("0-2s: lifts the cup") plus
        # the final pose leaves it nothing to improvise. Drafted from Action and
        # the clip length (build_motion.split_beats), then yours to edit.
        self.timing_field = QPlainTextEdit()
        self.timing_field.setPlaceholderText(
            "0-2s: lifts the cup and blows across it\n2-4s: glances up at the lens\n"
            "4-5s: holds still, half-smiling")
        self.timing_field.setFixedHeight(76)
        self.timing_field.setToolTip(
            "One beat per line, as start-end seconds. One action per beat; the beats "
            "should cover the whole clip with no gaps. Leave empty for an untimed prompt.")
        self.timing_field.textChanged.connect(self.refresh)
        self.ends_on_field = QLineEdit(
            placeholderText="the final pose, e.g. \"still, eyes on camera, steam drifting\"")
        self.ends_on_field.textChanged.connect(self.refresh)
        draft_timing_button = QPushButton("Draft timing from Action")
        draft_timing_button.setProperty("class", "ghost")
        draft_timing_button.setToolTip(
            "Split the Action into timed beats across the clip length, with a closing "
            "hold - a first draft to edit, it replaces what the Timing box says.")
        draft_timing_button.clicked.connect(self.draft_timing)

        template_form = QFormLayout()
        template_form.setHorizontalSpacing(T.COLUMN_GAP)
        template_form.setVerticalSpacing(T.SPACE["sm"])
        for label, widget in (("Shot type", self.shot_type), ("Subject", self.subject_field),
                              ("Action", self.action_field), ("Timing", self.timing_field),
                              ("Ends on", self.ends_on_field), ("Style", self.style_field),
                              ("Camera movement", self.camera_movement_field)):
            template_form.addRow(label, widget)

        # Opt-in, off by default (build_motion.avatar_guard_tail()'s own
        # docstring covers why this is separate from the standing negative
        # guard below) - lives beside the prompt fields it actually changes,
        # not the Generate card's job-parameter options further down.
        self.avatar_guard = QCheckBox("avatar/multi-cut guard")
        self.avatar_guard.setToolTip(
            "Append an extra guard for an avatar going through multiple cuts "
            "or carrying dialogue (identity drift, overacting, frozen pauses, "
            "gimbal-smooth camera moves, ...) - pairs well with \"multi-shot "
            "(auto)\" below.")
        self.avatar_guard.stateChanged.connect(self.refresh)

        # Measured from a viral one-take cat clip (video_realism_bank.json):
        # planted weight, follow-through, real-time speed, a background that
        # holds - and an ordinary phone instead of a named cinema camera.
        # HOW THE PROMPT IS WRITTEN. "One-take story" is the shape of the
        # user's own 150k-view prompt: "Static shot, ..." then the beats as
        # plain sentences in order with time words, closing on "Subtle, fluid
        # motion." (build_motion.assemble_story). "Tagged list" is the
        # original comma template with "0-3s:" codes, unchanged.
        self.write_as = QComboBox()
        self.write_as.addItem("One-take story (sentences)", "story")
        self.write_as.addItem("Tagged list (0-3s: codes)", "tagged")
        self.write_as.setToolTip(
            "One-take story: a short camera opening (\"Static shot\" for a still camera), then "
            "each Timing line as a sentence in order - Initially... Then... Suddenly... Finally... "
            "- the way viral prompts read. Timing lines can be plain lines or \"0-3s:\" beats; "
            "the seconds are dropped. Tagged list: the original comma template.")
        self.write_as.currentIndexChanged.connect(self._on_write_as)
        # Optional, not standing: the 150k-view prompt had no negatives at all.
        self.negatives = QCheckBox("Negatives (no warped face, no extra fingers...)")
        self.negatives.setChecked(False)
        self.negatives.setToolTip(
            "Appends the artifact guard - no warped face, no floating limbs, no distorted hands, "
            "no extra fingers, no morphing. Optional: off by default for a one-take story, on "
            "for a tagged list. The check reads 'optional' when it is off.")
        self.negatives.stateChanged.connect(self.refresh)
        self.real_motion = QCheckBox("Real motion (auto)")
        self.real_motion.setChecked(True)
        self.real_motion.setToolTip(
            "Adds how things really move, for this subject and camera: bodies planted with "
            "real weight, hair/fur/tails lagging a beat then settling, real-time speed (never "
            "slow motion) that builds over the first second, and a background that holds still "
            "or stays solid as the camera passes.")
        self.real_motion.stateChanged.connect(self.refresh)
        self.phone_look = QCheckBox("Phone video look")
        self.phone_look.setChecked(True)
        self.phone_look.setToolTip(
            "Style becomes an ordinary phone video with flat natural colours instead of a named "
            "film or cinema camera and colour grade. Toggling it rewrites the Style field.")
        self.phone_look.toggled.connect(self._apply_style_choice)

        self.prompt_view = QPlainTextEdit()
        self.prompt_view.setReadOnly(True)
        self.prompt_view.setProperty("class", "mono")
        self.prompt_view.setMinimumHeight(84)
        self.prompt_view.setPlaceholderText(
            "Select a movement, then edit any field above - the Kling prompt "
            "here is rebuilt from them live."
        )

        # Five form rows plus a multi-line preview, at full size, no longer
        # fit a 700px-floor window without crushing something - the fixed
        # 48/64px boxes that used to "fix" this just clipped the second line
        # of the preview mid-word, which read as overlapping garbage. Give
        # every field its natural height and let the whole block scroll as
        # one unit instead, so nothing is ever half-visible.
        form_holder = QWidget()
        form_holder_layout = QVBoxLayout(form_holder)
        form_holder_layout.setContentsMargins(0, 0, 0, 0)
        form_holder_layout.setSpacing(T.SPACE["sm"])
        form_holder_layout.addLayout(template_form)
        draft_row = QHBoxLayout()
        draft_row.addWidget(draft_timing_button)
        draft_row.addStretch(1)
        form_holder_layout.addLayout(draft_row)
        form_holder_layout.addWidget(self.avatar_guard)
        form_holder_layout.addWidget(self.real_motion)
        form_holder_layout.addWidget(self.phone_look)
        form_holder_layout.addWidget(self.negatives)
        write_row = QHBoxLayout()
        write_row.addWidget(QLabel("Write as"))
        write_row.addWidget(self.write_as, 1)
        form_holder_layout.addLayout(write_row)
        form_holder_layout.addWidget(self.prompt_view)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_scroll.setWidget(form_holder)
        form_scroll.setMinimumHeight(220)

        self.lint_badge = Badge("-", "neutral")
        # Secondary, not primary: copying text for pasting elsewhere is the
        # free path, and the button that actually spends money (below) is the
        # one that should read as the main action - they had this backwards.
        copy_button = QPushButton("Copy for Kling")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_prompt)

        self.apply_button = QPushButton("Apply framing to the still")
        self.apply_button.setToolTip(
            "Set the shot and composition this movement needs, on the character "
            "open in Images. Your explicit choices are never overwritten."
        )
        self.apply_button.clicked.connect(self.apply_hints)
        self.apply_button.setEnabled(False)

        # apply_button alone needs 372px and cannot shrink - paired with the
        # badge and copy button the row wanted 672px against the ~407px this
        # column actually has once its own QScrollArea refuses to compress it
        # any further (a resizable scroll area never goes below the content's
        # own minimum size - unlike a plain layout, it will not silently
        # overlap instead, so the excess was just clipped off-screen instead).
        # Splitting it onto its own row is the fix, not a wider scrollbar.
        actions = QHBoxLayout()
        actions.setSpacing(T.SPACE["sm"])
        actions.addWidget(self.lint_badge)
        actions.addWidget(copy_button)
        actions.addStretch(1)

        apply_row = QHBoxLayout()
        apply_row.addWidget(self.apply_button)
        apply_row.addStretch(1)

        # [AUDIO CUES] - no scene or sound sheet exists here to attach to, so
        # this is a standalone suggestion: the same ElevenLabs key-effect shape
        # and gate Cats' sound sheet uses, shown and copyable beside the Kling
        # prompt. It is never sent to Kling and never persisted - see the
        # rebuild plan for why (Kling's own audio stays off; two soundtracks
        # would fight the Sound section's three-layer system).
        self.audio_cues_field = QLineEdit(
            placeholderText="a specific sound for this shot, e.g. \"claws scraping "
                            "on a wooden door\" (optional)")
        self.audio_cues_field.textChanged.connect(self.refresh)
        self.audio_badge = Badge("-", "neutral")
        copy_cue_button = QPushButton("Copy sound cue")
        copy_cue_button.setProperty("class", "ghost")
        copy_cue_button.clicked.connect(self.copy_audio_cue)

        # copy_cue_button gets its own row for the same reason apply_button
        # does above - the field can shrink, the button cannot.
        audio_row = QHBoxLayout()
        audio_row.setSpacing(T.SPACE["sm"])
        audio_row.addWidget(MutedLabel("Audio cue"))
        audio_row.addWidget(self.audio_cues_field, 1)
        audio_row.addWidget(self.audio_badge)

        audio_button_row = QHBoxLayout()
        audio_button_row.addWidget(copy_cue_button)
        audio_button_row.addStretch(1)

        # THE FIRST FRAME. Kling is image-to-video underneath - the still
        # constrains composition, identity and framing far more than the
        # prompt does. Every clip made here used to start from nothing but
        # text, which is exactly why "the video I want" kept not happening.
        # Defaults to whatever is open in Images; an explicit pick overrides
        # it, same precedence rule as everywhere else in this app.
        self.still_label = MutedLabel("First frame: none")
        self.still_badge = Badge("-", "neutral")
        choose_still_button = QPushButton("Choose still...")
        choose_still_button.setProperty("class", "ghost")
        choose_still_button.clicked.connect(self.choose_still)
        clear_still_button = QPushButton("Clear")
        clear_still_button.setProperty("class", "ghost")
        clear_still_button.clicked.connect(self.clear_still)

        # Same split again: the label can shrink, "Choose still..." and
        # "Clear" cannot - all four together wanted 617px of ~407px.
        still_row = QHBoxLayout()
        still_row.setSpacing(T.SPACE["sm"])
        still_row.addWidget(self.still_badge)
        still_row.addWidget(self.still_label, 1)

        still_button_row = QHBoxLayout()
        still_button_row.setSpacing(T.SPACE["sm"])
        still_button_row.addWidget(choose_still_button)
        still_button_row.addWidget(clear_still_button)
        still_button_row.addStretch(1)

        # Kling 3.0's own options, for one clip. The Cats section takes its
        # duration from the scene it belongs to; here there is no scene, so the
        # length is a choice like the others.
        self.duration = QSpinBox(minimum=gv.DURATION_MIN, maximum=gv.DURATION_MAX)
        self.duration.setValue(5)
        self.duration.setSuffix("s")
        self.duration.setToolTip(
            "Kling 3.0 generates any whole second from {} to {}.".format(
                gv.DURATION_MIN, gv.DURATION_MAX))
        self.duration.valueChanged.connect(self.update_cost_note)
        # The beat checks measure the timeline against the clip length.
        self.duration.valueChanged.connect(self.refresh)

        self.aspect = QComboBox()
        for option in gv.ASPECTS:
            self.aspect.addItem(option, option)
        index = self.aspect.findData(gv.DEFAULTS["aspect_ratio"])
        if index >= 0:
            self.aspect.setCurrentIndex(index)

        self.mode = QComboBox()
        for option in gv.MODES:
            self.mode.addItem(option, option)
        self.mode.setToolTip("std is the cheapest tier. pro and 4K cost more per second.")
        self.mode.currentIndexChanged.connect(self.update_cost_note)

        self.sound = QCheckBox("audio")
        self.sound.setToolTip(
            "Kling's own audio, at roughly double the price per second. The Sound "
            "section makes effects in ElevenLabs instead.")
        self.sound.stateChanged.connect(self.update_cost_note)

        # Kling 3.0's Auto multi-shot: it decides the camera-angle changes/cuts
        # itself within the one clip - no separate per-cut prompting UI here,
        # that's Kling's own Custom mode and is not implemented. No separate
        # cost multiplier exists for this in pricing.json (the course notes it
        # carries no surcharge beyond the clip's own per-second price), so it
        # doesn't need to be in update_cost_note()'s inputs.
        self.multi_shot = QCheckBox("multi-shot (auto)")
        self.multi_shot.setToolTip(
            "Let Kling automatically vary camera angles/cuts within this one clip, "
            "instead of a single continuous shot.")

        self.generate_button = QPushButton("Generate the clip")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("videos"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.request_video)

        # Clips are the slowest thing in the app - minutes, not seconds - so
        # this is the path where having no way out hurt most. Videos runs on
        # its own pool, so MainWindow stops it through cancel_videos().
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "danger")
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip(
            "Stop waiting on this clip. A request already sent to Kling still "
            "finishes and may still be billed; anything queued is dropped.")
        self.cost_note = MutedLabel("")

        # generate_button (279px, no shrink) alone left only 105px for the
        # other four controls' combined 380px - same split as the rows above.
        # Tight (xs) spacing: even alone, duration+aspect+mode+sound at their
        # own minimums still needed a few px more than the column has.
        options = QHBoxLayout()
        options.setSpacing(T.SPACE["xs"])
        options.addWidget(self.duration)
        options.addWidget(self.aspect)
        options.addWidget(self.mode)
        options.addWidget(self.sound)
        options.addStretch(1)

        # Its own row, not squeezed into `options` above - that row is already
        # documented as tight at the floor window width (four controls at
        # their own minimums barely fit), so a fifth would risk the same
        # button-elision failure test_layout.py exists to catch.
        multi_shot_row = QHBoxLayout()
        multi_shot_row.addWidget(self.multi_shot)
        multi_shot_row.addStretch(1)

        generate_row = QHBoxLayout()
        generate_row.addWidget(self.generate_button)
        generate_row.addWidget(self.cancel_button)
        generate_row.addStretch(1)

        # form_scroll's own 220px floor covers the five-row form + prompt
        # preview alone, per the comment above - it says nothing about the
        # four rows and the cost note that come after it. At the 700px-floor
        # window those together still do not fit the card, and a QVBoxLayout
        # forced smaller than its own minimum size does not shrink - it lets
        # later rows overlap earlier ones instead. Same fix as Compose's
        # result card: everything below the two title labels scrolls as one
        # unit, so a small window scrolls rather than overlaps.
        below_title = QWidget()
        below_title_layout = QVBoxLayout(below_title)
        below_title_layout.setContentsMargins(0, 0, 0, 0)
        below_title_layout.setSpacing(T.SPACE["sm"])
        below_title_layout.addWidget(form_scroll, 1)
        below_title_layout.addLayout(actions)
        below_title_layout.addLayout(apply_row)
        below_title_layout.addLayout(audio_row)
        below_title_layout.addLayout(audio_button_row)
        below_title_layout.addLayout(still_row)
        below_title_layout.addLayout(still_button_row)
        below_title_layout.addLayout(options)
        below_title_layout.addLayout(multi_shot_row)
        below_title_layout.addLayout(generate_row)
        below_title_layout.addWidget(self.cost_note)

        below_title_scroll = QScrollArea()
        below_title_scroll.setWidgetResizable(True)
        # AsNeeded, not Off: a resizable QScrollArea never shrinks its content
        # below that content's own minimum size the way a plain layout would -
        # it clips instead. Every row above is now sized to fit the declared
        # 1100px-floor window with room to spare, but if a future row (or a
        # wider font) pushes it over again, a scrollbar surfaces that rather
        # than silently cutting a field off past the visible edge.
        below_title_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        below_title_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        below_title_scroll.setWidget(below_title)

        prompt_card = Card()
        prompt_card.body.setSpacing(T.SPACE["sm"])
        prompt_card.body.addWidget(self.movement_title)
        prompt_card.body.addWidget(self.movement_does)
        prompt_card.body.addWidget(below_title_scroll, 1)

        self.checks = QTreeWidget()
        self.checks.setColumnCount(3)
        self.checks.setHeaderLabels(["", "CHECK", "DETAIL"])
        self.checks.setRootIsDecorated(False)
        self.checks.setAlternatingRowColors(True)
        self.checks.setColumnWidth(0, 28)
        self.checks.setColumnWidth(1, 210)

        checks_card = Card()
        checks_card.body.setSpacing(T.SPACE["sm"])
        checks_card.body.addWidget(TitleLabel("Will this shot work?"))
        checks_card.body.addWidget(MutedLabel(
            "The Kling toolkit's own rules, plus what the still must contain."
        ))
        checks_card.body.addWidget(self.checks, 1)

        right = QSplitter(Qt.Orientation.Vertical)
        right.setObjectName("videos_prompt_checks")
        right.addWidget(prompt_card)
        right.addWidget(checks_card)
        right.setSizes([420, 260])

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("videos_picker_right")
        splitter.addWidget(picker)
        splitter.addWidget(right)
        splitter.setSizes([380, 720])
        splitter.setStretchFactor(1, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(splitter)
        return page

    # -- Glossary ----------------------------------------------------------- #
    def _build_glossary_tab(self):
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search 50 filmmaking terms...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_glossary)

        self.glossary_tree = QTreeWidget()
        self.glossary_tree.setColumnCount(2)
        self.glossary_tree.setHeaderLabels(["TERM", "MEANING"])
        self.glossary_tree.setAlternatingRowColors(True)
        self.glossary_tree.setColumnWidth(0, 240)
        self.glossary_tree.setWordWrap(True)

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("The Modern Cinematic Glossary"))
        card.body.addWidget(MutedLabel(
            "Framing, movement and lighting are things this app can act on. "
            "Editing and sound are here for your own reference - the app does "
            "not touch post-production."
        ))
        card.body.addWidget(self.search)
        card.body.addWidget(self.glossary_tree, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)

        self._filter_glossary("")
        return page

    def _filter_glossary(self, text):
        needle = (text or "").strip().lower()
        self.glossary_tree.clear()
        labels = self.glossary.get("categories", {})
        by_category = {}
        for entry in self.glossary.get("terms", []):
            haystack = (entry["term"] + " " + entry["definition"]).lower()
            if needle and needle not in haystack:
                continue
            by_category.setdefault(entry["category"], []).append(entry)

        for key, label in labels.items():
            rows = by_category.get(key, [])
            if not rows:
                continue
            parent = QTreeWidgetItem(["{}  ({})".format(label, len(rows)), ""])
            parent.setForeground(0, QBrush(QColor(self._palette.get("text_muted", "#94A3B8"))))
            self.glossary_tree.addTopLevelItem(parent)
            for entry in rows:
                parent.addChild(QTreeWidgetItem([entry["term"], entry["definition"]]))
            parent.setExpanded(True)

    # -- behaviour ---------------------------------------------------------- #
    def set_palette_tokens(self, palette):
        self._palette = palette
        self._filter_glossary(self.search.text() if hasattr(self, "search") else "")
        self.refresh()

    def _current_spec(self):
        return self.context() if self.context else {}

    def _resolved_still(self):
        """The first frame this clip will actually start from, or None.

        An explicit "Choose still..." pick always wins over whatever Compose
        currently has open - the same "explicit choice wins" precedence rule
        as shot/lighting/composition and the sound key-effect override.
        """
        if self._still_override:
            return self._still_override
        if self.image_provider:
            return self.image_provider() or None
        return None

    def _on_movement_selected(self, item, _previous):
        if item is None:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self.movement = key
        self.apply_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._prefill_from_movement()
        self.update_cost_note()
        self.refresh()

    def _prefill_from_movement(self):
        """A new movement pick re-fills all six fields - the one moment a
        fresh default is expected. Editing a field afterwards never gets
        silently overwritten; only picking another movement resets them.
        """
        movement = self.bank["movements"][self.movement]
        spec = self._current_spec()
        hints = bm.image_defaults(self.bank, self.movement)
        style = self._default_style(spec)

        for field, value in (
            (self.shot_type, hints.get("shot", "")),
            (self.subject_field, str(spec.get("subject", "")).strip()),
            (self.action_field, str(spec.get("action", "")).strip()),
            (self.style_field, style),
            (self.camera_movement_field,
             ", ".join(s for s in (movement["lead"], movement.get("detail", "")) if s)),
            (self.audio_cues_field,
             bsd.key_for(spec.get("subject", ""), spec.get("action", ""))),
        ):
            field.blockSignals(True)
            field.setText(value)
            field.blockSignals(False)
        self._fill_timing(str(spec.get("action", "")).strip())

    def _default_style(self, spec=None):
        """The Style field's default: the phone look, or a named camera +
        grade (never "cinematic lighting" - vague style words give a video
        model nothing to work with), plus the Compose mood."""
        spec = self._current_spec() if spec is None else spec
        if self.phone_look.isChecked():
            style = bm.phone_style(self.bank)
        else:
            # Seeded off the movement key so the same movement always
            # suggests the same preset.
            style = bm.style_preset(self.bank, seed=sum(ord(c) for c in self.movement))
        style += ", natural motion"
        mood = str(spec.get("mood", "")).strip()
        if mood:
            style += ", " + mood + " tone"
        return style

    def _story_opening(self):
        """A still camera opens on "Static shot"; any other move opens on
        whatever the Camera movement field says (yours to edit)."""
        story_leads = (self.bank.get("realism") or {}).get("story", {}).get("leads", {})
        if self.movement in story_leads:
            return story_leads[self.movement]
        return self.camera_movement_field.text().strip() or bm.story_lead(self.bank, self.movement)

    def _on_write_as(self, _index=None):
        """Switching the style flips the negatives to that style's default."""
        self.negatives.blockSignals(True)
        self.negatives.setChecked(self.write_as.currentData() == "tagged")
        self.negatives.blockSignals(False)
        self.refresh()

    def _apply_style_choice(self, _checked=None):
        """Toggling the phone look is an explicit choice, so it rewrites Style."""
        if self.movement:
            self.style_field.setText(self._default_style())

    def _fill_timing(self, action):
        beats = bm.split_beats(action, self.duration.value()) if action else []
        for field, value in (
            (self.timing_field, "\n".join(bm.format_beats([b]) for b in beats)),
            (self.ends_on_field, bm.default_end_state(action) if beats else ""),
        ):
            field.blockSignals(True)
            if isinstance(field, QPlainTextEdit):
                field.setPlainText(value)
            else:
                field.setText(value)
            field.blockSignals(False)

    def draft_timing(self):
        action = self.action_field.text().strip()
        if not action:
            self.status.emit("Type an Action first - the timing is drafted from it")
            return
        self._fill_timing(action)
        self.refresh()

    def refresh(self):
        """Re-assemble and re-check from whatever the six fields currently
        say - never touches their text. Safe to call on every keystroke, a
        theme change, or just navigating back to this tab.
        """
        if not self.movement:
            return
        movement = self.bank["movements"][self.movement]
        spec = self._current_spec()

        self.movement_title.setText(movement["name"])
        self.movement_does.setText(movement["does"])

        real_motion = (bm.real_motion_line(self.bank, self.subject_field.text(), self.movement)
                       if self.real_motion.isChecked() else "")
        if self.write_as.currentData() == "story":
            self.prompt = bm.assemble_story(
                self.bank, self.movement, self.subject_field.text(),
                bm.story_beats(self.timing_field.toPlainText(), self.action_field.text()),
                end_state=self.ends_on_field.text(), style=self.style_field.text(),
                negatives=self.negatives.isChecked(),
                avatar_guard=self.avatar_guard.isChecked(), real_motion=real_motion,
                opening=self._story_opening())
        else:
            self.prompt = bm.assemble_template(
                self.bank,
                self.shot_type.text(), self.subject_field.text(), self.action_field.text(),
                self.camera_movement_field.text(), self.style_field.text(),
                avatar_guard=self.avatar_guard.isChecked(),
                beats=bm.parse_beats(self.timing_field.toPlainText()),
                end_state=self.ends_on_field.text(),
                real_motion=real_motion, negatives=self.negatives.isChecked())
        self.prompt_view.setPlainText(self.prompt)

        cue = self.audio_cues_field.text().strip()
        if cue:
            cue_results = sl.lint(self.sound_bank, cue)
            cue_score, cue_total = sl.score(cue_results)
            self.audio_badge.set_status(
                "success" if cue_score == cue_total else "warning",
                "{}/{}".format(cue_score, cue_total))
        else:
            self.audio_badge.set_status("neutral", "-")

        checks, warnings = ml.lint(self.prompt, self.bank, self.movement, spec,
                                   negatives=self.negatives.isChecked(),
                                   seconds=self.duration.value())
        self.checks.clear()

        ok_colour = QColor(self._palette.get("success", "#34D399"))
        bad_colour = QColor(self._palette.get("error", "#F87171"))
        warn_colour = QColor(self._palette.get("warning", "#FBBF24"))

        for name, ok, detail in checks:
            row = QTreeWidgetItem(["OK" if ok else "!", name, detail])
            brush = QBrush(ok_colour if ok else bad_colour)
            for column in range(3):
                row.setForeground(column, brush)
            self.checks.addTopLevelItem(row)

        for warning in warnings:
            row = QTreeWidgetItem(["!", "The still is missing", warning])
            for column in range(3):
                row.setForeground(column, QBrush(warn_colour))
            self.checks.addTopLevelItem(row)

        for note in bm.hint_conflicts(self.bank, self.movement, spec):
            row = QTreeWidgetItem(["~", "Framing", note])
            for column in range(3):
                row.setForeground(column, QBrush(warn_colour))
            self.checks.addTopLevelItem(row)

        score = sum(1 for _, ok, _ in checks if ok)
        passed = score == len(checks) and not warnings
        self.lint_badge.set_status(
            "success" if passed else ("warning" if score == len(checks) else "danger"),
            "{}/{}{}".format(score, len(checks),
                             "" if not warnings else " + still"),
        )

        self._refresh_still_label()

    def _refresh_still_label(self):
        """What request_video() will actually send, recomputed live - Compose's
        current image can change while this tab isn't even focused."""
        path = self._resolved_still()
        if self._still_override:
            self.still_label.setText("First frame: {} (chosen)".format(Path(path).name))
            self.still_badge.set_status("success", "attached")
        elif path:
            self.still_label.setText("First frame: {} (from Images)".format(Path(path).name))
            self.still_badge.set_status("success", "attached")
        else:
            self.still_label.setText(
                "First frame: none - Kling will invent the scene from the prompt alone")
            self.still_badge.set_status("warning", "none")

    def video_options(self):
        return {"duration": int(self.duration.value()),
                "aspect_ratio": self.aspect.currentData() or gv.DEFAULTS["aspect_ratio"],
                "mode": self.mode.currentData() or "std",
                "sound": self.sound.isChecked(),
                "multi_shots": self.multi_shot.isChecked()}

    def update_cost_note(self):
        """What this one clip would cost, before the button is pressed."""
        if not hasattr(self, "cost_note"):
            return
        options = self.video_options()
        self.cost_note.setText("{}s clip · {}".format(
            options["duration"],
            gv.price_note(gv.DEFAULT_MODEL, options["duration"],
                          mode=options["mode"], sound=options["sound"])))

    def choose_still(self):
        start = str(assets.IMAGES_DIR if assets.IMAGES_DIR.exists() else ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose the first frame", start, "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._still_override = path
            self._refresh_still_label()
            self.status.emit("First frame set to {}".format(Path(path).name))

    def clear_still(self):
        self._still_override = None
        self._refresh_still_label()
        self.status.emit("Cleared - back to whatever is open in Images, if anything")

    def request_video(self):
        text = self.prompt_view.toPlainText().strip()
        if not text:
            self.status.emit("Pick a movement first")
            return
        still = self._resolved_still()
        if not still:
            answer = QMessageBox.question(
                self,
                "No first frame",
                "Generate with no first frame?\n\nKling will invent the scene from the "
                "prompt alone, with no still to keep the composition or identity fixed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        options = self.video_options()
        self.video_requested.emit(
            [{"index": 0, "prompt": text, "image": still,
              "duration": options.pop("duration"),
              "out_name": "clip-{}.mp4".format(self.movement or "move")}],
            options)

    def set_busy(self, busy, total=0):
        """Videos toggled its generate button from three scattered places and
        had no set_busy at all. One method now, so the Cancel button can never
        disagree with the Generate button about whether a clip is running."""
        self.generate_button.setEnabled(not busy and bool(self.movement))
        self.cancel_button.setEnabled(busy)

    def on_video_finished(self, _index, path):
        self.set_busy(False)
        self.status.emit("Clip saved: {}".format(path))

    def on_video_failed(self, _index, reason):
        self.set_busy(False)
        self.status.emit(reason[:160])

    def copy_prompt(self):
        if not self.prompt:
            self.status.emit("Pick a movement first")
            return
        QGuiApplication.clipboard().setText(self.prompt)
        self.status.emit("Copied - paste it into Kling")

    def copy_audio_cue(self):
        cue = self.audio_cues_field.text().strip()
        if not cue:
            self.status.emit("Nothing to copy - the audio cue is empty")
            return
        QGuiApplication.clipboard().setText(cue)
        self.status.emit("Copied - paste it into ElevenLabs")

    def apply_hints(self):
        if not self.movement:
            return
        hints = bm.image_defaults(self.bank, self.movement)
        if not hints:
            self.status.emit("This movement has no framing preference")
            return
        self.hints_applied.emit(dict(hints))
        self.status.emit(
            "Applied {} to the still - your own choices were kept".format(
                ", ".join(hints)
            )
        )
