"""The character spec form, sectioned by the six-part brief framework.

Tabs follow AI Video Bootcamp lesson 1: Purpose, then the parts of the brief the
app actually owns — Subject, Scene, Identity, Advanced.

UI only. It collects fields and hands back the dict tools/build_prompt.py
expects; it composes nothing itself. The public surface — `spec()`,
`load_spec()`, `apply_partial()`, `reference()`, `set_reference()`,
`lighting_value()`, `shot_value()`, `shot_custom()`, `composition_guide()`,
`composition_custom()`, the
`changed` signal and the `.seed` attribute — is what the rest of the app talks
to, so it stays stable regardless of how the tabs are arranged.

Shot, lighting and composition are all editable combos: the bank's entries are
tested starting points, not a closed world. Preset keys and typed text travel as
separate spec keys (`shot` vs `shot_custom`) so that a misspelt preset is still
rejected by the validators instead of quietly becoming a custom phrase.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402

from . import assets, tokens as T  # noqa: E402
from .widgets import MutedLabel, mark_error  # noqa: E402

AUTO_LABEL = "(auto)"
# Composition is opt-in, not auto-filled: the bank imposes no geometry of its own,
# so the empty choice means "none", not "let the app decide".
NO_GUIDE_LABEL = "(none)"

# What spec() substitutes when the subject box is empty, so that a prompt can
# always be composed. It is a stand-in, never something the user wrote, and
# anything asking "has this been filled in?" has to know the difference.
PLACEHOLDER_SUBJECT = "a person"


def _tab(rows, extra_widgets=()):
    """A tab page: a form of (label, widget) rows plus any trailing widgets."""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(T.SPACE["md"], T.SPACE["md"], T.SPACE["md"], T.SPACE["md"])
    layout.setSpacing(T.SPACE["md"])

    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(T.COLUMN_GAP)
    form.setVerticalSpacing(T.SPACE["sm"])
    for label, widget in rows:
        form.addRow(label, widget)
    layout.addLayout(form)

    for widget in extra_widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return page


class SpecEditor(QWidget):
    """Emits `changed` on any edit; `spec()` returns the tool-ready dict."""

    changed = pyqtSignal()
    # The deeper lighting tool lives in its own nav section, not here - this
    # combo stays the fast/simple path. Same relationship Videos' standalone
    # Audio Cue field already has to the full Sound section.
    open_lighting_requested = pyqtSignal()

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.bank = bank
        self._reference = ""

        self._build_fields()
        self._build_tabs()
        self._connect_signals()
        self._refresh_derived()

    # -- fields ------------------------------------------------------------- #
    def _build_fields(self):
        bank = self.bank

        self.purpose = QComboBox()
        self.purpose.addItem(AUTO_LABEL, "")
        for key, cfg in bank.get("purposes", {}).items():
            self.purpose.addItem(cfg.get("label", key), key)
        self.purpose.setToolTip(
            "What the image is for. Sets the shot and aspect below unless you set "
            "them yourself — your own choice always wins."
        )

        self.aspect = QComboBox(editable=True)
        self.aspect.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.aspect.addItems(["", "1:1", "4:5", "3:2", "16:9", "9:16"])
        self.aspect.setToolTip("Leave blank to take the aspect from the purpose.")

        self.purpose_note = MutedLabel("")

        self.subject = QPlainTextEdit()
        self.subject.setPlaceholderText(
            "a woman in her late twenties with light freckles and dark wavy hair"
        )
        self.subject.setFixedHeight(64)
        self.wardrobe = QLineEdit(placeholderText="an oversized cream knit sweater")
        self.action = QLineEdit(placeholderText="leaning against the counter with a mug")
        self.mood = QLineEdit(placeholderText="calm and unhurried")

        self.setting = QLineEdit(placeholderText="a bright apartment kitchen, mid-morning")

        # Editable, like lighting: the five presets are the tested starting
        # points, not the only shots that exist.
        self.shot = QComboBox(editable=True)
        self.shot.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.shot.addItem(AUTO_LABEL, "")
        for name in bank["shot_presets"]:
            self.shot.addItem(name, name)
        self.shot.setToolTip(
            "Leave on (auto) to take the shot from the purpose, pick a preset, or "
            "type your own — e.g. \"close-up iPhone-style photo\".\n"
            "A typed shot takes the camera slot and replaces the preset entirely. "
            "If it names no camera the realism check will say so: that is the gate "
            "working, not a bug."
        )

        # Editable: the bank's sources are suggestions, not a closed set. A typed
        # value goes through as-is, exactly as overrides.lighting does on the CLI.
        self.lighting = QComboBox(editable=True)
        self.lighting.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lighting.addItem(AUTO_LABEL, "")
        for term in bank["layers"]["lighting"]["terms"]:
            self.lighting.addItem(term, term)
        self.lighting.setToolTip(
            "Pick a source or type your own — e.g. \"firelight from a wood stove\".\n"
            "\"realistic shadows\" is always appended so the lighting layer still scores."
        )

        # Seven named geometries, plus anything you care to type — a framing
        # instruction in plain words ("framed to include the sky behind her") is
        # as legitimate as a named grid, and often clearer to the model.
        self.composition = QComboBox(editable=True)
        self.composition.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.composition.addItem(NO_GUIDE_LABEL, "")
        for key, guide in bp.guides(bank).items():
            self.composition.addItem(guide["label"], key)
            self.composition.setItemData(
                self.composition.count() - 1, guide["note"], Qt.ItemDataRole.ToolTipRole
            )
        self.composition.setToolTip(
            "Optional framing, off by default. On (none) no compositional rule is "
            "imposed at all - neither the bank nor the shot preset supplies one.\n"
            "Pick a named geometry or type your own instruction. Either way it pins "
            "the first composition slot and the bank fills the rest, so this can "
            "never cost you the composition layer; an explicit choice outranks the "
            "shot preset and any camera-move hint."
        )

        self.reference_label = MutedLabel("")
        self.reference_button = QPushButton("Choose reference image…")
        self.reference_button.setIcon(assets.icon("folder"))
        self.reference_button.setIconSize(assets.ICON_SIZE)
        self.reference_button.clicked.connect(self.choose_reference)
        self.reference_clear = QPushButton("Clear")
        self.reference_clear.setProperty("class", "ghost")
        self.reference_clear.clicked.connect(lambda: self.set_reference(""))

        self.extra = QPlainTextEdit()
        self.extra.setPlaceholderText("one extra direction per line")
        self.extra.setFixedHeight(72)
        self.seed = QSpinBox(minimum=0, maximum=9999)
        self.slug = QLineEdit(placeholderText="(auto from subject)")

        for field in [self.subject, self.extra, self.wardrobe, self.setting,
                      self.action, self.mood, self.slug, self.shot,
                      self.aspect, self.lighting, self.composition, self.purpose]:
            field.setMinimumWidth(140)

    # -- tabs --------------------------------------------------------------- #
    def _build_tabs(self):
        reference_row = QWidget()
        row_layout = QHBoxLayout(reference_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(T.SPACE["sm"])
        row_layout.addWidget(self.reference_button)
        row_layout.addWidget(self.reference_clear)
        row_layout.addStretch(1)

        self.tabs = QTabWidget()
        # Five sections in a narrow sidebar: let the bar scroll rather than clip,
        # and elide before it overflows.
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.addTab(
            _tab([("Purpose", self.purpose), ("Aspect", self.aspect)],
                 [self.purpose_note]),
            "Purpose",
        )
        self.tabs.addTab(
            _tab([("Subject", self.subject), ("Wardrobe", self.wardrobe),
                  ("Action", self.action), ("Mood", self.mood)]),
            "Subject",
        )
        open_lighting = QPushButton("Open Lighting section →")
        open_lighting.setProperty("class", "ghost")
        open_lighting.setToolTip(
            "Named setups (Rembrandt, split, loop, ...) and a direction + quality + "
            "source picker - the combo above stays the fast, simple path.")
        open_lighting.clicked.connect(self.open_lighting_requested)
        self.tabs.addTab(
            _tab([("Setting", self.setting), ("Shot", self.shot),
                  ("Lighting", self.lighting), ("Composition", self.composition)],
                 [open_lighting]),
            "Scene",
        )
        self.tabs.addTab(
            _tab([], [
                MutedLabel(
                    "Lock this character's face to an image so later shots stay the "
                    "same person. The reference is sent to the model alongside the "
                    "prompt — the wording alone cannot hold a face."
                ),
                reference_row,
                self.reference_label,
            ]),
            "Identity",
        )
        self.tabs.addTab(
            _tab([("Extra", self.extra), ("Seed", self.seed), ("Slug", self.slug)]),
            "More",
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.tabs)

    def _connect_signals(self):
        for widget in [self.subject, self.extra]:
            widget.textChanged.connect(self.changed)
        for widget in [self.wardrobe, self.setting, self.action, self.mood, self.slug]:
            widget.textChanged.connect(self.changed)
        self.purpose.currentIndexChanged.connect(self.changed)
        # Editable combos must watch text, not index — a typed value never
        # changes the index. Shot and composition joined this group when they
        # gained a custom option; watching the index would have made typed text
        # invisible to the live rebuild.
        self.shot.currentTextChanged.connect(self.changed)
        self.composition.currentTextChanged.connect(self.changed)
        self.lighting.currentTextChanged.connect(self.changed)
        self.aspect.currentTextChanged.connect(self.changed)
        self.seed.valueChanged.connect(self.changed)
        self.subject.textChanged.connect(self._validate)
        self.changed.connect(self._refresh_derived)

    def _validate(self):
        """A subject is the one field the prompt cannot be built without."""
        mark_error(self.subject, not self.subject.toPlainText().strip())

    def _refresh_derived(self):
        """Show what the purpose is supplying, and any disagreement with it."""
        self.reference_label.setText(
            "Identity locked to " + Path(self._reference).name if self._reference
            else "No reference image — the face is invented each time."
        )

        key = self.purpose.currentData()
        if not key:
            self.purpose_note.setText(
                "No purpose set. Shot and aspect are whatever you choose below."
            )
            return

        cfg = self.bank.get("purposes", {}).get(key, {})
        notes = bp.purpose_conflicts(self.bank, self.spec())
        if notes:
            self.purpose_note.setText(
                "Heads up: " + "; ".join(notes) + ". Your choice is being used."
            )
            return
        supplied = [
            "{} {}".format(field, cfg[field])
            for field in ("shot", "aspect")
            if cfg.get(field) and not self._explicit(field)
        ]
        detail = cfg.get("note", "")
        self.purpose_note.setText(
            ("Supplying " + ", ".join(supplied) + ". " if supplied else "") + detail
        )

    def _explicit(self, field):
        if field == "shot":
            # A typed shot is every bit as explicit as a picked one.
            return bool(self.shot_value() or self.shot_custom())
        return bool(self.aspect.currentText().strip())

    # -- reference image (character consistency) ---------------------------- #
    def reference(self):
        return self._reference

    def set_reference(self, path):
        self._reference = str(path or "")
        self.changed.emit()

    def choose_reference(self):
        start = str(assets.IMAGES_DIR if assets.IMAGES_DIR.exists() else ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a reference image", start, "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.set_reference(path)

    @staticmethod
    def _listed(combo, text):
        """The key of the listed item `text` names, or "".

        Typing a preset's exact name is choosing that preset - but the combo's
        index does not move when text is typed rather than picked, so
        currentData() alone reports it as free text. Left unresolved, typing
        "portrait" replaced the camera slot with the bare word "portrait" and
        threw the preset's lens and composition away.

        Matched against the visible text and the underlying key, so both
        "Rule of Thirds" and "rule-of-thirds" resolve.
        """
        text = (text or "").strip()
        if not text:
            return ""
        fixed = Qt.MatchFlag.MatchFixedString
        index = combo.findText(text, fixed)
        if index < 0:
            index = combo.findData(text, Qt.ItemDataRole.UserRole, fixed)
        return (combo.itemData(index) or "") if index >= 0 else ""

    def composition_guide(self):
        """The chosen framing geometry key, or "" for none or for typed text."""
        return (self.composition.currentData()
                or self._listed(self.composition, self.composition.currentText()))

    def composition_custom(self):
        """Typed framing text, or "" when a listed guide (or none) is chosen."""
        if self.composition_guide():
            return ""
        text = self.composition.currentText().strip()
        return "" if text in ("", NO_GUIDE_LABEL) else text

    def shot_value(self):
        """The chosen preset key, or "" for auto or for typed text."""
        return self.shot.currentData() or self._listed(self.shot, self.shot.currentText())

    def shot_custom(self):
        """Typed shot text, or "" when a listed preset (or auto) is chosen."""
        if self.shot_value():
            return ""
        text = self.shot.currentText().strip()
        return "" if text in ("", AUTO_LABEL) else text

    def lighting_value(self):
        """The chosen or typed lighting source, or "" for automatic."""
        text = self.lighting.currentText().strip()
        return "" if text == AUTO_LABEL else text

    def set_lighting_override(self, phrase):
        """Load a composed phrase from the Lighting section into this combo.

        The combo is editable with InsertPolicy.NoInsert - setCurrentText()
        writes straight into its embedded line edit without needing (or
        polluting) a matching item in the dropdown, the same mechanism
        load_spec() already relies on for restoring a saved custom value.
        currentTextChanged is already wired to `changed`, so the prompt
        preview updates the same way it does for any other edit here.
        """
        self.lighting.setCurrentText((phrase or "").strip())

    # -- data in / out ------------------------------------------------------ #
    def filled_keys(self):
        """The spec keys the user has actually put something into.

        Not the same question as "what does spec() contain": spec() substitutes
        PLACEHOLDER_SUBJECT so a prompt can always be composed, and treating that
        as filled made auto-fill reject the model's subject every single time -
        on an empty form, the one field that most needed filling.
        """
        values = self.spec()
        if not self.subject.toPlainText().strip():
            values.pop("subject", None)
        return {key for key, value in values.items()
                if value not in ("", None) and value != [] and value != {}}

    def spec(self):
        spec = {
            "subject": self.subject.toPlainText().strip() or PLACEHOLDER_SUBJECT,
            "seed": self.seed.value(),
        }
        if self._reference:
            # A reference image is what makes identity-locking meaningful, so
            # the two travel together.
            spec["reference"] = self._reference
            spec["lock_identity"] = True

        for key, widget in [
            ("wardrobe", self.wardrobe),
            ("setting", self.setting),
            ("action", self.action),
            ("mood", self.mood),
            ("slug", self.slug),
        ]:
            value = widget.text().strip()
            if value:
                spec[key] = value

        if self.purpose.currentData():
            spec["purpose"] = self.purpose.currentData()
        # Preset key and free text are separate keys, so a typo in a preset name
        # is still caught by validate_shot() instead of silently becoming a
        # custom phrase. The same for composition.
        if self.shot_value():
            spec["shot"] = self.shot_value()
        elif self.shot_custom():
            spec["shot_custom"] = self.shot_custom()
        if self.composition_guide():
            spec["composition_guide"] = self.composition_guide()
        elif self.composition_custom():
            spec["composition_guide_custom"] = self.composition_custom()
        if self.aspect.currentText().strip():
            spec["aspect"] = self.aspect.currentText().strip()

        extra = [line.strip() for line in self.extra.toPlainText().splitlines() if line.strip()]
        if extra:
            spec["extra"] = extra

        # An explicit source bypasses the bank's random pick, so re-add the
        # modifier the bank would otherwise append. That matters most for a
        # custom source the linter has no keyword for — "realistic shadows"
        # keeps the lighting layer scoring.
        lighting = self.lighting_value()
        if lighting:
            spec["overrides"] = {"lighting": [lighting, "realistic shadows"]}

        return spec

    def load_spec(self, spec):
        """Populate every field, then emit `changed` once — not a dozen times."""
        widgets = [
            self.subject, self.extra, self.wardrobe, self.setting, self.action,
            self.mood, self.slug, self.shot, self.aspect, self.lighting,
            self.composition, self.purpose, self.seed,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        self._reference = spec.get("reference", "") or ""
        self.subject.setPlainText(spec.get("subject", ""))
        self.wardrobe.setText(spec.get("wardrobe", ""))
        self.setting.setText(spec.get("setting", ""))
        self.action.setText(spec.get("action", ""))
        self.mood.setText(spec.get("mood", ""))
        self.slug.setText(spec.get("slug", ""))
        self.extra.setPlainText("\n".join(spec.get("extra", [])))
        self.seed.setValue(int(spec.get("seed", 0)))
        # A saved custom value is not in the list, so set the text; a saved
        # preset key selects its item. An *unknown* preset key is neither - it
        # falls back to (auto) rather than being resurrected as free text.
        self._restore_combo(self.shot, spec.get("shot", ""),
                            spec.get("shot_custom", ""), AUTO_LABEL)
        self._restore_combo(self.composition, spec.get("composition_guide", ""),
                            spec.get("composition_guide_custom", ""), NO_GUIDE_LABEL)
        self.purpose.setCurrentIndex(max(0, self.purpose.findData(spec.get("purpose", ""))))
        self.aspect.setCurrentText(spec.get("aspect", ""))

        # A saved custom source is not in the list, so fall back to setting the
        # text rather than silently resetting the field to "(auto)".
        override = spec.get("overrides", {}).get("lighting", [])
        source = override[0] if override else ""
        index = self.lighting.findData(source)
        if index >= 0:
            self.lighting.setCurrentIndex(index)
        else:
            self.lighting.setCurrentText(source)

        for widget in widgets:
            widget.blockSignals(False)

        self._validate()
        self.changed.emit()

    @staticmethod
    def _restore_combo(combo, key, custom, empty_label):
        """Select `key`'s item, or show `custom` as typed text, or reset."""
        if custom:
            combo.setCurrentText(custom)
            return
        index = combo.findData(key)
        combo.setCurrentIndex(max(0, index))
        if index < 0:
            combo.setCurrentText(empty_label)

    def apply_partial(self, spec, fill_blanks_only=False):
        """Merge suggested fields over the current form, keeping the rest.

        With `fill_blanks_only` an existing value is never replaced — which is
        the precedence rule the rest of this app runs on, applied to the model:
        it fills what you left empty and leaves your own choices alone.
        """
        merged = self.spec()
        # spec() substitutes the placeholder subject; writing that back through
        # load_spec() would put the literal words "a person" in the box, which
        # then looks like something the user typed to everything downstream.
        if not self.subject.toPlainText().strip():
            merged.pop("subject", None)
        incoming = {k: v for k, v in spec.items() if v}
        if fill_blanks_only:
            filled = self.filled_keys()
            incoming = {k: v for k, v in incoming.items() if k not in filled}
        merged.update(incoming)
        self.load_spec(merged)
        return sorted(incoming)
