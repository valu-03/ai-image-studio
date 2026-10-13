"""tools/scene_light_bank.json + build_scene_light.py + build_prompt's scene_lighting.

The bug this closes: with Lighting on (auto), select_layers() drew one of the
nine lighting terms at random, never reading the Setting - a bar at night could
be lit by golden-hour sun. What has to hold:

  * the bank only ever names lighting terms prompt_bank.json owns, so the
    weighted pick (and every rating behind it) still applies;
  * a night setting never draws a daylight term, across many seeds;
  * an unmatched setting falls back to all nine - never to nothing;
  * bounce follows the materials the Setting names; shadows are always there;
  * no phrase is banned, warned, or written as a refusal;
  * a spec WITHOUT the flag composes byte-for-byte as before;
  * the flag never lowers a realism score, and keeps 8/8;
  * an explicit pick that fights the Setting is reported, never changed.

Standard library only, no network, no Qt.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_scene_light as bsl  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bsl.load_bank()
IMAGE_BANK = bp.load_bank()
TERMS = IMAGE_BANK["layers"]["lighting"]["terms"]
DAYLIGHT = {"soft natural daylight", "golden hour sunlight", "overcast daylight",
            "harsh midday sunlight", "soft window light"}

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()) is not None


def every_phrase():
    for table in ("places", "times"):
        for cfg in BANK[table].values():
            yield cfg["source"]
            yield from cfg.get("by_time", {}).values()
    for cfg in BANK["surfaces"].values():
        yield cfg["phrase"]
    for phrases in BANK["shadows"].values():
        yield from phrases


print("=== THE BANK ONLY USES THE PROMPT BANK'S OWN TERMS ===")
stray = sorted({t for table in ("places", "times") for cfg in BANK[table].values()
                for t in cfg["allowed"] if t not in TERMS})
check("every `allowed` term exists in prompt_bank.json's lighting layer", not stray, str(stray))
check("it says plainly it is not course material", "NOT AI Video Bootcamp" in BANK["source"])
check("by_time keys are real times",
      all(t in BANK["times"] for cfg in BANK["places"].values() for t in cfg.get("by_time", {})))

print()
print("=== PHRASES ARE SAFE ===")
phrases = list(every_phrase())
bad = [p for p in phrases if any(has_term(p, t) for t in IMAGE_BANK["banned"] + IMAGE_BANK["warn"])]
check("no banned or warn term", not bad, str(bad[:2]))
animal_bad = [p for p in phrases if any(has_term(p, t) for t in rl.ANIMAL_BANNED)]
check("nothing an animal prompt bans (cat stories use this too)", not animal_bad, str(animal_bad[:2]))
negated = [p for p in phrases if re.search(r"\b(no|not|never|without|avoid)\b", p.lower())]
check("no phrase is written as a refusal", not negated, str(negated[:2]))
check("no phrase ends in a full stop", not [p for p in phrases if p.rstrip().endswith(".")])

print()
print("=== THE SOURCE FOLLOWS THE SETTING ===")
for setting, place, time in (
        ("a cocktail bar at night, brick walls", "bar", "night"),
        ("a kitchen at noon by the window", "window-interior", "midday"),
        ("a snowy slope on an overcast day", "snow", "overcast"),
        ("a quiet beach at sunset", "beach", "golden"),
        ("an abstract void", None, None)):
    got = bsl.read_scene(BANK, setting)
    check("{!r} reads as {}/{}".format(setting, place, time), got == (place, time), str(got))
check("a bar is not found inside 'barn' or 'barely'",
      bsl.read_scene(BANK, "a barely lit barn")[0] != "bar")
night = bsl.allowed_terms(BANK, "a cocktail bar at night")
check("a bar at night allows no daylight term", not (set(night) & DAYLIGHT), str(night))
noon = bsl.allowed_terms(BANK, "a kitchen at noon by the window")
check("a kitchen at noon allows window or daylight", set(noon) <= DAYLIGHT and noon, str(noon))
check("an unmatched setting falls back to all nine",
      bsl.allowed_terms(BANK, "an abstract void") == TERMS)
check("allowed terms keep the bank's order",
      night == [t for t in TERMS if t in night])
check("a street at night is lit by street lamps, not open sky",
      "lamps" in bsl.source_phrase(BANK, "a city street at night"))
check("the same street by day is open sky",
      "open sky" in bsl.source_phrase(BANK, "a city street"))

print()
print("=== IN A REAL PROMPT ===")
drew = set()
for seed in range(200):
    spec = {"subject": "a woman in her thirties", "setting": "a cocktail bar at night",
            "seed": seed, "scene_lighting": True}
    drew.update(t for t in bp.compose(IMAGE_BANK, spec)[1]["lighting"] if t != "realistic shadows")
check("200 seeds in a bar at night: never a daylight term", not (drew & DAYLIGHT), str(sorted(drew)))
check("...and the pick still varies across the allowed terms", len(drew) > 1, str(sorted(drew)))

plain = {"subject": "a woman", "setting": "a cocktail bar at night", "seed": 3}
before = bp.compose(IMAGE_BANK, plain)[0]
check("without the flag the prompt is byte-for-byte unchanged",
      before == bp.compose(IMAGE_BANK, dict(plain, scene_lighting=False))[0])
flagged = bp.compose(IMAGE_BANK, dict(plain, scene_lighting=True))[0]
check("with the flag the source is named", "pendant lamps over the bar" in flagged)
check("shadows always come through", "contact shadow" in flagged)
wood = bp.compose(IMAGE_BANK, {"subject": "a man", "setting": "a loft with a wooden floor",
                               "seed": 0, "scene_lighting": True})[0]
check("a wooden floor bounces warm light", "off the wooden surfaces" in wood)

explicit = dict(plain, scene_lighting=True, overrides={"lighting": ["soft window light", "realistic shadows"]})
prompt = bp.compose(IMAGE_BANK, explicit)[0]
check("an explicit lighting choice is kept", "soft window light" in prompt)
check("...and no second source is named against it", "lit by" not in prompt)
check("...but bounce and shadows still come through", "contact shadow" in prompt)

lowered = []
settings = ("a cocktail bar at night, wooden counter", "a sunny beach at noon", "a forest at golden hour",
            "a snowy street on an overcast day", "an office", "somewhere")
for seed in range(20):
    for setting in settings:
        base = {"subject": "a woman in her thirties", "setting": setting, "seed": seed}
        b = len(rl.lint(bp.compose(IMAGE_BANK, base)[0], IMAGE_BANK)[0])
        present, _m, banned, _w, _n = rl.lint(
            bp.compose(IMAGE_BANK, dict(base, scene_lighting=True))[0], IMAGE_BANK)
        if len(present) < b or banned or len(present) < 8:
            lowered.append((setting, seed, b, len(present)))
check("120 specs: scene lighting keeps every one at 8/8", not lowered, str(lowered[:3]))
check("the flag is NOT something a model can set", "scene_lighting" not in brief.SPEC_KEYS)

print()
print("=== CONFLICTS ARE REPORTED, NOT FIXED ===")
notes = bsl.conflicts_with(BANK, "a kitchen at night", "harsh midday sunlight")
check("midday sun in a night kitchen is reported", notes and "night" in notes[0], str(notes))
check("typed free text that clashes is reported too",
      bsl.conflicts_with(BANK, "a rooftop at night", "bright sunlight on her face"))
check("a fitting choice raises nothing", not bsl.conflicts_with(BANK, "a bar at night", "practical lighting"))
check("no time in the setting means nothing to clash with",
      not bsl.conflicts_with(BANK, "a kitchen", "harsh midday sunlight"))

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL SCENE LIGHT CHECKS PASSED")
