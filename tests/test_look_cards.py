"""tools/look_cards.py: the six Look cards the one-page studio shows.

No network. The claims worth defending: six cards in a fixed order, options
filtered by subject kind, defaults that are deterministic yet vary (light and
details rotate and avoid recent states), a candid off-centre default for
framing and pose, every option really composes through local_api.compose_look,
and the giveaway bank's `fix` maps agree with the cards.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import giveaways as gv  # noqa: E402
import local_api  # noqa: E402
import look_cards as lc  # noqa: E402

fails = []
KINDS = ("animal", "human", "object", "place")
CARD_IDS = ["light", "camera", "framing", "colour", "pose", "details"]


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== SIX CARDS IN ORDER ===")
check("six_cards_in_order", [c["id"] for c in lc.cards("animal")] == CARD_IDS)
for kind in KINDS:
    for card in lc.cards(kind):
        n = len(card["options"])
        check("{} {} has 4-6 options".format(kind, card["id"]), 4 <= n <= 6, str(n))

print()
print("=== KIND FILTERS ===")
check("kind_filters_options animal",
      not any(o.get("kinds") == ["human"] for c in lc.cards("animal") for o in c["options"]))
check("kind_filters_options human",
      not any(o.get("kinds") == ["animal"] for c in lc.cards("human") for o in c["options"]))
check("object and place see no person-only or animal-only options",
      all(set(o.get("kinds") or KINDS) & {"object", "place"}
          for k in ("object", "place") for c in lc.cards(k) for o in c["options"]))

print()
print("=== DEFAULTS ===")
check("defaults_deterministic", lc.defaults("animal", 7) == lc.defaults("animal", 7))
lights = {lc.defaults("human", s)["light"] for s in range(10)}
check("light varies over seeds", len(lights) >= 3, str(sorted(lights)))
details = {lc.defaults("animal", s)["details"] for s in range(10)}
check("details varies over seeds", len(details) >= 3, str(sorted(details)))
ok = True
for kind in KINDS:
    for s in range(10):
        d = lc.defaults(kind, s)
        ok = ok and lc.defaults(kind, s, avoid=[d])["light"] != d["light"]
        ok = ok and lc.defaults(kind, s, avoid=[d])["details"] != d["details"]
check("defaults_vary_and_avoid", ok)
d = lc.defaults("human", 3)
others = [dict(d, light=o["key"]) for o in lc.cards("human")[0]["options"] if o["key"] != d["light"]]
check("avoid with every option used still returns something",
      lc.defaults("human", 3, avoid=others + [d])["light"] in
      {o["key"] for o in lc.cards("human")[0]["options"]})
fr = lc.defaults("animal", 2)
phrase = lc.phrases(fr, "animal")["composition"].lower()
check("default_framing_not_centred",
      "centered" not in phrase and "centred" not in phrase
      and ("off-center" in phrase or "off-centre" in phrase or "candid" in phrase), phrase)
check("framing default is off_centre_candid", fr["framing"] == "off_centre_candid")
check("pose default is mid_moment for animal and human",
      lc.defaults("animal", 2)["pose"] == "mid_moment" and lc.defaults("human", 2)["pose"] == "mid_moment")
check("every default key is a real option for its kind", all(
    state[c["id"]] in {o["key"] for o in c["options"]}
    for k in KINDS for s in range(6)
    for state in [lc.defaults(k, s)] for c in lc.cards(k)))

print()
print("=== EVERY OPTION COMPOSES ===")
for kind in KINDS:
    base = lc.defaults(kind, 0)
    for card in lc.cards(kind):
        part = card["advanced_part"]
        for opt in card["options"]:
            state = dict(base, **{card["id"]: opt["key"]})
            try:
                out = lc.phrases(state, kind)
                good = bool(out.get(part, "").strip())
                detail = ""
            except local_api.LookError as exc:
                good, detail = False, str(exc)
            check("every_option_composes {} {}:{}".format(kind, card["id"], opt["key"]), good, detail)

print()
print("=== to_look ERRORS ===")
try:
    lc.to_look({"light": "nope"}, "animal")
    check("unknown option raises naming the card", False)
except ValueError as exc:
    check("unknown option raises naming the card", "light" in str(exc), str(exc))
try:
    lc.to_look({"details": "real_skin"}, "animal")
    check("person-only option rejected for animal", False)
except ValueError as exc:
    check("person-only option rejected for animal", "details" in str(exc))

print()
print("=== FIXES ===")
bank = gv.load_bank()["giveaways"]
new, extra = lc.apply_fix(lc.defaults("animal", 1), "posed_centre", "animal")
check("fix_changes_mapped_card", new["framing"] == bank["posed_centre"]["fix"]["framing"])
check("fix sets every mapped card for the bank", all(
    lc.apply_fix(lc.defaults("human", 1), key, "human")[0][card] == opt
    for key, g in bank.items() for card, opt in g["fix"].items()))
check("fix returns the bank's phrase", extra == bank["posed_centre"]["fix_phrase"])
state = lc.defaults("human", 4)
same, phrase = lc.apply_fix(state, "anatomy", "human")
check("unmappable_fix_returns_phrase", same == state and bool(phrase.strip()))
check("apply_fix does not mutate its input", state == lc.defaults("human", 4))
check("fixed state still composes for every kind", all(
    lc.phrases(lc.apply_fix(lc.defaults(k, 1), key, k)[0], k)
    for k in KINDS for key in bank))
try:
    lc.apply_fix(state, "no_such_giveaway", "human")
    check("unknown giveaway raises", False)
except ValueError:
    check("unknown giveaway raises", True)

print()
print("=== FEYNMAN COPY ===")
raw = lc.load()
good = True
for card in raw["cards"]:
    for item in [card] + card["options"]:
        good = good and all(str(item.get(f, "")).strip() for f in ("plain", "example"))
        good = good and len(item["plain"]) <= 120
check("feynman_copy_present", good)

print()
print("=== WEIGHTS ===")
_light = next(c for c in lc.cards("animal") if c["id"] == "light")
_fav = _light["options"][2]["key"]
_w = {"light": {_fav: 4.5}}
check("weights_tilt_ties",
      all(lc.defaults("animal", s, weights=_w)["light"] == _fav for s in range(8))
      and all(lc.defaults("animal", s, avoid=[{"light": _fav}], weights=_w)["light"] != _fav
              for s in range(8))
      and all(lc.defaults("animal", s, weights={"light": {}}) == lc.defaults("animal", s)
              for s in range(8)))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL LOOK CARDS CHECKS PASSED")
