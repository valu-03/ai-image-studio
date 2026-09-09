"""tools/persona_bank.json + build_persona.py - the Influencer Studio
section's data and composer. A persona is descriptive spec content, like
wardrobe/setting/mood - it is NOT one of realism_lint.py's 8 gated
photorealism layers (the same reasoning tests/test_posing_bank.py already
documents for Posing), so this suite does not run a detectability audit
against DETECT - instead it confirms a composed persona description never
interferes with the 8 layers that ARE gated, and that every unrecognised
key is dropped rather than smuggled through as free text.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_persona.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_persona as bper  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bper.load_bank()
image_bank = bp.load_bank()

print("=== every gender/age/hair/eye/style key composes without error ===")
for key in bper.genders(bank):
    result = bper.compose_persona(bank, gender=key)
    check("gender '{}' composes to something non-empty".format(key), bool(result.strip()), result)
for key in bper.age_ranges(bank):
    result = bper.compose_persona(bank, gender="woman", age_range=key)
    check("age range '{}' phrase appears".format(key),
          bper.age_ranges(bank)[key]["phrase"] in result, result)
for key in bper.hair_colors(bank):
    result = bper.compose_persona(bank, hair_color=key)
    check("hair color '{}' phrase appears".format(key),
          bper.hair_colors(bank)[key]["phrase"] in result, result)
for key in bper.eye_colors(bank):
    result = bper.compose_persona(bank, eye_color=key)
    check("eye color '{}' phrase appears".format(key),
          bper.eye_colors(bank)[key]["phrase"] in result, result)
for key in bper.style_tags(bank):
    result = bper.compose_persona(bank, style_tags_=[key])
    check("style tag '{}' phrase appears".format(key),
          bper.style_tags(bank)[key]["phrase"] in result, result)

print()
print("=== nothing given at all still composes something usable ===")
result = bper.compose_persona(bank)
check("an empty persona falls back to 'a person', the same default "
      "SpecEditor.PLACEHOLDER_SUBJECT already uses",
      result.strip() == "a person.", result)

print()
print("=== unrecognised keys are dropped, never smuggled through as free text ===")
result = bper.compose_persona(
    bank, gender="not-a-real-gender", age_range="not-a-real-range",
    hair_color="not-a-real-color", eye_color="not-a-real-color",
    style_tags_=["not-a-real-style", "luxury"])
check("an unknown gender falls back to the neutral default", result.startswith("a person"), result)
check("an unknown age range contributes nothing", "not-a-real-range" not in result, result)
check("an unknown hair/eye color contributes nothing",
      "not-a-real-color" not in result, result)
check("an unknown style tag is filtered out, the real one still applies",
      "not-a-real-style" not in result and "elevated" in result, result)

print()
print("=== a fully composed persona description never interferes with "
      "the 8 gated layers, in the Subject field ===")
for gender, age, style in [("woman", "25-30", ["luxury"]), ("man", "38-45", ["fitness", "edgy"])]:
    phrase = bper.compose_persona(
        bank, name="Zoe", gender=gender, age_range=age, style_tags_=style,
        hair_color="blonde", eye_color="blue", details="a small nose stud")
    spec = {"subject": phrase, "seed": 1}
    prompt, _ = bp.compose(image_bank, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    check("persona ({}, {}, {}) in the Subject field still scores 8/8".format(gender, age, style),
          len(present) == 8 and not banned, "missing: {}".format(missing))
    check("the persona phrase itself appears in the composed prompt",
          phrase.lower() in prompt.lower())

print()
print("=== the a/an article agrees with the first style tag's phrase ===")
result = bper.compose_persona(bank, style_tags_=["luxury"])
check("'elevated...' takes 'an'", "styled with an elevated" in result, result)
result = bper.compose_persona(bank, style_tags_=["casual"])
check("'relaxed...' takes 'a'", "styled with a relaxed" in result, result)

print()
print("=== details are appended as typed, name leads the sentence when given ===")
result = bper.compose_persona(bank, name="Mia", details="always carries a film camera")
check("name leads", result.startswith("Mia,"), result)
check("details trail, appended as typed", result.rstrip().endswith("film camera"), result)
result = bper.compose_persona(bank)
check("no name means no leading name clause", not result.startswith(","), result)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every gender", all(key in p.stdout for key in bper.genders(bank)))
check("--list names every age range", all(key in p.stdout for key in bper.age_ranges(bank)))
check("--list names every style tag", all(key in p.stdout for key in bper.style_tags(bank)))
check("--list names every hair color", all(key in p.stdout for key in bper.hair_colors(bank)))
check("--list names every eye color", all(key in p.stdout for key in bper.eye_colors(bank)))

p = run(["--name", "Zoe", "--gender", "woman", "--age-range", "25-30",
         "--hair-color", "blonde", "--eye-color", "blue", "--style", "luxury"])
check("a full set of flags exits 0", p.returncode == 0, p.stderr[:160])
check("the composed sentence names Zoe, the age range and the style",
      "Zoe" in p.stdout and "late twenties" in p.stdout and "elevated" in p.stdout,
      p.stdout[:200])

p = run([])
check("no arguments at all still exits 0 (every field is optional)", p.returncode == 0,
      p.stderr[:160])
check("falls back to 'a person'", "a person" in p.stdout, p.stdout[:160])

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:160])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL PERSONA BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
