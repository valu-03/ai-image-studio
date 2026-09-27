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
            # Named real cameras (Camera Language transcript's own recommendations).
            "arri alexa", "sony venice", "red v-raptor", "hasselblad",
        ],
        "fix": "name the camera, e.g. \"DSLR photography\" or \"cinematic film still\"",
    },
    "lens": {
        "label": "Lens and optics",
        "keys": [
            "mm lens", "mm prime", "depth of field", "bokeh", "focal length",
            "aperture", "f/1", "f/1.8", "f/2", "wide aperture",
            # "mm lens" is a plain substring, so ANY word between the
            # millimetres and the lens hid the phrase: "100mm macro portrait
            # lens" and even this app's own portrait preset phrase, "shot on an
            # 85mm portrait lens", both scored this layer at zero. The preset
            # only ever passed on its sibling "shallow depth of field" term.
            # Found by tools/prompt_anatomy.py reporting a false MISS on a real
            # prompt that plainly named its lens.
            "mm macro", "mm portrait",
            # The Capture section's lens-artefact vocabulary
            # (tools/capture_bank.json). Real glass is imperfect and those
            # imperfections are most of what separates a photograph from a
            # clean render - but a repo-wide grep found NONE of these words in
            # any bank, and none of them here either, so the app could neither
            # write them nor see them. Audited per phrase by
            # tests/test_capture_bank.py, not assumed.
            "chromatic aberration", "halation", "vignetting", "vignette",
            "veiling glare", "barrel distortion", "plane of focus", "fringing",
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
            # tools/lighting_bank.json's direction/quality/source/setup/technique
            # vocabulary - each entry there needs a way to be detected here, the
            # same rule every composition guide already has to follow, or a
            # deliberate choice from the new Lighting section would silently
            # fail the 8/8 gate.
            "frontal lighting", "loop lighting", "rembrandt", "split lighting",
            "broad lighting", "short lighting", "butterfly lighting",
            "hard directional light", "soft diffused light",
            "blue-hour", "open shade", "tungsten", "led panel", "fluorescent",
            "practical source", "studio strobe", "rim of light",
            "three-point lighting", "high-key", "low-key",
            "catchlight", "colour temperature", "color temperature", "motivated",
            "falling off", "translucency", "specular highlights", "fill light",
            # The Lighting bank's deepen pass (Lindsay Adler's course): four
            # more named setups and a light-shaping modifier vocabulary
            # (tools/lighting_bank.json). Audited for real, not assumed - see
            # tests/test_lighting_bank.py.
            "clam shell", "checkerboard", "old hollywood", "bounced off",
            "unmodified", "diffusion panel",
        ],
        "fix": "add \"soft natural daylight with realistic shadows\" (the highest-value phrase)",
    },
    "texture": {
        "label": "Texture and imperfections",
        "keys": [
            "pores", "micro-detail", "micro detail", "micro-texture", "fabric grain",
            "fabric fibers", "imperfection", "surface detail", "texture", "blemish",
            "freckle", "tactile", "wrinkle", "scratches",
            # "wear" was dropped. The only bank term that leaned on it is
            # "dust, scratches and wear", and "scratches" already earns that
            # term its point, so nothing became undetectable - while
            # subject_clause()'s "wearing <wardrobe>" stopped filling this
            # layer for free. Same reasoning this list already used to drop
            # "vellus": a key that earns nothing only widens the gate.
            # The Macro Insert bank (tools/macro_insert_bank.json) - skin-macro
            # vocabulary none of the keys above reach. Note "pores" is a plain
            # word and therefore start-anchored (\bpores), so it does NOT fire
            # on "pore-level"; the other five were absent from this table
            # entirely. Same rule every lighting/composition/colour bank phrase
            # already follows - audited per phrase, not assumed, by
            # tests/test_macro_insert.py. "vellus" was dropped from this list
            # before it shipped: every bank phrase using it also says "peach
            # fuzz", so it could never be the sole reason a phrase was seen,
            # and a key that earns nothing only widens the gate.
            "peach fuzz", "subsurface scattering", "pore-level",
            "sebaceous", "tonal variation",
        ],
        "fix": "add \"visible skin pores, natural fabric grain, slight imperfections\"",
    },
    "colour": {
        "label": "Colour and tone restraint",
        "keys": [
            "color grading", "colour grading", "muted tones", "earthy", "color balance",
            "colour balance", "realistic contrast", "soft highlights", "deep shadows",
            "natural skin tones", "neutral and photographic",
            # The Color Grading section's mood/film-look/technique phrases
            # (tools/color_bank.json). Audited for real, not assumed - see
            # tests/test_color_bank.py, including a banned/warn check since
            # this bank's source leans stylised rather than restrained.
            "extreme contrast", "color blocking", "primary colors", "high contrast",
            "amber and sand tones", "candy-colored", "accent colour", "accent color",
            "complementary colour contrast", "complementary color contrast",
            # Capture's highlight-rolloff option (tools/capture_bank.json):
            # tonal handling, not optics, which is why that option overrides
            # its group's layer.
            "rolling off", "short of clipping",
        ],
        "fix": "add \"natural color grading, realistic contrast\"",
    },
    "composition": {
        "label": "Composition",
        "keys": [
            "rule of thirds", "eye-level", "eye level", "candid", "unstaged",
            "natural framing", "separation", "framed from", "close-up", "waist up",
            # Capture's "evidence of a hand" group (tools/capture_bank.json) -
            # proof a person was holding the camera, which reads as framing
            # rather than optics.
            "handheld framing", "off level", "imperfect crop",
            # The Typography section (tools/typography_bank.json) - the first
            # vocabulary in this app for text INSIDE an image. These land on
            # composition rather than getting a layer of their own, and that is
            # not a fudge: reserving an even-toned region of the frame for type
            # IS a compositional instruction, and it is the one that decides
            # whether the type ends up legible. Before this, a repo-wide grep
            # for typography/headline/logo/lockup/type hierarchy found nothing
            # about text in an image anywhere - "\blogo\b" had zero hits in
            # tools/ at all - so the app could describe the photograph and not
            # one word of the advert laid over it. Audited per phrase by
            # tools/typography_lint.py, not assumed.
            "visual hierarchy", "dominant element", "focal point",
            "typographic block", "type occupying", "logo lockup",
            "reading order", "one idea per frame", "clear of the subject",
            "reads at a glance", "carrying the brand",
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
            # The Composition section's opt-in realism techniques
            # (tools/composition_bank.json). Same rule: audited for real, not
            # assumed - see tests/test_composition_bank.py.
            "negative space", "lead room", "midground", "frame within the frame",
            "asymmetrical balance", "scale contrast", "repeating pattern",
            # The Composition bank's atmosphere technique (mined from the
            # Depth & Cinematic Framing guide's own haze/fog/mist section).
            "haze",
            # The Camera Angle bank (tools/camera_angle_bank.json) - side and
            # shot-size phrases not already covered by motion_bank.json's own
            # image-hint framing terms above.
            "worm's-eye", "top-down", "frontal shot", "three-quarter angle",
            "profile shot", "back shot", "point-of-view", "full shot",
        ],
        "fix": "add \"eye-level shot, unstaged composition\"",
    },
    "grain": {
        "label": "Grain and capture quality",
        "keys": [
            "film grain", "cinematic grain", "sensor noise", "digital noise",
            "dynamic range", "sharp focus", "not overly polished",
            # The Capture section's film-stock and exposure vocabulary
            # (tools/capture_bank.json). Naming a stock implies a whole grain
            # structure in two words, and no film stock was nameable anywhere
            # in this app before - "35mm film" existed only as a style_bank
            # label and as prose inside an anatomy_bank example.
            "film stock", "portra", "cinestill", "tri-x", "pro 400h",
            "ektachrome", "slide film", "grain structure", "and white film",
            "luminance noise", "iso", "shutter", "dust speck",
        ],
        "fix": "add \"subtle film grain, sharp focus\"",
    },
}

