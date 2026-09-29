"""Static ad - the half of Ads that is one frame rather than five beats.

  Idea            the human insight, the strategic idea, the product, the tier
  Routes          two or more creative territories, each with its own device
  Art direction   the type layer: what leads, how much frame, where, in what order
  Critique        the ten creative-direction commands, as a gate

WHY THIS IS A SUB-SECTION AND NOT AN ELEVENTH RAIL ENTRY. `Ctrl+1..9` then
`Ctrl+0` is generated from `NAV_ITEMS[:10]` (main_window.py), because
QKeySequence cannot parse a multi-digit token - an eleventh section would be
the only one with no shortcut. A video ad and a static ad are also the same
job at two lengths, so they belong in one section.

WHAT IS DIFFERENT FROM THE VIDEO AD. `ads.py` scores a SCRIPT - five beats,
timings, a hook window. This scores an IDEA, and most of what makes an idea
good cannot be counted. So the gate has eight checked rows and two the user
must judge, and command 10 cannot say "ready" while either is untouched. That
is deliberate: an honest checklist lets the unjudgeable rows hold up the
verdict, or they are decoration.

THREE STATES, NOT TWO, in the gate: green means a rule verified it, amber
means a human asserted it, red means nobody has. GateTree already draws amber
for a row that passed but still has something to say; `creative_ad_lint`
marks every manual row that way.

This view composes and scores prompts; it does not spend money. The composed
prompts go to the clipboard, the same handoff Compose's Midjourney button and
Videos' "Copy for Kling" already use.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
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

import build_creative_ad as bca  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_typography as bt  # noqa: E402
import creative_ad_lint as cal  # noqa: E402
import realism_lint as rl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Badge, Card, GateTree, MutedLabel, TitleLabel  # noqa: E402

# Long enough that typing a sentence does not recompose on every keystroke,
# short enough that the gate feels live. Compose uses the same shape.
REBUILD_MS = 250

NO_LOCKUP = "(none)"

TOOLTIP = Qt.ItemDataRole.ToolTipRole


class StaticAdView(QWidget):
    """Emits `status`. Composes gated prompts; does not generate."""

    status = pyqtSignal(str)

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.bank = cal.load_bank()
        self.type_bank = bt.load_bank()
        self.image_bank = bp.load_bank()
        self._palette = palette or {}
        self._routes = []
        self._shots = []
        self._rows = []
        self.product_reference_path = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.rebuild)

        self.setup_ui()
        self.rebuild()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_idea_tab(), "Idea")
        self.tabs.addTab(self._build_routes_tab(), "Routes")
        self.tabs.addTab(self._build_art_tab(), "Art direction")
        self.tabs.addTab(self._build_critique_tab(), "Critique")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        layout.addWidget(MutedLabel(
            "One frame, not five beats. Write the insight, argue an idea, then "
            "make at least two routes from different territories - the gate "
            "checks eight of the ten commands and leaves two to you."))
        layout.addWidget(self.tabs)

    def _scrolled(self, inner):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(inner)
        return area

    def _build_idea_tab(self):
        card = Card()
        card.body.addWidget(TitleLabel("The idea"))

        self.product = QLineEdit()
        self.product.setPlaceholderText(
            "LumaWash shampoo, 250ml amber bottle - name the label text exactly")
        self.product.textChanged.connect(self.schedule_rebuild)

        self.insight = QPlainTextEdit()
        self.insight.setPlaceholderText(
            "You do not want a cleaner house, you want ten minutes where nobody "
            "needs anything from you")
        self.insight.setFixedHeight(64)
        self.insight.textChanged.connect(self.schedule_rebuild)

        self.idea = QPlainTextEdit()
        self.idea.setPlaceholderText(
            "Sell the ten minutes back, not the work done")
        self.idea.setFixedHeight(64)
        self.idea.textChanged.connect(self.schedule_rebuild)

        self.tier = QComboBox()
        for key, note in cal.tiers(self.bank).items():
            self.tier.addItem(key, key)
            self.tier.setItemData(self.tier.count() - 1, note, TOOLTIP)
        self.tier.setCurrentIndex(min(1, self.tier.count() - 1))
        self.tier.currentIndexChanged.connect(self.schedule_rebuild)

        form = QFormLayout()
        form.addRow("Product", self.product)
        form.addRow("Insight", self.insight)
        form.addRow("Strategic idea", self.idea)
        form.addRow("Tier", self.tier)
        card.body.addLayout(form)

        card.body.addWidget(MutedLabel(
            "The insight is what is true about the person before the product "
            "exists; the idea is what you do about it. Restating one as the "
            "other is the commonest failure, and command 2 checks for it."))

        self.product_reference_label = MutedLabel("Product photo: none")
        choose = QPushButton("Choose product photo...")
        choose.setProperty("class", "ghost")
        choose.clicked.connect(self.choose_product_reference)
        clear = QPushButton("Clear")
        clear.setProperty("class", "ghost")
        clear.clicked.connect(self.clear_product_reference)
        row = QHBoxLayout()
        row.addWidget(choose)
        row.addWidget(clear)
        row.addStretch(1)
        card.body.addWidget(self.product_reference_label)
        card.body.addLayout(row)
        card.body.addStretch(1)
        return self._scrolled(card)

    def _build_routes_tab(self):
        card = Card()
        card.body.addWidget(TitleLabel("Creative routes"))
        card.body.addWidget(MutedLabel(
            "Command 9 counts DISTINCT territories, not shots - two routes from "
            "one territory are one idea photographed twice."))

        self.route_tree = QTreeWidget()
        self.route_tree.setColumnCount(3)
        self.route_tree.setHeaderLabels(["TERRITORY", "NAME", "DEVICE"])
        self.route_tree.setRootIsDecorated(False)
        self.route_tree.setAlternatingRowColors(True)
        self.route_tree.setColumnWidth(0, 170)
        self.route_tree.setColumnWidth(1, 150)
        self.route_tree.itemSelectionChanged.connect(self.on_route_selected)
        card.body.addWidget(self.route_tree, 1)

        self.territory = QComboBox()
        for key, cfg in cal.routes(self.bank).items():
            self.territory.addItem("{} - {}".format(key, cfg["label"]), key)
            self.territory.setItemData(self.territory.count() - 1, cfg["asks"], TOOLTIP)
        self.territory.currentIndexChanged.connect(self.on_territory_changed)

        self.route_name = QLineEdit()
        self.route_name.setPlaceholderText("The clean ring")

        self.route_device = QPlainTextEdit()
        self.route_device.setPlaceholderText(
            "The visual idea itself - and the product has to be load-bearing in "
            "it, not merely present in the room")
        self.route_device.setFixedHeight(64)

        self.route_rationale = QPlainTextEdit()
        self.route_rationale.setPlaceholderText("Why this territory suits this insight")
        self.route_rationale.setFixedHeight(48)

        self.route_has_person = QCheckBox("This route has a person in it")
        self.route_has_person.setToolTip(
            "Keeps the portrait vocabulary. Left unticked, the prompt is "
            "composed with surface vocabulary instead - otherwise a shelf gets "
            "described as having realistic skin texture.")

        form = QFormLayout()
        form.addRow("Territory", self.territory)
        form.addRow("Name", self.route_name)
        form.addRow("Device", self.route_device)
        form.addRow("Why", self.route_rationale)
        form.addRow("", self.route_has_person)
        card.body.addLayout(form)

        use_example = QPushButton("Use this territory's example device")
        use_example.setProperty("class", "ghost")
        use_example.clicked.connect(self.use_example_device)
        add = QPushButton("Add route")
        add.setProperty("class", "primary")
        add.clicked.connect(self.add_route)
        update = QPushButton("Update selected")
        update.setProperty("class", "ghost")
        update.clicked.connect(self.update_route)
        remove = QPushButton("Remove selected")
        remove.setProperty("class", "ghost")
        remove.clicked.connect(self.remove_route)

        buttons = QHBoxLayout()
        for button in (use_example, add, update, remove):
            buttons.addWidget(button)
        buttons.addStretch(1)
        card.body.addLayout(buttons)
        return self._scrolled(card)

    def _build_art_tab(self):
        card = Card()
        card.body.addWidget(TitleLabel("Art direction"))
        card.body.addWidget(MutedLabel(
            "A static ad is a photograph with words on it. This is the only "
            "vocabulary in the app for the words."))

        self.type_combos = {}
        form = QFormLayout()
        for group, label in (("dominance", "What leads"), ("ratio", "Type share"),
                             ("zone", "Type zone"), ("lockup", "Logo"),
                             ("reading_order", "Reading order")):
            combo = QComboBox()
            combo.addItem(NO_LOCKUP, None)
            for key, option in bt.options(self.type_bank, group).items():
                combo.addItem(option["label"], key)
                combo.setItemData(combo.count() - 1, option["note"], TOOLTIP)
            combo.currentIndexChanged.connect(self.schedule_rebuild)
            self.type_combos[group] = combo
            form.addRow(label, combo)

        self.headline = QLineEdit()
        self.headline.setPlaceholderText("Ten minutes back")
        self.headline.setToolTip(
            "Checked against the ratio's own word cap. Image models garble long "
            "strings, so a headline over the cap warns rather than silently "
            "rendering as mush.")
        self.headline.textChanged.connect(self.schedule_rebuild)
        form.addRow("Headline", self.headline)
        card.body.addLayout(form)

        self.restraint_boxes = {}
        card.body.addWidget(MutedLabel("Copy discipline (stackable)"))
        for key, option in bt.options(self.type_bank, "restraint").items():
            box = QCheckBox(option["label"])
            box.setToolTip(option["note"])
            box.stateChanged.connect(self.schedule_rebuild)
            self.restraint_boxes[key] = box
            card.body.addWidget(box)

        self.type_phrase = QPlainTextEdit()
        self.type_phrase.setReadOnly(True)
        self.type_phrase.setFixedHeight(80)
        self.type_phrase.setPlaceholderText("The composed type direction appears here.")
        card.body.addWidget(self.type_phrase)

        self.type_warning = MutedLabel("")
        card.body.addWidget(self.type_warning)
        card.body.addStretch(1)
        return self._scrolled(card)

    def _build_critique_tab(self):
        card = Card()
        head = QHBoxLayout()
        head.addWidget(TitleLabel("The ten commands"))
        self.score_badge = Badge("0/10", "neutral")
        head.addWidget(self.score_badge)
        head.addStretch(1)
        card.body.addLayout(head)

        self.gate = GateTree()
        self.gate.set_palette_tokens(self._palette)
        card.body.addWidget(self.gate, 1)

        # The two rows no rule can judge. They are checkboxes rather than
        # anything cleverer because the honest interaction is a person saying
        # "I looked at this" - and command 10 refuses to pass until they do.
        card.body.addWidget(MutedLabel(
            "Yours to judge - command 10 cannot say campaign-ready until both "
            "are ticked:"))
        self.manual_boxes = {}
        for command in cal.commands(self.bank):
            if command.get("check") != "manual":
                continue
            box = QCheckBox("{}. {}".format(command["n"], command["label"]))
            box.setToolTip(command["asks"] + "\n\n" + command["why"])
            box.stateChanged.connect(self.schedule_rebuild)
            self.manual_boxes[command["key"]] = box
            card.body.addWidget(box)

        self.prompts = QPlainTextEdit()
        self.prompts.setReadOnly(True)
        self.prompts.setPlaceholderText(
            "The composed prompts appear here, one per route, each scored by the "
            "same 8/8 realism gate Compose uses.")
        card.body.addWidget(self.prompts, 1)

        copy_button = QPushButton("Copy prompts")
        copy_button.setProperty("class", "primary")
        copy_button.setIcon(assets.icon("copy"))
        copy_button.setIconSize(assets.ICON_SIZE)
        copy_button.clicked.connect(self.copy_prompts)
        row = QHBoxLayout()
        row.addWidget(copy_button)
        row.addStretch(1)
        card.body.addLayout(row)
        return self._scrolled(card)

    # -- routes ------------------------------------------------------------ #
    def on_territory_changed(self):
        key = self.territory.currentData()
        cfg = cal.routes(self.bank).get(key, {})
        self.territory.setToolTip(cfg.get("asks", ""))

    def use_example_device(self):
        key = self.territory.currentData()
        cfg = cal.routes(self.bank).get(key, {})
        example = cfg.get("example_device", "")
        if example:
            self.route_device.setPlainText(example)
            self.status.emit("Filled the device from this territory's example")

    def _form_route(self):
        return {
            "key": self.territory.currentData(),
            "name": self.route_name.text().strip() or self.territory.currentData(),
            "device": self.route_device.toPlainText().strip(),
            "rationale": self.route_rationale.toPlainText().strip(),
            "tier": self.tier.currentData(),
            "has_person": self.route_has_person.isChecked(),
        }

    def add_route(self):
        route = self._form_route()
        if not route["device"]:
            self.status.emit("A route needs a device - the device IS the idea")
            return
        self._routes.append(route)
        self.refresh_routes()
        self.schedule_rebuild()
        self.status.emit("Added route '{}'".format(route["name"]))

    def _selected_index(self):
        items = self.route_tree.selectedItems()
        if not items:
            return None
        return self.route_tree.indexOfTopLevelItem(items[0])

    def update_route(self):
        index = self._selected_index()
        if index is None:
            self.status.emit("Select a route to update")
            return
        route = self._form_route()
        if not route["device"]:
            self.status.emit("A route needs a device")
            return
        self._routes[index] = route
        self.refresh_routes()
        self.schedule_rebuild()
        self.status.emit("Updated route '{}'".format(route["name"]))

    def remove_route(self):
        index = self._selected_index()
        if index is None:
            self.status.emit("Select a route to remove")
            return
        removed = self._routes.pop(index)
        self.refresh_routes()
        self.schedule_rebuild()
        self.status.emit("Removed route '{}'".format(removed["name"]))

    def on_route_selected(self):
        index = self._selected_index()
        if index is None:
            return
        route = self._routes[index]
        position = self.territory.findData(route["key"])
        if position >= 0:
            self.territory.setCurrentIndex(position)
        self.route_name.setText(route["name"])
        self.route_device.setPlainText(route["device"])
        self.route_rationale.setPlainText(route.get("rationale", ""))
        self.route_has_person.setChecked(bool(route.get("has_person")))

    def refresh_routes(self):
        self.route_tree.clear()
        for route in self._routes:
            QTreeWidgetItem(self.route_tree,
                            [route["key"], route["name"], route["device"][:90]])

    # -- the product photo -------------------------------------------------- #
    def choose_product_reference(self):
        start = str(assets.IMAGES_DIR if assets.IMAGES_DIR.exists() else ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose the product photo", start,
            "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.product_reference_path = path
            self.product_reference_label.setText(
                "Product photo: {}".format(Path(path).name))
            self.schedule_rebuild()

    def clear_product_reference(self):
        self.product_reference_path = None
        self.product_reference_label.setText("Product photo: none")
        self.schedule_rebuild()

    # -- composing and scoring ---------------------------------------------- #
    def typography(self):
        out = {group: combo.currentData() for group, combo in self.type_combos.items()}
        out["restraint"] = [key for key, box in self.restraint_boxes.items()
                            if box.isChecked()]
        out["headline"] = self.headline.text().strip()
        return {k: v for k, v in out.items() if v}

    def brief(self):
        return {
            "product": self.product.text().strip(),
            "product_reference": self.product_reference_path,
            "insight": self.insight.toPlainText().strip(),
            "idea": self.idea.toPlainText().strip(),
            "tier": self.tier.currentData(),
            "typography": self.typography(),
            "routes": [dict(r) for r in self._routes],
        }

    def ticked(self):
        return [key for key, box in self.manual_boxes.items() if box.isChecked()]

    def schedule_rebuild(self):
        self._timer.start(REBUILD_MS)

    def rebuild(self):
        # Stop a pending run first: rebuild() replaces the composed state
        # wholesale, so a timer that fires afterwards would recompose from the
        # same inputs for nothing. ComposeView learned this the hard way - a
        # pending rebuild there silently reverted an adopted prompt.
        self._timer.stop()
        brief = self.brief()

        self.type_warning.setText("")
        self.type_phrase.setPlainText("")
        by_layer = {}
        if brief["typography"]:
            try:
                by_layer, warnings = bt.compose_typography(
                    self.type_bank, **{
                        k: v for k, v in brief["typography"].items()
                        if k in ("dominance", "ratio", "zone", "lockup",
                                 "reading_order", "restraint", "headline")})
                self.type_phrase.setPlainText(bt.phrase_for(by_layer))
                if warnings:
                    self.type_warning.setText(warnings[0])
            except bt.TypographyError as exc:
                self.type_warning.setText(str(exc))

        self._shots = []
        try:
            ad, _warnings = bca.build(self.bank, self.image_bank, brief)
            self._shots = ad["shots"]
        except (bca.BriefError, bt.TypographyError):
            # Not an error to report loudly - an incomplete brief is the normal
            # state while you are filling it in. The gate below says what is
            # missing, in the framework's own words.
            ad = dict(brief, shots=[])

        self.refresh_gate(ad)
        self.refresh_prompts()

    def refresh_gate(self, ad):
        rows = cal.lint(self.bank, ad, self.ticked())
        # Kept so anything that needs the verdict reads the same rows the tree
        # is showing, rather than re-linting or scraping the widget.
        self._rows = rows
        self.gate.set_checks(cal.rows_for_gate(rows))
        got, total = cal.score(rows)
        status = "success" if got == total else ("warning" if got >= total - 2 else "danger")
        self.score_badge.set_status(status, "{}/{}".format(got, total))

    def refresh_prompts(self):
        if not self._shots:
            self.prompts.setPlainText("")
            return
        blocks = []
        for shot in self._shots:
            present, _m, banned, _w, _n = rl.lint(
                shot["prompt"].lower(), self.image_bank)
            blocks.append("=== {} ({})  {}/8{}\n{}".format(
                shot["name"], shot["route"], len(present),
                "  BANNED: " + ", ".join(banned) if banned else "",
                shot["prompt"]))
        self.prompts.setPlainText("\n\n".join(blocks))

    def copy_prompts(self):
        text = self.prompts.toPlainText().strip()
        if not text:
            self.status.emit("Nothing composed yet - add a product and two routes")
            return
        QGuiApplication.clipboard().setText(text)
        self.status.emit("Copied {} prompt(s)".format(len(self._shots)))

    # -- theming ------------------------------------------------------------ #
    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.gate.set_palette_tokens(self._palette)

    def refresh(self):
        self.rebuild()
