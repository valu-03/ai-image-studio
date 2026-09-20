"""Gate what a scene DEPICTS, not how it is rendered.

The app's first content check. Every other linter here judges how an image is
made - realism_lint scores eight photorealism layers, motion_lint scores camera
craft, story_lint scores structure and continuity. None of them has ever asked
"what is happening to the animal in this scene, and is it acceptable?"

Four checks, from a user-supplied series brief's own harmlessness rules:

  injury     nothing described as damaging the animal
  distress   performed outrage is the comedy; real fear is not
  hazard     nothing sharp, hot, toxic, electrical or high staged near it
  softened   the one POSITIVE rule - a contact word needs a softener beside it

Exit code 0 when every check passes; 1 otherwise, the same contract as
realism_lint.py, ad_lint.py, relight_lint.py and macro_insert_lint.py, so a
workflow step can gate on it.

TWO RULES THIS FILE WILL NOT BEND, both measured rather than assumed:

1. It scans AUTHORED FIELDS ONLY - a subject, an action, a caption, a setting -
   never an assembled prompt and never a sound brief. The shared vocabulary is
   full of innocent collisions: "crushing" is in camera_angle_bank.json,
   "squash and stretch" in story_bank.json's stylised style, "slap" and
   "smacked" in sound_bank.json's own comedy examples. Pointed at a composed
   prompt this linter would fail clean photoreal work for words the photographer
   put there.

2. It is scoped PER FIELD, not across the joined text. Otherwise a "soft
   daylight" sitting in the setting vouches for an unsoftened swat in the
   action, and the softener rule quietly stops meaning anything.

Negation is not re-implemented: realism_lint.is_negated() is imported, so
"no claws" reads as safe here exactly as it does at the shared gate. That rule
is a PREFIX rule though - it looks backwards - so a phrase that defuses itself
afterwards ("claws sheathed") escapes it, and the bank's `defused` list is
stripped from the text before anything is scanned.

Usage:
    python tools/safety_lint.py --text "rolling on his back, all four paws going"
    python tools/safety_lint.py --scenes temp/outputs/stories/x.json
    python tools/safety_lint.py --check-bank
    echo "swatting the kitten off the table" | python tools/safety_lint.py -

Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "safety_bank.json"

# The fields a human actually writes. Everything else in a scene dict is
# composed by this app, and composing is not the thing being judged.
AUTHORED_FIELDS = ("subject", "action", "caption", "setting", "wardrobe",
                   "lead_action", "foil_action", "task", "mishap", "narration")

# The subset that STAGES something - that tells the model what to depict. The
# softener rule applies only to these, because a caption is read by a viewer
# and never executed: the source brief's own punchline caption is literally
# "bap bap!", which is the joke, not an instruction to hit a kitten. Injury,
# distress and hazard still scan everything, since a caption claiming an animal
# was hurt is a problem wherever it is written.
STAGING_FIELDS = ("action", "lead_action", "foil_action", "task", "mishap",
                  "subject", "setting", "wardrobe")


def load_bank(path=None):
    with (Path(path) if path else BANK_PATH).open(encoding="utf-8") as fh:
        return json.load(fh)


def _strip_defused(bank, text):
    """Remove self-defusing phrases before anything is scanned.

    is_negated() looks BACKWARDS, so it catches "no claws" and misses "claws
    sheathed". Rather than inventing a second, forward-looking negation rule -
    which would be a second thing to keep in step with realism_lint - the bank
    names the handful of phrases that defuse themselves and they are simply
    taken out of the text first.
    """
    for phrase in bank.get("defused", {}).get("phrases", []):
        text = text.replace(phrase.lower(), " ")
    return text


def _hits(text, stems=(), words=()):
    """[(term, index)] for every positive hit, negated ones already dropped.

    `stems` are start-anchored so "claw" catches "claws" and "clawing";
    `words` are whole-word so "pain" does not fire on "a painted wall".
    """
    found = []
    for term in stems:
        for match in re.finditer(r"\b" + re.escape(term.lower()), text):
            if not rl.is_negated(text, match.start()):
                found.append((term, match.start()))
                break
    for term in words:
        for match in re.finditer(r"\b" + re.escape(term.lower()) + r"\b", text):
            if not rl.is_negated(text, match.start()):
                found.append((term, match.start()))
                break
    return found


def scan_field(bank, text):
    """{category: [terms]} for one authored field. Empty dict means clean."""
    low = _strip_defused(bank, (text or "").lower())
    out = {}
    for key, cfg in bank["categories"].items():
        found = [term for term, _i in _hits(low, cfg.get("stems", ()), cfg.get("words", ()))]
        if found:
            out[key] = found
    return out


def contact_unsoftened(bank, text):
    """[terms] - contact words in this field with no softener in the SAME field."""
    cfg = bank["softened"]
    low = _strip_defused(bank, (text or "").lower())
    found = [term for term, _i in _hits(low, cfg.get("contact_stems", ()),
                                        cfg.get("contact_words", ()))]
    if not found:
        return []
    if any(soft.lower() in low for soft in cfg.get("softeners", ())):
        return []
    return found


def _fields_of(item, names=AUTHORED_FIELDS):
    """[(label, text)] - the authored fields of a scene dict, spec dict or string."""
    if isinstance(item, str):
        return [("text", item)]
    pairs = []
    spec = item.get("spec") if isinstance(item.get("spec"), dict) else {}
    for name in names:
        for source, prefix in ((item, ""), (spec, "spec.")):
            value = source.get(name)
            if isinstance(value, str) and value.strip():
                pairs.append((prefix + name, value))
    return pairs


def _category_check(key):
    def check(bank, items):
        bad = []
        for n, item in enumerate(items, 1):
            for label, text in _fields_of(item):
                found = scan_field(bank, text).get(key)
                if found:
                    bad.append("{}#{} {}: {}".format(
                        "scene " if len(items) > 1 else "", n, label, ", ".join(found)))
        if bad:
            return False, "{} - {}".format("; ".join(bad[:3]), bank["categories"][key]["fix"])
        return True, bank["categories"][key]["role"]
    return check


check_injury = _category_check("injury")
check_distress = _category_check("distress")
check_hazard = _category_check("hazard")


def check_softened(bank, items):
    """The positive rule: contact is allowed, unsoftened contact is not.

    Passes trivially when nothing makes contact at all - the same "too few to
    compare" shape story_lint.check_tasks_vary uses - and says so, rather than
    reporting a silent pass that reads like a real one.
    """
    bad, seen_contact = [], False
    for n, item in enumerate(items, 1):
        for label, text in _fields_of(item, STAGING_FIELDS):
            found = contact_unsoftened(bank, text)
            low = (text or "").lower()
            if any(re.search(r"\b" + re.escape(t), low)
                   for t in bank["softened"].get("contact_stems", ())):
                seen_contact = True
            if found:
                bad.append("{}#{} {}: {}".format(
                    "scene " if len(items) > 1 else "", n, label, ", ".join(found)))
    if bad:
        return False, "{} - {}".format("; ".join(bad[:3]), bank["softened"]["fix"])
    if not seen_contact:
        return True, "nothing makes contact, so nothing needs softening"
    return True, bank["softened"]["role"]


CHECKS = [
    ("injury", "No injury", check_injury),
    ("distress", "No genuine distress", check_distress),
    ("hazard", "No dangerous set", check_hazard),
    ("softened", "Contact is softened", check_softened),
]


def lint(bank, items):
    """[(key, label, passed, detail)] - one row per check."""
    results = []
    for key, label, fn in CHECKS:
        passed, detail = fn(bank, items)
        results.append((key, label, passed, detail))
    return results


def score(results):
    return sum(1 for _k, _l, passed, _d in results if passed), len(results)


def passes(bank, items):
    got, total = score(lint(bank, items))
    return got == total


# ---------------------------------------------------------------- bank audit
AUDIT_BANKS = ("prompt_bank.json", "story_bank.json", "sound_bank.json",
               "camera_angle_bank.json", "lighting_bank.json", "composition_bank.json",
               "motion_bank.json", "color_bank.json", "style_bank.json")


def _phrases(node, out):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _phrases(value, out)
    elif isinstance(node, list):
        for value in node:
            _phrases(value, out)
    return out


def _allowed(bank, name, phrase, terms):
    """True when this collision is one of the reviewed entries in `audit_allow`."""
    low = phrase.lower()
    for row in bank.get("audit_allow", {}).get("allow", []):
        if row.get("bank") == name and row.get("term") in terms \
                and row.get("contains", "").lower() in low:
            return True
    return False


def audit_banks(bank, names=AUDIT_BANKS):
    """[(bank, phrase, category, terms)] - every UNREVIEWED collision.

    Run PER PHRASE, never against a joined string: joining invents adjacencies
    that no real prompt has. This is what stops someone adding "crush" or
    "razor" to a category later and silently breaking the photoreal gate.

    A handful of real collisions are expected and harmless - "Blade Runner
    2049" is a colour-grade reference, not a knife - so the bank carries a
    reviewed `audit_allow` list, each entry stating why. Anything NOT on that
    list is reported, which keeps this a tripwire rather than a formality.
    """
    clashes = []
    for name in names:
        path = ROOT / "tools" / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for phrase in _phrases(json.load(fh), []):
                for key, terms in scan_field(bank, phrase).items():
                    if not _allowed(bank, name, phrase, terms):
                        clashes.append((name, phrase[:70], key, terms))
    return clashes


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Gate what a scene depicts - injury, distress, hazards, unsoftened contact.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("path", nargs="?", help="a text file to check, or - for stdin")
    p.add_argument("--text", help="check this string directly")
    p.add_argument("--scenes", help="a composed story JSON to check scene by scene")
    p.add_argument("--check-bank", action="store_true",
                   help="audit the safety vocabulary against every shipped bank and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.check_bank:
        clashes = audit_banks(bank)
        for name, phrase, key, terms in clashes:
            print("CLASH  {:<22} [{}] {!r} <- {}".format(name, key, phrase, ", ".join(terms)))
        print("\n{} collision(s) with shipped vocabulary".format(len(clashes)))
        if clashes:
            print("A safety term that fires on this app's own vocabulary would fail clean work.")
        return 1 if clashes else 0

    if args.scenes:
        path = Path(args.scenes)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Scenes file not found: {}".format(path))
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
        items = payload.get("scenes", payload) if isinstance(payload, dict) else payload
    elif args.text:
        items = [args.text]
    elif args.path == "-":
        items = [sys.stdin.read()]
    elif args.path:
        path = Path(args.path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("File not found: {}".format(path))
        items = [path.read_text(encoding="utf-8")]
    else:
        sys.exit("Give --text, --scenes, a file path, or - for stdin.")

    results = lint(bank, items)
    got, total = score(results)
    for _key, label, passed, detail in results:
        print("{}  {:<26} {}".format("PASS" if passed else "FAIL", label, detail))
    print("\n{}/{}".format(got, total))
    return 0 if got == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
