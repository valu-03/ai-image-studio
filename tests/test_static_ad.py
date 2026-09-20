"""tools/static_ad_bank.json + build_static_ad.py + static_ad_lint.py - static
(non-video) product ad composites: a presenter-less studio shot and a
presenter-holds-the-product lifestyle shot. No beats, no timing - unlike
tools/ugc_bank.json's five-beat video ad.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build_static_ad.py"
LINT = ROOT / "tools" / "static_ad_lint.py"
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import build_static_ad as bsa  # noqa: E402
import build_style as bstyle  # noqa: E402
import static_ad_lint as sal  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bsa.load_bank()
image_bank = bp.load_bank()
style_bank = bstyle.load_bank()

print("=== the bank is well-formed ===")
check("two modes: studio, lifestyle", set(bsa.modes(bank)) == {"studio", "lifestyle"},
      str(sorted(bsa.modes(bank))))
check("studio carries a real style key",
      bsa.modes(bank)["studio"]["style"] in bstyle.all_styles(style_bank))
check("studio has no presenter", bsa.modes(bank)["studio"]["presenter"] is False)
check("lifestyle has a presenter", bsa.modes(bank)["lifestyle"]["presenter"] is True)
check("label_accuracy_phrase is present", bool(bank.get("label_accuracy_phrase")))

PRODUCT = "LumaWash shampoo, 250ml amber bottle, black cap"
PRODUCT_REF = "temp/resources/images/lumawash-ref.png"
BASE_SPEC = {"seed": 0}

print()
print("=== compose_static_ad: both modes ===")
shots = bsa.compose_static_ad(bank, style_bank, image_bank, BASE_SPEC, PRODUCT, PRODUCT_REF)
check("two shots produced", len(shots) == 2, str(len(shots)))
check("modes are studio and lifestyle", {s["mode"] for s in shots} == {"studio", "lifestyle"})
check("every shot carries the product reference",
      all(PRODUCT_REF in s["references"] for s in shots))
check("every shot states the label-accuracy instruction",
      all(bank["label_accuracy_phrase"] in s["prompt"] for s in shots))

studio = next(s for s in shots if s["mode"] == "studio")
lifestyle = next(s for s in shots if s["mode"] == "lifestyle")
check("studio has no presenter reference (one reference only)", len(studio["references"]) == 1)
check("studio subject IS the product", studio["spec"]["subject"] == PRODUCT)
check("studio carries no identity/scene lock",
      not studio["spec"].get("lock_identity") and not studio["spec"].get("lock_scene"))
check("lifestyle subject is a person, not the product", lifestyle["spec"]["subject"] != PRODUCT)
check("lifestyle mentions the product in its action",
      PRODUCT in lifestyle["spec"].get("action", ""))

print()
print("=== compose_static_ad: presenter reference orders correctly ===")
PRESENTER_REF = "temp/resources/characters/ada-ref.png"
with_presenter = bsa.compose_static_ad(
    bank, style_bank, image_bank, BASE_SPEC, PRODUCT, PRODUCT_REF,
    mode="lifestyle", presenter_reference=PRESENTER_REF)
check("one shot produced", len(with_presenter) == 1)
check("presenter reference comes first, product last",
      with_presenter[0]["references"] == [PRESENTER_REF, PRODUCT_REF],
      str(with_presenter[0]["references"]))

print()
print("=== static_ad_lint: a good batch passes every check ===")
results = sal.lint(bank, shots)
got, total = sal.score(results)
check("full score on a well-formed batch", got == total, "{}/{}".format(got, total))

print()
print("=== static_ad_lint: catches real defects ===")
missing_mode = [studio]
results = sal.lint(bank, missing_mode, requested="both")
by_key = {key: passed for key, _label, passed, _detail in results}
check("a missing requested mode is caught", not by_key["modes_present"])

no_ref = dict(studio)
no_ref["references"] = []
results = sal.lint(bank, [no_ref])
by_key = {key: passed for key, _label, passed, _detail in results}
check("a missing reference is caught", not by_key["references"])

stray_lock = dict(studio)
stray_lock["spec"] = dict(stray_lock["spec"])
stray_lock["spec"]["lock_identity"] = True
results = sal.lint(bank, [stray_lock])
by_key = {key: passed for key, _label, passed, _detail in results}
check("a stray lock on a presenter-less mode is caught", not by_key["no_stray_lock"])

print()
print("=== CLI ===")


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names both modes", "studio" in p.stdout and "lifestyle" in p.stdout)

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

p = run(["--product", PRODUCT, "--reference", PRODUCT_REF, "--mode", "nope", "--no-write"])
check("an unknown --mode exits non-zero", p.returncode != 0)

p = run(["--reference", PRODUCT_REF, "--no-write"])
check("no --product exits non-zero", p.returncode != 0)

p = run(["--product", PRODUCT, "--no-write"])
check("no --reference exits non-zero", p.returncode != 0)

p = run(["--product", PRODUCT, "--reference", PRODUCT_REF, "--no-write"])
check("a well-formed run exits 0", p.returncode == 0, p.stderr[:160])
check("prints both composites", p.stdout.count("===") == 2, str(p.stdout.count("===")))

lint_p = subprocess.run([sys.executable, str(LINT), "--help"], capture_output=True, text=True, cwd=str(ROOT))
check("static_ad_lint --help exits 0", lint_p.returncode == 0, lint_p.stdout[:120])

lint_p = subprocess.run(
    [sys.executable, str(LINT), "--static-ad", "does-not-exist.json"],
    capture_output=True, text=True, cwd=str(ROOT))
check("static_ad_lint on a missing file exits non-zero", lint_p.returncode != 0)

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL STATIC AD CHECKS PASSED")

sys.exit(1 if fails else 0)
