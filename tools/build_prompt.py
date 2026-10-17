"""Build a layered, photorealistic image prompt from a character spec.

Implements the eight realism layers from the AI Video Bootcamp Phase 2 cheat-sheet
(lesson 20) using the vocabulary in tools/prompt_bank.json.

Usage:
    python tools/build_prompt.py --spec temp/resources/characters/<slug>.json
    python tools/build_prompt.py --spec <path> --detailed
    python tools/build_prompt.py --subject "a woman in her thirties" --shot selfie
    python tools/build_prompt.py --spec <path> --seed 3      # different word choices

Standard library only. No API keys, no network.
"""

import argparse
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_contact as bct  # noqa: E402
import build_evidence as bev  # noqa: E402
import build_face_detail as bfd  # noqa: E402
import build_material as bmt  # noqa: E402
import build_scene_light as bsl  # noqa: E402
import build_skin_features as bsf  # noqa: E402
import build_snapshot as bsn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "prompt_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"

LAYER_ORDER = ["core", "camera", "lens", "lighting", "texture", "colour", "composition", "grain"]


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


_SCENE_LIGHT_BANK = None


def _scene_light_bank():
    global _SCENE_LIGHT_BANK
    if _SCENE_LIGHT_BANK is None:
        _SCENE_LIGHT_BANK = bsl.load_bank()
    return _SCENE_LIGHT_BANK


_FACE_BANK = None
_EVIDENCE_BANK = None
_SKIN_BANK = None


def _skin_bank():
    global _SKIN_BANK
    if _SKIN_BANK is None:
        _SKIN_BANK = bsf.load_bank()
    return _SKIN_BANK


def _face_bank():
    global _FACE_BANK
    if _FACE_BANK is None:
        _FACE_BANK = bfd.load_bank()
    return _FACE_BANK


def _evidence_bank():
    global _EVIDENCE_BANK
    if _EVIDENCE_BANK is None:
        _EVIDENCE_BANK = bev.load_bank()
    return _EVIDENCE_BANK


def apply_subject_detail(spec):
    """Resolve the `face_detail`, `lived_in` and `skin_features` flags against THIS spec.

    Resolved here, at compose time, rather than by the form that set the
    flag: Variants copies one spec and changes its seed or its shot, and a
    detail baked in beforehand would give every seed the same details and a
    full-body angle the close-up's pores. After apply_purpose(), so a shot
    the purpose supplies picks the tier too.

    All land as non-layer overrides (free tail, additive). An explicit
    overrides["face_detail"], ["evidence"] or ["skin_features"] already
    present wins - a deliberate pick is never replaced by an automatic one.
    """
    if not (spec.get("face_detail") or spec.get("lived_in") or spec.get("skin_features")):
        return spec
    overrides = dict(spec.get("overrides") or {})
    kind = bev.subject_kind(_evidence_bank(), spec.get("subject", ""))
    if spec.get("skin_features") and "skin_features" not in overrides:
        phrase, _skipped = bsf.for_spec(_skin_bank(), spec, kind=kind)
        if phrase:
            overrides["skin_features"] = [phrase]
    if spec.get("face_detail") and "face_detail" not in overrides:
        phrase, _tier, _kind = bfd.face_detail(
            _face_bank(), spec.get("subject", ""), spec.get("shot", ""),
            spec.get("shot_custom", ""), spec.get("seed", 0), kind=kind)
        if phrase:
            overrides["face_detail"] = [phrase]
    if spec.get("lived_in") and "evidence" not in overrides and "evidence_auto" not in overrides:
        phrase, _warnings = bev.compose_evidence(
            _evidence_bank(), kind, seed=spec.get("seed", 0))
        if phrase:
            overrides["evidence_auto"] = [phrase]
    merged = dict(spec)
    merged["overrides"] = overrides
    return merged


def apply_scene_light(spec):
    """With `scene_lighting` set, add the scene's light physics to the tail.

    Source, bounce and shadows ride overrides["scene_light"] - a non-layer
    override, so free_overrides() appends it and it can only ADD to a realism
    score. When the lighting layer was chosen explicitly the source is left
    out (naming a second light would contradict it); bounce and shadows are
    physics and hold under any light. A caller that already set
    overrides["scene_light"] wins. Without the flag the spec is returned as is.
    """
    if not spec.get("scene_lighting"):
        return spec
    overrides = dict(spec.get("overrides") or {})
    if "scene_light" in overrides:
        return spec
    phrase, _place, _time = bsl.scene_light(
        _scene_light_bank(), spec.get("setting", ""), spec.get("seed", 0),
        include_source="lighting" not in overrides)
    if not phrase:
        return spec
    overrides["scene_light"] = [phrase]
    merged = dict(spec)
    merged["overrides"] = overrides
    return merged


