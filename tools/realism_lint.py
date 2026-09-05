"""Score an image prompt against the eight realism layers from lesson 20.

Usage:
    python tools/realism_lint.py temp/outputs/prompts/avatar-foo-20260828-1430.txt
    echo "a woman, neon glow, 3d render" | python tools/realism_lint.py -

Exit code 0 when the prompt scores 8/8 with no banned terms; 1 otherwise, so a
workflow step can gate on it.

Banned terms are only counted when used *positively* — "no CGI" and "nothing
airbrushed" are how a good prompt talks, and are not flagged.

Standard library only. No API keys, no network.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "prompt_bank.json"

# Detection keywords are deliberately broader than the prompt bank: a prompt may
# say "shot on a full-frame camera at f/1.8" and still satisfy the lens layer.
DETECT = {
    "core": {
        "label": "Core photorealism triggers",
        "keys": [
            "photorealistic", "photorealism", "ultra-realistic", "ultra realistic",
            "real-world photography", "cinematic realism", "lifelike", "true-to-life",
            "natural imperfections", "realistic skin", "hyper-realistic", "hyperrealistic",
        ],
        "fix": "add \"ultra-realistic\" or \"true-to-life textures\" (use 2-3 core triggers)",
    },
    "camera": {
        "label": "Camera language",
        "keys": [
            "dslr", "mirrorless", "film still", "documentary-style", "street photography",
            "studio portrait", "smartphone selfie", "phone camera", "front camera",
            "full-frame", "iphone", "shot on a real",
        ],
        "fix": "name the camera, e.g. \"DSLR photography\" or \"cinematic film still\"",
    },
    "lens": {
        "label": "Lens and optics",
        "keys": [
            "mm lens", "mm prime", "depth of field", "bokeh", "focal length",
            "aperture", "f/1", "f/1.8", "f/2", "wide aperture",
        ],
        "fix": "add \"shot on a 35mm lens, shallow depth of field, natural bokeh\"",
    },
    "lighting": {
        "label": "Real-world lighting",
        "keys": [
            "natural daylight", "natural light", "window light", "golden hour", "overcast",
            "practical lighting", "softbox", "rim light", "realistic shadows",
            "morning light", "sunlight", "led strip", "ceiling light", "bounce light",
            "chiaroscuro",
        ],
        "fix": "add \"soft natural daylight with realistic shadows\" (the highest-value phrase)",
    },
    "texture": {
        "label": "Texture and imperfections",
        "keys": [
            "pores", "micro-detail", "micro detail", "micro-texture", "fabric grain",
            "fabric fibers", "imperfection", "surface detail", "texture", "blemish",
            "freckle", "tactile", "wrinkle", "scratches", "wear",
        ],
        "fix": "add \"visible skin pores, natural fabric grain, slight imperfections\"",
    },
    "colour": {
        "label": "Colour and tone restraint",
        "keys": [
            "color grading", "colour grading", "muted tones", "earthy", "color balance",
            "colour balance", "realistic contrast", "soft highlights", "deep shadows",
            "natural skin tones", "neutral and photographic",
        ],
        "fix": "add \"natural color grading, realistic contrast\"",
    },
    "composition": {
        "label": "Composition",
        "keys": [
            "rule of thirds", "eye-level", "eye level", "candid", "unstaged",
            "natural framing", "separation", "framed from", "close-up", "waist up",
            # Framing terms the motion bank injects as composition overrides
            # (tools/motion_bank.json image_hints). Without these, choosing a
            # low-angle move would silently drop the composition layer to zero.
            "low-angle", "high-angle", "over-the-shoulder", "two-shot",
            "dutch angle", "medium shot", "wide shot", "establishing shot",
            # The optional framing geometries (prompt_bank.json composition_guides).
            # A guide pins the first composition slot, so if it were undetectable
            # here the layer could score zero and a deliberate choice would fail
            # the 8/8 gate.
            "phi grid", "diagonal composition", "leading lines", "triangular composition",
            "golden ratio", "golden spiral", "fibonacci", "harmonic armature",
        ],
        "fix": "add \"eye-level shot, unstaged composition\"",
    },
    "grain": {
        "label": "Grain and capture quality",
        "keys": [
            "film grain", "cinematic grain", "sensor noise", "digital noise",
            "dynamic range", "sharp focus", "not overly polished",
        ],
        "fix": "add \"subtle film grain, sharp focus\"",
    },
}

# A negator only covers the term when nothing separates them. Commas end a
# prompt segment, so "clean but not overly polished, neon glow" is NOT a
# negation of "neon glow" — that one is being asked for.
NEGATION = re.compile(
    r"\b(no|not|nothing|never|zero|without|avoid|avoiding|free of|non)\b[^.;,]{0,24}$"
)


def is_negated(text, index):
    """True when a banned term sits inside a negative instruction ('no CGI')."""
    return bool(NEGATION.search(text[max(0, index - 30):index]))


def find_terms(text, terms):
    """Return (positive_hits, negated_hits) for a list of terms."""
    positive, negated = [], []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        for match in re.finditer(pattern, text):
            (negated if is_negated(text, match.start()) else positive).append(term)
            break
    return positive, negated


def lint(text, bank):
    lower = text.lower()
    present, missing = [], []
    for name in ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]:
        cfg = DETECT[name]
        hit = next((k for k in cfg["keys"] if k in lower), None)
        (present if hit else missing).append((name, cfg, hit))

    banned_hits, _ = find_terms(lower, bank["banned"])
    warn_hits, _ = find_terms(lower, bank["warn"])

    negatives_present = any(
        re.search(r"\b(no|without|avoid|zero)\b[^.;,]{0,20}" + re.escape(word), lower)
        for word in ["cartoon", "cgi", "3d render", "game engine", "plastic", "watermark", "logo"]
    )

    return present, missing, banned_hits, warn_hits, negatives_present


def checks_for(text, bank):
    """`lint()`'s result, reshaped into GateTree's own {key, label, passed, fix,
    ok_text} rows - one row per realism layer plus a synthetic "no banned
    terms" row, in the fixed layer order (not present-then-missing, which
    would reorder the list every time a layer is fixed).
    """
    present, _missing, banned, _warn, _negatives = lint(text, bank)
    hit_by_layer = {name: hit for name, _cfg, hit in present}
    checks = []
    for name in ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]:
        cfg = DETECT[name]
        hit = hit_by_layer.get(name)
        checks.append({
            "key": name,
            "label": cfg["label"],
            "passed": hit is not None,
            "fix": cfg["fix"],
            "ok_text": "Uses \"{}\".".format(hit) if hit else "",
        })
    checks.append({
        "key": "banned",
        "label": "No banned terms",
        "passed": not banned,
        "fix": "Remove or rephrase: " + ", ".join(banned) + "." if banned else "",
        "ok_text": "No banned terms found.",
    })
    return checks


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Score a prompt against the eight realism layers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("prompt_file", help="path to a prompt .txt file, or - for stdin")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if args.prompt_file == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.prompt_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        text = path.read_text(encoding="utf-8")

    if not text.strip():
        sys.exit("Empty prompt.")

    with BANK_PATH.open(encoding="utf-8") as fh:
        bank = json.load(fh)

    present, missing, banned, warns, negatives_present = lint(text, bank)
    score = len(present)

    print("Realism score: {}/8".format(score))
    for name, cfg, hit in present:
        print("  [ok]   {:<28} <- \"{}\"".format(cfg["label"], hit))
    for name, cfg, _ in missing:
        print("  [MISS] {:<28} -> {}".format(cfg["label"], cfg["fix"]))

    if banned:
        print("\nBanned terms used positively (these break realism):")
        for term in banned:
            print("  [BAD]  {}".format(term))
    if warns:
        print("\nSoft warnings (allowed, but they do little on their own):")
        for term in warns:
            print("  [warn] {}".format(term))
    if not negatives_present:
        print(
            "\n  [note] No negative block found. Append: {}".format(
                ", ".join(bank["negatives"])
            )
        )

    ok = score == 8 and not banned
    print("\n{}".format("PASS - ready to generate." if ok else "FAIL - fix the items above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
