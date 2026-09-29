"""midjourney_export.py - a text-only reformat, never a new provider.

Midjourney has no official public API, so this is deliberately just a string
transform over an already-built, already-realism_lint-scored prompt: no
network, no key, nothing that could be mistaken for automating the Discord
bot every third-party "Midjourney API" actually puppets.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp
import midjourney_export as mx
import realism_lint as rl

bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


SPEC = {"subject": "a woman in her thirties", "aspect": "9:16", "seed": 0}
prompt, _ = bp.compose(bank, SPEC)
present, _, banned, _, _ = rl.lint(prompt.lower(), bank)

print("=== the source prompt is real and already passes the gate ===")
check("8/8 before export", len(present) == 8 and not banned, str(len(present)))

print()
print("=== negatives_to_no(): sentence form -> Midjourney's own syntax ===")
no_terms = mx.negatives_to_no(bank)
check("same count as the bank's negatives list", len(no_terms) == len(bank["negatives"]))
check("no leading 'no ' survives", all(not t.lower().startswith("no ") for t in no_terms),
      str(no_terms))
check("nothing invented - every term is a substring of its own bank phrase",
      all(no_terms[i] in bank["negatives"][i] for i in range(len(no_terms))), str(no_terms))

print()
print("=== to_midjourney(): the parameters actually present ===")
out = mx.to_midjourney(bank, SPEC, prompt)
check("the original prompt text survives, verbatim", prompt.strip() in out, out[:80])
check("--ar matches spec[aspect]", "--ar 9:16" in out, out[-160:])
check("--style raw by default (photoreal-leaning)", "--style raw" in out, out[-160:])
check("--stylize 50 by default", "--stylize 50" in out, out[-160:])
check("--v 6.1 by default", "--v 6.1" in out, out[-160:])
check("--no carries every bank negative, comma-joined",
      all(term in out for term in no_terms), out[-200:])
check("no leftover 'no ' prefix inside the --no clause itself",
      "--no no " not in out.lower(), out[-200:])

print()
print("=== every parameter is overridable ===")
out2 = mx.to_midjourney(bank, SPEC, prompt, version="6", style=None, stylize=250)
check("version override", "--v 6" in out2 and "--v 6.1" not in out2, out2[-160:])
check("style=None omits --style entirely", "--style" not in out2, out2[-160:])
check("stylize override", "--stylize 250" in out2, out2[-160:])

print()
print("=== no aspect set -> no --ar, not a blank/broken one ===")
no_aspect_spec = {"subject": "a woman"}
out3 = mx.to_midjourney(bank, no_aspect_spec, "a woman, photorealistic")
check("no --ar token at all", "--ar" not in out3, out3)

print()
print("=== a reference image adds a plain-text note, never an automated --cref ===")
with_ref = dict(SPEC, reference="temp/resources/characters/some-face.png")
out4 = mx.to_midjourney(bank, with_ref, prompt)
check("names the file", "some-face.png" in out4, out4[-260:])
check("says to attach it yourself", "attach this yourself" in out4, out4[-260:])
check("never emits an automated --cref/--sref", "--cref" not in out4 and "--sref" not in out4,
      out4[-260:])

out5 = mx.to_midjourney(bank, SPEC, prompt)  # SPEC has no "reference" key
check("no reference -> no note at all", "reference image" not in out5)

print()
print("=== CLI: no key, no network, --help documents the no-API reason ===")
import subprocess

TOOL = ROOT / "tools" / "midjourney_export.py"
p = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True,
                   cwd=str(ROOT))
check("--help exits 0", p.returncode == 0)
check("explains there is no official API", "no official public api" in p.stdout.lower(),
      p.stdout[:300])

SPEC_PATH = ROOT / "temp" / "resources" / "characters" / "_test-mj-export.json"
import json
SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
SPEC_PATH.write_text(json.dumps(SPEC), encoding="utf-8")
p = subprocess.run([sys.executable, str(TOOL), "--spec", str(SPEC_PATH)],
                   capture_output=True, text=True, cwd=str(ROOT))
check("CLI exits 0", p.returncode == 0, p.stderr[:200])
check("CLI output carries --ar", "--ar 9:16" in p.stdout, p.stdout[-160:])
SPEC_PATH.unlink()

print()
print("=== --sref: a STYLE reference, which is not the same as spec['reference'] ===")
# A style reference is a token (a job id, an --sref number, an image URL), so it
# CAN ride in the text. spec["reference"] is an image a human must attach in
# Discord, which is why that one stays a note and this one is a parameter.
out = mx.to_midjourney(bank, SPEC, prompt, sref="553469723")
check("--sref is emitted when given", "--sref 553469723" in out, out[-120:])
check("--sw is NOT emitted without a value", "--sw" not in out, out[-120:])

out = mx.to_midjourney(bank, SPEC, prompt, sref="553469723", sw=400)
check("--sw rides alongside --sref", "--sref 553469723" in out and "--sw 400" in out,
      out[-120:])

out = mx.to_midjourney(bank, SPEC, prompt, sw=400)
check("--sw alone is dropped - it means nothing without --sref",
      "--sw" not in out, out[-120:])

out = mx.to_midjourney(bank, SPEC, prompt)
check("no --sref by default, so every existing call is unchanged",
      "--sref" not in out and "--sw" not in out, out[-120:])

# This tool takes --spec or --prompt-file; it has no --subject of its own.
SREF_SPEC = ROOT / "temp" / "resources" / "characters" / "_test-mj-sref.json"
SREF_SPEC.parent.mkdir(parents=True, exist_ok=True)
SREF_SPEC.write_text(json.dumps(SPEC), encoding="utf-8")
p2 = subprocess.run([sys.executable, str(TOOL), "--spec", str(SREF_SPEC),
                     "--sref", "553469723", "--sw", "250", "--version", "7"],
                    capture_output=True, text=True, cwd=str(ROOT))
check("the CLI carries --sref, --sw and an explicit --v", p2.returncode == 0
      and "--sref 553469723" in p2.stdout and "--sw 250" in p2.stdout
      and "--v 7" in p2.stdout, (p2.stdout[-160:] or p2.stderr[:160]))
SREF_SPEC.unlink()


print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL MIDJOURNEY EXPORT CHECKS PASSED")

sys.exit(1 if fails else 0)
