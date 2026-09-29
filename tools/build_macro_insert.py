"""Beauty macro and feature-scoped macro inserts of one face.

Usage:
    python tools/build_macro_insert.py --list
    python tools/build_macro_insert.py --subject "a woman in her thirties" \\
        --set full-face-only
    python tools/build_macro_insert.py --spec temp/resources/characters/ada.json \\
        --reference temp/resources/characters/ada-face.png --set inserts-only
    python tools/build_macro_insert.py --spec <spec> --reference <ref> \\
        --insert eye --insert mouth

Two stages, and the order matters:

    STAGE 1  `full-face` CREATES the canonical face. It takes no reference and
             sets no identity lock, because there is nothing yet to lock to.
    STAGE 2  `eye`, `mouth` and `cheek` DERIVE from that generated image. Each
             one REQUIRES --reference, sets lock_identity, and carries its own
             feature-scoped `preserve` phrase naming what must not drift -
             gaze, lip proportions, undertone - none of which
             build_prompt.LOCK_COMPACT says on its own.

The vocabulary lives in macro_insert_bank.json, not prompt_bank.json: that is
the bank precedent lighting/composition/colour/camera-angle already set, and it
keeps extreme-macro skin language out of the shared random texture pool where a
wide environmental shot could otherwise draw "sebaceous shine" at random.

The composed shot-size phrase goes into spec["overrides"]["composition"], NOT
spec["shot_custom"] the way build_relight.py does it: composition is pick:2 and
pins rather than replaces, so the camera slot keeps a real capture device and
every shot here holds a strict 8/8 rather than build_relight.py's documented
7/8 angle-shot floor.

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
BANK_PATH = Path(__file__).resolve().parent / "macro_insert_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"

# prompt_bank.json's layers.lighting.always entry. select_layers() drops the
# `always` terms when a layer is overridden, so an overriding caller has to put
# it back - the same thing tests/test_lighting_bank.py already does.
LIGHTING_ALWAYS = "realistic shadows"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def inserts(bank):
    return bank.get("inserts", {})


def sets(bank):
    return bank.get("sets", {})


def validate_set(bank, name):
    """Return an error message for an unknown set name, or None."""
    if name and name not in sets(bank):
        return "Unknown set '{}'. Available: {}".format(name, ", ".join(sets(bank)))
    return None


def validate_insert(bank, name):
    """Return an error message for an unknown insert name, or None."""
    if name and name not in inserts(bank):
        return "Unknown insert '{}'. Available: {}".format(name, ", ".join(inserts(bank)))
    return None


def needs_reference(bank, insert_names):
    """The insert names in `insert_names` that derive from a reference image.

    `full-face` creates the face and needs nothing; every `insert` kind is a
    crop of an image that must already exist.
    """
    return [n for n in insert_names if inserts(bank).get(n, {}).get("kind") == "insert"]


def _insert_spec(base_spec, reference, entry, lighting_bank, camera_bank):
    """One shot's spec.

    A carried-over `shot` preset or `shot_custom` would fight the composed
    camera/lens/composition overrides - and `shot_custom` would take the
    camera slot outright and cost the shot its camera layer - so both are
    stripped. `variation` is stripped for the same reason build_relight.py
    strips it: it exists to describe a NEW scene, and this is a new crop of
    one that already exists.
    """
    spec = dict(base_spec)
    for field in ("variation", "shot", "shot_custom"):
        spec.pop(field, None)

    overrides = dict(spec.get("overrides", {}))
    entry_overrides = entry.get("overrides", {})
    for layer in ("camera", "lens", "texture"):
        if entry_overrides.get(layer):
            overrides[layer] = entry_overrides[layer]

    size_phrase, _warnings = bca.compose_camera_angle(camera_bank, size=entry["size"])
    overrides["composition"] = [size_phrase] + list(entry_overrides.get("composition", []))

    light, _warnings = bl.compose_lighting(
        lighting_bank, setup=entry["lighting_setup"],
        techniques_=entry.get("techniques", []))
    overrides["lighting"] = [light, LIGHTING_ALWAYS]

    spec["overrides"] = overrides

    # Stage two only: the inserts lock to the face stage one produced. The
    # `preserve` phrase is appended to whatever extras the caller already had,
    # never replacing them.
    if entry.get("kind") == "insert":
        spec["reference"] = reference
        spec["lock_identity"] = True
        spec["extra"] = list(base_spec.get("extra", [])) + [entry["preserve"]]

    return spec


def compose_macro_set(bank, image_bank, lighting_bank, camera_bank, base_spec,
                       reference, insert_names):
    """base_spec + reference + [insert name] -> a list of lint-ready shot dicts."""
    out = []
    for index, name in enumerate(insert_names):
        entry = inserts(bank)[name]
        spec = _insert_spec(base_spec, reference, entry, lighting_bank, camera_bank)
        spec["slug"] = "{}-macro-{}".format(
            bp.slugify(base_spec.get("slug") or base_spec.get("subject", "face")), name)
        prompt, layers = bp.compose(image_bank, spec)
        out.append({
            "index": index + 1,
            "insert": name,
            "label": entry["label"],
            "scope": entry["scope"],
            "kind": entry["kind"],
            "lighting_setup": entry["lighting_setup"],
            "size": entry["size"],
            "preserve": entry.get("preserve", ""),
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
        })
    return out


def _shot_label(shot):
    return "{} ({})".format(shot["label"], shot["scope"])


def shot_label(shot):
    """The insert's one-line name - its label and what it is scoped to.

    Public so the GUI labels a shot exactly as the written batch does;
    one source of truth rather than two that drift.
    """
    return _shot_label(shot)


def write_macro_set(base_spec, shots):
    """Write the batch to temp/outputs/prompts/: a readable .txt and a .json
    sibling macro_insert_lint.py's CLI reads. Returns the .txt path."""
    slug = bp.slugify(base_spec.get("slug") or base_spec.get("subject", "face"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = OUT_DIR / "macro-{}-{}.txt".format(slug, stamp)
    json_path = OUT_DIR / "macro-{}-{}.json".format(slug, stamp)

    blocks = []
    for shot in shots:
        blocks.append("=== {}. {}\n{}\n".format(shot["index"], _shot_label(shot), shot["prompt"]))
    txt_path.write_text("\n".join(blocks), encoding="utf-8")
    json_path.write_text(json.dumps({"shots": shots}, indent=2), encoding="utf-8")
    return txt_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Compose a beauty macro and feature-scoped macro inserts of one face.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON")
    p.add_argument("--subject", help="the face, if no --spec is given")
    p.add_argument("--reference", help="the full-face image the inserts crop into (stage two)")
    p.add_argument("--set", help="a named set from macro_insert_bank.json (see --list)")
    p.add_argument("--insert", action="append", default=[],
                    help="a single insert by name, repeatable, instead of --set")
    p.add_argument("--list", action="store_true", help="print every set and insert, then exit")
    p.add_argument("--no-write", action="store_true", help="print only, do not write files")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompts")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("SETS")
        for key, cfg in sets(bank).items():
            print("  {:<18} {}".format(key, cfg["label"]))
        print("\nINSERTS")
        for key, entry in inserts(bank).items():
            stage = "stage 1 - creates the face" if entry["kind"] == "portrait" \
                else "stage 2 - needs --reference"
            print("  {:<12} {:<28} {}".format(key, entry["label"], stage))
        return 0

    for error in (validate_set(bank, args.set),
                  *[validate_insert(bank, name) for name in args.insert]):
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

    if args.insert:
        names = list(args.insert)
    elif args.set:
        names = list(sets(bank)[args.set]["inserts"])
    else:
        sys.exit("Give either --set <name> (see --list) or --insert <name>.")

    deriving = needs_reference(bank, names)
    if deriving and not args.reference:
        sys.exit(
            "Give --reference <the full-face image>: {} crop into an existing face.\n"
            "Generate `full-face` first (--set full-face-only), keep the frame you "
            "like, then pass it here.".format(", ".join(deriving)))

    if args.seed is not None:
        base_spec["seed"] = args.seed

    image_bank = bp.load_bank()
    lighting_bank = bl.load_bank()
    camera_bank = bca.load_bank()
    shots = compose_macro_set(bank, image_bank, lighting_bank, camera_bank,
                               base_spec, args.reference, names)

    for shot in shots:
        print("=== {}. {}".format(shot["index"], _shot_label(shot)))
        print(shot["prompt"])
        print()

    if not args.no_write:
        path = write_macro_set(base_spec, shots)
        print("[macro]   {}".format(path), file=sys.stderr)
        print("[next]    python tools/macro_insert_lint.py --macro {}".format(
            str(path).replace(".txt", ".json")), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
