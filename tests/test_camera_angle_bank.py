"""tools/camera_angle_bank.json + build_camera_angle.py - the Camera Angle
section's vertical/side/size axes. Every phrase gets checked against
DETECT["composition"]["keys"] (not "camera" - these phrases live in
composition-adjacent territory, motion_bank.json's own framing terms already
established that precedent). Also locks in the one deliberately honest
tradeoff this section documents: a pure angle phrase with no camera
vocabulary can legitimately score the camera realism layer at 0/8, same as
typing any other custom shot - that's the gate working, not an oversight.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_camera_angle.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_camera_angle as bca  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bca.load_bank()
image_bank = bp.load_bank()


def hits(text):
    lower = text.lower()
    return [k for k in rl.DETECT["composition"]["keys"] if k in lower]


print("=== every axis phrase is detectable (the paired audit, run for real) ===")
undetectable = []
for kind, items in [("vertical", bca.verticals(bank)), ("side", bca.sides(bank)),
                     ("size", bca.sizes(bank))]:
    for key, cfg in items.items():
        if not hits(cfg["phrase"]):
            undetectable.append("{}/{}".format(kind, key))
check("no axis phrase is invisible to realism_lint", not undetectable, ", ".join(undetectable))

print()
print("=== any subset of the three axes composes ===")
phrase, warnings = bca.compose_camera_angle(bank, vertical="low-angle")
check("vertical alone composes", "low-angle" in phrase.lower(), phrase)
check("no warnings", not warnings, str(warnings))

phrase, _ = bca.compose_camera_angle(bank, side="profile", size="close-up")
check("side + size composes", "profile" in phrase.lower() and "close-up" in phrase.lower(), phrase)

phrase, _ = bca.compose_camera_angle(bank, vertical="low-angle", side="profile", size="close-up")
check("all three compose together",
      "low-angle" in phrase.lower() and "profile" in phrase.lower()
      and "close-up" in phrase.lower(), phrase)

print()
print("=== typed custom text always wins, entirely replacing the axes ===")
phrase, warnings = bca.compose_camera_angle(
    bank, vertical="low-angle", side="profile", custom="shot from a drone, looking straight down")
check("custom text wins over any picked axis",
      phrase == "shot from a drone, looking straight down", phrase)
check("no warnings", not warnings, str(warnings))

print()
print("=== each axis also accepts free text, not just bank keys ===")
phrase, warnings = bca.compose_camera_angle(bank, vertical="shot from a drone, looking straight down")
check("an unrecognised vertical is used literally, not rejected",
      phrase == "shot from a drone, looking straight down", phrase)
check("no warnings for a wholly custom axis", not warnings, str(warnings))

phrase, warnings = bca.compose_camera_angle(
    bank, side="peering around a doorframe", size="filling the whole frame")
check("custom side + custom size both pass through literally",
      "doorframe" in phrase and "filling the whole frame" in phrase, phrase)

phrase, _ = bca.compose_camera_angle(bank, vertical="low-angle", side="peering around a doorframe")
check("a real bank key still resolves to its phrase alongside custom text",
      "low-angle" in phrase.lower() and "doorframe" in phrase, phrase)

print()
print("=== bad input is refused, not silently ignored ===")
try:
    bca.compose_camera_angle(bank)
    check("giving nothing at all raises", False)
except bca.CameraAngleError:
    check("giving nothing at all raises", True)

print()
print("=== the honest tradeoff: a pure angle phrase can score camera 0/8 ===")
phrase, _ = bca.compose_camera_angle(bank, vertical="low-angle", side="profile", size="close-up")
spec = {"subject": "a man in his forties", "seed": 1, "shot_custom": phrase}
prompt, _ = bp.compose(image_bank, spec)
present, missing, banned, _, _ = rl.lint(prompt.lower(), image_bank)
missing_layers = [name for name, _cfg, _hit in missing]
check("camera legitimately scores 0/8 with no camera vocabulary in the phrase",
      "camera" in missing_layers, str(missing_layers))
check("no banned terms even so", not banned, str(banned))
check("composition still scores (the phrase itself is composition-detectable)",
      "composition" not in missing_layers, str(missing_layers))

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every vertical", all(key in p.stdout for key in bca.verticals(bank)))
check("--list names every side", all(key in p.stdout for key in bca.sides(bank)))
check("--list names every size", all(key in p.stdout for key in bca.sizes(bank)))

p = run(["--vertical", "low-angle", "--side", "profile", "--size", "close-up"])
check("all three flags exit 0", p.returncode == 0, p.stderr[:160])
check("all three phrases print", "low-angle" in p.stdout and "profile" in p.stdout
      and "close-up" in p.stdout, p.stdout[:200])

p = run(["--vertical", "shot from a drone, looking straight down"])
check("free-text --vertical exits 0 and is used literally", p.returncode == 0
      and "shot from a drone, looking straight down" in p.stdout, p.stdout[:200])

p = run([])
check("no arguments at all exits non-zero", p.returncode != 0)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:160])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL CAMERA ANGLE BANK CHECKS PASSED")

sys.exit(1 if fails else 0)
