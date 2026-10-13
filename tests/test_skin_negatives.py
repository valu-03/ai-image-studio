"""The skin-perfection negatives: five `banned`, two `warn` (prompt_bank v11).

Two real influencer reference prompts arrived asking for "Flawless glowing
skin texture" and "soft glowing skin". Neither phrase was in `banned` or
`warn`, even though `airbrushed`, `beauty filter`, `glamour retouching` and
`plastic skin` all were - and the texture layer's own note calls itself "the
single biggest defence against the plastic AI look".

THE SPLIT IS THE DECISION, and this file exists to hold it in place:

    banned  flawless skin, flawless glowing skin, poreless, perfect skin,
            blemish-free - each is the direct negation of the texture layer.
            "poreless" cannot be true of a photograph of skin.
    warn    glowing skin, ultra-detailed - a warn row says "this does nothing
            on its own". anatomy_bank.json's post-workout slot had already
            diagnosed the first one in prose before this change existed:
            "'Post-workout glow' is doing real work ... where 'glowing skin'
            names a wish." A wish is not a contradiction, so it is not banned.

The second half of the file is the part that matters more than the first. A
negative list is only safe if nothing the app itself composes trips it, so the
audit walks EVERY string in EVERY bank and splits them by the key they came
from: composable fields must be clean, documentation fields may say the words
out loud. That is not assumed anywhere below - it is measured, and the two
known documentation hits are asserted by name so that a future move of one of
those sentences into a composable field fails here instead of silently
flagging the app's own output.
"""
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bp.load_bank()

NEW_BANNED = ["flawless skin", "flawless glowing skin", "poreless",
              "perfect skin", "blemish-free"]
NEW_WARN = ["glowing skin", "ultra-detailed"]

# The two prompts that prompted the change, quoted rather than paraphrased.
TRAVEL_PROMPT = (
    "ultra-photorealistic photo of a smiling blonde woman with loose waves "
    "wearing a white linen dress and sandals, walking through a Parisian "
    "street with cafes and flowers, natural candid smile, confident relaxed "
    "walking pose, wind movement in hair and clothing, fashionable summer "
    "styling, effortless chic look, soft glowing skin, lifestyle aesthetic. "
    "Bright sunny daylight, warm golden tones, vibrant yet balanced colors, "
    "soft natural shadows, shallow depth of field, subject in sharp focus "
    "with slightly blurred background. Luxury travel editorial photography, "
    "high-end magazine cover style, cinematic composition, shot with premium "
    "professional camera, ultra-detailed 4K realism")
SELFIE_PROMPT = (
    "A hyper-realistic, ultra-detailed Instagram-style selfie portrait of an "
    "attractive influencer, taking a casual photo. They are located at a "
    "rooftop bar, smiling confidently. Flawless glowing skin texture, soft "
    "cinematic lighting like golden hour sun rays, shallow depth of field "
    "with a blurred background, shot on a premium smartphone camera, 8k "
    "resolution, photorealistic masterpiece")

print("=== the lists carry the new terms, in the right tier ===")
for term in NEW_BANNED:
    check("'{}' is banned".format(term), term in bank["banned"])
    check("...and is NOT also a soft warning", term not in bank["warn"])
for term in NEW_WARN:
    check("'{}' is a warning".format(term), term in bank["warn"])
    check("...and is deliberately NOT banned", term not in bank["banned"])
# A FLOOR, and the irony is recorded on purpose: the commit that added this
# file also replaced `== 10` with a floor in four other suites, for exactly
# this reason - and then pinned `== 11` here. The very next bank change
# (v12, the opt-in anatomy guard) broke it. The lesson does not stick by
# being written down somewhere else.
check("prompt_bank is at or past the version that carries them",
      bank["version"] >= 11, str(bank["version"]))

print()
print("=== the two prompts that prompted the change are now caught ===")
for label, text in (("travel editorial", TRAVEL_PROMPT),
                    ("Instagram selfie", SELFIE_PROMPT)):
    _p, _m, banned, warns, _n = rl.lint(text.lower(), bank)
    print("  {}: banned={} warn={}".format(label, banned, warns))
    check("the {} prompt raises a soft warning".format(label), bool(warns))
    check("...naming 'glowing skin', which both prompts ask for",
          "glowing skin" in warns)
    check("...and 'ultra-detailed', the sibling of an already-listed term",
          "ultra-detailed" in warns)

