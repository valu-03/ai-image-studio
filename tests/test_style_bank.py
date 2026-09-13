"""tools/style_bank.json + build_style.py - the Style section's 27 named
looks: 24 from the course's Style Reference Library (14 photoreal, 10
stylised), plus 2 app-original photoreal additions (`iphone-ugc-realism`,
`on-camera-flash-candid`) sourced from community UGC/avatar prompt-bank
material, not the course PDF, plus 1 more photoreal addition
(`universal-realism-lock`) sourced from a DIFFERENT official course lesson
("Removing the 'AI' Look") - each addition says so via its own `source`
field.

Two groups with two different contracts:
  photoreal - must NOT trip a banned term, and applied through
              spec["overrides"]["style"] a full prompt still scores 8/8.
  stylised  - deliberately not photographic. compose_style() returns a
              warning that it fights the realism vocabulary; the phrase still
              reaches the prompt (the Style section shows the warning and
              lets the user decide).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_style.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import build_style as bstyle  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bstyle.load_bank()
image_bank = bp.load_bank()


def score(phrase):
    spec = {"subject": "a woman in her thirties", "seed": 1,
            "overrides": {"style": [phrase]}}
    prompt, _ = bp.compose(image_bank, spec)
    present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
    return len(present), banned, missing, prompt


print("=== the bank is well-formed ===")
check("27 styles total", len(bstyle.all_styles(bank)) == 27, str(len(bstyle.all_styles(bank))))
check("both groups are non-empty",
      bool(bstyle.photoreal(bank)) and bool(bstyle.stylised(bank)))
for key, cfg in bstyle.all_styles(bank).items():
    check("'{}' has every field".format(key),
          all(cfg.get(f) for f in ("label", "keywords", "look", "when", "example")),
          str(sorted(cfg)))

print()
print("=== photoreal styles: not banned, and 8/8 through a full prompt ===")
for key, cfg in bstyle.photoreal(bank).items():
    phrase, warnings = bstyle.compose_style(bank, style=key)
    check("photoreal '{}' composes with no warning".format(key), not warnings, str(warnings))
    got, banned, missing, _ = score(phrase)
    check("photoreal '{}' scores 8/8".format(key),
          got == 8 and not banned, "score {} missing {} banned {}".format(got, missing, banned))

print()
print("=== stylised styles: warned, and the phrase reaches the prompt ===")
for key, cfg in bstyle.stylised(bank).items():
    phrase, warnings = bstyle.compose_style(bank, style=key)
    check("stylised '{}' returns a warning".format(key),
          warnings and "fights the realism" in warnings[0], str(warnings))
    _got, _banned, _missing, prompt = score(phrase)
    check("stylised '{}' phrase is actually in the prompt".format(key),
          cfg["keywords"].split(",")[0].lower() in prompt.lower(), prompt[-160:])

print()
print("=== precedence: custom text beats a picked style, and is never warned ===")
phrase, warnings = bstyle.compose_style(bank, style="anime-manga", custom="super-8 home movie look")
check("custom wins", phrase == "super-8 home movie look", phrase)
check("custom is never warned (used exactly as typed)", not warnings, str(warnings))

print()
print("=== bad input is refused ===")
for bad in (dict(style="not-a-real-style"), dict()):
    try:
        bstyle.compose_style(bank, **bad)
        check("compose_style({}) raises".format(bad), False)
    except bstyle.StyleError:
        check("compose_style({}) raises".format(bad), True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every style", all(k in p.stdout for k in bstyle.all_styles(bank)))

p = run(["--style", "35mm-film"])
check("--style exits 0", p.returncode == 0, p.stderr[:160])
check("--style prints the keywords", "35mm film" in p.stdout, p.stdout[:120])
check("a photoreal style prints no warning", not p.stderr.strip(), p.stderr[:120])

p = run(["--style", "oil-painting"])
check("a stylised style still exits 0", p.returncode == 0, p.stderr[:160])
check("but warns on stderr", "fights the realism" in p.stderr, p.stderr[:160])

p = run(["--style", "nope"])
check("an unknown --style exits non-zero", p.returncode != 0)

p = run(["--custom", "a sun-bleached grade"])
check("--custom exits 0 and prints it",
      p.returncode == 0 and "sun-bleached" in p.stdout, p.stdout[:120])

p = run([])
check("no arguments exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL STYLE BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
