"""tools/creative_direction_bank.json + build_creative_ad.py + creative_ad_lint.py.

The ten creative-direction commands, as a gate. Every row that CAN fail is
proved failing here on a fixture built to fail it - a checklist nobody has
watched go red is a checklist that might be wired to nothing.

The two rows that cannot fail automatically (3 and 7) are proved to block the
verdict anyway, which is the whole argument for keeping them: an honest
checklist lets the unjudgeable rows hold up "ready", or they are ornaments.

Standard library only, no network, no Qt.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_creative_ad as bca  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_typography as bt  # noqa: E402
import creative_ad_lint as cal  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = cal.load_bank()
IMAGE_BANK = bp.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def rows(ad, ticked=()):
    return {r["key"]: r for r in cal.lint(BANK, ad, ticked)}


def good_ad(**changes):
    """The worked brief, composed - the fixture every failure case mutates."""
    brief = copy.deepcopy(bca.EXAMPLE)
    brief.update(changes)
    ad, _warnings = bca.build(BANK, IMAGE_BANK, brief)
    return ad


print("=== THE BANK'S SHAPE ===")
check("it declares a version", isinstance(BANK.get("version"), int))
check("it says plainly that it is not course material",
      "NOT AI Video Bootcamp" in BANK.get("source", ""))
check("exactly ten commands, numbered 1-10",
      [c["n"] for c in cal.commands(BANK)] == list(range(1, 11)))
check("every command has asks, why and a check",
      all({"key", "n", "label", "asks", "why", "check"} <= set(c)
          for c in cal.commands(BANK)))
check("eight auto, two manual",
      (sum(1 for c in cal.commands(BANK) if c["check"] == "auto"),
       sum(1 for c in cal.commands(BANK) if c["check"] == "manual")) == (8, 2),
      str([c["key"] for c in cal.commands(BANK) if c["check"] == "manual"]))
check("the two manual rows are the two a regex cannot judge",
      [c["key"] for c in cal.commands(BANK) if c["check"] == "manual"]
      == ["direction", "premium"])
check("every auto row except `ready` names a rule this module implements",
      all(c.get("rule") in cal.RULES for c in cal.commands(BANK)
          if c["check"] == "auto" and c["key"] != "ready"),
      str([c.get("rule") for c in cal.commands(BANK)
           if c["check"] == "auto" and c.get("rule") not in cal.RULES]))
check("every route declares a tier that exists",
      all(set(cfg["tiers"]) <= set(cal.tiers(BANK)) for cfg in cal.routes(BANK).values()))
check("at least eight territories", len(cal.routes(BANK)) >= 8, str(len(cal.routes(BANK))))


print()
print("=== THE CLICHE LIST IS DETECTABLE, AND NEGATION-AWARE ===")
# The same audit every satellite bank in this project runs, applied to ideas
# rather than to realism vocabulary. A trope the linter cannot see is a trope
# the gate waves through.
for term in cal.cliches(BANK):
    used = "the concept is a {} in the middle of the frame".format(term)
    hit, _neg = rl.find_terms(used.lower(), cal.cliches(BANK))
    check("'{}' is detected when used".format(term), term in hit)
for term in cal.cliches(BANK):
    ruled_out = "no {} anywhere in this campaign".format(term)
    hit, neg = rl.find_terms(ruled_out.lower(), cal.cliches(BANK))
    check("'{}' does NOT trip when ruled out".format(term), not hit, str(hit))
check("every product-photo tell is detectable",
      all(t in rl.find_terms("the device is {} lit softly".format(t).lower(),
                             cal.photo_tells(BANK))[0]
          for t in cal.photo_tells(BANK)))


print()
print("=== THE WORKED BRIEF PASSES EVERY CHECKABLE ROW ===")
ad = good_ad()
base = rows(ad)
for key in ("insight", "idea", "necessity", "fresh", "hierarchy", "beyond", "routes"):
    check("`{}` passes on the worked brief".format(key), base[key]["passed"],
          base[key]["detail"][:70])
check("every composed route scores 8/8 with nothing banned",
      all(len(rl.lint(s["prompt"].lower(), IMAGE_BANK)[0]) == 8
          and not rl.lint(s["prompt"].lower(), IMAGE_BANK)[2] for s in ad["shots"]))
check("...and no soft warn term either",
      not [w for s in ad["shots"] for w in rl.lint(s["prompt"].lower(), IMAGE_BANK)[3]])


print()
print("=== EACH ROW GOES RED ON A FIXTURE BUILT TO FAIL IT ===")

# 1. An insight that is really a product feature. This reuses ugc_bank.json's
#    own feature/feeling vocabulary via ad_lint, rather than a second copy.
feature = good_ad(insight="A clinically proven formulation with 17 active ingredients")
check("command 1 fails on a product feature", not rows(feature)["insight"]["passed"])
detail = rows(feature)["insight"]["detail"]
check("...and names one of the feature words it matched",
      any(w in detail for w in ("ingredients", "formulation", "clinically")), detail[:70])
check("a one-word insight fails as a label",
      not rows(good_ad(insight="Tired"))["insight"]["passed"])

# 2. An idea that only restates the insight is not an argument.
echo = good_ad(idea="You do not want a cleaner house, you want ten minutes "
                    "where nobody needs anything from you really")
check("command 2 fails when the idea restates the insight",
      not rows(echo)["idea"]["passed"], rows(echo)["idea"]["detail"][:60])

# 4. The product must be in the DEVICE, not merely in the setting.
absent = copy.deepcopy(bca.EXAMPLE)
for route in absent["routes"]:
    route["device"] = route["device"].replace("LumaWash ", "")
absent_ad, _ = bca.build(BANK, IMAGE_BANK, absent)
check("command 4 fails when the product is in no device",
      not rows(absent_ad)["necessity"]["passed"],
      rows(absent_ad)["necessity"]["detail"][:60])

# 5. A stock trope, and - the half that matters - ruling one out must not trip.
trope = copy.deepcopy(bca.EXAMPLE)
trope["routes"][0]["device"] = "a lightbulb moment over her head as she reaches " \
                               "for the LumaWash bottle"
trope_ad, _ = bca.build(BANK, IMAGE_BANK, trope)
check("command 5 fails on a stock trope", not rows(trope_ad)["fresh"]["passed"])
check("...and names it", "lightbulb" in rows(trope_ad)["fresh"]["detail"])

ruled = copy.deepcopy(bca.EXAMPLE)
ruled["routes"][0]["rationale"] += " - and no lightbulb moment anywhere in this campaign"
ruled_ad, _ = bca.build(BANK, IMAGE_BANK, ruled)
check("...but RULING OUT a trope passes", rows(ruled_ad)["fresh"]["passed"],
      rows(ruled_ad)["fresh"]["detail"][:70])
check("...and says which trope was ruled out",
      "lightbulb" in rows(ruled_ad)["fresh"]["detail"])

# 6. Hierarchy: missing pieces, and a contradiction that cannot be composed.
no_zone = good_ad(typography={"dominance": "image-led", "ratio": "editorial"})
check("command 6 fails with no zone and no reading order",
      not rows(no_zone)["hierarchy"]["passed"])
check("...and says what is missing",
      "zone" in rows(no_zone)["hierarchy"]["detail"])
check("command 6 fails with no type direction at all",
      not rows(good_ad(typography={}))["hierarchy"]["passed"])

flat = {"dominance": "type-led", "ratio": "whisper", "zone": "upper-left",
        "reading_order": "headline-product-logo"}
try:
    bca.build(BANK, IMAGE_BANK, dict(copy.deepcopy(bca.EXAMPLE), typography=flat))
    check("a flat hierarchy is refused at build time", False)
except bt.TypographyError as exc:
    check("a flat hierarchy is refused at build time", True)
    check("...naming it as a flat hierarchy", "flat hierarchy" in str(exc), str(exc)[:70])
# ...and the lint row says the same thing rather than crashing on it.
check("command 6 reports the contradiction instead of raising",
      not rows({"typography": flat, "routes": []})["hierarchy"]["passed"])

# 8. A device that is just a product photograph.
photo = copy.deepcopy(bca.EXAMPLE)
photo["routes"][0]["device"] = "the LumaWash bottle on a white background, lit softly"
photo_ad, _ = bca.build(BANK, IMAGE_BANK, photo)
check("command 8 fails on a product-on-white device",
      not rows(photo_ad)["beyond"]["passed"], rows(photo_ad)["beyond"]["detail"][:60])
check("...and it is checked against static_ad_bank's own modes too",
      "static_ad_bank" in next(c for c in cal.commands(BANK) if c["key"] == "beyond")["why"])

# 9. One route is not a choice; two from one territory is one idea twice.
single = copy.deepcopy(bca.EXAMPLE)
single["routes"] = single["routes"][:1]
single_ad, _ = bca.build(BANK, IMAGE_BANK, single)
check("command 9 fails with a single route", not rows(single_ad)["routes"]["passed"])

same = copy.deepcopy(bca.EXAMPLE)
same["routes"][1]["key"] = same["routes"][0]["key"]
same_ad, _ = bca.build(BANK, IMAGE_BANK, same)
check("command 9 fails on two routes from one territory",
      not rows(same_ad)["routes"]["passed"], rows(same_ad)["routes"]["detail"][:60])


print()
print("=== COMMAND 10 CANNOT SAY 'READY' WHILE A HUMAN ROW IS UNTOUCHED ===")
# The argument for keeping the manual half. Every checkable row is green here.
clean = rows(ad)
check("every auto row except `ready` is green",
      all(r["passed"] for k, r in clean.items()
          if r["check"] == "auto" and k != "ready"))
check("`ready` is still FAILING", not clean["ready"]["passed"])
check("...and says how many rows are still yours",
      "2 still yours to judge" in clean["ready"]["detail"], clean["ready"]["detail"][:70])
check("one manual row ticked is not enough",
      not rows(ad, ticked=["direction"])["ready"]["passed"])
both = rows(ad, ticked=["direction", "premium"])
check("both ticked, and `ready` passes", both["ready"]["passed"],
      both["ready"]["detail"][:70])
check("the whole gate is 10/10 only then",
      cal.score(cal.lint(BANK, ad, ["direction", "premium"])) == (10, 10),
      str(cal.score(cal.lint(BANK, ad, ["direction", "premium"]))))
check("...and 7/10 before", cal.score(cal.lint(BANK, ad)) == (7, 10),
      str(cal.score(cal.lint(BANK, ad))))

# `ready` also re-checks the prompts, not just the idea.
broken = copy.deepcopy(ad)
broken["shots"][0]["prompt"] = "a nice picture of a shelf"
check("`ready` fails when a composed route stops scoring 8/8",
      not rows(broken, ticked=["direction", "premium"])["ready"]["passed"],
      rows(broken, ticked=["direction", "premium"])["ready"]["detail"][:60])


print()
print("=== A SHELF IS NOT DESCRIBED AS SKIN ===")
# prompt_bank.json is written for portraits - "realistic skin textures" is one
# of its eight core terms. Composed untouched, this builder's own worked
# example produced "realistic skin textures of a bathroom shelf".
vocab = BANK["object_vocabulary"]
check("the bank carries object vocabulary for core and texture",
      bool(vocab.get("core")) and bool(vocab.get("texture")))
check("none of it mentions skin",
      not [p for layer in ("core", "texture") for p in vocab[layer] if "skin" in p.lower()])
check("its core vocabulary hits the three distinct keys core requires",
      len(set(rl.layer_hits(rl.DETECT["core"]["keys"], ", ".join(vocab["core"]).lower())))
      >= rl.REQUIRED_HITS.get("core", 1))
check("its texture vocabulary hits the two distinct keys texture requires",
      len(set(rl.layer_hits(rl.DETECT["texture"]["keys"], ", ".join(vocab["texture"]).lower())))
      >= rl.REQUIRED_HITS.get("texture", 1))

body = [p for s in ad["shots"] for p in [s["prompt"].lower()]]
check("no composed route calls a shelf skin",
      not [p for p in body if "skin texture" in p or "skin micro" in p or "skin pores" in p],
      str([p[:60] for p in body if "skin texture" in p]))
check("...while the standing negative 'no plastic skin' still rides along",
      all("no plastic skin" in p for p in body))

person = copy.deepcopy(bca.EXAMPLE)
person["routes"][0]["has_person"] = True
person["routes"][0]["device"] = ("a woman asleep on a sofa at dawn with the "
                                 "LumaWash bottle just out of reach")
person_ad, _ = bca.build(BANK, IMAGE_BANK, person)
check("a route that says it carries a person keeps the portrait vocabulary",
      "skin" in person_ad["shots"][0]["prompt"].lower().replace("no plastic skin", ""))
check("...and still scores 8/8",
      len(rl.lint(person_ad["shots"][0]["prompt"].lower(), IMAGE_BANK)[0]) == 8)


print()
print("=== THE BUILDER REFUSES WHAT IT CANNOT BUILD ===")
for changes, why in [
        ({"product": ""}, "no product"),
        ({"routes": []}, "no routes"),
        ({"tier": "platinum"}, "an unknown tier")]:
    try:
        bca.build(BANK, IMAGE_BANK, dict(copy.deepcopy(bca.EXAMPLE), **changes))
        check("{} is refused".format(why), False)
    except bca.BriefError:
        check("{} is refused".format(why), True)

unknown = copy.deepcopy(bca.EXAMPLE)
unknown["routes"][0]["key"] = "vibes"
try:
    bca.build(BANK, IMAGE_BANK, unknown)
    check("an unknown territory is refused", False)
except bca.BriefError as exc:
    check("an unknown territory is refused", True)
    check("...and lists the real ones", "absence" in str(exc))

no_device = copy.deepcopy(bca.EXAMPLE)
no_device["routes"][0]["device"] = ""
try:
    bca.build(BANK, IMAGE_BANK, no_device)
    check("a route with no device is refused", False)
except bca.BriefError:
    check("a route with no device is refused", True)

# Same selection, same prompts - or nothing downstream can be compared.
a, _ = bca.build(BANK, IMAGE_BANK, copy.deepcopy(bca.EXAMPLE))
b, _ = bca.build(BANK, IMAGE_BANK, copy.deepcopy(bca.EXAMPLE))
check("the same brief composes to the same prompts",
      [s["prompt"] for s in a["shots"]] == [s["prompt"] for s in b["shots"]])
check("each route gets its own seed, so two routes are not one prompt twice",
      a["shots"][0]["prompt"] != a["shots"][1]["prompt"])


print()
print("=== GateTree GETS THE SHAPE IT EXPECTS ===")
gate = cal.rows_for_gate(cal.lint(BANK, ad))
check("one row per command", len(gate) == 10)
check("every row has GateTree's keys",
      all({"key", "label", "passed", "fix", "ok_text"} <= set(r) for r in gate))
ticked_gate = cal.rows_for_gate(cal.lint(BANK, ad, ["direction", "premium"]))
check("a TICKED manual row renders amber - asserted by a human, not verified",
      next(r for r in ticked_gate if r["key"] == "direction")["state"] == "warn")
check("...and an UNTICKED one is red, because nobody has judged it yet",
      next(r for r in gate if r["key"] == "direction")["passed"] is False
      and next(r for r in gate if r["key"] == "direction")["state"] is None)
check("...and a failing auto row is not amber",
      next(r for r in cal.rows_for_gate(cal.lint(BANK, photo_ad))
           if r["key"] == "beyond")["state"] is None)


print()
print("=== CLI ===")
check("--commands exits 0", cal.main(["--commands"]) == 0)
check("--list exits 0", bca.main(["--list"]) == 0)
check("--example prints a brief that actually builds", bca.main(["--example"]) == 0)
check("prompt_bank.json's version is untouched, so ratings survive",
      IMAGE_BANK["version"] == 10, str(IMAGE_BANK["version"]))
shared = json.dumps(IMAGE_BANK).lower()
for term in ("lightbulb moment", "packshot", "creative route"):
    check("'{}' did NOT leak into prompt_bank.json".format(term), term not in shared)


print()
print()
print("=== critique_static_ad(): it argues, it does not grade ===")
# The scope IS the design. Eight of the ten commands are decided by
# creative_ad_lint, and a model adds nothing to a rule that already answers the
# question - asking it to re-judge those would only invite disagreement with the
# gate. The two it cannot judge are the two a human ticks, and they render amber
# precisely because "somebody said so" is a weaker claim than "something checked".
import brief  # noqa: E402

text = brief.critique_static_ad(BANK)
manual = [c["key"] for c in cal.commands(BANK) if c["check"] == "manual"]
check("there are exactly two manual commands to critique", len(manual) == 2, str(manual))
check("the brief asks about direction", "directed" in text.lower())
check("...and about tier", "tier" in text.lower())

# THE LOAD-BEARING REFUSAL: nothing in the reply can be wired to a checkbox.
check("it forbids a pass/fail/score/boolean outright",
      "pass, fail, score or boolean" in text, text[:60])
for field in ('"passed"', '"score"', '"pass"', '"ok"', '"verdict"'):
    check("the reply shape declares no {} field".format(field), field not in text)
check("...and it says why - a human signs these two off",
      "a human signs these two off" in text)
check("it refuses to comment on the other eight",
      "Do not comment on the other eight commands" in text)

# It has to carry the tier definitions or "does it read as its tier" is unanswerable.
tiers = [k for k in BANK["tiers"] if k != "note"]
check("every tier's own definition is in the brief",
      all(t in text for t in tiers), str(tiers))
check("...with the bank's wording, not a paraphrase",
      BANK["tiers"]["luxury"] in text)

check("it asks for one change, not a list", "one edit, not a list" in text)
check("it names the weakest route, which no rule ranks",
      "weakest_route" in text)
check("it insists on quoting the brief's own words",
      "An unquoted objection is not actionable" in text)

guide = ROOT / "workflows" / "creative-static-ad.md"
check("the workflow guide exists", guide.exists())
body = guide.read_text(encoding="utf-8") if guide.exists() else ""
check("...and says the section spends no money",
      "spends no money" in body)
check("...and explains the three gate colours",
      "amber" in body.lower() and "green" in body.lower() and "red" in body.lower())
check("...and records that critique_static_ad returns no verdict",
      "no pass, no" in body.lower() or "returns no pass" in body.lower(), body[:0])


if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL CREATIVE AD CHECKS PASSED")