_CONTACT_BANK = None
_MATERIAL_BANK = None
_GENERIC_MATERIAL = None


def _contact_bank():
    global _CONTACT_BANK
    if _CONTACT_BANK is None:
        _CONTACT_BANK = bct.load_bank()
    return _CONTACT_BANK


def _material_bank():
    global _MATERIAL_BANK
    if _MATERIAL_BANK is None:
        _MATERIAL_BANK = bmt.load_bank()
    return _MATERIAL_BANK


def _generic_material():
    global _GENERIC_MATERIAL
    if _GENERIC_MATERIAL is None:
        _GENERIC_MATERIAL = bmt.generic_phrase(_material_bank())
    return _GENERIC_MATERIAL


def apply_physical(spec):
    """Resolve the `contact_detail` and `material_detail` flags against THIS spec.

    Weight and contact (build_contact) and the scene's own materials
    (build_material), read from the spec's text at compose time like the
    other realism flags, so a Variants seed gets its own default. Both land as
    non-layer overrides (free tail, additive); an explicit overrides["contact"]
    or overrides["material"] already present wins.

    When materials matched, lighting_bank.json's generic "material response"
    technique is taken out of an explicit lighting choice - the specific lines
    replace it, rather than the prompt saying the same thing twice.
    """
    if not (spec.get("contact_detail") or spec.get("material_detail")):
        return spec
    overrides = dict(spec.get("overrides") or {})
    if spec.get("contact_detail") and "contact" not in overrides:
        kind = bev.subject_kind(_evidence_bank(), spec.get("subject", ""))
        phrase, _keys = bct.read_contact(_contact_bank(), spec, kind=kind)
        if phrase:
            overrides["contact"] = [phrase]
    if spec.get("material_detail") and "material" not in overrides:
        phrase, _keys = bmt.read_materials(_material_bank(), spec)
        if phrase:
            overrides["material"] = [phrase]
            generic = _generic_material()
            lighting = overrides.get("lighting")
            if isinstance(lighting, str):
                lighting = [lighting]
            if lighting and any(generic in str(t) for t in lighting):
                kept = [bmt.without_generic(str(t), generic) for t in lighting]
                kept = [t for t in kept if t]
                if kept:
                    overrides["lighting"] = kept
                else:
                    overrides.pop("lighting")
    merged = dict(spec)
    merged["overrides"] = overrides
    return merged


_SNAPSHOT_BANK = None


def _snapshot_bank():
    global _SNAPSHOT_BANK
    if _SNAPSHOT_BANK is None:
        _SNAPSHOT_BANK = bsn.load_bank()
    return _SNAPSHOT_BANK


def apply_snapshot(bank, spec):
    """Resolve the `snapshot`, `background_life` and `moment` flags (build_snapshot).

    `snapshot`, when nothing deliberate chose the look: camera and lens from
    the bank's own phone preset (as overrides), `_phone_snapshot` so
    select_layers() drops the core pick's cinema words, and a "who took it"
    line. The other two add a line each. All lines are non-layer overrides
    on the free tail; an explicit one already present wins.
    """
    if not (spec.get("snapshot") or spec.get("background_life") or spec.get("moment")):
        return spec
    sb = _snapshot_bank()
    overrides = dict(spec.get("overrides") or {})
    merged = dict(spec)
    kind = bev.subject_kind(_evidence_bank(), spec.get("subject", ""))
    seed = spec.get("seed", 0)
    if spec.get("snapshot") and "snapshot" not in overrides:
        mode = bsn.snapshot_mode(sb, spec, custom_shot=bool(custom_shot(spec)))
        if mode != "skip":
            if mode == "phone":
                overrides.update(bsn.phone_layers(sb, bank))
            merged["_phone_snapshot"] = True
            overrides["snapshot"] = [bsn.who_line(sb, kind, seed, mode)]
    if spec.get("background_life") and "background" not in overrides:
        phrase, _place = bsn.background_line(sb, spec)
        if phrase:
            overrides["background"] = [phrase]
    if spec.get("moment") and "moment" not in overrides:
        phrase, _key = bsn.moment_line(sb, spec, kind)
        if phrase:
            overrides["moment"] = [phrase]
    merged["overrides"] = overrides
    return merged


