"""Compose view — spec in, linted prompt out, generated image beside it."""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
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
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import history as hist  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..lint_panel import LintPanel  # noqa: E402
from ..spec_editor import SpecEditor  # noqa: E402
from ..widgets import (  # noqa: E402
    AiSuggestionBadge, Card, ImagePreview, MutedLabel, StarRating, TitleLabel)
from ..workers import LlmTask  # noqa: E402


class ComposeView(QWidget):
    """Emits `generate_requested` with (prompt, references) for the controller."""

    generate_requested = pyqtSignal(str, list)
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

        library_buttons = QHBoxLayout()
        library_buttons.setSpacing(T.SPACE["sm"])
        library_buttons.addWidget(load_button)
        library_buttons.addWidget(save_button)
        library_buttons.addStretch(1)

        # Five buttons will not fit one row in a 330px column, so the editing
        # actions get their own, quieter row.
        new_button = QPushButton("New")
        new_button.setProperty("class", "ghost")
        new_button.clicked.connect(self.new_character)
        rename_button = QPushButton("Rename")
        rename_button.setProperty("class", "ghost")
        rename_button.clicked.connect(self.rename_character)
        delete_button = QPushButton("Delete")
        delete_button.setProperty("class", "danger")
        delete_button.clicked.connect(self.delete_character)

        crud_buttons = QHBoxLayout()
        crud_buttons.setSpacing(T.SPACE["sm"])
        crud_buttons.addWidget(new_button)
        crud_buttons.addWidget(rename_button)
        crud_buttons.addWidget(delete_button)
        crud_buttons.addStretch(1)

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
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        controls = QHBoxLayout()
        controls.setSpacing(T.SPACE["sm"])
        controls.addWidget(QLabel("Form"))
        controls.addWidget(self.form_mode)
        controls.addWidget(shuffle)
        controls.addStretch(1)
        controls.addWidget(copy_button)

        self.prompt_view = QPlainTextEdit()
        self.prompt_view.setReadOnly(True)
        self.prompt_view.setProperty("class", "mono")
        self.prompt_view.setPlaceholderText("The composed prompt appears here.")

        prompt_card = Card()
        prompt_card.body.setSpacing(T.SPACE["sm"])
        prompt_card.body.addWidget(TitleLabel("Prompt"))
        prompt_card.body.addLayout(controls)
        prompt_card.body.addWidget(self.prompt_view, 1)

        self.lint = LintPanel({})
        lint_card = Card()
        lint_card.body.setSpacing(T.SPACE["sm"])
        lint_card.body.addWidget(TitleLabel("Realism check"))
        lint_card.body.addWidget(self.lint, 1)

        middle = QSplitter(Qt.Orientation.Vertical)
        middle.addWidget(prompt_card)
        middle.addWidget(lint_card)
        middle.setSizes([300, 320])

        # --- right: image + rating ---------------------------------------- #
        self.preview = ImagePreview("No image yet.\nGenerate, or drop one in with Set reference.")

        self.generate_button = QPushButton("Generate image")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.clicked.connect(self.request_generate)

        self.rating = StarRating()
        self.rating.setEnabled(False)
        self.rating.rated.connect(self.apply_rating)

        # The reference controls live in the editor's Identity tab; this is the
        # read-out so you can see the lock state next to the result.
        self.reference_label = MutedLabel("No reference image — the face is invented each time.")

        # Caption above the stars, not beside them: side by side, the caption is
        # clipped in this column at any window size.
        rating_row = QVBoxLayout()
        rating_row.setSpacing(T.SPACE["xs"])
        rating_row.addWidget(MutedLabel("How did it turn out?"))
        rating_row.addWidget(self.rating)

        right_card = Card()
        right_card.body.setSpacing(T.SPACE["md"])
        right_card.body.addWidget(TitleLabel("Result"))
        right_card.body.addWidget(self.preview, 1)
        right_card.body.addLayout(rating_row)
        right_card.body.addWidget(self.reference_label)
        right_card.body.addWidget(self.generate_button)

        # Floors for all three, or the splitter falls back to an even split when
        # the window is small and hands the prompt a 237px column. They sum to
        # 810, which fits the 836px the canvas has at the 1100px minimum window.
        left.setMinimumWidth(300)
        # A form column has a natural width; without a ceiling the splitter
        # hands it the slack and starves the prompt, which is the column that
        # actually benefits from being wide.
        left.setMaximumWidth(420)
        middle.setMinimumWidth(280)
        right_card.setMinimumWidth(230)
        right_card.setMaximumWidth(460)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(middle)
        splitter.addWidget(right_card)
        splitter.setChildrenCollapsible(False)
        # Sizes must sit inside the min/max above: setSizes overrides a
        # maximum rather than clamping to it, so asking for 500 here would have
        # quietly defeated the 420 ceiling. Spare width goes to the prompt.
        splitter.setSizes([380, 470, 300])
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
            self.bank, spec, detailed=bool(self.form_mode.currentData()), weights=weights
        )
        self.prompt_view.setPlainText(prompt)
        self.passing = self.lint.update_result(prompt, self.bank)
        self.last_layers = layers
        self.status.emit(
            "{} words · {}".format(len(prompt.split()), "PASS" if self.passing else "needs work")
        )

    def reshuffle(self):
        self.editor.seed.setValue((self.editor.seed.value() + 1) % 10000)

    def prompt_text(self):
        return self.prompt_view.toPlainText()

    # -- results handed back from the Brief view ---------------------------- #
    def apply_suggested_spec(self, spec):
        """Merge a model-drafted spec over the form, keeping what you already set."""
        self.editor.apply_partial(spec)
        self.status.emit("Applied the drafted character — review it before generating")

    def use_upgraded_prompt(self, prompt):
        """Adopt a rewrite that already passed the gate in brief.py.

        It sticks until the next edit, at which point the spec wins again — the
        spec, not a one-off rewrite, is what the app can reproduce.
        """
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

    def set_busy(self, busy):
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText("Generating…" if busy else "Generate image")

    def show_image(self, path):
        self.current_image = path
        if self.preview.load(path):
            self.rating.setEnabled(True)
            if self.entry_id:
                hist.rate(self.entry_id, None, image=str(path))
            self.status.emit("Saved {}".format(Path(path).name))
        else:
            self.status.emit("Could not display {}".format(path))

    def apply_rating(self, value):
        if not self.entry_id:
            self.status.emit("Nothing to rate yet — generate first")
            return
        hist.rate(self.entry_id, value, image=str(self.current_image or ""))
        self.status.emit("Rated {}/5 — this now shapes future prompts".format(value))
