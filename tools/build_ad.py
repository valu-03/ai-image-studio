"""Build a UGC ad: brief -> five timed beats, each a real shot.

Usage:
    python tools/build_ad.py --product "LumaWash shampoo" --audience "women 25-40 with oily scalps" \
        --platform tiktok --emotion relief
    python tools/build_ad.py --spec temp/resources/characters/ada.json --platform instagram
    python tools/build_ad.py --list

The five beats come from the Social Media AD Structure: call out the pain, make
it relatable, offer a shift, introduce the product, stack proof and urgency.

Timing is the part that matters. The workflow checklist demands the product
appear within 5-10 seconds, and NO percentage split can hold that as the ad gets
longer - an even split puts beat 4 at 18s in a 30-second ad. So the setup is
capped in absolute seconds and beat 4 absorbs whatever is left, because the
product demonstration is the part that should grow with the runtime.

One presenter across all five shots: beat 1 generates the face, beats 2-5 lock
to it. That needs a provider with reference-image input, which today means Kie.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_motion as bm  # noqa: E402
import build_prompt as bp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "ugc_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def platforms(bank):
    return bank.get("platforms", {})


def beats(bank):
    return bank.get("beats", [])


def emotions(bank):
    return bank.get("emotions", {}).get("options", {})


def validate_platform(bank, platform):
    """Return an error message for an unknown platform, or None."""
    if platform and platform not in platforms(bank):
        return "Unknown platform '{}'. Available: {}".format(
            platform, ", ".join(platforms(bank)))
    return None


def validate_emotion(bank, emotion):
    """Return an error message for an unknown emotion, or None."""
    if emotion and emotion not in emotions(bank):
        return "Unknown emotion '{}'. Available: {}".format(
            emotion, ", ".join(emotions(bank)))
    return None


def validate_length(bank, platform, seconds):
    """Return an error message when a length is outside the platform's range."""
    cfg = platforms(bank).get(platform)
    if not cfg or seconds is None:
        return None
    allowed = cfg.get("lengths", [])
    if allowed and (seconds < min(allowed) or seconds > max(allowed)):
        return "{} ads run {}-{}s; you asked for {}s".format(
            cfg["label"], min(allowed), max(allowed), seconds)
    return None


def default_length(bank, platform):
    cfg = platforms(bank).get(platform, {})
    return cfg.get("default_length") or (cfg.get("lengths") or [20])[0]


# --------------------------------------------------------------------------- #
# Timing - the rule the whole design turns on
# --------------------------------------------------------------------------- #
def beat_timings(bank, seconds, platform=None):
    """[(beat, start, duration)] with the product landing inside 5-10 seconds.

    Not a percentage split. The setup (beats 1-3) is capped in absolute seconds
    so that beat 4 starts on time no matter how long the ad runs, the close
    (beat 5) is capped too because a CTA does not need more room in a longer ad,
    and beat 4 takes the remainder.

    Beat 1 is capped again, at the platform's hook window. Without that the two
    rules contradict each other: a 20s TikTok ad's setup budget hands beat 1
    3.1 seconds, and TikTok wants the first clip under 3. The hook window wins,
    and beats 2-3 absorb what beat 1 gives back.
    """
    timing = bank.get("timing", {})
    total = float(seconds)

    setup = min(timing.get("setup_share", 0.52) * total, timing.get("setup_cap", 9.0))
    close = min(timing.get("close_share", 0.22) * total, timing.get("close_cap", 10.0))
    middle = max(total - setup - close, timing.get("product_after", 4.0))
    # Re-derive the close so the three parts always sum to the total exactly.
    close = max(total - setup - middle, 0.0)

    all_beats = beats(bank)
    setup_beats, solution, proof = all_beats[:3], all_beats[3], all_beats[4]
    setup_weight = sum(b.get("weight", 1) for b in setup_beats) or 1

    cfg = platforms(bank).get(platform or "", {})
    hook_cap = min(cfg.get("hook_seconds", 1e9), cfg.get("first_clip_seconds", 1e9))

    shares = [beat.get("weight", 1) / setup_weight for beat in setup_beats]
    durations = [setup * share for share in shares]
    if durations[0] > hook_cap:
        # Give the overflow to beats 2-3 rather than shortening the setup, so
        # beat 4 still starts exactly where the product rule wants it.
        spare = durations[0] - hook_cap
        durations[0] = hook_cap
        tail = sum(shares[1:]) or 1
        for i in range(1, len(durations)):
            durations[i] += spare * (shares[i] / tail)

    out, cursor = [], 0.0
    for beat, duration in zip(setup_beats, durations):
        out.append((beat, round(cursor, 2), round(duration, 2)))
        cursor += duration
    out.append((solution, round(cursor, 2), round(middle, 2)))
    cursor += middle
    out.append((proof, round(cursor, 2), round(close, 2)))
    return out


def product_starts_at(bank, seconds, platform=None):
    """When beat 4 begins - the number the checklist actually asks about."""
    return beat_timings(bank, seconds, platform)[3][1]