def pick(rng, terms, count, weights=None):
    """Pick `count` terms, preserving the bank's ordering for readability.

    With `weights` (term -> multiplier from history.py), selection is biased
    toward terms that have rated well, using Efraimidis-Spirakis weighted
    sampling without replacement. Unweighted, every term is equally likely.
    """
    count = min(count, len(terms))
    if not weights:
        chosen = rng.sample(range(len(terms)), count)
    else:
        keyed = []
        for index, term in enumerate(terms):
            weight = max(1e-6, float(weights.get(term, 1.0)))
            # random() ** (1/w): larger weight -> key nearer 1 -> picked first.
            keyed.append((rng.random() ** (1.0 / weight), index))
        keyed.sort(reverse=True)
        chosen = [index for _, index in keyed[:count]]
    return [terms[i] for i in sorted(chosen)]


def custom_shot(spec):
    """Free-text shot description, or "" — see apply_custom_shot()."""
    return str(spec.get("shot_custom") or "").strip()


def custom_guide(spec):
    """Free-text composition description, or "" — see apply_composition_guide()."""
    return str(spec.get("composition_guide_custom") or "").strip()


def custom_purpose(spec):
    """A user-named placement, or "".

    Unlike `custom_shot()` and `custom_guide()`, this one contributes NOTHING
    to the composed prompt, and that is the whole design rather than an
    omission. A purpose never appears in a prompt: its only job is to supply
    `shot` and `aspect` when the spec is silent (see apply_purpose()), and a
    name the bank has never seen has no shot or aspect to supply. So a custom
    purpose is metadata - it travels with the spec, it reaches the model
    through brief._describe_current(), and it is recorded in history. What it
    must never do is make the app guess a crop on the user's behalf.
    """
    return str(spec.get("purpose_custom") or "").strip()


SKIN_WORDS = re.compile(r"\b(skin|pores?)\b", re.IGNORECASE)
# A focal length or a named lens - "100mm macro lens", "85 mm" - in a typed shot.
TYPED_LENS = re.compile(r"\b\d{2,3}\s?mm\b|\blens\b|\bmacro\b", re.IGNORECASE)
FOCAL_TERM = re.compile(r"\d+mm", re.IGNORECASE)


def _kind(spec):
    """The subject's kind ('human', 'animal', 'object', 'place') - an explicit
    spec["subject_kind"] wins ("person" is human), else read from the Subject."""
    explicit = spec.get("subject_kind")
    if explicit:
        return "human" if explicit == "person" else explicit
    return bev.subject_kind(_evidence_bank(), spec.get("subject", ""))


def select_layers(bank, spec, rng, weights=None):
    """Choose the vocabulary for each of the eight layers.

    Precedence: spec["overrides"] > shot preset > weighted pick from the bank.
    """
    layers = bank["layers"]
    # A custom shot suppresses the preset entirely: the two are alternatives,
    # and the typed one is the more explicit of them.
    preset = {} if custom_shot(spec) else bank["shot_presets"].get(spec.get("shot", ""), {})
    overrides = spec.get("overrides", {})
    selected = {}

    for name in LAYER_ORDER:
        if name in overrides:
            value = overrides[name]
            selected[name] = [value] if isinstance(value, str) else list(value)
            continue
        if name in preset:
            value = preset[name]
            selected[name] = [value] if isinstance(value, str) else list(value)
            continue
        cfg = layers[name]
        terms = cfg["terms"]
        # Scene-matched light: on auto, narrow the lighting pick to the terms
        # the Setting allows (a bar at night never draws golden hour). It is
        # the same weighted pick over a subset of the bank's own terms, so
        # ratings still steer it - and a spec without the flag is untouched.
        if name == "lighting" and spec.get("scene_lighting"):
            terms = bsl.allowed_terms(_scene_light_bank(), spec.get("setting", ""), terms)
        # A phone snapshot is not a cinema frame: same weighted pick, minus
        # the core and grain words that pull toward a polished film look.
        if spec.get("_phone_snapshot"):
            skip = set(_snapshot_bank()["snapshot"]["layer_skip"].get(name, []))
            terms = [t for t in terms if t not in skip] or terms
        # Skin and pores are human: on a cat, a bottle or a street they are
        # wrong words (realism_lint bans them on an animal outright). Same
        # weighted pick over the remaining core / texture terms.
        # A typed shot that names its own lens ("100mm macro lens") owns the
        # focal length: drawing "shot on a 35mm lens" as well would put two
        # lenses in one prompt. Depth of field and bokeh terms still apply.
        if name == "lens" and TYPED_LENS.search(custom_shot(spec)):
            terms = [t for t in terms if not FOCAL_TERM.search(t)] or terms
        # A close shot - a beauty portrait, a macro, a headshot - is lit
        # softly; chiaroscuro or harsh noon sun hides exactly the skin and eye
        # detail the close tier asks for (face_detail_bank.json).
        if name == "lighting" and bfd.shot_tier(
                _face_bank(), spec.get("shot", ""), custom_shot(spec)) == "close":
            skip = set(_face_bank()["shot_tiers"].get("close_lighting_skip", []))
            terms = [t for t in terms if t not in skip] or terms
        if name in ("core", "texture") and _kind(spec) != "human":
            terms = [t for t in terms if not SKIN_WORDS.search(t)] or terms
        # `always` terms are appended only when we chose the layer ourselves —
        # an override or preset is taken as authoritative.
        selected[name] = (
            pick(rng, terms, cfg.get("pick", 2), weights) + cfg.get("always", [])
        )

    selected["camera"] = apply_custom_shot(bank, spec, selected["camera"])
    selected["composition"] = apply_composition_guide(bank, spec, selected["composition"])
    return selected, preset


