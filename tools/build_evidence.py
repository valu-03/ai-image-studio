"""Compose lived-in evidence: small details that only exist because something
happened before the shutter.

Usage:
    python tools/build_evidence.py --list
    python tools/build_evidence.py --kind human --detail sunglasses-dent --detail hair-tie
    python tools/build_evidence.py --subject "a ginger tabby cat on a sofa" --seed 4
    python tools/build_evidence.py --kind object --detail thumbprint --custom "a price sticker half peeled off"

WHY THIS EXISTS. A generated image is too clean and too generic: nothing in it
has a history. Adding "imperfections" does not fix that - a random flaw reads as
noise. A flaw with a CAUSE reads as a moment that really happened: a dent on the
nose from sunglasses just taken off, hairs shed on the cushion it slept on, a
ring where the bottle stood wet. See evidence_bank.json's `note` for the rest.

Two ways in, the same split every Look toolkit has:
  * pick details by key (`--detail`, repeatable), plus optional free text;
  * or AUTO: give only a subject (or kind) and a seed, and the bank picks
    `auto_count` details for that kind, reproducibly - the same seed always
    picks the same details, the build_sound.accent_for() pattern.

The kind is the subject's - person, animal, object or place - and auto mode
reads it from the Subject text (subject_kind()), first match wins, so "a cat
asleep on her lap" is an animal and "a woman holding a cat" is a person.

Lands in spec["overrides"]["evidence"] - a non-layer override, which
build_prompt.free_overrides() appends to the free trailing segment. That is why
this can never lower a realism score: it only ever ADDS words to a prompt.

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent / "evidence_bank.json"

KINDS = ("human", "animal", "object", "place")


class EvidenceError(ValueError):
    """An unknown kind or detail key, or nothing to compose at all."""


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def options(bank, kind):
    return bank.get("kinds", {}).get(kind, {}).get("options", {})


def subject_kind(bank, subject):
    """'human', 'animal', 'place' or 'object' for a Subject text.

    Whole words only ("he" must not fire inside "the"). Between a person and
    an animal the EARLIEST match wins: the subject is what the sentence opens
    with, so "a cat asleep on her lap" is an animal and "a woman holding her
    cat" is a person. A place word never beats either - "a ginger street cat"
    and "a kitchen with a cat asleep" are about the cat; a place is the
    subject only when no person or animal is named at all. No match at all
    is an object - "a 250ml amber shampoo bottle" names no person, animal or
    room.
    """
    text = str(subject or "").lower()

    def earliest(kind):
        best = None
        for word in bank.get("kind_words", {}).get(kind, []):
            match = re.search(r"(?<![\w-]){}(?![\w-])".format(re.escape(word.lower())), text)
            if match and (best is None or match.start() < best):
                best = match.start()
        return best

    living = [(at, kind) for kind in ("human", "animal") for at in [earliest(kind)] if at is not None]
    if living:
        return min(living)[1]
    return "place" if earliest("place") is not None else "object"


def auto_details(bank, kind, seed=0, count=None):
    """`count` detail keys for `kind`, chosen reproducibly by seed, in bank order."""
    available = list(options(bank, kind))
    count = min(int(count or bank.get("auto_count", 2)), len(available))
    chosen = random.Random("evidence:{}:{}".format(kind, seed)).sample(available, count)
    return [key for key in available if key in chosen]


def compose_evidence(bank, kind, details=(), custom="", seed=None):
    """(phrase, warnings).

    `details` are bank keys for `kind`; `custom` is free text and always
    counts as one detail. With neither, and a `seed`, auto-picks. More than
    `max_details` is trimmed with a warning rather than refused - past three,
    evidence stops reading as a moment and starts reading as clutter.
    Order follows the bank, not the order typed, so the same selection always
    composes to the same string.
    """
    if kind not in bank.get("kinds", {}):
        raise EvidenceError("Unknown kind '{}'. Available: {}".format(
            kind, ", ".join(bank.get("kinds", {}))))
    available = options(bank, kind)
    for key in details:
        if key not in available:
            raise EvidenceError("Unknown {} detail '{}'. See --list.".format(kind, key))

    custom = str(custom or "").strip().rstrip(".")
    keys = [key for key in available if key in set(details)]
    if not keys and not custom:
        if seed is None:
            raise EvidenceError("Pick at least one detail, type your own, or give a seed.")
        keys = auto_details(bank, kind, seed)

    warnings = []
    limit = int(bank.get("max_details", 3))
    total = len(keys) + (1 if custom else 0)
    if total > limit:
        keep = limit - (1 if custom else 0)
        warnings.append(
            "{} details asked for - kept {}. Past {}, lived-in evidence stops reading "
            "as a moment and starts reading as clutter.".format(total, limit, limit))
        keys = keys[:keep]

    phrases = [available[key]["phrase"] for key in keys]
    if custom:
        phrases.append(custom)
    return ", ".join(phrases), warnings


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose lived-in evidence - details with a cause.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--kind", choices=KINDS, help="the subject's kind (default: read from --subject)")
    p.add_argument("--subject", default="", help="Subject text, to infer the kind from")
    p.add_argument("--detail", action="append", default=[], help="a detail key, repeatable")
    p.add_argument("--custom", default="", help="your own detail, as free text")
    p.add_argument("--seed", type=int, help="auto-pick details reproducibly")
    p.add_argument("--list", action="store_true", help="print every detail and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for kind, cfg in bank["kinds"].items():
            print("{}  (--kind {})".format(cfg["label"].upper(), kind))
            for key, option in cfg["options"].items():
                print("  {:<18} {}".format(key, option["phrase"]))
                print("  {:<18} -> {}".format("", option["note"]))
            print()
        return 0

    kind = args.kind or subject_kind(bank, args.subject)
    seed = args.seed if args.seed is not None else (0 if not args.detail and not args.custom else None)
    try:
        phrase, warnings = compose_evidence(bank, kind, args.detail, args.custom, seed)
    except EvidenceError as exc:
        sys.exit(str(exc))
    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
