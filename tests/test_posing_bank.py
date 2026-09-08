"""tools/posing_bank.json + build_posing.py - the Posing section's data and
composer. Posing is deliberately NOT one of realism_lint.py's 8 gated
photorealism layers (it's descriptive spec content, like wardrobe/setting/
mood), so this suite does not run a detectability audit against DETECT the
way test_lighting_bank.py/test_composition_bank.py do - instead it confirms
a posed action field never interferes with the 8 layers that ARE gated.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_posing.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_posing as bpo  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bpo.load_bank()
image_bank = bp.load_bank()

print("=== every named pose composes ===")
for key, cfg in bpo.poses(bank).items():
    phrase, warnings = bpo.compose_posing(bank, pose=key)
    check("pose '{}' composes with no warnings".format(key), not warnings, str(warnings))
    check("pose '{}' phrase matches the bank entry".format(key), phrase == cfg["phrase"], phrase)

print()
print("=== a posed action field never interferes with the 8 gated layers ===")
for key in list(bpo.poses(bank))[:3]:
    phrase, _ = bpo.compose_posing(bank, pose=key)
    spec = {"subject": "a woman in her thirties", "seed": 1, "action": phrase}
    prompt, _ = bp.compose(image_bank, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    check("pose '{}' in the action field still scores 8/8 on the other layers".format(key),
          len(present) == 8 and not banned, "missing: {}".format(missing))
    check("the pose phrase itself appears in the composed prompt", phrase.lower() in prompt.lower())

print()
print("=== typed custom text is used literally, not rejected ===")
phrase, warnings = bpo.compose_posing(bank, pose="leaning against a doorway, arms crossed")
check("a wholly custom pose is used exactly as typed",
      phrase == "leaning against a doorway, arms crossed", phrase)
check("no warnings", not warnings, str(warnings))

print()
print("=== techniques stack additively, technique_custom appends one more ===")
phrase, _ = bpo.compose_posing(
    bank, pose="s-curve", techniques_=["relaxed-hands", "negative-space-limbs"],
    technique_custom="a slight smile")
check("both named techniques and the custom phrase all appear",
      "relaxed and loose" in phrase and "negative space" in phrase and "slight smile" in phrase,
      phrase)

print()
print("=== bad input is refused, not silently ignored ===")
try:
    bpo.compose_posing(bank)
    check("giving no pose at all raises", False)
except bpo.PosingError:
    check("giving no pose at all raises", True)

try:
    bpo.compose_posing(bank, pose="s-curve", techniques_=["not-a-real-technique"])
    check("an unknown technique raises", False)
except bpo.PosingError:
    check("an unknown technique raises", True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every pose category",
      all(cat in p.stdout for cat in bank["poses"]), p.stdout[:200])

p = run(["--pose", "weight-back-leg"])
check("--pose exits 0", p.returncode == 0, p.stderr[:160])
check("--pose prints the phrase", "weight shifted onto the back leg" in p.stdout, p.stdout[:160])

p = run(["--pose", "a hand-typed pose instruction", "--technique", "relaxed-posture"])
check("typed --pose + --technique exits 0", p.returncode == 0, p.stderr[:160])
check("both appear", "a hand-typed pose instruction" in p.stdout and "relaxed" in p.stdout.lower(),
      p.stdout[:200])

p = run([])
check("no arguments at all exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:160])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL POSING BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
