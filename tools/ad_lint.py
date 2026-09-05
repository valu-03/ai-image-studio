"""Score a UGC ad against the workflow checklist and the five-beat structure.

Usage:
    python tools/ad_lint.py --ad temp/outputs/ads/lumawash.json
    python tools/ad_lint.py --ad x.json --platform tiktok --seconds 20

Exit code 0 when the ad passes every check; 1 otherwise, so a workflow step can
gate on it - the same contract as realism_lint.py and motion_lint.py.

Two checks are subtler than they look.

**The emotion check is scoped to beats 1-3.** Beat 4 is where naming the
mechanism is correct: "zero sulfates, zero harsh chemicals" is exactly what that
beat is for. "Sell the feeling" governs how an ad opens and frames itself, not
how it describes the product once it has earned the right to. A linter that
flagged beat 4 for saying what the product contains would be wrong.

**Beat 5 is two requirements.** Social proof and urgency are separate, and an ad
with proof but no reason to act now is the common failure - it reads finished.

Standard library only. No API keys, no network.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_ad as ba  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _has_any(text, words):
    """True when any word appears, respecting word boundaries for short tokens."""
    lower = (text or "").lower()
    for word in words:
        if " " in word or len(word) > 4:
            if word in lower:
                return True
        elif re.search(r"\b" + re.escape(word) + r"\b", lower):
            return True
    return False


def _matched(text, words):
    lower = (text or "").lower()
    return [w for w in words if w in lower]


def check_beats(bank, shots):
    """All five, in order."""
    expected = [b["key"] for b in ba.beats(bank)]
    actual = [s["key"] for s in shots]
    if actual == expected:
        return True, "all five beats, in order"
    missing = [k for k in expected if k not in actual]
    if missing:
        return False, "missing beat(s): {}".format(", ".join(missing))
    return False, "beats are out of order: {}".format(" -> ".join(actual))


def check_product_timing(bank, shots, seconds):
    """The checklist's own question: product or offer within 5-10 seconds."""
    timing = bank.get("timing", {})
    limit = timing.get("product_by", 10.0)
    solution = next((s for s in shots if s["key"] == "solution"), None)
    if solution is None:
        return False, "there is no product beat at all"
    start = solution["start"]
    if start <= limit:
        return True, "product appears at {:.1f}s".format(start)
    return False, (
        "product appears at {:.1f}s - the checklist wants it by {:.0f}s. "
        "Shorten beats 1-3 or the ad.".format(start, limit))


def check_hook(bank, shots, platform):
    """Beat 1 must exist, carry words, and fit the platform's hook window."""
    cfg = ba.platforms(bank).get(platform, {})
    window = cfg.get("hook_seconds", 3)
    first = shots[0] if shots else None
    if first is None or not (first.get("copy") or "").strip():
        return False, "beat 1 has no hook line - this is the only thing that stops a scroll"
    if first["duration"] > window + 0.05:
        return False, "the hook runs {:.1f}s; {} wants it inside {}s".format(
            first["duration"], cfg.get("label", platform), window)
    return True, "hook lands in {:.1f}s".format(first["duration"])


def check_first_clip(bank, shots, platform):
    """A slow opening shot is where viewers leave."""
    cfg = ba.platforms(bank).get(platform, {})
    limit = cfg.get("first_clip_seconds", 3)
    if not shots:
        return False, "no shots"
    duration = shots[0]["duration"]
    if duration <= limit + 0.05:
        return True, "first clip {:.1f}s".format(duration)
    return False, "first clip is {:.1f}s; keep it under {}s".format(duration, limit)


def check_emotion(bank, shots):
    """Beats 1-3 open on feeling. Beat 4 is exempt - see the module docstring."""
    vocab = bank.get("emotions", {})
    features = vocab.get("feature_words", [])
    feelings = vocab.get("feeling_words", [])

    offenders, felt = [], 0
    for shot in shots:
        if shot.get("sells") != "feeling":
            continue
        copy = shot.get("copy") or ""
        if not copy.strip():
            continue
        hits = _matched(copy, features)
        if hits and not _has_any(copy, feelings):
            offenders.append("beat {} ({})".format(shot["n"], hits[0]))
        if _has_any(copy, feelings):
            felt += 1

    if offenders:
        return False, (
            "{} open on specifications. Say how it feels, not what it contains "
            "- beat 4 is where the mechanism belongs.".format(", ".join(offenders)))
    if not felt:
        return False, "beats 1-3 carry no copy to judge - write the pain in the viewer's words"
    return True, "beats 1-3 speak to the viewer, not the spec sheet"