def free_overrides(spec):
    """Values of any spec["overrides"] entry that isn't one of the eight
    layers (e.g. "style" from the Style toolkit). Without this they'd be
    silently dropped - select_layers only walks LAYER_ORDER. They join the
    free "extra" segment, the same tail spec["extra"] already lands in."""
    out = []
    for name, value in (spec.get("overrides") or {}).items():
        if name in LAYER_ORDER:
            continue
        out.extend([value] if isinstance(value, str) else list(value))
    return out


def guides(bank):
    """The composition guides table: key -> {label, phrase, note}."""
    return bank.get("composition_guides", {}).get("guides", {})


def apply_custom_shot(bank, spec, chosen):
    """Put a typed shot description in the camera slot, replacing the bank's.

    The pin-vs-replace rule this project already uses for lighting: camera is
    `pick: 1`, so an explicit value can simply take the slot without throwing
    anything away. (Composition is `pick: 2`, which is why a guide pins instead.)

    An explicit `overrides["camera"]` still wins — it is the lower-level, more
    deliberate control, and nothing should silently outrank it.
    """
    phrase = custom_shot(spec)
    if not phrase or "camera" in spec.get("overrides", {}):
        return chosen
    return [phrase]


def apply_composition_guide(bank, spec, chosen):
    """Pin the chosen framing geometry to the front of the composition layer.

    A guide is a *pin*, not a replacement. Lighting is `pick: 1`, so an explicit
    source can simply take the slot; composition is `pick: 2`, and replacing the
    whole layer would throw away half of it. So the guide takes the first slot,
    the terms already chosen fill the rest, and the layer keeps its normal
    length — which is what keeps the linter's composition check scoring.

    That last point is what makes free text safe here: whatever is typed, a bank
    term still occupies the remaining slot, so a custom composition can never
    cost the prompt its composition layer. A custom *shot* has no such
    protection, because replacing is the correct move for a `pick: 1` layer.

    It is applied last on purpose: it therefore outranks a shot preset and a
    movement's image hint, both of which are defaults, and matches the rule used
    everywhere else — an explicit choice wins.
    """
    # Typed text beats a picked guide: it is the more specific of the two, and
    # the editor only ever sends one of them anyway.
    named = guides(bank).get(spec.get("composition_guide", ""))
    phrase = custom_guide(spec) or (named["phrase"] if named else "")
    if not phrase:
        return chosen
    keep = bank["layers"]["composition"].get("pick", 2) - 1
    # Drop any term the guide already says, so "rule of thirds" cannot appear twice.
    rest = [t for t in chosen if t not in phrase and phrase not in t]
    return [phrase] + rest[:max(0, keep)]


# Prepended when a prompt must reproduce an existing face rather than invent
# one. This is the whole mechanism behind character consistency.
LOCK_COMPACT = (
    "the exact same person as in the reference image — identical face, bone structure, "
    "eye colour, hairline, skin tone and distinguishing marks"
)
LOCK_DETAILED = (
    "The subject is the exact same person as in the reference image: identical facial "
    "structure, eye colour, hairline, skin tone and distinguishing marks. Only the scene, "
    "wardrobe, pose and camera change — the face must not be restyled, idealised or "
    "made younger."
)
LOCK_TAIL = "identity locked to the reference image"

