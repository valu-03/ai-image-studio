"""tools/relight_bank.json + build_relight.py + relight_lint.py - relighting and
re-angling an EXISTING photo, scene locked (the inverse of consistent-character.md's
identity lock).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_relight.py"
LINT = ROOT / "tools" / "relight_lint.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_relight as br  # noqa: E402
import relight_lint as rlint  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = br.load_bank()
image_bank = bp.load_bank()
lighting_bank = bl.load_bank()
camera_bank = bca.load_bank()

print("=== the bank is well-formed ===")
check("three named sets", len(br.sets(bank)) == 3, str(sorted(br.sets(bank))))
for key, cfg in br.sets(bank).items():
    check("'{}' has shots and a label".format(key), bool(cfg.get("shots")) and bool(cfg.get("label")))
    for shot in cfg["shots"]:
        if shot.get("lighting_setup"):
            check("'{}' lighting_setup '{}' is a real lighting_bank setup".format(key, shot["lighting_setup"]),
                  shot["lighting_setup"] in bl.setups(lighting_bank))
        if shot.get("side"):
            check("'{}' side '{}' is a real camera_angle_bank side".format(key, shot["side"]),
                  shot["side"] in bca.sides(camera_bank))

BASE_SPEC = {"subject": "a woman in her thirties", "seed": 0}
REFERENCE = "temp/resources/images/fixture-ref.png"

print()
print("=== compose_relight_set: scene stays fixed, only lighting/angle move ===")
shots = br.compose_relight_set(bank, image_bank, lighting_bank, camera_bank,
                                BASE_SPEC, REFERENCE, bank["sets"]["full-set"]["shots"])
check("four shots produced", len(shots) == 4, str(len(shots)))
check("every shot is scene-locked", all(s["spec"].get("lock_scene") for s in shots))
check("every shot carries the reference", all(s["spec"].get("reference") == REFERENCE for s in shots))
check("subject is identical across the batch",
      len({s["spec"]["subject"] for s in shots}) == 1)
check("every shot has a distinct (lighting, angle) combo",
      len({(s["lighting_setup"], s["side"]) for s in shots}) == 4)
check("the scene-lock clause reaches every prompt",
      all(bp.RELIGHT_LOCK_TAIL in s["prompt"] for s in shots))

print()
print("=== relight_lint: a good batch passes every check ===")
results = rlint.lint(image_bank, shots)
got, total = rlint.score(results)
check("full score on a well-formed batch", got == total, "{}/{}".format(got, total))

print()
print("=== relight_lint: a lighting-only batch scores a full 8/8 (camera untouched) ===")
lighting_only = br.compose_relight_set(bank, image_bank, lighting_bank, camera_bank,
                                       BASE_SPEC, REFERENCE, bank["sets"]["relight-pass"]["shots"])
present, _missing, _banned, _warn, _neg = __import__("realism_lint").lint(
    lighting_only[0]["prompt"].lower(), image_bank)
check("lighting-only shot scores 8/8", len(present) == 8, str(len(present)))

print()
print("=== relight_lint: catches a real defect ===")
broken = [dict(shots[0]), dict(shots[1])]
broken[1] = dict(broken[1])
broken[1]["spec"] = dict(broken[1]["spec"])
broken[1]["spec"]["subject"] = "a different person entirely"
results = rlint.lint(image_bank, broken)
check("subject drift is caught", not all(passed for _, _, passed, _ in results),
      str([(k, p) for k, _, p, _ in results]))

dup = [dict(shots[0]), dict(shots[0])]
results = rlint.lint(image_bank, dup)
by_key = {key: passed for key, _label, passed, _detail in results}
check("a duplicate combo is caught", not by_key["unique_combos"])

unlocked = [dict(shots[0])]
unlocked[0] = dict(unlocked[0])
unlocked[0]["spec"] = dict(unlocked[0]["spec"])
unlocked[0]["spec"]["lock_scene"] = False
results = rlint.lint(image_bank, unlocked)
by_key = {key: passed for key, _label, passed, _detail in results}
check("a missing scene lock is caught", not by_key["lock_scene"])

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every set", all(k in p.stdout for k in br.sets(bank)))

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

p = run(["--subject", "a woman", "--reference", REFERENCE, "--set", "nope", "--no-write"])
check("an unknown --set exits non-zero", p.returncode != 0)

p = run(["--reference", REFERENCE, "--set", "relight-pass", "--no-write"])
check("no --spec/--subject exits non-zero", p.returncode != 0)

p = run(["--subject", "a woman", "--set", "relight-pass", "--no-write"])
check("no --reference exits non-zero", p.returncode != 0)

p = run(["--subject", "a woman", "--reference", REFERENCE, "--set", "relight-pass", "--no-write"])
check("a well-formed run exits 0", p.returncode == 0, p.stderr[:160])
check("prints every shot's prompt", p.stdout.count("===") == 4, str(p.stdout.count("===")))

lint_p = subprocess.run(
    [sys.executable, str(LINT), "--help"], capture_output=True, text=True, cwd=str(ROOT))
check("relight_lint --help exits 0", lint_p.returncode == 0, lint_p.stdout[:120])

lint_p = subprocess.run(
    [sys.executable, str(LINT), "--relight", "does-not-exist.json"],
    capture_output=True, text=True, cwd=str(ROOT))
check("relight_lint on a missing file exits non-zero", lint_p.returncode != 0)

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL RELIGHT CHECKS PASSED")

sys.exit(1 if fails else 0)
