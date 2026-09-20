"""tools/macro_insert_bank.json + build_macro_insert.py + macro_insert_lint.py -
a full-face beauty macro (stage one, creates the face) plus feature-scoped
extreme-macro inserts of the eye, mouth and cheek (stage two, derive from it).

The audit that matters here is "no bank phrase is invisible to realism_lint",
run PER PHRASE rather than against an assembled override - an assembled texture
list passes on one legacy "pores" hit and would hide five undetectable
siblings, which is exactly the failure this audit exists to catch. It is also
what makes tests/test_story.py's hash-bump comment ("confirmed by running
lint(), not assumed") a true statement rather than a claim.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_macro_insert.py"
LINT = ROOT / "tools" / "macro_insert_lint.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_macro_insert as bmi  # noqa: E402
import build_prompt as bp  # noqa: E402
import macro_insert_lint as mlint  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bmi.load_bank()
image_bank = bp.load_bank()
lighting_bank = bl.load_bank()
camera_bank = bca.load_bank()

NEW_KEYS = ["peach fuzz", "subsurface scattering", "pore-level",
            "sebaceous", "tonal variation"]

print("=== the bank is well-formed ===")
check("four inserts", len(bmi.inserts(bank)) == 4, str(sorted(bmi.inserts(bank))))
check("three sets", len(bmi.sets(bank)) == 3, str(sorted(bmi.sets(bank))))
for name, entry in bmi.inserts(bank).items():
    check("'{}' has label/scope/kind/overrides".format(name),
          all(entry.get(f) for f in ("label", "scope", "kind", "overrides")))
    check("'{}' lighting_setup is real".format(name),
          entry["lighting_setup"] in bl.setups(lighting_bank), entry["lighting_setup"])
    for tech in entry.get("techniques", []):
        check("'{}' technique '{}' is real".format(name, tech),
              tech in bl.techniques(lighting_bank))
    check("'{}' size is a real camera_angle size".format(name),
          entry["size"] in bca.sizes(camera_bank), entry["size"])
    # The structural counterpart to the linter's no_custom_shot check.
    check("'{}' takes no shot/shot_custom".format(name),
          "shot" not in entry.get("overrides", {}) and "shot_custom" not in entry)

kinds = [e["kind"] for e in bmi.inserts(bank).values()]
check("exactly one portrait kind, three inserts",
      kinds.count("portrait") == 1 and kinds.count("insert") == 3, str(kinds))
check("only the insert kinds carry a preserve phrase",
      all(bool(e.get("preserve")) == (e["kind"] == "insert")
          for e in bmi.inserts(bank).values()))
check("full-face frames the whole face, not one part of it",
      bmi.inserts(bank)["full-face"]["size"] == "close-up",
      bmi.inserts(bank)["full-face"]["size"])
for key, cfg in bmi.sets(bank).items():
    check("set '{}' names only real inserts".format(key),
          all(n in bmi.inserts(bank) for n in cfg["inserts"]), str(cfg["inserts"]))

print()
print("=== no bank phrase is invisible to realism_lint (run per phrase, not assumed) ===")


def hits(layer, text):
    low = text.lower()
    return [k for k in rl.DETECT[layer]["keys"] if rl._layer_key_present(k, low)]


undetectable = []
for name, entry in bmi.inserts(bank).items():
    for phrase in entry["overrides"].get("texture", []):
        if not hits("texture", phrase):
            undetectable.append("{}/{}".format(name, phrase[:40]))
check("no texture phrase is invisible", not undetectable, "; ".join(undetectable))

# Composition is audited as the ASSEMBLED override, not per phrase, because it
# is deliberately two different things: the size phrase from
# camera_angle_bank.json carries detection, and the entry's own framing clause
# is supplementary prose that is not expected to be detectable alone.
undetectable = []
for name in bmi.inserts(bank):
    shot = bmi.compose_macro_set(bank, image_bank, lighting_bank, camera_bank,
                                 {"subject": "a woman", "seed": 0}, "ref.png", [name])[0]
    assembled = ", ".join(shot["spec"]["overrides"]["composition"])
    if not hits("composition", assembled):
        undetectable.append("{}/{}".format(name, assembled[:40]))
check("every assembled composition override is detectable", not undetectable,
      "; ".join(undetectable))

# A key added speculatively and never earned is dead weakening of the gate.
all_texture = [p for e in bmi.inserts(bank).values() for p in e["overrides"]["texture"]]
unearned = []
for key in NEW_KEYS:
    sole = [p for p in all_texture
            if rl._layer_key_present(key, p.lower()) and hits("texture", p) == [key]]
    if not sole:
        unearned.append(key)
check("every new DETECT key is the sole hit for at least one bank phrase",
      not unearned, "unearned: " + ", ".join(unearned))

print()
print("=== every insert composes and scores a strict 8/8, both forms ===")
for name in bmi.inserts(bank):
    for detailed in (False, True):
        shots = bmi.compose_macro_set(bank, image_bank, lighting_bank, camera_bank,
                                      {"subject": "a woman in her thirties", "seed": 0},
                                      "face-ref.png", [name])
        spec = shots[0]["spec"]
        prompt, _layers = bp.compose(image_bank, spec, detailed=detailed)
        present, _missing, banned, warn, neg = rl.lint(prompt.lower(), image_bank)
        form = "long" if detailed else "short"
        check("'{}' scores 8/8 ({})".format(name, form),
              len(present) == 8 and not banned, "{}/8 banned={}".format(len(present), banned))
        check("'{}' trips no soft warning ({})".format(name, form), not warn, str(warn))
        check("'{}' carries the negative block ({})".format(name, form), neg)

print()
print("=== compose_macro_set: one face, four crops ===")
BASE = {"subject": "a woman in her thirties", "seed": 0}
REF = "temp/resources/characters/ada-face.png"
shots = bmi.compose_macro_set(bank, image_bank, lighting_bank, camera_bank,
                              BASE, REF, bank["sets"]["beauty-macro"]["inserts"])
check("four shots produced", len(shots) == 4, str(len(shots)))
full = next(s for s in shots if s["insert"] == "full-face")
derived = [s for s in shots if s["kind"] == "insert"]
check("stage one is not identity-locked", not full["spec"].get("lock_identity"))
check("stage one carries no reference", not full["spec"].get("reference"))
check("stage one has no lock tail in its prompt", bp.LOCK_TAIL not in full["prompt"])
check("every insert is identity-locked", all(s["spec"]["lock_identity"] for s in derived))
check("every insert carries the reference", all(s["spec"]["reference"] == REF for s in derived))
check("every insert has the lock tail", all(bp.LOCK_TAIL in s["prompt"] for s in derived))
check("no shot carries a scene lock",
      not any(s["spec"].get("lock_scene") or bp.RELIGHT_LOCK_TAIL in s["prompt"] for s in shots))
check("one subject across the batch", len({s["spec"]["subject"] for s in shots}) == 1)
check("no shot carries shot/shot_custom",
      not any(s["spec"].get("shot") or s["spec"].get("shot_custom") for s in shots))
for shot in derived:
    preserve = bmi.inserts(bank)[shot["insert"]]["preserve"]
    check("'{}' preserve phrase is in its own prompt".format(shot["insert"]),
          preserve.lower() in shot["prompt"].lower())
    others = [s for s in shots if s is not shot]
    check("'{}' preserve phrase is in no other prompt".format(shot["insert"]),
          not any(preserve.lower() in o["prompt"].lower() for o in others))

carried = bmi.compose_macro_set(bank, image_bank, lighting_bank, camera_bank,
                                dict(BASE, extra=["a faint scar above one eyebrow"],
                                     variation={"setting": "a rooftop"}, shot="selfie"),
                                REF, ["eye"])
check("a caller's own extra survives alongside preserve",
      "a faint scar above one eyebrow" in carried[0]["prompt"])
check("a carried variation is stripped", "variation" not in carried[0]["spec"])
check("a carried shot preset is stripped", not carried[0]["spec"].get("shot"))

print()
print("=== macro_insert_lint: a good batch passes every check ===")
results = mlint.lint(bank, shots, "beauty-macro")
got, total = mlint.score(results)
check("full score on a well-formed batch", got == total, "{}/{}".format(got, total))


def only_fails(broken, key, requested="beauty-macro"):
    by_key = {k: p for k, _l, p, _d in mlint.lint(bank, broken, requested)}
    return by_key.get(key) is False


print()
print("=== macro_insert_lint: catches a real defect ===")
import copy  # noqa: E402

b = copy.deepcopy(shots)
b[1]["prompt"] = b[1]["prompt"].replace(bmi.inserts(bank)["eye"]["preserve"], "")
check("a stripped preserve phrase is caught", only_fails(b, "feature_scope"))

b = copy.deepcopy(shots)
b[1]["spec"]["lock_identity"] = False
check("a missing identity lock is caught", only_fails(b, "lock_identity"))

b = copy.deepcopy(shots)
b[0]["spec"]["lock_identity"] = True
check("a lock on the face-creating shot is caught", only_fails(b, "lock_identity"))

b = copy.deepcopy(shots)
b[1]["spec"]["lock_scene"] = True
check("a stray scene lock is caught", only_fails(b, "no_stray_scene_lock"))

b = copy.deepcopy(shots)
b[1]["spec"]["shot_custom"] = "a wide establishing shot"
check("a shot_custom grab is caught", only_fails(b, "no_custom_shot"))

b = copy.deepcopy(shots)
b.append(copy.deepcopy(b[1]))
check("a duplicate insert is caught", only_fails(b, "unique_inserts"))

b = copy.deepcopy(shots)
b[2]["spec"]["subject"] = "a different person entirely"
check("subject drift is caught", only_fails(b, "subject_unchanged"))

b = copy.deepcopy(shots)[:3]
check("a dropped insert is caught", only_fails(b, "inserts_present"))

b = copy.deepcopy(shots)
b[3]["spec"]["overrides"]["texture"] = ["a nice face"]
b[3]["prompt"], _ = bp.compose(image_bank, b[3]["spec"])
check("stripped macro vocabulary is caught", only_fails(b, "macro_vocabulary"))
# ...and this is exactly why macro_vocabulary is a separate check from realism.
# With every macro phrase gone, the prompt STILL scores a full 8/8: DETECT's
# plain "texture" key is start-anchored and fires on the core layer's own
# "true-to-life textures". realism alone would have waved this through.
present, _m, _b, _w, _n = rl.lint(b[3]["prompt"].lower(), image_bank)
check("realism alone would NOT have caught it (the loophole macro_vocabulary closes)",
      len(present) == 8, "{}/8".format(len(present)))

print()
print("=== the shared bank is untouched ===")
check("prompt_bank.json gained no shot preset",
      len(image_bank["shot_presets"]) == 6
      and "beauty-macro" not in image_bank["shot_presets"],
      str(sorted(image_bank["shot_presets"])))

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every set and insert",
      all(k in p.stdout for k in list(bmi.sets(bank)) + list(bmi.inserts(bank))))

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

p = run(["--subject", "a woman", "--reference", REF, "--set", "nope", "--no-write"])
check("an unknown --set exits non-zero", p.returncode != 0)

p = run(["--subject", "a woman", "--reference", REF, "--insert", "nope", "--no-write"])
check("an unknown --insert exits non-zero", p.returncode != 0)

p = run(["--reference", REF, "--set", "inserts-only", "--no-write"])
check("no --spec/--subject exits non-zero", p.returncode != 0)

p = run(["--subject", "a woman", "--set", "inserts-only", "--no-write"])
check("inserts without --reference exits non-zero", p.returncode != 0)
check("...and says which inserts need one", "eye" in p.stderr + p.stdout)

p = run(["--subject", "a woman", "--set", "full-face-only", "--no-write"])
check("full-face alone needs no --reference", p.returncode == 0, p.stderr[:160])

p = run(["--subject", "a woman", "--no-write"])
check("neither --set nor --insert exits non-zero", p.returncode != 0)

p = run(["--subject", "a woman", "--reference", REF, "--set", "beauty-macro", "--no-write"])
check("a well-formed run exits 0", p.returncode == 0, p.stderr[:160])
check("prints every shot", p.stdout.count("===") == 4, str(p.stdout.count("===")))

p = run(["--subject", "a woman", "--reference", REF,
         "--insert", "eye", "--insert", "mouth", "--no-write"])
check("repeated --insert builds exactly those two", p.stdout.count("===") == 2,
      str(p.stdout.count("===")))

lint_p = subprocess.run([sys.executable, str(LINT), "--help"],
                        capture_output=True, text=True, cwd=str(ROOT))
check("macro_insert_lint --help exits 0", lint_p.returncode == 0, lint_p.stdout[:120])

lint_p = subprocess.run([sys.executable, str(LINT), "--macro", "does-not-exist.json"],
                        capture_output=True, text=True, cwd=str(ROOT))
check("macro_insert_lint on a missing file exits non-zero", lint_p.returncode != 0)

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL MACRO INSERT CHECKS PASSED")

sys.exit(1 if fails else 0)