# The same mechanism for a subject that is not a person. Cats' story formats
# reference-lock every scene after the first, and they did it through
# LOCK_COMPACT verbatim - so every locked cat scene this app has ever built
# opened with "the exact same PERSON as in the reference image — identical
# face, bone structure, eye colour, HAIRLINE, SKIN TONE and distinguishing
# marks", followed by "a ginger tabby cat". Three of those five identity
# anchors do not exist on a cat, and none of the ones that actually hold a cat
# together across shots - coat pattern, ear notches, tail - were named at all.
#
# A separate constant rather than a parameterised one, for the same reason
# RELIGHT_LOCK_* is separate: it encodes a different set of invariants, not a
# reworded version of the same one.
LOCK_ANIMAL_COMPACT = (
    "the exact same animal as in the reference image — identical coat pattern and "
    "markings, eye colour, ear shape and notches, tail length and kink, and muzzle "
    "and chin colouring"
)
LOCK_ANIMAL_DETAILED = (
    "The subject is the exact same animal as in the reference image: identical coat "
    "pattern and markings, eye colour, ear shape and notches, tail length and kink, "
    "and muzzle and chin colouring. Only the scene, pose and camera change — the "
    "animal must not be restyled, idealised or made younger."
)
LOCK_ANIMAL_TAIL = "identity locked to the reference animal"


def locks_for(spec):
    """(compact, detailed, tail) identity-lock text for this spec's subject kind.

    Unknown kinds fall back to the human lock, which is what every caller that
    has never heard of subject_kind already gets.
    """
    if spec.get("subject_kind") == "animal":
        return LOCK_ANIMAL_COMPACT, LOCK_ANIMAL_DETAILED, LOCK_ANIMAL_TAIL
    return LOCK_COMPACT, LOCK_DETAILED, LOCK_TAIL

# Prepended when a prompt must reproduce an existing PHOTO's scene rather than
# invent a new one - the inverse of the identity lock above. There, the face is
# fixed and everything else changes; here everything is fixed and only the
# lighting and camera angle change. Used by tools/build_relight.py.
RELIGHT_LOCK_COMPACT = (
    "the exact same photo as the reference image — identical subject, pose, "
    "wardrobe, setting and framing — with only the lighting and camera angle "
    "changed as directed"
)
RELIGHT_LOCK_DETAILED = (
    "This is the exact same subject, pose, wardrobe, setting and framing as the "
    "reference image. Do not invent a new scene, outfit or pose. Only the "
    "lighting and the camera angle change, exactly as directed below."
)
RELIGHT_LOCK_TAIL = "locked to the reference photo's scene and framing"


def apply_variation(spec):
    """Fold spec['variation'] over the base spec for a new shot of one character.

    The identity fields (subject, and anything the variation does not name)
    survive untouched — that is what keeps the character the same person.
    """
    variation = spec.get("variation")
    if not variation:
        return spec
    merged = dict(spec)
    merged.pop("variation", None)
    for key, value in variation.items():
        if value:
            merged[key] = value
    merged["lock_identity"] = True
    return merged


def subject_clause(spec):
    """The 'what am I actually looking at' part, assembled from the spec."""
    parts = [spec.get("subject", "a person")]
    if spec.get("wardrobe"):
        parts.append("wearing " + spec["wardrobe"])
    if spec.get("action"):
        parts.append(spec["action"])
    # Posing rides straight after the action it qualifies: what the body is
    # doing, then how it is arranged while doing it. Before the setting,
    # because both belong to the person and "in <setting>" closes that group.
    if spec.get("posing"):
        parts.append(spec["posing"])
    if spec.get("setting"):
        parts.append("in " + spec["setting"])
    if spec.get("mood"):
        parts.append(spec["mood"] + " expression")
    return ", ".join(parts)


def build_compact(bank, spec, selected, preset):
    segments = []
    lock_compact, _lock_detailed, lock_tail = locks_for(spec)
    head = ", ".join(selected["core"]) + " of "
    if spec.get("lock_identity"):
        head += lock_compact + ", "
    if spec.get("lock_scene"):
        head += RELIGHT_LOCK_COMPACT + ", "
    segments.append(head + subject_clause(spec))
    for name in ["camera", "lens", "lighting", "texture", "colour", "composition", "grain"]:
        segments.append(", ".join(selected[name]))

    extra = (list(preset.get("extra", [])) + free_overrides(spec)
             + list(spec.get("extra", [])))
    if extra:
        segments.append(", ".join(extra))

    if spec.get("lock_identity"):
        segments.append(lock_tail)
    if spec.get("lock_scene"):
        segments.append(RELIGHT_LOCK_TAIL)
    segments.append(", ".join(bank["negatives"]))
    return ", ".join(segments)


