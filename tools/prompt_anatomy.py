"""Break a prompt into its slots - the skeleton, not the words.

Usage:
    python tools/prompt_anatomy.py --list
    python tools/prompt_anatomy.py --template beauty-macro
    python tools/prompt_anatomy.py --template video-sequence --scaffold
    python tools/prompt_anatomy.py --template video-sequence --scaffold --filled
    python tools/prompt_anatomy.py --template beauty-macro --analyse my-prompt.txt
    cat my-prompt.txt | python tools/prompt_anatomy.py --template macro-insert --analyse -

Two jobs, one for each direction:

    EXPLAIN   --template <name>            print the slot skeleton in order:
                                            what each slot does, WHY it matters,
                                            and a worked example. This is the
                                            teaching half - read it to write
                                            your own prompt from scratch.
    ANALYSE   --template <name> --analyse   take a prompt you already have and
                                            report which slots it fills and
                                            which it leaves empty.
    SCAFFOLD  --template <name> --scaffold  print the same skeleton as text you
                                            can paste into a prompt box and
                                            fill in (add --filled to get the
                                            worked examples in place instead).

`analyse` is keyword presence, not parsing. It answers "which slots does this
prompt appear to fill", which is honest and deterministic; it does not pretend
to segment free prose into semantic regions. A slot that maps onto one of the
eight gated realism layers is detected by realism_lint.py's OWN DETECT table
rather than a second copy of those keywords - the same no-duplication rule
relight_bank.json follows for lighting and camera-angle phrases.

Standard library only. No API keys, no network.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "anatomy_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def templates(bank):
    return bank.get("templates", {})


def slots(bank, template):
    return templates(bank).get(template, {}).get("slots", [])


def validate_template(bank, name):
    """Return an error message for an unknown template, or None."""
    if name and name not in templates(bank):
        return "Unknown template '{}'. Available: {}".format(
            name, ", ".join(templates(bank)))
    return None


def _motion_verbs():
    """tools/motion_lint.py's own MOTION_VERBS, imported lazily.

    Lazy because motion_lint imports build_motion, and nothing in the image
    half of this tool should pay for the video half at import time.
    """
    import motion_lint as ml

    return list(ml.MOTION_VERBS)


# The same no-duplication rule as `layer`, for vocabulary that lives in a
# linter other than realism_lint. A camera-movement slot that kept its own
# copy of the motion verbs would silently drift away from what motion_lint
# actually gates on - which is the whole failure this indirection prevents.
BORROW = {"motion-verbs": _motion_verbs}


def slot_keywords(slot):
    """The keywords that detect this slot.

    Three detection paths, in the order they take precedence:

      layer    borrows realism_lint's own DETECT keys, so this tool and the
               8/8 gate can never disagree about what counts as (say) camera
               language. A layer slot carries nothing of its own.
      borrow   borrows another linter's table by name (see BORROW), and MAY
               add its own `detect` keys on top - motion_lint's verbs cover
               "dollies" and "drifts" but know nothing about "handheld".
      detect   the slot's own list, for vocabulary no linter owns yet.

    A slot's OWN keys are searched before any borrowed ones, because that is
    what analyse() reports back as the match. The borrowed verbs are bare
    words - "push" matches "sunglasses pushed on head" as happily as it does a
    push-in - so letting them answer first would fill the camera slot with a
    true verdict and a misleading quotation.
    """
    if slot.get("layer"):
        return list(rl.DETECT[slot["layer"]]["keys"])
    keys = list(slot.get("detect", []))
    return keys + (list(BORROW[slot["borrow"]]()) if slot.get("borrow") else [])


def _key_positions(key, text):
    """Every index where `key` matches, using realism_lint's own matching rule:
    a plain single word is start-anchored (\bkey), anything with a space,
    hyphen or digit is a plain substring. Mirrors realism_lint._layer_key_present,
    which answers the same question but cannot say WHERE."""
    key = key.lower()
    if rl._PLAIN_WORD.fullmatch(key):
        return [m.start() for m in re.finditer(r"\b" + re.escape(key), text)]
    out, start = [], 0
    while True:
        index = text.find(key, start)
        if index < 0:
            return out
        out.append(index)
        start = index + 1


def slot_present(slot, text):
    """(present, matched keyword or None) for one slot against a prompt.

    A keyword sitting inside a negation does NOT fill its slot. Without this,
    "no CGI look" filled the Aesthetic framing slot on the word "look", and a
    prompt was credited for the very thing it was ruling out. realism_lint
    already had to solve this for banned terms, so its is_negated() is reused
    here rather than a second negation rule being invented.
    """
    low = text.lower()
    for key in slot_keywords(slot):
        for index in _key_positions(key, low):
            if not rl.is_negated(low, index):
                return True, key
    return False, None


def slot_origin(slot):
    """One short phrase naming where this slot's keywords come from.

    Shared by the CLI and the Anatomy tab so the two cannot describe the same
    slot differently.
    """
    if slot.get("layer"):
        return "realism layer '{}'".format(slot["layer"])
    if slot.get("borrow"):
        return "{} from motion_lint{}".format(
            slot["borrow"].replace("-", " "),
            ", plus its own keywords" if slot.get("detect") else "")
    return "own keywords"


def analyse(bank, template, text):
    """[(slot, present, hit)] - one row per slot, in template order."""
    return [(slot,) + slot_present(slot, text) for slot in slots(bank, template)]


def coverage(rows):
    """(filled, total) across an analyse() result."""
    return sum(1 for _slot, present, _hit in rows if present), len(rows)


def explain_lines(bank, template):
    """The teaching skeleton as printable lines."""
    cfg = templates(bank)[template]
    out = ["{}  -  {}".format(cfg["label"], template), "", cfg["summary"], ""]
    for index, slot in enumerate(slots(bank, template), 1):
        origin = slot_origin(slot)
        out.append("{:>2}. [{}]  {}".format(index, slot["key"].upper(), slot["label"]))
        out.append("    does   {}".format(slot["does"]))
        out.append("    why    {}".format(slot["why"]))
        out.append("    e.g.   {}".format(slot["example"]))
        out.append("    ({})".format(origin))
        out.append("")
    return out


def _scaffold_line(slot, filled):
    """One `LABEL: value` line of a pasteable skeleton.

    Some slots' examples already open with their own band heading (the video
    templates write "CHARACTER LOCK: ..." because that is how the prompt is
    actually laid out). Re-prefixing those would produce "CHARACTER LOCK:
    CHARACTER LOCK: ..." - so a heading the example already carries is left
    alone rather than stripped or doubled.
    """
    head = slot["label"].upper()
    value = slot["example"] if filled else "<{}>".format(slot["does"].rstrip(".").lower())
    if filled and value.upper().startswith(head + ":"):
        return value
    return "{}: {}".format(head, value)


def scaffold_lines(bank, template, filled=False):
    """The template as text you can paste into a prompt box and fill in.

    `filled=False` gives the empty shape - every slot as a placeholder naming
    its own job. `filled=True` gives the same shape with the worked examples in
    place, to edit down rather than write up.

    Two layouts, because the templates are two different kinds of thing. A
    banded template (the video sequence, the beauty macro) really is written as
    labelled lines, so it scaffolds that way. A template whose `scaffold` is
    "inline" is one flowing sentence - and for those the labels must NOT be
    emitted, because motion_lint.py's first rule is that the prompt OPENS with
    the camera move, and a "CAMERA LEAD:" prefix in front of it is exactly the
    thing that rule is checking for. The slot names go in a legend above the
    line instead, where they teach without ending up in the prompt.

    Deliberately NOT a composed prompt: this tool teaches structure and owns no
    vocabulary, so what it hands you is a form, not an answer.
    """
    cfg = templates(bank)[template]
    rows = slots(bank, template)
    inline = cfg.get("scaffold") == "inline"

    out = ["# {} - {} slots".format(cfg["label"], len(rows))]
    out.append("# Worked example - swap the words, keep the shape." if filled else
               "# Replace every <...>. An empty slot is a decision, not an error -")
    if not filled:
        out.append("# delete any part you genuinely do not want to decide.")
    if inline:
        lead = " - the camera move goes FIRST" if rows[0].get("borrow") == "motion-verbs" else ""
        out.append("# One flowing prompt, in this order{}:".format(lead))
        for index, slot in enumerate(rows, 1):
            out.append("#   {}. {} - {}".format(index, slot["label"], slot["does"].rstrip(".").lower()))
        out.append("")
        parts = [slot["example"] if filled else "<{}>".format(slot["label"].lower())
                 for slot in rows]
        out.append(", ".join(parts))
        return out

    out.append("")
    for slot in rows:
        out.append(_scaffold_line(slot, filled))
    return out


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Break a prompt into its slots - the skeleton, not the words.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--template", help="a template name (see --list)")
    p.add_argument("--analyse", help="a prompt file to score against the template, or - for stdin")
    p.add_argument("--list", action="store_true", help="print every template and exit")
    p.add_argument("--scaffold", action="store_true",
                   help="print the template as a pasteable fill-in-the-blanks skeleton")
    p.add_argument("--filled", action="store_true",
                   help="with --scaffold, use the worked examples instead of placeholders")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for key, cfg in templates(bank).items():
            print("  {:<20} {:<32} {} slots".format(key, cfg["label"], len(cfg["slots"])))
            print("  {:<20} {}".format("", cfg["summary"]))
            print()
        return 0

    error = validate_template(bank, args.template)
    if error:
        sys.exit(error)
    if not args.template:
        sys.exit("Give --template <name> (see --list).")

    if args.scaffold:
        for line in scaffold_lines(bank, args.template, filled=args.filled):
            print(line)
        return 0

    if not args.analyse:
        for line in explain_lines(bank, args.template):
            print(line)
        return 0

    if args.analyse == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.analyse)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        text = path.read_text(encoding="utf-8")
    if not text.strip():
        sys.exit("Empty prompt.")

    rows = analyse(bank, args.template, text)
    filled, total = coverage(rows)
    print("{} - {}/{} slots filled".format(templates(bank)[args.template]["label"], filled, total))
    print()
    for slot, present, hit in rows:
        if present:
            print("  [ok]   {:<22} <- \"{}\"".format(slot["label"], hit))
        else:
            print("  [MISS] {:<22} -> {}".format(slot["label"], slot["does"]))
            print("         why: {}".format(slot["why"]))
    print()
    print("Empty slots are not errors - they are decisions you have not made yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
