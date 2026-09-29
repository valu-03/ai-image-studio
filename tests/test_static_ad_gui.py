"""The Static ad sub-section, and the container split that carries it.

Two things this suite is really protecting.

FIRST, that splitting Ads did not disturb the five-beat flow. `MainWindow`
keeps `self.ads_view` pointing at the video half, so every existing
`win.ads_view` reference, signal wire and test keeps working. tests/test_ads.py
asserts `av.tabs.count() == 6` against that same attribute; this file asserts
the container around it.

SECOND, that the gate's THREE states survive into the widget. `creative_ad_lint`
distinguishes green (a rule verified it), amber (a human asserted it) and red
(nobody has). GateTree only draws amber for a row that PASSED and carries
"state": "warn", so a manual row has to be both ticked and flagged - the first
implementation set a ticked row's state to "pass", which collapsed green and
amber and meant no row in the app could ever render amber at all.
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

import build_creative_ad as bca  # noqa: E402
import creative_ad_lint as cal  # noqa: E402
import realism_lint as rl  # noqa: E402
import build_prompt as bp  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.main_window import NAV_ITEMS, SUBVIEW_ROUTES  # noqa: E402
from ui.views.ads_container import AdsContainer  # noqa: E402
from ui.views.static_ad import StaticAdView  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


BANK = cal.load_bank()
IMAGE_BANK = bp.load_bank()
EXAMPLE = bca.EXAMPLE


def filled_view():
    """A view driven exactly as a user would drive it, not a stubbed one."""
    view = StaticAdView({})
    view.product.setText(EXAMPLE["product"])
    view.insight.setPlainText(EXAMPLE["insight"])
    view.idea.setPlainText(EXAMPLE["idea"])
    for group, key in EXAMPLE["typography"].items():
        if group in view.type_combos:
            view.type_combos[group].setCurrentIndex(view.type_combos[group].findData(key))
    for key in EXAMPLE["typography"].get("restraint", []):
        view.restraint_boxes[key].setChecked(True)
    view.headline.setText(EXAMPLE["typography"]["headline"])
    for route in EXAMPLE["routes"]:
        view.territory.setCurrentIndex(view.territory.findData(route["key"]))
        view.route_name.setText(route["name"])
        view.route_device.setPlainText(route["device"])
        view.route_rationale.setPlainText(route["rationale"])
        view.add_route()
    view.rebuild()
    return view


print("=== THE CONTAINER SPLIT DID NOT DISTURB THE VIDEO AD ===")
bank = bp.load_bank()
container = AdsContainer(bank, {})
check("two tabs, video ad first",
      [container.tabs.tabText(i) for i in range(container.tabs.count())]
      == ["Video ad", "Static ad"])
check("the video half is still a whole AdsView with its six tabs",
      container.video.tabs.count() == 6, str(container.video.tabs.count()))
check("the container exposes both children",
      hasattr(container, "video") and hasattr(container, "static"))
check("show_static / show_video move the tab",
      (container.show_static() or container.tabs.currentIndex()) == 1)
container.show_video()
check("...and back", container.tabs.currentIndex() == 0)

check("the rail is still ten entries", len(NAV_ITEMS) == 10, str(len(NAV_ITEMS)))
check("the static ad is deep-linkable as a sub-view",
      SUBVIEW_ROUTES.get("static_ad") == ("ads", 1), str(SUBVIEW_ROUTES.get("static_ad")))
check("...and Ads is not itself in SUBVIEW_ROUTES as a rail key",
      "ads" not in SUBVIEW_ROUTES)


print()
print("=== THE VIEW RENDERS ITS FOUR BEATS ===")
view = StaticAdView({})
check("four tabs, in working order",
      [view.tabs.tabText(i) for i in range(view.tabs.count())]
      == ["Idea", "Routes", "Art direction", "Critique"])
check("the gate shows one row per command",
      view.gate.tree.topLevelItemCount() == len(cal.commands(BANK)),
      str(view.gate.tree.topLevelItemCount()))
check("an empty brief scores 0 of ten", view.score_badge.text().startswith("0/"),
      view.score_badge.text())
check("every territory in the bank is offered",
      view.territory.count() == len(cal.routes(BANK)), str(view.territory.count()))
check("every tier is offered", view.tier.count() == len(cal.tiers(BANK)))
check("the two manual rows get a checkbox each",
      set(view.manual_boxes) == {c["key"] for c in cal.commands(BANK)
                                 if c["check"] == "manual"},
      str(sorted(view.manual_boxes)))
check("an empty brief composes no prompts", not view.prompts.toPlainText().strip())


print()
print("=== A FILLED BRIEF SCORES, AND THE MANUAL ROWS HOLD IT BACK ===")
view = filled_view()
check("both routes are listed", view.route_tree.topLevelItemCount() == 2)
check("both routes composed a prompt", len(view._shots) == 2, str(len(view._shots)))
check("every composed prompt clears the 8/8 realism gate",
      all(len(rl.lint(s["prompt"].lower(), IMAGE_BANK)[0]) == 8 for s in view._shots))
check("...with nothing banned",
      not [b for s in view._shots for b in rl.lint(s["prompt"].lower(), IMAGE_BANK)[2]])
check("the type direction composed", "visual hierarchy" in view.type_phrase.toPlainText())
check("it scores 7 of 10 with the human rows untouched",
      view.score_badge.text() == "7/10", view.score_badge.text())

for box in view.manual_boxes.values():
    box.setChecked(True)
view.rebuild()
check("...and 10 of 10 once both are ticked",
      view.score_badge.text() == "10/10", view.score_badge.text())

# Half is not enough - this is the whole argument for keeping the manual rows.
view.manual_boxes["premium"].setChecked(False)
view.rebuild()
check("one row ticked is not enough - and `ready` is the row that refuses",
      view.score_badge.text() == "8/10"
      and not {r["key"]: r for r in view._rows}["ready"]["passed"],
      view.score_badge.text())
view.manual_boxes["premium"].setChecked(True)
view.rebuild()


print()
print("=== GREEN, AMBER AND RED ARE THREE DIFFERENT THINGS ===")
rows = {r["key"]: r for r in cal.rows_for_gate(cal.lint(BANK, {
    "product": EXAMPLE["product"], "insight": EXAMPLE["insight"],
    "idea": EXAMPLE["idea"], "typography": EXAMPLE["typography"],
    "routes": EXAMPLE["routes"], "shots": view._shots}, ["direction", "premium"]))}
check("a ticked manual row is amber - asserted, not verified",
      rows["direction"]["passed"] and rows["direction"]["state"] == "warn")
check("a rule-verified row is green, not amber",
      rows["insight"]["passed"] and rows["insight"]["state"] is None)


print()
print("=== THE GATE REACTS TO WHAT THE USER TYPES ===")
# Command 8: a device that is really a packshot.
view = filled_view()
view.route_tree.setCurrentItem(view.route_tree.topLevelItem(0))
view.route_device.setPlainText("the LumaWash bottle on a white background, lit softly")
view.update_route()
view.rebuild()
beyond = {r["key"]: r for r in view._rows}["beyond"]
check("a product-on-white device turns command 8 red", not beyond["passed"])
check("...and the row says which route and which tell",
      "white background" in beyond["detail"], beyond["detail"][:70])
check("the tree shows a row per command throughout",
      view.gate.tree.topLevelItemCount() == len(cal.commands(BANK)))

# Command 5: a stock trope, and the negation half.
view = filled_view()
view.route_tree.setCurrentItem(view.route_tree.topLevelItem(0))
view.route_device.setPlainText(
    "a lightbulb moment over her head as she reaches for the LumaWash bottle")
view.update_route()
view.rebuild()
fresh = {r["key"]: r for r in view._rows}["fresh"]
check("a stock trope turns command 5 red", not fresh["passed"])
check("...and names it", "lightbulb" in fresh["detail"], fresh["detail"][:60])

# Command 9: one route is not a choice.
view = filled_view()
view.route_tree.setCurrentItem(view.route_tree.topLevelItem(1))
view.remove_route()
view.rebuild()
check("removing a route drops it below 7/10", view.score_badge.text() != "7/10",
      view.score_badge.text())
check("...and the view still composes without raising", isinstance(view._shots, list))


print()
print("=== ROUTE EDITING ===")
view = filled_view()
check("selecting a route loads it back into the form",
      (view.route_tree.setCurrentItem(view.route_tree.topLevelItem(0)) or
       view.route_device.toPlainText()) == EXAMPLE["routes"][0]["device"])
before = view.route_tree.topLevelItemCount()
view.route_device.setPlainText("")
view.add_route()
check("a route with no device is refused",
      view.route_tree.topLevelItemCount() == before, "added an empty device")


print()
print("=== HANDOFF ===")
view = filled_view()
view.copy_prompts()
check("Copy prompts puts both prompts on the clipboard",
      app.clipboard().text().count("===") == 2, str(app.clipboard().text().count("===")))
check("...and what it copied carries the 8/8 score per route",
      app.clipboard().text().count("8/8") == 2)
check("the view spends no money - it has no generate signal",
      not [n for n in dir(view) if "generate" in n.lower()], str(
          [n for n in dir(view) if "generate" in n.lower()]))


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL STATIC AD GUI CHECKS PASSED")