def build_detailed(bank, spec, selected, preset):
    _lock_compact, lock_detailed, _lock_tail = locks_for(spec)
    core = ", ".join(selected["core"])
    sentences = [
        "{core} of {subject}.".format(core=core[0].upper() + core[1:], subject=subject_clause(spec)),
    ]
    if spec.get("lock_identity"):
        sentences.append(lock_detailed)
    if spec.get("lock_scene"):
        sentences.append(RELIGHT_LOCK_DETAILED)
    sentences += [
        "Captured as if on {camera}, {lens}, producing authentic optical depth with natural "
        "lens falloff and gentle edge softness while the subject stays razor-sharp.".format(
            camera=", ".join(selected["camera"]), lens=", ".join(selected["lens"])
        ),
        "The scene is lit by {lighting}, with light wrap, bounce light and soft ambient "
        "occlusion giving the subject dimensional depth and grounded presence.".format(
            lighting=", ".join(selected["lighting"])
        ),
        "Surfaces carry real-world micro-texture including {texture} — nothing looks "
        "airbrushed or artificially clean.".format(texture=", ".join(selected["texture"])),
        "Color grading is {colour}, neutral and photographic with true whites and natural "
        "skin tones, avoiding oversaturation or artificial HDR.".format(
            colour=", ".join(selected["colour"])
        ),
        "The framing follows {composition}, giving clear separation between the subject and "
        "the environment.".format(composition=", ".join(selected["composition"])),
        "There is {grain} and subtle sensor noise in the shadows; highlights roll off "
        "smoothly with no clipping and blacks retain detail instead of crushing.".format(
            grain=", ".join(selected["grain"])
        ),
    ]

    extra = (list(preset.get("extra", [])) + free_overrides(spec)
             + list(spec.get("extra", [])))
    if extra:
        sentences.append("Additional direction: {}.".format(", ".join(extra)))

    sentences.append(
        "It should be visually indistinguishable from a real photograph: {}.".format(
            ", ".join(bank["negatives"])
        )
    )
    return " ".join(sentences)


DEFAULT_ANATOMY_GUARD = [
    "no warped face", "no distorted hands or extra fingers",
    "no floating or extra limbs", "no duplicated figures", "no morphing",
]


def anatomy_guard_tail(bank):
    """An OPT-IN guard against the anatomy failures `negatives` does not name.

    The standing negatives list defends the LOOK - no cartoon style, no CGI,
    no plastic skin. None of its seven entries says anything about the body,
    and the body is where a generated image is most often caught: a sixth
    finger, a hand that melts into a sleeve, a second copy of the subject in
    the background. A since-removed template bank carried this vocabulary
    ("no warped face, no floating limbs, no distorted hands, no morphing"),
    but only inside one template's own guard slot, and motion_bank.json has
    its own version for video - so of the three paths that compose a prompt,
    the ordinary image path was the only one with no anatomy guard at all.

    OPT-IN, off by default, exactly like build_motion.avatar_guard_tail(),
    and for the same reason: "no distorted hands" is noise on a product shot
    with no person in it. A guard that is always on is a guard nobody can
    aim. Callers that never ask are byte-for-byte unaffected, which is why
    adding this changed no existing test's expected output.
    """
    return ", ".join(bank.get("anatomy_guard") or DEFAULT_ANATOMY_GUARD)


def validate_shot(bank, shot):
    """Return an error message for an unknown shot preset, or None."""
    if shot and shot not in bank["shot_presets"]:
        return "Unknown shot '{}'. Available: {}".format(shot, ", ".join(bank["shot_presets"]))
    return None


def validate_purpose(bank, purpose):
    """Return an error message for an unknown purpose KEY, or None.

    Only ever handed `spec["purpose"]`, never `spec["purpose_custom"]` - that
    is the point of keeping them apart. A typo in a listed placement is still
    an error here instead of silently becoming a custom one, which is the same
    reason shot/shot_custom are two keys.
    """
    if purpose and purpose not in bank.get("purposes", {}):
        return "Unknown purpose '{}'. Available: {}".format(
            purpose, ", ".join(bank.get("purposes", {}))
        )
    return None


def validate_guide(bank, guide):
    """Return an error message for an unknown composition guide, or None."""
    if guide and guide not in guides(bank):
        return "Unknown composition guide '{}'. Available: {}".format(
            guide, ", ".join(guides(bank))
        )
    return None


