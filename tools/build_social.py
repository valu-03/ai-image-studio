"""Titles, a caption and hashtags for a finished episode.

The first tool here that writes words for a PLATFORM rather than for a model.
It is deterministic, like every other tool in this folder: it composes from the
bank's patterns and the episode's own premise and captions rather than calling
a language model. What a model would add is phrasing; what this needs is
structure and a gate, and social_lint.py supplies the second.

One disagreement it will not paper over. The series brief asks for 15-20
hashtags. This app's own ugc_bank.json, transcribed from the course, says
"Four at most. More than that and the algorithm gets a confused signal about
the topic." social_lint enforces the brief's range because that is what was
asked for, and this tool prints the course's advice on every run so the choice
stays visible rather than becoming a default nobody remembers making.

Usage:
    python tools/build_social.py --premise "the kitten will not hand over the tiny phone"
    python tools/build_social.py --premise "..." --captions "Bap." "And STAY off the phone."
    python tools/build_social.py --list-premises

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_story as bs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "social_bank.json"


def load_bank(path=None):
    with (Path(path) if path else BANK_PATH).open(encoding="utf-8") as fh:
        return json.load(fh)


def limits(bank):
    return bank.get("limits", {})


def _title_case(text):
    """Sentence case, not Title Case - a platform title reads as a sentence."""
    text = (text or "").strip().rstrip(".")
    return text[:1].upper() + text[1:] if text else ""


def _sentence(text):
    text = (text or "").strip()
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text[:1].upper() + text[1:]


def _short(text, cap=38):
    """The premise trimmed to its first clause.

    Premise seeds run 28-54 characters, and a pattern that wraps one adds
    another 10-35. Long seeds therefore blew the title window and
    social_lint.check_titles rejected the result - correctly, which is how this
    was found. Cutting at the first clause boundary keeps a title readable
    where truncating mid-word would not.
    """
    text = (text or "").strip().rstrip(".")
    for sep in (" and ", " until ", " while ", ", ", " - "):
        if sep in text:
            text = text.split(sep)[0]
            break
    if len(text) > cap:
        text = text[:cap].rsplit(" ", 1)[0]
    return text


def compose_titles(bank, premise, wanted=None, short=None):
    """Distinct titles, longest-fitting first, capped at the bank's length limit.

    Patterns that overflow the limit are skipped rather than truncated: a title
    cut mid-word is worse than one fewer title, and the linter would reject it
    anyway.
    """
    cfg = limits(bank)
    wanted = wanted or cfg.get("titles_wanted", 3)
    high = cfg.get("title_max_chars", 70)
    low = cfg.get("title_min_chars", 12)
    slots = {
        "premise_title": _title_case(premise),
        "premise_lower": (premise or "").strip().rstrip(".").lower(),
        "premise_sentence": _sentence(premise),
        "premise_short": _title_case(short or _short(premise)),
        "premise_short_lower": (short or _short(premise)).lower(),
    }
    out = []
    for pattern in bank.get("title_patterns", []):
        try:
            text = pattern.format(**slots).strip()
        except KeyError:
            continue
        if not (low <= len(text) <= high) or text in out:
            continue
        out.append(text)
        if len(out) >= wanted:
            break
    return out


def compose_caption(bank, premise, captions=(), seed=0):
    """One caption. The episode's last on-screen caption becomes the tag line,
    because that line is the punchline the viewer just watched land."""
    patterns = bank.get("caption_patterns", [])
    if not patterns:
        return ""
    text = patterns[int(seed) % len(patterns)].format(
        premise_sentence=_sentence(premise),
        premise_title=_title_case(premise),
        premise_lower=(premise or "").strip().lower(),
    ).strip()
    tail = next((c for c in reversed(list(captions)) if (c or "").strip()), "")
    if tail:
        text = '{} "{}"'.format(text, tail.strip().rstrip("."))
    high = limits(bank).get("caption_max_chars", 300)
    return text[:high].rstrip()


def compose_hashtags(bank, wanted=None):
    """Tiered, in order, de-duplicated, to the requested count.

    Tiered rather than one flat list so the first tags - the ones carrying the
    most weight - are the ones that actually describe the video.
    """
    cfg = limits(bank)
    wanted = wanted or cfg.get("hashtag_min", 15)
    wanted = max(cfg.get("hashtag_min", 15), min(wanted, cfg.get("hashtag_max", 20)))
    tags, seen = [], set()
    groups = bank.get("hashtags", {})
    for tier in ("core", "niche", "broad"):
        for tag in groups.get(tier, []):
            clean = tag.lstrip("#").strip().lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            tags.append("#" + clean)
            if len(tags) >= wanted:
                return tags
    return tags


def compose_social(bank, premise, captions=(), seed=0, hashtag_count=None, short=None):
    """Everything a finished episode needs to be posted.

    `short` is the premise as a two-to-four word noun phrase. Supplied, it is
    what the title patterns take; omitted, _short() derives one by cutting at
    the first clause. The derived form is a fallback, not the intent - a seed
    written as a sentence cuts into a fragment, which is why story_bank's
    premises carry a hand-written `short` of their own.
    """
    return {
        "premise": (premise or "").strip(),
        "short": (short or _short(premise)).strip(),
        "titles": compose_titles(bank, premise, short=short),
        "caption": compose_caption(bank, premise, captions, seed),
        "hashtags": compose_hashtags(bank, hashtag_count),
    }


def social_text(pack):
    """The pack as something you can paste, one block per field."""
    lines = ["TITLES"]
    for index, title in enumerate(pack.get("titles", []), 1):
        lines.append("  {}. {}".format(index, title))
    lines += ["", "CAPTION", "  " + pack.get("caption", ""), "", "HASHTAGS",
              "  " + " ".join(pack.get("hashtags", []))]
    return "\n".join(lines)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Titles, a caption and hashtags for a finished episode.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--premise", help="the episode in one line (see --list-premises)")
    p.add_argument("--short", help="the episode as a short noun phrase, for the titles")
    p.add_argument("--captions", nargs="*", default=[],
                   help="the episode's on-screen captions, in order")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--hashtags", type=int, help="how many hashtags to emit")
    p.add_argument("--list-premises", action="store_true",
                   help="print story_bank's premise seeds and exit")
    p.add_argument("--json", action="store_true", help="emit the pack as JSON")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list_premises:
        for key, row in bs.premises(bs.load_bank()).items():
            print("  {:<20} {:<30} {}".format(key, row["short"], row["seed"]))
        return 0

    if not args.premise:
        sys.exit("Give --premise (see --list-premises).")

    pack = compose_social(bank, args.premise, args.captions, args.seed, args.hashtags,
                          short=args.short)
    if args.json:
        print(json.dumps(pack, indent=2, ensure_ascii=False))
        return 0

    print(social_text(pack))
    conflict = bank.get("hashtag_conflict", {})
    if conflict:
        print("")
        print("note      {} hashtags, per the series brief.".format(len(pack["hashtags"])))
        print("          This app's own course notes disagree: \"{}\"".format(
            conflict.get("course_advice", "")))
        print("          ({})".format(conflict.get("course_source", "")))
    print("")
    print("[next]    python tools/social_lint.py --premise {!r}".format(args.premise),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
