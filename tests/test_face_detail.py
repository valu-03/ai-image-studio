"""tools/face_detail_bank.json + build_face_detail.py - micro-detail scaled to the shot.

The rule this exists for: detail has to match what the camera can resolve.
Pores in a full-body frame are detail no lens could record, and asking for
them makes a model over-sharpen the face into a render. So:

  * the wide tier carries NO pore language, ever;
  * each tier's phrases are detectable by realism_lint's texture keys (human)
    or ANIMAL texture keys (pets) - a phrase the gate cannot see is decoration;
  * no warn or banned terms - the FULL FACE source's "8K ultra-photorealistic"
    stays out;
  * a human spec with face detail on still scores a full 8/8;
  * the close tier really is keyed into macro_insert_bank.json, not copied.

Standard library only, no network, no Qt.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_face_detail as bfd  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bfd.load_bank()
IMAGE_BANK = bp.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()) is not None


def detectable(phrase, kind="human"):
    keys = rl.detect_for(kind)["texture"]["keys"]
    return any(key in phrase.lower() for key in keys)


print("=== SHOT TIERS ===")
for shot, custom, tier in (
        ("portrait", "", "mid"), ("selfie", "", "mid"), ("environmental", "", "wide"),
        ("product-demo", "", "wide"), ("", "", "mid"),
        ("", "extreme close-up beauty portrait", "close"),
        ("", "tight headshot on a 100mm macro", "close"),
        ("", "close-up iPhone-style photo", "mid"),
        ("", "full-body shot on a sidewalk", "wide"),
        ("", "medium-wide shot", "wide"),
        ("", "a lazy afternoon", "mid")):
    got = bfd.shot_tier(BANK, shot, custom)
    check("{!r}/{!r} -> {}".format(shot, custom, tier), got == tier, got)
check("every shot preset in prompt_bank.json has a tier",
      set(IMAGE_BANK["shot_presets"]) <= set(BANK["shot_tiers"]["presets"]),
      str(set(IMAGE_BANK["shot_presets"]) - set(BANK["shot_tiers"]["presets"])))

print()
print("=== HUMAN TIERS ===")
for tier in bfd.TIERS:
    pool = bfd.human_pool(BANK, tier)
    check("{} tier has more phrases than it picks".format(tier),
          len(pool) > BANK["human"][tier]["pick"], str(len(pool)))
    undetected = [p for p in pool if not detectable(p)]
    check("{} tier: every phrase is detectable as texture".format(tier), not undetected,
          str(undetected[:2]))
    bad = [p for p in pool if any(has_term(p, t) for t in IMAGE_BANK["banned"] + IMAGE_BANK["warn"])]
    check("{} tier: no banned or warn term".format(tier), not bad, str(bad[:2]))
wide = " ".join(bfd.human_pool(BANK, "wide")).lower()
check("the wide tier carries NO pore language", "pore" not in wide)
mid_close = " ".join(bfd.human_pool(BANK, "close")).lower()
check("the close tier does name pores", "pore" in mid_close)
macro_texture = BANK["_macro"]["inserts"]["full-face"]["overrides"]["texture"]
check("the close tier draws on macro_insert_bank.json's full-face texture, by reference",
      all(p in bfd.human_pool(BANK, "close") for p in macro_texture))
check("no close-tier phrase is drawn twice",
      len(bfd.human_pool(BANK, "close")) == len(set(bfd.human_pool(BANK, "close"))))
for source_phrase in ("never one uniform skin tone", "natural asymmetry"):
    check("carries the FULL FACE idea '{}'".format(source_phrase),
          source_phrase in " ".join(bfd.human_pool(BANK, "mid") + bfd.human_pool(BANK, "wide")))

print()
print("=== ANIMALS AND THINGS ===")
cat_close = bfd.face_detail(BANK, "a ginger tabby cat", "", "extreme close-up", 1)
check("a cat close-up gets coat/face detail", cat_close[0] and cat_close[2] == "animal", str(cat_close))
check("cat detail is detectable by the ANIMAL texture keys",
      all(detectable(p, "animal") for p in bfd.animal_pool(BANK, "close", "cat")))
check("a dog never gets feline eyes",
      not any("slit pupils" in p for p in bfd.animal_pool(BANK, "close", "dog")))
check("a wide cat shot gets coat only",
      not any("vibrissae" in p for p in bfd.animal_pool(BANK, "wide", "cat")))
check("a product gets nothing", bfd.face_detail(BANK, "an amber shampoo bottle")[0] == "")
check("a room gets nothing", bfd.face_detail(BANK, "a quiet kitchen at dawn")[0] == "")
check("an unknown animal gets nothing rather than cat fur",
      bfd.face_detail(BANK, "a horse in a field")[0] == "")

print()
print("=== IN A REAL PROMPT ===")
check("same spec, same phrase (reproducible by seed)",
      bfd.face_detail(BANK, "a woman", "portrait", "", 4) == bfd.face_detail(BANK, "a woman", "portrait", "", 4))
below = []
for seed in range(30):
    for shot, custom in (("portrait", ""), ("environmental", ""), ("", "extreme close-up headshot on a Canon EOS R5")):
        spec = {"subject": "a woman in her thirties", "seed": seed}
        if shot:
            spec["shot"] = shot
        if custom:
            spec["shot_custom"] = custom
        before = len(rl.lint(bp.compose(IMAGE_BANK, spec)[0], IMAGE_BANK)[0])
        phrase = bfd.for_spec(BANK, spec)[0]
        spec["overrides"] = {"face_detail": [phrase]}
        prompt = bp.compose(IMAGE_BANK, spec)[0]
        present, _missing, banned, _warn, _neg = rl.lint(prompt, IMAGE_BANK)
        if len(present) < before or banned:
            below.append((seed, shot or custom, len(present), before))
check("90 specs: face detail never lowers a score or adds a banned term", not below, str(below[:3]))
spec = {"subject": "a woman in her thirties", "seed": 0, "shot": "portrait"}
spec["overrides"] = {"face_detail": [bfd.for_spec(BANK, spec)[0]]}
present = rl.lint(bp.compose(IMAGE_BANK, spec)[0], IMAGE_BANK)[0]
check("a portrait with face detail scores 8/8", len(present) == 8, str(len(present)))

print()
print("=== A CLOSE BEAUTY SHOT GETS ONE LENS AND SOFT LIGHT ===")
for typed in ("close-up of her face", "close-up of his face", "a face close-up"):
    check("{!r} is a close shot".format(typed), bfd.shot_tier(BANK, "", typed) == "close")
check("a plain 'close-up' is still mid", bfd.shot_tier(BANK, "", "close-up") == "mid")
beauty = {"subject": "a striking blonde woman", "shot_custom": "extreme close-up beauty portrait, 100mm macro lens"}
lenses, lights = set(), set()
for seed in range(200):
    layers = bp.compose(IMAGE_BANK, dict(beauty, seed=seed))[1]
    lenses.update(layers["lens"])
    lights.update(layers["lighting"])
check("a typed '100mm macro lens' never gets a second focal length (200 seeds)",
      not [t for t in lenses if re.search(r"\d+mm", t)], str(sorted(lenses)))
check("...but depth of field and bokeh still come through",
      {"shallow depth of field", "natural bokeh"} & lenses)
check("a close shot never draws chiaroscuro or harsh noon sun (200 seeds)",
      not lights & set(BANK["shot_tiers"]["close_lighting_skip"]), str(sorted(lights)))
mid_lights = {t for seed in range(200)
              for t in bp.compose(IMAGE_BANK, {"subject": "a woman", "seed": seed})[1]["lighting"]}
check("...while a mid shot still can", "chiaroscuro lighting" in mid_lights)
plain_lenses = {t for seed in range(100) for t in bp.compose(
    IMAGE_BANK, {"subject": "a woman", "shot_custom": "medium shot by a window", "seed": seed})[1]["lens"]}
check("a typed shot that names no lens keeps the focal-length picks",
      any(re.search(r"\d+mm", t) for t in plain_lenses))

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL FACE DETAIL CHECKS PASSED")
