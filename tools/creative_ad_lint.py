"""Score a static ad against the ten creative-direction commands.

Usage:
    python tools/creative_ad_lint.py --ad temp/outputs/prompts/creative-ad-lumawash.json
    python tools/creative_ad_lint.py --ad x.json --ticked direction,premium
    python tools/creative_ad_lint.py --commands       # print the ten and exit

Exit code 0 when every row passes; 1 otherwise - the same contract as
realism_lint.py, ad_lint.py and static_ad_lint.py.

WHAT IS DIFFERENT ABOUT THIS GATE. Every other linter in this app scores a
PROMPT. This one scores an IDEA, and most of what makes an idea good cannot be
counted. So eight rows are checked and two are not, and the two that are not
block the verdict anyway - see `ready` below. An auto row whose rule cannot
actually run is downgraded to manual rather than shown as checked-but-blank,
which is ui/views/ads.py's rule, stated there as: a checklist that claims to
have verified something it has not is worse than no checklist.

THE ROW THAT DOES THE MOST WORK is `necessity`. An ad whose product appears
only in the SETTING - on the shelf, in a hand, on the counter - is an ad for
the category, and a competitor could run it unchanged. The product noun has to
appear in the route's DEVICE, which is the visual idea itself.

WHY DICTS AND NOT ad_lint's TUPLES. ad_lint.lint() returns
(key, label, passed, detail). These rows carry two more things - whether the
row was auto or manual, and a `state` so a manual row can render amber in
GateTree rather than red - and a fifth positional element would silently break
every existing unpacking of that shape. rows_for_gate() converts.

Standard library only. No API keys, no network.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_lint as al  # noqa: E402
import build_ad as ba  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_static_ad as bsa  # noqa: E402
import build_typography as bt  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "creative_direction_bank.json"

# Words that carry no meaning when asking "is the product in this device?".
# Deliberately short: a long stop list starts throwing away real product nouns
# ("pro", "one", "air" are all in product names).
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with",
    "from", "by", "is", "it", "its", "this", "that", "ml", "oz", "g", "kg",
    "pack", "bottle", "tube", "jar", "tin", "box",
}

MIN_WORDS = 4          # an insight or an idea shorter than this is a label
DISTINCT_BELOW = 0.6   # token overlap at or above this means idea == insight


def load_bank(path=None):
    with (Path(path) if path else BANK_PATH).open(encoding="utf-8") as fh:
        return json.load(fh)


def commands(bank):
    return bank.get("commands", [])


def routes(bank):
    return {k: v for k, v in bank.get("routes", {}).items() if k != "note"}


def tiers(bank):
    return {k: v for k, v in bank.get("tiers", {}).items() if k != "note"}


def cliches(bank):
    return list(bank.get("cliches", {}).get("terms", []))


def photo_tells(bank):
    return list(bank.get("product_photo_tells", {}).get("terms", []))


def _words(text):
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower())
            if w not in STOPWORDS and len(w) > 2]


def product_nouns(product):
    """The tokens that would prove the product is present, longest first.

    Longest first because a device naming the brand is stronger evidence than
    one naming the category: "lumawash" beats "shampoo", and reporting the
    better match makes the detail line more useful.
    """
    seen, out = set(), []
    for word in _words(product):
        if word.isdigit() or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return sorted(out, key=len, reverse=True)


def _overlap(left, right):
    a, b = set(_words(left)), set(_words(right))
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def route_text(route):
    return " ".join(str(route.get(field, ""))
                    for field in ("name", "rationale", "device"))


def idea_text(ad):
    """Everything a human wrote, which is what the cliche list is applied to.

    The composed PROMPTS are deliberately excluded: a prompt is generated from
    these words, so scanning both would report the same trope twice and make
    the count meaningless.
    """
    parts = [ad.get("insight", ""), ad.get("idea", "")]
    parts += [route_text(r) for r in ad.get("routes", [])]
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# The eight checkable commands
# --------------------------------------------------------------------------- #
def check_insight(bank, ad):
    text = (ad.get("insight") or "").strip()
    if not text:
        return False, "no insight written - start with what is true about the person"
    if len(text.split()) < MIN_WORDS:
        return False, "'{}' is a label, not an insight - write the sentence".format(text)

    vocab = ba.load_bank().get("emotions", {})
    features = al._matched(text, vocab.get("feature_words", []))
    feelings = al._has_any(text, vocab.get("feeling_words", []))
    if features and not feelings:
        return False, (
            "this is a product feature, not a human insight - it leads on '{}'. "
            "Say how it feels, not what it contains.".format(features[0]))
    return True, "reads as something true about the person, not about the product"


def check_idea(bank, ad):
    text = (ad.get("idea") or "").strip()
    insight = (ad.get("insight") or "").strip()
    if not text:
        return False, "no strategic idea - the insight is what is true, this is what you do about it"
    if len(text.split()) < MIN_WORDS:
        return False, "'{}' is a label, not an idea".format(text)
    if not insight:
        return True, "an idea is present (no insight to compare it against)"
    overlap = _overlap(text, insight)
    if overlap >= DISTINCT_BELOW:
        return False, (
            "the idea restates the insight ({:.0%} of the same words) - an "
            "observation is not an argument".format(overlap))
    return True, "materially different from the insight ({:.0%} shared)".format(overlap)


def check_necessity(bank, ad):
    product = ad.get("product") or ""
    nouns = product_nouns(product)
    if not nouns:
        return False, "no product named, so nothing can be shown to need it"
    hits = []
    for route in ad.get("routes", []):
        device = (route.get("device") or "").lower()
        found = [n for n in nouns if re.search(r"\b" + re.escape(n), device)]
        if found:
            hits.append("{} ({})".format(route.get("key", "?"), found[0]))
    if not hits:
        return False, (
            "the product appears in no route's device - looked for {}. An idea "
            "the product is merely present in is an ad for the category.".format(
                ", ".join(nouns[:3])))
    return True, "the product is load-bearing in: {}".format(", ".join(hits))


def check_fresh(bank, ad):
    text = idea_text(ad).lower()
    if not text.strip():
        return False, "nothing written to judge"
    hit, negated = rl.find_terms(text, cliches(bank))
    if hit:
        return False, "trades on a stock trope: {}".format(", ".join(sorted(set(hit))))
    if negated:
        return True, "no stock trope - and {} ruled out by name".format(
            ", ".join(sorted(set(negated))))
    return True, "no stock trope from the bank's list"


def check_hierarchy(bank, ad):
    typo = ad.get("typography") or {}
    if not typo:
        return False, "no type direction at all - a static ad is a photograph with words on it"
    missing = [name for name in ("zone", "reading_order") if not typo.get(name)]
    if missing:
        return False, "no {} - the eye needs somewhere to land and an order to travel".format(
            " and no ".join(m.replace("_", " ") for m in missing))
    try:
        _by_layer, warnings = bt.compose_typography(
            bt.load_bank(),
            dominance=typo.get("dominance"), ratio=typo.get("ratio"),
            zone=typo.get("zone"), lockup=typo.get("lockup"),
            reading_order=typo.get("reading_order"),
            restraint=typo.get("restraint", ()), headline=typo.get("headline"))
    except bt.TypographyError as exc:
        return False, str(exc)
    if warnings:
        return True, "hierarchy holds, with a note: {}".format(warnings[0])
    return True, "a zone, a reading order, and a dominance that agrees with its ratio"


def check_beyond(bank, ad):
    tells = photo_tells(bank)
    # Read the two existing modes from static_ad_bank rather than restating
    # them, so this check cannot drift away from what those modes really are.
    try:
        modes = bsa.modes(bsa.load_bank())
        mode_words = [cfg.get("label", "").lower() for cfg in modes.values()]
        mode_words += [key.lower() + " composite" for key in modes]
    except Exception:
        mode_words = []

    offenders = []
    for route in ad.get("routes", []):
        device = (route.get("device") or "").strip()
        if not device:
            offenders.append("{}: no device at all".format(route.get("key", "?")))
            continue
        hit, _negated = rl.find_terms(device.lower(), tells + mode_words)
        if hit:
            offenders.append("{}: {}".format(route.get("key", "?"), hit[0]))
    if offenders:
        return False, "still a product photograph - {}".format("; ".join(offenders))
    if not ad.get("routes"):
        return False, "no routes to judge"
    return True, "every device is an idea the product is in, not a photo of it"


def check_routes(bank, ad):
    entries = ad.get("routes", [])
    if len(entries) < 2:
        return False, (
            "{} route - one route is not a choice, it is the first thing you "
            "thought of".format(len(entries)) if entries else "no routes at all")
    known = routes(bank)
    unknown = [r.get("key") for r in entries if r.get("key") not in known]
    if unknown:
        return False, "unknown territory: {}. See --commands.".format(
            ", ".join(str(u) for u in unknown))
    distinct = {r.get("key") for r in entries}
    if len(distinct) < 2:
        return False, (
            "{} routes but all from the '{}' territory - that is one idea "
            "photographed twice".format(len(entries), list(distinct)[0]))
    return True, "{} routes across {} territories: {}".format(
        len(entries), len(distinct), ", ".join(sorted(distinct)))


def check_ready(bank, ad, others=None, ticked=()):
    """Derived: every auto row green, both manual rows ticked, every shot 8/8.

    This is the only row that can say "ready", and it cannot say it while a
    manual row is untouched. That is what stops the manual half being
    decoration.
    """
    failed = [row["label"] for row in (others or []) if not row["passed"]]
    if failed:
        return False, "not yet - {} still failing".format(", ".join(failed))

    manual = [c["key"] for c in commands(bank) if c.get("check") == "manual"]
    unticked = [k for k in manual if k not in ticked]
    if unticked:
        labels = [c["label"] for c in commands(bank) if c["key"] in unticked]
        return False, (
            "every checkable row passes; {} still yours to judge: {}".format(
                len(unticked), "; ".join(labels)))

    image_bank = bp.load_bank()
    bad = []
    for shot in ad.get("shots", []):
        present, _m, banned, _w, _n = rl.lint((shot.get("prompt") or "").lower(), image_bank)
        if len(present) != 8 or banned:
            bad.append("{} scores {}/8{}".format(
                shot.get("route", "?"), len(present),
                " with banned terms" if banned else ""))
    if bad:
        return False, "the idea is ready but the prompts are not: {}".format("; ".join(bad))
    return True, "campaign-ready: every row green, manual rows signed off, every route 8/8"


RULES = {
    "insight": check_insight,
    "idea": check_idea,
    "necessity": check_necessity,
    "fresh": check_fresh,
    "hierarchy": check_hierarchy,
    "beyond": check_beyond,
    "routes": check_routes,
}


def lint(bank, ad, ticked=()):
    """[{key, label, passed, detail, check, state}] - one row per command.

    `ready` is evaluated last and reads the rows above it, which is the only
    ordering dependency in here.
    """
    ticked = set(ticked or ())
    rows, auto_rows = [], []
    for command in commands(bank):
        key, label = command["key"], command["label"]
        if command.get("check") == "manual":
            done = key in ticked
            # `state` stays "warn" whether or not it is ticked, because it
            # describes the ROW, not the outcome: this one is asserted by a
            # person and was never verified by anything. Combined with
            # `passed`, GateTree then draws three distinct states - green for
            # a rule that checked something, amber for a human who signed it
            # off, red for nobody having judged it yet. Setting this to "pass"
            # when ticked collapsed the first two, and no row could ever be
            # amber at all.
            rows.append({
                "key": key, "label": label, "passed": done,
                "check": "manual", "state": "warn",
                "detail": (command["asks"] if not done
                           else "signed off by a human: " + command["asks"]),
            })
            continue
        if key == "ready":
            rows.append({"key": key, "label": label, "check": "auto",
                         "passed": None, "detail": "", "state": "pass"})
            continue
        rule = RULES.get(command.get("rule"))
        if rule is None:
            # An auto row this file cannot actually evaluate is downgraded to
            # manual rather than shown as checked-but-blank.
            rows.append({
                "key": key, "label": label, "passed": key in ticked,
                "check": "manual", "state": "warn",
                "detail": "no rule implemented for this row - yours to judge",
            })
            continue
        passed, detail = rule(bank, ad)
        row = {"key": key, "label": label, "passed": passed, "detail": detail,
               "check": "auto", "state": "pass" if passed else "fail"}
        rows.append(row)
        auto_rows.append(row)

    for row in rows:
        if row["passed"] is None:
            passed, detail = check_ready(bank, ad, auto_rows, ticked)
            row.update(passed=passed, detail=detail,
                       state="pass" if passed else "fail")
    return rows


def score(rows):
    return sum(1 for row in rows if row["passed"]), len(rows)


def rows_for_gate(rows):
    """GateTree's own shape - {key, label, passed, fix, ok_text, state}.

    A manual row passes as soon as it is ticked, and renders amber until then
    via GateTree's existing "state": "warn" support.
    """
    out = []
    for row in rows:
        out.append({
            "key": row["key"], "label": row["label"], "passed": bool(row["passed"]),
            "fix": row["detail"], "ok_text": row["detail"],
            "state": "warn" if (row["passed"] and row.get("state") == "warn") else None,
        })
    return out


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a static ad against the ten creative-direction commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--ad", help="path to a creative-ad JSON (see build_creative_ad.py)")
    p.add_argument("--ticked", default="",
                   help="comma-separated manual rows you have judged (e.g. direction,premium)")
    p.add_argument("--commands", action="store_true", help="print the ten commands and exit")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    bank = load_bank()

    if args.commands:
        for command in commands(bank):
            print("{:>2}. {:<34} [{}]".format(
                command["n"], command["label"], command.get("check", "auto")))
            print("    {}".format(command["asks"]))
        print()
        print("TERRITORIES")
        for key, cfg in routes(bank).items():
            print("  {:<26} {}".format(key, cfg["label"]))
            print("  {:<26} {}".format("", cfg["asks"]))
        return 0

    if not args.ad:
        sys.exit("Give --ad <path to a creative-ad JSON>, or --commands.")
    path = Path(args.ad)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Creative-ad file not found: {}".format(path))
    ad = json.loads(path.read_text(encoding="utf-8"))

    ticked = [t.strip() for t in args.ticked.split(",") if t.strip()]
    rows = lint(bank, ad, ticked)
    got, total = score(rows)
    for row in rows:
        mark = "PASS" if row["passed"] else ("TODO" if row["check"] == "manual" else "FAIL")
        print("{}  {:<34} {}".format(mark, row["label"], row["detail"]))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