def apply_purpose(bank, spec):
    """Fill `shot` and `aspect` from the stated purpose where the spec is silent.

    Purpose is a *default provider*, never an override: an explicit choice always
    wins, otherwise picking a purpose would quietly discard a deliberate one.
    """
    purpose = bank.get("purposes", {}).get(spec.get("purpose", ""))
    if not purpose:
        return spec
    merged = dict(spec)
    for field in ("shot", "aspect"):
        # A typed shot is an explicit choice, so the purpose must not fill the
        # preset slot behind it — that preset would then supply camera, lens and
        # composition terms the user never asked for.
        if field == "shot" and custom_shot(merged):
            continue
        if not merged.get(field) and purpose.get(field):
            merged[field] = purpose[field]
    return merged


def purpose_conflicts(bank, spec):
    """Explicit choices that disagree with the stated purpose. Inform, don't fix."""
    purpose = bank.get("purposes", {}).get(spec.get("purpose", ""))
    if not purpose:
        return []
    label = purpose.get("label", spec.get("purpose"))
    notes = []
    if purpose.get("shot") and custom_shot(spec):
        notes.append("{} expects the {} shot; you have typed your own".format(
            label, purpose["shot"]))
    for field in ("shot", "aspect"):
        wanted, actual = purpose.get(field), spec.get(field)
        if wanted and actual and actual != wanted:
            notes.append(
                "{} expects {} {}; you have set {}".format(label, field, wanted, actual)
            )
    return notes


def compose(bank, spec, detailed=False, weights=None, anatomy_guard=False):
    """Spec -> (prompt text, chosen layer terms).

    The single entry point for anything that needs a prompt — the CLI below and
    gui.py both call this, so prompt logic lives in exactly one place.
    `weights` biases vocabulary toward terms that have rated well (history.py).
    `anatomy_guard=True` appends anatomy_guard_tail(bank) - opt-in, off by
    default; see that function's docstring for why it is not always on.
    """
    spec = apply_purpose(bank, spec)
    spec = apply_variation(spec)
    spec = apply_subject_detail(spec)
    spec = apply_scene_light(spec)
    spec = apply_physical(spec)
    spec = apply_snapshot(bank, spec)
    rng = random.Random(spec.get("seed", 0))
    selected, preset = select_layers(bank, spec, rng, weights)
    prompt = (
        build_detailed(bank, spec, selected, preset)
        if detailed
        else build_compact(bank, spec, selected, preset)
    )
    # Before the aspect, which stays last: it is a framing parameter, not
    # part of the description, and every reader of these prompts expects to
    # find it at the end.
    if anatomy_guard:
        guard = anatomy_guard_tail(bank)
        prompt += (" Anatomy must be correct: {}.".format(guard)
                   if detailed else ", " + guard)
    if spec.get("aspect"):
        joiner = " Aspect ratio {}." if detailed else ", aspect ratio {}"
        prompt += joiner.format(spec["aspect"])
    return prompt, selected


