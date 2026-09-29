"""Compose's own Posing field, and the REPLACE semantic every Apply button has.

Posing used to share the Action field. That made the two things a viewer sees
in a photograph - what the subject is DOING, and how the body is ARRANGED while
doing it - compete for one line of text, so the Posing section's "Apply to
Compose" overwrote the thing the shot was about in order to say how the body
sat. `posing` is now its own spec key, and `SpecEditor.set_posing_override()`
lands in a field that belongs to it alone.

THE OTHER HALF OF THIS SUITE is the question that prompted the field: does
Apply ADD to the prompt, or CHANGE it? Every `set_X_override()` in
ui/spec_editor.py writes one widget with setText/setCurrentText, and the prompt
is recomposed from `spec()` on every `changed` - so applying twice cannot
accumulate. That is easy to break by "improving" a setter into an append, and
it would not fail any other suite, so it is pinned here for all six of them.

The exception is `set_capture_overrides()`, which EXTENDS across layers by
design (a film stock is true at the same time as a lighting setup, not instead
of it) while still replacing its own previous selection wholesale. That is
pinned too, because the difference is deliberate.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication, QFormLayout, QLabel  # noqa: E402

import brief  # noqa: E402
import build_posing as bpo  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402
from ui.spec_editor import SpecEditor  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


BANK = bp.load_bank()


def labels_of(editor):
    """Every form label in the Subject tab, in the order they are laid out."""
    page = editor.tabs.widget(1)
    form = page.findChild(QFormLayout)
    out = []
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        if item is not None and isinstance(item.widget(), QLabel):
            out.append(item.widget().text())
    return out


print("=== THE FIELD IS ON THE SUBJECT TAB, NEXT TO THE ACTION IT QUALIFIES ===")
ed = SpecEditor(BANK)
check("the Subject tab is where it lives", ed.tabs.tabText(1) == "Subject",
      ed.tabs.tabText(1))
names = labels_of(ed)
check("a Posing label is drawn", "Posing" in names, str(names))
check("Action is still drawn too - this added a field, it did not rename one",
      "Action" in names, str(names))
check("Posing sits directly after Action",
      names.index("Posing") == names.index("Action") + 1, str(names))
check("...and before Mood", names.index("Posing") < names.index("Mood"), str(names))
check("it has a worked example as its placeholder, not a restated label",
      "weight on the back foot" in ed.posing.placeholderText(), ed.posing.placeholderText())


print()
print("=== IT REACHES THE SPEC, AND SURVIVES A ROUND TRIP ===")
ed = SpecEditor(BANK)
check("an empty Posing field emits no key at all", "posing" not in ed.spec())
ed.posing.setText("weight on the back foot, chin dropped a few degrees")
check("a filled one does", ed.spec().get("posing") ==
      "weight on the back foot, chin dropped a few degrees", str(ed.spec().get("posing")))
check("it counts as a filled key", "posing" in ed.filled_keys())

ed2 = SpecEditor(BANK)
ed2.load_spec(ed.spec())
check("load_spec restores it", ed2.posing.text() == ed.posing.text(), ed2.posing.text())

# apply_partial round-trips through spec() -> load_spec(), so a key missing from
# load_spec() is silently dropped by auto-fill rather than by anything obvious.
ed2.apply_partial({"wardrobe": "a grey wool coat"}, fill_blanks_only=True)
check("apply_partial does not drop it on the way through",
      ed2.posing.text() == ed.posing.text(), ed2.posing.text())


print()
print("=== APPLY REPLACES, IT DOES NOT ACCUMULATE ===")
ed = SpecEditor(BANK)
POSE_BANK = bpo.load_bank()
pose_keys = list(bpo.poses(POSE_BANK))
first, _ = bpo.compose_posing(POSE_BANK, pose=pose_keys[0])
second, _ = bpo.compose_posing(POSE_BANK, pose=pose_keys[1])

ed.set_posing_override(first)
check("the first Apply lands", ed.posing.text() == first, ed.posing.text())
ed.set_posing_override(first)
check("applying the SAME phrase twice leaves one copy, not two",
      ed.posing.text() == first, ed.posing.text())
ed.set_posing_override(second)
check("applying a DIFFERENT phrase changes it rather than appending",
      ed.posing.text() == second and first not in ed.posing.text(), ed.posing.text())
check("...so the composed prompt carries the new pose only",
      first.lower() not in bp.compose(BANK, ed.spec())[0].lower())
ed.set_posing_override("")
check("applying nothing clears it", ed.posing.text() == "")

# The same contract, for every other section that has an Apply button. A setter
# quietly turned into an append would double a phrase on the second click.
ed = SpecEditor(BANK)
for name, setter, widget, value in [
    ("Lighting", ed.set_lighting_override, lambda: ed.lighting.currentText(),
     "harsh midday sunlight"),
    ("Composition", ed.set_composition_override, lambda: ed.composition.currentText(),
     "rule of thirds with lead room to the left"),
    ("Colour", ed.set_colour_override, lambda: ed.colour.currentText(),
     "muted melancholic grade"),
    ("Camera Angle", ed.set_shot_override, lambda: ed.shot.currentText(),
     "a three-quarter medium close-up at eye level"),
    ("Subject", ed.set_subject_override, lambda: ed.subject.toPlainText(),
     "a nurse in her forties"),
    ("Posing", ed.set_posing_override, lambda: ed.posing.text(),
     "weight on the back foot"),
]:
    setter(value)
    setter(value)
    check("{}: twice is once - Apply replaces its own field".format(name),
          widget() == value, widget())


print()
print("=== POSING AND ACTION NO LONGER FIGHT ===")
ed = SpecEditor(BANK)
ed.action.setText("wiping down the counter")
ed.set_posing_override("weight on the back foot, shoulders turned away from the camera")
check("Apply leaves Action alone", ed.action.text() == "wiping down the counter",
      ed.action.text())
spec = ed.spec()
check("both keys reach the spec",
      spec.get("action") and spec.get("posing"), str(sorted(spec)))
clause = bp.subject_clause(spec)
check("the clause says what they are doing, then how the body sits",
      clause.index("wiping down the counter") < clause.index("weight on the back foot"),
      clause)

spec["setting"] = "a small coffee shop after closing"
clause = bp.subject_clause(spec)
check("...and both stay inside the person, before the setting opens",
      clause.index("weight on the back foot") < clause.index("in a small coffee shop"),
      clause)


print()
print("=== A POSE IS NOT A GATED LAYER, AND MUST NOT DISTURB THE EIGHT ===")
for key in list(bpo.poses(bpo.load_bank()))[:4]:
    phrase, _ = bpo.compose_posing(bpo.load_bank(), pose=key)
    spec = {"subject": "a woman in her thirties", "seed": 3,
            "action": "reaching for a mug", "posing": phrase}
    prompt, _ = bp.compose(BANK, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), BANK)
    check("pose '{}' in the Posing field still scores 8/8".format(key),
          len(present) == 8 and not banned, "missing: {}".format(missing))
    check("...and the phrase really is in the prompt", phrase.lower() in prompt.lower())


print()
print("=== AUTO-FILL KNOWS THE KEY EXISTS ===")
check("posing is a key a model may write into a spec", "posing" in brief.SPEC_KEYS)
check("...and it is still not one of the two suggest-only keys",
      "posing" not in brief.SUGGEST_KEYS)
described = brief._describe_current({"subject": "a nurse", "posing": "chin dropped"})
check("an existing pose is shown to the model rather than hidden from it",
      any(line.startswith("posing:") for line in described), str(described))


print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL POSING FIELD CHECKS PASSED")
