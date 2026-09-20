"""The Anatomy tab actually renders TEXT.

This suite exists because of a specific shipped bug: ui/widgets.py's Card
builds its own QVBoxLayout in __init__ and exposes it as `.body`, and the view
called `QVBoxLayout(card)` instead. Qt refuses to install a second layout on a
widget that already has one, so every label added to it was orphaned - never
parented, never laid out, never drawn. The cards rendered as empty rounded
boxes and the whole tab read as blank.

Nothing caught it: tests/test_anatomy.py exercises the tool, not the view, and
tests/test_layout.py's clipped-label and overlap checks have nothing to measure
when a card contains zero labels. Counting Cards is not enough either - the
Cards themselves were present and visible. The assertion that matters is that
each card CONTAINS labels carrying non-empty text.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

import prompt_anatomy as pa  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.views.anatomy import AnatomyView  # noqa: E402
from ui.widgets import Card  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def card_text(card):
    return [lab.text() for lab in card.findChildren(QLabel) if lab.text().strip()]


bank = pa.load_bank()
view = AnatomyView()
view.resize(900, 700)
view.show()
app.processEvents()

print("=== the picker separates image prompts from video prompts ===")
picker_keys = [view.picker.itemData(i) for i in range(view.picker.count())]
picker_labels = [view.picker.itemText(i) for i in range(view.picker.count())]
image_keys = list(pa.image_templates(bank))
video_keys = list(pa.video_templates(bank))
check("every template appears exactly once in the picker",
      sorted(picker_keys) == sorted(pa.templates(bank)), str(picker_keys))
check("image templates come first, as one contiguous group",
      picker_keys[:len(image_keys)] == image_keys, str(picker_keys))
check("video templates come after, as one contiguous group",
      picker_keys[len(image_keys):] == video_keys, str(picker_keys))
check("every image template's label says so",
      all("Image prompt" in lab for lab in picker_labels[:len(image_keys)]), str(picker_labels))
check("every video template's label says so",
      all("Video prompt" in lab for lab in picker_labels[len(image_keys):]), str(picker_labels))

print()
print("=== the Skeleton half renders text, for every template ===")
for index in range(view.picker.count()):
    view.picker.setCurrentIndex(index)
    app.processEvents()
    name = view.current_template()
    expected = len(pa.slots(bank, name))
    cards = [view.skeleton_body.itemAt(i).widget() for i in range(view.skeleton_body.count())]
    cards = [c for c in cards if isinstance(c, Card)]
    check("'{}' renders one card per slot".format(name), len(cards) == expected,
          "{} cards for {} slots".format(len(cards), expected))
    empty = [c for c in cards if not card_text(c)]
    check("'{}' has no empty cards".format(name), not empty,
          "{} empty of {}".format(len(empty), len(cards)))
    # Every slot's label must actually appear on screen somewhere.
    shown = " ".join(t for c in cards for t in card_text(c))
    missing = [s["label"] for s in pa.slots(bank, name) if s["label"] not in shown]
    check("'{}' shows every slot label".format(name), not missing, str(missing[:3]))
    check("'{}' shows the why lines".format(name), shown.count("why") >= len(cards))

print()
print("=== the Copy buttons put the skeleton on the clipboard ===")
for index in range(view.picker.count()):
    view.picker.setCurrentIndex(index)
    app.processEvents()
    name = view.current_template()
    view.copy_blank.click()
    app.processEvents()
    blank = app.clipboard().text()
    check("'{}' Copy structure fills the clipboard".format(name), bool(blank.strip()),
          repr(blank[:40]))
    check("'{}' the copied structure is the tool's own".format(name),
          blank == "\n".join(pa.scaffold_lines(bank, name, filled=False)))
    view.copy_filled.click()
    app.processEvents()
    filled = app.clipboard().text()
    check("'{}' Copy worked example differs from the blank".format(name),
          filled != blank and bool(filled.strip()))
    check("'{}' the worked example has no placeholders left".format(name),
          "<" not in filled.replace("#", ""), filled[:60])

print()
print("=== the Check half renders text ===")
view.picker.setCurrentIndex(0)
app.processEvents()
view.input.setPlainText(
    "extreme close-up portrait of a woman, 100mm macro lens, visible pores, "
    "peach fuzz, soft window light, neutral grey background, no CGI look")
view.run_check()
app.processEvents()

cards = [view.result_body.itemAt(i).widget() for i in range(view.result_body.count())]
cards = [c for c in cards if isinstance(c, Card)]
check("one result card per slot", len(cards) == len(pa.slots(bank, "beauty-macro")),
      str(len(cards)))
check("no empty result cards", not [c for c in cards if not card_text(c)])
check("the coverage badge reads N/M slots", "/" in view.coverage.text() and "slots" in view.coverage.text(),
      view.coverage.text())
filled = [c for c in cards if any("filled" in t for t in card_text(c))]
check("at least one slot reports filled", bool(filled), str(len(filled)))
check("a filled card names the matched keyword",
      any("found" in t for c in filled for t in card_text(c)))

print()
print("=== empty input clears the result, without crashing ===")
view.input.setPlainText("")
view.run_check()
app.processEvents()
check("badge cleared", view.coverage.text() == "", repr(view.coverage.text()))
remaining = [view.result_body.itemAt(i).widget() for i in range(view.result_body.count())]
check("no result cards left", not [c for c in remaining if isinstance(c, Card)])

print()
print("=== switching template re-renders rather than stacking ===")
view.picker.setCurrentIndex(1)
app.processEvents()
view.picker.setCurrentIndex(0)
app.processEvents()
cards = [view.skeleton_body.itemAt(i).widget() for i in range(view.skeleton_body.count())]
cards = [c for c in cards if isinstance(c, Card)]
check("card count is stable after switching back",
      len(cards) == len(pa.slots(bank, "beauty-macro")), str(len(cards)))
check("no orphaned leftovers from the other template",
      len(view.findChildren(Card)) == len(cards), str(len(view.findChildren(Card))))

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL ANATOMY GUI CHECKS PASSED")

sys.exit(1 if fails else 0)
