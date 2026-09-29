"""Reformat an already-built, already-scored prompt for Midjourney - text only.

Midjourney has no official public API; every third-party service that
automates it puppets the Discord bot, against Midjourney's own terms. This
tool changes nothing about how a generation happens in this app - it is a
pure text transform, the same spirit as Cats' "Copy sound cue" button: hand
you something to paste into Midjourney yourself, not a new provider.

Usage:
    python tools/midjourney_export.py --spec temp/resources/characters/x.json
    python tools/midjourney_export.py --prompt-file temp/outputs/prompts/x.txt --aspect 9:16
    python tools/midjourney_export.py --spec x.json --style default --stylize 100 --version 6

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prompt as bp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Photorealism-leaning defaults: raw mode plus a low stylize value pull
# Midjourney toward literal/photographic instead of its default painterly
# bias - both overridable via CLI flags for anyone who wants the normal look.
DEFAULT_VERSION = "6.1"
DEFAULT_STYLE = "raw"
DEFAULT_STYLIZE = 50


def negatives_to_no(bank):
    """prompt_bank.json's sentence-form negatives ("no cartoon style") -> MJ's
    own comma-separated --no syntax ("cartoon style, CGI, ...")."""
    terms = []
    for phrase in bank.get("negatives", []):
        term = phrase.strip()
        for prefix in ("no ", "No "):
            if term.startswith(prefix):
                term = term[len(prefix):]
                break
        if term:
            terms.append(term)
    return terms


def to_midjourney(bank, spec, prompt, version=DEFAULT_VERSION, style=DEFAULT_STYLE,
                   stylize=DEFAULT_STYLIZE, sref=None, sw=None):
    """An already-built prompt + its spec -> the same prompt with Midjourney's
    own parameter syntax appended.

    Never invents new wording: `prompt` is used verbatim - whatever
    build_prompt.compose() already produced and realism_lint already scored -
    and every parameter comes from the spec's own real fields (`spec["aspect"]`,
    `spec["reference"]`) or the bank's own negatives list. Nothing here writes
    new prompt vocabulary.

    `prompt` already ends with the negatives in sentence form ("no cartoon
    style, ...") and, if `spec["aspect"]` was set, a trailing "aspect ratio
    9:16" clause - compose() always appends both. This deliberately does NOT
    strip either one before appending --no/--ar: `prompt` is natural-language
    text, not structured data, and parsing/trimming the tail of an already-
    assembled sentence to remove what looks redundant is exactly the kind of
    fragile text-surgery this project avoids elsewhere (a hardcoded-string
    comparison against rendered UI text was already a real bug once - see
    AiSuggestionBadge in CLAUDE.md). Midjourney seeing the same instruction
    twice - once as prose, once as its own native parameter - is redundant,
    not wrong.
    """
    params = []
    aspect = str(spec.get("aspect") or "").strip()
    if aspect:
        params.append("--ar {}".format(aspect))
    if style:
        params.append("--style {}".format(style))
    if stylize is not None:
        params.append("--stylize {}".format(stylize))
    no_terms = negatives_to_no(bank)
    if no_terms:
        params.append("--no {}".format(", ".join(no_terms)))
    if version:
        params.append("--v {}".format(version))
    # --sref is a STYLE reference (a job id, a --sref number, or an image URL),
    # which is a different thing from spec["reference"] below: that one is a
    # character/scene reference the user has to attach in Discord themselves.
    # A style reference is just a token, so unlike an image it CAN be carried
    # in the text - which is why this one is a parameter and that one is a note.
    if sref:
        params.append("--sref {}".format(sref))
    # --sw only means anything alongside --sref, so it is not emitted alone.
    if sref and sw is not None:
        params.append("--sw {}".format(sw))

    text = prompt.strip()
    if params:
        text = text.rstrip(", ") + " " + " ".join(params)

    reference = str(spec.get("reference") or "").strip()
    if reference:
        text += (
            "\n\n[reference image: {} - attach this yourself in Discord; "
            "Midjourney has no API to upload it for you]".format(reference)
        )
    return text


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Reformat a built prompt for Midjourney (text only, no API).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON - builds the prompt fresh")
    p.add_argument("--prompt-file", help="an already-built prompt .txt instead of --spec")
    p.add_argument("--aspect", help="override the aspect ratio (--ar), e.g. 9:16")
    p.add_argument("--version", default=DEFAULT_VERSION, help="Midjourney model version (--v)")
    p.add_argument("--style", default=DEFAULT_STYLE,
                    help="'raw' (photoreal-leaning, the default) or 'default' for MJ's own look")
    p.add_argument("--stylize", type=int, default=DEFAULT_STYLIZE, help="--stylize value (0-1000)")
    p.add_argument("--sref",
                   help="style reference to match: a job id, an --sref number or an "
                        "image URL. Carried as a parameter, not as an attachment.")
    p.add_argument("--sw", type=int,
                   help="how strongly to apply --sref (0-1000). Ignored without it.")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    bank = bp.load_bank()
    spec = {}
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        spec = json.loads(path.read_text(encoding="utf-8"))

    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        prompt = path.read_text(encoding="utf-8").strip()
    elif args.spec:
        prompt, _ = bp.compose(bank, spec)
    else:
        sys.exit("Give --spec <path>, or --prompt-file <path> (with --spec for its fields too).")

    if args.aspect:
        spec = dict(spec, aspect=args.aspect)

    style = None if args.style == "default" else args.style
    print(to_midjourney(bank, spec, prompt, version=args.version, style=style,
                        stylize=args.stylize, sref=args.sref, sw=args.sw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
