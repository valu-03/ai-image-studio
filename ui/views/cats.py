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
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

import build_sound as bsd  # noqa: E402
import build_story as bs  # noqa: E402
import generate_video as gv  # noqa: E402
import history as hist  # noqa: E402
import story_lint as stl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Badge, Card, GateTree, MutedLabel, TitleLabel  # noqa: E402
from ..workers import LlmTask  # noqa: E402
from .cats_custom import CustomPromptTab  # noqa: E402

# Every field any format asks for. The parser accepts them all and each format
# takes what it wants, rather than there being one parser per format.
SCRIPT_FIELDS = {"caption", "narration", "action", "setting", "task", "mishap"}


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
        self._palette = palette or {}
        self.scenes = []
        self.script = {}
        self.passing = False
        self.images = {}            # scene index -> generated still
        self.videos = {}            # scene index -> generated clip
        self.entries = {}           # scene index -> history entry id
        self.status_by_scene = {}
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

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_story_tab(), "Story")
        self.tabs.addTab(self._build_scenes_tab(), "Scenes")
        self.tabs.addTab(self._build_prompts_tab(), "Prompts")
        self.tabs.addTab(self._build_custom_tab(), "Custom Prompt")
        self.tabs.addTab(self._build_capcut_tab(), "CapCut")
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
        for label, widget in [("Format", self.format), ("Idea", self.idea),
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
        script_card.setMinimumWidth(330)

        # Seven labelled rows and a scene-by-scene script both want the whole
        # height of the tab. Stacked, they asked for 700px of a 537px page, and
        # Qt resolves that by violating both minimums - which is how every field
        # ended up 9px tall with its text sliced through the middle. Side by
        # side they each get the full height, and the width is there for it.
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_scroll.setWidget(form)
        # The scroll area is the belt to the splitter's braces: on a short window
        # the form scrolls rather than crushing its own rows again.
        form_scroll.setMinimumWidth(320)
        form_scroll.setMaximumWidth(430)

        split = QSplitter(Qt.Orientation.Horizontal)
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
        gate.setMinimumWidth(300)

        # Side by side, not stacked. Nine scenes and twelve checks are both
        # lists, and stacking them split 537px of page between two things that
        # each wanted 400 - so both sat on their 76px floor showing exactly one
        # row, which is worse than useless for a checklist. Across, each gets
        # the full height, and the splitter still lets you favour one.
        split = QSplitter(Qt.Orientation.Horizontal)
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

            for label, text, empty in (
                    ("Still prompt", scene["prompt"], ""),
                    ("Video prompt ({})".format(scene["movement"] or "no move"),
                     scene["motion_prompt"],
                     "This beat has no camera move, so there is no video prompt.")):
                row = QHBoxLayout()
                row.addWidget(MutedLabel(label), 1)
                button = QPushButton("Copy")
                button.setProperty("class", "ghost")
                button.clicked.connect(
                    lambda _=False, value=text: self.copy_text(value))
                button.setEnabled(bool(text))
                row.addWidget(button)
                card.body.addLayout(row)

                box = QPlainTextEdit(text or empty)
                box.setReadOnly(True)
                box.setProperty("class", "mono")
                box.setFixedHeight(84 if text else 40)
                card.body.addWidget(box)

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
        steps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        for label, visible in (("Job", trade), ("Look", not trade)):
            caption, widget = self.form_rows[label]
            caption.setVisible(visible)
            widget.setVisible(visible)
        caption, _ = self.form_rows["The cat"]
        caption.setText("The cats" if trade else "The cat")
        self.subject.setPlaceholderText(
            "two cats - a broad grey tabby and a lean ginger tom" if trade
            else "a ginger tabby cat with one torn ear")
        self.script_box.setPlaceholderText(
            self.TRADE_PLACEHOLDER if trade else self.STORY_PLACEHOLDER)
        self.script_help.setText(self.TRADE_HELP if trade else self.STORY_HELP)
        self.timeline.set_hook(not trade, self.story_bank.get("hook_seconds", 3.0))
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
        return self.style.currentData() or self.story_bank.get("default_style", "photoreal")

    def clip_length(self):
        return int(self.clip.value())

    def base_spec(self):
        spec = {"seed": 0}
        if self.subject.text().strip():
            spec["subject"] = self.subject.text().strip()
        else:
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
            fmt=fmt, trade=self.trade_key())

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
        subject = (self.scenes[0]["spec"].get("subject") if self.scenes else None) or "the cat"
        sheets = bsd.story_sound(self.sound_bank, self.scenes, subject=subject)
        self.sheet_box.setPlainText(
            bs.edit_sheet_text(self.story_bank, self.scenes, sheets))

    def copy_sheet(self):
        text = self.sheet_box.toPlainText()
        if not text.strip():
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Edit sheet copied")

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
                       self.format_key(), self.trade_key())
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
