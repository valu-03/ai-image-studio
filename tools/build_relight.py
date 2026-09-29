"""Change the lighting and/or camera angle of an EXISTING photo, batch-composed.

Usage:
    python tools/build_relight.py --list
    python tools/build_relight.py --spec temp/resources/images/porch.json \\
        --reference temp/resources/images/porch-ref.png --set avatar-turnaround
    python tools/build_relight.py --spec <spec> --reference <ref> \\
        --shots temp/resources/relight-shots.json

Two real AI Video Bootcamp techniques, applied together - see relight_bank.json's
own `source` field for the exact lessons and quotes. Every shot locks the SCENE
to the reference photo (`--lock-scene` in build_prompt.py) rather than locking
identity: same subject, wardrobe, setting, pose and framing as the source photo -
only the lighting and/or camera angle change, exactly as directed. This is the
inverse of consistent-character.md's lock (same face, everything else changes) -
here everything else is fixed and only light/angle move, which is why this tool
never touches spec["variation"] - that mechanism exists for describing a NEW
scene, and this feature's whole point is not describing a new scene.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_camera_angle as bca  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_prompt as bp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "relight_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def sets(bank):
    return bank.get("sets", {})


def validate_set(bank, name):
    """Return an error message for an unknown set name, or None."""
    if name and name not in sets(bank):
        return "Unknown set '{}'. Available: {}".format(name, ", ".join(sets(bank)))
    return None


def _shot_spec(base_spec, reference, shot, lighting_bank, camera_bank):
    """base_spec + reference, scene-locked, with this shot's lighting/angle.

    subject/wardrobe/setting/action come from base_spec UNCHANGED - that is
    the whole point of a scene lock. `variation` is stripped even if the base
    spec carries one; it is the wrong mechanism here (see module docstring).
    """
    spec = dict(base_spec)
    spec.pop("variation", None)
    spec["reference"] = reference
    spec["lock_scene"] = True

    overrides = dict(spec.get("overrides", {}))
    if shot.get("lighting_setup"):
        phrase, _warnings = bl.compose_lighting(lighting_bank, setup=shot["lighting_setup"])
        overrides["lighting"] = phrase
    spec["overrides"] = overrides

    if any(shot.get(k) for k in ("vertical", "side", "size")):
        phrase, _warnings = bca.compose_camera_angle(
            camera_bank, vertical=shot.get("vertical"),
            side=shot.get("side"), size=shot.get("size"))
        spec["shot_custom"] = phrase

    return spec


def compose_relight_set(bank, image_bank, lighting_bank, camera_bank, base_spec,
                         reference, shots):
    """base_spec + reference + [{"lighting_setup"|"vertical"/"side"/"size"}] ->
    a list of shot dicts, each independently lint-ready. subject/wardrobe/
    setting/action are inherited from base_spec unchanged in every shot.
    """
    out = []
    for index, shot in enumerate(shots):
        spec = _shot_spec(base_spec, reference, shot, lighting_bank, camera_bank)
        spec["slug"] = "{}-relight-{}".format(
            bp.slugify(base_spec.get("slug") or base_spec.get("subject", "photo")), index + 1)
        prompt, layers = bp.compose(image_bank, spec)
        out.append({
            "index": index + 1,
            "lighting_setup": shot.get("lighting_setup"),
            "vertical": shot.get("vertical"),
            "side": shot.get("side"),
            "size": shot.get("size"),
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
        })
    return out


def _shot_label(shot):
    bits = [b for b in (shot.get("lighting_setup"), shot.get("side"),
                        shot.get("vertical"), shot.get("size")) if b]
    return " / ".join(bits) or "shot"


def shot_label(shot):
    """The shots' one-line name - lighting setup and/or angle axes, joined.

    Public so the GUI labels a shot exactly as the written batch does;
    one source of truth rather than two that drift.
    """
    return _shot_label(shot)


def write_relight_set(base_spec, shots):
    """Write the whole batch to temp/outputs/prompts/: a readable .txt and a
    .json sibling relight_lint.py's CLI reads. Returns the .txt path."""
    slug = bp.slugify(base_spec.get("slug") or base_spec.get("subject", "photo"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = OUT_DIR / "relight-{}-{}.txt".format(slug, stamp)
    json_path = OUT_DIR / "relight-{}-{}.json".format(slug, stamp)

    blocks = []
    for shot in shots:
        blocks.append("=== {}. {}\n{}\n".format(shot["index"], _shot_label(shot), shot["prompt"]))
    txt_path.write_text("\n".join(blocks), encoding="utf-8")
    json_path.write_text(json.dumps({"shots": shots}, indent=2), encoding="utf-8")
    return txt_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Batch-compose relit/re-angled prompts from one reference photo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a spec JSON describing the source photo")
    p.add_argument("--subject", help="the source photo's subject, if no --spec is given")
    p.add_argument("--reference", help="path to the source photo")
    p.add_argument("--set", help="a named set from relight_bank.json (see --list)")
    p.add_argument("--shots", help="path to a JSON array of custom shot dicts instead of --set")
    p.add_argument("--list", action="store_true", help="print every named set and exit")
    p.add_argument("--no-write", action="store_true", help="print only, do not write files")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompts")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        for key, cfg in sets(bank).items():
            print("  {:<20} {}".format(key, cfg["label"]))
            for shot in cfg["shots"]:
                print("      {}".format(_shot_label(shot)))
        return 0

    error = validate_set(bank, args.set)
    if error:
        sys.exit(error)

    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        base_spec = json.loads(path.read_text(encoding="utf-8"))
    elif args.subject:
        base_spec = {"subject": args.subject, "seed": 0}
    else:
        sys.exit("Give either --spec <path> or --subject \"...\". See --help.")

    if not args.reference:
        sys.exit("Give --reference <path to the source photo>.")

    if args.shots:
        shots_path = Path(args.shots)
        if not shots_path.is_absolute():
            shots_path = ROOT / shots_path
        if not shots_path.exists():
            sys.exit("Shots file not found: {}".format(shots_path))
        shots_in = json.loads(shots_path.read_text(encoding="utf-8"))
    elif args.set:
        shots_in = sets(bank)[args.set]["shots"]
    else:
        sys.exit("Give either --set <name> (see --list) or --shots <path.json>.")

    if args.seed is not None:
        base_spec["seed"] = args.seed

    image_bank = bp.load_bank()
    lighting_bank = bl.load_bank()
    camera_bank = bca.load_bank()
    shots = compose_relight_set(bank, image_bank, lighting_bank, camera_bank,
                                 base_spec, args.reference, shots_in)

    for shot in shots:
        print("=== {}. {}".format(shot["index"], _shot_label(shot)))
        print(shot["prompt"])
        print()

    if not args.no_write:
        path = write_relight_set(base_spec, shots)
        print("[relight] {}".format(path), file=sys.stderr)
        print("[next]    python tools/relight_lint.py --relight {}".format(
            str(path).replace(".txt", ".json")), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
