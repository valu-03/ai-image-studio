"""Score a macro-insert batch against the identity-lock and macro-vocabulary gates.

Usage:
    python tools/macro_insert_lint.py --macro temp/outputs/prompts/macro-ada-20260916-1130.json
    python tools/macro_insert_lint.py --macro x.json --set inserts-only

Exit code 0 when every shot passes every check; 1 otherwise - the same
contract as realism_lint.py, ad_lint.py and relight_lint.py.

Realism here is a STRICT 8/8, with no per-shot floor. relight_lint.py accepts
7/8 on an angle shot because build_relight.py routes its composed phrase into
spec["shot_custom"], which replaces the pick:1 camera slot and can legitimately
leave the prompt naming no capture device. This feature does not have that
problem - the shot-size phrase goes into the pick:2 composition layer, which
pins rather than replaces, so the camera slot keeps a real camera. The
`no_custom_shot` check below is what keeps that true: it fails the batch if any
shot ever reintroduces shot_custom, rather than quietly relaxing the gate.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_macro_insert as bmi  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _image_bank():
    return bp.load_bank()


def check_inserts_present(bank, shots, requested):
    wanted = list(bmi.sets(bank)[requested]["inserts"]) if requested in bmi.sets(bank) \
        else [s["insert"] for s in shots]
    actual = [s["insert"] for s in shots]
    missing = [n for n in wanted if n not in actual]
    if missing:
        return False, "missing insert(s): {}".format(", ".join(missing))
    return True, "every requested insert is present: {}".format(", ".join(actual))


def check_realism(bank, shots, requested):
    image_bank = _image_bank()
    bad = []
    for shot in shots:
        present, _missing, banned, warn, _neg = rl.lint(shot["prompt"].lower(), image_bank)
        if len(present) != 8 or banned:
            bad.append("{} scores {}/8{}".format(
                shot["insert"], len(present), " with banned terms" if banned else ""))
        elif warn:
            bad.append("{} trips a soft warning: {}".format(shot["insert"], ", ".join(warn)))
    if bad:
        return False, "; ".join(bad)
    return True, "every shot scores a strict 8/8, no banned or warned terms"


def check_lock_identity(bank, shots, requested):
    """Only the `insert` kinds lock. `full-face` creates the face and has
    nothing to lock to - a lock there would claim a reference that does not
    exist yet."""
    bad = []
    for shot in shots:
        locked = bool(shot["spec"].get("lock_identity"))
        tail = bp.LOCK_TAIL in shot["prompt"]
        if shot["kind"] == "insert":
            if not locked:
                bad.append("{} is not identity-locked".format(shot["insert"]))
            elif not tail:
                bad.append("{} lock clause missing from the prompt".format(shot["insert"]))
        elif locked or tail:
            bad.append("{} creates the face but carries an identity lock".format(shot["insert"]))
    if bad:
        return False, "; ".join(bad)
    return True, "every insert is locked to the reference face; full-face is not"


def check_no_stray_scene_lock(bank, shots, requested):
    """A macro crop changes framing radically and on purpose - the scene lock
    asserts the opposite, so the two would fight inside one prompt."""
    bad = [s["insert"] for s in shots
           if s["spec"].get("lock_scene") or bp.RELIGHT_LOCK_TAIL in s["prompt"]]
    if bad:
        return False, "a scene lock leaked into: {}".format(", ".join(bad))
    return True, "no stray scene lock"


def check_feature_scope(bank, shots, requested):
    """The check that makes this feature real: LOCK_COMPACT alone never says
    "gaze", "lip proportions" or "undertone"."""
    bad = []
    for shot in shots:
        if shot["kind"] != "insert":
            continue
        preserve = bmi.inserts(bank).get(shot["insert"], {}).get("preserve", "")
        if not preserve or preserve.lower() not in shot["prompt"].lower():
            bad.append(shot["insert"])
    if bad:
        return False, "no feature-scoped preserve phrase in: {}".format(", ".join(bad))
    return True, "every insert states exactly what to preserve"


# The skin-macro keys this feature added to realism_lint.DETECT["texture"].
# Checking for these specifically, rather than just "the texture layer scored",
# is deliberate: DETECT["texture"]'s plain "texture" key is start-anchored and
# so fires on the CORE layer's own "true-to-life textures" / "realistic skin
# textures". A shot whose macro vocabulary had been stripped entirely would
# still score the texture layer on that alone - so a check that only asked
# "did texture score?" would pass a prompt with no macro detail left in it.
MACRO_KEYS = ("peach fuzz", "subsurface scattering", "pore-level",
              "sebaceous", "tonal variation")


def check_macro_vocabulary(bank, shots, requested):
    """Every shot must carry the macro bank's OWN skin vocabulary, not merely
    score the texture layer on a word inherited from another layer."""
    bad = []
    for shot in shots:
        low = shot["prompt"].lower()
        if not any(key in low for key in MACRO_KEYS):
            bad.append(shot["insert"])
    if bad:
        return False, "no macro skin vocabulary in: {}".format(", ".join(bad))
    return True, "every shot carries the macro bank's own skin vocabulary"


def check_no_custom_shot(bank, shots, requested):
    bad = [s["insert"] for s in shots
           if s["spec"].get("shot_custom") or s["spec"].get("shot")]
    if bad:
        return False, "took the camera slot (costs the strict 8/8): {}".format(", ".join(bad))
    return True, "no shot takes the camera slot"


def check_unique_inserts(bank, shots, requested):
    seen, dupes = set(), []
    for shot in shots:
        if shot["insert"] in seen:
            dupes.append(shot["insert"])
        seen.add(shot["insert"])
    if dupes:
        return False, "duplicate insert: {}".format(", ".join(dupes))
    return True, "every insert appears once"


def check_subject_unchanged(bank, shots, requested):
    if not shots:
        return False, "no shots"
    fields = ("subject", "wardrobe", "mood")
    base = {f: shots[0]["spec"].get(f) for f in fields}
    bad = [shot["insert"] for shot in shots[1:]
           if any(shot["spec"].get(f) != base[f] for f in fields)]
    if bad:
        return False, "subject/wardrobe/mood drifted in: {}".format(", ".join(bad))
    return True, "one face across the batch"


CHECKS = [
    ("inserts_present", "Requested inserts present", check_inserts_present),
    ("realism", "Realism, strict 8/8", check_realism),
    ("lock_identity", "Identity locked to the reference face", check_lock_identity),
    ("no_stray_scene_lock", "No stray scene lock", check_no_stray_scene_lock),
    ("feature_scope", "Every insert states what to preserve", check_feature_scope),
    ("macro_vocabulary", "Macro texture is detectable", check_macro_vocabulary),
    ("no_custom_shot", "No shot takes the camera slot", check_no_custom_shot),
    ("unique_inserts", "No duplicate inserts", check_unique_inserts),
    ("subject_unchanged", "One face across the batch", check_subject_unchanged),
]


def lint(bank, shots, requested="beauty-macro"):
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
        description="Score a macro-insert batch against the identity-lock and vocabulary gates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--macro", required=True, help="path to a macro batch JSON (from build_macro_insert.py)")
    p.add_argument("--set", default="beauty-macro", help="the set that was requested (default beauty-macro)")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    path = Path(args.macro)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Macro file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    shots = data.get("shots", [])

    bank = bmi.load_bank()
    results = lint(bank, shots, args.set)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<40} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
