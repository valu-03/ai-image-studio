"""Build ElevenLabs sound-effect prompts, and the three-layer sheet for a scene.

Usage:
    python tools/build_sound.py --source "torch flame" --action crackling --place "a temple hallway"
    python tools/build_sound.py --scene "a kitchen at night" --doing "landing on a table" --subject "cat paws"
    python tools/build_sound.py --theme comedy
    python tools/build_sound.py --list

A scene needs three sounds, not one, and they do different jobs:

    ambience   the bed under the whole scene. Continuous, no events.
    key        the action you can actually see happening.
    accent     the punctuation - the cut, the reveal, the punchline.

That is the part people miss. One effect on its own sounds like a sound effect;
three layers sound like a place. The accent is the only one that should be
noticeable, and there should never be two of them in one scene.

Everything composed here is scored by sound_lint before it is returned, so this
module cannot emit a prompt the gate would reject - the same contract the image
side has with realism_lint.

Standard library only. No API keys, no network.
"""

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sound_lint as sl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"

MAX_WORDS = 12


def load_bank():
    return sl.load_bank()


def themes(bank):
    return sl.themes(bank)


def roles(bank):
    return sl.roles(bank)


def examples(bank):
    return sl.examples(bank)


def _trim(text, limit=MAX_WORDS):
    """Keep a prompt inside the length the examples actually run to."""
    words = (text or "").split()
    return " ".join(words[:limit])


def _clean(text):
    return " ".join(str(text or "").split()).strip(" ,.")


def compose(bank, source, action, place=None, treatment=None):
    """Assemble one prompt in the measured pattern: source + action + placement.

    Returns the text only; call `lint` on it, or use `compose_checked`.
    """
    parts = [_clean(source), _clean(action)]
    if place:
        place = _clean(place)
        # The examples say "in a temple hallway", not "temple hallway".
        first = place.split()[0].lower() if place.split() else ""
        if first not in bank.get("placement_words", []):
            place = "in " + place
        parts.append(place)
    if treatment:
        parts.append("with " + _clean(treatment))
    return _trim(" ".join(p for p in parts if p))


def compose_checked(bank, source, action, place=None, treatment=None):
    """(text, passed, results) - composed and immediately scored."""
    text = compose(bank, source, action, place, treatment)
    results = sl.lint(bank, text)
    got, total = sl.score(results)
    return text, got == total, results


def suggest(bank, theme, count=3, seed=0):
    """Example prompts from one theme, chosen reproducibly."""
    rows = sl.by_theme(bank, theme)
    if not rows:
        return []
    rng = random.Random(seed)
    count = min(count, len(rows))
    return [rows[i] for i in sorted(rng.sample(range(len(rows)), count))]


# --------------------------------------------------------------------------- #
# The three layers of a scene
# --------------------------------------------------------------------------- #
_DANGLING = {"on", "in", "at", "of", "the", "a", "an", "with", "by", "to",
             "from", "over", "under", "near", "and", "for"}
AMBIENCE_TAIL = "room tone humming quietly in the background"


def ambience_for(setting, seed=0):
    """The bed. A place, humming - never an event.

    The setting is shortened BEFORE the tail is added, not after. Trimming the
    whole sentence to the word limit chopped the tail instead: a real setting of
    "a small suburban kitchen at night, lit by the open fridge" came out as
    "...lit by the open fridge room tone", which is not a sentence and not a
    sound. The place is the first few words; the rest is scene description that
    a room tone cannot carry anyway.
    """
    setting = _clean(setting) or "an empty room"
    # Strip a leading article so "a kitchen" reads as "kitchen room tone".
    for article in ("a ", "an ", "the "):
        if setting.lower().startswith(article):
            setting = setting[len(article):]
            break
    # Cut at the first comma: "a kitchen at night, lit by the fridge" is a place
    # followed by a lighting note, and only the place belongs in a room tone.
    setting = setting.split(",")[0].strip()
    room = MAX_WORDS - len(AMBIENCE_TAIL.split())
    words = setting.split()[:max(1, room)]
    # Never end on a dangling function word: truncating a long setting produced
    # "derelict warehouse on the room tone", which reads as a mistake.
    while len(words) > 1 and words[-1].lower() in _DANGLING:
        words.pop()
    setting = " ".join(words)
    # "empty room room tone" - do not say room twice.
    tail = AMBIENCE_TAIL
    if setting.lower().endswith("room"):
        tail = tail.split(" ", 1)[1]
    return "{} {}".format(setting, tail)


def key_for(subject, doing, seed=0):
    """The action you can see. This one has to land on the right frame."""
    subject = _clean(subject) or "the subject"
    doing = _clean(doing) or "moving"
    return _trim("{} {}".format(subject, doing))


def accent_for(bank, theme="comedy", seed=0):
    """The punctuation, taken from the course's own examples.

    Cycles rather than samples. Random picks per scene collided - scenes 4 and 5
    of a five-scene story drew the same accent - and the same joke landing twice
    in a row is worse than a duller one that does not repeat.
    """
    rows = sl.by_theme(bank, theme)
    if not rows:
        return "sudden whoosh with dramatic reverb"
    return rows[int(seed) % len(rows)]["text"]


