"""Settings view — provider, model, key presence, theme, paths.

Key *presence* is shown. A key value is never rendered, copied or logged.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QThreadPool, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ask_llm  # noqa: E402
import elevenlabs_voices as voices_tool  # noqa: E402
import generate_image as gi  # noqa: E402
import generate_sound as gsnd  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel  # noqa: E402
from ..workers import VoiceDeleteTask, VoiceListTask  # noqa: E402


class SettingsView(QWidget):
    provider_changed = pyqtSignal(str)
    model_changed = pyqtSignal(str)
    theme_toggled = pyqtSignal()
    image_options_changed = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._voice_pool = QThreadPool(self)
        self._voice_pool.setMaxThreadCount(1)
        self.setup_ui()

    def setup_ui(self):
        self.provider = QComboBox()
        self.provider.addItems(sorted(gi.PROVIDERS))
        self.provider.setCurrentText(gi.DEFAULT_PROVIDER)
        self.provider.currentTextChanged.connect(self.on_provider_changed)

        self.model = QLineEdit()
        self.model.setPlaceholderText(gi.PROVIDERS[gi.DEFAULT_PROVIDER]["default_model"])
        self.model.setToolTip(
            "Leave blank to use the default, or the value of the provider's *_IMAGE_MODEL "
            "variable in .env"
        )
        self.model.textChanged.connect(self.model_changed)

        self.key_badge = Badge("checking", "neutral")
        # Higgsfield authenticates with an id AND a secret; one badge would report
        # "set" while the request still cannot be signed.
        self.secret_badge = Badge("", "neutral")
        self.secret_badge.hide()
        recheck = QPushButton("Re-check .env")
        recheck.clicked.connect(self.refresh_key_state)

        key_row = QHBoxLayout()
        key_row.setSpacing(T.SPACE["sm"])
        key_row.addWidget(self.key_badge)
        key_row.addWidget(self.secret_badge)
        key_row.addWidget(recheck)
        key_row.addStretch(1)

        self.reference_note = MutedLabel("")

        # Nano Banana Pro's own options, from its documented enums. `resolution`
        # was not sent at all before, so every image came back at the 1K default
        # however the app was set up.
        self.resolution = QComboBox()
        for option in gi.KIE_RESOLUTIONS:
            self.resolution.addItem(option, option)
        self.resolution.setToolTip(
            "What Nano Banana Pro renders at. Larger costs more per image; the "
            "estimate on the generate button follows this.")
        self.resolution.currentIndexChanged.connect(self.image_options_changed)

        self.output_format = QComboBox()
        for option in gi.KIE_OUTPUT_FORMATS:
            self.output_format.addItem(option, option)
        self.output_format.setToolTip(
            "png keeps every pixel; jpg is smaller. Reference images are uploaded "
            "either way.")
        self.output_format.currentIndexChanged.connect(self.image_options_changed)

        theme_button = QPushButton("Toggle light / dark")
        theme_button.clicked.connect(self.theme_toggled)

        form = QFormLayout()
        form.setHorizontalSpacing(T.COLUMN_GAP)
        form.setVerticalSpacing(T.SPACE["md"])
        form.addRow("Provider", self.provider)
        form.addRow("Model override", self.model)
        form.addRow("Resolution", self.resolution)
        form.addRow("Image format", self.output_format)
        form.addRow("API key", key_row)
        form.addRow("Appearance", theme_button)

        provider_card = Card()
        provider_card.body.addWidget(TitleLabel("Generation"))
        provider_card.body.addLayout(form)
        provider_card.body.addWidget(self.reference_note)
        provider_card.body.addWidget(MutedLabel(
            "Keys live in .env at the project root and are never displayed, copied or written "
            "to temp/. Without a key the app still composes and scores prompts - you just "
            "paste them into the provider's own interface yourself."
        ))

        # OpenRouter no longer generates images. It is the one text model, and it
        # is optional - it makes prompts better, it does not make them possible.
        self.text_model = QLineEdit()
        self.text_model.setPlaceholderText(ask_llm.DEFAULT_MODEL)
        self.text_model.setToolTip(
            "Leave blank to use the default, or the value of {} in .env".format(
                ask_llm.MODEL_VAR)
        )
        self.text_key_badge = Badge("checking", "neutral")
        text_row = QHBoxLayout()
        text_row.setSpacing(T.SPACE["sm"])
        text_row.addWidget(self.text_key_badge)
        text_row.addStretch(1)

        text_form = QFormLayout()
        text_form.setHorizontalSpacing(T.COLUMN_GAP)
        text_form.setVerticalSpacing(T.SPACE["md"])
        text_form.addRow("Text model", self.text_model)
        text_form.addRow("API key", text_row)

        text_card = Card()
        text_card.body.addWidget(TitleLabel("Prompt help (optional)"))
        text_card.body.addLayout(text_form)
        text_card.body.addWidget(MutedLabel(
            "OpenRouter powers the Brief tab only - drafting a character from an idea, "
            "rewriting a prompt, critiquing an image. Every reply is re-scored by the "
            "realism check before it is accepted, and without a key the rest of the app is "
            "unaffected."
        ))

        # ElevenLabs: real sound-effect and text-to-speech generation, and
        # voice cloning. Same "presence only" key badge as every other
        # provider above - optional, and the Sound tab still builds and
        # scores prompts without it.
        self.sound_key_badge = Badge("checking", "neutral")
        recheck_sound = QPushButton("Re-check .env")
        recheck_sound.clicked.connect(self.refresh_key_state)
        sound_key_row = QHBoxLayout()
        sound_key_row.setSpacing(T.SPACE["sm"])
        sound_key_row.addWidget(self.sound_key_badge)
        sound_key_row.addWidget(recheck_sound)
        sound_key_row.addStretch(1)

        self.voice_list = QListWidget()
        self.voice_list.setMaximumHeight(120)
        refresh_voices_button = QPushButton("Refresh")
        refresh_voices_button.setProperty("class", "ghost")
        refresh_voices_button.clicked.connect(self.refresh_voice_list)
        delete_voice_button = QPushButton("Delete selected")
        delete_voice_button.setProperty("class", "ghost")
        delete_voice_button.clicked.connect(self.delete_selected_voice)
        voice_actions = QHBoxLayout()
        voice_actions.setSpacing(T.SPACE["sm"])
        voice_actions.addWidget(refresh_voices_button)
        voice_actions.addWidget(delete_voice_button)
        voice_actions.addStretch(1)

        sound_card = Card()
        sound_card.body.addWidget(TitleLabel("Sound and voice (optional)"))
        sound_card.body.addLayout(sound_key_row)
        sound_card.body.addWidget(MutedLabel(
            "ElevenLabs powers the Sound tab's real Generate buttons, Ads' per-beat "
            "voiceover and Cats' per-scene voiceover. Without a key, Sound still builds "
            "and scores prompts to paste in by hand."))
        sound_card.body.addWidget(MutedLabel("Cloned voices on this account:"))
        sound_card.body.addWidget(self.voice_list)
        sound_card.body.addLayout(voice_actions)

        paths_card = Card()
        paths_card.body.addWidget(TitleLabel("Paths"))
        for label, path, disposable in [
            ("Characters", assets.CHARACTERS_DIR, False),
            ("Prompts", assets.PROMPTS_DIR, True),
            ("Images", assets.IMAGES_DIR, True),
            ("Videos", assets.VIDEOS_DIR, True),
            ("Sound effects", assets.SOUND_DIR, True),
            ("Voice / speech", assets.VOICE_DIR, True),
        ]:
            row = QHBoxLayout()
            row.setSpacing(T.SPACE["sm"])
            caption = MutedLabel("{}  ·  {}".format(
                label, "disposable" if disposable else "keep — these are your assets"
            ))
            button = QPushButton("Open")
            button.setProperty("class", "ghost")
            button.setIcon(assets.icon("folder"))
            button.setIconSize(assets.ICON_SIZE)
            button.clicked.connect(lambda _=False, p=path: self.open_path(p))
            row.addWidget(caption, 1)
            row.addWidget(button)
            paths_card.body.addLayout(row)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(provider_card)
        layout.addWidget(text_card)
        layout.addWidget(sound_card)
        layout.addWidget(paths_card)
        layout.addStretch(1)

        # Three cards of prose need more height than a 700px window leaves, and
        # a QVBoxLayout that runs out of room squashes its children below their
        # minimums rather than refusing - the key field came out 14px tall
        # against a 34px minimum, and every explanatory paragraph lost its last
        # line. Scrolling is the correct answer for a page of settings.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # AsNeeded, never Off: a resizable QScrollArea does not shrink its
        # content below that content's own minimum - it CLIPS, and with the
        # bar off nothing (no scrollbar, no overlap, no elision) reveals the
        # missing part. See CLAUDE.md; Compose lost 274px of every button
        # this way. test_layout.py now fails on it.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.refresh_key_state()
        self.refresh_voice_list()

    def on_provider_changed(self, name):
        cfg = gi.PROVIDERS.get(name)
        if cfg:
            self.model.setPlaceholderText(cfg["default_model"])
        self.refresh_key_state()
        self.provider_changed.emit(name)

    def image_options(self):
        """The generation options that belong to the request, not to the prompt."""
        return {"resolution": self.resolution.currentData() or "1K",
                "output_format": self.output_format.currentData() or "png"}

    def refresh_key_state(self):
        """Presence only - the value is read but never surfaced."""
        name = self.provider.currentText()
        cfg = gi.PROVIDERS.get(name, {})

        def badge(widget, variable):
            present = bool(gi.env_value(variable))
            widget.set_status(
                "success" if present else "warning",
                "{} {}".format(variable, "set" if present else "missing"),
            )

        if cfg.get("key"):
            badge(self.key_badge, cfg["key"])
        if cfg.get("secret"):
            badge(self.secret_badge, cfg["secret"])
            self.secret_badge.show()
        else:
            self.secret_badge.hide()

        self.reference_note.setText(
            "Reference images work with this provider - character consistency is available."
            if cfg.get("references") else
            "This provider takes no reference image, so a locked face cannot be carried "
            "over. Generating with a reference set is refused rather than silently ignored."
        )
        badge(self.text_key_badge, ask_llm.KEY_VAR)
        badge(self.sound_key_badge, gsnd.KEY_VAR)

    def refresh_voice_list(self):
        task = VoiceListTask()
        task.signals.finished.connect(self._on_voices_loaded)
        task.signals.failed.connect(lambda reason: self.status.emit(reason))
        self._voice_pool.start(task)

    def _on_voices_loaded(self, voices):
        self.voice_list.clear()
        for voice in voices:
            item = QListWidgetItem("{}  ({})".format(voice["name"], voice["category"]))
            item.setData(Qt.ItemDataRole.UserRole, voice["voice_id"])
            self.voice_list.addItem(item)

    def delete_selected_voice(self):
        item = self.voice_list.currentItem()
        if not item:
            self.status.emit("Pick a voice to delete first")
            return
        # Deleting removes the voice from the ElevenLabs account - irreversible,
        # and not local like the character/persona deletes, which both confirm.
        answer = QMessageBox.question(
            self, "Delete this voice?",
            "{}\n\nThis removes it from your ElevenLabs account permanently. "
            "It cannot be undone.".format(item.text()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        voice_id = item.data(Qt.ItemDataRole.UserRole)
        task = VoiceDeleteTask(voice_id)
        task.signals.finished.connect(self._on_voice_deleted)
        task.signals.failed.connect(lambda reason: self.status.emit(reason))
        self._voice_pool.start(task)

    def _on_voice_deleted(self, _voice_id):
        self.status.emit("Voice deleted")
        self.refresh_voice_list()

    def open_path(self, path):
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.status.emit("Opened {}".format(path))

    def current_model(self):
        return self.model.text().strip() or None

    def current_text_model(self):
        return self.text_model.text().strip() or None
