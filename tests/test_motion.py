"""The Kling motion toolkit: the bank, the two PDF rules, and the gate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_motion as bm
import build_prompt as bp
import motion_lint as ml
import realism_lint as rl

bank = bm.load_bank()
image_bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


SPECS = [
    {"subject": "a woman in her thirties", "setting": "a wide rooftop at dusk overlooking the city, mist rolling in",
     "action": "walking away from camera toward the edge", "mood": "calm"},
    {"subject": "a man with a beard", "setting": "a misty lake at dawn, trees on the far bank",
     "action": "wading into the water", "mood": "still"},
    {"subject": "a child", "setting": "a crowded market with tents and people, a doorway behind",
     "action": "holding a small brass key on the ground", "mood": "curious"},
]

print("=== bank integrity ===")
check("40 movements", len(bank["movements"]) == 40, str(len(bank["movements"])))
counts = {}
for movement in bank["movements"].values():
    counts[movement["category"]] = counts.get(movement["category"], 0) + 1
check("30 core / 6 niche / 4 combo",
      counts == {"core": 30, "niche": 6, "combo": 4}, str(counts))

missing_fields = [k for k, m in bank["movements"].items()
                  if not all(m.get(f) for f in ("name", "does", "lead", "example", "category"))]
check("every movement is complete", not missing_fields, str(missing_fields[:5]))

unknown = set()
for movement in bank["movements"].values():
    unknown |= set(movement.get("requires", [])) - set(bank["requirements"])
check("every requirement is defined", not unknown, str(sorted(unknown)))

undetected = set(bank["requirements"]) - set(bm.DETECTORS)
check("every requirement is detectable", not undetected, str(sorted(undetected)))

hint_shots = {m.get("image_hints", {}).get("shot") for m in bank["movements"].values()}
hint_shots.discard(None)
check("hint shots are real presets",
      hint_shots <= set(image_bank["shot_presets"]), str(hint_shots))

print()
print("=== RULE 1: always start with the camera angle ===")
bad = []
for key in bank["movements"]:
    for index, spec in enumerate(SPECS):
        prompt, _ = bm.compose(bank, key, spec)
        if ml.leads_with_camera(prompt, bank) is None:
            bad.append((key, index))
check("all 40 x 3 prompts lead with a camera move", not bad,
      "{} failures {}".format(len(bad), bad[:4]))

empty = [k for k in bank["movements"] if not bm.compose(bank, k, SPECS[0])[0].strip()]
check("no movement composes an empty prompt", not empty, str(empty[:5]))

print()
print("=== the motion gate ===")
good, _ = bm.compose(bank, "orbit-360", SPECS[0])
checks, _ = ml.lint(good, bank, "orbit-360", SPECS[0])
check("a good prompt passes", all(ok for _, ok, _ in checks),
      str([n for n, ok, _ in checks if not ok]))

checks, _ = ml.lint("a woman standing in a kitchen, warm light", bank)
by_name = {n: ok for n, ok, _ in checks}
check("no camera lead is caught", not by_name["Leads with a camera movement"])
check("no motion is caught", not by_name["Describes motion"])

checks, _ = ml.lint(
    "cinematic slow dolly in toward a man, then the camera pulls out to reveal the room",
    bank)
by_name = {n: ok for n, ok, _ in checks}
check("push-in + pull-out is caught", not by_name["No contradictions"])

checks, _ = ml.lint(
    "camera slowly orbits around a man while the camera smoothly tracking behind him", bank)
by_name = {n: ok for n, ok, _ in checks}
check("two competing moves are caught", not by_name["One dominant movement"])

checks, _ = ml.lint(
    "camera cranes down and slowly orbits around a warrior on a battlefield, descending while circling",
    bank, "combo-crane-orbit")
by_name = {n: ok for n, ok, _ in checks}
check("a declared combo is allowed two moves", by_name["One dominant movement"])

checks, _ = ml.lint(
    "camera slowly descends from above the surface into the kitchen underwater, bubbles rising",
    bank)
by_name = {n: ok for n, ok, _ in checks}
check("underwater in a kitchen is caught", not by_name["No contradictions"])

print()
print("=== RULE 2: think ahead - the still must support the move ===")
tight = {"subject": "a woman", "setting": "a room", "shot": "portrait"}
warnings = bm.check_compatibility(bank, "orbit-360", tight)
check("orbit on a tight portrait warns about space",
      any(w["requirement"] == "space" for w in warnings), str([w["requirement"] for w in warnings]))

dry = {"subject": "a woman", "setting": "a bright apartment kitchen"}
warnings = bm.check_compatibility(bank, "dive-underwater", dry)
check("underwater with no water warns",
      any(w["requirement"] == "water" for w in warnings), str([w["requirement"] for w in warnings]))

faceless = {"setting": "an empty street"}
warnings = bm.check_compatibility(bank, "over-shoulder", faceless)
check("over-the-shoulder with no subject warns",
      any(w["requirement"] == "subject" for w in warnings), str([w["requirement"] for w in warnings]))

facing = {"subject": "a woman", "setting": "a street", "action": "smiling at the camera"}
warnings = bm.check_compatibility(bank, "track-behind", facing)
check("tracking behind a face-on shot warns",
      any(w["requirement"] == "shoulder" for w in warnings), str([w["requirement"] for w in warnings]))

good_pair = {"subject": "a woman", "setting": "a wide rooftop overlooking the city",
             "action": "walking away from camera", "shot": "environmental"}
check("a compatible pairing produces no warnings",
      bm.check_compatibility(bank, "track-behind", good_pair) == [],
      str(bm.check_compatibility(bank, "track-behind", good_pair)))

check("warnings carry a fix",
      all(w["fix"] for w in bm.check_compatibility(bank, "orbit-360", tight)))

print()
print("=== precedence: hints fill gaps, explicit choices win ===")
silent = {"subject": "a woman", "seed": 0}
merged = bm.apply_image_hints(bank, "orbit-360", silent)
check("hint fills a silent shot", merged.get("shot") == "environmental", str(merged.get("shot")))
check("hint fills composition",
      merged.get("overrides", {}).get("composition") == ["natural framing"],
      str(merged.get("overrides")))

explicit = {"subject": "a woman", "seed": 0, "shot": "portrait"}
merged = bm.apply_image_hints(bank, "orbit-360", explicit)
check("explicit shot survives", merged.get("shot") == "portrait", str(merged.get("shot")))
notes = bm.hint_conflicts(bank, "orbit-360", explicit)
check("the conflict is reported", len(notes) == 1, str(notes))
check("reported, not corrected", merged.get("shot") == "portrait")

own = {"subject": "a woman", "seed": 0, "overrides": {"composition": ["rule of thirds"]}}
merged = bm.apply_image_hints(bank, "orbit-360", own)
check("an explicit composition override survives",
      merged["overrides"]["composition"] == ["rule of thirds"], str(merged["overrides"]))

print()
print("=== hints never break the image score ===")
broken = []
for key in bank["movements"]:
    merged = bm.apply_image_hints(bank, key, {"subject": "a woman in a room", "seed": 0})
    prompt, _ = bp.compose(image_bank, merged)
    present, _, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    if len(present) != 8 or banned:
        broken.append((key, len(present), banned))
check("all 40 movements still yield 8/8 stills", not broken, str(broken[:4]))

print()
print("=== bank versioning ===")
import history as hist
# The version is expected to move whenever the term lists change, so assert the
# machinery rather than the number - pinning the literal makes a correct bump
# look like a regression.
version = image_bank.get("version")
check("prompt_bank carries a version", isinstance(version, int) and version >= 1,
      str(version))
check("history reads the same one", hist.current_bank_version() == version, str(version))
stale = [{"rating": 5, "bank_version": version - 1, "layers": {"core": ["photorealistic"]}}]
fresh, skipped = hist.usable(stale)
check("a stale entry is excluded, not mixed", fresh == [] and skipped == 1,
      "fresh={} skipped={}".format(len(fresh), skipped))
current = [{"rating": 5, "bank_version": version, "layers": {"core": ["photorealistic"]}}]
fresh, skipped = hist.usable(current)
check("a current entry is used", len(fresh) == 1 and skipped == 0)

print()
print("=== glossary ===")
import json
glossary = json.loads((ROOT / "tools" / "glossary.json").read_text(encoding="utf-8"))
check("50 terms", len(glossary["terms"]) == 50, str(len(glossary["terms"])))
cats = {t["category"] for t in glossary["terms"]}
check("every term has a known category", cats <= set(glossary["categories"]), str(cats))
check("every term has a definition", all(t["definition"] for t in glossary["terms"]))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL MOTION CHECKS PASSED")
