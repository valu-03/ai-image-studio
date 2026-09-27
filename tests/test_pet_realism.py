"""tools/pet_realism_bank.json, and the species-aware gate that scores it.

THE FAILURE THIS SUITE EXISTS TO PREVENT is the one it was written after. The
photoreal cat style used to carry four phrases that read exactly like fur
vocabulary - "visible individual fur strands", "whisker detail", "wet nose
texture", "natural animal anatomy" - and every one of them scored NOTHING on
realism_lint. Deleting all four left the scene's 8/8 completely unchanged,
because the gate was scoring the prompt's own "realistic skin textures"
instead. A bank whose phrases the gate cannot see is decoration.

So: every texture-layer phrase in the bank is checked against the ANIMAL
texture keys, per phrase, not assumed - the same audit
tests/test_lighting_bank.py and tests/test_macro_insert.py run for their banks.

Standard library only, no network, no Qt.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import build_story as bs  # noqa: E402
import realism_lint as rl  # noqa: E402
import story_lint as stl  # noqa: E402

PET = json.loads((ROOT / "tools" / "pet_realism_bank.json").read_text(encoding="utf-8"))
IMAGE_BANK = bp.load_bank()
STORY_BANK = bs.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== THE BANK'S SHAPE ===")
check("it declares a version", isinstance(PET.get("version"), int))
check("it says where it came from, and that it is not course material",
      "NOT AI Video Bootcamp" in PET.get("source", ""))
check("every level names groups that exist",
      all(g in PET["groups"] for level in PET["levels"].values() for g in level["groups"]))
check("every species names groups that exist",
      all(g in PET["groups"] for sp in PET["species"].values() for g in sp["groups"]))
check("every group declares which layer it belongs to",
      all("layer" in g for g in PET["groups"].values()))


print()
print("=== EVERY TEXTURE PHRASE IS VISIBLE TO THE ANIMAL GATE ===")
animal_keys = rl.detect_for("animal")["texture"]["keys"]
for name, group in PET["groups"].items():
    if group.get("layer") != "texture":
        continue
    for phrase in group["phrases"]:
        hits = rl.layer_hits(animal_keys, phrase.lower())
        check("'{}...' is detectable".format(phrase[:44]), bool(hits), str(hits))

print()
print("=== ...AND NONE OF THEM TRIPS A BANNED OR WARN TERM ===")
for name, group in PET["groups"].items():
    for phrase in group["phrases"]:
        banned, _ = rl.find_terms(phrase.lower(), IMAGE_BANK["banned"] + rl.ANIMAL_BANNED)
        warn, _ = rl.find_terms(phrase.lower(), IMAGE_BANK["warn"])
        check("'{}...' is clean".format(phrase[:40]), not banned and not warn,
              str(banned + warn))

print()
print("=== STRUCTURE IS NOT SCORED AS SURFACE ===")
# `anatomy` describes how the animal is BUILT - skeletal proportion, stance -
# not what its coat looks like. If it scored the texture layer, a prompt could
# clear the coat check without ever describing the coat, which is the same hole
# the four decorative phrases left open.
#
# `extremities` is deliberately NOT included here: "leathery paw pads with fur
# tufting between the toes" is surface description and reads as texture
# correctly. It rides `extra` because it is about specific body parts rather
# than the coat as a whole, not because it must stay invisible to the gate.
texture, extra = bs.pet_realism_phrases("macro")
check("the macro level yields both surface and structure", bool(texture) and bool(extra))
for phrase in PET["groups"]["anatomy"]["phrases"]:
    check("'{}...' does NOT score the texture layer".format(phrase[:40]),
          not rl.layer_hits(animal_keys, phrase.lower()))


print()
print("=== THE GATE IS SPECIES-AWARE, NOT MERELY WIDER ===")
check("the human key lists are untouched by the animal mode",
      rl.detect_for("human") is rl.DETECT)
check("an unknown kind falls back to human, never to something looser",
      rl.detect_for("marsupial") is rl.DETECT)
check("the animal core layer drops 'realistic skin'",
      "realistic skin" not in rl.detect_for("animal")["core"]["keys"]
      and "realistic skin" in rl.DETECT["core"]["keys"])

# The inversion, stated as the two prompts that demonstrated it.
EXPERT_CAT = (
    "ultra-realistic, photorealistic, lifelike detail of a ginger tabby cat, "
    "a dense double coat with visible guard hairs lying over a softer undercoat, "
    "long vibrissae with natural curve and asymmetry, moist, finely pitted nose leather, "
    "slit pupils with a faint tapetum sheen, DSLR photography, shot on an 85mm portrait "
    "lens, shallow depth of field, soft natural daylight, realistic shadows, earthy color "
    "palette, realistic contrast, eye-level shot, candid moment, subtle film grain, sharp focus"
)
OLD_APP_OUTPUT = (
    "cinematic realism, true-to-life textures, realistic skin textures of a ginger tabby "
    "cat, studio portrait photography, shot on an 85mm portrait lens, shallow depth of "
    "field, soft natural daylight, realistic shadows, skin micro-details, tactile "
    "materials, earthy color palette, cinematic color balance, eye-level shot, foreground "
    "and background separation, high dynamic range used lightly, sharp focus"
)


def passes(text, kind):
    present, _m, banned, _w, _n = rl.lint(text.lower(), IMAGE_BANK, kind=kind)
    return len(present) == 8 and not banned


check("a real cat prompt PASSES as an animal", passes(EXPERT_CAT, "animal"))
check("...and used to fail as a human, which is the bug", not passes(EXPERT_CAT, "human"))
check("'realistic skin textures of a cat' FAILS as an animal",
      not passes(OLD_APP_OUTPUT, "animal"))
check("...though it passed as a human, which is the other half of the bug",
      passes(OLD_APP_OUTPUT, "human"))


print()
print("=== THE IDENTITY LOCK KNOWS WHAT IT IS LOCKING ===")
check("an animal spec gets the animal lock",
      bp.locks_for({"subject_kind": "animal"})[0] is bp.LOCK_ANIMAL_COMPACT)
check("everything else still gets the human lock",
      bp.locks_for({})[0] is bp.LOCK_COMPACT
      and bp.locks_for({"subject_kind": "person"})[0] is bp.LOCK_COMPACT)
for word in ("person", "hairline", "skin tone", "bone structure"):
    check("the animal lock never says '{}'".format(word),
          word not in bp.LOCK_ANIMAL_COMPACT.lower()
          and word not in bp.LOCK_ANIMAL_DETAILED.lower())
for word in ("coat pattern", "ear shape", "tail length"):
    check("the animal lock names '{}'".format(word), word in bp.LOCK_ANIMAL_COMPACT.lower())


print()
print("=== END TO END: EVERY CAT FORMAT ===")
BASE = {"seed": 0, "subject": "a ginger tabby cat with one torn ear",
        "setting": "a cluttered home office"}
for fmt, kwargs in [("story", {}), ("trade", {"trade": "builders"}),
                    ("sitcom", {"cast": "tommy"})]:
    scenes = bs.compose_story(STORY_BANK, dict(BASE), seconds=30, clip_length=5,
                              style="photoreal", reference="scene-1.png",
                              image_bank=IMAGE_BANK, fmt=fmt, **kwargs)
    check("{}: every scene passes".format(fmt),
          all(s["passed"] for s in scenes),
          str([s["n"] for s in scenes if not s["passed"]]))
    ok, detail = stl.check_prompts(STORY_BANK, scenes, image_bank=IMAGE_BANK)
    check("{}: story_lint agrees".format(fmt), ok, detail[:60])
    for word in ("same person", "hairline", "skin tone", "skin texture"):
        guilty = [s["n"] for s in scenes if word in s["prompt"].lower()]
        check("{}: no scene says '{}'".format(fmt, word), not guilty, str(guilty))
    check("{}: the coat vocabulary is actually in the prompt".format(fmt),
          "guard hairs" in scenes[0]["prompt"].lower())

# The stylised look is judged by its own `expects` block and must be untouched
# by any of this.
stylised = bs.compose_story(STORY_BANK, dict(BASE), seconds=30, clip_length=5,
                            style="stylised", reference="scene-1.png",
                            image_bank=IMAGE_BANK, fmt="story")
ok, detail = stl.check_prompts(STORY_BANK, stylised, image_bank=IMAGE_BANK)
check("the stylised look still passes its own gate", ok, detail[:60])
check("and carries no coat vocabulary", "guard hairs" not in stylised[0]["prompt"].lower())


print()
print("=== A MISSING BANK DEGRADES, IT DOES NOT CRASH ===")
check("an unknown level yields nothing rather than raising",
      bs.pet_realism_phrases("no-such-level") == ([], []))
check("an empty bank yields nothing rather than raising",
      bs.pet_realism_phrases("natural", {}) == ([], []))


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL PET REALISM CHECKS PASSED")