def write_prompt(spec, prompt):
    """Write a prompt to temp/outputs/prompts/ and return the path."""
    slug = slugify(spec.get("slug") or spec.get("subject", "avatar"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "avatar-{}-{}.txt".format(slug, stamp)
    out_path.write_text(prompt + "\n", encoding="utf-8")
    return out_path


def slugify(text):
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:40] or "untitled"


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a layered photorealistic prompt from a character spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON in temp/resources/characters/")
    p.add_argument("--subject", help="subject description (used when no --spec is given)")
    p.add_argument("--wardrobe", help="what they are wearing")
    p.add_argument("--setting", help="where they are")
    p.add_argument("--action", help="what they are doing")
    p.add_argument("--posing", help="how the body is arranged - weight, shoulders, hands")
    p.add_argument("--mood", help="expression / mood")
    p.add_argument(
        "--shot",
        help="shot preset: portrait, selfie, talking-head, product-demo, environmental",
    )
    p.add_argument(
        "--purpose",
        help="what the image is for: tiktok-ugc, instagram-post, youtube-thumbnail, "
             "website-hero, ad-creative, character-ref. Sets shot and aspect unless "
             "you set them yourself.",
    )
    p.add_argument(
        "--purpose-custom", dest="purpose_custom",
        help="your own placement instead of a listed one, e.g. \"LinkedIn banner\". "
             "Recorded with the spec; supplies no shot or aspect, so set those "
             "yourself.",
    )
    p.add_argument(
        "--shot-custom", dest="shot_custom",
        help="your own shot description instead of a preset, e.g. \"close-up "
             "iPhone-style photo\". Takes the camera slot; suppresses the preset.",
    )
    p.add_argument(
        "--composition-guide", dest="composition_guide",
        help="optional framing geometry: rule-of-thirds, phi-grid, diagonals, triangle, "
             "golden-ratio, golden-spiral, harmonic-armature, dynamic-symmetry. Pins the "
             "first composition "
             "slot; the bank fills the rest.",
    )
    p.add_argument(
        "--composition-custom", dest="composition_guide_custom",
        help="your own framing instruction instead of a named guide, e.g. \"framed to "
             "include the sky and the water behind her\". Pinned the same way.",
    )
    p.add_argument(
        "--list-guides", action="store_true",
        help="print the composition guides and what each one does, then exit",
    )
    p.add_argument("--slug", help="output filename slug (defaults to the spec slug or subject)")
    p.add_argument("--detailed", action="store_true", help="emit the long paragraph form")
    p.add_argument("--anatomy-guard", action="store_true",
                   help="append the body guard (no extra fingers/limbs, no duplicated "
                        "figures, no morphing) - off by default, see anatomy_guard_tail()")
    p.add_argument("--seed", type=int, help="seed for word choice; same seed = same prompt")
    p.add_argument("--no-write", action="store_true", help="print only, do not write a file")
    p.add_argument(
        "--variants", type=int, default=1,
        help="build N prompts from consecutive seeds, for side-by-side comparison",
    )
    p.add_argument(
        "--learned", action="store_true",
        help="bias vocabulary toward terms that rated well in temp/outputs/history.jsonl",
    )
    p.add_argument(
        "--lock-identity", action="store_true",
        help="prepend the reference-image identity lock (for consistent characters)",
    )
    p.add_argument(
        "--lock-scene", action="store_true",
        help="prepend the reference-photo scene lock (for relighting/re-angling "
             "an existing photo) - the inverse of --lock-identity",
    )
    p.add_argument("--log", action="store_true", help="record each prompt in history.jsonl")
    return p.parse_args(argv)


def spec_from_args(args):
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        with path.open(encoding="utf-8") as fh:
            spec = json.load(fh)
    else:
        if not args.subject:
            sys.exit("Give either --spec <path> or --subject \"...\". See --help.")
        spec = {}

    for field in ["subject", "wardrobe", "setting", "action", "posing", "mood", "shot", "slug",
                  "purpose", "purpose_custom", "composition_guide", "shot_custom",
                  "composition_guide_custom"]:
        value = getattr(args, field, None)
        if value:
            spec[field] = value
    if args.seed is not None:
        spec["seed"] = args.seed
    if args.lock_identity:
        spec["lock_identity"] = True
    if args.lock_scene:
        spec["lock_scene"] = True
    return spec


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if getattr(args, "list_guides", False):
        for key, guide in guides(bank).items():
            print("{:<18} {}".format(key, guide["label"]))
            print("{:<18} {}".format("", guide["note"]))
        return 0

    spec = spec_from_args(args)

    for error in (validate_purpose(bank, spec.get("purpose")),
                  validate_shot(bank, spec.get("shot")),
                  validate_guide(bank, spec.get("composition_guide"))):
        if error:
            sys.exit(error)

    for note in purpose_conflicts(bank, spec):
        print("[note]    {}".format(note), file=sys.stderr)

    weights = None
    if args.learned:
        import history

        weights = history.weights()
        print(
            "[learned] biasing on {} rated term(s)".format(len(weights)), file=sys.stderr
        )

    # `.get("seed", 0)` still returns None when the spec file literally has
    # "seed": null (not merely omits it), and None + index is a TypeError.
    base_seed = spec.get("seed") or 0
    for index in range(max(1, args.variants)):
        variant = dict(spec, seed=base_seed + index)
        prompt, layers = compose(bank, variant, detailed=args.detailed, weights=weights,
                                 anatomy_guard=args.anatomy_guard)

        if args.variants > 1:
            print("\n=== seed {} ===".format(variant["seed"]))
        print(prompt)

        if args.log:
            import history
            import realism_lint

            present, _, banned, _, _ = realism_lint.lint(prompt.lower(), bank)
            entry_id = history.append(
                variant, prompt, layers, len(present),
                len(present) == 8 and not banned, args.detailed,
            )
            print("[logged]  {}".format(entry_id), file=sys.stderr)

        if not args.no_write:
            out_path = write_prompt(variant, prompt)
            print("[written] {}".format(out_path), file=sys.stderr)

    if not args.no_write and args.variants == 1:
        print("[next]    python tools/realism_lint.py <that file>", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
