"""Upscale a generated still to 4K before it goes into Videos.

Usage:
    python tools/upscale_image.py --image temp/outputs/images/x.png
    python tools/upscale_image.py --image x.png --out x-4k.png
    python tools/upscale_image.py --image x.png --dry-run

Not a new provider, not new transport: this is generate_image.generate() with
the image being upscaled as the sole reference and a fixed instruction prompt
instead of a user-written one - the bootcamp's own advanced 4K template
(the "PROMPT_BANK"/upscaling lessons), used verbatim rather than reworded.
Nano Banana Pro via Kie is the only provider with reference input, which is
what upscaling an EXISTING image structurally requires - generate() already
refuses a reference on a provider that lacks one, the same message shape as
every other reference-carrying call in this project.

THE RULE THIS TOOL EXISTS FOR (bootcamp, Phase 2 - upscaling): "REMEMBER you
need to UPSCALE before you animate! The higher the quality of the image you
throw into the video generators the more pixels it has to work with, meaning
the end result is overall higher quality." Upscale a still BEFORE it goes to
Videos' Motion tab or Cats' per-scene clip, not after.

Standard library only. No API keys, no network beyond what generate() needs.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# The course's own "advanced" template, verbatim (Phase 2, Upscaling to 4K with
# Nanobanana PRO) - a basic one-line version exists too, but this is the one
# the lesson calls "even better": it preserves identity/composition/lighting
# explicitly, names the micro-detail targets, and bans the specific failure
# mode ("AI plastic skin") rather than a vague "no bad quality".
UPSCALE_PROMPT = (
    "Upscale this image to true ultra-realistic 4K. Preserve the original "
    "composition, lighting, and character identity. Improve micro-details: "
    "skin texture, fabric fibers, hair strands, natural shadows, depth, "
    "reflections, crisp edges. No AI plastic skin, no over-smoothing, no "
    "repainting, no style shift. Maintain the exact original pose and "
    "proportions. Cinematic sharpness with subtle grain."
)


def upscale(path, provider="kie", model=None, base=None, dry_run=False,
            should_cancel=None, on_stage=None, out_name=None):
    """The image at `path` -> a saved 4K path. Same (path, error) contract as
    generate_image.generate() - exactly one of the two is None."""
    return gi.generate(
        provider=provider, prompt=UPSCALE_PROMPT, out_name=out_name,
        references=[path], model=model, base=base, dry_run=dry_run,
        should_cancel=should_cancel, on_stage=on_stage,
    )


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Upscale a still to 4K, ready for Videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--image", required=True, help="the still to upscale")
    p.add_argument("--out", help="output filename inside temp/outputs/images/")
    p.add_argument("--provider", choices=sorted(gi.PROVIDERS), default="kie",
                    help="must support reference images - kie is the default and, "
                         "today, the only one that does")
    p.add_argument("--model", help="override the model id for this call")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument(
        "--dry-run", action="store_true",
        help="build and describe the request without sending it or needing a key",
    )
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    image = Path(args.image)
    if not image.is_absolute():
        image = ROOT / image
    if not image.exists():
        sys.exit("Image not found: {}".format(image))

    if args.dry_run:
        cfg = gi.PROVIDERS[args.provider]
        if not cfg.get("references"):
            print("{} has no reference-image input.".format(cfg["label"]), file=sys.stderr)
            return 3
        print("provider: {} ({})".format(args.provider, cfg["label"]))
        print("image:    {}".format(image))
        print("prompt:   {}".format(UPSCALE_PROMPT))
        return 0

    print("Upscaling with {}...".format(args.provider), file=sys.stderr)
    path, error = upscale(
        str(image), provider=args.provider, model=args.model, base=args.base_url,
        on_stage=lambda message: print(message, file=sys.stderr), out_name=args.out,
    )
    if error:
        print(str(error), file=sys.stderr)
        return error.code

    print("[image] {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
