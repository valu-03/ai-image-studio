"""One root cause, four locations: an editable QComboBox's `currentData()`
does not move when the user types over its text after having picked an item
from the dropdown - only `currentIndex` selection (or a programmatic
setCurrentIndex/setCurrentText matching an item) moves it. A `currentData()`
-first fast path in `_resolved()`/`shot_value()`/`composition_guide()` used
to trust that stale value over whatever was actually typed, so picking a
preset and then typing something else over it silently kept composing the
OLD preset forever - reported as "posing: if it's custom there is no prompt
below" (an empty-looking field never recovering), but reproduced directly in
three more places sharing the exact same pattern.

The fix everywhere is the same: resolve purely from the CURRENT text via
`findText()`/`findData()`, the way `SpecEditor._listed()` (the one
implementation that was already correct) always has - never touch
`currentIndex()`/`currentData()` directly.

This suite proves the fix in all four locations with the exact repro that
found the bug: pick a real entry, then retype different text over it, and
confirm the result is the NEW text - not frozen on the old pick.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import build_prompt as bp  # noqa: E402
from ui.spec_editor import SpecEditor  # noqa: E402
from ui.views.lighting import LightingView  # noqa: E402
from ui.views.posing import PosingView  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== PosingView.pose_combo (the reported bug) ===")

pv = PosingView()
index = pv.pose_combo.findData("weight-back-leg")
check("the pose key exists in the bank", index >= 0)
pv.pose_combo.setCurrentIndex(index)
check("picking resolves to the picked pose's phrase",
      "weight shifted onto the back leg" in pv.composed.text(), pv.composed.text())

pv.pose_combo.setCurrentText("sitting cross-legged on the floor, hands in lap")
check("retyping updates the composed phrase to the NEW text",
      pv.composed.text() == "sitting cross-legged on the floor, hands in lap", pv.composed.text())
check("the old picked pose's phrase is gone",
      "weight shifted" not in pv.composed.text())
check("Apply is enabled for the new custom text", pv.apply_button.isEnabled())


print()
print("=== LightingView's deep-path combos (same _resolved(), same bug) ===")

lv = LightingView()
index = lv.direction_combo.findData("rembrandt")
check("the direction key exists in the bank", index >= 0)
lv.direction_combo.setCurrentIndex(index)
check("picking resolves to the picked direction's key",
      LightingView._resolved(lv.direction_combo) == "rembrandt")

lv.direction_combo.setCurrentText("light raking sharply across the cheekbone")
check("retyping resolves to the NEW typed text",
      LightingView._resolved(lv.direction_combo) == "light raking sharply across the cheekbone",
      LightingView._resolved(lv.direction_combo))
check("not frozen on the old key",
      LightingView._resolved(lv.direction_combo) != "rembrandt")


print()
print("=== SpecEditor.shot (the core Compose form's Shot field) ===")

bank = bp.load_bank()
ed = SpecEditor(bank)
index = ed.shot.findData("portrait")
check("the shot preset exists", index >= 0)
ed.shot.setCurrentIndex(index)
check("picking resolves shot_value() to the preset key", ed.shot_value() == "portrait")
check("shot_custom() is empty for a picked preset", ed.shot_custom() == "")

ed.shot.setCurrentText("close-up handheld iPhone shot")
check("retyping clears shot_value() (no longer a listed preset)", ed.shot_value() == "")
check("retyping surfaces the NEW text via shot_custom()",
      ed.shot_custom() == "close-up handheld iPhone shot", ed.shot_custom())
spec = ed.spec()
check("the composed spec carries the new custom shot, not the stale preset",
      spec.get("shot_custom") == "close-up handheld iPhone shot" and not spec.get("shot"),
      str({k: spec.get(k) for k in ("shot", "shot_custom")}))


print()
print("=== SpecEditor.composition (the core Compose form's Composition field) ===")

ed2 = SpecEditor(bank)
index = ed2.composition.findData("rule-of-thirds")
check("the guide key exists", index >= 0)
ed2.composition.setCurrentIndex(index)
check("picking resolves composition_guide() to the guide key",
      ed2.composition_guide() == "rule-of-thirds")
check("composition_custom() is empty for a picked guide", ed2.composition_custom() == "")

ed2.composition.setCurrentText("a completely different custom framing instruction")
check("retyping clears composition_guide() (no longer a listed guide)",
      ed2.composition_guide() == "")
check("retyping surfaces the NEW text via composition_custom()",
      ed2.composition_custom() == "a completely different custom framing instruction",
      ed2.composition_custom())


print()
print("=== picking and leaving it alone still works (no regression) ===")

pv2 = PosingView()
pv2.pose_combo.setCurrentIndex(pv2.pose_combo.findData("s-curve"))
check("posing: an untouched pick still composes a non-empty phrase",
      bool(pv2.composed.text()), pv2.composed.text())
check("posing: apply enabled on an untouched pick", pv2.apply_button.isEnabled())

print()
print("=== posing: a technique alone (no base pose) composes ===")

pv3 = PosingView()
check("posing: empty form disables Apply", not pv3.apply_button.isEnabled())
box = next(iter(pv3.technique_checks.values()))
box.setChecked(True)
check("posing: ticking a technique with no pose fills the Result",
      pv3._has_result and bool(pv3.composed.text().strip()), pv3.composed.text())
check("posing: Apply enabled from a lone technique", pv3.apply_button.isEnabled())
box.setChecked(False)
check("posing: unticking it empties the Result again", not pv3._has_result)
check("posing: Apply disabled once the form is empty again",
      not pv3.apply_button.isEnabled())

ed3 = SpecEditor(bank)
ed3.shot.setCurrentIndex(ed3.shot.findData("selfie"))
check("shot: an untouched pick still resolves to the preset key", ed3.shot_value() == "selfie")

ed3.composition.setCurrentIndex(ed3.composition.findData("golden-spiral"))
check("composition: an untouched pick still resolves to the guide key",
      ed3.composition_guide() == "golden-spiral")

print()
print("=== fresh typing with nothing ever picked still works (no regression) ===")

ed4 = SpecEditor(bank)
ed4.shot.setCurrentText("an over-the-shoulder shot on 35mm film")
check("shot: fresh custom text with no prior pick resolves correctly",
      ed4.shot_value() == "" and ed4.shot_custom() == "an over-the-shoulder shot on 35mm film")


print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL COMBO-RESOLVE CHECKS PASSED")
