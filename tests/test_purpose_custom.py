"""A placement you name yourself, and the two things it deliberately will not do.

Purpose was the last closed combo on the Compose form. It is now editable like
Shot, Lighting, Composition and Colour, but it is NOT the same kind of field as
any of them, and this suite exists to keep the difference from being tidied
away by someone who notices the inconsistency:

  Shot / Lighting / Composition / Colour   a PHRASE. Typed text goes into the
                                           prompt, so a custom one works
                                           exactly as well as a listed one.

  Purpose                                  a DEFAULT PROVIDER. It never appears
                                           in a prompt. Its only job is to fill
                                           `shot` and `aspect` when the spec is
                                           silent, and a name the bank has
                                           never seen has neither to give.

So a custom purpose supplies nothing, says so in the note under the field, and
earns its keep as metadata instead: it travels with the spec, and the model is
shown it when it fills the form. The two refusals pinned here are that it must
not invent a crop, and that a MODEL must not be able to set one - that would be
a way around the validate_purpose() filter that already drops invented
placements.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402
from ui.spec_editor import AUTO_LABEL, SpecEditor  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


BANK = bp.load_bank()
CUSTOM = "LinkedIn banner"


print("=== THE BOX TAKES TYPING AT ALL ===")
ed = SpecEditor(BANK)
check("the combo is editable", ed.purpose.isEditable())
check("...but typing does not pollute the dropdown with new items",
      ed.purpose.insertPolicy() == ed.purpose.InsertPolicy.NoInsert)
before = ed.purpose.count()
ed.purpose.setCurrentText(CUSTOM)
check("the listed placements are unchanged after typing", ed.purpose.count() == before,
      "{} -> {}".format(before, ed.purpose.count()))
check("every listed placement is still offered",
      before == len(BANK.get("purposes", {})) + 1, str(before))
check("the typed text survives in the box", ed.purpose.currentText() == CUSTOM)
check("the tooltip warns it supplies no shot or aspect",
      "supplies no shot or aspect" in ed.purpose.toolTip(), ed.purpose.toolTip())


print()
print("=== LISTED KEY AND TYPED TEXT ARE SEPARATE SPEC KEYS ===")
ed = SpecEditor(BANK)
ed.purpose.setCurrentIndex(ed.purpose.findData("tiktok-ugc"))
spec = ed.spec()
check("a picked placement emits `purpose`", spec.get("purpose") == "tiktok-ugc")
check("...and no `purpose_custom`", "purpose_custom" not in spec)

ed.purpose.setCurrentText(CUSTOM)
spec = ed.spec()
check("a typed placement emits `purpose_custom`", spec.get("purpose_custom") == CUSTOM)
check("...and no `purpose`", "purpose" not in spec)
check("build_prompt reads it back", bp.custom_purpose(spec) == CUSTOM)

# The whole reason the keys are split: a typo must stay an error, not become a
# silent custom placement. Same rule as shot / shot_custom.
check("a misspelt listed key is still rejected by validate_purpose",
      bp.validate_purpose(BANK, "instgram-post") is not None)
check("...while a typed placement never reaches that validator at all",
      bp.validate_purpose(BANK, spec.get("purpose")) is None)

ed.purpose.setCurrentText(AUTO_LABEL)
check("(auto) emits neither key", "purpose" not in ed.spec()
      and "purpose_custom" not in ed.spec(), str(sorted(ed.spec())))


print()
print("=== IT SUPPLIES NOTHING, AND THE NOTE SAYS SO ===")
ed = SpecEditor(BANK)
ed.purpose.setCurrentIndex(ed.purpose.findData("youtube-thumbnail"))
listed = bp.apply_purpose(BANK, ed.spec())
check("a listed placement fills shot and aspect",
      listed.get("shot") == "portrait" and listed.get("aspect") == "16:9", str(listed))
check("...and the note says what it is supplying",
      "Supplying" in ed.purpose_note.text(), ed.purpose_note.text())

ed.purpose.setCurrentText(CUSTOM)
custom_spec = ed.spec()
filled = bp.apply_purpose(BANK, custom_spec)
check("a typed placement fills no shot", not filled.get("shot"), str(filled.get("shot")))
check("...and no aspect", not filled.get("aspect"), str(filled.get("aspect")))
check("...and raises no conflict notes", bp.purpose_conflicts(BANK, custom_spec) == [],
      str(bp.purpose_conflicts(BANK, custom_spec)))
note = ed.purpose_note.text()
check("the note names the placement back to the user", CUSTOM in note, note)
check("...and says plainly that it supplies neither",
      "supplies no shot or aspect" in note, note)

# Once the user sets them, the note stops nagging about the ones they set.
ed.aspect.setCurrentText("16:9")
note = ed.purpose_note.text()
check("setting aspect drops it from the note", "aspect" not in note.split("supplies no")[-1],
      note)
check("...and shot is still asked for", "shot" in note.split("supplies no")[-1], note)
ed.shot.setCurrentText("a tight waist-up shot on a 50mm lens")
note = ed.purpose_note.text()
check("setting both clears the ask entirely", "supplies no" not in note, note)
check("...and the placement is still named", CUSTOM in note, note)


print()
print("=== IT IS METADATA, SO IT MUST SURVIVE A ROUND TRIP ===")
ed = SpecEditor(BANK)
ed.subject.setPlainText("a founder in her forties, grey streak at the temple")
ed.purpose.setCurrentText(CUSTOM)
saved = ed.spec()

ed2 = SpecEditor(BANK)
ed2.load_spec(saved)
check("load_spec restores the typed placement", ed2.purpose.currentText() == CUSTOM,
      ed2.purpose.currentText())
check("...and spec() still reports it as custom, not as a key",
      ed2.spec().get("purpose_custom") == CUSTOM)

ed2.apply_partial({"wardrobe": "a charcoal blazer"}, fill_blanks_only=True)
check("auto-fill does not drop it on the way through",
      ed2.purpose_custom() == CUSTOM, ed2.purpose_custom())

# A listed placement arriving from the model must not displace what the user
# typed - "your own choice always wins" is the rule the whole form runs on.
ed2.apply_partial({"purpose": "instagram-post"}, fill_blanks_only=True)
check("a model-suggested listed placement does not overwrite the typed one",
      ed2.purpose_custom() == CUSTOM, ed2.purpose.currentText())


print()
print("=== A PLACEMENT NEVER REACHES THE PROMPT, LISTED OR NOT ===")
spec = {"subject": "a founder in her forties", "seed": 5, "purpose_custom": CUSTOM}
prompt, _ = bp.compose(BANK, spec)
check("the typed placement is not in the composed prompt",
      CUSTOM.lower() not in prompt.lower())
present, missing, banned, _, _ = rl.lint(prompt.lower(), BANK)
check("a custom placement leaves the 8/8 gate untouched",
      len(present) == 8 and not banned, "missing: {}".format(missing))
check("...and so does a listed one",
      len(rl.lint(bp.compose(BANK, {"subject": "a founder in her forties", "seed": 5,
                                    "purpose": "instagram-post"})[0].lower(), BANK)[0]) == 8)


print()
print("=== A USER MAY NAME A PLACEMENT; A MODEL MAY NOT ===")
check("purpose_custom is not a key a model may write",
      "purpose_custom" not in brief.SPEC_KEYS, str(sorted(brief.SPEC_KEYS)))
check("...and not a suggest-only key either",
      "purpose_custom" not in brief.SUGGEST_KEYS)
check("a listed purpose IS still writable by a model", "purpose" in brief.SPEC_KEYS)
described = brief._describe_current({"subject": "a founder", "purpose_custom": CUSTOM})
check("but the model is SHOWN the one the user typed",
      any(line == "purpose_custom: " + CUSTOM for line in described), str(described))


print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL CUSTOM PURPOSE CHECKS PASSED")
