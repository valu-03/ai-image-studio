"""tools/scene_variety.py: a different real light and place per series of shots."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import scene_variety as sv  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


KEYS = ["series-{}".format(i) for i in range(50)]
check("deterministic", all(sv.pick(k, "animal") == sv.pick(k, "animal") for k in KEYS))
combos = {tuple(sv.pick(k, "animal").values()) for k in KEYS}
check("spread_ge_5", len(combos) >= 5, str(len(combos)))
every = [p for k in KEYS for kind in ("human", "animal", "place", "object")
         for p in sv.pick(k, kind).values()] + sv.LIGHTS + sum(sv.PLACES.values(), [])
check("no_sunny_wood", not any("sun" in p.lower() and "wood" in p.lower() for p in every))
check("no phrase is wood at all", not any("wood" in p.lower() for p in every))
check("every light phrase names a light source", all(sv.names_light_source(p) for p in sv.LIGHTS))
check("a prompt with a window names one", sv.names_light_source("a cat by the window"))
check("'lighting' and 'light grey' are not sources",
      not sv.names_light_source("a light grey cat, soft lighting"))
check("'Sunday' is not the sun", not sv.names_light_source("a cat on Sunday"))
check("empty key still picks", set(sv.pick("", "human")) == {"light", "place"})

OUT = [sv.pick(k, "animal", True)["light"] for k in KEYS]
check("outdoor_pick_from_outdoor_list", all(p in sv.OUTDOOR_LIGHTS for p in OUT))
check("outdoor_spread_ge_5", len(set(OUT)) >= 5, str(len(set(OUT))))
check("outdoor_no_sunny_wood", not any("sun" in p.lower() and "wood" in p.lower()
                                       for p in sv.OUTDOOR_LIGHTS))
check("outdoor lights name a light source", all(sv.names_light_source(p) for p in sv.OUTDOOR_LIGHTS))
check("outdoor deterministic", sv.pick("series-1", "human", True) == sv.pick("series-1", "human", True))
check("indoor default stays indoor", sv.pick("series-1", "human")["light"] in sv.LIGHTS)
check("street and beach are outdoors", sv.names_outdoor("a cat walks down the street")
      and sv.names_outdoor("a dog on the beach"))
check("'forestry' / 'parkour' are not outdoor words", not sv.names_outdoor("a cat in the kitchen"))

if fails:
    print("\n{} FAILED: {}".format(len(fails), ", ".join(fails)))
    sys.exit(1)
print("\nAll scene_variety checks passed")