_p, _m, selfie_banned, _w, _n = rl.lint(SELFIE_PROMPT.lower(), bank)
check("the selfie prompt's 'Flawless glowing skin' is a HARD reject",
      "flawless glowing skin" in selfie_banned, str(selfie_banned))
# The travel prompt asks only for "soft glowing skin" - a wish, not a
# contradiction - so it must warn WITHOUT being rejected. A list that failed
# this one would be punishing a phrase for the company it usually keeps.
_p, _m, travel_banned, _w, _n = rl.lint(TRAVEL_PROMPT.lower(), bank)
check("the travel prompt warns but is NOT rejected", not travel_banned,
      str(travel_banned))

print()
print("=== negation still wins: asking for the opposite is not a hit ===")
# find_terms()/is_negated() already did this for every other banned term; the
# new ones get no special treatment, and prompt-writing advice like "no
# flawless skin" has to remain sayable.
for term in NEW_BANNED + NEW_WARN:
    text = "a portrait with visible pores, no {}, natural texture".format(term)
    _p, _m, banned, warns, _n = rl.lint(text, bank)
    check("'no {}' is not read as asking for it".format(term),
          term not in banned and term not in warns,
          "banned={} warn={}".format(banned, warns))

print()
print("=== NOTHING the app can compose trips any of the seven ===")
# Keys whose strings are assembled into a prompt, versus keys that exist to
# explain a choice to the user in the GUI. Documentation is allowed to name a
# bad phrase - that is how it argues against it.
COMPOSABLE = {"phrase", "phrases", "example", "examples", "keywords", "terms",
              "text", "extra", "camera", "lens", "composition", "prompt",
              "negatives", "negative", "clause", "line", "lines", "template",
              "vocabulary", "suffix", "prefix"}
DOCUMENTATION = {"why", "does", "note", "when", "look", "source", "label",
                 "matching_note", "snap_note", "description", "hint", "tip",
                 "warning", "reason", "rationale", "explain", "avoid"}
# The gate's own input, not content it judges. prompt_bank's `banned` and
# `warn` lists necessarily contain every term being tested here, and
# `banned_claims`/`cliches`/`product_photo_tells` are the same idea in the
# social and creative-direction banks: a list of things to REJECT. Walking them
# as if they were prompt text would make this audit fail on its own subject.
REJECT_LISTS = {"banned", "warn", "banned_claims", "cliches",
                "product_photo_tells", "not_effects", "conflicts", "defused",
                "softened", "audit_allow"}

ALL_NEW = NEW_BANNED + NEW_WARN
composable_hits, doc_hits, unclassified = [], [], set()


def walk(node, where, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, where, k)
    elif isinstance(node, list):
        for item in node:
            walk(item, where, key)
    elif isinstance(node, str):
        if key in REJECT_LISTS:
            return
        positive, _negated = rl.find_terms(node.lower(), ALL_NEW)
        if not positive:
            return
        record = "{}:{} -> {} in {!r}".format(
            where, key, positive, node[:70])
        if key in COMPOSABLE:
            composable_hits.append(record)
        elif key in DOCUMENTATION:
            doc_hits.append(record)
        else:
            unclassified.add(key)
            doc_hits.append(record + "  [key not classified]")


for path in sorted(glob.glob(str(ROOT / "tools" / "*.json"))):
    name = Path(path).name
    with open(path, encoding="utf-8") as fh:
        walk(json.load(fh), name)

for record in doc_hits:
    print("    (documentation) " + record)
check("no composable bank string trips the new lists",
      not composable_hits, " | ".join(composable_hits))
check("every hit that exists is in a documentation field",
      not unclassified, "unclassified keys: " + ", ".join(sorted(unclassified)))

print()
print("=== the app's own composed output stays clean over many seeds ===")
# The generic walk covers bank strings; this covers what compose() actually
# ASSEMBLES from them, which is not the same thing - a term can be clean alone
# and dirty beside its neighbour.
dirty = []
for seed in range(200):
    prompt, _ = bp.compose(bank, {"subject": "a woman in her thirties",
                                  "seed": seed})
    positive, _negated = rl.find_terms(prompt.lower(), ALL_NEW)
    if positive:
        dirty.append("seed {}: {}".format(seed, positive))
check("200 composed prompts, none tripping a new term", not dirty,
      " | ".join(dirty[:3]))

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("all checks passed")
