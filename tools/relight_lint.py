"""Score a relight/re-angle batch against the scene-lock and vocabulary gates.

Usage:
    python tools/relight_lint.py --relight temp/outputs/prompts/relight-porch-20260915-1200.json

Exit code 0 when every shot passes every check; 1 otherwise - the same
contract as realism_lint.py and ad_lint.py, so a workflow step can gate on it.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def check_realism(image_bank, shots):
    """8/8 for a lighting-only shot. A shot that also requested an angle is
    held to 7/8 with `camera` as the only miss - build_camera_angle.py's own
    docstring documents this tradeoff: its composed phrase replaces the
    camera slot and can legitimately name no capture device, "that's the gate
    working, not a bug." Anything below that, or any banned term, still fails.
    """
    bad = []
    for shot in shots:
        present, missing, banned, _warn, _neg = rl.lint(shot["prompt"].lower(), image_bank)
        has_angle = any(shot.get(k) for k in ("vertical", "side", "size"))
        missing_names = {name for name, _cfg, _hit in missing}
        floor = 7 if has_angle and missing_names <= {"camera"} else 8
        if len(present) < floor or banned:
            bad.append("shot {} scores {}/8{}".format(
                shot["index"], len(present), " with banned terms" if banned else ""))
    if bad:
        return False, "; ".join(bad)
    return True, "every shot scores 8/8 (7/8 with only camera missing, on an angle shot)"


def check_lock_scene(image_bank, shots):
    bad = []
    for shot in shots:
        if not shot["spec"].get("lock_scene"):
            bad.append("shot {} is not scene-locked".format(shot["index"]))
        elif bp.RELIGHT_LOCK_TAIL not in shot["prompt"]:
            bad.append("shot {} lock clause missing from the prompt".format(shot["index"]))
    if bad:
        return False, "; ".join(bad)
    return True, "every shot is scene-locked to the reference photo"


def check_vocabulary_present(image_bank, shots):
    """Whatever a shot asked for (lighting and/or angle) must actually be
    detectable in ITS OWN prompt - realism_lint's own lighting/composition
    DETECT tables already cover every lighting_bank/camera_angle_bank phrase
    (see tools/realism_lint.py), so this reuses that gate rather than a
    second keyword table."""
    bad = []
    for shot in shots:
        present, _missing, _banned, _warn, _neg = rl.lint(shot["prompt"].lower(), image_bank)
        hit_layers = {name for name, _cfg, _hit in present}
        if shot.get("lighting_setup") and "lighting" not in hit_layers:
            bad.append("shot {} lighting not detectable".format(shot["index"]))
        if any(shot.get(k) for k in ("vertical", "side", "size")) and "composition" not in hit_layers:
            bad.append("shot {} angle not detectable".format(shot["index"]))
    if bad:
        return False, "; ".join(bad)
    return True, "every requested lighting/angle is detectable in its own prompt"


def check_unique_combos(image_bank, shots):
    seen, dupes = set(), []
    for shot in shots:
        key = (shot.get("lighting_setup"), shot.get("vertical"), shot.get("side"), shot.get("size"))
        if key in seen:
            dupes.append("shot {}".format(shot["index"]))
        seen.add(key)
    if dupes:
        return False, "duplicate lighting/angle combo: {}".format(", ".join(dupes))
    return True, "every shot has a distinct lighting/angle combo"


def check_subject_unchanged(image_bank, shots):
    if not shots:
        return False, "no shots"
    fields = ("subject", "wardrobe", "setting", "action")
    base = {f: shots[0]["spec"].get(f) for f in fields}
    bad = [
        "shot {}".format(shot["index"]) for shot in shots[1:]
        if any(shot["spec"].get(f) != base[f] for f in fields)
    ]
    if bad:
        return False, "subject/wardrobe/setting/action drifted in: {}".format(", ".join(bad))
    return True, "subject, wardrobe, setting and action are identical across the batch"


CHECKS = [
    ("realism", "Realism 8/8", check_realism),
    ("lock_scene", "Scene locked to the reference photo", check_lock_scene),
    ("vocabulary", "Requested lighting/angle is detectable", check_vocabulary_present),
    ("unique_combos", "No duplicate lighting/angle combos", check_unique_combos),
    ("subject_unchanged", "Only lighting/angle vary", check_subject_unchanged),
]


def lint(image_bank, shots):
    """[(key, label, passed, detail)] - one row per check."""
    results = []
    for key, label, fn in CHECKS:
        passed, detail = fn(image_bank, shots)
        results.append((key, label, passed, detail))
    return results


def score(results):
    return sum(1 for _, _, passed, _ in results if passed), len(results)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a relight/re-angle batch against the scene-lock and vocabulary gates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--relight", required=True, help="path to a relight batch JSON (from build_relight.py)")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    path = Path(args.relight)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Relight file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    shots = data.get("shots", [])

    image_bank = bp.load_bank()
    results = lint(image_bank, shots)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<40} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
