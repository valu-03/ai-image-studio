"""Compose a camera-angle phrase - vertical position + side + shot size, any
subset, or your own typed text.

Usage:
    python tools/build_camera_angle.py --list
    python tools/build_camera_angle.py --vertical low-angle
    python tools/build_camera_angle.py --vertical low-angle --side profile --size close-up
    python tools/build_camera_angle.py --custom "shot from a drone, looking straight down"

Three independent axes - unlike Lighting's quality x source, there's no
natural contradiction between them (low-angle + profile + close-up is a
perfectly valid real combination), so there's no conflicts check here, and
no --technique either - the three axes fully describe camera position on
their own.

`--custom` always wins entirely if given, same precedence as everywhere
else in this project. Otherwise composes whichever subset of --vertical/
--side/--size you give (comma-joined) - give at least one, or nothing
resolves and CameraAngleError is raised.

The result is meant to be typed straight into Compose's own Shot field as
custom text (ui/spec_editor.py's shot combo), replacing the camera slot -
EXACTLY like typing any other custom shot today. That means it can
legitimately score the camera realism layer at 0/8 if the phrase names no
actual capture device - that's the gate working, not a bug, the same words
the Shot field's own tooltip already uses. Combine with a picked camera (or
the Camera Angle library's own Library tab has no opinion on this either
way) if you want the camera layer to keep scoring.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "camera_angle_bank.json"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def verticals(bank):
    return bank.get("verticals", {})


def sides(bank):
    return bank.get("sides", {})


def sizes(bank):
    return bank.get("sizes", {})


class CameraAngleError(ValueError):
    """An unknown key was asked for, or nothing at all resolved to a phrase."""


def compose_camera_angle(bank, vertical=None, side=None, size=None, custom=None):
    """(phrase, warnings). `warnings` is always [] - the three axes never
    contradict each other, so there's nothing to warn about. Raises
    CameraAngleError for an unknown key, or if nothing at all is given.
    """
    custom = (custom or "").strip()
    if custom:
        return custom, []

    parts = []
    if vertical:
        cfg = verticals(bank).get(vertical)
        if not cfg:
            raise CameraAngleError("Unknown vertical '{}'. See --list.".format(vertical))
        parts.append(cfg["phrase"])
    if side:
        cfg = sides(bank).get(side)
        if not cfg:
            raise CameraAngleError("Unknown side '{}'. See --list.".format(side))
        parts.append(cfg["phrase"])
    if size:
        cfg = sizes(bank).get(size)
        if not cfg:
            raise CameraAngleError("Unknown size '{}'. See --list.".format(size))
        parts.append(cfg["phrase"])

    if not parts:
        raise CameraAngleError(
            "Give --vertical, --side, --size, or --custom text - at least one.")

    return ", ".join(parts), []


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a camera-angle phrase - vertical position + side + "
                    "shot size, any subset, or your own text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--vertical", help="e.g. low-angle, high-angle, worms-eye (see --list)")
    p.add_argument("--side", help="e.g. profile, three-quarter, over-the-shoulder (see --list)")
    p.add_argument("--size", help="e.g. close-up, wide, medium (see --list)")
    p.add_argument("--custom", help="typed camera-angle text - beats everything else")
    p.add_argument("--list", action="store_true", help="print every option and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("VERTICALS")
        for key, cfg in verticals(bank).items():
            print("  {:<14} {}".format(key, cfg["note"]))
        print("\nSIDES")
        for key, cfg in sides(bank).items():
            print("  {:<20} {}".format(key, cfg["note"]))
        print("\nSIZES")
        for key, cfg in sizes(bank).items():
            print("  {:<18} {}".format(key, cfg["note"]))
        return 0

    try:
        phrase, warnings = compose_camera_angle(
            bank, vertical=args.vertical, side=args.side, size=args.size, custom=args.custom)
    except CameraAngleError as exc:
        sys.exit(str(exc))

    print(phrase)
    for warning in warnings:
        print("[warn] {}".format(warning), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
