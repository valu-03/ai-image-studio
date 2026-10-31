"""Read a generated PHOTO for giveaways: what makes it look made, not taken.

A vision model looks at the picture and says which of a short, fixed list of
giveaways it can see and where. The list lives in tools/giveaway_bank.json;
the reply is whitelisted against it, exactly like tools/vision_lint.py: only
bank keys are ever read, a reply that is not a JSON object is reported as an
error (never a false "looks real", never a crash), and the result is
display-only - it is never pasted into a prompt.

These are photographic-realism notes only (framing, texture, light, anatomy).

Usage:
    python tools/giveaways.py --image temp/outputs/images/x.png --kind animal
    python tools/giveaways.py --image x.png --kind human --reference ref.png

Key:   OPENROUTER_API_KEY in .env, same as ask_llm.py.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask_llm  # noqa: E402

BANK_PATH = Path(__file__).resolve().parent / "giveaway_bank.json"
KINDS = ("animal", "human", "object", "place")
UNREADABLE = "The picture check didn't answer in a form we can read."


def load_bank():
    with open(BANK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _keys_for(giveaways, kind):
    return [k for k, g in giveaways.items() if kind in g["kinds"]]


def build_prompt(kind, has_reference):
    bank = load_bank()["giveaways"]
    keys = _keys_for(bank, kind)
    lines = ["Look at the FIRST image as a photograph and say which of these "
             "giveaways, if any, make it look generated instead of taken:"]
    for key in keys:
        look_for = bank[key]["look_for"]
        lines.append("- {}: {}".format(key, look_for.get(kind) or look_for["default"]))
    if has_reference:
        lines.append("The SECOND image is only a reference for the subject; do "
                     "not judge it.")
    lines.append("")
    lines.append(
        "Return ONLY a JSON object, no prose, no markdown fences, with one entry "
        "per giveaway above using these exact keys: {}.".format(", ".join(keys)))
    lines.append('Each value is {"seen": true|false, "where": "a short place in the '
                 'picture, or empty"}.')
    return "\n".join(lines)


def check(image_path, kind, reference_path=None, model=None, ask=None):
    """(giveaways, error) - exactly one is None.

    giveaways: [{"key", "label", "plain", "where", "fixable"}, ...] for every
    bank key the model marked seen, in bank order. `ask` defaults to
    ask_llm.ask and exists so a test can inject a fake.
    """
    ask = ask or ask_llm.ask
    bank = load_bank()["giveaways"]
    images = [image_path] + ([reference_path] if reference_path else [])
    text, error = ask(build_prompt(kind, bool(reference_path)), images=images, model=model)
    if error:
        return None, error
    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return None, UNREADABLE

    found = []
    for key in _keys_for(bank, kind):
        entry = payload.get(key)
        if not (isinstance(entry, dict) and entry.get("seen") is True):
            continue
        g = bank[key]
        found.append({
            "key": key,
            "label": g["label"],
            "plain": g["plain"],
            "where": str(entry.get("where", "") or "").strip(),
            "fixable": bool(g["fix"] or g["fix_phrase"]),
        })
    return found, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--reference", help="a reference image of the subject")
    parser.add_argument("--model", help="override the vision model id for this call")
    args = parser.parse_args(argv)

    found, error = check(args.image, args.kind, args.reference, args.model)
    if error:
        print(error, file=sys.stderr)
        return 3
    if not found:
        print("No giveaways spotted.")
        return 0
    for g in found:
        where = " ({})".format(g["where"]) if g["where"] else ""
        print("- {}{}: {}".format(g["label"], where, g["plain"]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
