"""Sound category - ElevenLabs sound-effect prompts.

  Library   the course's 100 example prompts, by theme
  Compose   build one prompt and score it
  Scenes    the three-layer sheet for the story open in the Cats tab

The three layers are the part that matters. One effect on its own sounds like a
sound effect; ambience under a key effect under an accent sounds like a place.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QThreadPool, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402  (slugify - for naming generated audio files)
import build_sound as bsd  # noqa: E402
import elevenlabs_voices as voices_tool  # noqa: E402
import generate_image as gi  # noqa: E402  (key-presence check only)
import generate_sound as gsnd  # noqa: E402
import generate_speech as gspeech  # noqa: E402
import sound_lint as sl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..hints import NAV_HINTS
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402
from ..workers import SoundTask, SpeechTask, VoiceCloneTask, VoiceListTask  # noqa: E402


class SoundView(QWidget):
    """Emits `status`; reads the current story through `context`."""

    status = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bsd.load_bank()
        self._palette = palette or {}
        self.context = None          # set by the controller: () -> [scene dicts]
        # Real ElevenLabs generation is entirely local to this view - unlike
        # Compose/Ads/Cats generation, it needs no shared spec, provider or
        # credits state from MainWindow, so it owns its own small pool rather
        # than routing through one there. Same "an occasional single call, not
        # a batch of parallel jobs" reasoning as RefineTask/CreditsTask.
        self._audio_pool = QThreadPool(self)
        self._audio_pool.setMaxThreadCount(2)
        self._last_effect_path = None
        self._last_speech_path = None
        self._sheet_queue = []
        self._sheet_total = 0
        self._sheet_done = 0
        self._sample_paths = []
        self.setup_ui()
        self.reload_library()
        self.rebuild_compose()
        self.rebuild()
        self.refresh_voices()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_compose_tab(), "Compose")
        self.tabs.addTab(self._build_scenes_tab(), "Scenes")
        self.tabs.addTab(self._build_voices_tab(), "Voices")

        layout = QVBoxLayout(self)
        # The section says what it is for. Seven of the ten rail sections
        # said nothing at all; the sentence is ui/hints.py's, the same one
        # the rail tooltip and the Go menu use, so the three cannot drift.
        layout.addWidget(MutedLabel(NAV_HINTS["sound"]))
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _key_present(self):
        return bool(gi.env_value(gsnd.KEY_VAR))

    def _build_library_tab(self):
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the 100 examples…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload_library)

        self.theme_filter = QComboBox()
        self.theme_filter.addItem("Every theme", "")
        for key, cfg in sl.themes(self.bank).items():
            self.theme_filter.addItem(cfg["label"], key)
            self.theme_filter.setItemData(
                self.theme_filter.count() - 1, cfg["note"], Qt.ItemDataRole.ToolTipRole)
        self.theme_filter.currentIndexChanged.connect(self.reload_library)

        self.library = QTreeWidget()
        self.library.setColumnCount(2)
        self.library.setHeaderLabels(["#", "PROMPT"])
        self.library.setRootIsDecorated(True)
        self.library.setAlternatingRowColors(True)
        self.library.itemDoubleClicked.connect(self.copy_example)

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(lambda: self.copy_example(self.library.currentItem()))

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(self.search, 1)
        row.addWidget(self.theme_filter)
        row.addWidget(copy_button)

        card = Card()
        card.body.addWidget(TitleLabel("100 example prompts"))
        card.body.addWidget(MutedLabel(
            "Verbatim from the course. Double-click to copy one. They are also this "
            "section's test fixture: if the linter ever rejects one of these, the "
            "linter is wrong about it, not the other way round."))
        card.body.addLayout(row)
        card.body.addWidget(self.library, 1)
        return self._wrap(card)

    def _build_compose_tab(self):
        self.source = QLineEdit(placeholderText="torch flame")
        self.action = QLineEdit(placeholderText="crackling")
        self.place = QLineEdit(placeholderText="a temple hallway")
        self.treatment = QLineEdit(placeholderText="comedic echo")
        for field in (self.source, self.action, self.place, self.treatment):
            field.textChanged.connect(self.rebuild_compose)

        self.composed = QLineEdit()
        self.composed.setReadOnly(True)
        self.composed.setProperty("class", "mono")
        self.composed.setPlaceholderText(
            "Source + Action build the prompt - Where and How refine it")

        self.compose_badge = Badge("0/4", "neutral")
        self.compose_tree = QTreeWidget()
        self.compose_tree.setColumnCount(3)
        self.compose_tree.setHeaderLabels(["", "CHECK", "DETAIL"])
        self.compose_tree.setRootIsDecorated(False)
        self.compose_tree.setAlternatingRowColors(True)
        self.compose_tree.setMaximumHeight(160)

        self.compose_advice = MutedLabel("")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        # Real generation, next to the copy-to-clipboard path that already
        # existed - never replacing it, since a missing key must still leave
        # the prompt usable by hand.
        self.generate_effect_button = QPushButton("Generate")
        self.generate_effect_button.setIcon(assets.icon("generate"))
        self.generate_effect_button.setIconSize(assets.ICON_SIZE)
        self.generate_effect_button.setToolTip(
            "Send this to ElevenLabs and get back a real sound-effect file.")
        self.generate_effect_button.clicked.connect(self.generate_composed_effect)

        self.effect_play_button = QPushButton("Play")
        self.effect_play_button.setProperty("class", "ghost")
        self.effect_play_button.clicked.connect(
            lambda: self._play(self._last_effect_path))
        self.effect_play_button.setEnabled(False)

        self.effect_open_button = QPushButton("Open folder")
        self.effect_open_button.setProperty("class", "ghost")
        self.effect_open_button.clicked.connect(lambda: self._open_folder(assets.SOUND_DIR))

        self.effect_status = MutedLabel("")

        form = Card()
        form.body.addWidget(TitleLabel("Build one"))
        form.body.addWidget(MutedLabel(self.bank.get("pattern", {}).get("shape", "")))
        for label, widget in [("Source", self.source), ("Action", self.action),
                              ("Where", self.place), ("How", self.treatment)]:
            line = QHBoxLayout()
            caption = QLabel(label)
            caption.setMinimumWidth(70)
            line.addWidget(caption)
            line.addWidget(widget, 1)
            form.body.addLayout(line)

        out_row = QHBoxLayout()
        out_row.addWidget(self.composed, 1)
        out_row.addWidget(copy_button)
        form.body.addLayout(out_row)

        generate_row = QHBoxLayout()
        generate_row.setSpacing(T.SPACE["sm"])
        generate_row.addWidget(self.generate_effect_button)
        generate_row.addWidget(self.effect_play_button)
        generate_row.addWidget(self.effect_open_button)
        generate_row.addStretch(1)
        form.body.addLayout(generate_row)
        form.body.addWidget(self.effect_status)

        gate = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Will this work?"))
        header.addWidget(self.compose_badge)
        header.addStretch(1)
        gate.body.addLayout(header)
        gate.body.addWidget(self.compose_tree)
        gate.body.addWidget(self.compose_advice)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(form)
        layout.addWidget(gate, 1)
        return self._scrolled(body)

    def _build_scenes_tab(self):
        self.theme_for_scenes = QComboBox()
        for key, cfg in sl.themes(self.bank).items():
            self.theme_for_scenes.addItem(cfg["label"], key)
        index = self.theme_for_scenes.findData("comedy")
        if index >= 0:
            self.theme_for_scenes.setCurrentIndex(index)
        self.theme_for_scenes.currentIndexChanged.connect(self.rebuild)

        self.scene_tree = QTreeWidget()
        self.scene_tree.setColumnCount(3)
        self.scene_tree.setHeaderLabels(["SCENE", "LAYER", "PROMPT"])
        self.scene_tree.setAlternatingRowColors(True)

        copy_all = QPushButton("Copy the whole sheet")
        copy_all.setIcon(assets.icon("copy"))
        copy_all.setIconSize(assets.ICON_SIZE)
        copy_all.clicked.connect(self.copy_sheet)

        self.generate_sheet_button = QPushButton("Generate all sounds")
        self.generate_sheet_button.setToolTip(
            "Sends every passing layer in this sheet to ElevenLabs, one at a time.")
        self.generate_sheet_button.clicked.connect(self.generate_sheet_sounds)

        row = QHBoxLayout()
        row.setSpacing(T.SPACE["sm"])
        row.addWidget(QLabel("Accent theme"))
        row.addWidget(self.theme_for_scenes)
        row.addStretch(1)
        row.addWidget(copy_all)
        row.addWidget(self.generate_sheet_button)

        self.scene_note = MutedLabel("")
        self.sheet_progress = MutedLabel("")

        card = Card()
        card.body.addWidget(TitleLabel("Sound for the open story"))
        card.body.addWidget(MutedLabel(
            "Three layers per scene. Ambience runs under everything and should never "
            "be noticed; the key effect lands on the frame where the action happens; "
            "the accent punctuates the cut. Never two accents in one scene."))
        card.body.addLayout(row)
        card.body.addWidget(self.scene_note)
        card.body.addWidget(self.sheet_progress)
        card.body.addWidget(self.scene_tree, 1)
        return self._wrap(card)

    def _wrap(self, card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)
        return self._scrolled(page)

    def _scrolled(self, widget):
        """A resizable QScrollArea never shrinks its content below that
        content's own minimum - with the bar off it clips silently instead.
        AsNeeded, never Off - see CLAUDE.md; Compose's result card lost 274px
        of every button this way. Every tab in this view added real rows on
        top of what test_layout.py had already verified fit exactly at the
        1100x700 floor, so each one gets this same safety net Settings
        already uses for its own page of cards.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- library ----------------------------------------------------------- #
    def reload_library(self):
        needle = self.search.text().strip().lower()
        theme = self.theme_filter.currentData() or ""
        self.library.clear()
        shown = 0
        for key, cfg in sl.themes(self.bank).items():
            if theme and key != theme:
                continue
            rows = [e for e in sl.by_theme(self.bank, key)
                    if not needle or needle in e["text"].lower()]
            if not rows:
                continue
            parent = QTreeWidgetItem(self.library, ["", cfg["label"]])
            parent.setToolTip(1, cfg["note"])
            parent.setExpanded(True)
            for entry in rows:
                child = QTreeWidgetItem(parent, [str(entry["n"]), entry["text"]])
                child.setData(0, Qt.ItemDataRole.UserRole, entry["text"])
                shown += 1
        self.library.setColumnWidth(0, 44)
        self.library.setColumnWidth(1, 460)
        if needle or theme:
            self.status.emit("{} of 100 examples".format(shown))

    def copy_example(self, item=None):
        if item is None:
            self.status.emit("Pick an example first")
            return
        text = item.data(0, Qt.ItemDataRole.UserRole)
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    # -- compose ----------------------------------------------------------- #
    def rebuild_compose(self):
        if not hasattr(self, "compose_tree"):
            return
        source = self.source.text().strip()
        action = self.action.text().strip()
        if not source and not action:
            started = self.place.text().strip() or self.treatment.text().strip()
            self.composed.setText("")
            self.compose_tree.clear()
            self.compose_badge.set_status("neutral", "0/4")
            self.compose_advice.setText(
                "Fill in Source and Action - what makes the sound and what it is "
                "doing. Where and How are optional." if started else "")
            self.generate_effect_button.setEnabled(False)
            return

        text = bsd.compose(self.bank, source, action,
                           self.place.text().strip() or None,
                           self.treatment.text().strip() or None)
        self.composed.setText(text)

        results = sl.lint(self.bank, text)
        got, total = sl.score(results)
        self.compose_tree.clear()
        for _, label, passed, detail in results:
            row = QTreeWidgetItem(self.compose_tree, ["", label, detail])
            row.setText(0, "OK" if passed else "!")
            row.setForeground(0, QColor(self._palette.get(
                "success" if passed else "error", "#34D399" if passed else "#F87171")))
        self.compose_tree.setColumnWidth(0, 30)
        self.compose_tree.setColumnWidth(1, 180)
        self.compose_badge.set_status("success" if got == total else "danger",
                                      "{}/{}".format(got, total))
        notes = sl.advice(self.bank, text)
        self.compose_advice.setText(" ".join(notes))

        # Generation is gated the same way the badge already is: every prompt
        # passes the gate before it is handed onward, same rule realism_lint
        # enforces for images.
        passed = got == total
        self.generate_effect_button.setEnabled(passed)
        self.generate_effect_button.setToolTip(
            "Send this to ElevenLabs and get back a real sound-effect file."
            if passed else "Fix the failing checks above first - this prompt would be refused.")

    def copy_composed(self):
        text = self.composed.text().strip()
        if not text:
            self.status.emit("Nothing composed yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    # -- real generation ----------------------------------------------------- #
    def generate_composed_effect(self):
        text = self.composed.text().strip()
        if not text:
            self.status.emit("Nothing composed yet")
            return
        if not self._key_present():
            self.effect_status.setText(
                "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        self.generate_effect_button.setEnabled(False)
        self.effect_status.setText("Generating...")
        task = SoundTask(text)
        task.signals.finished.connect(self._on_effect_finished)
        task.signals.failed.connect(self._on_effect_failed)
        task.signals.stage.connect(self.effect_status.setText)
        self._audio_pool.start(task)

    def _on_effect_finished(self, path):
        self._last_effect_path = path
        self.effect_play_button.setEnabled(True)
        self.effect_status.setText("Saved: {}".format(path))
        self.generate_effect_button.setEnabled(True)
        self.status.emit("Sound effect generated")

    def _on_effect_failed(self, reason):
        self.effect_status.setText(reason)
        self.generate_effect_button.setEnabled(True)

    def _play(self, path):
        if not path:
            self.status.emit("Nothing generated yet")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_folder(self, path):
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- the story's sheet -------------------------------------------------- #
    def scenes(self):
        return list(self.context() or []) if self.context else []

    def sheets(self):
        theme = "comedy"
        if hasattr(self, "theme_for_scenes"):
            theme = self.theme_for_scenes.currentData() or "comedy"
        return bsd.story_sound(self.bank, self.scenes(), theme=theme)

    def rebuild(self):
        if not hasattr(self, "scene_tree"):
            return
        scenes = self.scenes()
        self.scene_tree.clear()
        if not scenes:
            self.scene_note.setText(
                "No story open. Build one in Cats, then come back - this sheet is "
                "generated from its scenes.")
            return

        sheets = self.sheets()
        failing = 0
        for sheet in sheets:
            parent = QTreeWidgetItem(
                self.scene_tree, ["{}. {}".format(sheet["n"], sheet["label"]), "", ""])
            parent.setExpanded(True)
            for layer in sheet["layers"]:
                child = QTreeWidgetItem(parent, ["", layer["label"], layer["text"]])
                child.setToolTip(1, "{}\n\n{}".format(layer["role"], layer["note"]))
                if not layer["passed"]:
                    failing += 1
                    child.setForeground(2, QColor(
                        self._palette.get("error", "#F87171")))
                    child.setToolTip(2, "; ".join(layer["failures"]))
        self.scene_tree.setColumnWidth(0, 150)
        self.scene_tree.setColumnWidth(1, 110)
        self.scene_note.setText(
            "{} scenes, {} prompts{}.".format(
                len(sheets), len(sheets) * 3,
                "" if not failing else " - {} need work".format(failing)))

    def copy_sheet(self):
        sheets = self.sheets()
        if not sheets:
            self.status.emit("No story open")
            return
        QGuiApplication.clipboard().setText(bsd.sheet_text(sheets))
        self.status.emit("Sound sheet copied - {} prompts".format(len(sheets) * 3))

    def generate_sheet_sounds(self):
        """Real audio for every passing layer, one ElevenLabs call at a time.

        A layer that fails sound_lint (shown red in the tree already) is
        skipped rather than forced - the same gate the Compose tab's own
        Generate button already respects.
        """
        sheets = self.sheets()
        if not sheets:
            self.status.emit("No story open")
            return
        if not self._key_present():
            self.sheet_progress.setText(
                "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        if self._sheet_queue:
            self.status.emit("Already generating this sheet")
            return

        slug = bp.slugify(self.scenes()[0].get("label", "story")) if self.scenes() else "story"
        queue = []
        for sheet in sheets:
            for layer in sheet["layers"]:
                if not layer["passed"]:
                    continue
                out_name = "sfx-{}-{}-{}.mp3".format(slug, sheet["n"], layer["layer"])
                queue.append((layer["text"], out_name))
        if not queue:
            self.sheet_progress.setText("Nothing to generate - every layer needs work first.")
            return

        self._sheet_queue = queue
        self._sheet_total = len(queue)
        self._sheet_done = 0
        self.generate_sheet_button.setEnabled(False)
        self._advance_sheet_queue()

    def _advance_sheet_queue(self):
        if not self._sheet_queue:
            self.sheet_progress.setText(
                "Done - {} of {} sounds generated.".format(self._sheet_done, self._sheet_total))
            self.generate_sheet_button.setEnabled(True)
            self.status.emit("Sound sheet generated")
            return
        text, out_name = self._sheet_queue.pop(0)
        self.sheet_progress.setText("Generating {} of {}: {}".format(
            self._sheet_done + 1, self._sheet_total, out_name))
        task = SoundTask(text, out_name=out_name)
        task.signals.finished.connect(self._on_sheet_item_done)
        task.signals.failed.connect(self._on_sheet_item_failed)
        self._audio_pool.start(task)

    def _on_sheet_item_done(self, _path):
        self._sheet_done += 1
        self._advance_sheet_queue()

    def _on_sheet_item_failed(self, reason):
        self.sheet_progress.setText(reason)
        self._sheet_done += 1
        self._advance_sheet_queue()

    # -- voices: text-to-speech + cloning ------------------------------------ #
    def _build_voices_tab(self):
        self.tts_text = QLineEdit(placeholderText="Your hair gets greasy 5 hours after washing it.")
        self.tts_text.textChanged.connect(self._update_tts_cost)

        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(160)

        refresh_voices = QPushButton("Refresh")
        refresh_voices.setProperty("class", "ghost")
        refresh_voices.clicked.connect(self.refresh_voices)

        self.tts_cost_label = MutedLabel("")

        self.generate_speech_button = QPushButton("Generate")
        self.generate_speech_button.setIcon(assets.icon("generate"))
        self.generate_speech_button.setIconSize(assets.ICON_SIZE)
        self.generate_speech_button.clicked.connect(self.generate_tts)

        self.speech_play_button = QPushButton("Play")
        self.speech_play_button.setProperty("class", "ghost")
        self.speech_play_button.setEnabled(False)
        self.speech_play_button.clicked.connect(lambda: self._play(self._last_speech_path))

        self.speech_open_button = QPushButton("Open folder")
        self.speech_open_button.setProperty("class", "ghost")
        self.speech_open_button.clicked.connect(lambda: self._open_folder(assets.VOICE_DIR))

        self.speech_status = MutedLabel("")

        voice_row = QHBoxLayout()
        voice_row.setSpacing(T.SPACE["sm"])
        voice_row.addWidget(QLabel("Voice"))
        voice_row.addWidget(self.voice_combo, 1)
        voice_row.addWidget(refresh_voices)

        speech_row = QHBoxLayout()
        speech_row.setSpacing(T.SPACE["sm"])
        speech_row.addWidget(self.generate_speech_button)
        speech_row.addWidget(self.speech_play_button)
        speech_row.addWidget(self.speech_open_button)
        speech_row.addStretch(1)

        speak_card = Card()
        speak_card.body.addWidget(TitleLabel("Text to speech"))
        speak_card.body.addWidget(self.tts_text)
        speak_card.body.addLayout(voice_row)
        speak_card.body.addWidget(self.tts_cost_label)
        speak_card.body.addLayout(speech_row)
        speak_card.body.addWidget(self.speech_status)

        # -- clone a voice ---------------------------------------------------
        self.clone_name = QLineEdit(placeholderText="Narrator")
        self.clone_description = QLineEdit(placeholderText="Warm, calm, mid-30s (optional)")
        self.clone_samples_label = MutedLabel("No samples chosen yet")
        add_sample = QPushButton("Add sample...")
        add_sample.setProperty("class", "ghost")
        add_sample.clicked.connect(self.pick_samples)
        clear_samples = QPushButton("Clear")
        clear_samples.setProperty("class", "ghost")
        clear_samples.clicked.connect(self._clear_samples)

        self.consent_check = QCheckBox(
            "I have the right to clone this voice (it's mine, or I have explicit permission).")
        self.consent_check.stateChanged.connect(self._update_clone_enabled)
        self.clone_name.textChanged.connect(self._update_clone_enabled)

        self.clone_button = QPushButton("Clone voice")
        self.clone_button.setEnabled(False)
        self.clone_button.clicked.connect(self.clone_voice_clicked)

        self.clone_status = MutedLabel("")

        sample_row = QHBoxLayout()
        sample_row.setSpacing(T.SPACE["sm"])
        sample_row.addWidget(self.clone_samples_label, 1)
        sample_row.addWidget(add_sample)
        sample_row.addWidget(clear_samples)

        clone_card = Card()
        clone_card.body.addWidget(TitleLabel("Clone a voice"))
        clone_card.body.addWidget(MutedLabel(
            "1-3 short, clean audio samples of ONE speaker. Cloning a voice without the "
            "right to is the one real misuse risk here, so this is refused - by the tool "
            "itself, not only this checkbox - until the consent box below is checked."))
        clone_card.body.addWidget(self.clone_name)
        clone_card.body.addWidget(self.clone_description)
        clone_card.body.addLayout(sample_row)
        clone_card.body.addWidget(self.consent_check)
        clone_card.body.addWidget(self.clone_button)
        clone_card.body.addWidget(self.clone_status)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(speak_card)
        layout.addWidget(clone_card)
        layout.addStretch(1)
        return self._scrolled(page)

    def _update_tts_cost(self):
        characters, credits, confidence = gspeech.estimate_cost(self.tts_text.text())
        self.tts_cost_label.setText(
            "{} characters (~{} credits, {})".format(characters, credits, confidence)
            if characters else "")

    def refresh_voices(self):
        task = VoiceListTask()
        task.signals.finished.connect(self._on_voices_loaded)
        task.signals.failed.connect(lambda reason: self.speech_status.setText(reason))
        self._audio_pool.start(task)

    def _on_voices_loaded(self, voices):
        current = self.voice_combo.currentData()
        self.voice_combo.clear()
        for voice in voices:
            label = "{} ({})".format(voice["name"], voice["category"]) if voice["category"] \
                else voice["name"]
            self.voice_combo.addItem(label, voice["voice_id"])
        index = self.voice_combo.findData(current)
        if index >= 0:
            self.voice_combo.setCurrentIndex(index)

    def generate_tts(self):
        text = self.tts_text.text().strip()
        if not text:
            self.status.emit("Nothing to speak")
            return
        if not self._key_present():
            self.speech_status.setText(
                "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        voice_id = self.voice_combo.currentData()
        if not voice_id:
            self.speech_status.setText("Pick a voice first (Refresh if the list is empty).")
            return
        self.generate_speech_button.setEnabled(False)
        self.speech_status.setText("Generating...")
        task = SpeechTask(text, voice_id=voice_id)
        task.signals.finished.connect(self._on_speech_finished)
        task.signals.failed.connect(self._on_speech_failed)
        task.signals.stage.connect(self.speech_status.setText)
        self._audio_pool.start(task)

    def _on_speech_finished(self, path):
        self._last_speech_path = path
        self.speech_play_button.setEnabled(True)
        self.speech_status.setText("Saved: {}".format(path))
        self.generate_speech_button.setEnabled(True)
        self.status.emit("Speech generated")

    def _on_speech_failed(self, reason):
        self.speech_status.setText(reason)
        self.generate_speech_button.setEnabled(True)

    def pick_samples(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pick 1-3 audio samples", str(Path.home()),
            "Audio (*.wav *.mp3 *.m4a *.ogg *.flac)")
        if not paths:
            return
        self._sample_paths = (self._sample_paths + paths)[:3]
        self.clone_samples_label.setText(
            "{} sample(s): {}".format(
                len(self._sample_paths),
                ", ".join(Path(p).name for p in self._sample_paths)))
        self._update_clone_enabled()

    def _clear_samples(self):
        self._sample_paths = []
        self.clone_samples_label.setText("No samples chosen yet")
        self._update_clone_enabled()

    def _update_clone_enabled(self):
        self.clone_button.setEnabled(
            bool(self.clone_name.text().strip())
            and bool(self._sample_paths)
            and self.consent_check.isChecked())

    def clone_voice_clicked(self):
        if not self._key_present():
            self.clone_status.setText(
                "No {} set in .env - get one at {}".format(gsnd.KEY_VAR, gsnd.WHERE))
            return
        self.clone_button.setEnabled(False)
        self.clone_status.setText("Cloning...")
        task = VoiceCloneTask(
            self.clone_name.text().strip(), list(self._sample_paths),
            description=self.clone_description.text().strip() or None,
            consented=self.consent_check.isChecked())
        task.signals.finished.connect(self._on_clone_finished)
        task.signals.failed.connect(self._on_clone_failed)
        self._audio_pool.start(task)

    def _on_clone_finished(self, voice_id):
        self.clone_status.setText("Cloned - voice_id {}".format(voice_id))
        self.status.emit("Voice cloned")
        self._clear_samples()
        self.consent_check.setChecked(False)
        self.refresh_voices()

    def _on_clone_failed(self, reason):
        self.clone_status.setText(reason)
        self._update_clone_enabled()

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.rebuild_compose()
        self.rebuild()

    def refresh(self):
        self.rebuild()
        self.refresh_voices()