# --------------------------------------------------------------------------- #
# Shots - one presenter across five beats
# --------------------------------------------------------------------------- #
def beat_spec(bank, beat, base_spec, platform, reference=None):
    """The character spec for one beat's still.

    Beat 1 invents the presenter. Beats 2-5 lock to the face it produced, which
    is the existing consistent-character mechanism applied along a sequence
    rather than across separate sessions.
    """
    cfg = platforms(bank).get(platform, {})
    spec = dict(base_spec)
    spec["shot"] = base_spec.get("shot") or beat.get("shot")
    if cfg.get("purpose") and not spec.get("purpose"):
        spec["purpose"] = cfg["purpose"]
    if cfg.get("aspect"):
        spec["aspect"] = cfg["aspect"]
    spec["slug"] = "{}-{}".format(
        bp.slugify(base_spec.get("slug") or base_spec.get("subject", "ad")), beat["key"])
    if reference:
        spec["reference"] = reference
        spec["lock_identity"] = True
    return spec


def compose_ad(bank, base_spec, platform, seconds=None, copy=None, reference=None,
               image_bank=None, motion_bank=None):
    """Brief -> the whole ad as a list of shot dicts.

    Each shot carries its timing, its copy, a linted still prompt and a motion
    prompt. `copy` maps a beat key to its lines; anything missing is left empty
    rather than invented here - words are the model's job or the user's, and
    `ad_lint` judges whichever arrives.
    """
    image_bank = image_bank or bp.load_bank()
    motion_bank = motion_bank or bm.load_bank()
    seconds = seconds or default_length(bank, platform)
    copy = copy or {}

    shots = []
    for index, (beat, start, duration) in enumerate(beat_timings(bank, seconds, platform)):
        # Beats after the first lock to the presenter beat 1 established.
        spec = beat_spec(bank, beat, base_spec, platform,
                         reference=reference if (reference and index > 0) else None)
        prompt, layers = bp.compose(image_bank, spec)
        movement = beat.get("movement")
        motion = ""
        if movement in motion_bank.get("movements", {}):
            motion, _ = bm.compose(motion_bank, movement, spec)
        shots.append({
            "n": beat["n"],
            "key": beat["key"],
            "label": beat["label"],
            "role": beat["role"],
            "must_do": beat.get("must_do", ""),
            "sells": beat.get("sells", "feeling"),
            "start": start,
            "duration": duration,
            "end": round(start + duration, 2),
            "copy": copy.get(beat["key"], ""),
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
            "movement": movement,
            "motion_prompt": motion,
        })
    return shots


def ad_script(shots):
    """The copy alone, as a readable script."""
    lines = []
    for shot in shots:
        lines.append("[{:.1f}-{:.1f}s] {}. {}".format(
            shot["start"], shot["end"], shot["n"], shot["label"]))
        lines.append("    " + (shot["copy"] or "(no copy yet)"))
    return "\n".join(lines)


def write_ad(base_spec, platform, shots):
    """Write the whole ad to temp/outputs/prompts/ and return the path."""
    from datetime import datetime

    slug = bp.slugify(base_spec.get("slug") or base_spec.get("subject", "ad"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "ad-{}-{}-{}.txt".format(platform, slug, stamp)

    blocks = []
    for shot in shots:
        blocks.append(
            "=== {}. {}  [{:.1f}-{:.1f}s]\n"
            "copy:   {}\n"
            "still:  {}\n"
            "motion: {}\n".format(
                shot["n"], shot["label"], shot["start"], shot["end"],
                shot["copy"] or "(none)", shot["prompt"], shot["motion_prompt"] or "(none)"))
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return out_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a five-beat UGC ad from a brief.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON (the presenter)")
    p.add_argument("--subject", help="the presenter, if no --spec is given")
    p.add_argument("--product", help="what is being sold")
    p.add_argument("--audience", help="who it is for - age, pain points, desires, niche")
    p.add_argument("--platform", default="tiktok", help="tiktok, youtube, instagram, meta-google")
    p.add_argument("--emotion", help="the feeling to target (see --list)")
    p.add_argument("--seconds", type=int, help="ad length; defaults to the platform's")
    p.add_argument("--setting", help="where the presenter is")
    p.add_argument("--list", action="store_true", help="print platforms, beats and emotions")
    p.add_argument("--no-write", action="store_true", help="print only, do not write a file")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("PLATFORMS")
        for key, cfg in platforms(bank).items():
            print("  {:<14} {:<18} {}  {}s".format(
                key, cfg["label"], cfg["aspect"], "/".join(str(s) for s in cfg["lengths"])))
        print("\nBEATS")
        for beat in beats(bank):
            print("  {}. {:<30} sells the {}".format(beat["n"], beat["label"], beat["sells"]))
        print("\nEMOTIONS")
        for key, cfg in emotions(bank).items():
            print("  {:<20} {}".format(key, cfg["feeling"]))
        return 0

    for error in (validate_platform(bank, args.platform),
                  validate_emotion(bank, args.emotion),
                  validate_length(bank, args.platform, args.seconds)):
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

    if args.setting:
        base_spec["setting"] = args.setting

    seconds = args.seconds or default_length(bank, args.platform)
    shots = compose_ad(bank, base_spec, args.platform, seconds)

    print("{} - {}s, product at {:.1f}s".format(
        platforms(bank)[args.platform]["label"], seconds,
        product_starts_at(bank, seconds, args.platform)), file=sys.stderr)
    print(ad_script(shots))

    if not args.no_write:
        path = write_ad(base_spec, args.platform, shots)
        print("\n[ad] {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
