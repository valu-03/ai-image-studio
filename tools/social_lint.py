"""Gate the words that go on the platform, not the words that go to the model.

Six checks. Exit 0 when every one passes, 1 otherwise - the same contract as
realism_lint.py, story_lint.py, sound_lint.py and safety_lint.py, so a workflow
step can gate on it.

This linter exists for one reason: build_social.py is a generator, and this
project does not ship a generator with nothing deciding whether its output is
good. "A text model suggests, a linter decides" applies even when no text model
was involved - a pattern that composes a title 90 characters long is wrong in
exactly the way a model would have been.

What it cannot judge, and does not pretend to: whether a caption is funny.

Usage:
    python tools/social_lint.py --premise "the kitten will not hand over the phone"
    python tools/social_lint.py --pack temp/outputs/social/x.json

Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_social as bsoc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

TAG = re.compile(r"^#[a-z0-9]+$")


def check_titles(bank, pack):
    """Enough titles, each inside the length window, none repeated."""
    cfg = bsoc.limits(bank)
    titles = [t.strip() for t in pack.get("titles", []) if t and t.strip()]
    wanted = cfg.get("titles_wanted", 3)
    if len(titles) < wanted:
        return False, "{} title(s), wanted {}".format(len(titles), wanted)
    low, high = cfg.get("title_min_chars", 12), cfg.get("title_max_chars", 70)
    bad = ["{!r} is {} chars".format(t[:30], len(t)) for t in titles
           if not (low <= len(t) <= high)]
    if bad:
        return False, "{} - the window is {}-{}".format("; ".join(bad[:2]), low, high)
    if len(set(titles)) != len(titles):
        return False, "two titles are identical"
    return True, "{} titles, {}-{} chars".format(len(titles), low, high)


def check_title_variety(bank, pack):
    """Three titles that all open the same way are one title.

    The cheapest real failure mode of pattern-composed copy: every pattern
    starting with the same slot produces three near-identical lines that look
    like a choice and are not one.
    """
    titles = [t.strip() for t in pack.get("titles", []) if t and t.strip()]
    if len(titles) < 2:
        return True, "too few titles to compare"
    openers = [t.split()[0].lower().rstrip(",:.") for t in titles if t.split()]
    if len(set(openers)) < 2:
        return False, "every title opens with {!r} - that is one title, written out three times".format(
            openers[0])
    return True, "{} distinct openings".format(len(set(openers)))


def check_caption(bank, pack):
    """A caption exists and fits."""
    cfg = bsoc.limits(bank)
    caption = (pack.get("caption") or "").strip()
    low, high = cfg.get("caption_min_chars", 40), cfg.get("caption_max_chars", 300)
    if not caption:
        return False, "no caption"
    if not (low <= len(caption) <= high):
        return False, "{} chars - the window is {}-{}".format(len(caption), low, high)
    return True, "{} chars".format(len(caption))


def check_hashtag_count(bank, pack):
    """The count the brief asked for.

    The bank records that this app's own course notes recommend four at most;
    the brief asked for 15-20 and that is what is enforced. The disagreement is
    reported here on every pass so it stays a visible decision.
    """
    cfg = bsoc.limits(bank)
    tags = pack.get("hashtags", [])
    low, high = cfg.get("hashtag_min", 15), cfg.get("hashtag_max", 20)
    if not (low <= len(tags) <= high):
        return False, "{} hashtags - the brief asks for {}-{}".format(len(tags), low, high)
    advice = bank.get("hashtag_conflict", {}).get("course_advice", "")
    return True, "{} hashtags ({}-{} per the brief; the course notes say: {})".format(
        len(tags), low, high, advice or "n/a")


def check_hashtag_form(bank, pack):
    """Well-formed and unique: one hash, lowercase, no spaces, no repeats."""
    tags = pack.get("hashtags", [])
    bad = [t for t in tags if not TAG.match((t or "").strip())]
    if bad:
        return False, "malformed: {}".format(", ".join(repr(t) for t in bad[:3]))
    lowered = [t.lower() for t in tags]
    dupes = sorted({t for t in lowered if lowered.count(t) > 1})
    if dupes:
        return False, "repeated: {}".format(", ".join(dupes[:3]))
    return True, "all well-formed and unique"


def check_no_claims(bank, pack):
    """No caption that turns a joke into something a viewer could act on."""
    words = [w.lower() for w in bank.get("banned_claims", {}).get("words", [])]
    text = " ".join([pack.get("caption", "")] + list(pack.get("titles", []))).lower()
    hits = [w for w in words if w in text]
    if hits:
        return False, "{} - {}".format(", ".join(hits[:3]),
                                       "a joke caption should not read as a promise")
    return True, "no claim language"


CHECKS = [
    ("titles", "Titles present and sized", check_titles),
    ("variety", "Titles are actually different", check_title_variety),
    ("caption", "Caption present and sized", check_caption),
    ("tag_count", "Hashtag count", check_hashtag_count),
    ("tag_form", "Hashtags well-formed", check_hashtag_form),
    ("claims", "No claim language", check_no_claims),
]


def lint(bank, pack):
    """[(key, label, passed, detail)] - one row per check."""
    return [(key, label) + fn(bank, pack) for key, label, fn in CHECKS]


def score(results):
    return sum(1 for _k, _l, passed, _d in results if passed), len(results)


def passes(bank, pack):
    got, total = score(lint(bank, pack))
    return got == total


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Gate an episode's titles, caption and hashtags.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--premise", help="compose a pack from this premise, then lint it")
    p.add_argument("--captions", nargs="*", default=[])
    p.add_argument("--pack", help="a social pack JSON to lint")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = bsoc.load_bank()

    if args.pack:
        path = Path(args.pack)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Pack not found: {}".format(path))
        with path.open(encoding="utf-8") as fh:
            pack = json.load(fh)
    elif args.premise:
        pack = bsoc.compose_social(bank, args.premise, args.captions, args.seed)
    else:
        sys.exit("Give --premise or --pack.")

    results = lint(bank, pack)
    got, total = score(results)
    for _key, label, passed, detail in results:
        print("{}  {:<28} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
