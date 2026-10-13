"""tools/evidence_bank.json + build_evidence.py - lived-in details with a cause.

What has to hold for this to be safe to put in every prompt:
  * no phrase carries a banned or warn term, or a negation that would make
    realism_lint discount a keyword next to it;
  * the builder trims to three, never more, and order of selection never
    changes the output;
  * adding evidence to a spec NEVER lowers its realism score - it rides the
    free tail as a non-layer override, so it can only add words;
  * subject_kind() reads the subject the way a person would: the earliest
    match wins, whole words only.

Standard library only, no network, no Qt.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_evidence as bev  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bev.load_bank()
IMAGE_BANK = bp.load_bank()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def all_options():
    for kind, cfg in BANK["kinds"].items():
        for key, option in cfg["options"].items():
            yield kind, key, option


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()) is not None


def score(prompt):
    present = rl.lint(prompt, IMAGE_BANK)[0]
    return len(present)


print("=== THE BANK'S SHAPE ===")
check("it declares a version", isinstance(BANK.get("version"), int))
check("it says plainly that it is not course material",
      "NOT AI Video Bootcamp" in BANK.get("source", ""))
check("four kinds: human, animal, object, place",
      sorted(BANK["kinds"]) == sorted(bev.KINDS), str(sorted(BANK["kinds"])))
check("every option has a label, a cause, a phrase and a note",
      all({"label", "cause", "phrase", "note"} <= set(o) for _k, _key, o in all_options()))
check("every kind offers at least auto_count + 2 details",
      all(len(cfg["options"]) >= BANK["auto_count"] + 2 for cfg in BANK["kinds"].values()))
check("no phrase ends in a full stop (build_compact comma-joins them)",
      not [key for _k, key, o in all_options() if o["phrase"].rstrip().endswith(".")])

print()
print("=== EVERY PHRASE IS SAFE TO ADD TO ANY PROMPT ===")
banned = [key for _k, key, o in all_options()
          if any(has_term(o["phrase"], t) for t in IMAGE_BANK["banned"])]
check("no phrase uses a banned term", not banned, str(banned))
warned = [key for _k, key, o in all_options()
          if any(has_term(o["phrase"], t) for t in IMAGE_BANK["warn"])]
check("no phrase uses a warn term", not warned, str(warned))
negated = [key for _k, key, o in all_options()
           if re.search(r"\b(no|not|never|without|avoid)\b", o["phrase"].lower())]
check("no phrase is written as a refusal (is_negated would discount it)", not negated, str(negated))

print()
print("=== THE BUILDER ===")
phrase, warnings = bev.compose_evidence(BANK, "human", ["sunglasses-dent", "hair-tie"])
check("two picks compose to both phrases", "sunglasses" in phrase and "hair tie" in phrase, phrase)
check("two picks raise no warning", not warnings, str(warnings))
forward = bev.compose_evidence(BANK, "object", ["thumbprint", "water-ring"])[0]
backward = bev.compose_evidence(BANK, "object", ["water-ring", "thumbprint"])[0]
check("selection order does not change the output", forward == backward)
phrase, warnings = bev.compose_evidence(
    BANK, "object", ["thumbprint", "water-ring", "label-lift", "dust-edges"])
check("four picks are trimmed to three", phrase.count(", ") == 2 and len(warnings) == 1, phrase)
phrase, warnings = bev.compose_evidence(
    BANK, "object", ["thumbprint", "water-ring", "label-lift"], custom="a price sticker half peeled off")
check("custom text counts toward the cap and is always kept",
      "price sticker" in phrase and phrase.count(", ") == 2 and warnings, phrase)
check("custom text alone composes",
      bev.compose_evidence(BANK, "place", custom="a coat left on the chair")[0] == "a coat left on the chair")
check("auto mode picks auto_count details",
      bev.compose_evidence(BANK, "animal", seed=3)[0].count(", ") == BANK["auto_count"] - 1)
check("auto mode is reproducible by seed",
      bev.compose_evidence(BANK, "human", seed=7) == bev.compose_evidence(BANK, "human", seed=7))
distinct = {bev.compose_evidence(BANK, "human", seed=s)[0] for s in range(12)}
check("different seeds draw different details", len(distinct) > 3, str(len(distinct)))
for bad_call, label in (
        (lambda: bev.compose_evidence(BANK, "robot", ["x"]), "an unknown kind"),
        (lambda: bev.compose_evidence(BANK, "human", ["thumbprint"]), "another kind's detail"),
        (lambda: bev.compose_evidence(BANK, "human"), "nothing at all and no seed")):
    try:
        bad_call()
        check("refuses " + label, False)
    except bev.EvidenceError:
        check("refuses " + label, True)

print()
print("=== SUBJECT KIND ===")
for subject, kind in (
        ("a woman in her thirties with freckles", "human"),
        ("a ginger tabby cat on a windowsill", "animal"),
        ("a cat asleep on her lap", "animal"),
        ("a woman holding her cat", "human"),
        ("a golden retriever puppy", "animal"),
        ("a 250ml amber shampoo bottle on marble", "object"),
        ("a quiet kitchen at dawn", "place"),
        ("a chubby ginger street cat", "animal"),
        ("a kitchen with a cat asleep on the counter", "animal"),
        ("a beach dog shaking off water", "animal"),
        ("a cafe barista pouring milk", "human"),
        ("the theme of the shot", "object")):
    check("'{}' is {}".format(subject, kind), bev.subject_kind(BANK, subject) == kind,
          bev.subject_kind(BANK, subject))

print()
print("=== ADDING EVIDENCE NEVER LOWERS A SCORE ===")
lowered = []
for seed in range(40):
    for subject, kind in (("a woman in her thirties", "human"), ("a ginger tabby cat", "animal"),
                          ("an amber glass bottle", "object")):
        spec = {"subject": subject, "seed": seed, "shot": "portrait"}
        before = score(bp.compose(IMAGE_BANK, spec)[0])
        with_evidence = dict(spec, overrides={"evidence": [bev.compose_evidence(BANK, kind, seed=seed)[0]]})
        prompt = bp.compose(IMAGE_BANK, with_evidence)[0]
        if score(prompt) < before:
            lowered.append((subject, seed))
check("120 specs: evidence never costs a layer", not lowered, str(lowered[:5]))
spec = {"subject": "a woman in her thirties", "seed": 0,
        "overrides": {"evidence": [bev.compose_evidence(BANK, "human", ["hair-tie"])[0]]}}
check("the phrase actually reaches the prompt", "hair tie" in bp.compose(IMAGE_BANK, spec)[0])

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL EVIDENCE BANK CHECKS PASSED")
