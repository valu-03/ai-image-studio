"""upscale_image.py - the course's "upscale before you animate" rule, verified.

Not a new provider or a new request shape: this tool is generate_image.generate()
with one fixed prompt and the image being upscaled as its sole reference, so the
thing worth defending is that it stays that thin - the constant is the course's
own template verbatim, a provider with no reference input is refused exactly the
way every other reference-carrying call in this project already is, and a real
request actually carries the fixed prompt and the uploaded reference through to
Kie, using the same mock the rest of the image-generation suite trusts.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
TOOL = ROOT / "tools" / "upscale_image.py"
IMAGES = ROOT / "temp" / "outputs" / "images"

import mock_api

PORT = 8795
mock_api.serve(PORT)
BASE = "http://127.0.0.1:{}".format(PORT)

EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-upscale-empty.env"
EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")

REFERENCE = Path(tempfile.gettempdir()) / "aivs-upscale-reference.png"
REFERENCE.write_bytes(mock_api.PNG)

KIE = {"KIE_API_KEY": "kie-key"}

fails = []
written = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def run(args, env_extra=None):
    env = dict(os.environ)
    env["AIVS_ENV_FILE"] = str(EMPTY_ENV)
    env.pop("KIE_API_KEY", None)
    env.update(env_extra or {})
    mock_api.reset()
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + args,
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    return proc


def saved(name):
    path = IMAGES / name
    written.append(path)
    return path


print("=== the constant is the course's advanced template, not a paraphrase ===")
sys.path.insert(0, str(ROOT / "tools"))
import upscale_image as ui  # noqa: E402

for phrase in ("4K", "Preserve the original composition, lighting, and character identity",
               "No AI plastic skin", "no over-smoothing", "no repainting", "no style shift",
               "Maintain the exact original pose and proportions"):
    check("prompt includes {!r}".format(phrase[:40]), phrase in ui.UPSCALE_PROMPT)

print()
print("=== a provider with no reference input is refused, not silently dropped ===")
p = run(["--image", str(REFERENCE), "--provider", "higgsfield", "--dry-run"])
check("exits 3", p.returncode == 3, str(p.returncode))
check("names the provider", "Higgsfield Soul" in p.stderr, p.stderr[:160])
check("says why", "no reference-image input" in p.stderr, p.stderr[:160])

print()
print("=== a missing image is refused before any request is built ===")
p = run(["--image", "temp/outputs/images/does-not-exist.png", "--dry-run"])
check("exits non-zero", p.returncode != 0, str(p.returncode))
check("names the missing file", "not found" in p.stderr.lower() or "not found" in p.stdout.lower(),
      (p.stdout + p.stderr)[:160])

print()
print("=== dry run needs no key, and leaks none ===")
p = run(["--image", str(REFERENCE), "--dry-run"])
check("exits 0", p.returncode == 0, p.stderr[:160])
check("shows the prompt", "ultra-realistic 4K" in p.stdout, p.stdout[:160])
check("shows kie as the provider", "kie" in p.stdout, p.stdout[:160])

print()
print("=== --help documents the rule this tool exists for ===")
p = run(["--help"])
check("exits 0", p.returncode == 0)
check("names the pipeline rule", "upscale before you animate" in p.stdout.lower(),
      p.stdout[:200])

print()
print("=== kie: the fixed prompt and the reference actually reach the request ===")
p = run(["--image", str(REFERENCE), "--base-url", BASE, "--out", "test-upscale.png"], KIE)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("prints the marker", p.stdout.startswith("[image] "), p.stdout[:80])
img = saved("test-upscale.png")
check("file written", img.exists())
check("real PNG bytes", img.exists() and img.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
sent = mock_api.STATE["last"]
check("hit createTask", "createTask" in (sent or {}).get("path", ""), str(sent and sent["path"]))
body = (sent or {}).get("body", {})
check("the fixed template, not something else, went out",
      "4K" in json.dumps(body) and "AI plastic skin" in json.dumps(body))
check("the reference was uploaded then referenced",
      "image_input" in json.dumps(body.get("input", {})),
      json.dumps(body.get("input", {}))[:160])
check("no key in output", "kie-key" not in p.stdout)

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL UPSCALE CHECKS PASSED")

for path in written:
    try:
        path.unlink()
    except OSError:
        pass
try:
    REFERENCE.unlink()
except OSError:
    pass

sys.exit(1 if fails else 0)
