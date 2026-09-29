"""Influencer Studio - a persona builder: name, gender, age range, style
tags, hair/eye colour, free-text details and up to 8 mood-reference images,
composed into one Subject description and saved to a roster for reuse.

  Roster          saved personas (temp/resources/personas/*.json) - new/
                  load/rename/delete, the same CRUD shape ComposeView's own
                  character library already uses (ui/views/compose.py)
  Build           the form, plus a live-recomposed Result panel (Copy, Save
                  to roster, Apply to Compose) - the same "give me the
                  prompt, then I decide" shape every other technique
                  section already has
  Face Reference  a searchable, read-only browser over
                  tools/face_glossary.json (face-shape/facial-structure/
                  skin-texture vocabulary), the same shape as the Videos
                  tab's own filmmaking Glossary. "Insert into Details"
                  appends the selected term into the Build tab's free-text
                  Additional Details field - it is never composed, scored
                  or wired into any spec field itself.
  Voice           a persona's reusable VOICE blueprint (accent, tone, pacing,
                  personality) - the course's "Consistent Character Voices"
                  lesson teaches defining this once and pasting the exact
                  same text into every prompt where the character speaks,
                  since even small wording changes shift the voice a model
                  produces. tools/voice_bank.json/build_voice.py supply 16
                  named starting-point styles; the actual persisted field is
                  the freely-editable text box, saved/loaded with the
                  persona like `details` already is. Not folded into
                  compose_persona()'s Subject sentence (voice isn't visual
                  spec content) and not wired into video generation directly
                  - this app has no per-line dialogue field to wire it into,
                  so the payoff is a stable, copyable block of text.

Reference images are a local mood board only - style/aesthetic reference,
never wired into SpecEditor.set_reference()/lock_identity, the app's actual
identity-lock mechanism. There is deliberately no attractiveness/face-shape/
body-shape control here - a face or build is free-text prose in Additional
Details, the same way Compose's own Subject field already works everywhere
else in this app. See tools/build_persona.py's docstring and
workflows/build-an-influencer.md. The Face Reference tab respects that
boundary too - it is a browsable word list to help write that prose, not a
new structured pick.
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QGuiApplication, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
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
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_persona as bper  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_voice as bvoice  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..hints import NAV_HINTS
from ..widgets import Badge, Card, MutedLabel, TitleLabel, chip_row  # noqa: E402

REFERENCE_LIMIT = 8
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class _ReferenceDropArea(QFrame):
    """A drop target for reference images - style/mood only.

    No drag-and-drop existed anywhere in this codebase before this view; this
    is deliberately kept small and view-local rather than a generic reusable
    drop-zone class nothing else needs yet.
    """

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setAcceptDrops(True)
        self.setMinimumHeight(56)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE["md"], T.SPACE["md"], T.SPACE["md"], T.SPACE["md"])
        label = MutedLabel("Drag & drop images here, or use Browse… below")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        images = [path for path in paths if Path(path).suffix.lower() in IMAGE_SUFFIXES]
        if images:
            self.files_dropped.emit(images)
        event.acceptProposedAction()


class _ReferenceThumbnail(QFrame):
    """One small reference-image tile with its own remove control."""

    remove_requested = pyqtSignal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setProperty("class", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE["xs"], T.SPACE["xs"], T.SPACE["xs"], T.SPACE["xs"])
        layout.setSpacing(2)

        preview = QLabel()
        preview.setFixedSize(56, 56)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(
                56, 56, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation))
        else:
            preview.setText("?")

        remove_button = QToolButton()
        remove_button.setText("✕")
        remove_button.setToolTip("Remove this reference image")
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self.path))

        layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(remove_button, 0, Qt.AlignmentFlag.AlignHCenter)


class InfluencerStudioView(QWidget):
    """Emits `status`; `persona_applied(phrase)` on Apply to Compose."""

    status = pyqtSignal(str)
    persona_applied = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bper.load_bank()
        self.voice_bank = bvoice.load_bank()
        self._palette = palette or {}
        self._reference_images = []
        self.face_glossary = self._load_face_glossary()
        self.setup_ui()
        self.reload_roster()
        self.rebuild_compose()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_roster_tab(), "Roster")
        self.tabs.addTab(self._build_build_tab(), "Build")
        self.tabs.addTab(self._build_face_reference_tab(), "Face Reference")
        self.tabs.addTab(self._build_voice_tab(), "Voice")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # The section says what it is for. Seven of the ten rail sections said
        # nothing at all; the sentence is ui/hints.py's, the same one the rail
        # tooltip and the Go menu use, so the three cannot drift.
        layout.addWidget(MutedLabel(NAV_HINTS["influencer_studio"]))
        layout.addWidget(self.tabs)

    def _build_roster_tab(self):
        self.roster = QListWidget()
        self.roster.setAlternatingRowColors(True)
        self.roster.itemActivated.connect(self.load_selected)
        self.roster.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.roster.customContextMenuRequested.connect(self.show_roster_menu)
        self.roster.setToolTip("Double-click a saved persona to load it")

        load_button = QPushButton("Load")
        load_button.setIcon(assets.icon("folder"))
        load_button.setIconSize(assets.ICON_SIZE)
        load_button.clicked.connect(self.load_selected)
        new_button = QPushButton("New")
        new_button.clicked.connect(self.new_persona)

        row_one = QHBoxLayout()
        row_one.setSpacing(T.SPACE["xs"])
        row_one.addWidget(load_button)
        row_one.addWidget(new_button)

        rename_button = QPushButton("Rename…")
        rename_button.clicked.connect(self.rename_persona)
        delete_button = QPushButton("Delete")
        delete_button.setProperty("class", "danger")
        delete_button.clicked.connect(self.delete_persona)

        row_two = QHBoxLayout()
        row_two.setSpacing(T.SPACE["xs"])
        row_two.addWidget(rename_button)
        row_two.addWidget(delete_button)

        card = Card()
        card.body.addWidget(TitleLabel("Saved personas"))
        card.body.addWidget(MutedLabel(
            "Every persona you save lives here, reusable across characters. "
            "Double-click one, or select it and press \"Load\", to open it on the "
            "Build tab."))
        card.body.addWidget(self.roster, 1)
        card.body.addLayout(row_one)
        card.body.addLayout(row_two)
        return self._wrap(card)

    def _build_build_tab(self):
        self.name_field = QLineEdit(placeholderText="e.g. Zoe")
        self.name_field.textChanged.connect(self.rebuild_compose)

        self.gender_combo = QComboBox()
        self.gender_combo.addItem("Select gender", "")
        for key, cfg in bper.genders(self.bank).items():
            self.gender_combo.addItem(cfg["label"], key)
        self.gender_combo.currentIndexChanged.connect(self.rebuild_compose)

        age_layout, self.age_buttons, self.age_group = chip_row(
            [(key, cfg["label"]) for key, cfg in bper.age_ranges(self.bank).items()],
            exclusive=True, columns=4)
        for button in self.age_buttons.values():
            button.toggled.connect(self.rebuild_compose)

        style_layout, self.style_buttons, self.style_group = chip_row(
            [(key, cfg["label"]) for key, cfg in bper.style_tags(self.bank).items()],
            exclusive=False, columns=5)
        for button in self.style_buttons.values():
            button.toggled.connect(self.rebuild_compose)

        hair_layout, self.hair_buttons, self.hair_group = chip_row(
            [(key, cfg["label"], cfg["swatch"])
             for key, cfg in bper.hair_colors(self.bank).items()],
            exclusive=True, columns=5)
        for button in self.hair_buttons.values():
            button.toggled.connect(self.rebuild_compose)

        eye_layout, self.eye_buttons, self.eye_group = chip_row(
            [(key, cfg["label"], cfg["swatch"])
             for key, cfg in bper.eye_colors(self.bank).items()],
            exclusive=True, columns=5)
        for button in self.eye_buttons.values():
            button.toggled.connect(self.rebuild_compose)

        self.details_field = QPlainTextEdit()
        self.details_field.setPlaceholderText(
            "Add any extra details: clothing, accessories, tattoos, makeup, vibe…")
        self.details_field.setFixedHeight(72)
        self.details_field.textChanged.connect(self.rebuild_compose)

        self.reference_drop = _ReferenceDropArea()
        self.reference_drop.files_dropped.connect(self.add_reference_images)
        browse_button = QPushButton("Browse…")
        browse_button.setIcon(assets.icon("folder"))
        browse_button.setIconSize(assets.ICON_SIZE)
        browse_button.clicked.connect(self.choose_reference_images)
        self.reference_count_label = MutedLabel("")
        self.reference_row = QHBoxLayout()
        self.reference_row.setSpacing(T.SPACE["xs"])

        self.composed = QLabel("")
        self.composed.setWordWrap(True)
        self.composed.setProperty("class", "mono")
        self.status_badge = Badge("pick something", "neutral")

        copy_button = QPushButton("Copy")
        copy_button.setProperty("class", "ghost")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_composed)

        save_button = QPushButton("Save to roster")
        save_button.setIcon(assets.icon("save"))
        save_button.setIconSize(assets.ICON_SIZE)
        save_button.clicked.connect(self.save_persona)

        self.apply_button = QPushButton("Apply to Compose")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.clicked.connect(self.apply_to_compose)

        form = Card()
        form.body.addWidget(TitleLabel("Build a persona"))
        form.body.addWidget(MutedLabel("Name"))
        form.body.addWidget(self.name_field)
        form.body.addWidget(MutedLabel("Gender"))
        form.body.addWidget(self.gender_combo)
        form.body.addWidget(MutedLabel("Age range"))
        form.body.addLayout(age_layout)
        form.body.addWidget(MutedLabel("Style & aesthetic (pick any number)"))
        form.body.addLayout(style_layout)
        form.body.addWidget(MutedLabel("Hair color"))
        form.body.addLayout(hair_layout)
        form.body.addWidget(MutedLabel("Eye color"))
        form.body.addLayout(eye_layout)
        form.body.addWidget(MutedLabel("Additional details"))
        form.body.addWidget(self.details_field)
        form.body.addWidget(MutedLabel(
            "Reference images — style/mood only, up to {}. Never sent as an identity "
            "lock; for that, use Compose's own reference picker on its Identity "
            "tab.".format(REFERENCE_LIMIT)))
        form.body.addWidget(self.reference_drop)
        ref_actions = QHBoxLayout()
        ref_actions.setSpacing(T.SPACE["sm"])
        ref_actions.addWidget(browse_button)
        ref_actions.addWidget(self.reference_count_label)
        ref_actions.addStretch(1)
        form.body.addLayout(ref_actions)
        form.body.addLayout(self.reference_row)
        self._rebuild_reference_thumbnails()

        result = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Result"))
        header.addWidget(self.status_badge)
        header.addStretch(1)
        result.body.addLayout(header)
        result.body.addWidget(self.composed)
        actions = QHBoxLayout()
        actions.setSpacing(T.SPACE["sm"])
        actions.addWidget(copy_button)
        actions.addWidget(save_button)
        actions.addWidget(self.apply_button)
        actions.addStretch(1)
        result.body.addLayout(actions)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(form)
        layout.addWidget(result)
        return self._scrolled(body)

    # -- Face Reference (browse-only, feeds Additional Details) -------------#
    def _load_face_glossary(self):
        path = ROOT / "tools" / "face_glossary.json"
        if not path.exists():
            return {"terms": [], "categories": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_face_reference_tab(self):
        self.face_search = QLineEdit()
        self.face_search.setPlaceholderText("Search face-shape and facial-structure terms…")
        self.face_search.setClearButtonEnabled(True)
        self.face_search.textChanged.connect(self._filter_face_glossary)

        self.face_tree = QTreeWidget()
        self.face_tree.setColumnCount(2)
        self.face_tree.setHeaderLabels(["TERM", "MEANING"])
        self.face_tree.setAlternatingRowColors(True)
        self.face_tree.setColumnWidth(0, 220)
        self.face_tree.setWordWrap(True)
        self.face_tree.itemDoubleClicked.connect(self._insert_face_term)

        insert_button = QPushButton("Insert into Details")
        insert_button.clicked.connect(lambda: self._insert_face_term(self.face_tree.currentItem()))

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Face & facial-structure reference"))
        card.body.addWidget(MutedLabel(
            "Browse-only vocabulary for the Build tab's free-text Additional Details "
            "field - there is deliberately no face-shape or body-shape picker in this "
            "app (see the Build tab). Double-click a term, or select one and press "
            "\"Insert into Details\", to add it there."
        ))
        card.body.addWidget(self.face_search)
        card.body.addWidget(self.face_tree, 1)
        actions = QHBoxLayout()
        actions.addWidget(insert_button)
        actions.addStretch(1)
        card.body.addLayout(actions)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)

        self._filter_face_glossary("")
        return self._scrolled(page)

    def _filter_face_glossary(self, text):
        needle = (text or "").strip().lower()
        self.face_tree.clear()
        labels = self.face_glossary.get("categories", {})
        by_category = {}
        for entry in self.face_glossary.get("terms", []):
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
            self.face_tree.addTopLevelItem(parent)
            for entry in rows:
                parent.addChild(QTreeWidgetItem([entry["term"], entry["definition"]]))
            parent.setExpanded(True)

    def _insert_face_term(self, item, _column=0):
        if item is None or item.parent() is None:
            self.status.emit("Select a term (not a category) to insert it")
            return
        term = item.text(0)
        existing = self.details_field.toPlainText().strip()
        self.details_field.setPlainText(existing + (", " if existing else "") + term)
        self.status.emit("Inserted \"{}\" into Additional Details".format(term))

    # -- Voice (a persona's reusable voice blueprint) ------------------------#
    def _build_voice_tab(self):
        self.voice_style_combo = QComboBox()
        self.voice_style_combo.addItem("(pick a starting point)", "")
        for key, cfg in bvoice.styles(self.voice_bank).items():
            self.voice_style_combo.addItem(cfg["label"], key)
        self.voice_style_combo.setToolTip(
            "A named vocal-delivery style from the course's \"Consistent Character "
            "Voices\" lesson - a starting point, not required.")
        self.voice_style_combo.currentIndexChanged.connect(self._rebuild_voice_preview)

        self.voice_accent_field = QLineEdit()
        self.voice_accent_field.setPlaceholderText(
            "e.g. \"Australian accent\", \"soft Irish accent\" - leave blank for a neutral accent")
        self.voice_accent_field.textChanged.connect(self._rebuild_voice_preview)

        self.voice_preview = MutedLabel("")
        self.voice_preview.setWordWrap(True)
        self.voice_preview.setProperty("class", "mono")

        use_button = QPushButton("Use this blueprint")
        use_button.clicked.connect(self._use_voice_preview)

        generator = Card()
        generator.body.addWidget(TitleLabel("Generate a starting point"))
        generator.body.addWidget(MutedLabel(
            "Pick a named vocal style and an accent, or skip this and just type your own "
            "below. Either way: keep the wording IDENTICAL across every prompt for this "
            "character - even a small change shifts the voice a model produces."))
        generator.body.addWidget(self.voice_style_combo)
        generator.body.addWidget(self.voice_accent_field)
        generator.body.addWidget(self.voice_preview)
        gen_actions = QHBoxLayout()
        gen_actions.addWidget(use_button)
        gen_actions.addStretch(1)
        generator.body.addLayout(gen_actions)

        self.voice_field = QPlainTextEdit()
        self.voice_field.setPlaceholderText(
            "This character's voice blueprint - accent, tone, pacing, personality. Paste "
            "this exact text into every prompt where they need to speak.")
        self.voice_field.setFixedHeight(96)

        copy_voice_button = QPushButton("Copy")
        copy_voice_button.setProperty("class", "ghost")
        copy_voice_button.setIcon(assets.icon("copy"))
        copy_voice_button.setIconSize(assets.ICON_SIZE)
        copy_voice_button.clicked.connect(self.copy_voice)

        blueprint = Card()
        blueprint.body.addWidget(TitleLabel("Voice blueprint"))
        blueprint.body.addWidget(MutedLabel(
            "Saved and reloaded with this persona, like Additional Details. Not applied "
            "to Compose automatically - this app has no per-line dialogue field to wire "
            "it into, so copy it into whatever prompt needs this character to speak."))
        blueprint.body.addWidget(self.voice_field)
        voice_actions = QHBoxLayout()
        voice_actions.addWidget(copy_voice_button)
        voice_actions.addStretch(1)
        blueprint.body.addLayout(voice_actions)

        self._rebuild_voice_preview()

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(generator)
        layout.addWidget(blueprint)
        return self._scrolled(body)

    def _rebuild_voice_preview(self):
        if not hasattr(self, "voice_preview"):
            return
        style = self.voice_style_combo.currentData() or None
        if not style:
            self.voice_preview.setText("Pick a style above to preview a starting blueprint.")
            return
        accent = self.voice_accent_field.text().strip()
        phrase, _warnings = bvoice.compose_voice(self.voice_bank, style=style, accent=accent)
        self.voice_preview.setText(phrase)

    def _use_voice_preview(self):
        style = self.voice_style_combo.currentData() or None
        if not style:
            self.status.emit("Pick a style first")
            return
        accent = self.voice_accent_field.text().strip()
        phrase, _warnings = bvoice.compose_voice(self.voice_bank, style=style, accent=accent)
        self.voice_field.setPlainText(phrase)
        self.status.emit("Voice blueprint set - edit it freely, then Save to roster")

    def copy_voice(self):
        text = self.voice_field.toPlainText().strip()
        if not text:
            self.status.emit("Nothing to copy yet")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied voice blueprint")

    def _wrap(self, card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, T.SPACE["md"], 0, 0)
        layout.addWidget(card)
        return self._scrolled(page)

    def _scrolled(self, widget):
        """See CLAUDE.md - a resizable QScrollArea never shrinks its content
        below that content's own minimum, it clips silently with the bar off.
        AsNeeded, never Off, on every page in this view from day one."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # -- reference images (local mood board only) ---------------------------#
    def choose_reference_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose reference images", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if paths:
            self.add_reference_images(paths)

    def add_reference_images(self, paths):
        room = REFERENCE_LIMIT - len(self._reference_images)
        if room <= 0:
            self.status.emit("Already at the {} reference image limit".format(REFERENCE_LIMIT))
            return
        accepted, rejected = list(paths[:room]), list(paths[room:])
        self._reference_images.extend(accepted)
        self._rebuild_reference_thumbnails()
        if rejected:
            self.status.emit(
                "Added {}, skipped {} — {} image limit reached".format(
                    len(accepted), len(rejected), REFERENCE_LIMIT))
        else:
            self.status.emit("Added {} reference image(s)".format(len(accepted)))

    def remove_reference_image(self, path):
        if path in self._reference_images:
            self._reference_images.remove(path)
            self._rebuild_reference_thumbnails()

    def _rebuild_reference_thumbnails(self):
        while self.reference_row.count():
            item = self.reference_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for path in self._reference_images:
            thumb = _ReferenceThumbnail(path)
            thumb.remove_requested.connect(self.remove_reference_image)
            self.reference_row.addWidget(thumb)
        self.reference_row.addStretch(1)
        self.reference_count_label.setText(
            "{}/{}".format(len(self._reference_images), REFERENCE_LIMIT))

    # -- compose -------------------------------------------------------------#
    def _picked_style_tags(self):
        return [key for key, button in self.style_buttons.items() if button.isChecked()]

    @staticmethod
    def _picked_single(buttons):
        for key, button in buttons.items():
            if button.isChecked():
                return key
        return None

    def rebuild_compose(self):
        if not hasattr(self, "composed"):
            return
        name = self.name_field.text().strip()
        gender = self.gender_combo.currentData() or None
        age = self._picked_single(self.age_buttons)
        styles = self._picked_style_tags()
        hair = self._picked_single(self.hair_buttons)
        eye = self._picked_single(self.eye_buttons)
        details = self.details_field.toPlainText().strip()
        phrase = bper.compose_persona(
            self.bank, name=name, gender=gender, age_range=age, style_tags_=styles,
            hair_color=hair, eye_color=eye, details=details,
        )
        # compose_persona never raises - a blank form still returns "a person."
        # - so an empty form must not read as a green "ready" persona.
        filled = any([name, gender, age, styles, hair, eye, details])
        self.composed.setText(phrase if filled else "Describe the persona above to build a Subject sentence.")
        self.status_badge.set_status(
            "success" if filled else "neutral", "ready" if filled else "empty")
        self.apply_button.setEnabled(filled)

    def copy_composed(self):
        if not self.apply_button.isEnabled():
            self.status.emit("Nothing composed yet")
            return
        text = self.composed.text().strip()
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied: " + text)

    def apply_to_compose(self):
        if not self.apply_button.isEnabled():
            self.status.emit("Nothing composed yet")
            return
        self.persona_applied.emit(self.composed.text().strip())
        self.status.emit("Applied to Compose")

    # -- persona dict in/out --------------------------------------------------#
    def _persona_dict(self):
        return {
            "name": self.name_field.text().strip(),
            "gender": self.gender_combo.currentData() or "",
            "age_range": self._picked_single(self.age_buttons) or "",
            "style_tags": self._picked_style_tags(),
            "hair_color": self._picked_single(self.hair_buttons) or "",
            "eye_color": self._picked_single(self.eye_buttons) or "",
            "details": self.details_field.toPlainText().strip(),
            "reference_images": list(self._reference_images),
            "voice": self.voice_field.toPlainText().strip(),
        }

    @staticmethod
    def _set_exclusive_selection(buttons, group, key):
        """Check `key`'s button and uncheck every other one - including
        clearing to NONE checked when `key` matches nothing (a blank New
        persona).

        A plain `button.setChecked(False)` is not enough here: Qt's
        `QButtonGroup` refuses to let its currently-checked button be
        unchecked via `setChecked(False)` while the group is exclusive - the
        group is written to always keep exactly one button checked once any
        button in it ever has been. Found by testing New (blank) after
        loading a real persona: every chip's OWN state looked right in
        isolation, but the previously-checked Age/Hair/Eye chip stayed
        visibly checked and its phrase stayed in the composed sentence.
        Toggling the group's own exclusivity off for the clear, then back on,
        is what actually lets zero be a valid state.
        """
        if group is not None:
            group.setExclusive(False)
        for button_key, button in buttons.items():
            button.blockSignals(True)
            button.setChecked(button_key == key)
            button.blockSignals(False)
        if group is not None:
            group.setExclusive(True)

    def _load_persona_dict(self, persona):
        """Populate every field, then recompose once - not per-field."""
        self.name_field.blockSignals(True)
        self.name_field.setText(persona.get("name", ""))
        self.name_field.blockSignals(False)

        self.gender_combo.blockSignals(True)
        index = self.gender_combo.findData(persona.get("gender", ""))
        self.gender_combo.setCurrentIndex(max(0, index))
        self.gender_combo.blockSignals(False)

        age_key = persona.get("age_range", "")
        self._set_exclusive_selection(self.age_buttons, self.age_group, age_key)

        style_keys = set(persona.get("style_tags", []))
        for key, button in self.style_buttons.items():
            button.blockSignals(True)
            button.setChecked(key in style_keys)
            button.blockSignals(False)

        hair_key = persona.get("hair_color", "")
        self._set_exclusive_selection(self.hair_buttons, self.hair_group, hair_key)

        eye_key = persona.get("eye_color", "")
        self._set_exclusive_selection(self.eye_buttons, self.eye_group, eye_key)

        self.details_field.blockSignals(True)
        self.details_field.setPlainText(persona.get("details", ""))
        self.details_field.blockSignals(False)

        self._reference_images = list(persona.get("reference_images", []))
        self._rebuild_reference_thumbnails()

        self.voice_field.setPlainText(persona.get("voice", ""))

        self.rebuild_compose()

    # -- roster CRUD (mirrors ComposeView's own character library) ----------#
    # Its own folder, its own JSON shape - a persona is lighter-weight and
    # structured differently than a full character spec, so it gets a
    # parallel roster (assets.PERSONAS_DIR) rather than being crammed into
    # assets.CHARACTERS_DIR. See ui/views/compose.py's reload_library()/
    # load_selected()/save_spec()/new_character()/rename_character()/
    # delete_character() - this is the same shape, adapted.
    def reload_roster(self, select_stem=None):
        self.roster.clear()
        assets.PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(assets.PERSONAS_DIR.glob("*.json")):
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.roster.addItem(item)
        if select_stem:
            for row in range(self.roster.count()):
                if self.roster.item(row).text() == select_stem:
                    self.roster.setCurrentRow(row)
                    break

    def load_selected(self):
        item = self.roster.currentItem()
        if item is None:
            self.status.emit("Select a persona in the roster first")
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        try:
            persona = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Could not load persona", "{}\n\n{}".format(path, exc))
            return
        self._load_persona_dict(persona)
        self.tabs.setCurrentIndex(1)
        self.status.emit("Loaded {}".format(path.name))

    def save_persona(self):
        persona = self._persona_dict()
        slug = self.safe_slug(persona.get("name") or "persona")
        path = self.persona_path(slug)

        if path.exists():
            answer = QMessageBox.question(
                self, "Overwrite persona?",
                "{} already exists.\n\nOverwrite it?".format(path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        persona["slug"] = slug
        assets.PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(persona, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.reload_roster(select_stem=slug)
        self.status.emit("Saved {}".format(path.name))

    def persona_path(self, stem):
        return assets.PERSONAS_DIR / "{}.json".format(stem)

    def safe_slug(self, text):
        """slugify(), hardened for use as a filename - same guards
        ComposeView.safe_slug() already applies (trailing hyphens, Windows
        reserved device names)."""
        slug = bp.slugify(text).strip("-")
        reserved = slug.lower() in {"con", "prn", "aux", "nul"}
        if reserved or (slug[:3].lower() in {"com", "lpt"} and slug[3:].isdigit()):
            slug += "-persona"
        return slug or "untitled"

    def selected_path(self, action):
        item = self.roster.currentItem()
        if item is None:
            self.status.emit("Select a persona to {} first".format(action))
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def show_roster_menu(self, point):
        menu = QMenu(self.roster)
        menu.addAction("Load", self.load_selected)
        menu.addAction("New", self.new_persona)
        menu.addAction("Rename...", self.rename_persona)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_persona)
        menu.exec(self.roster.mapToGlobal(point))

    def new_persona(self):
        self._load_persona_dict({})
        self.roster.setCurrentRow(-1)
        self.tabs.setCurrentIndex(1)
        self.status.emit("New persona - fill it in, then Save to roster")

    def rename_persona(self):
        path = self.selected_path("rename")
        if path is None:
            return
        name, ok = QInputDialog.getText(self, "Rename persona", "New name:", text=path.stem)
        if not ok:
            return
        if not name.strip():
            self.status.emit("A persona needs a name")
            return
        slug = self.safe_slug(name)
        if slug == path.stem:
            return
        target = self.persona_path(slug)
        if target.exists():
            QMessageBox.warning(
                self, "Name already taken", "{} already exists.".format(target.name))
            return
        try:
            persona = json.loads(path.read_text(encoding="utf-8"))
            persona["slug"] = slug
            target.write_text(
                json.dumps(persona, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            path.unlink()
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Could not rename persona", "{}\n\n{}".format(path, exc))
            return
        self.reload_roster(select_stem=slug)
        self.status.emit("Renamed to {}".format(target.name))

    def delete_persona(self):
        path = self.selected_path("delete")
        if path is None:
            return
        answer = QMessageBox.question(
            self, "Delete persona?",
            "{} will be removed from disk. This cannot be undone.".format(path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Could not delete persona", "{}\n\n{}".format(path, exc))
            return
        self.reload_roster()
        self.status.emit("Deleted {}".format(path.name))

    # -- theming -------------------------------------------------------------#
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        if hasattr(self, "face_search"):
            self._filter_face_glossary(self.face_search.text())

    def refresh(self):
        pass
