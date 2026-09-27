"""Cats category - a story told in scenes, end to end.

  Story     the idea, the shape, the look, the length
  Scenes    the storyboard, with the gate beside it
  CapCut    the edit sheet for THIS story, plus the assembly steps

The timeline strip on the Scenes tab draws the thing this section exists to make
visible: a scene is one clip, and what survives the cut is slightly less than
what you generate. Kling 3.0 takes any whole second from 3 to 15, so the scene
COUNT is what absorbs a long runtime - the arc gives the shape and its
repeatable beat expands to fill the time.

There is no separate checklist tab. The gate on the Scenes tab IS the checklist,
and a second panel restating it would be a second copy to go stale.
"""

import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
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
import build_prompt as bp  # noqa: E402
import build_pet_sound as bps  # noqa: E402
import build_social as bsoc  # noqa: E402
import build_sound as bsd  # noqa: E402
import build_story as bs  # noqa: E402
import generate_image as gi  # noqa: E402  (key-presence check only)
import generate_sound as gsnd  # noqa: E402  (KEY_VAR, WHERE - shared ElevenLabs constants)
import generate_speech as gspeech  # noqa: E402
import generate_video as gv  # noqa: E402
import history as hist  # noqa: E402
import render_video as rv  # noqa: E402
import sound_lint as sl  # noqa: E402
import social_lint as socl  # noqa: E402
import story_lint as stl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Badge, Card, GateTree, MutedLabel, TitleLabel  # noqa: E402
from ..workers import LlmTask, RenderTask, SoundTask, SpeechTask  # noqa: E402
from .cats_custom import CustomPromptTab  # noqa: E402

# Every field any format asks for. The parser accepts them all and each format
# takes what it wants, rather than there being one parser per format.
SCRIPT_FIELDS = {"caption", "narration", "action", "setting", "task", "mishap",
                 "lead_action", "foil_action"}