# A negator only covers the term when nothing separates them. Commas end a
# prompt segment, so "clean but not overly polished, neon glow" is NOT a
# negation of "neon glow" — that one is being asked for.
#
# A colon ends a clause the same way, and leaving it out of this class was a
# real false negation once layer keys started being checked for it: in
# "hard light, not soft: sunlight casting hard shadows", the "not soft:" is
# contrasting, and the sunlight after it is exactly what the prompt is asking
# for - but it fell inside the window and the lighting layer stopped scoring.
# --------------------------------------------------------------------------- #
# The gate is a HUMAN-PORTRAIT detector, and pointed at an animal it did not
# merely miss - it rewarded the wrong answer. Measured before this existed:
#
#   a hand-written cat prompt naming guard hairs, vibrissae, nose leather and
#   slit pupils, with full camera/lens/lighting/colour/grain
#                                                -> 7/8, MISSING texture, FAIL
#   this app's own photoreal cat scene, which reads
#   "realistic skin textures of a ginger tabby cat"        -> 8/8, PASS
#
# ...and deleting all four of story_bank.json's fur phrases left that 8/8
# completely unchanged, because none of them scored anything. The gate was
# certifying a cat for having human skin and rejecting one for having fur.
#
# The fix SWITCHES the texture layer's keys, it does not widen them. Adding fur
# words to the human list would have loosened the shared gate for every human
# prompt in the app - which is precisely what tests/test_story.py's hash pin on
# this file exists to catch. A human prompt's key list is untouched.
DETECT_BY_KIND = {
    "animal": {
        "core": {
            "label": "Core photorealism triggers",
            # The human list's "realistic skin" is gone. On an animal that
            # phrase is not a photorealism trigger, it is a mistake - and it
            # was the single term doing the most damage, because
            # prompt_bank.json's core layer can pick "realistic skin textures"
            # and every photoreal cat scene this app built therefore opened by
            # asking for skin on a cat.
            "keys": [
                "photorealistic", "photorealism", "ultra-realistic", "ultra realistic",
                "real-world photography", "cinematic realism", "lifelike", "true-to-life",
                "natural imperfections", "hyper-realistic", "hyperrealistic",
            ],
            "fix": "add \"ultra-realistic\" or \"true-to-life textures\" (use 2-3 core triggers)",
        },
        "texture": {
            "label": "Coat and fur detail",
            "keys": [
                "fur", "guard hair", "undercoat", "coat", "pelt", "vibrissae",
                "whisker", "nose leather", "paw pad", "tapetum", "slit pupil",
                "dander", "tufting", "down",
                # Kept from the human list: these are surface words that stay
                # true of an animal, and dropping them would make a good prompt
                # that happens to use them score lower, not higher.
                "texture", "tactile", "surface detail", "micro-detail",
            ],
            "fix": "describe the COAT, not skin: "
                   "\"a dense double coat with visible guard hairs, long vibrissae, "
                   "moist nose leather\"",
        },
    },
}

