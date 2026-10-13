"""Light that comes FROM the scene - its source, its bounce, its shadows.

Usage:
    python tools/build_scene_light.py --setting "a cocktail bar at night, brick walls, wooden counter"
    python tools/build_scene_light.py --setting "a sunny beach at noon" --seed 3
    python tools/build_scene_light.py --setting "a kitchen at night" --lighting "golden hour sunlight"

THE PROBLEM. With Compose's Lighting on (auto), build_prompt used to draw one of
prompt_bank.json's nine lighting terms at random, never looking at the Setting -
so a bar at night could be lit by "golden hour sunlight". A subject lit one way
inside a scene that implies another is the pasted-in look.

THREE THINGS, all read from the Setting text (place, time of day, materials):

  1. The SOURCE. `allowed_terms()` narrows the lighting layer to the bank
     terms that can exist there - the place's list intersected with the
     time's, falling back to whichever matched, then to all nine. The
     weighted pick in build_prompt.select_layers() still chooses among them,
     so history.weights() keeps working. `source_phrase()` names the actual
     light: "street lamps overhead and the glow of shop windows".
  2. BOUNCE. Light takes the colour of what it hits - warm off wood, green
     off grass, cool off snow, coloured off a neon sign. Up to two, in the
     order the Setting mentions them.
  3. SHADOWS. One direction for subject and scene, and a contact shadow
     where they meet - mismatched or missing shadows are the second most
     common tell of a generated image.

`conflicts_with()` reports an explicit lighting choice that contradicts the
Setting ("harsh midday sunlight" in a setting that says "at night"). Reported,
never corrected - an explicit choice wins, a disagreement is surfaced.

No import of build_prompt here (build_prompt imports this). Standard library
only. No API keys, no network.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent / "scene_light_bank.json"
PROMPT_BANK_PATH = Path(__file__).resolve().parent / "prompt_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _all_lighting_terms():
    with PROMPT_BANK_PATH.open(encoding="utf-8") as fh:
        return list(json.load(fh)["layers"]["lighting"]["terms"])


def _first_hit(text, words):
    """Position of the earliest whole-word match of any of `words`, or None."""
    best = None
    for word in words:
        match = re.search(r"(?<!\w){}(?!\w)".format(re.escape(word.lower())), text)
        if match and (best is None or match.start() < best):
            best = match.start()
    return best


def _earliest(table, text):
    """The key in `table` whose keywords appear earliest in `text`, or None."""
    best_key, best_at = None, None
    for key, cfg in table.items():
        at = _first_hit(text, cfg.get("keywords", []))
        if at is not None and (best_at is None or at < best_at):
            best_key, best_at = key, at
    return best_key


def read_scene(bank, setting):
    """(place key or None, time key or None) for a Setting text."""
    text = str(setting or "").lower()
    return _earliest(bank["places"], text), _earliest(bank["times"], text)


def allowed_terms(bank, setting, terms=None):
    """The lighting-layer terms this Setting allows, in the bank's own order.

    Place AND time when both match and agree on something; otherwise the time
    (it is the stronger physical constraint - nothing makes noon sun at night)
    then the place; otherwise every term, unchanged. Never returns a term the
    prompt bank does not own.
    """
    terms = list(terms) if terms is not None else _all_lighting_terms()
    place, time = read_scene(bank, setting)
    sets = []
    if place and time:
        both = set(bank["places"][place]["allowed"]) & set(bank["times"][time]["allowed"])
        sets.append(both)
    if time:
        sets.append(set(bank["times"][time]["allowed"]))
    if place:
        sets.append(set(bank["places"][place]["allowed"]))
    for allowed in sets:
        narrowed = [t for t in terms if t in allowed]
        if narrowed:
            return narrowed
    return terms


def source_phrase(bank, setting):
    """The named light in this place, at this time, or "" when nothing matched."""
    place, time = read_scene(bank, setting)
    if place:
        cfg = bank["places"][place]
        return (cfg.get("by_time", {}).get(time) if time else None) or cfg["source"]
    if time:
        return bank["times"][time]["source"]
    return ""


def bounce_phrases(bank, setting):
    """Up to max_surfaces bounce phrases, in the order the Setting names them."""
    text = str(setting or "").lower()
    found = []
    for key, cfg in bank["surfaces"].items():
        at = _first_hit(text, cfg["keywords"])
        if at is not None:
            found.append((at, cfg["phrase"]))
    found.sort()
    phrases = list(dict.fromkeys(p for _at, p in found))
    return phrases[:int(bank.get("max_surfaces", 2))]


def shadow_phrases(bank, seed=0):
    """One coherence phrase and one contact-shadow phrase, chosen by seed."""
    rng = random.Random("scene-light:{}".format(seed))
    return [rng.choice(bank["shadows"]["coherence"]), rng.choice(bank["shadows"]["contact"])]


def scene_light(bank, setting, seed=0, include_source=True):
    """(phrase, place, time). The tail phrase: source (unless the lighting
    layer was chosen explicitly - then naming another source would contradict
    it), bounce, shadows. Shadows are physics and true under any light, so
    they come through even for an empty Setting."""
    place, time = read_scene(bank, setting)
    parts = []
    source = source_phrase(bank, setting) if include_source else ""
    if source:
        parts.append("lit by " + source)
    parts.extend(bounce_phrases(bank, setting))
    parts.extend(shadow_phrases(bank, seed))
    return ", ".join(parts), place, time


def conflicts_with(bank, setting, lighting):
    """Notes for an explicit lighting choice the Setting contradicts. [] if none.

    Two checks: a bank term outside what the time of day allows, and - for
    free text the bank has no list for - a clash word the time names.
    """
    lighting = str(lighting or "").strip()
    if not lighting:
        return []
    place, time = read_scene(bank, setting)
    if not time:
        return []
    cfg = bank["times"][time]
    lower = lighting.lower()
    bank_terms = _all_lighting_terms()
    clash = (lighting in bank_terms and lighting not in cfg["allowed"]) or \
        any(_first_hit(lower, [w]) is not None for w in cfg.get("clashes", []))
    if not clash:
        return []
    return ["\"{}\" does not fit a {} setting - it suggests {}".format(
        lighting, time, " or ".join(cfg["allowed"]))]


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Light that comes from the scene: source, bounce, shadows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--setting", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lighting", default="", help="an explicit lighting choice, to check it fits")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    phrase, place, time = scene_light(bank, args.setting, args.seed,
                                      include_source=not args.lighting)
    print(phrase)
    print("[place: {}, time: {}] lighting layer may use: {}".format(
        place or "-", time or "-", ", ".join(allowed_terms(bank, args.setting))), file=sys.stderr)
    for note in conflicts_with(bank, args.setting, args.lighting):
        print("[heads up] " + note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
