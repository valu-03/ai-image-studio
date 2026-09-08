"""tools/composition_bank.json + build_composition.py - the Composition
section's opt-in realism techniques, verified the same way the Lighting
section's own bank/composer already is: every phrase has to be detectable by
realism_lint, a full prompt built with a guide or custom text still has to
score 8/8, and bad input has to be refused rather than silently accepted.

The seven named geometries themselves are NOT retested here - they already
live in tools/prompt_bank.json and are covered exhaustively by
tests/test_composition.py, which this file leaves untouched.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_composition.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_composition as bc  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


comp_bank = bc.load_bank()
image_bank = bp.load_bank()


def hits(text):
    lower = text.lower()
    return [k for k in rl.DETECT["composition"]["keys"] if k in lower]


print("=== every technique phrase is detectable (the paired audit, run for real) ===")
undetectable = []
for key, cfg in bc.techniques(comp_bank).items():
    if not hits(cfg["phrase"]):
        undetectable.append("technique/{}".format(key))
check("no technique phrase is invisible to realism_lint", not undetectable,
      ", ".join(undetectable))

print()
print("=== every guide, alone, still composes and scores 8/8 in a full prompt ===")
for key in bp.guides(image_bank):
    phrase, warnings = bc.compose_composition(image_bank, comp_bank, guide=key)
    check("guide '{}' composes with no warnings".format(key), not warnings, str(warnings))
    spec = {"subject": "a woman in her thirties", "seed": 1,
            "composition_guide": key}
    prompt, _ = bp.compose(image_bank, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    check("guide '{}' scores 8/8".format(key), len(present) == 8 and not banned,
          "missing: {}".format(missing))

print()
print("=== custom text overrides a picked guide (precedence check) ===")
phrase, warnings = bc.compose_composition(
    image_bank, comp_bank, guide="rule-of-thirds",
    custom="framed low, looking up at the subject")
check("custom text wins over the guide", phrase == "framed low, looking up at the subject",
      phrase)
check("no warnings", not warnings, str(warnings))

print()
print("=== techniques stack additively and stay detectable in a full prompt ===")
phrase, warnings = bc.compose_composition(
    image_bank, comp_bank, guide="diagonals",
    techniques_=["lead-room", "negative-space"])
check("both techniques appear in the composed phrase",
      "lead room" in phrase.lower() and "negative space" in phrase.lower(), phrase)
spec = {"subject": "a man in his forties", "seed": 2,
        "composition_guide_custom": phrase}
prompt, _ = bp.compose(image_bank, spec)
present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
check("still scores 8/8 with two techniques stacked on a guide",
      len(present) == 8 and not banned, "missing: {}".format(missing))

print()
print("=== the atmosphere technique (haze separating depth layers) ===")
phrase, warnings = bc.compose_composition(
    image_bank, comp_bank, guide="rule-of-thirds", techniques_=["atmosphere"])
check("atmosphere phrase appears", "haze" in phrase.lower(), phrase)
check("no warnings", not warnings, str(warnings))

print()
print("=== technique_custom adds one more free-text phrase beyond the checklist ===")
phrase, warnings = bc.compose_composition(
    image_bank, comp_bank, guide="triangle", techniques_=["negative-space"],
    technique_custom="the horizon kept low in the frame")
check("both the checklist technique and the custom phrase appear",
      "negative space" in phrase.lower() and "horizon kept low" in phrase.lower(), phrase)
check("no warnings", not warnings, str(warnings))

phrase, _ = bc.compose_composition(
    image_bank, comp_bank, custom="framed through a car window",
    technique_custom="reflections faintly visible in the glass")
check("technique_custom stacks on custom framing text too, not just a guide",
      "car window" in phrase and "reflections faintly visible" in phrase, phrase)

print()
print("=== bad input is refused, not silently ignored ===")
try:
    bc.compose_composition(image_bank, comp_bank, guide="not-a-real-guide")
    check("an unknown guide raises", False)
except bc.CompositionError:
    check("an unknown guide raises", True)

try:
    bc.compose_composition(image_bank, comp_bank)
    check("giving neither guide nor custom raises", False)
except bc.CompositionError:
    check("giving neither guide nor custom raises", True)

try:
    bc.compose_composition(image_bank, comp_bank, custom="a plain framing note",
                            techniques_=["not-a-real-technique"])
    check("an unknown technique raises", False)
except bc.CompositionError:
    check("an unknown technique raises", True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every guide", all(key in p.stdout for key in bp.guides(image_bank)))
check("--list names every technique", all(key in p.stdout for key in bc.techniques(comp_bank)))

p = run(["--guide", "rule-of-thirds"])
check("--guide exits 0", p.returncode == 0, p.stderr[:160])
check("--guide prints the phrase", "rule of thirds" in p.stdout, p.stdout[:160])

p = run(["--custom", "a hand-typed framing note", "--technique", "lead-room"])
check("--custom + --technique exits 0", p.returncode == 0, p.stderr[:160])
check("--custom beats nothing else and the technique is appended",
      "a hand-typed framing note" in p.stdout and "lead room" in p.stdout.lower(),
      p.stdout[:200])

p = run(["--guide", "triangle", "--technique-custom", "the horizon kept low in the frame"])
check("--technique-custom exits 0 and appends the phrase",
      p.returncode == 0 and "horizon kept low" in p.stdout, p.stdout[:200])

p = run(["--guide", "not-a-real-guide"])
check("an unknown --guide exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:160])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL COMPOSITION BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
