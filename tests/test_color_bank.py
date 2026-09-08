"""tools/color_bank.json + build_color.py - the Color Grading section's
moods, film looks and techniques, verified the same way Lighting/Composition
already are - AND checked against banned/warn, not just detectability, since
this is the first bank whose source material leans stylised (neon cyberpunk,
hot pink Barbie) rather than photographically restrained.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_color.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_color as bc  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bc.load_bank()
image_bank = bp.load_bank()


def hits(text):
    lower = text.lower()
    return [k for k in rl.DETECT["colour"]["keys"] if k in lower]


def banned_hits(text):
    lower = text.lower()
    return [b for b in image_bank["banned"] if b in lower]


print("=== every phrase is detectable AND not banned (the paired audit, run for real) ===")
undetectable, banned_found = [], []
for kind, items in [("mood", bc.moods(bank)), ("film_look", bc.film_looks(bank)),
                     ("technique", bc.techniques(bank))]:
    for key, cfg in items.items():
        if not hits(cfg["phrase"]):
            undetectable.append("{}/{}".format(kind, key))
        if banned_hits(cfg["phrase"]):
            banned_found.append("{}/{}: {}".format(kind, key, banned_hits(cfg["phrase"])))
check("no phrase is invisible to realism_lint", not undetectable, ", ".join(undetectable))
check("no phrase trips a banned term", not banned_found, ", ".join(banned_found))

print()
print("=== every mood and film look, alone, composes and scores 8/8 in a full prompt ===")
for kind, items in [("mood", bc.moods(bank)), ("film_look", bc.film_looks(bank))]:
    for key in items:
        kwargs = {kind: key}
        phrase, warnings = bc.compose_color(bank, **kwargs)
        check("{} '{}' composes with no warnings".format(kind, key), not warnings, str(warnings))
        spec = {"subject": "a woman in her thirties", "seed": 1,
                "overrides": {"colour": [phrase]}}
        prompt, _ = bp.compose(image_bank, spec)
        present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
        check("{} '{}' scores 8/8".format(kind, key), len(present) == 8 and not banned,
              "missing: {}".format(missing))

print()
print("=== custom text overrides a picked mood/film look (precedence check) ===")
phrase, warnings = bc.compose_color(bank, mood="epic-heroic", custom="sun-bleached pastel grade")
check("custom text wins over the mood", phrase == "sun-bleached pastel grade", phrase)
check("no warnings", not warnings, str(warnings))

print()
print("=== mood + film_look together is refused (two complete recipes, not stackable) ===")
try:
    bc.compose_color(bank, mood="epic-heroic", film_look="dune")
    check("mood + film_look together raises", False)
except bc.ColorError:
    check("mood + film_look together raises", True)

print()
print("=== techniques stack additively ===")
phrase, _ = bc.compose_color(bank, mood="dark-moody", techniques_=["accent-echo", "warm-cool-contrast"])
check("both techniques appear in the composed phrase",
      "accent colour" in phrase.lower() and "complementary colour contrast" in phrase.lower(),
      phrase)

print()
print("=== bad input is refused, not silently ignored ===")
try:
    bc.compose_color(bank, mood="not-a-real-mood")
    check("an unknown mood raises", False)
except bc.ColorError:
    check("an unknown mood raises", True)

try:
    bc.compose_color(bank, film_look="not-a-real-film")
    check("an unknown film look raises", False)
except bc.ColorError:
    check("an unknown film look raises", True)

try:
    bc.compose_color(bank)
    check("giving nothing at all raises", False)
except bc.ColorError:
    check("giving nothing at all raises", True)

try:
    bc.compose_color(bank, mood="dark-moody", techniques_=["not-a-real-technique"])
    check("an unknown technique raises", False)
except bc.ColorError:
    check("an unknown technique raises", True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every mood", all(key in p.stdout for key in bc.moods(bank)))
check("--list names every film look", all(key in p.stdout for key in bc.film_looks(bank)))

p = run(["--mood", "epic-heroic"])
check("--mood exits 0", p.returncode == 0, p.stderr[:160])
check("--mood prints the phrase", "epic tone" in p.stdout, p.stdout[:160])

p = run(["--film-look", "dune"])
check("--film-look exits 0", p.returncode == 0, p.stderr[:160])
check("--film-look prints the phrase", "Dune-inspired" in p.stdout, p.stdout[:160])

p = run(["--mood", "epic-heroic", "--film-look", "dune"])
check("--mood + --film-look exits non-zero", p.returncode != 0)

p = run(["--mood", "not-a-real-mood"])
check("an unknown --mood exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:160])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL COLOR BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
