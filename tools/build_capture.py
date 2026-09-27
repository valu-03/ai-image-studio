"""Compose a capture phrase - film stock, lens artefacts, exposure and the
evidence that a person was holding the camera.

Usage:
    python tools/build_capture.py --list
    python tools/build_capture.py --film-stock portra-400
    python tools/build_capture.py --optic halation --optic vignetting
    python tools/build_capture.py --film-stock cinestill-800t --optic veiling-glare \
                                  --exposure iso-400-shadow-noise --evidence handheld-frame
    python tools/build_capture.py --film-stock portra-400 --overrides

WHAT THIS IS FOR. The rest of this app describes the SUBJECT well and the
CAPTURE not at all: a repo-wide grep across every bank returned zero hits for
chromatic aberration, halation, veiling glare, vignetting, barrel distortion,
ISO, shutter speed, white balance and sensor dust, and no film stock is named
anywhere. Output therefore topped out at "well-lit studio photograph" - clean,
plausible, and with no evidence that a physical camera made it. That evidence
is most of what separates a photograph from a render.

Unlike Lighting or Colour, this composes across SEVERAL of build_prompt.py's
layers at once - a film stock strengthens `grain`, a lens artefact strengthens
`lens`, white balance strengthens `lighting`. So `--overrides` prints a JSON
object keyed by layer, ready for spec["overrides"], rather than one phrase.
Without it you get the plain comma-joined phrase, which is what the GUI Applies
into the free trailing segment.

Each option declares the layer it strengthens and tests/test_capture_bank.py
checks that realism_lint can actually SEE it, per phrase. A phrase the gate
cannot detect is decoration - which is exactly what story_bank.json's four fur
phrases turned out to be.

RESTRAINT IS THE POINT: real artefacts are faint. Every phrase in the bank is
hedged, and stacking all of them produces a filter rather than a photograph -
compose() warns when you ask for more than four.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "capture_bank.json"

# Past this many stacked artefacts the look stops reading as a camera and
# starts reading as a preset. A warning, never a refusal - the same shape
# build_motion.compose() uses for an incompatible move.
BUSY_AT = 4

GROUP_ARGS = {
    "film_stock": "film_stock",
    "optics": "optic",
    "exposure": "exposure",
    "evidence": "evidence",
}


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def groups(bank):
    return bank.get("groups", {})


def options(bank, group):
    return groups(bank).get(group, {}).get("options", {})


def layer_of(bank, group, key):
    """The realism_lint layer this option strengthens.

    An option may override its group's layer: white balance sits in the
    exposure group but is colour temperature, which belongs to lighting. The
    group layer is a default, not a claim about every option in it.
    """
    group_cfg = groups(bank).get(group, {})
    option = group_cfg.get("options", {}).get(key, {})
    return option.get("layer") or group_cfg.get("layer")


class CaptureError(ValueError):
    """An unknown key, two film stocks at once, or nothing selected at all."""


def compose_capture(bank, film_stock=None, optics=(), exposure=(), evidence=()):
    """(phrases_by_layer, warnings).

    `phrases_by_layer` maps a build_prompt layer name to the list of phrases
    chosen for it, so a caller can drop it straight into spec["overrides"].
    Order within a layer follows the bank, not the order they were typed, so
    the same selection always composes to the same string.
    """
    selection = [("film_stock", [film_stock] if film_stock else []),
                 ("optics", list(optics)),
                 ("exposure", list(exposure)),
                 ("evidence", list(evidence))]

    chosen = []
    for group, keys in selection:
        available = options(bank, group)
        if groups(bank).get(group, {}).get("exclusive") and len(keys) > 1:
            raise CaptureError(
                "{} is one complete pick - two of them contradict each other.".format(
                    groups(bank)[group]["label"]))
        for key in keys:
            if key not in available:
                raise CaptureError("Unknown {} option '{}'. See --list.".format(group, key))
        # Bank order, not argument order.
        chosen.extend((group, key) for key in available if key in keys)

    if not chosen:
        raise CaptureError(
            "Give at least one of --film-stock, --optic, --exposure or --evidence.")

    # A stock can already contain an artefact: CineStill 800T's whole signature
    # IS its halation, so picking both produced "subtle halation blooming
    # around the brightest highlights, subtle halation blooming softly around
    # the brightest highlights" - a stutter that reads as emphasis to the model
    # and makes the artefact louder than any real one. Declared in the bank
    # rather than string-matched, so the two cannot drift apart.
    implied = set()
    for group, key in chosen:
        implied.update(options(bank, group)[key].get("implies", []))
    dropped = [key for _group, key in chosen if key in implied]
    chosen = [(group, key) for group, key in chosen if key not in implied]

    by_layer = {}
    for group, key in chosen:
        layer = layer_of(bank, group, key)
        by_layer.setdefault(layer, []).append(options(bank, group)[key]["phrase"])

    warnings = []
    for key in dropped:
        warnings.append(
            "'{}' is already part of the film stock you picked - dropped rather "
            "than said twice.".format(key))
    if len(chosen) > BUSY_AT:
        warnings.append(
            "{} artefacts stacked - real capture is faint, and past about {} this "
            "reads as a filter rather than a photograph.".format(len(chosen), BUSY_AT))
    return by_layer, warnings


def phrase_for(by_layer):
    """The flat, comma-joined phrase - what the GUI Applies as free text."""
    return ", ".join(phrase for phrases in by_layer.values() for phrase in phrases)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a capture phrase - film stock, lens artefacts, "
                    "exposure, and evidence of a hand on the camera.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--film-stock", help="a bank key (see --list); at most one")
    p.add_argument("--optic", action="append", default=[],
                   help="a lens artefact, repeatable (see --list)")
    p.add_argument("--exposure", action="append", default=[],
                   help="an exposure or sensor property, repeatable (see --list)")
    p.add_argument("--evidence", action="append", default=[],
                   help="evidence of a hand on the camera, repeatable (see --list)")
    p.add_argument("--overrides", action="store_true",
                   help="print JSON keyed by build_prompt layer, for spec['overrides']")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for group, cfg in groups(bank).items():
            print("{}  (--{}{})".format(
                cfg["label"].upper(), GROUP_ARGS[group].replace("_", "-"),
                ", at most one" if cfg.get("exclusive") else ", repeatable"))
            print("  {}".format(cfg["note"]))
            for key, option in cfg["options"].items():
                print("  {:<24} {}".format(key, option["label"]))
                print("  {:<24} -> {}".format("", option["note"]))
            print()
        return 0

    try:
        by_layer, warnings = compose_capture(
            bank, film_stock=args.film_stock, optics=args.optic,
            exposure=args.exposure, evidence=args.evidence)
    except CaptureError as exc:
        sys.exit(str(exc))

    if args.overrides:
        print(json.dumps(by_layer, indent=2))
    else:
        print(phrase_for(by_layer))
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