class ClipTimeline(QWidget):
    """Two bars per scene: what you generate, and what survives the cut.

    The Ads timeline draws one row because an ad beat has one duration. A story
    scene has two, and the whole point is that they differ - so this draws the
    clip above and the kept portion below it, aligned.
    """

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or {}
        self.scenes = []
        self.hook_seconds = 3.0
        self.show_hook = True
        self.setMinimumHeight(74)
        self.setMaximumHeight(74)

    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.update()

    def set_hook(self, show, hook_seconds=3.0):
        """`trade` has no 3-second hook rule - it opens on a full take. Drawing
        the marker anyway would tell you an opening is "late" against a rule
        this format was never judged by."""
        self.show_hook, self.hook_seconds = show, hook_seconds
        self.update()

    def set_story(self, scenes, hook_seconds=3.0):
        self.scenes, self.hook_seconds = scenes, hook_seconds
        self.update()

    def paintEvent(self, event):
        if not self.scenes:
            return
        colours = self._palette
        accent = QColor(colours.get("primary", "#38BDF8"))
        ok = QColor(colours.get("success", "#34D399"))
        bad = QColor(colours.get("error", "#F87171"))
        muted = QColor(colours.get("text_muted", "#94A3B8"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = painter.fontMetrics()
        width = self.width()

        generated = sum(s["clip_seconds"] for s in self.scenes) or 1
        kept = sum(s["edit_seconds"] for s in self.scenes) or 1

        # Row 1: the clips you pay for, to their own scale.
        top, height = 4, 16
        scale = width / float(generated)
        x = 0.0
        for scene in self.scenes:
            w = max(scene["clip_seconds"] * scale - 2, 2)
            colour = QColor(accent)
            colour.setAlpha(90)
            painter.fillRect(int(x), top, int(w), height, colour)
            x += scene["clip_seconds"] * scale

        # Row 2: what survives, to the finished video's scale.
        top2, height2 = 30, 18
        scale2 = width / float(kept)
        x = 0.0
        for scene in self.scenes:
            w = max(scene["edit_seconds"] * scale2 - 2, 2)
            colour = QColor(ok if scene.get("beat") == "hook" else accent)
            colour.setAlpha(210 if scene.get("beat") == "hook" else 150)
            painter.fillRect(int(x), top2, int(w), height2, colour)
            label = str(scene["n"])
            text_width = metrics.horizontalAdvance(label)
            if w >= text_width + 6:
                painter.setPen(muted)
                painter.drawText(int(x + (w - text_width) / 2), top2 + height2 - 5, label)
            x += scene["edit_seconds"] * scale2

        # The 3-second line, on the finished scale - only for formats judged by
        # the hook rule. Drawing it for a format with no such rule (every
        # reference `trade` video opens on a full 10s take) would read as a
        # failure that was never actually checked.
        if self.show_hook:
            first = self.scenes[0]
            late = first["edit_seconds"] > self.hook_seconds + 0.05
            marker = int(min(self.hook_seconds, kept) * scale2)
            painter.setPen(bad if late else ok)
            painter.drawLine(marker, top2 - 4, marker, top2 + height2 + 4)
            caption = "{:.0f}s".format(self.hook_seconds)
            caption_width = metrics.horizontalAdvance(caption)
            cx = min(max(0, marker - caption_width // 2), max(0, width - caption_width))
            painter.drawText(cx, top2 + height2 + metrics.ascent() + 4, caption)

        painter.setPen(muted)
        painter.drawText(0, top + metrics.ascent() - 2, "")
        painter.end()


class CatsView(QWidget):
    """Emits `generate_requested` with one job per scene."""

    generate_requested = pyqtSignal(list)
    video_requested = pyqtSignal(list, dict)
    story_changed = pyqtSignal()
    status = pyqtSignal(str)
    # Separate from `generate_requested`, which is shaped for one job per
    # scene - the Custom Prompt tab generates exactly one still at a time,
    # the same (prompt, references) shape Compose's own signal uses.
    custom_generate_requested = pyqtSignal(str, list)

    def __init__(self, bank, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bank                     # the image/realism bank
        self.story_bank = bs.load_bank()
        self.sound_bank = bsd.load_bank()
        self.pet_sound_bank = bps.load_bank()
        self.social_bank = bsoc.load_bank()
        self.motion_bank = bm.load_bank()
        self._palette = palette or {}
        self.scenes = []
        self.script = {}
        self.passing = False
        self.images = {}            # scene index -> generated still
        self.videos = {}            # scene index -> generated clip
        self.voiceovers = {}        # scene index -> generated voiceover audio
        self.sfx = {}               # scene index -> {layer: generated audio path}
        self.entries = {}           # scene index -> history entry id
        self.status_by_scene = {}
        # scene index -> {shot_type, subject, action, style, camera_movement,
        # audio_cues} - the 6-field template, hand-edited or defaulted the
        # first time that scene's card is built. Same accepted limitation as
        # images/videos above: keyed by index, so reshaping the story (a
        # different arc or length) can leave a stale entry pointing at a scene
        # that no longer lines up with it.
        self.custom_motion = {}
        self._motion_widgets = {}   # scene index -> {"preview", "audio_badge"}, rebuilt each tab render
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setup_ui()
        # Populates the arc list and shows the right rows for the default
        # format; it ends by rebuilding, so there is no second call here.
        self.on_format_changed()

    # -- construction ------------------------------------------------------ #
    PROMPTS_TAB = 2

    # What each format's script looks like, shown in the box as a placeholder,
    # and explained above it - the explanation used to be static text naming
    # only the story format's own headings and fields, wrong for anything else.
    STORY_PLACEHOLDER = (
        "[hook]\ncaption: He has done this before.\nnarration: Every night. Same time."
        "\naction: staring at the fridge handle\n\n[setup]\ncaption: ...")
    STORY_HELP = (
        "One block per scene, headed [hook], [setup], [escalation]… Each takes "
        "caption, narration and action. The actions must differ - a story where "
        "the cat does the same thing five times is one shot repeated.")
    TRADE_PLACEHOLDER = (
        "[task]\ntask: shovelling wet cement beside a green wheelbarrow\n"
        "mishap: one shoves the other flat into the dirt\n\n"
        "[task-2]\ntask: smoothing plaster onto a wall\nmishap: ...")
    TRADE_HELP = (
        "One block per take, headed [setup], [task], [task-2]… Each takes a task "
        "and a mishap - no caption, no narration, nobody speaks. The tasks must "
        "differ - two takes of the same job is padding.")
    SITCOM_PLACEHOLDER = (
        "[hook]\ncaption: He has done this before.\n"
        "lead_action: clutching a tiny rubber phone to his chest\n"
        "foil_action: watching from the arm of the sofa\n\n[tantrum]\ncaption: ...")
    SITCOM_HELP = (
        "One block per stage, headed [hook], [tantrum], [discipline], [reset], "
        "[lecture]. Each takes a caption and one action per character - no "
        "narration, this reads on mute. Whenever the mother makes contact, say it "
        "is soft and the claws are in: the safety gate rejects the scene otherwise.")

    # Keyed by format, not chosen by a boolean - see ui_cfg().
    PLACEHOLDERS = {"story": STORY_PLACEHOLDER, "trade": TRADE_PLACEHOLDER,
                    "sitcom": SITCOM_PLACEHOLDER}
    HELP = {"story": STORY_HELP, "trade": TRADE_HELP, "sitcom": SITCOM_HELP}

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_story_tab(), "Story")
        self.tabs.addTab(self._build_scenes_tab(), "Scenes")
        self.tabs.addTab(self._build_prompts_tab(), "Prompts")
        self.tabs.addTab(self._build_custom_tab(), "Custom Prompt")
        self.tabs.addTab(self._build_capcut_tab(), "CapCut")
        self.tabs.addTab(self._build_social_tab(), "Social")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _build_story_tab(self):
        self.idea = QLineEdit(placeholderText="a cat that raids the fridge every night")
        self.subject = QLineEdit(placeholderText="a ginger tabby cat with one torn ear")
        self.setting = QLineEdit(placeholderText="a suburban kitchen at night")
        # These were not connected to anything. Typing the cat and the place left
        # every scene still saying "a cat" until some other control happened to
        # trigger a rebuild - so the prompts on screen were not the prompts the
        # form described. `idea` is only used for the AI call, so it stays out.
        self.subject.textChanged.connect(self.rebuild)
        self.setting.textChanged.connect(self.rebuild)
        # Not rebuild - see above, `idea` only feeds the AI call and re-planning
        # the story per keystroke is the bug that comment describes. The post is
        # composed FROM the idea and is cheap, so it alone follows the typing.
        self.idea.textChanged.connect(self.refresh_social)

        # The format decides almost everything else on this tab: which arcs
        # exist, what the script box asks for, whether there is a camera move at
        # all. It goes first for that reason.
        self.format = QComboBox()
        for key, cfg in bs.formats(self.story_bank).items():
            self.format.addItem(cfg["label"], key)
            self.format.setItemData(self.format.count() - 1, cfg.get("note", ""),
                                    Qt.ItemDataRole.ToolTipRole)
        index = self.format.findData(
            self.story_bank.get("default_format", bs.DEFAULT_FORMAT))
        if index >= 0:
            self.format.setCurrentIndex(index)
        self.format.currentIndexChanged.connect(self.on_format_changed)

        self.trade = QComboBox()
        for key, cfg in bs.trades(self.story_bank).items():
            self.trade.addItem(cfg["label"], key)
            self.trade.setItemData(self.trade.count() - 1, cfg.get("note", ""),
                                   Qt.ItemDataRole.ToolTipRole)
        self.trade.setToolTip(
            "The job they are doing. It fills the uniform, the place and the props "
            "- everything the reference videos put on screen before anything "
            "happens. Anything you have typed yourself is kept.")
        self.trade.currentIndexChanged.connect(self.rebuild)

        # Who the series is about. A cast fills the subject, the setting and -
        # for a pair - the relative-scale sentence, all of which story_lint
        # then checks survived into every scene.
        self.cast = QComboBox()
        for key, cfg in bs.casts(self.story_bank).items():
            self.cast.addItem(cfg["label"], key)
            self.cast.setItemData(self.cast.count() - 1, cfg.get("note", ""),
                                  Qt.ItemDataRole.ToolTipRole)
        self.cast.setToolTip(
            "The recurring cast. It fills the cats, the room and - when there are two "
            "of them - how big one is next to the other, which is the whole visual "
            "joke. Anything you have typed yourself is kept.")
        self.cast.currentIndexChanged.connect(self.rebuild)

        # One line that says what this episode is about. It fills the Idea box
        # rather than the script: the words are still written and still gated.
        self.premise = QComboBox()
        self.premise.addItem("(write your own)", "")
        for key, row in bs.premises(self.story_bank).items():
            self.premise.addItem(row["seed"], key)
        self.premise.setToolTip(
            "Fifty episode seeds. Picking one fills the Idea box above - it is a "
            "starting point for the auto-fill, not a script.")
        self.premise.currentIndexChanged.connect(self.on_premise_picked)

        self.style = QComboBox()
        for key, cfg in bs.styles(self.story_bank).items():
            self.style.addItem(cfg["label"], key)
            self.style.setItemData(self.style.count() - 1, cfg["note"],
                                   Qt.ItemDataRole.ToolTipRole)
        self.style.currentIndexChanged.connect(self.rebuild)

        self.arc = QComboBox()
        self.arc.currentIndexChanged.connect(self.rebuild)

        self.seconds = QSpinBox(minimum=10, maximum=120)
        self.seconds.setValue(bs.default_seconds(self.story_bank))
        self.seconds.valueChanged.connect(self.rebuild)

        # A spin box, not a list: Kling 3.0 takes any whole second from 3 to 15,
        # so thirteen dropdown rows would be a worse way to say "pick a number".
        low, high = bs.clip_range(self.story_bank)
        self.clip = QSpinBox(minimum=low, maximum=high)
        self.clip.setValue(bs.default_clip(self.story_bank))
        self.clip.setSuffix("s per clip")
        self.clip.setToolTip(
            "The longest a single generated clip may run. Kling 3.0 takes {}-{}s.\n"
            "Shorter clips mean more scenes for the same runtime; longer ones mean "
            "fewer, longer takes. The Scenes tab shows what it costs either way."
            .format(low, high))
        self.clip.valueChanged.connect(self.rebuild)

        self.write_button = QPushButton("Auto-fill the whole story")
        self.write_button.setIcon(assets.icon("brief"))
        self.write_button.setIconSize(assets.ICON_SIZE)
        self.write_button.setToolTip(
            "From the idea: invents the cat and the place if you have left them "
            "blank, then writes every scene. Anything you have already typed is "
            "kept and used as the brief. "
            "Optional. Uses OpenRouter, and every reply is re-scored by the story "
            "gate before it is accepted.")
        self.write_button.clicked.connect(self.write_story)
        # set_status()-only, like Ads' draft_badge and Compose's autofill -
        # the result is applied to the form/script directly (see on_written
        # below), so there is no separate payload behind an Apply button.
        self.write_badge = AiSuggestionBadge("Writing…")
        self.write_badge.set_status("neutral", "not run")

        self.script_box = QPlainTextEdit()
        self.script_box.setPlaceholderText(self.STORY_PLACEHOLDER)
        self.script_box.textChanged.connect(self.on_script_edited)

        form = Card()
        form.body.addWidget(TitleLabel("The story"))
        self.form_rows = {}
        for label, widget in [("Format", self.format), ("Cast", self.cast),
                              ("Premise", self.premise), ("Idea", self.idea),
                              ("The cat", self.subject), ("Where", self.setting),
                              ("Job", self.trade), ("Look", self.style),
                              ("Shape", self.arc), ("Length (s)", self.seconds),
                              ("Clip length", self.clip)]:
            row = QHBoxLayout()
            caption = QLabel(label)
            caption.setMinimumWidth(max(88, caption.sizeHint().width()))
            row.addWidget(caption)
            row.addWidget(widget, 1)
            form.body.addLayout(row)
            self.form_rows[label] = (caption, widget)
        self.arc_note = MutedLabel("")
        form.body.addWidget(self.arc_note)
        # Without this the rows share out any spare height and drift apart; with
        # it they keep their natural size and the slack collects at the bottom.
        form.body.addStretch(1)

        write_row = QHBoxLayout()
        write_row.addWidget(self.write_button)
        write_row.addWidget(self.write_badge)
        write_row.addStretch(1)

        script_card = Card()
        script_card.body.addWidget(TitleLabel("Scene by scene"))
        script_card.body.addLayout(write_row)
        self.script_help = MutedLabel("")
        script_card.body.addWidget(self.script_help)
        script_card.body.addWidget(self.script_box, 1)
        # 330 was a guess that never accounted for write_row's own two widgets -
        # at the 1100px-floor window the button lost width to the badge sharing
        # its row, eliding "Auto-fill the whole story". Same fix as Ads' matching
        # draft_row/copy_card: floor it to what the row actually needs.
        script_card.setMinimumWidth(max(
            330,
            self.write_button.sizeHint().width() + T.SPACE["sm"]
            + self.write_badge.sizeHint().width() + 2 * T.CARD_PADDING + 12,
        ))

        # Seven labelled rows and a scene-by-scene script both want the whole
        # height of the tab. Stacked, they asked for 700px of a 537px page, and
        # Qt resolves that by violating both minimums - which is how every field
        # ended up 9px tall with its text sliced through the middle. Side by
        # side they each get the full height, and the width is there for it.
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_scroll.setWidget(form)
        # The scroll area is the belt to the splitter's braces: on a short window
        # the form scrolls rather than crushing its own rows again.
        form_scroll.setMinimumWidth(320)
        form_scroll.setMaximumWidth(430)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("cats_story_form_script")
        split.addWidget(form_scroll)
        split.addWidget(script_card)
        split.setChildrenCollapsible(False)
        split.setSizes([390, 520])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(split)
        return page

    def _build_scenes_tab(self):
        self.timeline = ClipTimeline(self._palette)
        self.timing_label = MutedLabel("")

        self.scene_tree = QTreeWidget()
        self.scene_tree.setColumnCount(6)
        self.scene_tree.setHeaderLabels(
            ["", "SCENE", "CLIP", "KEEP", "WHAT HAPPENS", "STATUS"])
        self.scene_tree.setRootIsDecorated(False)
        self.scene_tree.setAlternatingRowColors(True)
        # Generated stills land on their own row. Before this the images existed
        # on disk and nothing in the app ever showed them.
        self.scene_tree.setIconSize(QSize(34, 46))
        self.scene_tree.currentItemChanged.connect(self.on_scene_selected)

        self.lint_badge = Badge("0/12", "neutral")
        # This hand-built tree-plus-label was one of three independent answers
        # to "QTreeWidget will not wrap text" (sound.py and ads.py each built
        # their own too) - now the shared GateTree, same shape: a row per
        # check, the selected (or first-failing) row's reason in a label below.
        self.gate = GateTree()
        # A floor rather than a ceiling: twelve checks in a fixed 230px box left
        # one row visible at the minimum window size. 110 was too generous and
        # overflowed the card at 1100x700 - the layout gate caught it.
        self.gate.tree.setMinimumHeight(76)
        self.scene_tree.setMinimumHeight(76)

        # Kling's options, read from the bank so the enums are stated once and
        # the request builder and this row cannot drift apart.
        model_cfg = bs.video_models(self.story_bank).get(bs.DEFAULT_VIDEO_MODEL, {})
        defaults = model_cfg.get("defaults", {})
        self.video_mode = QComboBox()
        for option in model_cfg.get("mode", ["std"]):
            self.video_mode.addItem(option, option)
        index = self.video_mode.findData(defaults.get("mode", "std"))
        if index >= 0:
            self.video_mode.setCurrentIndex(index)
        self.video_mode.setToolTip(
            "std is the cheapest tier that still looks right. pro and 4K cost "
            "more per second - the estimate below updates when you change it.")
        self.video_mode.currentIndexChanged.connect(self.update_cost_note)

        self.video_sound = QCheckBox("native audio")
        self.video_sound.setChecked(bool(defaults.get("sound", False)))
        self.video_sound.setToolTip(
            "Kling can generate its own audio, at roughly double the price per "
            "second. Off by default: the Sound section already builds three "
            "ElevenLabs layers per scene, and two soundtracks fight.")
        self.video_sound.stateChanged.connect(self.update_cost_note)

        self.video_button = QPushButton("Generate the clips")
        self.video_button.setIcon(assets.icon("videos"))
        self.video_button.setIconSize(assets.ICON_SIZE)
        self.video_button.setToolTip(
            "One clip per scene, each starting from that scene's generated still "
            "- which is what keeps the same cat across the cuts. Generate the "
            "stills first.")
        self.video_button.clicked.connect(self.request_videos)
        self.cost_note = MutedLabel("")

        self.generate_button = QPushButton("Generate every scene")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.clicked.connect(self.request_generate)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)

        board = Card()
        board.body.addWidget(TitleLabel("Storyboard"))
        board.body.addWidget(self.timeline)
        board.body.addWidget(self.timing_label)
        board.body.addWidget(self.scene_tree, 1)
        board.setMinimumWidth(420)

        gate = Card()
        header = QHBoxLayout()
        # "Will this story work?" needed 315px of a 300px column and clipped.
        # The badge beside it has to fit too, so the title is the part that goes.
        header.addWidget(TitleLabel("Will it work?"))
        header.addWidget(self.lint_badge)
        header.addStretch(1)
        gate.body.addLayout(header)
        gate.body.addWidget(self.gate, 1)
        gate.body.addWidget(self.generate_button)
        gate.body.addWidget(self.progress)

        video_row = QHBoxLayout()
        video_row.addWidget(MutedLabel("Video"))
        video_row.addWidget(self.video_mode)
        video_row.addWidget(self.video_sound)
        video_row.addStretch(1)
        gate.body.addLayout(video_row)
        gate.body.addWidget(self.video_button)
        gate.body.addWidget(self.cost_note)
        # 300 never accounted for the two full-width primary buttons stacked
        # inside it - "Generate every scene" lost 20px at the 1100px floor.
        # Same self-healing floor as script_card/copy_card above.
        gate.setMinimumWidth(max(
            300,
            max(self.generate_button.sizeHint().width(),
                self.video_button.sizeHint().width()) + 2 * T.CARD_PADDING + 12,
        ))

        # Side by side, not stacked. Nine scenes and twelve checks are both
        # lists, and stacking them split 537px of page between two things that
        # each wanted 400 - so both sat on their 76px floor showing exactly one
        # row, which is worse than useless for a checklist. Across, each gets
        # the full height, and the splitter still lets you favour one.
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("cats_scenes_board_gate")
        split.addWidget(board)
        split.addWidget(gate)
        split.setChildrenCollapsible(False)
        split.setSizes([500, 340])
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(split)
        return page

    def _build_prompts_tab(self):
        """Both prompts for every scene, side by side and copyable.

        `motion_prompt` has been built per scene since the section shipped and
        was never shown anywhere - the storyboard tooltip named the movement key
        but not the sentence you actually paste into Kling.
        """
        self.prompts_body = QWidget()
        self.prompts_layout = QVBoxLayout(self.prompts_body)
        self.prompts_layout.setContentsMargins(0, 0, 0, 0)
        self.prompts_layout.setSpacing(T.COLUMN_GAP)
        # Without this the scroll area sizes the body to the viewport instead of
        # to its contents, and nine scene cards get squeezed into 500px - the
        # prompt boxes end up overlapping and the row labels 0px tall. The layout
        # gate caught exactly that. SetMinimumSize makes the body demand the
        # height it needs, so the scroll area scrolls rather than crushing.
        self.prompts_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.prompts_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.prompts_body)

        copy_all = QPushButton("Copy every prompt")
        copy_all.setIcon(assets.icon("copy"))
        copy_all.setIconSize(assets.ICON_SIZE)
        copy_all.clicked.connect(self.copy_all_prompts)

        header = QHBoxLayout()
        header.addWidget(TitleLabel("Every scene, both prompts"))
        header.addStretch(1)
        header.addWidget(copy_all)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addLayout(header)
        layout.addWidget(MutedLabel(
            "The still goes to Nano Banana Pro; the move goes to Kling with that "
            "still as its first frame. Generating from the Scenes tab does both "
            "for you - these are here for when you would rather paste them in."))
        layout.addWidget(scroll, 1)
        return page

    def rebuild_prompts(self):
        """Rebuilt on demand rather than on every keystroke."""
        if not hasattr(self, "prompts_layout"):
            return
        while self.prompts_layout.count():
            item = self.prompts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._motion_widgets = {}
        for index, scene in enumerate(self.scenes):
            card = Card()
            card.body.setSpacing(T.SPACE["sm"])

            head = QHBoxLayout()
            head.addWidget(TitleLabel("{}. {}".format(scene["n"], scene["label"])))
            head.addWidget(Badge("{}s clip · keep {:.1f}s".format(
                scene["clip_seconds"], scene["edit_seconds"]), "neutral"))
            head.addStretch(1)
            card.body.addLayout(head)

            if scene.get("caption") or scene.get("narration"):
                card.body.addWidget(MutedLabel("caption: {}    narration: {}".format(
                    scene.get("caption") or "-", scene.get("narration") or "-")))

            # -- still prompt: unchanged, auto-composed, read-only ------------ #
            still_row = QHBoxLayout()
            still_row.addWidget(MutedLabel("Still prompt"), 1)
            still_copy = QPushButton("Copy")
            still_copy.setProperty("class", "ghost")
            still_copy.clicked.connect(
                lambda _=False, value=scene["prompt"]: self.copy_text(value))
            still_copy.setEnabled(bool(scene["prompt"]))
            still_row.addWidget(still_copy)
            card.body.addLayout(still_row)
            still_box = QPlainTextEdit(scene["prompt"])
            still_box.setReadOnly(True)
            still_box.setProperty("class", "mono")
            still_box.setFixedHeight(84)
            card.body.addWidget(still_box)

            # -- video prompt: the 6-field template, hand-editable ------------ #
            self._build_motion_card_section(card, index, scene)

            # check_compatibility returns {requirement, label, fix} dicts, not
            # strings - joining them raised inside a tab-change slot, and Qt
            # answers a Python exception in a slot by aborting the process.
            if scene.get("warnings"):
                card.body.addWidget(MutedLabel(
                    "The move wants something the still may not have: " + "; ".join(
                        "{} - {}".format(w.get("label", ""), w.get("fix", "")).strip(" -")
                        for w in scene["warnings"])))
            self.prompts_layout.addWidget(card)
        self.prompts_layout.addStretch(1)

    def _default_motion_fields(self, index, scene):
        """[SHOT TYPE] + [SUBJECT] + [ACTION] + [STYLE] + [CAMERA MOVEMENT] +
        [AUDIO CUES], defaulted from this scene's own movement/spec - the
        starting point a hand edit then replaces.
        """
        spec = scene.get("spec", {}) or {}
        key = scene.get("movement")
        camera = bs.locked_camera(self.story_bank, scene.get("format") or self.format_key())
        if key == "locked-off" and camera:
            camera_movement = ", ".join(
                s for s in (camera.get("lead", ""), camera.get("detail", "")) if s)
            shot_type = ""
        elif key and key in self.motion_bank.get("movements", {}):
            movement = self.motion_bank["movements"][key]
            camera_movement = ", ".join(
                s for s in (movement["lead"], movement.get("detail", "")) if s)
            shot_type = bm.image_defaults(self.motion_bank, key).get("shot", "")
        else:
            camera_movement = ""
            shot_type = ""
        mood = str(spec.get("mood", "")).strip()
        # A named camera + grade, not "cinematic lighting" - cycled by scene
        # index the same reproducible way accent_for() cycles accents, so
        # neighbouring scenes do not all suggest the same preset. "subtle" is
        # baked in here, not in Videos' own default - a cat's own movement
        # reads as fake fastest when it is too big, a live house rule that
        # only applies to this section.
        style = bm.style_preset(self.motion_bank, seed=index) + ", subtle natural motion"
        if mood:
            style += ", " + mood + " tone"
        return {
            "shot_type": shot_type,
            "subject": str(spec.get("subject", "")).strip(),
            "action": str(spec.get("action", "")).strip(),
            "style": style,
            "camera_movement": camera_movement,
            "audio_cues": bsd.key_for(spec.get("subject", ""), spec.get("action", "")),
        }

    def _build_motion_card_section(self, card, index, scene):
        is_stored = index in self.custom_motion
        fields = self.custom_motion.setdefault(index, self._default_motion_fields(index, scene))
        # Tagged with the scene it was edited for, so rebuild() can tell a
        # real hand edit apart from a stale one left behind at the same
        # index by a DIFFERENT beat - see rebuild()'s own pruning.
        fields.setdefault("_scene_key", scene.get("key"))
        if is_stored:
            # rebuild() recomposes scene["motion_prompt"] from scratch on
            # every story change; a stored hand edit has to win back over
            # that here, not wait for the next keystroke in this card.
            scene["motion_prompt"] = bm.assemble_template(
                self.motion_bank, fields.get("shot_type", ""), fields.get("subject", ""),
                fields.get("action", ""), fields.get("camera_movement", ""),
                fields.get("style", ""))

        card.body.addWidget(MutedLabel("Video prompt ({})".format(scene["movement"] or "no move")))
        form = QFormLayout()
        form.setHorizontalSpacing(T.COLUMN_GAP)
        form.setVerticalSpacing(T.SPACE["xs"])
        widgets = {}
        for key, label in (("shot_type", "Shot type"), ("subject", "Subject"),
                           ("action", "Action"), ("style", "Style"),
                           ("camera_movement", "Camera movement")):
            edit = QLineEdit(fields.get(key, ""))
            edit.textChanged.connect(
                lambda text, i=index, k=key: self._on_motion_field_edited(i, k, text))
            form.addRow(label, edit)
            widgets[key] = edit
        card.body.addLayout(form)

        preview = QPlainTextEdit(scene["motion_prompt"])
        preview.setReadOnly(True)
        preview.setProperty("class", "mono")
        preview.setFixedHeight(56)
        card.body.addWidget(preview)

        audio_row = QHBoxLayout()
        audio_row.addWidget(MutedLabel("Audio cue"))
        audio_edit = QLineEdit(fields.get("audio_cues", ""))
        audio_edit.setPlaceholderText("optional - feeds the CapCut sound sheet's key effect")
        audio_edit.textChanged.connect(
            lambda text, i=index: self._on_motion_field_edited(i, "audio_cues", text))
        audio_badge = Badge("-", "neutral")
        video_copy = QPushButton("Copy")
        video_copy.setProperty("class", "ghost")
        video_copy.clicked.connect(
            lambda _=False, i=index: self.copy_text(self.scenes[i]["motion_prompt"]))
        audio_row.addWidget(audio_edit, 1)
        audio_row.addWidget(audio_badge)
        audio_row.addWidget(video_copy)
        card.body.addLayout(audio_row)

        self._motion_widgets[index] = {"preview": preview, "audio_badge": audio_badge}
        self._update_audio_badge(index, fields.get("audio_cues", ""))

        # Real ElevenLabs sound effects, one button per layer - the ambience/
        # key/accent text already computed for the CapCut sheet, generated for
        # real rather than left as a prompt someone pastes into ElevenLabs by
        # hand. Each button's tooltip carries the actual cue text and its
        # sound_lint score, so "Generate" is never a mystery click.
        sfx_row = QHBoxLayout()
        sfx_row.addWidget(MutedLabel("Sound"))
        for entry in self._scene_sound_layers(index):
            button = QPushButton(entry["label"])
            button.setProperty("class", "ghost")
            button.setToolTip('"{}"  ({}/{})'.format(
                entry["text"], entry["score"], entry["total"]))
            button.clicked.connect(
                lambda _=False, i=index, lk=entry["layer"]: self.generate_scene_sfx(i, lk))
            sfx_row.addWidget(button)
        card.body.addLayout(sfx_row)
        sfx_status = MutedLabel("")
        card.body.addWidget(sfx_status)
        self._motion_widgets[index]["sfx_status"] = sfx_status

        # Real spoken narration - story format only. `trade`'s whole point is
        # one locked-off take with no words at all (story_lint drops the
        # `words` check for it entirely), so this row does not exist for it,
        # the same way the CapCut panel and the script box already vary by
        # format rather than being built once and left showing stale advice.
        # Never auto-filled: an empty line means no voiceover, exactly like
        # the audio-cue field above it.
        if self.format_key() == "story":
            voice_row = QHBoxLayout()
            voice_row.addWidget(MutedLabel("Voiceover"))
            voice_edit = QLineEdit(fields.get("voiceover", ""))
            voice_edit.setPlaceholderText("optional - what this scene says out loud")
            voice_edit.textChanged.connect(
                lambda text, i=index: self._on_motion_field_edited(i, "voiceover", text))
            voice_generate = QPushButton("Generate")
            voice_generate.setProperty("class", "ghost")
            voice_generate.clicked.connect(lambda _=False, i=index: self.generate_scene_voiceover(i))
            voice_row.addWidget(voice_edit, 1)
            voice_row.addWidget(voice_generate)
            card.body.addLayout(voice_row)
            voice_status = MutedLabel("")
            card.body.addWidget(voice_status)
            self._motion_widgets[index]["voice_status"] = voice_status

    def _on_motion_field_edited(self, index, key, text):
        fields = self.custom_motion.setdefault(index, {})
        fields[key] = text
        if not (0 <= index < len(self.scenes)):
            return
        self.scenes[index]["motion_prompt"] = bm.assemble_template(
            self.motion_bank, fields.get("shot_type", ""), fields.get("subject", ""),
            fields.get("action", ""), fields.get("camera_movement", ""),
            fields.get("style", ""))
        widgets = self._motion_widgets.get(index, {})
        if widgets.get("preview") is not None:
            widgets["preview"].setPlainText(self.scenes[index]["motion_prompt"])
        if key == "audio_cues":
            self._update_audio_badge(index, text)
            # The CapCut sheet is the actual destination for this field - keep
            # it in step rather than waiting for the next unrelated rebuild.
            self.refresh_sheet()

    def _update_audio_badge(self, index, text):
        widgets = self._motion_widgets.get(index, {})
        badge = widgets.get("audio_badge")
        if badge is None:
            return
        cue = (text or "").strip()
        if not cue:
            badge.set_status("neutral", "-")
            return
        results = sl.lint(self.sound_bank, cue)
        got, total = sl.score(results)
        badge.set_status("success" if got == total else "warning",
                         "{}/{}".format(got, total))

    def generate_scene_voiceover(self, index):
        fields = self.custom_motion.get(index, {})
        text = (fields.get("voiceover") or "").strip()
        widgets = self._motion_widgets.get(index, {})
        status = widgets.get("voice_status")
        if not text:
            if status:
                status.setText("Write a voiceover line first.")
            return
        if not gi.env_value(gsnd.KEY_VAR):
            if status:
                status.setText(
                    "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        voice_id = gspeech.default_voice()
        if not voice_id:
            if status:
                status.setText(
                    "No default voice set - pick one to copy an id from in Sound -> Voices, "
                    "then set ELEVENLABS_VOICE_ID in .env.")
            return
        if status:
            status.setText("Generating...")
        slug = "cats-{}-{}".format(self.scenes[index]["n"], "voice") \
            if 0 <= index < len(self.scenes) else "cats-{}-voice".format(index)
        task = SpeechTask(text, voice_id=voice_id, out_name="{}.mp3".format(slug))
        task.signals.finished.connect(
            lambda path, i=index: self._on_scene_voiceover_done(i, path))
        task.signals.failed.connect(
            lambda reason, i=index: self._on_scene_voiceover_failed(i, reason))
        self.pool.start(task)

    def _on_scene_voiceover_done(self, index, path):
        self.voiceovers[index] = str(path)
        status = self._motion_widgets.get(index, {}).get("voice_status")
        if status:
            status.setText("Saved: {}".format(path))
        self.status.emit("Voiceover generated")

    def _on_scene_voiceover_failed(self, index, reason):
        status = self._motion_widgets.get(index, {}).get("voice_status")
        if status:
            status.setText(reason)

    def _sound_subject(self):
        return (self.scenes[0]["spec"].get("subject") if self.scenes else None) or "the cat"

    def _extra_sound_layers(self, index, scene):
        """The sitcom format's two extra layers: a cat voice, and the reset snap.

        Returns nothing for every other format, so `story` and `trade` keep the
        three layers sound_bank defines. Each layer is still scored by
        sound_lint inside build_sound - going through this seam rather than
        appending afterwards is what keeps an extra layer from reaching a sheet
        ungated.

        Which character voices a beat is the bank's call (voice_for_beat), not
        this view's - `who` is left unset so discipline and lecture correctly
        play the foil rather than always defaulting to the lead.
        """
        if self.format_key() != "sitcom":
            return None
        cast = bs.cast_members(self.story_bank, self.cast_key())
        foil = next((m for m in cast if m.get("role") == "foil"), {})
        return bps.extra_layers(self.pet_sound_bank, self.sound_bank,
                                scene.get("beat", ""), seed=index,
                                offscreen_foil=bool(foil.get("offscreen")))

    def _scene_sound_layers(self, index):
        """The same sheet refresh_sheet() prints for CapCut, for just this one
        scene - the single source both the button tooltips and the actual
        generation call read from, so they can never disagree.

        Three layers for most formats, five for `sitcom`; the difference comes
        from _extra_sound_layers, which is passed here as well as to the sheet
        for exactly that reason.
        """
        if not (0 <= index < len(self.scenes)):
            return []
        scene = self.scenes[index]
        spec = scene.get("spec", {})
        return bsd.scene_sound(
            self.sound_bank,
            setting=spec.get("setting") or scene.get("setting", ""),
            subject=self._sound_subject(),
            doing=spec.get("action") or scene.get("action", ""),
            seed=index, key_override=self._audio_cue_overrides().get(index),
            extra=self._extra_sound_layers(index, scene))

    def generate_scene_sfx(self, index, layer):
        if not gi.env_value(gsnd.KEY_VAR):
            self.status.emit(
                "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        entry = next((e for e in self._scene_sound_layers(index) if e["layer"] == layer), None)
        status = self._motion_widgets.get(index, {}).get("sfx_status")
        if not entry:
            return
        if status:
            status.setText("Generating {}...".format(entry["label"]))
        slug = "cats-{}-{}".format(self.scenes[index]["n"], layer) \
            if 0 <= index < len(self.scenes) else "cats-{}-{}".format(index, layer)
        task = SoundTask(entry["text"], out_name="{}.mp3".format(slug))
        task.signals.finished.connect(
            lambda path, i=index, lk=layer: self._on_scene_sfx_done(i, lk, path))
        task.signals.failed.connect(lambda reason, i=index: self._on_scene_sfx_failed(i, reason))
        self.pool.start(task)

    def _on_scene_sfx_done(self, index, layer, path):
        self.sfx.setdefault(index, {})[layer] = str(path)
        status = self._motion_widgets.get(index, {}).get("sfx_status")
        if status:
            status.setText("Saved {}: {}".format(layer, path))
        self.status.emit("{} sound generated".format(layer.title()))

    def _on_scene_sfx_failed(self, index, reason):
        status = self._motion_widgets.get(index, {}).get("sfx_status")
        if status:
            status.setText(reason[:200])

    def _audio_cue_overrides(self):
        """{scene index: cue text} for every scene with a non-blank cue -
        story_sound() falls back to key_for() wherever this has no entry."""
        return {index: fields["audio_cues"] for index, fields in self.custom_motion.items()
                if fields.get("audio_cues", "").strip()}

    def copy_text(self, text):
        if not (text or "").strip():
            self.status.emit("Nothing to copy")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied")

    def copy_all_prompts(self):
        blocks = []
        for scene in self.scenes:
            blocks.append("{}. {}  ({}s clip, keep {:.1f}s)".format(
                scene["n"], scene["label"], scene["clip_seconds"], scene["edit_seconds"]))
            blocks.append("  still: " + scene["prompt"])
            blocks.append("  video: " + (scene["motion_prompt"] or "(no move)"))
            blocks.append("")
        self.copy_text("\n".join(blocks))

    def on_tab_changed(self, index):
        if index == self.PROMPTS_TAB:
            self.rebuild_prompts()

    def on_scene_selected(self, current, _previous):
        """Selecting a scene in the storyboard opens it in the Prompts tab."""
        if current is None or not hasattr(self, "prompts_body"):
            return
        self._selected_scene = self.scene_tree.indexOfTopLevelItem(current)

    def _build_custom_tab(self):
        """A hand-written prompt in, split and re-adaptable - the opposite
        direction from every other tab here, which only ever builds a prompt
        from the story bank. See ui/views/cats_custom.py.
        """
        self.custom_tab = CustomPromptTab(self.bank, self._palette)
        self.custom_tab.status.connect(self.status)
        self.custom_tab.custom_generate_requested.connect(self.custom_generate_requested)
        return self.custom_tab

    def _build_capcut_tab(self):
        self.sheet_box = QPlainTextEdit()
        self.sheet_box.setReadOnly(True)
        self.sheet_box.setProperty("class", "mono")
        # The sheet is aligned columns. Wrapping folded "ambience  empty room
        # tone humming quietly in the background" back to column zero and broke
        # the alignment that makes it scannable, so it scrolls sideways instead.
        self.sheet_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        copy_sheet = QPushButton("Copy the sheet")
        copy_sheet.setIcon(assets.icon("copy"))
        copy_sheet.setIconSize(assets.ICON_SIZE)
        copy_sheet.clicked.connect(self.copy_sheet)

        self.render_button = QPushButton("Render Video")
        self.render_button.setIcon(assets.icon("videos"))
        self.render_button.setIconSize(assets.ICON_SIZE)
        self.render_button.clicked.connect(self.request_render)
        self.render_status = MutedLabel("")

        # Labels in a scroll area rather than a two-column tree. Nine steps of
        # prose in a tree read "Import all of them at once and lay them e" -
        # a tree row is one line tall and clips, whatever setWordWrap says.
        #
        # Built empty here and filled by refresh_capcut_steps(): the assembly
        # steps are per FORMAT (a one-take gag has no hook to trim and no
        # caption to add), and the format is not known until the Story tab has
        # been touched, so this cannot be filled once at construction time.
        self.steps_body = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_body)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(T.SPACE["md"])
        self.steps_note = MutedLabel("")

        steps = QScrollArea()
        steps.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        steps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        steps.setFrameShape(QScrollArea.Shape.NoFrame)
        steps.setWidget(self.steps_body)

        sheet_card = Card()
        sheet_row = QHBoxLayout()
        sheet_row.addWidget(TitleLabel("Edit sheet"))
        sheet_row.addStretch(1)
        sheet_row.addWidget(copy_sheet)
        sheet_card.body.addLayout(sheet_row)
        sheet_card.body.addWidget(MutedLabel(
            "Built from this story: which clip, which seconds of it to keep, the "
            "caption, the three sound layers and the cut into the next scene."))
        sheet_card.body.addWidget(self.sheet_box, 1)
        # A second row rather than crowding the title row above: at the
        # minimum window width there is no room left there for a second
        # button without eliding both its and "Copy the sheet"'s text.
        render_row = QHBoxLayout()
        render_row.addWidget(self.render_button)
        render_row.addWidget(self.render_status, 1)
        sheet_card.body.addLayout(render_row)
        sheet_card.setMinimumWidth(380)

        steps_card = Card()
        steps_card.body.addWidget(TitleLabel("Assembling it"))
        steps_card.body.addWidget(self.steps_note)
        steps_card.body.addWidget(steps, 1)
        steps_card.setMinimumWidth(330)

        # The sheet is built from this story; the steps are a fixed reference.
        # An even vertical split gave the reference as much room as the thing
        # you actually work from, and left the sheet showing three lines.
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("cats_capcut_sheet_steps")
        split.addWidget(sheet_card)
        split.addWidget(steps_card)
        split.setChildrenCollapsible(False)
        split.setSizes([470, 370])
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(split)
        return page

    # -- the format ---------------------------------------------------------- #
    def format_key(self):
        return (self.format.currentData()
                or self.story_bank.get("default_format", bs.DEFAULT_FORMAT))

    def trade_key(self):
        return self.trade.currentData() if self.is_trade() else None

    def is_trade(self):
        return bs.scene_fields(self.story_bank, self.format_key()) == ["task", "mishap"]

    def is_sitcom(self):
        return self.format_key() == "sitcom"

    def cast_key(self):
        """The cast this format uses, or None for a format that has no casts."""
        if not self.ui_cfg().get("rows", {}).get("Cast"):
            return bs.default_cast(self.story_bank, self.format_key())
        return self.cast.currentData() or bs.default_cast(self.story_bank, self.format_key())

    def ui_cfg(self, fmt=None):
        """The format's own form description - which rows, what they are called.

        This used to be an `is_trade()` boolean read at five separate places.
        Two formats fit in a boolean; three do not, and every one of those
        branches would have had to be re-read as "trade, or sitcom, or both?"
        individually. The format declares its own form instead.
        """
        return bs.format_cfg(self.story_bank, fmt or self.format_key()).get("ui", {})

    def on_premise_picked(self):
        """A premise seed fills the Idea box. It is a starting point, not a script."""
        seed = self.premise.currentText()
        if self.premise.currentData() and seed:
            self.idea.setText(seed)
        self.refresh_social()

    def on_format_changed(self):
        """Switching format re-plans everything, because everything changes.

        The arcs belong to the format, so the list is rebuilt rather than
        filtered; the clip length follows the format's own default because a
        one-take gag runs about ten seconds and a narrative beat about five.
        """
        fmt = self.format_key()
        trade = self.is_trade()

        self.arc.blockSignals(True)
        self.arc.clear()
        for key, cfg in bs.arcs(self.story_bank, fmt).items():
            self.arc.addItem(cfg["label"], key)
            self.arc.setItemData(self.arc.count() - 1, cfg.get("note", ""),
                                 Qt.ItemDataRole.ToolTipRole)
        wanted = (bs.format_cfg(self.story_bank, fmt).get("default_arc")
                  or self.story_bank.get("default_arc", "classic"))
        index = self.arc.findData(wanted)
        self.arc.setCurrentIndex(max(0, index))
        self.arc.blockSignals(False)

        self.clip.blockSignals(True)
        self.clip.setValue(bs.default_clip(self.story_bank, fmt))
        self.clip.blockSignals(False)
        self.seconds.blockSignals(True)
        self.seconds.setValue(bs.default_seconds(self.story_bank, fmt))
        self.seconds.blockSignals(False)

        ui = self.ui_cfg(fmt)
        for label, visible in ui.get("rows", {}).items():
            if label in self.form_rows:
                caption, widget = self.form_rows[label]
                caption.setVisible(bool(visible))
                widget.setVisible(bool(visible))
        caption, _ = self.form_rows["The cat"]
        caption.setText(ui.get("cast_label", "The cat"))
        self.subject.setPlaceholderText(ui.get("subject_placeholder", ""))
        self.script_box.setPlaceholderText(self.PLACEHOLDERS.get(fmt, self.STORY_PLACEHOLDER))
        self.script_help.setText(self.HELP.get(fmt, self.STORY_HELP))
        self.timeline.set_hook(bool(ui.get("show_hook", True)),
                               self.story_bank.get("hook_seconds", 3.0))
        self.refresh_capcut_steps(fmt)
        self.rebuild()

    def refresh_capcut_steps(self, fmt):
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        capcut = bs.capcut_cfg(self.story_bank, fmt)
        self.steps_note.setText(capcut.get("note", ""))
        for item in capcut.get("steps", []):
            heading = QLabel(item["step"])
            heading.setWordWrap(True)
            text = MutedLabel(item["text"])
            self.steps_layout.addWidget(heading)
            self.steps_layout.addWidget(text)
        self.steps_layout.addStretch(1)

    # -- state -------------------------------------------------------------- #
    def arc_key(self):
        return self.arc.currentData() or self.story_bank.get("default_arc", "classic")

    def style_key(self):
        """The look this format uses, or the bank's default when it hides the row.

        `trade` sets ui.rows.Look false, but this read the hidden combo anyway -
        so picking Stylised on `story` and then switching to `trade` kept
        generating stylised scenes with no visible control saying so, and no way
        to get back without switching format again. Same guard cast_key()
        already uses for the Cast row, for the same reason.
        """
        if not self.ui_cfg().get("rows", {}).get("Look"):
            return self.story_bank.get("default_style", "photoreal")
        return self.style.currentData() or self.story_bank.get("default_style", "photoreal")

    def clip_length(self):
        return int(self.clip.value())

    def _cast_supplies_subject(self):
        """True when the active cast has its own subject to fill the blank with.

        Only sitcom's casts declare one today. Checked rather than assumed, so
        this stays correct if story or trade ever gain a cast of their own.
        """
        return bool(bs.casts(self.story_bank).get(self.cast_key() or "", {}).get("subject"))

    def base_spec(self):
        spec = {"seed": 0}
        subject = self.subject.text().strip()
        if subject:
            spec["subject"] = subject
        elif not self._cast_supplies_subject():
            # A REAL bug this line exists to avoid repeating: apply_cast() in
            # build_story.py only fills spec["subject"] when the key is absent
            # or falsy - "a cat" is neither, so setting it unconditionally here
            # meant the whole cast mechanism was dead through the GUI. Leaving
            # the key unset when a cast can supply it lets apply_cast do its
            # job; every other format keeps its old "a cat" fallback exactly
            # as before, since none of their casts declare a subject.
            spec["subject"] = "a cat"
        if self.setting.text().strip():
            spec["setting"] = self.setting.text().strip()
        return spec

    @staticmethod
    def parse_script(text):
        """[hook] blocks of `field: value` lines -> {key: {field: value}}.

        One parser for every format: it accepts any field a format asks for and
        ignores the rest, so switching format does not need a second parser.
        """
        script, current = {}, None
        for raw in (text or "").splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip().lower()
                script.setdefault(current, {})
                continue
            if current and ":" in line:
                field, _, value = line.partition(":")
                field = field.strip().lower()
                if field in SCRIPT_FIELDS and value.strip():
                    script[current][field] = value.strip()
        return {k: v for k, v in script.items() if v}

    def set_script(self, script):
        """Fill the box from a dict without re-triggering a parse storm."""
        blocks = []
        wanted = bs.scene_fields(self.story_bank, self.format_key())
        for key in self.scene_keys():
            fields = script.get(key, {})
            blocks.append("[{}]".format(key))
            for field in wanted:
                blocks.append("{}: {}".format(field, fields.get(field, "")))
            blocks.append("")
        self.script_box.blockSignals(True)
        self.script_box.setPlainText("\n".join(blocks).rstrip() + "\n")
        self.script_box.blockSignals(False)
        self.script = dict(script)
        self.rebuild()

    def scene_keys(self):
        # build_story owns this list: the scene count comes from the runtime, so
        # a local copy derived from the arc alone would leave scenes wordless.
        return bs.scene_keys(self.story_bank, self.arc_key(), self.seconds.value(),
                             self.clip_length(), self.format_key())

    def on_script_edited(self):
        self.script = self.parse_script(self.script_box.toPlainText())
        self.rebuild()

    # -- the gate ----------------------------------------------------------- #
    def rebuild(self):
        if not hasattr(self, "scene_tree"):
            return
        arc, seconds = self.arc_key(), self.seconds.value()
        fmt = self.format_key()
        self.scenes = bs.compose_story(
            self.story_bank, self.base_spec(), arc=arc, seconds=seconds,
            clip_length=self.clip_length(), style=self.style_key(),
            script=self.script, reference="scene-1.png", image_bank=self.bank,
            fmt=fmt, trade=self.trade_key(), cast=self.cast_key())

        # A hand edit in custom_motion is tagged with the scene KEY it was
        # made for (_build_motion_card_section). Arc/cast/trade/style/format
        # all rebuild here too, and any of them can reshuffle which beat
        # lands on which index - so an edit typed for "the meltdown" must not
        # silently relabel whatever beat now sits at that same index. Prune
        # here, once, rather than in every reader of custom_motion (the
        # motion-prompt card, the audio-cue overrides, the voiceover text).
        for index in list(self.custom_motion):
            current = self.scenes[index].get("key") if index < len(self.scenes) else None
            if self.custom_motion[index].get("_scene_key") != current:
                del self.custom_motion[index]

        cfg = bs.arcs(self.story_bank, fmt).get(arc, {})
        self.arc_note.setText("{}  -  {}".format(cfg.get("label", arc), cfg.get("note", "")))

        self.scene_tree.clear()
        for index, scene in enumerate(self.scenes):
            item = QTreeWidgetItem(self.scene_tree, [
                str(scene["n"]),
                scene["label"],
                "{}s".format(scene["clip_seconds"]),
                "{:.1f}s".format(scene["edit_seconds"]),
                scene["caption"] or scene["spec"].get("action") or scene["role"],
                self.status_by_scene.get(index, ""),
            ])
            if not scene["caption"]:
                item.setForeground(4, QColor(self._palette.get("text_muted", "#94A3B8")))
            item.setToolTip(4, "{}\n\nmove: {}\nnarration: {}".format(
                scene["must_do"], scene["movement"] or "none",
                scene["narration"] or "(none)"))
            # Editing the script re-plans the story and rebuilds these rows, so
            # an already-generated still has to be put back or it would appear
            # to have been lost.
            path = self.images.get(index)
            if path and Path(path).exists():
                item.setIcon(1, QIcon(path))
                item.setToolTip(1, path)
        for column, width in ((0, 24), (1, 92), (2, 44), (3, 46)):
            self.scene_tree.setColumnWidth(column, width)
        self.scene_tree.setColumnWidth(5, 62)

        self.timeline.set_story(
            self.scenes, float(self.story_bank.get("hook_seconds", 3.0)))
        generated = sum(s["clip_seconds"] for s in self.scenes)
        kept = round(sum(s["edit_seconds"] for s in self.scenes), 1)
        note, ratio = stl.cost_note(self.scenes)
        self.timing_label.setText(
            "Top bar: {}s of clip you generate. Bottom bar: the {:.0f}s that survives "
            "the cut. {}".format(generated, kept, note))

        results = stl.lint(self.story_bank, self.scenes, arc, seconds,
                           image_bank=self.bank, clip_length=self.clip_length(),
                           fmt=fmt)
        got, total = stl.score(results)
        failing = sum(1 for _, _, passed, _ in results if not passed)
        # One failure shown at a time, not all of them: three stacked sentences
        # grew the old fix_label past the height of the tree above it. GateTree
        # auto-selects the first failing row and shows just its reason; picking
        # another row shows that one's instead - the rest are a click away.
        self.gate.set_checks([
            {
                "key": key, "label": label, "passed": passed,
                "fix": "To fix - {}: {}".format(label, detail) + (
                    "  (+{} more - pick another row for its reason)".format(failing - 1)
                    if failing > 1 else ""),
                "ok_text": "Every check passes. The story is ready to generate.",
            }
            for key, label, passed, detail in results
        ])
        self.lint_badge.set_status("success" if got == total else "danger",
                                   "{}/{}".format(got, total))
        self.passing = got == total

        # On the button rather than in the card. It is a standing explanation,
        # not a changing result, and the gate card ran out of room for both it
        # and the video options - the layout gate said so.
        self.generate_button.setToolTip(
            "Scene 1 creates the cat; every later scene locks to that face. "
            "Reference images are Kie-only, so on another provider these would "
            "be {} different cats.".format(len(self.scenes)))

        self.refresh_sheet()
        self.update_cost_note()
        self.story_changed.emit()

    def refresh_sheet(self):
        if not hasattr(self, "sheet_box"):
            return
        # story_sound's subject defaulted to the literal string "the cat" -
        # right for a single-cat story, but the sheet said "the cat shovelling
        # cement" over a two-cat scene. The real subject is on every scene's
        # own spec, so use it rather than the placeholder.
        sheets = bsd.story_sound(self.sound_bank, self.scenes, subject=self._sound_subject(),
                                 key_overrides=self._audio_cue_overrides(),
                                 extra_for=self._extra_sound_layers)
        self.sheet_box.setPlainText(
            bs.edit_sheet_text(self.story_bank, self.scenes, sheets))
        self.refresh_social()

    def copy_sheet(self):
        text = self.sheet_box.toPlainText()
        if not text.strip():
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Edit sheet copied")

    # -- the post ----------------------------------------------------------- #
    def _build_social_tab(self):
        """Titles, a caption and hashtags for the finished episode.

        The only tab here whose output goes to a platform rather than to a
        model. Composed deterministically by build_social and gated by
        social_lint, shown with the same GateTree every other gate in this app
        uses, so a failing pack looks like a failing prompt rather than like a
        different kind of thing.
        """
        self.social_box = QPlainTextEdit()
        self.social_box.setReadOnly(True)
        self.social_box.setProperty("class", "mono")

        self.social_gate = GateTree()
        self.social_note = MutedLabel("")
        self.social_note.setWordWrap(True)

        copy_all = QPushButton("Copy the post")
        copy_all.setIcon(assets.icon("copy"))
        copy_all.setIconSize(assets.ICON_SIZE)
        copy_all.clicked.connect(self.copy_social)

        copy_tags = QPushButton("Copy hashtags only")
        copy_tags.setIcon(assets.icon("copy"))
        copy_tags.setIconSize(assets.ICON_SIZE)
        copy_tags.clicked.connect(self.copy_hashtags)

        card = Card()
        card.body.addWidget(TitleLabel("The post"))
        card.body.addWidget(MutedLabel(
            "Composed from the premise and the episode's own captions - no model "
            "involved, and gated like everything else here."))
        card.body.addWidget(self.social_box, 1)
        row = QHBoxLayout()
        row.addWidget(copy_all)
        row.addWidget(copy_tags)
        row.addStretch(1)
        card.body.addLayout(row)
        card.body.addWidget(self.social_gate)
        card.body.addWidget(self.social_note)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        return page

    def social_pack(self):
        """The pack for the current episode, or None when there is nothing yet."""
        premise = (self.idea.text() or "").strip()
        if not premise and self.scenes:
            premise = (self.scenes[0].get("caption") or "").strip()
        if not premise:
            return None
        captions = [s.get("caption", "") for s in self.scenes]
        # The picked premise carries its own hand-written short form; a
        # premise typed by hand falls back to build_social deriving one.
        short = bs.premise_short(self.story_bank, self.premise.currentData())
        return bsoc.compose_social(self.social_bank, premise, captions, short=short or None)

    def refresh_social(self):
        if not hasattr(self, "social_box"):
            return
        pack = self.social_pack()
        if pack is None:
            self.social_box.setPlainText("")
            self.social_gate.set_checks([])
            self.social_note.setText(
                "Type an idea (or pick a premise) on the Story tab and this fills in.")
            return
        self.social_box.setPlainText(bsoc.social_text(pack))
        results = socl.lint(self.social_bank, pack)
        self.social_gate.set_checks([
            {"key": key, "label": label, "passed": passed,
             "fix": "To fix - {}: {}".format(label, detail),
             "ok_text": "The post passes every check."}
            for key, label, passed, detail in results])
        conflict = self.social_bank.get("hashtag_conflict", {})
        self.social_note.setText(
            "{} hashtags, per the series brief. This app's own course notes disagree: "
            "\"{}\" ({})".format(len(pack["hashtags"]), conflict.get("course_advice", ""),
                                 conflict.get("course_source", "")))

    def copy_social(self):
        text = self.social_box.toPlainText()
        if not text.strip():
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Post copied")

    def copy_hashtags(self):
        pack = self.social_pack()
        if not pack:
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(" ".join(pack["hashtags"]))
        self.status.emit("{} hashtags copied".format(len(pack["hashtags"])))

    # -- the optional text model -------------------------------------------- #
    def write_story(self):
        """Cast the cat, then write every scene - blanks only, then gated.

        One button rather than two. Whatever is already typed in survives and
        becomes part of the brief; only the empty fields are invented.
        """
        idea = self.idea.text().strip()
        if not idea:
            self.status.emit("Say what the story is about first")
            return
        self.write_badge.thinking()
        self.write_button.setEnabled(False)
        task = LlmTask("autofill_story", self.story_bank, self.bank, idea,
                       self.base_spec(), self.arc_key(), self.style_key(),
                       self.seconds.value(), self.clip_length(), None,
                       self.format_key(), self.trade_key(), self.cast_key())
        task.signals.finished.connect(self.on_written)
        task.signals.failed.connect(self.on_write_failed)
        task.signals.done.connect(lambda _a: self.write_button.setEnabled(True))
        self.pool.start(task)

    def on_written(self, _action, result):
        # The cast comes back first and goes into the boxes he can see and edit,
        # rather than living invisibly inside the spec.
        cast = result.get("cast") or {}
        for key, widget in (("subject", self.subject), ("setting", self.setting)):
            if cast.get(key) and not widget.text().strip():
                widget.blockSignals(True)
                widget.setText(cast[key])
                widget.blockSignals(False)
        script = result.get("script") or {}
        if script:
            self.set_script(script)
        elif cast:
            self.rebuild()
        if result.get("accepted"):
            self.write_badge.set_status("success", "accepted {}/{}".format(
                result.get("score"), result.get("total")))
            self.status.emit("Story accepted - it passed the gate")
        else:
            # Shown, not discarded: a near miss is a useful draft and the failing
            # rows say exactly what to change.
            self.write_badge.set_status("warning", "{}/{}".format(
                result.get("score"), result.get("total")))
            self.status.emit(result.get("reason", "The story did not pass")[:160])

    def on_write_failed(self, _action, reason):
        self.write_badge.set_status("danger", "failed")
        self.status.emit(reason[:160])

    # -- generation ---------------------------------------------------------- #
    def request_generate(self):
        if not self.scenes:
            self.status.emit("Nothing to generate yet")
            return
        self.images = {}
        self.entries = {}
        jobs = []
        for index, scene in enumerate(self.scenes):
            # Logged before the request goes out, so a scene that fails is still
            # a recorded experiment rather than a gap. `rate` attaches the file
            # when it arrives.
            entry_id = hist.append(scene["spec"], scene["prompt"], scene["layers"],
                                   scene.get("score", 0), bool(scene.get("passed")),
                                   detailed=False)
            self.entries[index] = entry_id
            jobs.append({
                "index": index,
                "prompt": scene["prompt"],
                "beat": scene["key"],
                "out_name": "story-{}-{}-{}.png".format(
                    scene["n"], scene["beat"], entry_id[-6:]),
                # Carries the aspect into the request body; the story bank says
                # 9:16 and nothing was sending it.
                "spec": scene["spec"],
            })
            self._set_scene_status(index, "queued…")
        # No success message here: whether these are queued or refused is the
        # controller's call, and an optimistic message would overwrite its answer.
        self.generate_requested.emit(jobs)

    def video_options(self):
        return {"mode": self.video_mode.currentData() or "std",
                "sound": self.video_sound.isChecked()}

    def update_cost_note(self):
        """What the clips would cost, before the button is pressed."""
        if not hasattr(self, "cost_note"):
            return
        seconds = sum(s["clip_seconds"] for s in self.scenes)
        note = gv.price_note(bs.DEFAULT_VIDEO_MODEL, seconds, **self.video_options())
        self.cost_note.setText("{} clips · {}s of video · {}".format(
            len(self.scenes), seconds, note))

    def request_videos(self):
        """One clip per scene, from that scene's still."""
        if not self.scenes:
            self.status.emit("Nothing to generate yet")
            return
        missing = [s["n"] for i, s in enumerate(self.scenes) if not self.images.get(i)]
        if missing:
            # Text-to-video would work, but every clip would invent its own cat.
            # Refused rather than quietly producing a different animal per scene,
            # which is the same rule the still sequence follows.
            self.status.emit(
                "Generate the stills first - scenes {} have no image, and a clip "
                "without one invents its own cat.".format(
                    ", ".join(str(n) for n in missing[:6])))
            return
        jobs = [{"index": i, "prompt": scene["motion_prompt"] or scene["prompt"],
                 "image": self.images.get(i),
                 "duration": scene["clip_seconds"],
                 "out_name": "story-{}-{}.mp4".format(scene["n"], scene["beat"])}
                for i, scene in enumerate(self.scenes)]
        self.video_requested.emit(jobs, self.video_options())

    def on_video_finished(self, index, path):
        self.videos[index] = str(path)
        self._set_scene_status(index, "clip ready")

    def on_video_failed(self, index, reason):
        self._set_scene_status(index, "clip failed")
        self.status.emit(reason[:160])

    # -- render --------------------------------------------------------------- #
    def request_render(self):
        """Concatenate every scene's clip (plus its voiceover and any
        generated SFX layers) into one exported .mp4 - the in-app alternative
        to the manual CapCut pass."""
        if not self.scenes:
            self.status.emit("Nothing to render yet")
            return
        missing = [s["n"] for i, s in enumerate(self.scenes) if not self.videos.get(i)]
        if missing:
            self.status.emit(
                "Generate the clips first - scenes {} have no video.".format(
                    ", ".join(str(n) for n in missing[:6])))
            return
        scenes_payload = [
            {"clip_path": self.videos[i], "voice_path": self.voiceovers.get(i),
             "sfx_paths": list(self.sfx.get(i, {}).values()),
             "duration": scene["clip_seconds"]}
            for i, scene in enumerate(self.scenes)
        ]
        aspect = (self.scenes[0]["spec"].get("aspect") if self.scenes else None) or "9:16"
        slug = bp.slugify(self.base_spec().get("slug")
                          or self.base_spec().get("subject", "cat"))
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        out_path = rv.OUT_DIR / "{}-{}.mp4".format(slug, stamp)

        self.render_button.setEnabled(False)
        self.render_status.setText("Rendering...")
        task = RenderTask(scenes_payload, out_path, aspect_ratio=aspect)
        task.signals.stage.connect(self._on_render_stage)
        task.signals.finished.connect(self._on_render_finished)
        task.signals.failed.connect(self._on_render_failed)
        task.signals.done.connect(lambda: self.render_button.setEnabled(True))
        self.pool.start(task)

    def _on_render_stage(self, message):
        self.render_status.setText(message)

    def _on_render_finished(self, path):
        self.render_status.setText("Saved: {}".format(path))
        self.status.emit("Video rendered")

    def _on_render_failed(self, reason):
        self.render_status.setText(reason[:200])
        self.status.emit(reason[:160])

    # -- batch feedback ------------------------------------------------------ #
    # The controller calls these. They used to not exist: every story result was
    # handed to the Images/Variants grid, which drops any index it has no tile
    # for, so a generated story disappeared without an error anywhere.
    def set_busy(self, busy, total=0):
        self.generate_button.setEnabled(not busy and bool(self.scenes))
        self.write_button.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, total)
            self.progress.setValue(0)

    def set_progress(self, completed, total):
        self.progress.setRange(0, total)
        self.progress.setValue(completed)

    def on_item_finished(self, index, path):
        self.images[index] = str(path)
        self._set_scene_status(index, "ready")
        item = self.scene_tree.topLevelItem(index)
        if item is not None:
            item.setIcon(1, QIcon(str(path)))
        entry_id = self.entries.get(index)
        if entry_id:
            hist.rate(entry_id, None, image=str(path))
        if self.tabs.currentIndex() == self.PROMPTS_TAB:
            self.rebuild_prompts()

    def on_item_failed(self, index, reason):
        self._set_scene_status(index, "failed")
        item = self.scene_tree.topLevelItem(index)
        if item is not None:
            item.setToolTip(0, reason)
        self.status.emit(reason[:160])

    def _set_scene_status(self, index, text):
        self.status_by_scene[index] = text
        item = self.scene_tree.topLevelItem(index)
        if item is not None:
            item.setText(5, text)

    # -- theming -------------------------------------------------------------- #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.timeline.set_palette_tokens(palette)
        self.gate.set_palette_tokens(self._palette)
        self.custom_tab.set_palette_tokens(self._palette)
        self.rebuild()

    def refresh(self):
        self.rebuild()
