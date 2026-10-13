"""contact_bank.json + material_bank.json + build_prompt.apply_physical.

What has to hold:

  * every phrase is safe - nothing banned or warned, nothing an animal prompt
    bans, no refusal wording, no trailing full stop;
  * contact follows the text: the support and action named, earliest first,
    only phrases for the subject's kind, a default when nothing matched,
    nothing at all for a place;
  * materials follow the text, excludes apply (iced coffee never steams),
    no match gives nothing, and colour words do not read as fruit;
  * Lighting's generic "material response" sentence is replaced only when
    specific materials were found;
  * a spec WITHOUT the flags composes byte-for-byte as before;
  * the flags never lower a realism score and keep 8/8;
  * an explicit override wins; neither flag is something a model can set;
  * the two CLIs run.

Standard library only, no network, no Qt.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import brief  # noqa: E402
import build_contact as bct  # noqa: E402
import build_material as bmt  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

CONTACT = bct.load_bank()
MATERIAL = bmt.load_bank()
IMAGE_BANK = bp.load_bank()
KINDS = ("human", "animal", "object")

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()) is not None


def every_phrase():
    for table in ("supports", "actions"):
        for cfg in CONTACT[table].values():
            yield from (cfg[k] for k in KINDS if cfg.get(k))
    for phrases in CONTACT["by_kind"].values():
        yield from phrases
    for cfg in MATERIAL["materials"].values():
        yield cfg["phrase"]


def contact(**spec):
    return bct.read_contact(CONTACT, spec)


def materials(**spec):
    return bmt.read_materials(MATERIAL, spec)


print("=== PHRASES ARE SAFE ===")
phrases = list(every_phrase())
bad = [p for p in phrases if any(has_term(p, t) for t in IMAGE_BANK["banned"] + IMAGE_BANK["warn"])]
check("no banned or warn term", not bad, str(bad[:2]))
animal_phrases = [cfg["animal"] for t in ("supports", "actions") for cfg in CONTACT[t].values()
                  if cfg.get("animal")] + CONTACT["by_kind"]["animal"] + \
                 [cfg["phrase"] for cfg in MATERIAL["materials"].values()]
animal_bad = [p for p in animal_phrases if any(has_term(p, t) for t in rl.ANIMAL_BANNED)]
check("nothing an animal prompt bans", not animal_bad, str(animal_bad[:2]))
negated = [p for p in phrases if re.search(r"\b(no|not|never|without|avoid)\b", p.lower())]
check("no phrase is written as a refusal", not negated, str(negated[:2]))
check("no phrase ends in a full stop", not [p for p in phrases if p.rstrip().endswith(".")])
check("both banks say plainly they are not course material",
      "NOT AI Video Bootcamp" in CONTACT["source"] and "NOT AI Video Bootcamp" in MATERIAL["source"])
check("every excludes key is a real material",
      all(x in MATERIAL["materials"] for c in MATERIAL["materials"].values() for x in c.get("excludes", [])))
check("a place has no contact defaults", CONTACT["by_kind"]["place"] == [])

print()
print("=== CONTACT FOLLOWS THE TEXT ===")
_p, keys = contact(subject="a woman in her thirties", action="sitting on a sofa holding a coffee mug")
check("a woman sitting on a sofa holding a mug: sitting, then sofa (earliest first, max 2)",
      keys == ["sitting", "sofa"], str(keys))
_p, keys = contact(subject="a woman", action="on a sofa holding a mug")
check("...on a sofa holding a mug: sofa, then holding", keys == ["sofa", "holding"], str(keys))
phrase, keys = contact(subject="a ginger cat", setting="asleep on a duvet")
check("a cat asleep on a duvet gets the animal phrases",
      keys == ["lying", "bed"] and "fur" in phrase and "skin" not in phrase, phrase)
phrase, keys = contact(subject="a perfume bottle", setting="on a marble table")
check("a bottle on a table gets the OBJECT table phrase, never forearms",
      keys == ["table"] and "forearms" not in phrase, phrase)
_p, keys = contact(subject="a cat held by a woman")
check("an action with no phrase for the kind is skipped (a cat is not 'holding')",
      "holding" not in keys, str(keys))
phrase, keys = contact(subject="a man in his forties", seed=3)
check("nothing matched: one default for the kind, no keys",
      not keys and phrase in CONTACT["by_kind"]["human"], phrase)
check("the default is reproducible by seed",
      contact(subject="a man", seed=3) == contact(subject="a man", seed=3))
check("...and seeds differ", len({contact(subject="a man", seed=s)[0] for s in range(20)}) > 1)
check("a place gets nothing", contact(subject="a quiet street at night") == ("", []))
check("whole words only: 'embedded' is not a bed, 'depth of field' not grass",
      contact(subject="a woman", setting="embedded lights, shallow depth of field")[1] == [])

print()
print("=== MATERIALS FOLLOW THE TEXT ===")
_p, keys = materials(subject="a woman holding a coffee mug", wardrobe="a wool sweater")
check("a mug of coffee and a wool sweater: the first two named", keys == ["coffee", "ceramic"], str(keys))
_p, keys = materials(subject="a woman", wardrobe="a wool sweater and denim jeans")
check("wardrobe is read: knit, denim", keys == ["knit", "denim"], str(keys))
_p, keys = materials(subject="a perfume bottle", setting="on a marble counter")
check("a perfume bottle on marble: glass, stone", keys == ["glass", "stone"], str(keys))
phrase, keys = materials(subject="an iced coffee")
check("iced coffee gets condensation and never rising steam",
      keys == ["cold_drink"] and "steam" not in phrase, str(keys))
check("ice cream is not a cold drink", materials(subject="a scoop of ice cream")[1] == ["ice_cream"])
check("colour words are not fruit or jewellery",
      materials(subject="an orange cat", setting="a field at golden hour")[1] == [])
check("no material named: nothing", materials(subject="a man", setting="a park") == ("", []))
check("at most max_phrases", all(
    len(materials(subject="glass, steel, wool, silk, bread and cheese")[1]) <= MATERIAL["max_phrases"]
    for _ in [0]))

print()
print("=== IN A REAL PROMPT ===")
base = {"subject": "a woman in her thirties", "action": "sitting on a sofa holding a coffee mug",
        "wardrobe": "a wool sweater", "seed": 2}
before = bp.compose(IMAGE_BANK, base)[0]
check("without the flags the prompt is byte-for-byte unchanged",
      before == bp.compose(IMAGE_BANK, dict(base, contact_detail=False, material_detail=False))[0])
flagged = bp.compose(IMAGE_BANK, dict(base, contact_detail=True, material_detail=True))[0]
check("with the flags the contact lines are in", "clothing creasing at the hips" in flagged)
check("...and the material lines", "curl of steam rising off the coffee" in flagged)
check("added to the tail, before the negatives",
      flagged.index("curl of steam") < flagged.index("no cartoon style"))
explicit = dict(base, contact_detail=True, overrides={"contact": ["my own weight cue"]})
check("an explicit contact override wins",
      "my own weight cue" in bp.compose(IMAGE_BANK, explicit)[0]
      and "clothing creasing" not in bp.compose(IMAGE_BANK, explicit)[0])

generic = bmt.generic_phrase(MATERIAL)
check("the generic Lighting sentence is found in lighting_bank.json", generic.startswith("distinct material"))
lit = dict(base, material_detail=True, overrides={"lighting": ["soft window light, " + generic,
                                                               "realistic shadows"]})
prompt = bp.compose(IMAGE_BANK, lit)[0]
check("materials found: the generic sentence is replaced", generic not in prompt and "curl of steam" in prompt)
check("...and the rest of the lighting choice is kept", "soft window light" in prompt)
plain_lit = dict(lit, subject="a man", action="", wardrobe="")
check("no materials found: the generic sentence stays", generic in bp.compose(IMAGE_BANK, plain_lit)[0])
only = dict(base, material_detail=True, overrides={"lighting": [generic]})
check("a lighting choice that was ONLY the generic sentence hands the layer back to the bank",
      generic not in bp.compose(IMAGE_BANK, only)[0])
check("bmt.without_generic leaves text without it alone",
      bmt.without_generic("soft window light", generic) == "soft window light")

lowered = []
specs = (
    {"subject": "a woman in her thirties", "action": "lying on a bed reading a book"},
    {"subject": "a ginger tabby cat", "setting": "curled up on a wool blanket"},
    {"subject": "a man", "action": "leaning on a wall", "wardrobe": "a leather jacket and jeans"},
    {"subject": "a perfume bottle", "setting": "on a marble counter"},
    {"subject": "a pizza", "setting": "on a wooden table"},
    {"subject": "an empty street at night", "setting": "wet with rain"},
)
for seed in range(15):
    for spec in specs:
        spec = dict(spec, seed=seed)
        kind = "animal" if "cat" in spec["subject"] else "human"
        # Banned terms already in the plain prompt (the image bank's own skin
        # vocabulary on a cat) are not this feature's to fix - only ADDED ones count.
        b_present, _m, b_banned, _w, _n = rl.lint(bp.compose(IMAGE_BANK, spec)[0], IMAGE_BANK, kind=kind)
        present, _m, banned, _w, _n = rl.lint(
            bp.compose(IMAGE_BANK, dict(spec, contact_detail=True, material_detail=True))[0],
            IMAGE_BANK, kind=kind)
        added = set(banned) - set(b_banned)
        if len(present) < len(b_present) or added:
            lowered.append((spec["subject"], seed, len(b_present), len(present), added))
check("90 specs: the flags never lower a realism score or add a banned term",
      not lowered, str(lowered[:3]))
check("neither flag is something a model can set",
      "contact_detail" not in brief.SPEC_KEYS and "material_detail" not in brief.SPEC_KEYS)

print()
print("=== CLI ===")
run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_contact.py"), "--subject", "a cat",
                      "--setting", "asleep on a duvet"], capture_output=True, text=True)
check("build_contact.py prints the phrase", run.returncode == 0 and "bedding" in run.stdout, run.stderr)
run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_material.py"), "--subject",
                      "a glass of iced lemonade"], capture_output=True, text=True)
check("build_material.py prints the phrase", run.returncode == 0 and "condensation" in run.stdout,
      run.stderr)
run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_material.py"), "--list"],
                     capture_output=True, text=True)
check("--list works", run.returncode == 0 and "ice_cream" in run.stdout)

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL PHYSICAL REALISM CHECKS PASSED")