# Human-anatomy words that are simply wrong on an animal. These are why the old
# gate passed - "realistic skin textures", "visible skin pores" and the
# identity lock's "hairline" and "skin tone" were all scoring or riding along
# unchallenged on a cat. Treated exactly like `banned`: flagged only when used
# positively, so "no plastic skin" stays fine.
ANIMAL_BANNED = [
    "skin pores", "skin texture", "skin textures", "skin micro-details",
    "pore-level", "sebaceous", "peach fuzz", "hairline", "skin tone",
    "bone structure",
]


def detect_for(kind="human"):
    """The DETECT table for a subject kind. Unknown kinds fall back to human,
    because a missing or misspelled kind must never silently relax the gate."""
    overrides = DETECT_BY_KIND.get(kind)
    if not overrides:
        return DETECT
    merged = dict(DETECT)
    merged.update(overrides)
    return merged


NEGATION = re.compile(
    r"\b(no|not|nothing|never|zero|without|avoid|avoiding|free of|non)\b[^.;,:]{0,24}$"
)


def is_negated(text, index):
    """True when a banned term sits inside a negative instruction ('no CGI')."""
    return bool(NEGATION.search(text[max(0, index - 30):index]))


_PLAIN_WORD = re.compile(r"[a-z]+")

# A plain single word is anchored at BOTH ends, with an inflection tail, so
# "imperfection" still catches "imperfections" but "texture" no longer fires
# inside "textureless" - a word that means the exact opposite of the layer it
# was filling. Start-anchoring alone (the previous rule) stopped the suffix
# case ("streetwear") but left every prefix case open, and the biggest one was
# not hypothetical: build_prompt.subject_clause() writes "wearing <wardrobe>"
# into nearly every prompt this app composes, so the plain word "wear" was
# silently satisfying the texture layer - the one layer prompt_bank.json itself
# calls the single biggest defence against the plastic AI look.
_INFLECTION = r"(?:s|es|d|ed)?"


