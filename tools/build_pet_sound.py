"""The two extra audio layers the sitcom format needs: a cat voice, and a snap.

sound_bank.json gives every scene three layers - ambience, key effect, accent.
A pet sitcom needs two more, and only one of them is new vocabulary:

  vocal   the animal's own voice, keyed by beat and by which character it is.
          Genuinely new: a repo-wide grep for meow/purr/chirp/hiss/yowl/trill
          returned zero hits anywhere in tools/ before this file existed. The
          app's flagship format is a cat story, and the cat had no voice.
  snap    the tiny sound on the instant-angel cut. NOT new vocabulary - it is
          composed from sound_bank's own `transition` theme, whose description
          is already "MOMENTS: something stops, reverses or resets".

There is no pet_sound_lint.py, deliberately. Every phrase composed here is
scored through the existing sound_lint.py before it is returned, which is the
same contract build_sound.py already has with that linter. A second linter
would be a second copy of the same four rules.

Usage:
    python tools/build_pet_sound.py --check-bank
    python tools/build_pet_sound.py --beat tantrum --setting "a living room"
    python tools/build_pet_sound.py --beat discipline --offscreen-foil

Standard library only.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sound_lint as sl  # noqa: E402
import build_sound as bsd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "pet_sound_bank.json"


def load_bank(path=None):
    with (Path(path) if path else BANK_PATH).open(encoding="utf-8") as fh:
        return json.load(fh)


def roles(bank):
    return bank.get("roles", {})


def _cycle(rows, seed):
    """Cycle rather than sample - the same reasoning build_sound.accent_for
    documents: a random pick per scene collided, and the same sound landing
    twice in a row is worse than a duller one that does not repeat."""
    if not rows:
        return ""
    return rows[int(seed) % len(rows)]


def vocal_for(bank, beat, who="lead", seed=0, offscreen=False):
    """The character's own voice for one beat.

    `offscreen` swaps the whole set: a foil that is an unseen human hand does
    not vocalise, so what carries that beat is what the hand DOES - which is
    still a sound, and still has to pass the same gate.
    """
    group = "foil_offscreen" if (who == "foil" and offscreen) else who
    rows = bank.get("vocalisations", {}).get(group, {}).get(beat, [])
    if not rows:
        rows = bank.get("vocalisations", {}).get(group, {}).get("tantrum", [])
    return _cycle(rows, seed)


def contact_for(bank, seed=0):
    """The comedic paw-tap for the discipline beat."""
    return _cycle(bank.get("contact", {}).get("phrases", []), seed)


def snap_for(sound_bank, seed=0, bank=None):
    """The reset snap, drawn from sound_bank's OWN transition theme.

    Reused, not copied - the same no-duplication rule relight_lint follows for
    lighting phrases and motion_lint follows for motion verbs. `snap_prefer`
    narrows that theme to the rows that read as a comic reset by NUMBER, so the
    phrases themselves still live in exactly one file; without it the cycle
    hands a cat sitcom "Wind ripping through as the past materializes".
    """
    bank = bank or {}
    theme = bank.get("snap_theme", "transition")
    prefer = bank.get("snap_prefer") or []
    if prefer:
        rows = [row for row in sl.by_theme(sound_bank, theme) if row.get("n") in prefer]
        if rows:
            return _cycle(rows, seed)["text"]
    return bsd.accent_for(sound_bank, theme, seed)


def voice_for_beat(bank, beat):
    """Which character's voice plays on this beat, by default.

    Declared in the bank rather than hardcoded here: the kitten drives hook,
    tantrum and reset - it is the one performing - but the FOIL drives
    discipline and lecture, because those are the two beats where the foil is
    the one doing something (story_bank's own `must_do` for discipline is
    "One economical correction from the foil", and for lecture "The mother
    says her piece" - the caption is HER line). Without this, every caller
    defaulted `who` to "lead" and the foil's own vocabulary never played.
    """
    return bank.get("voice_by_beat", {}).get(beat, "lead")


def extra_layers(bank, sound_bank, beat, seed=0, offscreen_foil=False, who=None):
    """[layer dict] ready for build_sound.scene_sound(extra=...).

    `who`, when given, overrides which character vocalises - otherwise
    voice_for_beat() decides. Each layer carries its own label/role/note so
    scene_sound can lint it exactly like one of the three built-in layers
    without knowing what it is.
    """
    cfg = roles(bank)
    out = []

    who = who or voice_for_beat(bank, beat)
    text = vocal_for(bank, beat, who=who, seed=seed, offscreen=offscreen_foil)
    if text:
        out.append({
            "layer": "vocal",
            "label": cfg.get("vocal", {}).get("label", "Cat voice"),
            "role": cfg.get("vocal", {}).get("role", ""),
            "note": cfg.get("vocal", {}).get("note", ""),
            "text": text,
            "after": "ambience",
        })

    if beat == "discipline":
        text = contact_for(bank, seed)
        if text:
            out.append({
                "layer": "contact",
                "label": "Contact",
                "role": "The paw tap itself, on the frame it lands.",
                "note": "safety_lint gates the words; this is the sound they make.",
                "text": text,
                "after": "key",
            })

    if beat == "reset":
        text = snap_for(sound_bank, seed, bank)
        if text:
            out.append({
                "layer": "snap",
                "label": cfg.get("snap", {}).get("label", "Reset snap"),
                "role": cfg.get("snap", {}).get("role", ""),
                "note": cfg.get("snap", {}).get("note", ""),
                "text": text,
                "after": "accent",
            })
    return out


def every_phrase(bank):
    """Every phrase this bank owns, for the --check-bank audit."""
    out = []
    for group, beats in bank.get("vocalisations", {}).items():
        for beat, rows in beats.items():
            for text in rows:
                out.append(("{}/{}".format(group, beat), text))
    for text in bank.get("contact", {}).get("phrases", []):
        out.append(("contact", text))
    return out


def check_bank(bank, sound_bank):
    """[(where, text, score, total, failures)] for every phrase that does not pass."""
    bad = []
    for where, text in every_phrase(bank):
        results = sl.lint(sound_bank, text)
        got, total = sl.score(results)
        if got != total:
            bad.append((where, text, got, total, [d for _k, _l, ok, d in results if not ok]))
    return bad


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="The cat-voice and snap audio layers for the sitcom format.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--beat", default="tantrum", help="which beat to compose for")
    p.add_argument("--who", default=None, choices=["lead", "foil"],
                   help="force a voice; omit to let voice_for_beat() pick it per beat")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--offscreen-foil", action="store_true",
                   help="the foil is an unseen human hand, not a second cat")
    p.add_argument("--check-bank", action="store_true",
                   help="score every phrase in the bank through sound_lint and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()
    sound_bank = sl.load_bank()

    if args.check_bank:
        bad = check_bank(bank, sound_bank)
        for where, text, got, total, failures in bad:
            print("FAIL  {:<22} {}/{}  {!r}".format(where, got, total, text))
            for detail in failures:
                print("        {}".format(detail))
        total_phrases = len(every_phrase(bank))
        print("\n{}/{} phrases pass sound_lint".format(total_phrases - len(bad), total_phrases))
        return 1 if bad else 0

    layers = extra_layers(bank, sound_bank, args.beat, args.seed,
                          args.offscreen_foil, args.who)
    if not layers:
        print("No extra layers for beat {!r}.".format(args.beat))
        return 0
    for layer in layers:
        results = sl.lint(sound_bank, layer["text"])
        got, total = sl.score(results)
        print("{:<9} {:<3} {}".format(layer["layer"], "{}/{}".format(got, total), layer["text"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
