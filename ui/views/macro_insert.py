"""Macro insert - a beauty macro of one face, and extreme crops of its features.

TWO STAGES, AND THE ORDER IS THE WHOLE TOOL:

    full-face   CREATES the canonical face. Takes no reference and sets no
                identity lock, because there is nothing yet to lock to.
    eye /       DERIVE from that generated image. Each REQUIRES a reference,
    mouth /     sets lock_identity, and carries its own feature-scoped
    cheek       `preserve` line naming what must not drift - gaze, lip
                proportions, undertone - none of which the shared identity
                lock says on its own.

So `Full face only` is the one set in this app that composes WITHOUT a
reference, and `reference_problem()` below is overridden to allow exactly that.
Run it, judge the skin rendering, save the winner, then come back with it as
the reference for the three inserts - that is cheaper than spending four
generations to find out the face was wrong.

Unlike Relight, every shot here holds a strict 8/8: the shot size rides in
`overrides["composition"]`, which PINS rather than replaces, so the camera slot
keeps a real capture device. build_macro_insert.py's docstring records that
choice against build_relight.py's documented 7/8 angle floor.

See ui/views/batch_shots.py for why this is an Images tab rather than a Look one.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_macro_insert as bmi  # noqa: E402
import macro_insert_lint as mil  # noqa: E402

from .batch_shots import BatchShotView  # noqa: E402


class MacroInsertView(BatchShotView):
    """Emits `status`. `spec_provider`/`image_provider` are set by MainWindow."""

    TITLE = "Beauty macro and feature inserts"
    INTRO = ("A full-face beauty macro, then extreme crops of the eye, mouth and "
             "cheek that lock to it. Generate the face first, save it, then come "
             "back with it as the reference for the inserts.")
    SET_LABEL = "Stage"
    SHOT_COLUMN = "Insert"
    EMPTY_HINT = ("Pick a stage and press Compose. Full face needs no reference; "
                  "the inserts crop into one.")

    def load_bank(self):
        self.lighting_bank = bl.load_bank()
        self.camera_bank = bca.load_bank()
        return bmi.load_bank()

    def set_options(self):
        return [(key, cfg["label"], cfg.get("source_note", ""))
                for key, cfg in bmi.sets(self.bank).items()]

    def _insert_names(self, set_key):
        return bmi.sets(self.bank)[set_key]["inserts"]

    def compose_shots(self, base_spec, reference, set_key):
        return bmi.compose_macro_set(
            self.bank, self.image_bank, self.lighting_bank, self.camera_bank,
            base_spec, reference, self._insert_names(set_key))

    def lint_shots(self, shots, set_key):
        return mil.lint(self.bank, shots, requested=set_key)

    def write_shots(self, base_spec, shots):
        return bmi.write_macro_set(base_spec, shots)

    def shot_label(self, shot):
        return bmi.shot_label(shot)

    def reference_problem(self, set_key):
        """Stage one is the exception: `full-face` creates the face, so asking
        it for a reference would be asking for the thing it exists to make.
        The tool already knows which names are derived - needs_reference() -
        so this asks it rather than hard-coding a set name.
        """
        if self._reference:
            return ""
        derived = bmi.needs_reference(self.bank, self._insert_names(set_key))
        if not derived:
            return ""
        return ("{} crop{} into a face that must already exist — generate the "
                "full-face macro first, save it, then choose it here.".format(
                    ", ".join(derived), "s" if len(derived) == 1 else ""))
