"""Score a static ad batch (studio/lifestyle composites) against the
label-accuracy and reference-fidelity gates.

Usage:
    python tools/static_ad_lint.py --static-ad temp/outputs/prompts/static-ad-lumawash-20260915-1200.json
    python tools/static_ad_lint.py --static-ad x.json --mode lifestyle

Exit code 0 when every shot passes every check; 1 otherwise - the same
contract as realism_lint.py, ad_lint.py and relight_lint.py.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402
import build_static_ad as bsa  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def check_modes_present(bank, shots, requested):
    wanted = list(bsa.modes(bank)) if requested == "both" else [requested]
    actual = [s["mode"] for s in shots]
    missing = [m for m in wanted if m not in actual]
    if missing:
        return False, "missing mode(s): {}".format(", ".join(missing))
    return True, "every requested mode is present: {}".format(", ".join(actual))


def check_realism(bank, shots, requested):
    image_bank = bp.load_bank()
    bad = []
    for shot in shots:
        present, _missing, banned, _warn, _neg = rl.lint(shot["prompt"].lower(), image_bank)
        if len(present) != 8 or banned:
            bad.append("{} scores {}/8{}".format(
                shot["mode"], len(present), " with banned terms" if banned else ""))
    if bad:
        return False, "; ".join(bad)
    return True, "every shot scores 8/8, no banned terms"


def check_label_accuracy(bank, shots, requested):
    phrase = bank.get("label_accuracy_phrase", "")
    bad = [s["mode"] for s in shots if phrase.lower() not in s["prompt"].lower()]
    if bad:
        return False, "label-accuracy instruction missing from: {}".format(", ".join(bad))
    return True, "every shot states the label-accuracy instruction"


def check_references(bank, shots, requested):
    bad = [s["mode"] for s in shots if not s.get("references")]
    if bad:
        return False, "no reference image attached: {}".format(", ".join(bad))
    return True, "every shot carries at least the product reference"


def check_no_stray_lock(bank, shots, requested):
    bad = []
    for shot in shots:
        cfg = bsa.modes(bank).get(shot["mode"], {})
        if not cfg.get("presenter") and (shot["spec"].get("lock_identity") or shot["spec"].get("lock_scene")):
            bad.append(shot["mode"])
    if bad:
        return False, "a presenter-less mode carries an identity/scene lock: {}".format(", ".join(bad))
    return True, "no stray identity/scene lock on a presenter-less mode"


CHECKS = [
    ("modes_present", "Requested modes present", check_modes_present),
    ("realism", "Realism 8/8", check_realism),
    ("label_accuracy", "Label-accuracy instruction present", check_label_accuracy),
    ("references", "Reference image attached", check_references),
    ("no_stray_lock", "No stray identity/scene lock", check_no_stray_lock),
]


def lint(bank, shots, requested="both"):
    """[(key, label, passed, detail)] - one row per check."""
    results = []
    for key, label, fn in CHECKS:
        passed, detail = fn(bank, shots, requested)
        results.append((key, label, passed, detail))
    return results


def score(results):
    return sum(1 for _, _, passed, _ in results if passed), len(results)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a static ad batch against the label-accuracy and reference gates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--static-ad", required=True, help="path to a static-ad batch JSON")
    p.add_argument("--mode", default="both", help="the mode(s) that were requested (default both)")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    path = Path(args.static_ad)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Static-ad file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    shots = data.get("shots", [])

    bank = bsa.load_bank()
    results = lint(bank, shots, args.mode)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<36} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
