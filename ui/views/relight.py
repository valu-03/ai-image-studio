"""Relight - change the light and/or the camera angle of a photo you already have.

Four shots at a time, every one of them scene-locked to the reference: same
person, same wardrobe, same room, same pose, same framing. Only the light moves,
or only the angle, or both. That lock is the inverse of the one Compose's
Identity tab sets - there the face is held and everything else is free; here
everything else is held and only the light and the lens move.

THE 7/8 FLOOR IS NOT A BUG, and it is the one thing worth knowing before reading
the gate. An angle shot composes a camera-angle phrase that takes the camera
slot outright, and that phrase can legitimately name no capture device - so the
shot scores 7/8 with `camera` as the only miss. `relight_lint.check_realism()`
holds lighting-only shots to a full 8 and angle shots to 7, and fails anything
below its own floor or anything with a banned term. build_camera_angle.py's
docstring reached that conclusion first: "that's the gate working, not a bug."

See ui/views/batch_shots.py for why this is an Images tab rather than a Look one.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_relight as brl  # noqa: E402
import relight_lint as rll  # noqa: E402

from .batch_shots import BatchShotView  # noqa: E402


class RelightView(BatchShotView):
    """Emits `status`. `spec_provider`/`image_provider` are set by MainWindow."""

    TITLE = "Relight an existing photo"
    INTRO = ("Re-light or re-angle a photo you already have. Every shot keeps the "
             "subject, wardrobe, setting and pose of the reference — only the light "
             "and the camera move.")
    SET_LABEL = "Set"
    SHOT_COLUMN = "Lighting / angle"
    EMPTY_HINT = ("Choose a reference photo and press Compose. Four prompts come "
                  "back, each one scene-locked to it.")

    def load_bank(self):
        self.lighting_bank = bl.load_bank()
        self.camera_bank = bca.load_bank()
        return brl.load_bank()

    def set_options(self):
        return [(key, cfg["label"], cfg.get("source_note", ""))
                for key, cfg in brl.sets(self.bank).items()]

    def compose_shots(self, base_spec, reference, set_key):
        shots = brl.sets(self.bank)[set_key]["shots"]
        return brl.compose_relight_set(
            self.bank, self.image_bank, self.lighting_bank, self.camera_bank,
            base_spec, reference, shots)

    def lint_shots(self, shots, set_key):
        return rll.lint(self.image_bank, shots)

    def write_shots(self, base_spec, shots):
        return brl.write_relight_set(base_spec, shots)

    def shot_label(self, shot):
        return brl.shot_label(shot)

    def reference_problem(self, set_key):
        """Every set here needs one: a relight with nothing to relight is just
        a new photo, which is what Compose is already for."""
        if not self._reference:
            return ("Choose a reference photo first — every shot here is locked to "
                    "one, and without it this is just Compose.")
        return ""
