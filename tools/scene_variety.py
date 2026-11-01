"""Scene variety: a different, real-world light and place for each skit.

Past pictures kept landing in the same sunny-window-plus-wooden-furniture room.
`pick(key, kind)` chooses a light phrase and a place phrase from a hash of
`key` (a skit tag, or the prompt text when there is no tag), so the choice is:

  * deterministic - the same key always gives the same pair, so every shot of
    one skit (which share a tag) shares one light;
  * spread out - different keys land on many different combinations;
  * never the old cliche - no phrase mixes sun and wood.

`names_light_source(text)` is the check the Local API uses to decide whether a
prompt already says where its light comes from; if it does, nothing is added.

Standard library only. `python tools/scene_variety.py --help`.
"""
import argparse
import hashlib
import json
import re

LIGHTS = [
    "overcast afternoon light through a north window",
    "kitchen strip light at night",
    "warm table lamp in an otherwise dark room",
    "cool blue dusk light from a balcony door",
    "bare ceiling bulb with a mix of window light",
    "TV glow flickering across the room in the evening",
    "harsh on-camera flash in a dim hallway",
    "grey rainy-day light from a big window",
    "street lamp glow coming through half-closed blinds",
    "low golden hour light along the floor",
    "fluorescent tube light in a plain garage",
    "bathroom vanity lamp with the door ajar",
    "early morning daylight, pale and flat, through net curtains",
    "soft candle and lamp light at a late dinner",
    "shaded open-door daylight on a back step",
]

PLACES = {
    "default": [
        "a small galley kitchen with tiled walls",
        "a hallway with painted plaster walls and coats on hooks",
        "a tiled bathroom with a frosted window",
        "a cramped balcony with a plastic chair",
        "a garage with shelves of boxes",
        "a stairwell with concrete steps",
        "a laundry room with a washing machine",
        "a bedroom with a bare mattress on the floor",
    ],
    "animal": [
        "a tiled kitchen floor by the fridge",
        "a carpeted hallway by the front door",
        "a laundry room next to the washing machine",
        "a balcony with a plastic crate",
        "a garage floor next to a bicycle",
        "a stairwell landing with a worn mat",
        "a bathroom floor beside the bath",
        "a back step by a rubbish bin",
    ],
}

# Words that mean a prompt already says where its light comes from. A bare
# "light" is not enough ("lighting" and "light grey" are not sources).
_SOURCE_WORDS = [
    "window", "lamp", "sun", "sunlight", "sunset", "sunrise", "daylight",
    "natural light", "overcast", "flash", "candle", "candlelight", "neon",
    "strip light", "tube light", "bulb", "ceiling light", "streetlight",
    "street lamp", "golden hour", "firelight", "fire light", "tv glow",
    "screen glow", "headlight", "lantern", "spotlight", "softbox", "skylight",
    "moonlight", "dusk", "dawn", "led", "fluorescent", "backlit", "lit by",
    "ring light",
]
_SOURCE_RE = re.compile(r"(?<![a-z])(?:" + "|".join(
    re.escape(w) for w in sorted(_SOURCE_WORDS, key=len, reverse=True)) + r")(?![a-z])",
    re.IGNORECASE)


def names_light_source(text):
    """True when `text` names a light source (see _SOURCE_WORDS)."""
    return bool(_SOURCE_RE.search(str(text or "")))


def _index(key, salt, size):
    digest = hashlib.sha256("{}|{}".format(salt, key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def pick(key, kind):
    """{"light": phrase, "place": phrase} for `key`; `kind` is human/animal/place/object."""
    key = str(key or "")
    places = PLACES.get(kind, PLACES["default"])
    return {"light": LIGHTS[_index(key, "light", len(LIGHTS))],
            "place": places[_index(key, "place", len(places))]}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Show the light and place chosen for a skit tag or prompt text.")
    parser.add_argument("key", help="skit tag or prompt text")
    parser.add_argument("--kind", default="human",
                        help="human, animal, place or object (default human)")
    args = parser.parse_args(argv)
    print(json.dumps(pick(args.key, args.kind), indent=2))


if __name__ == "__main__":
    main()
