"""Weight and contact: what the subject presses on, and how it gives.

Usage:
    python tools/build_contact.py --list
    python tools/build_contact.py --subject "a woman" --action "curled up on a sofa holding a mug"
    python tools/build_contact.py --subject "a ginger cat" --setting "asleep on a duvet"
    python tools/build_contact.py --subject "a man in his forties" --seed 3

THE PROBLEM. Generated images rarely show weight. A body sits on a sofa and the
cushion stays flat; a hand holds a mug without pressing into it; a sleeve never
creases at the elbow. Each piece looks right on its own and the whole looks
pasted together. scene_light_bank.json already grounds the subject with a
contact SHADOW - this is the other half, the surfaces and fabric actually
deforming where they meet.

HOW. contact_bank.json lists `supports` (sofa, bed, grass, snow, table...) and
`actions` (holding, sitting, lying...), each with whole-word keywords and one
phrase per subject kind. Subject, Action, Posing and Setting are read together;
matches are used in the order the text mentions them (earliest first, the
build_scene_light rule), at most `max_phrases`. An entry without a phrase for
the subject's kind is skipped, so a perfume bottle on a table never gets
"forearms resting". Nothing matched: `by_kind` supplies a default, picked by
seed the build_evidence way, so Variants' seeds differ and each is reproducible.

Lands in spec["overrides"]["contact"] via build_prompt.apply_physical() - a
non-layer override, appended to the free tail, so it can only ever ADD to a
realism score.

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_evidence as bev  # noqa: E402
import build_scene_light as bsl  # noqa: E402

BANK_PATH = Path(__file__).resolve().parent / "contact_bank.json"
TEXT_FIELDS = ("subject", "action", "posing", "setting")


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def spec_text(spec, fields=TEXT_FIELDS):
    """The spec fields this reads, joined, lower-cased."""
    return " ".join(str(spec.get(f) or "") for f in fields).lower()


def mentioned(table, text):
    """Keys of `table` whose keywords appear in `text`, earliest mention first.

    Whole words only (bsl._first_hit), so "bar" is not found in "barely" and
    "bed" not in "embedded". Ties keep the table's own order."""
    hits = []
    for order, (key, cfg) in enumerate(table.items()):
        at = bsl._first_hit(text, cfg.get("keywords", []))
        if at is not None:
            hits.append((at, order, key))
    return [key for _at, _order, key in sorted(hits)]


def read_contact(bank, spec, kind=None, seed=None):
    """(phrase, matched keys) for a spec. `kind` defaults to the Subject's.

    Supports and actions are merged by where they are mentioned, then only
    the ones with a phrase for this kind are kept. With none, one `by_kind`
    default by seed (matched keys then empty). A place gets nothing.
    """
    if kind is None:
        kind = bev.subject_kind(bev.load_bank(), spec.get("subject", ""))
    text = spec_text(spec)
    entries = dict(bank.get("supports", {}))
    entries.update(bank.get("actions", {}))
    keys = [k for k in mentioned(entries, text) if entries[k].get(kind)]
    keys = keys[:int(bank.get("max_phrases", 2))]
    if keys:
        return ", ".join(entries[k][kind] for k in keys), keys
    defaults = list(bank.get("by_kind", {}).get(kind, []))
    if not defaults:
        return "", []
    seed = spec.get("seed", 0) if seed is None else seed
    count = min(int(bank.get("default_count", 1)), len(defaults))
    chosen = random.Random("contact:{}:{}".format(kind, seed)).sample(defaults, count)
    return ", ".join(p for p in defaults if p in chosen), []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose weight and contact - what the subject presses on, and how it gives.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--subject", default="")
    p.add_argument("--action", default="")
    p.add_argument("--posing", default="")
    p.add_argument("--setting", default="")
    p.add_argument("--kind", choices=bev.KINDS, help="override the kind read from --subject")
    p.add_argument("--seed", type=int, default=0, help="picks the default when nothing matched")
    p.add_argument("--list", action="store_true", help="print every entry and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()
    if args.list:
        for table in ("supports", "actions"):
            print(table.upper())
            for key, cfg in bank[table].items():
                print("  {:<10} {}".format(key, ", ".join(cfg["keywords"])))
                for kind in bev.KINDS:
                    if cfg.get(kind):
                        print("  {:<10}   {}: {}".format("", kind, cfg[kind]))
            print()
        return 0
    spec = {"subject": args.subject, "action": args.action, "posing": args.posing,
            "setting": args.setting, "seed": args.seed}
    phrase, _keys = read_contact(bank, spec, kind=args.kind)
    if not phrase:
        print("(nothing - a place has nothing pressing on anything)", file=sys.stderr)
        return 0
    print(phrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
