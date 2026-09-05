"""Variants view — sample several seeds, generate them concurrently, pick a winner.

This is the real iteration loop: you do not perfect one prompt, you sample and
select. Picking a winner is also the cheapest possible rating signal, so it
feeds the same history the Insights view reads.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import history as hist  # noqa: E402
import realism_lint as rl  # noqa: E402

from .. import assets, tokens as T  # noqa: E402
from ..widgets import Card, MutedLabel, ResultCard, TitleLabel  # noqa: E402

COLUMNS = 3


class VariantsView(QWidget):
    generate_requested = pyqtSignal(list)   # [(index, prompt, out_name, references)]
    cancel_requested = pyqtSignal()
    status = pyqtSignal(str)
    seed_adopted = pyqtSignal(int)

    def __init__(self, bank, parent=None):
        super().__init__(parent)
        self.bank = bank
        self.spec_provider = None      # set by the controller
        self.cards = {}
        self.entries = {}
        self.prompts = {}
        self.selected = None
        self.setup_ui()

    def setup_ui(self):
        self.count = QSpinBox(minimum=2, maximum=12, value=6)
        self.count.setToolTip("How many seeds to sample")

        self.build_button = QPushButton("Build prompts")
        self.build_button.clicked.connect(self.build_variants)

        self.generate_button = QPushButton("Generate all")
        self.generate_button.setProperty("class", "primary")
        self.generate_button.setIcon(assets.icon("generate"))
        self.generate_button.setIconSize(assets.ICON_SIZE)
        self.generate_button.clicked.connect(self.request_generate)
        self.generate_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "danger")
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.cancel_button.setEnabled(False)

        self.adopt_button = QPushButton("Pick as winner")
        self.adopt_button.clicked.connect(self.adopt_selected)
        self.adopt_button.setEnabled(False)

        controls = QHBoxLayout()
        controls.setSpacing(T.SPACE["sm"])
        controls.addWidget(QLabel("Seeds"))
        controls.addWidget(self.count)
        controls.addWidget(self.build_button)
        controls.addWidget(self.generate_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch(1)
        controls.addWidget(self.adopt_button)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(T.COLUMN_GAP)
        self.grid.setContentsMargins(0, 0, 0, 0)
        # Equal columns by construction. Without this the columns are sized from
        # their contents' hints, so a single wider image made its whole column
        # wider than the other two — the "seeds 3 and 6 are bigger" symptom,
        # both of those being column index 2.
        for column in range(COLUMNS):
            self.grid.setColumnStretch(column, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_host)

        self.hint = MutedLabel(
            "Build prompts from consecutive seeds, generate them together, then pick the one "
            "that looks most real. Picking records a 5-star outcome and adopts that seed."
        )

        card = Card()
        card.body.setSpacing(T.SPACE["md"])
        card.body.addWidget(TitleLabel("Variant sampling"))
        card.body.addWidget(self.hint)
        card.body.addLayout(controls)
        card.body.addWidget(self.progress)
        card.body.addWidget(scroll, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)

    # -- building ---------------------------------------------------------- #
    def clear_grid(self):
        for card in self.cards.values():
            card.setParent(None)
        # Drop the row stretches too: a row left stretching after a smaller
        # batch would hold open space no card occupies.
        for row in range(self.grid.rowCount()):
            self.grid.setRowStretch(row, 0)
        self.cards, self.entries, self.prompts = {}, {}, {}
        self.selected = None
        self.adopt_button.setEnabled(False)

    def build_variants(self):
        if self.spec_provider is None:
            return
        spec, detailed, weights = self.spec_provider()
        error = bp.validate_shot(self.bank, spec.get("shot"))
        if error:
            self.status.emit(error)
            return

        self.clear_grid()
        base_seed = spec.get("seed", 0)
        for index in range(self.count.value()):
            seed = base_seed + index
            variant = dict(spec, seed=seed)
            prompt, layers = bp.compose(self.bank, variant, detailed=detailed, weights=weights)
            present, _, banned, _, _ = rl.lint(prompt.lower(), self.bank)
            score = len(present)
            passed = score == 8 and not banned

            entry_id = hist.append(variant, prompt, layers, score, passed, detailed)
            self.entries[index] = entry_id
            self.prompts[index] = prompt

            card = ResultCard(index, "seed {} · {}/8".format(seed, score))
            card.set_status("neutral", "queued")
            card.seed = seed
            card.clicked.connect(self.select_card)
            card.rated.connect(self.rate_card)
            self.cards[index] = card
            self.grid.addWidget(card, index // COLUMNS, index % COLUMNS)

        # Rows too, or a row holding a taller image claims the extra height.
        for row in range((len(self.cards) + COLUMNS - 1) // COLUMNS):
            self.grid.setRowStretch(row, 1)

        self.generate_button.setEnabled(True)
        self.status.emit(
            "Built {} variants from seeds {}–{}".format(
                len(self.cards), base_seed, base_seed + len(self.cards) - 1
            )
        )

    def request_generate(self):
        if not self.prompts:
            return
        references = []
        if self.spec_provider:
            spec, _, _ = self.spec_provider()
            if spec.get("reference"):
                references = [spec["reference"]]
        jobs = []
        for index, prompt in sorted(self.prompts.items()):
            out_name = "variant-{}-{}.png".format(self.cards[index].seed, self.entries[index][-6:])
            jobs.append((index, prompt, out_name, references))
            self.cards[index].set_status("accent", "generating…")
        self.generate_requested.emit(jobs)

    # -- batch feedback ---------------------------------------------------- #
    def set_busy(self, busy, total=0):
        self.generate_button.setEnabled(not busy and bool(self.prompts))
        self.build_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, total)
            self.progress.setValue(0)

    def set_progress(self, completed, total):
        self.progress.setRange(0, total)
        self.progress.setValue(completed)

    def on_item_finished(self, index, path):
        card = self.cards.get(index)
        if card is None:
            return
        card.set_image(path)
        card.set_status("success", "ready")
        card.image_path = path
        entry_id = self.entries.get(index)
        if entry_id:
            hist.rate(entry_id, None, image=str(path))

    def on_item_failed(self, index, reason):
        card = self.cards.get(index)
        if card is None:
            return
        card.set_status("danger", "failed")
        card.preview.setText("failed")
        card.setToolTip(reason)
        self.status.emit(reason)

    def rate_card(self, index, value):
        """Rate one variant directly - previously the only rating path was
        "pick the winner", which force-rated every other card a 2. A card can
        now be rated on its own, and adopt_selected() below already skips any
        card that already has a rating, so the two paths do not fight.
        """
        card = self.cards.get(index)
        entry_id = self.entries.get(index)
        if not entry_id:
            return
        hist.rate(entry_id, value, image=str(getattr(card, "image_path", "") or ""))
        self.status.emit("Rated seed {} · {}/5".format(getattr(card, "seed", index), value))

    # -- selection --------------------------------------------------------- #
    def select_card(self, index):
        self.selected = index
        for key, card in self.cards.items():
            card.set_selected(key == index)
        self.adopt_button.setEnabled(True)

    def adopt_selected(self):
        if self.selected is None:
            return
        card = self.cards[self.selected]
        entry_id = self.entries.get(self.selected)
        if entry_id:
            hist.rate(entry_id, 5, note="picked as variant winner",
                      image=str(getattr(card, "image_path", "")))
        # Everything not picked is evidence too — a losing sample is a 2.
        for index, other_id in self.entries.items():
            if index != self.selected and other_id:
                existing = hist.find(hist.load(), other_id)
                if existing and existing.get("rating") is None:
                    hist.rate(other_id, 2, note="not picked")
        self.seed_adopted.emit(card.seed)
        self.status.emit(
            "Adopted seed {} — winner rated 5, the rest 2. Insights updated.".format(card.seed)
        )
