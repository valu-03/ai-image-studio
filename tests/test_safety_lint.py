"""tools/safety_lint.py - the app's first CONTENT gate.

Every other linter here judges how an image is made. This one judges what it
depicts, which makes it the one linter that can do real damage by being wrong
in either direction: too loose and it is decoration, too tight and it fails
clean photoreal work for words the photographer put there.

The check that matters most in this file is the collision audit at the bottom.
It asserts that no safety term fires on any phrase this app already ships -
run PER PHRASE, never against a joined string, because joining invents
adjacencies no real prompt has. Three real collisions were found by running it
the first time: "crushing" in camera_angle_bank, "squash and stretch" in
story_bank's stylised style, and "slap"/"smacked" in sound_bank's own comedy
examples. Without this, adding "crush" or "razor" to a category later would
silently start failing prompts that score 8/8.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_story as bs  # noqa: E402
import safety_lint as sfl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = sfl.load_bank()


def scan(text):
    return sfl.scan_field(bank, text)


print("=== the bank is well-formed ===")
check("four checks", len(sfl.CHECKS) == 4, str([k for k, _l, _f in sfl.CHECKS]))
check("three negative categories", len(bank["categories"]) == 3, str(list(bank["categories"])))
for key, cfg in bank["categories"].items():
    check("'{}' has stems or words".format(key), bool(cfg.get("stems") or cfg.get("words")))
    check("'{}' has a fix line".format(key), bool(cfg.get("fix")))
check("the softener rule has both halves",
      bool(bank["softened"].get("contact_stems")) and bool(bank["softened"].get("softeners")))
check("the source names itself as written, not transcribed",
      "NOT transcribed" in bank["source"] or "Written for this app" in bank["source"])

print()
print("=== stems match inflections; words do not over-match ===")
# The whole reason for two lists. Start-anchoring "pain" fires on "a painted
# wall"; whole-wording "swat" misses "swatting".
check("'claw' catches 'clawing'", "injury" in scan("clawing at the sofa"))
check("'claw' catches 'claws'", "injury" in scan("claws out"))
check("'pain' does NOT fire on 'a painted wall'", not scan("a painted wall behind a rug"))
check("'bite' catches 'biting'", "injury" in scan("biting the other cat"))
check("'swat' catches 'swatting'",
      bool(sfl.contact_unsoftened(bank, "swatting the kitten off the table")))
check("'shove' catches 'shoving'", bool(sfl.contact_unsoftened(bank, "shoving him aside")))

print()
print("=== negation reads as safe, in both directions ===")
# Backwards: realism_lint.is_negated, imported rather than re-implemented.
for phrase in ("no claws", "without claws", "never any claws", "no pain at all"):
    check("prefix negation: {!r}".format(phrase), not scan(phrase))
# Forwards: is_negated is a PREFIX rule, so these need the `defused` list.
for phrase in ("claws sheathed", "claws retracted", "clawless"):
    check("post-modified: {!r}".format(phrase), not scan(phrase), str(scan(phrase)))
check("but bare claws are still caught", "injury" in scan("claws out and hissing"))

print()
print("=== the softener rule: the one POSITIVE check ===")
check("soft contact passes",
      not sfl.contact_unsoftened(bank, "a soft cartoon-like paw tap, claws in"))
check("gentle contact passes", not sfl.contact_unsoftened(bank, "a gentle bop on the head"))
check("bare contact fails", bool(sfl.contact_unsoftened(bank, "a swat to the shoulder")))

results = {key: (passed, detail) for key, _label, passed, detail
           in sfl.lint(bank, [{"action": "sitting quietly on a rug"}])}
check("nothing making contact passes trivially, and says so",
      results["softened"][0] and "nothing makes contact" in results["softened"][1],
      results["softened"][1])

print()
print("=== scope: staging fields only for the softener rule ===")
# The source brief's own punchline caption is literally "bap bap!". A caption
# is read by a viewer, never executed by a model.
caption_only = [{"caption": "Bap.", "action": "sitting bolt upright with paws tucked"}]
results = {key: passed for key, _l, passed, _d in sfl.lint(bank, caption_only)}
check("a contact word in a CAPTION does not fail the softener rule", results["softened"])
staging = [{"caption": "Bap.", "action": "swatting him off the table"}]
results = {key: passed for key, _l, passed, _d in sfl.lint(bank, staging)}
check("the same word in an ACTION does fail it", not results["softened"])
# But injury/distress/hazard still scan everything, captions included.
results = {key: passed for key, _l, passed, _d
           in sfl.lint(bank, [{"caption": "he was bleeding everywhere"}])}
check("injury IS still caught in a caption", not results["injury"])

print()
print("=== hazards and distress ===")
for text, key in (("batting a knife off the counter", "hazard"),
                  ("jumping from the balcony rail", "hazard"),
                  ("sniffing an open bottle of bleach", "hazard"),
                  ("cowering under the sofa, trembling", "distress"),
                  ("being punished for it", "distress")):
    check("{!r} -> {}".format(text[:34], key), key in scan(text), str(scan(text)))

print()
print("=== a composed prompt is NOT what this scans ===")
# Rule 1 in the module docstring, asserted rather than trusted. A full photoreal
# prompt is stuffed with words that read as violent out of context.
import build_prompt as bp  # noqa: E402

image_bank = bp.load_bank()
prompt, _layers = bp.compose(image_bank, {
    "subject": "a grey tabby cat", "action": "sitting on a rug",
    "setting": "a bright living room", "seed": 2})
check("AUTHORED_FIELDS does not include the composed prompt",
      "prompt" not in sfl.AUTHORED_FIELDS)
check("STAGING_FIELDS is a subset of AUTHORED_FIELDS",
      set(sfl.STAGING_FIELDS) <= set(sfl.AUTHORED_FIELDS))
# _fields_of prefixes a spec field with "spec." so a failure can name where it
# came from, so the membership test is against the suffix.
seen = [name.split(".")[-1]
        for name, _text in sfl._fields_of({"spec": {"subject": "x"}, "caption": "y"})]
check("a scene dict exposes only authored text to the scanner",
      seen and all(name in sfl.AUTHORED_FIELDS for name in seen), str(seen))

print()
print("=== THE COLLISION AUDIT: no safety term fires on shipped vocabulary ===")
clashes = sfl.audit_banks(bank)
check("zero unreviewed collisions across every shipped bank", not clashes,
      "; ".join("{} {!r} <- {}".format(n, p[:40], t) for n, p, _k, t in clashes[:3]))
allow = bank.get("audit_allow", {}).get("allow", [])
check("every allowlisted collision states why", all(row.get("why") for row in allow),
      str(len(allow)))
check("the allowlist is small enough to have been read", len(allow) <= 12, str(len(allow)))

# And the audit must actually be capable of failing, or it proves nothing.
poisoned = dict(bank)
poisoned["categories"] = dict(bank["categories"])
poisoned["categories"]["injury"] = dict(bank["categories"]["injury"])
poisoned["categories"]["injury"]["stems"] = list(
    bank["categories"]["injury"]["stems"]) + ["crush"]
check("the audit CATCHES a term that collides ('crush' is in camera_angle_bank)",
      bool(sfl.audit_banks(poisoned)), str(len(sfl.audit_banks(poisoned))))

print()
print("=== it is opt-in, and the old formats are provably untouched ===")
story_bank = bs.load_bank()
for fmt in ("story", "trade"):
    checks = bs.format_cfg(story_bank, fmt).get("checks", [])
    check("'{}' does not run the safety gate".format(fmt), "safety" not in checks)
check("'sitcom' does", "safety" in bs.format_cfg(story_bank, "sitcom").get("checks", []))
# trade's own shipped mishap would fail the softener rule - which is exactly
# why widening this gate to a format written before it would be a nuisance.
mishaps = [m for cfg in bs.trades(story_bank).values() for m in cfg.get("mishaps", [])]
tripped = [m for m in mishaps if sfl.contact_unsoftened(bank, m)]
check("and trade's own vocabulary would indeed trip it", bool(tripped),
      repr(tripped[0][:50]) if tripped else "none")

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL SAFETY LINT CHECKS PASSED")

sys.exit(1 if fails else 0)