# "Over 10,000 women swear by it" is social proof with no proof *word* in it.
# A quantity IS the evidence, and it is the most common form the beat takes, so
# a number of three or more digits counts on its own. Found by a live model
# reply that the word list alone wrongly rejected.
NUMERIC_PROOF = re.compile(
    r"\b\d{1,3}(?:[,.]\d{3})+\b|\b\d{3,}\b|\b\d+\s?(?:k|m|million|thousand)\b",
    re.IGNORECASE)


def has_proof(bank, text):
    return _has_any(text, bank.get("proof_words", [])) or bool(NUMERIC_PROOF.search(text or ""))


def check_proof_and_urgency(bank, shots):
    """Beat 5 is two requirements, and the missing half is usually urgency."""
    proof_shot = next((s for s in shots if s["key"] == "proof"), None)
    if proof_shot is None:
        return False, "there is no proof beat"
    copy = proof_shot.get("copy") or ""
    if not copy.strip():
        return False, "beat 5 has no copy - it needs social proof AND a reason to act now"
    proof = has_proof(bank, copy)
    has_urgency = _has_any(copy, bank.get("urgency_words", []))
    if proof and has_urgency:
        return True, "proof and urgency both present"
    if proof:
        return False, ("beat 5 has proof but no urgency - add a deadline or an offer. "
                       "This is the common one: it reads finished without it.")
    if has_urgency:
        return False, "beat 5 has urgency but no proof - add numbers, reviews or customers"
    return False, "beat 5 has neither proof nor urgency"


def check_cta(bank, shots):
    """A CTA somewhere in the ad, spoken or on screen."""
    joined = " ".join((s.get("copy") or "") for s in shots)
    if _has_any(joined, bank.get("cta_words", [])):
        return True, "a call to action is present"
    return False, "no call to action - say what you want them to do"


def check_aspect(bank, shots, platform):
    cfg = ba.platforms(bank).get(platform, {})
    wanted = cfg.get("aspect")
    actual = {s["spec"].get("aspect") for s in shots if s.get("spec")}
    if not wanted:
        return True, "no aspect requirement"
    if actual == {wanted}:
        return True, "{} throughout".format(wanted)
    return False, "{} wants {}; shots carry {}".format(
        cfg.get("label", platform), wanted, ", ".join(sorted(str(a) for a in actual)))


def check_length(bank, platform, seconds):
    error = ba.validate_length(bank, platform, seconds)
    if error:
        return False, error
    return True, "{}s is inside the platform's range".format(seconds)


CHECKS = [
    ("beats", "Five-beat structure", check_beats),
    ("product_by_10s", "Product within 5-10s", check_product_timing),
    ("hook", "Hook", check_hook),
    ("first_clip", "First clip", check_first_clip),
    ("emotion", "Sells the feeling (beats 1-3)", check_emotion),
    ("proof", "Proof and urgency", check_proof_and_urgency),
    ("cta", "Call to action", check_cta),
    ("aspect", "Aspect ratio", check_aspect),
    ("length", "Ad length", check_length),
]


def lint(bank, shots, platform, seconds):
    """[(key, label, passed, detail)] - one row per check."""
    results = []
    for key, label, fn in CHECKS:
        if key == "beats":
            passed, detail = fn(bank, shots)
        elif key == "product_by_10s":
            passed, detail = fn(bank, shots, seconds)
        elif key in ("hook", "first_clip", "aspect"):
            passed, detail = fn(bank, shots, platform)
        elif key == "length":
            passed, detail = fn(bank, platform, seconds)
        else:
            passed, detail = fn(bank, shots)
        results.append((key, label, passed, detail))
    return results


def score(results):
    return sum(1 for _, _, passed, _ in results if passed), len(results)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a UGC ad against the checklist and the five-beat structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--ad", required=True, help="path to an ad JSON (shots + platform + seconds)")
    p.add_argument("--platform", help="override the platform recorded in the file")
    p.add_argument("--seconds", type=int, help="override the length recorded in the file")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    path = Path(args.ad)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit("Ad file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))

    bank = ba.load_bank()
    platform = args.platform or data.get("platform", "tiktok")
    seconds = args.seconds or data.get("seconds") or ba.default_length(bank, platform)
    shots = data.get("shots", [])

    results = lint(bank, shots, platform, seconds)
    got, total = score(results)
    for _, label, passed, detail in results:
        print("{}  {:<32} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
