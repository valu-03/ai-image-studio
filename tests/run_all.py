"""Run every suite. One command, from anywhere:

    python tests/run_all.py            all suites
    python tests/run_all.py motion     only suites whose name contains "motion"

Each suite is a plain script that prints "  OK" / "  FAIL" lines and exits
non-zero on failure - no test framework, no dependencies beyond PyQt6 for the
GUI suites. Qt runs offscreen so nothing opens a window.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# CLI suites first: they are fast and their failures explain GUI failures.
ORDER = [
    "test_motion.py",
    "test_brief.py",
    "test_advisor.py",
    "test_generate.py",
    "test_upscale.py",
    "test_refine.py",
    "test_midjourney.py",
    "test_history.py",
    "test_lighting_bank.py",
    "test_lighting.py",
    "test_composition_bank.py",
    "test_composition.py",
    "test_combo_resolve.py",
    "test_workers.py",
    "test_color_bank.py",
    "test_style_bank.py",
    "test_posing_bank.py",
    "test_camera_angle_bank.py",
    "test_persona_bank.py",
    "test_autofill.py",
    "test_autofill_gui.py",
    "test_advisor_gui.py",
    "test_library.py",
    "test_influencer_studio_gui.py",
    "test_ads.py",
    "test_sound.py",
    "test_sound_gui.py",
    "test_elevenlabs.py",
    "test_video.py",
    "test_story.py",
    "test_cats_custom.py",
    "test_newui.py",
    "test_layout.py",
    "smoke_gui.py",
]


HISTORY_PATH = ROOT / "temp" / "outputs" / "history.jsonl"
PRICING_PATH = ROOT / "tools" / "pricing.json"


def _read_history():
    if not HISTORY_PATH.exists():
        return []
    return [line for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv):
    global HISTORY_BEFORE
    HISTORY_BEFORE = _read_history()
    # A real clip generated once through the CLI to verify a feature - exactly
    # what a "run it live, once" verification step asks for - permanently
    # overwrites tools/pricing.json's seeded numbers with a real measured charge.
    # That is the feature working correctly, but it left test_video.py silently
    # assuming the seed was still there, and it failed the next time anyone ran
    # this file - twice, on two different real charges. Snapshotting and
    # restoring the tracked file is the same belt-and-braces the history log
    # gets below; the AIVS_PRICING_FILE seam set into `env` is the primary fix.
    pricing_before = PRICING_PATH.read_bytes() if PRICING_PATH.exists() else None
    needle = argv[0].lower() if argv else ""
    suites = [name for name in ORDER
              if (HERE / name).exists() and needle in name.lower()]
    if not suites:
        print("No suites match {!r}. Available: {}".format(
            needle, ", ".join(ORDER)))
        return 2

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    # Central safety net: no suite's idea of "no key" should depend on what is in
    # the developer's .env. read_env() outranks os.environ, so without this a real
    # key silently turns the no-key tests into false passes. Suites may still set
    # their own AIVS_ENV_FILE; setdefault leaves those alone.
    empty_env = Path(tempfile.gettempdir()) / "aivs-run-all-empty.env"
    empty_env.write_text("# intentionally empty" + chr(10), encoding="utf-8")
    env.setdefault("AIVS_ENV_FILE", str(empty_env))
    # A modal "are you sure" nobody can click is a hang, not a safeguard.
    env.setdefault("AIVS_ASSUME_YES", "1")
    # Belt and braces with the snapshot below: no suite can reach the live
    # outcome log at all, so a synthetic 8/8 row cannot bias history.weights().
    env.setdefault("AIVS_HISTORY_FILE", str(empty_env.parent / "aivs-tests-history.jsonl"))
    # Same reasoning, for the pricing table: seeded fresh from the real file on
    # every run, so gv.load_pricing() sees the real seed numbers, but nothing a
    # suite does to it - record_actual(), save_measured() - can reach the file
    # this project actually tracks.
    test_pricing = empty_env.parent / "aivs-tests-pricing.json"
    if PRICING_PATH.exists():
        test_pricing.write_bytes(PRICING_PATH.read_bytes())
    env.setdefault("AIVS_PRICING_FILE", str(test_pricing))
    # Same reasoning again: MainWindow reads AIVS_SETTINGS_APP at import time
    # to pick which QSettings key it opens. Every GUI suite now also sets
    # this itself (so it isolates when run standalone, not just under this
    # runner), but a central default here is the same belt-and-braces this
    # file already applies to the other three - a suite added later that
    # forgets its own setdefault still cannot reach the user's real saved
    # provider/model/theme/window geometry.
    env.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

    total_ok = total_fail = 0
    failed_suites = []

    for name in suites:
        proc = subprocess.run(
            [sys.executable, str(HERE / name)],
            capture_output=True, text=True, cwd=str(ROOT), env=env,
        )
        output = proc.stdout + proc.stderr
        ok = sum(1 for line in output.splitlines() if line.startswith("  OK"))
        bad = [line for line in output.splitlines() if line.startswith("  FAIL")]
        total_ok += ok
        total_fail += len(bad)

        print("{:<18} {:>4} passed, {} failed{}".format(
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

    # Tests write into temp/outputs; leave no synthetic ratings behind - but
    # RESTORE the real log rather than deleting it. This used to unlink the whole
    # file and call every row "synthetic", which destroyed every rating the user
    # had ever given. Those ratings feed history.weights(), so it quietly gutted
    # the feedback loop this project is built on.
    after = _read_history()
    synthetic = len(after) - len(HISTORY_BEFORE)
    if HISTORY_BEFORE:
        HISTORY_PATH.write_text(
            "".join(line + chr(10) for line in HISTORY_BEFORE), encoding="utf-8")
    elif HISTORY_PATH.exists():
        HISTORY_PATH.unlink()
    if synthetic > 0:
        print("cleaned {} synthetic history row(s), kept {} real one(s)".format(
            synthetic, len(HISTORY_BEFORE)))

    # Belt-and-braces restore for the pricing table too - the AIVS_PRICING_FILE
    # seam above should mean nothing touched the real file at all, but this is
    # the same safety net as the history restore in case some code path used
    # `path=` explicitly and bypassed the seam.
    if pricing_before is not None and PRICING_PATH.exists() \
            and PRICING_PATH.read_bytes() != pricing_before:
        PRICING_PATH.write_bytes(pricing_before)
        print("restored tools/pricing.json - a suite wrote to the tracked file directly")

    return 1 if failed_suites else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
