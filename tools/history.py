"""Outcome log — what was generated, and how good it actually turned out.

This is the file that closes the loop. realism_lint.py scores *vocabulary*;
this records what the vocabulary actually produced, so the two can be compared.

Usage:
    python tools/history.py list [--limit 20]
    python tools/history.py show <id>
    python tools/history.py rate <id> <1-5> [--note "..."]
    python tools/history.py analyze [--layer lighting] [--min-count 2]
    python tools/history.py diff <id-a> <id-b>

Store: temp/outputs/history.jsonl — one JSON object per line, append-only in
normal use. Standard library only.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Overridable so a suite can log somewhere disposable. Without this seam, any
# test that exercises a generate path appends to the real outcome log - and
# ratings are what history.weights() runs on, so a handful of synthetic 8/8 rows
# quietly bias the vocabulary the app suggests. The same reasoning as
# AIVS_ENV_FILE: the test must not be able to reach the live data at all.
HISTORY = Path(os.environ.get("AIVS_HISTORY_FILE")
               or (ROOT / "temp" / "outputs" / "history.jsonl"))

LAYERS = ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]

# How fast a term's observed rating overrides the neutral prior. Higher = more
# evidence needed before the bias bites.
CONFIDENCE_PRIOR = 3.0
NEUTRAL_RATING = 3.0

# UCB1's exploration coefficient. weights() used to be pure exploitation - a
# term with one lucky 5-star rating was permanently outweighed by a mediocre
# term with 20 ratings, and a term nobody had ever picked sat at flat neutral
# forever with no way to rise above it. This constant scales the bonus that
# corrects that: bigger = more willing to re-try an under-sampled term at the
# cost of a confidently-good one.
#
# 0.08, not something larger - the exploit half above is BOUNDED (a perfect
# 5-star mean asymptotes to 1.667, so the whole meaningful spread is under
# 0.7), but the bonus grows with sqrt(log(layer_total)), which is unbounded
# and grows FOREVER as more generations happen, however slowly. A first
# attempt at 0.4 passed every check except one - tests/test_history.py caught
# it directly: past roughly 14 total ratings in one layer, an UNTRIED term
# would permanently outrank even a perfectly-rated, heavily-confirmed one,
# because the bonus alone already exceeded the entire exploit range. 0.08
# keeps the bonus a real, meaningful nudge (still enough to out-rank a
# genuinely mediocre established term) without being able to out-rank a truly
# excellent one until N is very large - checked, not assumed, by the same
# test. Tunable later without touching the formula's shape.
EXPLORATION_C = 0.08


def load():
    """Every entry, oldest first. A corrupt line is skipped, not fatal."""
    if not HISTORY.exists():
        return []
    entries = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def save_all(entries):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


BANK_PATH = ROOT / "tools" / "prompt_bank.json"


def current_bank_version():
    """The vocabulary version these ratings are about.

    Ratings reference terms by name. Rename or remove a term and every earlier
    rating silently becomes about something else - weights() would keep
    returning numbers, just wrong ones. Stamping the version is what makes that
    detectable instead of silent.
    """
    try:
        with BANK_PATH.open(encoding="utf-8") as fh:
            return json.load(fh).get("version", 0)
    except (OSError, json.JSONDecodeError):
        return 0


def load_prompt_bank():
    """The full prompt bank, or {} if it cannot be read.

    weights() needs this for the FULL vocabulary per layer, not just terms
    that already happen to have a rating - see its own docstring. A separate
    small read from current_bank_version()'s, which is called at a different
    time (per append(), at write time) and only needs the one field.
    """
    try:
        with BANK_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def new_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:22]


def append(spec, prompt, layers, score, passed, detailed=False, image=None, note="", look=None):
    """Record one generated prompt. Returns the entry id.

    `note` is additive - every existing call site omits it and gets the same
    blank string as before. It exists so a caller that generates outside the
    normal one-shot flow (tools/refine_image.py's retry loop) can tag which
    attempt an entry was, without a second, breaking schema for "traceable".
    """
    entry = {
        "id": new_id(),
        "ts": datetime.now().isoformat(timespec="seconds"),
        "slug": spec.get("slug") or "",
        "subject": spec.get("subject", ""),
        "shot": spec.get("shot", ""),
        "seed": spec.get("seed", 0),
        "detailed": bool(detailed),
        "score": score,
        "passed": bool(passed),
        "bank_version": current_bank_version(),
        "layers": {k: list(v) for k, v in layers.items()},
        # The WHOLE spec, so an entry can be loaded back into Compose.
        # subject/shot/seed above are the three fields the table shows and
        # were all that was ever kept, which meant a history row could be
        # read but never reopened - wardrobe, setting, posing, lighting and
        # every override were simply not recorded. Additive: entries written
        # before this have no "spec" key and every reader uses .get().
        "spec": dict(spec),
        "prompt": prompt,
        "image": image or "",
        "rating": None,
        "note": note or "",
    }
    if look:
        entry["look"] = {"kind": look.get("kind", ""),
                         "cards": dict(look.get("cards") or {})}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["id"]


class AmbiguousId(Exception):
    """More than one entry starts with the given prefix."""

    def __init__(self, matches):
        self.matches = matches
        super().__init__(
            "'{}' matches {} entries — use the full id:\n  {}".format(
                matches[0]["id"][:15], len(matches),
                "\n  ".join(m["id"] for m in matches[:8]),
            )
        )


def find(entries, entry_id):
    """Exact id, or unique prefix. Raises AmbiguousId on an ambiguous prefix."""
    exact = [e for e in entries if e["id"] == entry_id]
    if exact:
        return exact[0]
    matches = [e for e in entries if e["id"].startswith(entry_id)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousId(matches)
    return None


def rate(entry_id, rating, note=None, image=None):
    """Attach an outcome rating (1-5) to an entry. Returns the updated entry."""
    entries = load()
    entry = find(entries, entry_id)
    if entry is None:
        return None
    entry["rating"] = None if rating is None else int(rating)
    if note is not None:
        entry["note"] = note
    if image is not None:
        entry["image"] = image
    save_all(entries)
    return entry


def record_vision_qc(entry_id, result):
    """Attach a post-generation vision QC result to an entry. Returns the entry.

    `result` is whatever tools/vision_lint.py's caller assembled (score, total,
    checks) - stored as-is under a new key. weights()/term_stats() below only
    ever read `layers` and `rating`, so this key is provably inert to the
    bandit logic; no migration is needed for entries that lack it.
    """
    entries = load()
    entry = find(entries, entry_id)
    if entry is None:
        return None
    entry["vision_qc"] = result
    save_all(entries)
    return entry


def usable(entries=None, bank_version=None):
    """(rated entries from the current bank, count skipped as stale)."""
    entries = load() if entries is None else entries
    version = current_bank_version() if bank_version is None else bank_version
    rated = [e for e in entries if e.get("rating") is not None]
    fresh = [e for e in rated if e.get("bank_version", 0) == version]
    return fresh, len(rated) - len(fresh)


def term_stats(entries=None):
    """{layer: {term: {"n": int, "mean": float}}} over rated entries only.

    Entries from an older vocabulary version are excluded, not silently mixed.
    """
    fresh, _ = usable(entries)
    buckets = {layer: {} for layer in LAYERS}
    for entry in fresh:
        if entry.get("rating") is None:
            continue
        for layer, terms in (entry.get("layers") or {}).items():
            if layer not in buckets:
                continue
            for term in terms:
                buckets[layer].setdefault(term, []).append(float(entry["rating"]))
    return {
        layer: {
            term: {"n": len(values), "mean": sum(values) / len(values)}
            for term, values in terms.items()
        }
        for layer, terms in buckets.items()
    }


def weights(entries=None, bank=None):
    """{term: multiplier} biasing selection toward terms worth trying.

    This is UCB1, not a plain average: each term's multiplier is an exploit
    half (today's original shrinkage estimate - a term with no evidence sits
    at the neutral prior, evidence pulls it away in proportion to how much of
    it there is, so one lucky 5-star does not dominate the bank) PLUS an
    explore half that is largest for a term nobody has picked yet and shrinks
    as it accumulates ratings. Without the explore half, a term that got
    exactly one great rating stays permanently outweighed by a mediocre term
    with twenty, and a term nobody has ever picked sits at flat neutral with
    no way to rise above it - build_prompt.pick()'s weighted sampling would
    then just keep confirming whatever already happened to be tried early.

    The candidate set per layer is the FULL bank vocabulary
    (`bank["layers"][name]["terms"]`), not only terms that already have a
    rating - an unrated term needs its own explicit entry to ever be
    preferred, not build_prompt.pick()'s neutral 1.0 fallback for a term
    missing from this dict entirely.

    `layer_total` (the N in UCB's log(N) term) is scored PER LAYER, not
    globally: build_prompt.pick() draws each layer's terms as its own
    independent competition, so a term's exploration bonus should only be
    judged against how much the *rest of its own layer* has been tried.

    With zero ratings anywhere, every term in a layer gets an identical
    bonus - `pick()`'s ranking-by-`rng.random() ** (1/weight)` with a constant
    weight is then mathematically the same as ranking by rng.random() alone,
    i.e. this degrades to today's plain uniform sampling rather than doing
    something new and unverified the first time anyone ever uses the app.
    """
    bank = bank if bank is not None else load_prompt_bank()
    stats = term_stats(entries)
    bank_layers = bank.get("layers", {}) if isinstance(bank, dict) else {}

    result = {}
    for layer in LAYERS:
        layer_stats = stats.get(layer, {})
        layer_total = sum(stat["n"] for stat in layer_stats.values())
        candidates = set(layer_stats) | set(bank_layers.get(layer, {}).get("terms", []))
        for term in candidates:
            stat = layer_stats.get(term)
            n, mean = (stat["n"], stat["mean"]) if stat else (0, NEUTRAL_RATING)
            shrink = n / (n + CONFIDENCE_PRIOR)
            raw = mean / NEUTRAL_RATING
            exploit = 1.0 + (raw - 1.0) * shrink
            bonus = EXPLORATION_C * math.sqrt(math.log(layer_total + 2) / (n + 1))
            result[term] = max(0.1, exploit + bonus)
    return result


THUMBS = {"up": 5, "down": 1}
CARD_PRIOR_RATING = 3.0
CARD_PRIOR_WEIGHT = 2


def recent(limit=30):
    """Newest first, only entries whose image file still exists."""
    out = []
    for entry in reversed(load()):
        image = entry.get("image")
        if not image:
            continue
        path = Path(image)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            out.append(entry)
            if len(out) >= limit:
                break
    return out


def card_weights(entries=None):
    """{card_id: {option_key: mean rating}} from rated entries that stored a look.

    The mean is shrunk toward a neutral 3 with the weight of two ratings, so
    one thumb moves an option only a little. Current bank version only.
    """
    fresh, _ = usable(entries)
    sums = {}
    for entry in fresh:
        cards = (entry.get("look") or {}).get("cards") or {}
        for card_id, key in cards.items():
            total, n = sums.setdefault(card_id, {}).get(key, (0.0, 0))
            sums[card_id][key] = (total + float(entry["rating"]), n + 1)
    return {
        card_id: {
            key: (CARD_PRIOR_RATING * CARD_PRIOR_WEIGHT + total)
            / (CARD_PRIOR_WEIGHT + n)
            for key, (total, n) in options.items()
        }
        for card_id, options in sums.items()
    }


def segments(prompt):
    return [seg.strip() for seg in prompt.split(",") if seg.strip()]


def diff_prompts(prompt_a, prompt_b):
    """(removed, added) comma-segments between two prompts."""
    a, b = segments(prompt_a), segments(prompt_b)
    set_a, set_b = set(a), set(b)
    return [s for s in a if s not in set_b], [s for s in b if s not in set_a]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _fmt_row(entry):
    try:
        rating = int(entry.get("rating"))
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(5, rating))
    stars = "*" * rating + "." * (5 - rating) if rating else "-----"
    return "{id}  {stars}  {score}/8  seed {seed:<5} {slug}".format(
        id=entry.get("id", "?"),
        stars=stars,
        score=entry.get("score", "?"),
        seed=entry.get("seed") if entry.get("seed") is not None else 0,
        slug=(entry.get("slug") or entry.get("subject", ""))[:40],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Log, rate and analyse generated prompts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="recent entries, newest last")
    p_list.add_argument("--limit", type=int, default=20)

    p_show = sub.add_parser("show", help="full entry")
    p_show.add_argument("id")

    p_rate = sub.add_parser("rate", help="attach an outcome rating")
    p_rate.add_argument("id")
    p_rate.add_argument("rating", type=int, choices=[1, 2, 3, 4, 5])
    p_rate.add_argument("--note", default=None)

    p_an = sub.add_parser("analyze", help="which terms correlate with good results")
    p_an.add_argument("--layer", choices=LAYERS, default=None)
    p_an.add_argument("--min-count", type=int, default=1)

    p_diff = sub.add_parser("diff", help="what changed between two prompts")
    p_diff.add_argument("id_a")
    p_diff.add_argument("id_b")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    entries = load()

    def resolve(entry_id):
        try:
            return find(entries, entry_id)
        except AmbiguousId as exc:
            sys.exit(str(exc))

    if args.command == "list":
        if not entries:
            print("No history yet. Generate a prompt first.")
            return 0
        for entry in entries[-args.limit:]:
            print(_fmt_row(entry))
        rated = [e for e in entries if e.get("rating") is not None]
        print("\n{} entries, {} rated.".format(len(entries), len(rated)))
        return 0

    if args.command == "show":
        entry = resolve(args.id)
        if entry is None:
            sys.exit("No entry matching '{}'".format(args.id))
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return 0

    if args.command == "rate":
        entry = rate(args.id, args.rating, args.note)
        if entry is None:
            sys.exit("No entry matching '{}'".format(args.id))
        print("Rated {} -> {}/5".format(entry["id"], entry["rating"]))
        return 0

    if args.command == "diff":
        a, b = resolve(args.id_a), resolve(args.id_b)
        if a is None or b is None:
            sys.exit("Need two valid ids.")
        removed, added = diff_prompts(a["prompt"], b["prompt"])
        print("--- {}  ({}/5)".format(a["id"], a.get("rating") or "-"))
        print("+++ {}  ({}/5)".format(b["id"], b.get("rating") or "-"))
        for seg in removed:
            print("  - " + seg)
        for seg in added:
            print("  + " + seg)
        if not removed and not added:
            print("  (identical segments)")
        return 0

    # analyze
    stats = term_stats(entries)
    rated = [e for e in entries if e.get("rating") is not None]
    if not rated:
        print("Nothing rated yet — ratings are what make this useful.")
        print("Rate a few with:  python tools/history.py rate <id> <1-5>")
        return 0

    print("Based on {} rated generation(s).\n".format(len(rated)))
    layers = [args.layer] if args.layer else LAYERS
    for layer in layers:
        rows = [
            (term, stat) for term, stat in stats[layer].items()
            if stat["n"] >= args.min_count
        ]
        if not rows:
            continue
        rows.sort(key=lambda r: (-r[1]["mean"], -r[1]["n"]))
        print("{}:".format(layer.upper()))
        for term, stat in rows:
            print("  {:>4.2f}  (n={:<3}) {}".format(stat["mean"], stat["n"], term))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