def _key_positions(key, text):
    """Every index where a DETECT layer key matches `text`.

    Moved down here from prompt_anatomy._key_positions(), which had to mirror
    this module's own matching rule from the outside in order to answer WHERE a
    key matched rather than merely whether it did. Both callers need the
    position now - a key only fills its layer when it is not sitting inside a
    negation - so the rule lives once, in the module that owns it, and
    prompt_anatomy imports it.

    A multi-token key ("mm lens", "depth of field", "true-to-life") stays a
    plain substring test - it can't hide inside another word, and it needs to
    match a suffix like the "mm lens" in "85mm lens".
    """
    key = key.lower()
    if _PLAIN_WORD.fullmatch(key):
        return [m.start() for m in
                re.finditer(r"\b" + re.escape(key) + _INFLECTION + r"\b", text)]
    out, start = [], 0
    while True:
        index = text.find(key, start)
        if index < 0:
            return out
        out.append(index)
        start = index + 1


def _layer_key_present(key, text):
    """True when a DETECT layer key appears in `text`, negations included.

    Kept as the plain "is it in there" question for callers that genuinely want
    it. lint() does NOT use this - a prompt that says "no bokeh" contains the
    word and must not score for it.
    """
    return bool(_key_positions(key, text))


def layer_hits(keys, text):
    """The layer keys `text` actually earns: present, and not negated.

    is_negated() already existed for banned terms and was never consulted for
    layer keys, so "no bokeh, avoid film grain, no texture" scored lens, grain
    AND texture - the prompt was credited for the three things it was ruling
    out. prompt_anatomy.slot_present() had already hit this exact bug one file
    over ("no CGI look" filling a slot on the word "look") and solved it the
    same way.
    """
    hits = []
    for key in keys:
        for index in _key_positions(key, text):
            if not is_negated(text, index):
                hits.append(key)
                break
    return hits


def find_terms(text, terms):
    """Return (positive_hits, negated_hits) for a list of terms."""
    positive, negated = [], []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        for match in re.finditer(pattern, text):
            (negated if is_negated(text, match.start()) else positive).append(term)
            break
    return positive, negated


LAYER_ORDER = ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]

# How many DISTINCT keys a layer needs before it scores. The default is one,
# which is what every layer used to need. `core` and `texture` ask for the same
# count prompt_bank.json's own `pick` already asks the BUILDER for, because
# those two are the layers that carry photorealism rather than describe a
# camera: one lone word ("lifelike", "texture") was enough to score them, so
# "lifelike iphone aperture sunlight texture high contrast close-up sharp
# focus" - eight unrelated words, no subject, no scene - scored a full 8/8 and
# exited 0. Raising only these two is deliberate: camera and lighting are
# pick:1 in the bank, so requiring more of them would demand vocabulary the
# builder cannot produce.
#
# The counts are MEASURED against the builder, not copied from `pick`. Over 300
# seeds of build_prompt.compose(), the bank's own core picks yielded 3 distinct
# DETECT keys every single time, but its texture picks yielded only 2 in 16% of
# draws - three chosen terms are not three distinct keys when two of them both
# match "texture". A threshold of 3 here would have failed this app's own
# output roughly one time in six, which is a gate calibrated against nothing.
REQUIRED_HITS = {"core": 3, "texture": 2}


