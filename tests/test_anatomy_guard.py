"""The image path's body guard, and the one template that is not photoreal.

Both came out of a reference prompt for premium mythological illustration -
a slot-structured brief whose "Avoid" paragraph named the failures nothing on
the image path was guarding against: distorted anatomy, extra limbs,
duplicated figures, malformed hands.

TWO SEPARATE THINGS, deliberately, because they belong in different banks:

  prompt_bank.anatomy_guard   five phrases, OPT-IN, appended by
                              build_prompt.compose(anatomy_guard=True). Of the
                              three paths that compose a prompt, the ordinary
                              image path was the only one with no body guard -
                              motion_bank had `avatar_guard` for video, and
                              anatomy_bank had this exact vocabulary inside one
                              template's guard slot.

  mythic-illustration         a 12-slot anatomy_bank template, and the FIRST
                              image template that is not photoreal. It declares
                              no camera, lens or grain slot: those three layers
                              describe a capture device and an illustration was
                              not captured. It keeps lighting, colour and
                              texture, which mean as much to a painting.

The load-bearing assertion in this file is the one that proves the guard is
genuinely opt-in: composing without the flag must be BYTE-IDENTICAL to what
the app produced before the key existed. That is what let prompt_bank go from
v11 to v12 without a single other suite's expected prompt changing.
"""
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bp.load_bank()

SPEC = {"subject": "Athena on the temple steps", "seed": 7, "aspect": "4:5"}

print("=== the guard exists, in the bank and in code ===")
check("prompt_bank carries an anatomy_guard list",
      isinstance(bank.get("anatomy_guard"), list) and bank["anatomy_guard"])
check("it is NOT folded into the standing negatives",
      not any(g in bank["negatives"] for g in bank["anatomy_guard"]))
check("the negatives list is still exactly the seven it was",
      len(bank["negatives"]) == 7, str(len(bank["negatives"])))
check("build_prompt has a code-level fallback, like build_motion's",
      isinstance(bp.DEFAULT_ANATOMY_GUARD, list) and bp.DEFAULT_ANATOMY_GUARD)
check("the bank's list and the fallback agree",
      bank["anatomy_guard"] == bp.DEFAULT_ANATOMY_GUARD)
for phrase in bank["anatomy_guard"]:
    check("'{}' is phrased as a negation".format(phrase), phrase.startswith("no "))

print()
print("=== OPT-IN: without the flag, output is byte-identical ===")
# The whole reason v11 -> v12 broke no other suite. If this ever fails, the
# guard has stopped being opt-in and every expected prompt in the repo is wrong.
for detailed in (False, True):
    plain = bp.compose(bank, dict(SPEC), detailed=detailed)[0]
    again = bp.compose(bank, dict(SPEC), detailed=detailed, anatomy_guard=False)[0]
    check("detailed={}: anatomy_guard=False changes nothing".format(detailed),
          plain == again)
    guarded = bp.compose(bank, dict(SPEC), detailed=detailed, anatomy_guard=True)[0]
    check("detailed={}: the flag does add something".format(detailed),
          guarded != plain and len(guarded) > len(plain))
    for phrase in bank["anatomy_guard"]:
        check("detailed={}: '{}' reaches the prompt".format(detailed, phrase),
              phrase in guarded)
    # The aspect is a framing parameter and every reader expects it last.
    check("detailed={}: the aspect is still the last thing said".format(detailed),
          guarded.rstrip(". ").endswith("4:5"), guarded[-40:])

print()
print("=== the guard does not disturb the gate it sits beside ===")
# Each phrase is a negation, and find_terms()/is_negated() must keep reading
# them as such - otherwise "no distorted hands" would itself trip a hit.
guarded = bp.compose(bank, dict(SPEC), anatomy_guard=True)[0]
present, _m, banned, warns, _n = rl.lint(guarded.lower(), bank)
check("a guarded prompt still scores 8/8", len(present) == 8, "{}/8".format(len(present)))
check("...trips no banned term", not banned, str(banned))
check("...and raises no soft warning either", not warns, str(warns))

print()
print("=== the guard reaches the GUI, not just the CLI ===")
# The whole point of the recent work was closing CLI-only gaps, so a new
# opt-in nobody can reach would be the same mistake in a new place.
compose_src = io.open(ROOT / "ui" / "views" / "compose.py", encoding="utf-8").read()
check("Compose builds a checkbox for it", "self.anatomy_guard" in compose_src)
check("...and passes it into compose()", "anatomy_guard=self.anatomy_guard" in compose_src)
check("...and recomposes when it is toggled",
      "self.anatomy_guard.toggled.connect" in compose_src)
bp_src = io.open(ROOT / "tools" / "build_prompt.py", encoding="utf-8").read()
check("the CLI exposes it too", "--anatomy-guard" in bp_src)
check("...and the docstring says it is off by default",
      "off by\n    default" in bp_src or "opt-in, off by" in bp_src)

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("all checks passed")