def scene_sound(bank, setting, subject, doing, theme="comedy", seed=0, key_override=None,
                extra=None):
    """The full sheet for one scene, each layer already scored.

    Three layers by default - ambience, key, accent - which is what
    sound_bank.json defines and what every format except `sitcom` wants.

    `key_override`, when given, replaces the auto-composed key-effect text -
    the same "an explicit choice always wins" precedence this project already
    gives shot/lighting/composition. Ambience and accent are untouched: an
    Audio Cue describes the one thing you can see happening, not the room
    tone or the punctuation. Still linted like any other layer - an override
    is not exempt from the gate.

    `extra`, when given, is a list of pre-composed layer dicts - see
    build_pet_sound.extra_layers() - each carrying its own label/role/note and
    an `after` naming the layer it follows. They are linted here, by the same
    call on the same line as the built-in three, so an extra layer cannot
    reach a sound sheet ungated. This function stays ignorant of what they
    are: a cat's voice and a comedy snap are build_pet_sound's business, and
    a second bank's vocabulary has no reason to be named in this file.
    """
    key_override = _clean(key_override)
    rows = [
        ("ambience", ambience_for(setting, seed), None),
        ("key", _trim(key_override) if key_override else key_for(subject, doing, seed), None),
        ("accent", accent_for(bank, theme, seed), None),
    ]
    for item in (extra or []):
        text = _clean(item.get("text"))
        if not text:
            continue
        after = item.get("after", "accent")
        index = next((i for i, (key, _t, _e) in enumerate(rows) if key == after), len(rows) - 1)
        rows.insert(index + 1, (item.get("layer", "extra"), _trim(text), item))

    layers = []
    for key, text, item in rows:
        results = sl.lint(bank, text)
        got, total = sl.score(results)
        cfg = item if item is not None else roles(bank).get(key, {})
        layers.append({
            "layer": key,
            "label": cfg.get("label", key.title()),
            "role": cfg.get("role", ""),
            "note": cfg.get("note", ""),
            "text": text,
            "passed": got == total,
            "score": got,
            "total": total,
            "failures": [d for _, _, ok, d in results if not ok],
            "advice": sl.advice(bank, text),
        })
    return layers


def story_sound(bank, scenes, subject="the cat", theme="comedy", key_overrides=None,
                extra_for=None):
    """A sheet per scene, for a whole story. Scene index seeds the accent so two
    neighbouring scenes do not get the same one.

    `key_overrides`, when given, is a {scene_index: text} dict - a scene with
    no entry (or an empty one) falls back to the auto-composed key effect,
    exactly as before this parameter existed.

    `extra_for`, when given, is a callable taking (index, scene) and returning
    extra layers for that scene - the seam the sitcom format uses to add a cat
    voice on every beat and a snap on the reset. A callable rather than a dict
    because which layers a scene gets depends on its BEAT, which only the
    caller knows; passing None leaves every existing caller untouched.
    """
    key_overrides = key_overrides or {}
    sheets = []
    for index, scene in enumerate(scenes):
        spec = scene.get("spec", {}) if isinstance(scene, dict) else {}
        sheets.append({
            "n": scene.get("n", index + 1),
            "label": scene.get("label", "scene {}".format(index + 1)),
            "layers": scene_sound(
                bank,
                setting=spec.get("setting") or scene.get("setting", ""),
                subject=subject,
                doing=spec.get("action") or scene.get("action", ""),
                theme=theme,
                seed=index,
                key_override=key_overrides.get(index),
                extra=extra_for(index, scene) if extra_for else None,
            ),
        })
    return sheets


def sheet_text(sheets):
    """The sound sheet as something you can paste next to ElevenLabs."""
    lines = []
    for sheet in sheets:
        lines.append("=== {}. {}".format(sheet["n"], sheet["label"]))
        for layer in sheet["layers"]:
            flag = "" if layer["passed"] else "   [{}/{}]".format(
                layer["score"], layer["total"])
            lines.append("  {:<9} {}{}".format(layer["layer"], layer["text"], flag))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_sheet(slug, sheets):
    """Write a sound sheet to temp/outputs/prompts/ and return the path."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "sound-{}-{}.txt".format(slug or "scene", stamp)
    out_path.write_text(sheet_text(sheets), encoding="utf-8")
    return out_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build ElevenLabs sound-effect prompts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--source", help="what makes the sound, e.g. \"torch flame\"")
    p.add_argument("--action", help="what it is doing, e.g. \"crackling\"")
    p.add_argument("--place", help="where it happens, e.g. \"a temple hallway\"")
    p.add_argument("--treatment", help="how it sounds, e.g. \"comedic echo\"")
    p.add_argument("--scene", help="a setting, to build the three layers for it")
    p.add_argument("--subject", default="the cat", help="who or what the scene is about")
    p.add_argument("--doing", help="what the subject is doing, for the key effect")
    p.add_argument("--theme", help="accent theme (see --list)")
    p.add_argument("--list", action="store_true", help="print the themes and roles")
    p.add_argument("--no-write", action="store_true", help="print only, do not write a file")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("THEMES")
        for key, cfg in themes(bank).items():
            print("  {:<12} {:<20} {}".format(key, cfg["label"], cfg["note"]))
        print("\nLAYERS")
        for key, cfg in roles(bank).items():
            print("  {:<10} {}".format(key, cfg["role"]))
            print("  {:<10} {}".format("", cfg["note"]))
        return 0

    if args.scene:
        layers = scene_sound(bank, args.scene, args.subject, args.doing or "moving",
                             theme=args.theme or "comedy")
        sheets = [{"n": 1, "label": args.scene, "layers": layers}]
        print(sheet_text(sheets))
        failed = [l for l in layers if not l["passed"]]
        if not args.no_write:
            path = write_sheet("scene", sheets)
            print("[sheet]   {}".format(path), file=sys.stderr)
        return 1 if failed else 0

    if not args.source or not args.action:
        sys.exit("Give --source and --action, or --scene. See --help.")

    text, passed, results = compose_checked(
        bank, args.source, args.action, args.place, args.treatment)
    print(text)
    for _, label, ok, detail in results:
        if not ok:
            print("[gate]    {}: {}".format(label, detail), file=sys.stderr)
    for note in sl.advice(bank, text):
        print("[note]    {}".format(note), file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
