"""Ads category - the five-beat UGC advert, end to end.

  Brief       who it is for, where it runs, what feeling it targets
  Storyboard  the five beats as timed shots, with the gate beside them
  Variants    A/B on the hook, which is the only part worth testing first
  Checklist   the workflow checklist, auto-ticked where the app can actually tell
  Publishing  platform craft, reference only

The timeline strip on the Storyboard tab exists for one reason: the checklist
demands the product appear within 5-10 seconds, and that is the rule most easily
broken and least easily seen in a list of text.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
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

import ad_lint as al  # noqa: E402
import build_ad as ba  # noqa: E402
import realism_lint as rl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import AiSuggestionBadge, Badge, Card, GateTree, MutedLabel, TitleLabel  # noqa: E402
from ..workers import LlmTask  # noqa: E402


class Timeline(QWidget):
    """Where each beat sits, and where the 10-second line falls.

    A list of numbers hides the one failure that matters; a bar shows it.
    """

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = palette or {}
        self.shots = []
        self.seconds = 0
        self.limit = 10.0
        # Two bands: the blocks, then a clear strip beneath them for the marker
        # label. Sharing one band is what let the "10s" caption land on top of a
        # beat number.
        self.setMinimumHeight(58)
        self.setMaximumHeight(58)

    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.update()

    def set_ad(self, shots, seconds, limit=10.0):
        self.shots, self.seconds, self.limit = shots, seconds or 0, limit
        self.update()

    def paintEvent(self, event):
        if not self.shots or not self.seconds:
            return
        colours = self._palette
        accent = QColor(colours.get("primary", "#38BDF8"))
        ok = QColor(colours.get("success", "#34D399"))
        bad = QColor(colours.get("error", "#F87171"))
        muted = QColor(colours.get("text_muted", "#94A3B8"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = painter.fontMetrics()
        width, top, height = self.width(), 6, 22
        scale = width / float(self.seconds)

        for shot in self.shots:
            x = shot["start"] * scale
            w = max(shot["duration"] * scale - 2, 2)
            colour = QColor(accent if shot["key"] != "solution" else ok)
            colour.setAlpha(210 if shot["key"] == "solution" else 120)
            painter.fillRect(int(x), top, int(w), height, colour)

            # A number wider than its block would be drawn over the next beat,
            # so a block too narrow to hold one simply goes unlabelled. The bar
            # already says where the beat is; a digit in the wrong block lies.
            label = str(shot["n"])
            text_width = metrics.horizontalAdvance(label)
            if w >= text_width + 6:
                painter.setPen(muted)
                painter.drawText(
                    int(x + (w - text_width) / 2), top + height - 6, label)

        solution = next((s for s in self.shots if s["key"] == "solution"), None)
        late = solution is not None and solution["start"] > self.limit
        marker = int(min(self.limit, self.seconds) * scale)
        painter.setPen(bad if late else ok)
        painter.drawLine(marker, top - 4, marker, top + height + 4)

        # Its own band below the blocks, and clamped so it cannot run off
        # either edge when the marker sits at 0s or at the very end.
        caption = "{:.0f}s".format(self.limit)
        caption_width = metrics.horizontalAdvance(caption)
        x = min(max(0, marker - caption_width // 2), max(0, width - caption_width))
        painter.drawText(x, top + height + metrics.ascent() + 6, caption)
        painter.end()


class AdsView(QWidget):
    """Emits `generate_requested` with (jobs, provider_note) for the controller."""

    generate_requested = pyqtSignal(list)
    status = pyqtSignal(str)

    def __init__(self, bank, palette=None, parent=None):
        super().__init__(parent)
        self.bank = bank                    # the image/realism bank
        self.ad_bank = ba.load_bank()
        self._palette = palette or {}
        self.shots = []
        self.copy = {}
        self.images = {}            # shot index -> generated file
        self.status_by_shot = {}
        self.context = None                 # set by the controller: () -> spec dict
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setup_ui()
        self.rebuild()

    # -- construction ------------------------------------------------------ #
    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_brief_tab(), "Brief")
        self.tabs.addTab(self._build_storyboard_tab(), "Storyboard")
        self.tabs.addTab(self._build_variants_tab(), "Variants")
        self.tabs.addTab(self._build_checklist_tab(), "Checklist")
        self.tabs.addTab(self._build_publishing_tab(), "Publishing")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def _build_brief_tab(self):
        self.product = QLineEdit(placeholderText="LumaWash - a sulfate-free shampoo")
        self.audience = QPlainTextEdit()
        self.audience.setPlaceholderText(
            "women 25-40 with oily scalps who have tried drugstore and salon brands")
        self.audience.setFixedHeight(60)

        self.platform = QComboBox()
        for key, cfg in ba.platforms(self.ad_bank).items():
            self.platform.addItem(cfg["label"], key)
        self.platform.currentIndexChanged.connect(self.on_platform_changed)

        self.emotion = QComboBox()
        self.emotion.addItem("(none)", "")
        for key, cfg in ba.emotions(self.ad_bank).items():
            self.emotion.addItem(cfg["label"], key)
            self.emotion.setItemData(self.emotion.count() - 1, cfg["feeling"],
                                     Qt.ItemDataRole.ToolTipRole)

        self.seconds = QSpinBox(minimum=5, maximum=120)
        self.seconds.valueChanged.connect(self.rebuild)

        self.platform_note = MutedLabel("")

        self.draft_button = QPushButton("Draft the copy with AI")
        self.draft_button.setIcon(assets.icon("brief"))
        self.draft_button.setIconSize(assets.ICON_SIZE)
        self.draft_button.setToolTip(
            "Optional. Uses OpenRouter, and every reply is re-scored by the ad gate "
            "before it is accepted.")
        # set_status() only, like Brief's Critique tab and Compose's autofill -
        # a draft is applied to the script box automatically the moment it
        # comes back (see on_drafted below), so there is no separate payload
        # to hold behind an Apply button.
        self.draft_badge = AiSuggestionBadge("Drafting…")
        self.draft_badge.set_status("neutral", "not run")
        self.draft_button.clicked.connect(self.draft_copy)

        self.script = QPlainTextEdit()
        self.script.setPlaceholderText(
            "pain: ...\nrelatable: ...\nshift: ...\nsolution: ...\nproof: ...")
        self.script.textChanged.connect(self.on_script_edited)

        form = Card()
        form.body.addWidget(TitleLabel("Who, where and what feeling"))
        for label, widget in [("Product", self.product), ("Audience", self.audience),
                              ("Platform", self.platform), ("Emotion", self.emotion),
                              ("Length (s)", self.seconds)]:
            row = QHBoxLayout()
            caption = QLabel(label)
            # A flat 90 clipped "Emotion" once the column narrowed: the label
            # sat on its minimum and its own text needed 98. Take whichever is
            # larger so a font change cannot reintroduce it.
            caption.setMinimumWidth(max(90, caption.sizeHint().width()))
            row.addWidget(caption)
            row.addWidget(widget, 1)
            form.body.addLayout(row)
        form.body.addWidget(self.platform_note)

        draft_row = QHBoxLayout()
        draft_row.addWidget(self.draft_button)
        draft_row.addWidget(self.draft_badge)
        draft_row.addStretch(1)

        copy_card = Card()
        copy_card.body.addWidget(TitleLabel("The five beats"))
        copy_card.body.addLayout(draft_row)
        copy_card.body.addWidget(MutedLabel(
            "One line per beat, as \"key: text\". Beats 1-3 sell the feeling; beat 4 is "
            "where the product's specifics belong; beat 5 needs proof AND urgency."))
        copy_card.body.addWidget(self.script, 1)
        copy_card.setMinimumWidth(330)
        form.body.addStretch(1)

        # Stacked, the form and the script asked for more height than the tab
        # has and Qt answered by squashing both below their minimums - every
        # field 18px tall against a 34px minimum. Side by side they fit, and the
        # scroll area means a shorter window scrolls rather than crushing them.
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_scroll.setWidget(form)
        form_scroll.setMinimumWidth(320)
        form_scroll.setMaximumWidth(430)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(form_scroll)
        split.addWidget(copy_card)
        split.setChildrenCollapsible(False)
        split.setSizes([390, 520])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(split)
        self.on_platform_changed()
        return page

    def _build_storyboard_tab(self):
        self.timeline = Timeline(self._palette)
        self.timing_label = MutedLabel("")

        self.beat_tree = QTreeWidget()
        self.beat_tree.setColumnCount(5)
        self.beat_tree.setHeaderLabels(["", "BEAT", "TIME", "COPY / SHOT", "IMAGE"])
        self.beat_tree.setIconSize(QSize(34, 46))
        self.beat_tree.setRootIsDecorated(False)
        self.beat_tree.setAlternatingRowColors(True)

        self.lint_badge = Badge("0/9", "neutral")
        # ad_lint's own detail strings run 50-70+ characters ("beat 5 has
        # proof but no urgency - add a deadline or an offer") - genuinely too
        # long for a fixed-width tree column, unlike Sound's or Videos' own
        # gate rows. GateTree's row + detail-label shape is for exactly this.
        self.gate = GateTree()

        self.generate_button = QPushButton("Generate all five shots")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.clicked.connect(self.request_generate)
        self.identity_note = MutedLabel("")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)

        board = Card()
        board.body.addWidget(TitleLabel("Storyboard"))
        board.body.addWidget(self.timeline)
        board.body.addWidget(self.timing_label)
        board.body.addWidget(self.beat_tree, 1)

        gate = Card()
        header = QHBoxLayout()
        header.addWidget(TitleLabel("Will this ad work?"))
        header.addWidget(self.lint_badge)
        header.addStretch(1)
        gate.body.addLayout(header)
        gate.body.addWidget(self.gate, 1)
        gate.body.addWidget(self.identity_note)
        gate.body.addWidget(self.generate_button)
        gate.body.addWidget(self.progress)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.COLUMN_GAP)
        layout.addWidget(board, 1)
        layout.addWidget(gate)
        return page

    def _build_variants_tab(self):
        self.hook_list = QPlainTextEdit()
        self.hook_list.setPlaceholderText(
            "One competing hook per line.\n\n"
            "Your hair gets greasy 5 hours after washing it.\n"
            "You're shedding more hair in the shower than your dog.\n"
            "You bought a expensive shampoo and it made it worse.")
        self.hook_tree = QTreeWidget()
        self.hook_tree.setColumnCount(3)
        self.hook_tree.setHeaderLabels(["#", "HOOK", "VERDICT"])
        self.hook_tree.setRootIsDecorated(False)
        self.hook_tree.setAlternatingRowColors(True)
        check = QPushButton("Check every hook")
        check.clicked.connect(self.check_hooks)

        card = Card()
        card.body.addWidget(TitleLabel("A/B the hook"))
        card.body.addWidget(MutedLabel(
            "The hook is the only part worth testing first - everything after it is "
            "only seen by people the hook already kept. The body stays fixed."))
        card.body.addWidget(self.hook_list)
        card.body.addWidget(check)
        card.body.addWidget(self.hook_tree, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        return page

    def _build_checklist_tab(self):
        self.checklist_tree = QTreeWidget()
        self.checklist_tree.setColumnCount(3)
        self.checklist_tree.setHeaderLabels(["", "ITEM", "HOW"])
        self.checklist_tree.setAlternatingRowColors(True)

        card = Card()
        card.body.addWidget(TitleLabel("AI advertisement workflow checklist"))
        card.body.addWidget(MutedLabel(
            "Ticked rows are checked by the app. Open rows are yours to judge - the app "
            "cannot tell whether a client approved something or whether an image is "
            "scroll-stopping, and pretending otherwise would make the whole list worthless."))
        card.body.addWidget(self.checklist_tree, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        return page

    def _build_publishing_tab(self):
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["TOPIC", "WHAT TO DO"])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setWordWrap(True)
        publishing = self.ad_bank.get("publishing", {})
        for item in publishing.get("items", []):
            QTreeWidgetItem(tree, ["", item["topic"], item["text"]][1:])
        tree.setColumnWidth(0, 130)

        card = Card()
        card.body.addWidget(TitleLabel("Publishing"))
        card.body.addWidget(MutedLabel(publishing.get("note", "")))
        card.body.addWidget(tree, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        return page

    # -- state ------------------------------------------------------------- #
    def platform_key(self):
        return self.platform.currentData() or "tiktok"

    def on_platform_changed(self):
        cfg = ba.platforms(self.ad_bank).get(self.platform_key(), {})
        lengths = cfg.get("lengths", [15, 30])
        self.seconds.blockSignals(True)
        self.seconds.setRange(min(lengths), max(lengths))
        self.seconds.setValue(cfg.get("default_length", min(lengths)))
        self.seconds.blockSignals(False)
        self.platform_note.setText("{}  -  {}  -  {}".format(
            cfg.get("aspect", ""), cfg.get("tone", ""), cfg.get("note", "")))
        self.rebuild()

    def on_script_edited(self):
        self.copy = self.parse_script(self.script.toPlainText())
        self.rebuild()

    @staticmethod
    def parse_script(text):
        copy = {}
        for line in (text or "").splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            if key in {b["key"] for b in ba.beats(ba.load_bank())} and value.strip():
                copy[key] = value.strip()
        return copy

    def base_spec(self):
        spec = dict(self.context() if self.context else {})
        spec.pop("reference", None)
        spec.pop("lock_identity", None)
        spec.setdefault("subject", "a person")
        return spec

    def set_copy(self, copy):
        """Fill the script box from a dict, without re-triggering a parse storm."""
        self.script.blockSignals(True)
        self.script.setPlainText("\n".join(
            "{}: {}".format(b["key"], copy.get(b["key"], "")) for b in ba.beats(self.ad_bank)))
        self.script.blockSignals(False)
        self.copy = dict(copy)
        self.rebuild()

    # -- the gate ---------------------------------------------------------- #
    def rebuild(self):
        if not hasattr(self, "beat_tree"):
            return
        platform = self.platform_key()
        seconds = self.seconds.value()
        self.shots = ba.compose_ad(self.ad_bank, self.base_spec(), platform, seconds,
                                   copy=self.copy, image_bank=self.bank)

        self.beat_tree.clear()
        for shot in self.shots:
            item = QTreeWidgetItem(self.beat_tree, [
                str(shot["n"]),
                shot["label"],
                "{:.1f}-{:.1f}s".format(shot["start"], shot["end"]),
                shot["copy"] or shot["role"],
                self.status_by_shot.get(shot["n"] - 1, ""),
            ])
            path = self.images.get(shot["n"] - 1)
            if path and Path(path).exists():
                item.setIcon(1, QIcon(path))
                item.setToolTip(1, path)
            if not shot["copy"]:
                item.setForeground(3, QColor(self._palette.get("text_muted", "#94A3B8")))
            item.setToolTip(3, "{}\n\nshot: {}\nmove: {}".format(
                shot["must_do"], shot["spec"].get("shot", ""), shot["movement"] or "none"))
        self.beat_tree.setColumnWidth(0, 26)
        self.beat_tree.setColumnWidth(1, 190)
        self.beat_tree.setColumnWidth(2, 84)
        self.beat_tree.setColumnWidth(4, 64)

        limit = self.ad_bank.get("timing", {}).get("product_by", 10.0)
        self.timeline.set_ad(self.shots, seconds, limit)
        product_at = ba.product_starts_at(self.ad_bank, seconds, platform)
        self.timing_label.setText(
            "Product appears at {:.1f}s of {}s. The checklist wants it by {:.0f}s.".format(
                product_at, seconds, limit))

        results = al.lint(self.ad_bank, self.shots, platform, seconds)
        got, total = al.score(results)
        self.gate.set_checks([
            {"key": key, "label": label, "passed": passed, "fix": detail, "ok_text": detail}
            for key, label, passed, detail in results
        ])
        self.lint_badge.set_status("success" if got == total else "danger",
                                   "{}/{}".format(got, total))
        self.passing = got == total

        self.identity_note.setText(
            "Beat 1 creates the presenter; beats 2-5 lock to that face. Reference images "
            "are Kie-only, so on another provider these would be five different people.")
        self.refresh_checklist(results)

    def checklist_state(self, results):
        """What the app can honestly tell, beyond the lint rows themselves."""
        state = {key: passed for key, _, passed, _ in results}
        state["audience"] = bool(self.audience.toPlainText().strip())
        state["copy"] = len(self.copy) == len(ba.beats(self.ad_bank))
        state["shots"] = all(s["spec"].get("shot") and s["movement"] for s in self.shots)
        state["realism"] = all(
            len(rl.lint(s["prompt"].lower(), self.bank)[0]) == 8 for s in self.shots)
        # Beats 2-5 are built to lock to beat 1; whether the provider can carry
        # the reference is the controller's business, not this panel's.
        state["identity"] = all(s["key"] != "pain" for s in self.shots[1:])
        state["variants"] = len(
            [l for l in self.hook_list.toPlainText().splitlines() if l.strip()]) >= 2
        return state

    def refresh_checklist(self, results):
        state = self.checklist_state(results)
        self.checklist_tree.clear()
        for section in self.ad_bank.get("checklist", []):
            parent = QTreeWidgetItem(self.checklist_tree, ["", section["section"], ""])
            parent.setExpanded(True)
            for item in section["items"]:
                rule = item.get("rule")
                # An "auto" tag the app cannot actually evaluate is downgraded to
                # manual rather than shown as checked-but-blank. A checklist that
                # claims to have verified something it has not is worse than no
                # checklist.
                known = item.get("check") == "auto" and rule in state
                mark = ("OK" if state[rule] else "!") if known else ""
                how = "checked by the app" if known else "yours to judge"
                child = QTreeWidgetItem(parent, [mark, item["text"], how])
                if known:
                    child.setForeground(0, QColor(self._palette.get(
                        "success" if state[rule] else "error",
                        "#34D399" if state[rule] else "#F87171")))
        self.checklist_tree.setColumnWidth(0, 30)
        self.checklist_tree.setColumnWidth(1, 420)

    def check_hooks(self):
        """Score each competing hook on its own, against beat 1's rules."""
        lines = [l.strip() for l in self.hook_list.toPlainText().splitlines() if l.strip()]
        platform = self.platform_key()
        seconds = self.seconds.value()
        self.hook_tree.clear()
        for index, hook in enumerate(lines, 1):
            copy = dict(self.copy)
            copy["pain"] = hook
            shots = ba.compose_ad(self.ad_bank, self.base_spec(), platform, seconds,
                                  copy=copy, image_bank=self.bank)
            results = al.lint(self.ad_bank, shots, platform, seconds)
            emotion = next((d for k, _, p, d in results if k == "emotion" and not p), "")
            hook_row = next((d for k, _, p, d in results if k == "hook"), "")
            verdict = emotion or hook_row
            row = QTreeWidgetItem(self.hook_tree, [str(index), hook, verdict])
            # Comparing several hooks side by side is the point of this tree,
            # so it stays a tree rather than GateTree's one-at-a-time detail
            # panel - but the same long ad_lint sentences still don't fit the
            # column, so the full text is at least a hover away from clipped.
            row.setToolTip(2, verdict)
        self.hook_tree.setColumnWidth(0, 30)
        self.hook_tree.setColumnWidth(1, 420)
        self.status.emit("Checked {} hook(s)".format(len(lines)))

    # -- the optional text model ------------------------------------------- #
    def draft_copy(self):
        """Ask OpenRouter for the five beats. The gate decides, not the model."""
        product = self.product.text().strip()
        audience = self.audience.toPlainText().strip()
        if not product:
            self.status.emit("Say what the product is first")
            return
        self.draft_badge.thinking()
        self.draft_button.setEnabled(False)
        task = LlmTask("ad_copy", self.ad_bank, self.bank, product, audience,
                       self.platform_key(), self.emotion.currentData() or None,
                       self.seconds.value(), self.base_spec())
        task.signals.finished.connect(self.on_drafted)
        task.signals.failed.connect(self.on_draft_failed)
        task.signals.done.connect(lambda _a: self.draft_button.setEnabled(True))
        self.pool.start(task)

    def on_drafted(self, _action, result):
        copy = result.get("copy") or {}
        if copy:
            self.set_copy(copy)
        if result.get("accepted"):
            self.draft_badge.set_status("success", "accepted {}/{}".format(
                result.get("score"), result.get("total")))
            self.status.emit("Draft accepted - it passed the ad gate")
        else:
            # Shown, not discarded: a near-miss is a useful starting point, and
            # the failing rows say exactly what to change.
            self.draft_badge.set_status("warning", "{}/{}".format(
                result.get("score"), result.get("total")))
            self.status.emit(result.get("reason", "The draft did not pass")[:160])

    def on_draft_failed(self, _action, reason):
        self.draft_badge.set_status("danger", "failed")
        self.status.emit(reason[:160])

    def request_generate(self):
        """Hand the controller one job per beat, in order."""
        if not self.shots:
            self.status.emit("Nothing to generate yet")
            return
        self.images = {}
        self.status_by_shot = {}
        jobs = [{"index": i, "prompt": shot["prompt"], "beat": shot["key"],
                 "out_name": "ad-{}-{}.png".format(shot["n"], shot["key"]),
                 "spec": shot["spec"]}
                for i, shot in enumerate(self.shots)]
        for index in range(len(jobs)):
            self._set_shot_status(index, "queued…")
        # No success message here: whether these are queued or refused is the
        # controller's call, and an optimistic message would overwrite its answer.
        self.generate_requested.emit(jobs)

    # -- batch feedback ------------------------------------------------------ #
    # These did not exist. Every generated ad shot was handed to the Images
    # Variants grid, which silently drops any index it has no tile for - so the
    # five shots were written to disk and never shown anywhere.
    def set_busy(self, busy, total=0):
        self.generate_button.setEnabled(not busy and bool(self.shots))
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, total)
            self.progress.setValue(0)

    def set_progress(self, completed, total):
        self.progress.setRange(0, total)
        self.progress.setValue(completed)

    def on_item_finished(self, index, path):
        self.images[index] = str(path)
        self._set_shot_status(index, "ready")
        item = self.beat_tree.topLevelItem(index)
        if item is not None:
            item.setIcon(1, QIcon(str(path)))
            item.setToolTip(1, str(path))

    def on_item_failed(self, index, reason):
        self._set_shot_status(index, "failed")
        self.status.emit(reason[:160])

    def _set_shot_status(self, index, text):
        self.status_by_shot[index] = text
        item = self.beat_tree.topLevelItem(index)
        if item is not None:
            item.setText(4, text)

    def set_palette_tokens(self, palette):
        self._palette = palette or {}
        self.timeline.set_palette_tokens(palette)
        # GateTree colours its own rows from whatever palette it was last
        # given, defaulting to the dark theme's hex values if never told
        # otherwise - fine in dark, wrong in light. rebuild() below re-renders
        # its rows, but only this call tells it which palette to render them in.
        self.gate.set_palette_tokens(self._palette)
        self.rebuild()

    def refresh(self):
        self.rebuild()
