"""The six Look cards the one-page photo studio shows.

Each card (light, camera, framing, colour, pose, details) offers a few curated
options with plain-English copy; an option's `look` maps a local_api LOOK_KEY
to a compose_look choice or a ready phrase. A card state is {card_id: option_key}.

Usage:
    python tools/look_cards.py --kind animal --seed 3
"""

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import giveaways  # noqa: E402
import local_api  # noqa: E402

CARDS_PATH = Path(__file__).resolve().parent / "look_cards.json"
KINDS = ("animal", "human", "object", "place")
ROTATING = ("light", "details")


def load():
    with open(CARDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_kind(kind):
    if kind not in KINDS:
        raise ValueError("unknown kind: {}".format(kind))


def _visible(option, kind):
    return kind in (option.get("kinds") or KINDS)


def cards(kind):
    """The six cards with only the options that suit `kind`."""
    _check_kind(kind)
    out = []
    for card in copy.deepcopy(load()["cards"]):
        card["options"] = [o for o in card["options"] if _visible(o, kind)]
        out.append(card)
    return out


def defaults(kind, seed, avoid=()):
    """{card_id: option_key}. Same seed, same answer.

    Light and details rotate with the seed and skip any choice used in
    `avoid` (recent states) when another exists; the other cards take their
    fixed candid default (or the first option if it does not suit the kind).
    """
    state = {}
    for card in cards(kind):
        keys = [o["key"] for o in card["options"]]
        if card["id"] in ROTATING:
            used = {a.get(card["id"]) for a in avoid}
            start = seed % len(keys)
            ordered = keys[start:] + keys[:start]
            state[card["id"]] = next((k for k in ordered if k not in used), ordered[0])
        else:
            want = card.get("default")
            state[card["id"]] = want if want in keys else keys[0]
    return state


def to_look(state, kind):
    """A local_api.compose_look choices dict. ValueError names a bad card."""
    by_id = {c["id"]: c for c in cards(kind)}
    look = {}
    for card_id, key in state.items():
        card = by_id.get(card_id)
        if card is None:
            raise ValueError("unknown card: {}".format(card_id))
        option = next((o for o in card["options"] if o["key"] == key), None)
        if option is None:
            raise ValueError("{}: unknown option '{}'".format(card_id, key))
        look.update(copy.deepcopy(option["look"]))
    return look


def phrases(state, kind):
    return local_api.compose_look(to_look(state, kind))[0]


def apply_fix(state, giveaway_key, kind):
    """(new state, fix_phrase). Cards the fix names but `kind` has no such
    option for are left alone."""
    bank = giveaways.load_bank()["giveaways"]
    if giveaway_key not in bank:
        raise ValueError("unknown giveaway: {}".format(giveaway_key))
    entry = bank[giveaway_key]
    by_id = {c["id"]: {o["key"] for o in c["options"]} for c in cards(kind)}
    new = dict(state)
    for card_id, key in entry["fix"].items():
        if key in by_id.get(card_id, ()):
            new[card_id] = key
    return new, entry.get("fix_phrase", "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    state = defaults(args.kind, args.seed)
    print(json.dumps(state, indent=2))
    for part, text in phrases(state, args.kind).items():
        print("{}: {}".format(part, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
