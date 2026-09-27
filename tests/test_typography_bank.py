"""tools/typography_bank.json + build_typography.py + typography_lint.py.

The per-phrase detectability audit every bank suite in this project runs -
test_lighting_bank.py, test_color_bank.py, test_capture_bank.py,
test_pet_realism.py - applied to the first vocabulary this app has ever had for
text INSIDE an image.

WHY THIS BANK EXISTS. A repo-wide grep for typography, headline, logo, copy
placement, kerning, lockup or type hierarchy across every bank and tool
returned nothing about text in an image: the only hits were ui/tokens.py's own
Qt stylesheet fonts and one photographic phrase, "negative-space". "logo" had
zero hits in tools/ at all. An app that builds advertising could describe the
photograph and not one word of the advert laid over it.

Standard library only, no network, no Qt.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import build_typography as bt  # noqa: E402
import realism_lint as rl  # noqa: E402
import typography_lint as tl  # noqa: E402

BANK = bt.load_bank()
IMAGE_BANK = bp.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def all_options():
    for group in bt.GROUP_ORDER:
        for key, option in bt.groups(BANK)[group]["options"].items():
            yield group, key, option


print("=== THE BANK'S SHAPE ===")
check("it declares a version", isinstance(BANK.get("version"), int))
check("it says plainly that it is not course material",
      "NOT AI Video Bootcamp" in BANK.get("source", ""))
check("GROUP_ORDER covers every group in the bank",
      set(bt.GROUP_ORDER) == set(bt.groups(BANK)), str(sorted(bt.groups(BANK))))
check("every group declares a default layer",
      all("layer" in cfg for cfg in bt.groups(BANK).values()))
check("every option has a label, a phrase and a note",
      all({"label", "phrase", "note"} <= set(o) for _g, _k, o in all_options()))
check("no phrase ends in a full stop (build_compact comma-joins them)",
      not [k for _g, k, o in all_options() if o["phrase"].rstrip().endswith(".")])
check("restraint is the only stackable group",
      [g for g, cfg in bt.groups(BANK).items() if not cfg.get("exclusive")] == ["restraint"])
check("every ratio declares a word cap",
      all(o.get("max_words") for _k, o in bt.options(BANK, "ratio").items()))


print()
print("=== EVERY PHRASE IS VISIBLE TO THE LAYER IT CLAIMS ===")
for group, key, option in all_options():
    layer = bt.layer_of(BANK, group, key)
    check("'{}' is a real realism_lint layer".format(layer), layer in rl.DETECT)
    hits = rl.layer_hits(rl.DETECT[layer]["keys"], option["phrase"].lower())
    check("{}:{} is detectable by {}".format(group, key, layer), bool(hits), str(hits))

print()
print("=== ...AND NOT ONLY INSIDE A NEGATION ===")
# The trap this bank very nearly shipped. `lockup.none` and
# `restraint.no-legal` were first written as "no brand logo in the frame" and
# "no small print or legal line in the frame" - both sensible English, both
# completely invisible, because is_negated() correctly refuses to score a key
# a prompt is ruling out. Nothing else in the repo would have noticed.
for group, key, option in all_options():
    layer = bt.layer_of(BANK, group, key)
    phrase = option["phrase"].lower()
    keys = rl.DETECT[layer]["keys"]
    raw = [k for k in keys if rl._key_positions(k, phrase)]
    scored = rl.layer_hits(keys, phrase)
    check("{}:{} scores positively, not just textually".format(group, key),
          not (raw and not scored), "matches only inside a negation")

# ...and the check has teeth: a phrase written the old way must be caught.
old_way = "no logo lockup in the frame, the packaging itself carrying it"
keys = rl.DETECT["composition"]["keys"]
check("a negated-only phrase IS detected as such",
      [k for k in keys if rl._key_positions(k, old_way)] and not rl.layer_hits(keys, old_way))

print()
print("=== ...AND TRIPS NO BANNED OR WARN TERM ===")
for group, key, option in all_options():
    phrase = option["phrase"].lower()
    banned, _ = rl.find_terms(phrase, IMAGE_BANK["banned"])
    warn, _ = rl.find_terms(phrase, IMAGE_BANK["warn"])
    check("{}:{} is clean".format(group, key), not banned and not warn, str(banned + warn))


print()
print("=== typography_lint AGREES ===")
rows = tl.audit(BANK, IMAGE_BANK)
check("it audits every option", len(rows) == len(list(all_options())))
check("every option passes all four checks",
      all(r["detectable"] and r["clean"] and r["positive"] and r["restrained"] for r in rows),
      str([r["key"] for r in rows
           if not (r["detectable"] and r["clean"] and r["positive"] and r["restrained"])]))
check("the bank's compatibility table is sound", not tl.check_compatibility(BANK),
      str(tl.check_compatibility(BANK)))
check("every named conflict pair exists", not tl.check_conflicts(BANK),
      str(tl.check_conflicts(BANK)))
check("the CLI exits 0", tl.main(["--quiet"]) == 0)


print()
print("=== A FLAT HIERARCHY IS REFUSED, BY NAME ===")
# The commonest way a layout dies is that everything is loud, so nothing leads.
# That is hard to see in words - but the contradiction that expresses it is
# not: type leading while getting a tenth of the frame is a flat hierarchy
# stated twice.
try:
    bt.compose_typography(BANK, dominance="type-led", ratio="whisper")
    check("type-led + whisper is refused", False)
except bt.TypographyError as exc:
    check("type-led + whisper is refused", True)
    check("...and the message names both sides and the way out",
          "flat hierarchy" in str(exc) and "poster" in str(exc), str(exc)[:90])

for dominance, ratio in [("image-led", "poster"), ("product-led", "type-first")]:
    try:
        bt.compose_typography(BANK, dominance=dominance, ratio=ratio)
        check("{} + {} is refused".format(dominance, ratio), False)
    except bt.TypographyError:
        check("{} + {} is refused".format(dominance, ratio), True)

# ...while every pairing the bank calls compatible must actually compose.
for dominance in bt.options(BANK, "dominance"):
    for ratio in bt.compatible_ratios(BANK, dominance):
        try:
            bt.compose_typography(BANK, dominance=dominance, ratio=ratio)
            check("{} + {} composes".format(dominance, ratio), True)
        except bt.TypographyError as exc:
            check("{} + {} composes".format(dominance, ratio), False, str(exc)[:70])

# A contradiction RAISES; a conflict only warns. The difference is real: two
# values that cannot both be true of one layout have no composed answer, while
# a logo sitting where the headline goes is still a coherent layout you have
# been told about.
_bl, warnings = bt.compose_typography(BANK, zone="upper-left", lockup="top-left")
check("a named conflict warns rather than raising",
      warnings and "on top of each other" in warnings[0], str(warnings))
_bl, clean = bt.compose_typography(BANK, zone="lower-band", lockup="top-left")
check("...and an unconflicting pair does not", not clean, str(clean))


print()
print("=== WORD CAPS ARE CHECKED AGAINST THE RATIO ===")
_bl, warnings = bt.compose_typography(
    BANK, ratio="whisper", headline="Sleep is not a luxury it is the whole point")
check("too long for the ratio warns", warnings and "garble" in warnings[0], str(warnings))
check("...and the warning names both numbers",
      warnings and "10-word" in warnings[0] and "carries 3" in warnings[0], str(warnings))
_bl, ok = bt.compose_typography(BANK, ratio="whisper", headline="Sleep matters")
check("a headline within the cap does not warn", not ok, str(ok))
_bl, ok = bt.compose_typography(BANK, ratio="poster",
                                headline="Sleep is not a luxury it is the point")
check("the same headline is fine at a bigger ratio", not ok, str(ok))


print()
print("=== COMPOSING ===")
by_layer, _w = bt.compose_typography(BANK, zone="upper-left")
check("one option composes to one layer", list(by_layer) == ["composition"])
a, _ = bt.compose_typography(BANK, zone="upper-left", restraint=["one-idea", "no-legal"])
b, _ = bt.compose_typography(BANK, restraint=["no-legal", "one-idea"], zone="upper-left")
check("selection order does not change the output", a == b)
check("phrases come out broadest-first, in GROUP_ORDER",
      bt.phrase_for(bt.compose_typography(
          BANK, dominance="image-led", ratio="editorial", zone="upper-left")[0]
      ).index("visual hierarchy") <
      bt.phrase_for(bt.compose_typography(
          BANK, dominance="image-led", ratio="editorial", zone="upper-left")[0]
      ).index("negative space"))

for bad_call, why in [
        (lambda: bt.compose_typography(BANK), "nothing selected"),
        (lambda: bt.compose_typography(BANK, zone="no-such-zone"), "an unknown key"),
        (lambda: bt.compose_typography(BANK, restraint=["nope"]), "an unknown restraint")]:
    try:
        bad_call()
        check("{} is refused".format(why), False)
    except bt.TypographyError:
        check("{} is refused".format(why), True)


print()
print("=== IT STRENGTHENS A REAL PROMPT, AND STAYS OUT OF THE SHARED BANK ===")
spec = {"subject": "a woman holding a chocolate bar toward the camera",
        "setting": "a seamless burnt-orange studio backdrop", "seed": 7}
plain, _sel = bp.compose(IMAGE_BANK, dict(spec))
by_layer, _w = bt.compose_typography(
    BANK, dominance="image-led", ratio="editorial", zone="upper-left",
    lockup="corner-quiet", reading_order="headline-product-logo")
withtype, _sel2 = bp.compose(IMAGE_BANK, dict(spec, overrides=by_layer))
present, _m, banned, warn, _n = rl.lint(withtype.lower(), IMAGE_BANK)
check("a typography-strengthened prompt still passes 8/8",
      len(present) == 8 and not banned, "{}/8 {}".format(len(present), banned))
check("...with no warn terms either", not warn, str(warn))
check("and it actually carries the vocabulary",
      "logo lockup" in withtype.lower() and "reading order" in withtype.lower())
check("the plain prompt carried neither",
      "logo lockup" not in plain.lower() and "reading order" not in plain.lower())

check("prompt_bank.json's version is untouched, so ratings survive",
      IMAGE_BANK["version"] == 10, str(IMAGE_BANK["version"]))
shared = json.dumps(IMAGE_BANK).lower()
for term in ("logo lockup", "reading order", "typographic block", "headline"):
    check("'{}' did NOT leak into prompt_bank.json".format(term),
          not re.search(r"\b" + re.escape(term) + r"\b", shared))


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL TYPOGRAPHY BANK CHECKS PASSED")
