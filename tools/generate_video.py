"""Generate a video clip from a prompt, and price a batch before you run it.

Usage:
    python tools/generate_video.py --prompt "slow push in on the cat" --duration 5
    python tools/generate_video.py --prompt "..." --image temp/outputs/images/x.png
    python tools/generate_video.py --prompt "..." --mode pro --sound --dry-run
    python tools/generate_video.py --price --duration 5 --count 7

Kling 3.0 through Kie, which is the same job API the images already use:

    POST /api/v1/jobs/createTask     {"model": "kling-3.0/video", "input": {...}}
    GET  /api/v1/jobs/recordInfo     until state == success, then download a URL

So this file holds NO transport of its own. Submitting, polling, downloading,
credentials, the User-Agent and the reference upload all come from
generate_image.py - if the two ever disagreed about how Kie is spoken to, one of
them would be wrong.

THE PART THAT COSTS MONEY:

    duration    "3" to "15", a STRING, whole seconds
    mode        std | pro | 4K    - pro is the higher-resolution tier
    sound       native audio, and roughly doubles the per-second price

Defaults are std and sound off: the cheapest combination that still looks right.
Sound is off by default for a second reason - the Sound section already builds
three ElevenLabs layers per scene, and two soundtracks fight.

Image-to-video is the point for a story: pass the scene's generated still as
`--image` and the clip starts from a frame that already has the right cat in it.

Key values are never printed, logged, or written to temp/. Standard library only.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "temp" / "outputs" / "videos"
# Overridable so a suite can price against a disposable copy - the same reasoning
# as history.py's AIVS_HISTORY_FILE. Without this seam, ANY code path that calls
# save_measured()/record_actual() with no explicit `path=` - including a real
# clip generated once through the CLI to verify a feature, exactly as intended -
# permanently overwrites the tracked seed file with a real charge, and every test
# run after that silently assumes numbers that are no longer the seed.
PRICING_PATH = Path(os.environ.get("AIVS_PRICING_FILE")
                    or (Path(__file__).resolve().parent / "pricing.json"))

DEFAULT_MODEL = "kling-3.0/video"
MODEL_VAR = "KIE_VIDEO_MODEL"

# Kling 3.0's documented input enums. An unknown value is dropped and reported,
# never sent hopefully - a rejected request costs a round trip to discover.
DURATION_MIN, DURATION_MAX = 3, 15
ASPECTS = ("16:9", "9:16", "1:1")
MODES = ("std", "pro", "4K")

DEFAULTS = {"aspect_ratio": "9:16", "mode": "std", "sound": False, "multi_shots": False}


def load_pricing():
    with PRICING_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# What it will cost, before it costs it
# --------------------------------------------------------------------------- #
def estimate(model, units, pricing=None, **options):
    """(credits, confidence, note) for `units` images or seconds.

    `units` is images for an image model and seconds for a video one, which is
    what the table's `unit` field says. Returns None credits when the model is
    not in the table rather than inventing a number.
    """
    pricing = pricing or load_pricing()
    cfg = (pricing.get("models") or {}).get(model)
    if not cfg:
        return None, "unknown", "{} is not in pricing.json".format(model)

    total = float(cfg.get("credits_per_unit", 0)) * float(units)
    for name, table in (cfg.get("multipliers") or {}).items():
        value = options.get(name)
        if value is None:
            continue
        key = str(value).lower() if isinstance(value, bool) else str(value)
        for candidate, factor in table.items():
            if str(candidate).lower() == key.lower():
                total *= float(factor)
                break
    return round(total), cfg.get("confidence", "estimated"), cfg.get("note", "")


def price_note(model, units, credits_left=None, pricing=None, **options):
    """One line for the button that is about to spend it."""
    total, confidence, _ = estimate(model, units, pricing, **options)
    if total is None:
        return "cost unknown for {}".format(model)
    text = "~{:,} credits ({})".format(total, confidence)
    if credits_left is not None:
        text += " · you have {:,}".format(int(credits_left))
        if total > credits_left:
            text += " - not enough"
    return text


def save_measured(model, units, credits_used, path=None):
    """Write a measured per-unit price back to pricing.json."""
    path = Path(path or PRICING_PATH)
    pricing = record_actual(model, units, credits_used, path=path)
    path.write_text(json.dumps(pricing, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return pricing


def record_actual(model, units, credits_used, pricing=None, path=None):
    """Replace a guessed per-unit price with one the provider actually charged.

    This is the whole point of the `confidence` field: the seeded numbers come
    off a marketing page, and the first real job replaces them with a fact.
    """
    path = Path(path or PRICING_PATH)
    pricing = pricing or json.loads(path.read_text(encoding="utf-8"))
    cfg = (pricing.get("models") or {}).get(model)
    if not cfg or not units or credits_used is None:
        return pricing
    cfg["credits_per_unit"] = round(float(credits_used) / float(units), 3)
    cfg["confidence"] = "measured"
    cfg["measured_on"] = datetime.now().strftime("%Y-%m-%d")
    return pricing


# --------------------------------------------------------------------------- #
# The request
# --------------------------------------------------------------------------- #
def build_submit(base, model, key, prompt, image_urls=(), duration=5,
                 aspect_ratio=None, mode=None, sound=None, multi_shots=None):
    """(url, body, headers, dropped) for one Kling 3.0 job."""
    dropped = []

    def pick(value, allowed, default, name):
        if value is None:
            return default
        text = str(value).strip()
        for option in allowed:
            if text.lower() == option.lower():
                return option
        dropped.append("{}={}".format(name, text))
        return default

    try:
        seconds = int(duration)
    except (TypeError, ValueError):
        dropped.append("duration={}".format(duration))
        seconds = 5
    if not DURATION_MIN <= seconds <= DURATION_MAX:
        dropped.append("duration={}".format(seconds))
        seconds = max(DURATION_MIN, min(DURATION_MAX, seconds))

    payload = {
        "prompt": prompt,
        # A STRING, per the spec. Sending the integer is the kind of thing that
        # fails at the provider for a reason the error message will not explain.
        "duration": str(seconds),
        "aspect_ratio": pick(aspect_ratio, ASPECTS, DEFAULTS["aspect_ratio"], "aspect_ratio"),
        "mode": pick(mode, MODES, DEFAULTS["mode"], "mode"),
        "sound": bool(DEFAULTS["sound"] if sound is None else sound),
        "multi_shots": bool(DEFAULTS["multi_shots"] if multi_shots is None else multi_shots),
    }
    if image_urls:
        payload["image_urls"] = list(image_urls)

    url = "{}/api/v1/jobs/createTask".format(base.rstrip("/"))
    return url, {"model": model, "input": payload}, gi.kie_headers(key), dropped


def _resolve(model=None, base=None):
    cfg = gi.PROVIDERS["kie"]
    key = gi.env_value(cfg["key"])
    model = model or gi.env_value(MODEL_VAR) or DEFAULT_MODEL
    return cfg, key, model, base or cfg["base"]


def generate(prompt="", out_name=None, image=None, duration=5, aspect_ratio=None,
             mode=None, sound=None, model=None, base=None, dry_run=False,
             should_cancel=None, on_stage=None):
    """Prompt -> saved .mp4 path. Returns (path, error, credits_used).

    Mirrors generate_image.generate's contract deliberately: exactly one of path
    and error is None, and the caller never has to know how Kie is spoken to.
    """
    def stage(message):
        if on_stage:
            on_stage(message)

    cfg, key, model, base = _resolve(model, base)
    if not key and not dry_run:
        return None, gi.GenerationError(
            "{} not set in {} - cannot reach Kling.\nGet a key at {}\n\nMeanwhile, "
            "paste this prompt into Kling's own interface:\n\n{}".format(
                cfg["key"], gi.ENV_PATH, cfg["where"], prompt), 1), None

    image_urls = []
    try:
        if image:
            stage("Uploading the first frame...")
            upload_base = base if base != cfg["base"] else None
            image_urls.append(gi.upload_kie_reference(key, image, upload_base))
        url, body, headers, dropped = build_submit(
            base, model, key or "DRY-RUN", prompt, image_urls, duration,
            aspect_ratio, mode, sound)
    except (FileNotFoundError, RuntimeError) as exc:
        return None, gi.GenerationError(str(exc), 3), None
    if dropped:
        stage("Ignored (not a documented value): " + ", ".join(dropped))

    if dry_run:
        return url, None, None

    stage("Submitting to {}...".format(model))
    status, payload, raw = gi.post_json(url, body, headers)
    if status != 200:
        return None, gi.GenerationError("API error {}: {}".format(
            status, gi.describe_api_error(payload, raw)), 4), None
    task_id = gi.parse_kie_submit(payload)
    if not task_id:
        return None, gi.GenerationError(
            "No task id in the reply: {}".format((raw or "")[:200]), 4), None

    used = {"credits": None}

    def fetch():
        poll_url, poll_headers = gi.build_kie_status(base, task_id, key)
        code, poll_payload, poll_raw = gi.get_json(poll_url, poll_headers)
        # Without this a token expiry / 429 / 500 mid-render reads as "keep
        # polling" until JOB_TIMEOUT (5 min) and is then reported as a
        # timeout - the wrong diagnosis. The image path checks the same way.
        if code >= 400:
            raise gi.GenerationError("Status check failed {}: {}".format(
                code, gi.describe_api_error(poll_payload, poll_raw)), 3)
        if used["credits"] is None:
            used["credits"] = gi.credits_consumed(poll_payload)
        return gi.parse_kie_status(poll_payload)

    stage("Kling is generating - this takes minutes, not seconds...")
    try:
        # poll() raises rather than returning an error, and it is shared with the
        # image path - so the cancel, timeout and failure behaviour is identical
        # for a clip and for a still.
        video_url = gi.poll(fetch, should_cancel=should_cancel, on_stage=on_stage)
        stage("Downloading...")
        data, _mime = gi.download(video_url)
    except gi.GenerationError as exc:
        return None, exc, used["credits"]
    except RuntimeError as exc:
        return None, gi.GenerationError(str(exc), 4), used["credits"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or "clip-{}.mp4".format(datetime.now().strftime("%Y%m%d-%H%M%S"))
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    path = OUT_DIR / name
    path.write_bytes(data)
    return path, None, used["credits"]


# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file")
    parser.add_argument("--image", help="first frame, for image-to-video")
    parser.add_argument("--duration", type=int, default=5,
                        help="whole seconds, {}-{}".format(DURATION_MIN, DURATION_MAX))
    parser.add_argument("--aspect", choices=ASPECTS, default=DEFAULTS["aspect_ratio"])
    parser.add_argument("--mode", choices=MODES, default=DEFAULTS["mode"])
    parser.add_argument("--sound", action="store_true", help="native audio (about 2x price)")
    parser.add_argument("--out", help="output filename inside temp/outputs/videos/")
    parser.add_argument("--model", help="override the model id for this call")
    parser.add_argument("--dry-run", action="store_true", help="print the request, send nothing")
    parser.add_argument("--price", action="store_true", help="estimate the cost and stop")
    parser.add_argument("--count", type=int, default=1, help="how many clips, for --price")
    args = parser.parse_args(argv)

    _cfg, _key, model, _base = _resolve(args.model)

    if args.price:
        seconds = args.duration * args.count
        total, confidence, note = estimate(model, seconds, mode=args.mode, sound=args.sound)
        print("{} clip(s) x {}s = {}s".format(args.count, args.duration, seconds))
        print("mode={}  sound={}".format(args.mode, args.sound))
        print("~{} credits ({})".format(total, confidence))
        left, error = gi.credits()
        print("balance: {}".format(left if error is None else "unknown ({})".format(error)))
        if note:
            print("\n{}".format(note))
        return 0

    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if not prompt.strip():
        sys.exit("Nothing to generate: pass --prompt or --prompt-file.")

    if args.dry_run:
        url, body, _headers, dropped = build_submit(
            _base, model, "DRY-RUN", prompt,
            ["https://example.invalid/first-frame.png"] if args.image else [],
            args.duration, args.aspect, args.mode, args.sound)
        print("POST {}".format(url))
        print(json.dumps(body, indent=2))
        if dropped:
            print("ignored: {}".format(", ".join(dropped)))
        return 0

    path, error, used = generate(
        prompt=prompt, out_name=args.out, image=args.image, duration=args.duration,
        aspect_ratio=args.aspect, mode=args.mode, sound=args.sound, model=args.model,
        on_stage=lambda message: print(message, file=sys.stderr))
    if error:
        print(str(error), file=sys.stderr)
        return getattr(error, "code", 4)
    print("[video] {}".format(path))
    if used is not None:
        print("[credits] {}".format(used))
    return 0


if __name__ == "__main__":
    sys.exit(main())
