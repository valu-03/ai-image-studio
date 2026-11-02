"""Run every suite. One command, from anywhere:

    python tests/run_all.py            all suites
    python tests/run_all.py look       only suites whose name contains "look"

Each suite is a plain script that prints "  OK" / "  FAIL" lines and exits
non-zero on failure - no real network or spend (every provider is mocked).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ORDER = [
    "test_realism_lint.py",
    "test_pet_realism.py",
    "test_scene_variety.py",
    "test_evidence_bank.py",
    "test_face_detail.py",
    "test_scene_light.py",
    "test_physical.py",
    "test_snapshot.py",
    "test_brief.py",
    "test_retry.py",
    "test_upscale.py",
    "test_refine.py",
    "test_history.py",
    "test_pricing.py",
    "test_vision_lint.py",
    "test_giveaways.py",
    "test_look_cards.py",
    "test_lighting_bank.py",
    "test_composition_bank.py",
    "test_color_bank.py",
    "test_style_bank.py",
    "test_skin_negatives.py",
    "test_anatomy_guard.py",
    "test_posing_bank.py",
    "test_camera_angle_bank.py",
    "test_local_api.py",
    "test_studio_look.py",
    "test_studio_photos.py",
    "test_studio_desktop.py",
    "test_safety_lint.py",
]

HISTORY_PATH = ROOT / "temp" / "outputs" / "history.jsonl"
PRICING_PATH = ROOT / "tools" / "pricing.json"


def _read_history():
    if not HISTORY_PATH.exists():
        return []
    return [line for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv):
    history_before = _read_history()
    pricing_before = PRICING_PATH.read_bytes() if PRICING_PATH.exists() else None
    needle = argv[0].lower() if argv else ""
    suites = [name for name in ORDER
              if (HERE / name).exists() and needle in name.lower()]
    if not suites:
        print("No suites match {!r}. Available: {}".format(
            needle, ", ".join(ORDER)))
        return 2

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    empty_env = Path(tempfile.gettempdir()) / "aivs-run-all-empty.env"
    empty_env.write_text("# intentionally empty\n", encoding="utf-8")
    env.setdefault("AIVS_ENV_FILE", str(empty_env))
    env.setdefault("AIVS_ASSUME_YES", "1")
    env.setdefault("AIVS_HISTORY_FILE", str(empty_env.parent / "aivs-tests-history.jsonl"))
    test_pricing = empty_env.parent / "aivs-tests-pricing.json"
    if PRICING_PATH.exists():
        test_pricing.write_bytes(PRICING_PATH.read_bytes())
    env.setdefault("AIVS_PRICING_FILE", str(test_pricing))

    total_ok = total_fail = 0
    failed_suites = []

    for name in suites:
        proc = subprocess.run(
            [sys.executable, str(HERE / name)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(ROOT), env=env,
        )
        output = proc.stdout + proc.stderr
        ok = sum(1 for line in output.splitlines() if line.startswith("  OK"))
        bad = [line for line in output.splitlines() if line.startswith("  FAIL")]
        total_ok += ok
        total_fail += len(bad)

        print("{:<24} {:>4} passed, {} failed{}".format(
            name, ok, len(bad), "" if proc.returncode == 0 else "  (exit {})".format(proc.returncode)))
        for line in bad:
            print("    " + line.strip())
        if proc.returncode != 0:
            failed_suites.append(name)
            if not bad:
                print("    " + output.strip().splitlines()[-1][:160] if output.strip() else "")

    print("")
    print("TOTAL: {} passed, {} failed across {} suite(s)".format(
        total_ok, total_fail, len(suites)))
    if failed_suites:
        print("SUITES THAT EXITED NON-ZERO: " + ", ".join(failed_suites))

    after = _read_history()
    synthetic = len(after) - len(history_before)
    if history_before:
        HISTORY_PATH.write_text(
            "".join(line + "\n" for line in history_before), encoding="utf-8")
    elif HISTORY_PATH.exists():
        HISTORY_PATH.unlink()
    if synthetic > 0:
        print("cleaned {} synthetic history row(s), kept {} real one(s)".format(
            synthetic, len(history_before)))

    if pricing_before is not None and PRICING_PATH.exists() \
            and PRICING_PATH.read_bytes() != pricing_before:
        PRICING_PATH.write_bytes(pricing_before)
        print("restored tools/pricing.json - a suite wrote to the tracked file directly")

    return 1 if failed_suites else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
