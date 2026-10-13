"""Phone snapshot, unstaged background, the moment - the viral street-cat look.

Usage:
    python tools/build_snapshot.py --list
    python tools/build_snapshot.py --subject "a chubby ginger street cat" \\
        --action "sitting next to an empty metal bowl, staring at it" \\
        --setting "a busy shopping street pavement, overcast day" --seed 2

THE PROBLEM. A reference frame the user supplied - a street cat by an empty
steel bowl - reads as real for reasons no layer of the prompt said:

  * WHO TOOK IT. An ordinary phone held low by someone who crouched down. The
    camera layer's weighted pick could land on "shot on an ARRI Alexa" or
    "cinematic realism" - the polished-cinema look that frame is not.
  * THE BACKGROUND IS NOT STAGED. A passer-by's legs blurred mid-step,
    scooters cut off by the frame, grime in the paving joints. Generated
    backgrounds are empty and tidy, arranged around the subject.
  * A MOMENT, NOT A POSE. The cat is staring at an EMPTY bowl - a split
    second of a story, not a held position.

THREE PARTS, each its own Compose toggle and spec flag (snapshot_bank.json):

  * `snapshot`  - with no shot chosen, prompt_bank.json's own `phone-candid`
    preset supplies camera and lens, the core pick skips its cinema words
    (build_prompt.select_layers), and one "who took it" line by subject kind
    is added. A chosen shot, typed shot, explicit camera/lens or a film stock
    is a deliberate look and wins: nothing changes (the phone presets
    themselves still get the line).
  * `background_life` - the Setting's place gives one passer-by, one unrelated
    everyday thing and one worn surface, picked by seed. A studio or plain
    backdrop gets nothing.
  * `moment` - a split second named by Subject/Action/Posing for the kind,
    or a kind default by seed.

The lines land in non-layer overrides ("snapshot", "background", "moment")
via build_prompt.apply_snapshot(), appended to the free tail - they can only
ADD to a realism score.

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_contact as bct  # noqa: E402
import build_evidence as bev  # noqa: E402

BANK_PATH = Path(__file__).resolve().parent / "snapshot_bank.json"
CAPTURE_PATH = Path(__file__).resolve().parent / "capture_bank.json"
MOMENT_FIELDS = ("subject", "action", "posing")


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _film_stock_phrases():
    with CAPTURE_PATH.open(encoding="utf-8") as fh:
        capture = json.load(fh)
    return [o["phrase"] for o in capture["groups"]["film_stock"]["options"].values()]


def _seeded(salt, kind, seed, options):
    return random.Random("{}:{}:{}".format(salt, kind, seed)).choice(options) if options else ""


def snapshot_mode(bank, spec, custom_shot=False):
    """'phone' (apply the phone preset), 'keep' (a phone preset is already
    chosen - add the line only) or 'skip' (a deliberate look wins)."""
    cfg = bank["snapshot"]
    overrides = spec.get("overrides") or {}
    if "camera" in overrides or "lens" in overrides or custom_shot:
        return "skip"
    values = [v for value in overrides.values()
              for v in ([value] if isinstance(value, str) else list(value))]
    if any(stock in str(v) for v in values for stock in _film_stock_phrases()):
        return "skip"
    shot = spec.get("shot") or ""
    if not shot:
        return "phone"
    return "keep" if shot in cfg["phone_presets"] else "skip"


def phone_layers(bank, prompt_bank):
    """{"camera": [...], "lens": [...]} from prompt_bank.json's phone preset.

    Camera and lens only - the preset's own `extra` ("shot by a friend
    holding the phone") would contradict a who-line about a passer-by."""
    preset = prompt_bank["shot_presets"][bank["snapshot"]["preset"]]
    as_list = lambda v: [v] if isinstance(v, str) else list(v)  # noqa: E731
    return {"camera": as_list(preset["camera"]), "lens": as_list(preset["lens"])}


def who_line(bank, kind, seed=0, mode="phone"):
    """The "who took it" line for a kind, plus the phone processing. In
    'keep' mode the chosen phone preset already says who took it."""
    cfg = bank["snapshot"]
    line = _seeded("snapshot", kind, seed, cfg["who"].get(kind, [])) if mode == "phone" else ""
    return ", ".join(x for x in (line, cfg.get("processing", "")) if x)


def read_place(bank, setting, subject=""):
    """The background key for a Setting (then the Subject), "plain" for a
    studio/backdrop, or None."""
    for text in (str(setting or "").lower(), str(subject or "").lower()):
        if not text.strip():
            continue
        if bct.mentioned({"plain": {"keywords": bank["plain_keywords"]}}, text):
            return "plain"
        keys = bct.mentioned(bank["backgrounds"], text)
        if keys:
            return keys[0]
    return None


def background_line(bank, spec, seed=None):
    """(phrase, place key or None): one passer-by, one everyday thing, one worn surface."""
    seed = spec.get("seed", 0) if seed is None else seed
    place = read_place(bank, spec.get("setting", ""), spec.get("subject", ""))
    if place in (None, "plain"):
        return "", place
    cfg = bank["backgrounds"][place]
    parts = [_seeded("background-" + part, place, seed, cfg.get(part, []))
             for part in ("passers", "clutter", "ground")]
    return ", ".join(p for p in parts if p), place


def moment_line(bank, spec, kind, seed=None):
    """(phrase, action key or None) - the named split second, or a kind default."""
    seed = spec.get("seed", 0) if seed is None else seed
    cfg = bank["moments"]
    text = bct.spec_text(spec, MOMENT_FIELDS)
    for key in bct.mentioned(cfg["actions"], text):
        phrase = cfg["actions"][key].get(kind)
        if phrase:
            return phrase, key
    return _seeded("moment", kind, seed, cfg["by_kind"].get(kind, [])), None


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Phone snapshot, unstaged background and the moment for one spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--subject", default="")
    p.add_argument("--action", default="")
    p.add_argument("--posing", default="")
    p.add_argument("--setting", default="")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--list", action="store_true", help="print the places and moments and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()
    if args.list:
        print("PLACES")
        for key, cfg in bank["backgrounds"].items():
            print("  {:<8} {}".format(key, ", ".join(cfg["keywords"])))
        print("\nMOMENTS")
        for key, cfg in bank["moments"]["actions"].items():
            print("  {:<8} {}".format(key, ", ".join(cfg["keywords"])))
        return 0
    spec = {"subject": args.subject, "action": args.action, "posing": args.posing,
            "setting": args.setting, "seed": args.seed}
    kind = bev.subject_kind(bev.load_bank(), args.subject)
    print("who:        " + who_line(bank, kind, args.seed))
    background, place = background_line(bank, spec)
    print("background: " + (background or "(nothing - {})".format(
        "a plain backdrop" if place == "plain" else "no place recognised in the Setting")))
    print("moment:     " + (moment_line(bank, spec, kind)[0] or "(nothing)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