def required_hits(name, bank=None):
    """How many distinct keys layer `name` needs. Falls back to the bank's own
    `pick` only where REQUIRED_HITS names the layer, never above it."""
    return REQUIRED_HITS.get(name, 1)


def lint(text, bank, selected=None, kind="human"):
    """Score `text` against the eight layers.

    `kind` is the subject kind - "human" (the default, and what every existing
    caller gets) or "animal", which swaps the texture layer for coat vocabulary
    and adds the human-anatomy words that are wrong on an animal to the banned
    list. See DETECT_BY_KIND for why this switches rather than widens.

    `selected` is build_prompt's chosen-terms dict. When it is supplied the
    layers are judged from those terms instead of from the rendered prompt,
    because build_detailed() wraps them in fixed prose that itself contains
    "bounce light", "micro-texture", "color grading", "separation" and "sensor
    noise" - five of the eight layers scored off the template's own scaffolding
    with every user-selected term blanked out. Free-text callers (the Advisor,
    Cats' Custom Prompt, the CLI) pass nothing and are judged on the text, which
    is the only thing they have.
    """
    lower = text.lower()
    detect = detect_for(kind)
    present, missing = [], []
    for name in LAYER_ORDER:
        cfg = detect[name]
        source = lower
        if selected is not None:
            source = ", ".join(selected.get(name, [])).lower()
        hits = layer_hits(cfg["keys"], source)
        if len(hits) >= required_hits(name, bank):
            present.append((name, cfg, hits[0]))
        else:
            missing.append((name, cfg, None))

    banned_list = list(bank["banned"])
    if kind == "animal":
        banned_list += ANIMAL_BANNED
    banned_hits, _ = find_terms(lower, banned_list)
    warn_hits, _ = find_terms(lower, bank["warn"])

    negatives_present = any(
        re.search(r"\b(no|without|avoid|zero)\b[^.;,]{0,20}" + re.escape(word), lower)
        for word in ["cartoon", "cgi", "3d render", "game engine", "plastic", "watermark", "logo"]
    )

    return present, missing, banned_hits, warn_hits, negatives_present


def checks_for(text, bank, selected=None, kind="human"):
    """`lint()`'s result, reshaped into GateTree's own {key, label, passed, fix,
    ok_text} rows - one row per realism layer plus a synthetic "no banned
    terms" row, in the fixed layer order (not present-then-missing, which
    would reorder the list every time a layer is fixed).

    A tenth row reports the soft `warn` list. It carries passed=True and an
    extra "state" key, because a warn term has never been a failure and making
    it one would reject prompts this app has already shipped - but printing it
    only to the CLI meant the GUI never showed that "8k masterpiece,
    award-winning, trending on artstation" was riding along inside a green
    8/8. GateTree reads passed/fix/ok_text and ignores keys it does not know,
    so the nine-row contract is unchanged for every existing caller.
    """
    present, _missing, banned, warn, _negatives = lint(text, bank, selected, kind)
    hit_by_layer = {name: hit for name, _cfg, hit in present}
    detect = detect_for(kind)
    checks = []
    for name in LAYER_ORDER:
        cfg = detect[name]
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
    checks.append({
        "key": "warn",
        "label": "No empty superlatives",
        "passed": True,
        "state": "warn" if warn else "ok",
        "fix": "These do nothing on their own - cut them: " + ", ".join(warn) + "." if warn else "",
        "ok_text": "No empty superlatives found.",
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
