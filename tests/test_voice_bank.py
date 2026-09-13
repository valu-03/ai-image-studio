"""tools/voice_bank.json + build_voice.py - the sixteen named voice-blueprint
templates from the course's "Consistent Character Voices" lesson. Each
template has one `{accent}` slot filled by compose_voice(); this is not one
of realism_lint.py's 8 gated photorealism layers, so there is no DETECT
keyword requirement or 8/8 scoring check here, unlike tools/style_bank.json.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_voice.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_voice as bv  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bv.load_bank()

print("=== the bank is well-formed ===")
check("16 voice styles total", len(bv.styles(bank)) == 16, str(len(bv.styles(bank))))
for key, cfg in bv.styles(bank).items():
    check("'{}' has every field".format(key),
          all(cfg.get(f) for f in ("label", "phrase_template", "when")), str(sorted(cfg)))
    check("'{}' phrase_template has an {{accent}} slot".format(key),
          "{accent}" in cfg["phrase_template"], cfg["phrase_template"])

print()
print("=== every style composes, with the accent filled in ===")
for key in bv.styles(bank):
    phrase, warnings = bv.compose_voice(bank, style=key, accent="Australian accent")
    check("'{}' fills the accent".format(key), "Australian accent" in phrase, phrase)
    check("'{}' returns no warnings".format(key), not warnings, str(warnings))

print()
print("=== a blank accent falls back rather than reading oddly ===")
phrase, _ = bv.compose_voice(bank, style="confident", accent=None)
check("falls back to the neutral accent text", bv.FALLBACK_ACCENT in phrase, phrase)
phrase, _ = bv.compose_voice(bank, style="confident", accent="   ")
check("whitespace-only accent also falls back", bv.FALLBACK_ACCENT in phrase, phrase)

print()
print("=== precedence: custom text beats a picked style, and is never warned ===")
phrase, warnings = bv.compose_voice(
    bank, style="confident", accent="Irish accent",
    custom="a gravelly, world-weary baritone, unhurried")
check("custom wins", phrase == "a gravelly, world-weary baritone, unhurried", phrase)
check("custom is never warned (used exactly as typed)", not warnings, str(warnings))

print()
print("=== bad input is refused ===")
for bad in (dict(style="not-a-real-style"), dict()):
    try:
        bv.compose_voice(bank, **bad)
        check("compose_voice({}) raises".format(bad), False)
    except bv.VoiceError:
        check("compose_voice({}) raises".format(bad), True)

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every style", all(k in p.stdout for k in bv.styles(bank)))

p = run(["--style", "confident", "--accent", "Australian accent"])
check("--style exits 0", p.returncode == 0, p.stderr[:160])
check("--style prints the filled phrase", "Australian accent" in p.stdout, p.stdout[:160])

p = run(["--style", "confident"])
check("--style with no --accent still exits 0 and falls back",
      p.returncode == 0 and bv.FALLBACK_ACCENT in p.stdout, p.stdout[:160])

p = run(["--style", "nope"])
check("an unknown --style exits non-zero", p.returncode != 0)

p = run(["--custom", "a warm, unhurried radio-announcer voice"])
check("--custom exits 0 and prints it",
      p.returncode == 0 and "radio-announcer" in p.stdout, p.stdout[:160])

p = run([])
check("no arguments exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL VOICE BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
