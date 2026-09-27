"""tools/capture_bank.json + build_capture.py + capture_lint.py.

The per-phrase detectability audit every bank suite in this project runs -
test_lighting_bank.py, test_color_bank.py, test_macro_insert.py,
test_pet_realism.py - applied to the capture vocabulary.

WHY THIS BANK EXISTS. A repo-wide grep across every other bank returned ZERO
hits for chromatic aberration, halation, veiling glare, vignetting, barrel
distortion, ISO, shutter speed, white balance, motion blur and sensor dust, and
no film stock is named anywhere. So the app described its SUBJECT well and its
CAPTURE not at all, and output topped out at "well-lit studio photograph" -
plausible, clean, and with no evidence a physical camera made it.

WHY NOT IN prompt_bank.json. That file is hash-pinned by test_story.py, and
bumping its `version` makes history.usable() discard every rated entry - which
would silently reset the UCB1 weights behind "prefer learned terms". This
suite asserts that neither happened.

Standard library only, no network, no Qt.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_capture as bc  # noqa: E402
import build_prompt as bp  # noqa: E402
import capture_lint as cl  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bc.load_bank()
IMAGE_BANK = bp.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def all_options():
    for group, cfg in bc.groups(BANK).items():
        for key, option in cfg["options"].items():
            yield group, key, option


print("=== THE BANK'S SHAPE ===")
check("it declares a version", isinstance(BANK.get("version"), int))
check("it says plainly that it is not course material",
      "NOT AI Video Bootcamp" in BANK.get("source", ""))
check("every group declares a default layer",
      all("layer" in cfg for cfg in bc.groups(BANK).values()))
check("every option has a label, a phrase and a note",
      all({"label", "phrase", "note"} <= set(o) for _g, _k, o in all_options()))
check("no phrase ends in a full stop (build_compact comma-joins them)",
      not [k for _g, k, o in all_options() if o["phrase"].rstrip().endswith(".")])
check("film stock is the only exclusive group",
      [g for g, cfg in bc.groups(BANK).items() if cfg.get("exclusive")] == ["film_stock"])


print()
print("=== EVERY PHRASE IS VISIBLE TO THE LAYER IT CLAIMS ===")
# This is the check that would have caught story_bank.json's four fur phrases,
# which read like vocabulary and scored nothing at all.
for group, key, option in all_options():
    layer = bc.layer_of(BANK, group, key)
    check("'{}' is a real realism_lint layer".format(layer), layer in rl.DETECT)
    hits = rl.layer_hits(rl.DETECT[layer]["keys"], option["phrase"].lower())
    check("{} is detectable by {}".format(key, layer), bool(hits), str(hits))

print()
print("=== ...AND TRIPS NO BANNED OR WARN TERM ===")
# Film-stock language sits close to the "cinematic masterpiece" /
# "award-winning" vocabulary the warn list exists to catch.
for _group, key, option in all_options():
    phrase = option["phrase"].lower()
    banned, _ = rl.find_terms(phrase, IMAGE_BANK["banned"])
    warn, _ = rl.find_terms(phrase, IMAGE_BANK["warn"])
    check("{} is clean".format(key), not banned and not warn, str(banned + warn))

print()
print("=== capture_lint AGREES ===")
rows = cl.audit(BANK, IMAGE_BANK)
check("it audits every option", len(rows) == len(list(all_options())))
check("every option passes all three checks",
      all(r["detectable"] and r["clean"] and r["restrained"] for r in rows),
      str([r["key"] for r in rows if not (r["detectable"] and r["clean"] and r["restrained"])]))
check("the CLI exits 0", cl.main(["--quiet"]) == 0)


print()
print("=== COMPOSING ===")
by_layer, warnings = bc.compose_capture(BANK, film_stock="portra-400")
check("a film stock lands on the grain layer", by_layer == {
    "grain": [BANK["groups"]["film_stock"]["options"]["portra-400"]["phrase"]]})
check("and warns about nothing", warnings == [])

by_layer, _w = bc.compose_capture(BANK, optics=["halation", "vignetting"])
check("two optics stack on one layer", len(by_layer["lens"]) == 2)

# Order follows the bank, not the order they were typed, so the same selection
# always composes to the same string.
a, _ = bc.compose_capture(BANK, optics=["vignetting", "halation"])
b, _ = bc.compose_capture(BANK, optics=["halation", "vignetting"])
check("selection order does not change the output", a == b)

by_layer, _w = bc.compose_capture(BANK, film_stock="portra-400",
                                  exposure=["tungsten-wb", "highlight-rolloff"])
check("an option may override its group's layer",
      set(by_layer) == {"grain", "lighting", "colour"}, str(sorted(by_layer)))

# CineStill's whole signature IS its halation - asking for both produced the
# phrase twice, which reads as emphasis and makes the artefact louder than a
# real one.
by_layer, warnings = bc.compose_capture(BANK, film_stock="cinestill-800t", optics=["halation"])
check("an implied artefact is dropped, not said twice", "lens" not in by_layer)
check("and the caller is told", warnings and "already part of" in warnings[0])
check("the stock's own halation is still there",
      "halation" in bc.phrase_for(by_layer))

_bl, warnings = bc.compose_capture(
    BANK, film_stock="portra-400", optics=["halation", "vignetting", "veiling-glare"],
    exposure=["sensor-dust"], evidence=["handheld-frame"])
check("stacking too many artefacts warns", warnings and "reads as a filter" in warnings[0])

for bad_call, why in [
        (lambda: bc.compose_capture(BANK), "nothing selected"),
        (lambda: bc.compose_capture(BANK, optics=["no-such-thing"]), "unknown key")]:
    try:
        bad_call()
        check("{} is refused".format(why), False)
    except bc.CaptureError:
        check("{} is refused".format(why), True)


print()
print("=== IT STRENGTHENS A REAL PROMPT, AND STAYS OUT OF THE SHARED BANK ===")
spec = {"subject": "a tired barista closing up late", "setting": "an empty cafe", "seed": 4}
plain, _sel = bp.compose(IMAGE_BANK, dict(spec))
by_layer, _w = bc.compose_capture(BANK, film_stock="portra-400", optics=["halation"])
withcap, _sel2 = bp.compose(IMAGE_BANK, dict(spec, overrides=by_layer))
present, _m, banned, _w2, _n = rl.lint(withcap.lower(), IMAGE_BANK)
check("a capture-strengthened prompt still passes 8/8",
      len(present) == 8 and not banned, "{}/8 {}".format(len(present), banned))
check("and actually carries the vocabulary",
      "portra" in withcap.lower() and "halation" in withcap.lower())
check("the plain prompt carried neither",
      "portra" not in plain.lower() and "halation" not in plain.lower())

check("prompt_bank.json's version is untouched, so ratings survive",
      IMAGE_BANK["version"] == 10, str(IMAGE_BANK["version"]))
# Word-boundary matched, not substring: "portra" is inside "portrait", which
# prompt_bank.json says constantly.
import re  # noqa: E402

shared = json.dumps(IMAGE_BANK).lower()
for term in ("portra", "cinestill", "halation", "chromatic aberration", "vignetting"):
    check("'{}' did NOT leak into prompt_bank.json".format(term),
          not re.search(r"\b" + re.escape(term) + r"\b", shared))


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL CAPTURE BANK CHECKS PASSED")
