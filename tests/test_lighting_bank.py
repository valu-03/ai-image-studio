"""tools/lighting_bank.json + build_lighting.py - the new Lighting section's data
and composer, verified the same way the original 8 realism layers already are:
every phrase the bank can produce has to be detectable by realism_lint, a
contradictory combination has to be caught rather than silently composed, and
a full prompt built with a lighting override still has to score 8/8.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_lighting.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_lighting as bl  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bl.load_bank()
image_bank = bp.load_bank()


def hits(text):
    lower = text.lower()
    return [k for k in rl.DETECT["lighting"]["keys"] if k in lower]


print("=== every bank phrase is detectable (the paired audit, run for real) ===")
undetectable = []
for kind, items in [("direction", bl.directions(bank)), ("quality", bl.qualities(bank)),
                     ("source", bl.sources(bank)), ("setup", bl.setups(bank)),
                     ("technique", bl.techniques(bank))]:
    for key, cfg in items.items():
        if not hits(cfg["phrase"]):
            undetectable.append("{}/{}".format(kind, key))
check("no bank phrase is invisible to realism_lint", not undetectable,
      ", ".join(undetectable))

print()
print("=== every setup composes and scores 8/8 in a full prompt ===")
for key, cfg in bl.setups(bank).items():
    phrase, warnings = bl.compose_lighting(bank, setup=key)
    check("setup '{}' composes with no warnings".format(key), not warnings, str(warnings))
    spec = {"subject": "a woman in her thirties", "seed": 1,
            "overrides": {"lighting": [phrase, "realistic shadows"]}}
    prompt, _ = bp.compose(image_bank, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    check("setup '{}' scores 8/8".format(key), len(present) == 8 and not banned,
          "missing: {}".format(missing))

print()
print("=== the deep path composes direction + quality + source ===")
phrase, warnings = bl.compose_lighting(bank, direction="loop", quality="soft", source="led-panel")
check("a non-contradictory deep-path combo has no warnings", not warnings, str(warnings))
check("the phrase carries all three parts",
      "loop" in phrase.lower() and "soft" in phrase.lower() and "led" in phrase.lower(),
      phrase)

print()
print("=== a contradictory combination is warned, not silently accepted ===")
phrase, warnings = bl.compose_lighting(bank, quality="hard", source="overcast")
check("hard + overcast is flagged", len(warnings) == 1, str(warnings))
check("the phrase is still composed (a warning, not a refusal)", bool(phrase))

phrase, warnings = bl.compose_lighting(bank, quality="soft", source="direct-sun")
check("soft + direct-sun is flagged", len(warnings) == 1, str(warnings))

phrase, warnings = bl.compose_lighting(bank, quality="hard", source="direct-sun")
check("hard + direct-sun (a real pairing) is NOT flagged", not warnings, str(warnings))

print()
print("=== realism_techniques stack additively on either path ===")
phrase, _ = bl.compose_lighting(bank, setup="loop", techniques_=["catchlights", "falloff"])
check("both techniques appear in the composed phrase",
      "catchlight" in phrase.lower() and "falling off" in phrase.lower(), phrase)

print()
print("=== bad input is refused, not silently ignored ===")
try:
    bl.compose_lighting(bank, setup="not-a-real-setup")
    check("an unknown setup raises", False)
except bl.LightingError:
    check("an unknown setup raises", True)

try:
    bl.compose_lighting(bank, setup="rembrandt", direction="loop")
    check("setup + direction together is refused", False)
except bl.LightingError:
    check("setup + direction together is refused", True)

try:
    bl.compose_lighting(bank)
    check("giving nothing at all raises", False)
except bl.LightingError:
    check("giving nothing at all raises", True)

try:
    bl.compose_lighting(bank, direction="loop", techniques_=["not-a-real-technique"])
    check("an unknown technique raises", False)
except bl.LightingError:
    check("an unknown technique raises", True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every setup", all(key in p.stdout for key in bl.setups(bank)))

p = run(["--setup", "rembrandt"])
check("--setup exits 0", p.returncode == 0, p.stderr[:160])
check("--setup prints the phrase", "Rembrandt lighting" in p.stdout, p.stdout[:160])

p = run(["--quality", "hard", "--source", "overcast"])
check("a contradictory CLI combo still exits 0 (warned, not refused)", p.returncode == 0)
check("the CLI prints the warning to stderr", "huge, close, diffuse source" in p.stderr,
      p.stderr[:200])

p = run(["--setup", "not-a-real-setup"])
check("an unknown --setup exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0 and documents the two paths",
      p.returncode == 0 and "FAST" in p.stdout and "DEEP" in p.stdout, p.stdout[:200])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL LIGHTING BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
