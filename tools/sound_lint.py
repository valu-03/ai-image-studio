"""Score an ElevenLabs sound-effect prompt against the pattern the course's own
100 examples actually share.

Usage:
    python tools/sound_lint.py "Torch flame crackling in a temple hallway"
    python tools/sound_lint.py --file temp/outputs/prompts/sound-x.txt
    python tools/sound_lint.py --check-bank      # score all 100; they are the fixture

Exit code 0 when the prompt passes every check; 1 otherwise - the same contract
as realism_lint.py, motion_lint.py and ad_lint.py, so a workflow can gate on it.

THE RULES ARE MEASURED, NOT GUESSED. The first version of this file guessed at
the pattern and rejected 31 of the course's own prompts. Counted across all 100:

    word count                              4 to 9, mean 6.5
    carries an -ing action verb             81 / 100
    carries a preposition                   92 / 100
    carries an action, placement or qualifier   100 / 100

(The 82nd -ing word is "being", in "Greek lyre being plucked" - a copula,
not an action, and excluded on purpose.)

So exactly one structural property is universal, and only that one is a hard
check: **the prompt must describe an event rather than an object.** "a sword" is
a thing; "sword unsheathing with a metallic ring" is a sound. Naming the space
is advice, not a rule - "Sandbags rustling and barbed wire creaking" names none
and is a perfectly good prompt.

The other failure worth gating is the one the model answers instead of refusing:
it makes **effects**. Ask it for music or a spoken line and it returns something
unusable. That word list is deliberately short - "dialogue" is not on it, because
example 72 is "Heartbeat slowing down before emotional dialogue", which uses the
word to say *when* the effect plays. A gate that rejects the course's own
example is wrong about the example.

Standard library only. No API keys, no network.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "sound_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def examples(bank):
    return bank.get("examples", [])


def themes(bank):
    return bank.get("themes", {})


def roles(bank):
    return bank.get("roles", {})


def by_theme(bank, theme):
    return [e for e in examples(bank) if e.get("theme") == theme]


# An -ing verb of three letters or more before the suffix, so "ring" and "king"
# do not read as actions on their own.
ACTION = re.compile(r"\b[a-z]{3,}ing\b", re.IGNORECASE)

# Event nouns: the 18 examples with no -ing verb lean on these instead -
# "Squishy cheese plop", "Dramatic punch impact", "Sudden flash ... pulse".
EVENT_WORDS = [
    "plop", "slap", "squeak", "slip", "gulp", "fart", "ding", "pop", "whoosh",
    "boom", "impact", "zap", "burst", "crack", "thud", "clank", "chant", "roar",
    "hum", "static", "siren", "explosion", "sizzle", "growl", "chatter", "flash",
    "pulse", "rewind", "change", "reverb", "echo", "noise", "sound", "distortion",
    "silence", "footstep", "screaming",
]


def _has_any(text, words):
    """Word-boundary match, so 'in' does not fire inside 'raining'."""
    lower = (text or "").lower()
    found = []
    for word in words:
        pattern = r"\b" + re.escape(word.lower()) + r"\b"
        if re.search(pattern, lower):
            found.append(word)
    return found


def check_present(bank, text):
    if (text or "").strip():
        return True, "{} words".format(len((text or "").split()))
    return False, "nothing to judge - write the effect first"


def check_event(bank, text):
    """The one structural property all 100 examples share.

    An action, a placement or a qualifier - any one of them turns a noun into a
    sound. Requiring more than one would reject the course's own prompts.
    """
    if not (text or "").strip():
        return False, "nothing to judge"
    action = ACTION.search(text or "")
    events = _has_any(text, EVENT_WORDS)
    placement = _has_any(text, bank.get("placement_words", []))
    treatment = _has_any(text, bank.get("treatments", []))

    if action:
        return True, "action: {}".format(action.group(0))
    if events:
        return True, "event: {}".format(events[0])
    if placement or treatment:
        return True, "qualified: {}".format((placement or treatment)[0])
    return False, ("this names an object, not a sound. Say what it is DOING "
                   "(\"sword unsheathing\"), where it is, or how it sounds.")


def check_length(bank, text):
    limit = bank.get("pattern", {}).get("max_words", 12)
    words = len((text or "").split())
    if words <= limit:
        return True, "{} words".format(words)
    return False, ("{} words; keep it under {}. The course's examples run 4 to 9 - "
                   "past that you are describing a scene, not a sound.".format(words, limit))


def check_is_an_effect(bank, text):
    """The failure the model answers instead of refusing."""
    hits = _has_any(text, bank.get("not_effects", []))
    if not hits:
        return True, "an effect, not music or speech"
    return False, ("asks for {} - this model makes sound EFFECTS only. Music and "
                   "spoken lines come back unusable.".format(hits[0]))


CHECKS = [
    ("present", "Something to judge", check_present),
    ("event", "Describes an event", check_event),
    ("length", "Short enough", check_length),
    ("effect", "Is an effect", check_is_an_effect),
]


def lint(bank, text):
    """[(key, label, passed, detail)] - one row per hard check."""
    return [(key, label, *fn(bank, text)) for key, label, fn in CHECKS]


def score(results):
    return sum(1 for _, _, passed, _ in results if passed), len(results)


def passes(bank, text):
    got, total = score(lint(bank, text))
    return got == total


def advice(bank, text):
    """Notes that are worth saying but are not failures.

    Kept separate from lint() on purpose. 92 of the 100 examples name a space
    and 81 carry an -ing action verb, so both are strong habits - but neither is
    universal, and a gate may only fail what is actually required.
    """
    notes = []
    if not _has_any(text, bank.get("placement_words", [])) \
            and not _has_any(text, bank.get("treatments", [])):
        notes.append(
            "No space or treatment. 92 of the 100 examples say where it happens "
            "(\"in a temple hallway\") or how it sounds (\"with comedic echo\") - "
            "it is the single cheapest upgrade to a prompt.")
    if not ACTION.search(text or ""):
        notes.append(
            "No -ing verb. 81 of the 100 use one; it is the most reliable way to "
            "tell the model this is an event.")
    if len((text or "").split()) < 4:
        notes.append("Shorter than any of the 100 examples, which start at 4 words.")
    return notes


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score an ElevenLabs sound-effect prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("text", nargs="?", help="the prompt to score")
    p.add_argument("--file", help="read the prompt from a file instead")
    p.add_argument("--check-bank", action="store_true",
                   help="score all 100 example prompts; they are the fixture")
    p.add_argument("--theme", help="print the examples for one theme, then exit")
    p.add_argument("--list-themes", action="store_true", help="print the themes")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    bank = load_bank()

    if args.list_themes:
        for key, cfg in themes(bank).items():
            print("{:<12} {:<20} {}".format(key, cfg["label"], cfg["note"]))
        return 0

    if args.theme:
        rows = by_theme(bank, args.theme)
        if not rows:
            sys.exit("Unknown theme '{}'. Available: {}".format(
                args.theme, ", ".join(themes(bank))))
        for entry in rows:
            print("{:>3}. {}".format(entry["n"], entry["text"]))
        return 0

    if args.check_bank:
        bad = []
        for entry in examples(bank):
            results = lint(bank, entry["text"])
            got, total = score(results)
            if got != total:
                bad.append((entry, [d for _, _, ok, d in results if not ok]))
        print("{}/{} of the course's own examples pass".format(
            len(examples(bank)) - len(bad), len(examples(bank))))
        for entry, reasons in bad:
            print("  {:>3}. {}".format(entry["n"], entry["text"]))
            for reason in reasons:
                print("       {}".format(reason))
        return 1 if bad else 0

    text = args.text
    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        text = path.read_text(encoding="utf-8").strip()
    if not text:
        sys.exit("Give a prompt, or --file <path>. See --help.")

    results = lint(bank, text)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<24} {}".format("PASS" if passed else "FAIL", label, detail))
    for note in advice(bank, text):
        print("note  {}".format(note))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
