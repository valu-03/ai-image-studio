"""Compose form options, spec assembly, derived notes, and prompt preview.

Ports the domain assembly of the former SpecEditor / ComposeView over
tools/build_prompt.py, build_scene_light.py, build_contact.py, build_material.py,
build_skin_features.py, build_snapshot.py, build_evidence.py, and realism_lint.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build_contact as bct  # noqa: E402
import build_evidence as bev  # noqa: E402
import build_material as bmt  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_scene_light as bsl  # noqa: E402
import build_skin_features as bsf  # noqa: E402
import build_snapshot as bsn  # noqa: E402
import history  # noqa: E402
import realism_lint as rl  # noqa: E402

PLACEHOLDER_SUBJECT = "a person"
ASPECTS = ["", "1:1", "4:5", "3:2", "16:9", "9:16"]


def compose_options():
    """All dropdown and checkbox options used by the Compose tab."""
    bank = bp.load_bank()
    skin_bank = bsf.load_bank()
    purposes = [
        {
            "key": key,
            "label": cfg.get("label", key),
            "shot": cfg.get("shot", ""),
            "aspect": cfg.get("aspect", ""),
            "note": cfg.get("note", ""),
        }
        for key, cfg in bank.get("purposes", {}).items()
    ]
    guides = [
        {
            "key": key,
            "label": g.get("label", key),
            "phrase": g.get("phrase", ""),
            "note": g.get("note", ""),
        }
        for key, g in bp.guides(bank).items()
    ]
    skin_features = [
        {
            "key": key,
            "label": label,
            "tip": " / ".join(
                "{}: {}".format(tier, skin_bank["features"][key].get(tier) or "skipped")
                for tier in ("close", "mid", "wide")
            ),
        }
        for key, label in bsf.labels(skin_bank)
    ]
    return {
        "purposes": purposes,
        "aspects": ASPECTS,
        "shots": list(bank.get("shot_presets", {}).keys()),
        "lighting_terms": list(bank["layers"]["lighting"]["terms"]),
        "colour_terms": list(bank["layers"]["colour"]["terms"]),
        "composition_guides": guides,
        "skin_features": skin_features,
    }


def _resolve_purpose(bank, text):
    val = str(text or "").strip()
    if not val or val == "(auto)":
        return "", ""
    purposes = bank.get("purposes", {})
    low = val.lower()
    for k, cfg in purposes.items():
        if low == k.lower() or low == str(cfg.get("label", "")).lower():
            return k, ""
    return "", val


def _resolve_shot(bank, text):
    val = str(text or "").strip()
    if not val or val == "(auto)":
        return "", ""
    presets = bank.get("shot_presets", {})
    low = val.lower()
    for k in presets:
        if low == k.lower():
            return k, ""
    return "", val


def _resolve_guide(bank, text):
    val = str(text or "").strip()
    if not val or val == "(none)":
        return "", ""
    guides = bp.guides(bank)
    low = val.lower()
    for k, g in guides.items():
        if low == k.lower() or low == str(g.get("label", "")).lower():
            return k, ""
    return "", val


def build_spec_and_preview(form, look_overrides=None):
    """Turn the Compose tab form dict into (spec, prompt, kind, lint_checks, notes)."""
    form = dict(form or {})
    look_overrides = dict(look_overrides or {})
    bank = bp.load_bank()
    ev_bank = bev.load_bank()
    sl_bank = bsl.load_bank()
    ct_bank = bct.load_bank()
    mt_bank = bmt.load_bank()
    sn_bank = bsn.load_bank()

    raw_subject = str(form.get("subject") or "").strip()
    subject = raw_subject or PLACEHOLDER_SUBJECT
    try:
        seed = max(0, min(9999, int(form.get("seed") or 0)))
    except (TypeError, ValueError):
        seed = 0

    spec = {"subject": subject, "seed": seed}

    posing_val = str(form.get("posing") or look_overrides.get("posing") or "").strip()
    for key in ("wardrobe", "setting", "action", "mood", "slug"):
        val = str(form.get(key) or "").strip()
        if val:
            spec[key] = val
    if posing_val:
        spec["posing"] = posing_val

    purpose_key, purpose_custom = _resolve_purpose(bank, form.get("purpose"))
    if purpose_key:
        spec["purpose"] = purpose_key
    elif purpose_custom:
        spec["purpose_custom"] = purpose_custom

    shot_input = str(form.get("shot") or look_overrides.get("camera") or "").strip()
    shot_key, shot_custom = _resolve_shot(bank, shot_input)
    if shot_key:
        spec["shot"] = shot_key
    elif shot_custom:
        spec["shot_custom"] = shot_custom

    comp_input = str(form.get("composition") or look_overrides.get("composition") or "").strip()
    guide_key, guide_custom = _resolve_guide(bank, comp_input)
    if guide_key:
        spec["composition_guide"] = guide_key
    elif guide_custom:
        spec["composition_guide_custom"] = guide_custom

    aspect = str(form.get("aspect") or "").strip()
    if aspect:
        spec["aspect"] = aspect

    raw_extra = form.get("extra") or ""
    if isinstance(raw_extra, str):
        extra = [line.strip() for line in raw_extra.splitlines() if line.strip()]
    elif isinstance(raw_extra, list):
        extra = [str(x).strip() for x in raw_extra if str(x).strip()]
    else:
        extra = []
    if extra:
        spec["extra"] = extra

    lighting = str(form.get("lighting") or look_overrides.get("lighting") or "").strip()
    if lighting == "(auto)":
        lighting = ""
    colour = str(form.get("colour") or look_overrides.get("color") or "").strip()
    if colour == "(auto)":
        colour = ""

    overrides = {}
    if lighting:
        overrides["lighting"] = [lighting, "realistic shadows"]
    if colour:
        overrides["colour"] = [colour]
    if look_overrides.get("style"):
        overrides["style"] = [look_overrides["style"]]
    if look_overrides.get("capture"):
        overrides["capture"] = [look_overrides["capture"]]

    face_detail = bool(form.get("face_detail", True))
    lived_in = bool(form.get("lived_in", False))
    contact_detail = bool(form.get("contact_detail", True))
    material_detail = bool(form.get("material_detail", True))
    snapshot = bool(form.get("snapshot", True))
    background_life = bool(form.get("background_life", True))
    moment = bool(form.get("moment", True))
    match_light = bool(form.get("match_light", True))

    if face_detail:
        spec["face_detail"] = True
    if look_overrides.get("evidence"):
        overrides["evidence"] = [look_overrides["evidence"]]
    elif lived_in:
        spec["lived_in"] = True

    if match_light:
        spec["scene_lighting"] = True
    if contact_detail:
        spec["contact_detail"] = True
    if material_detail:
        spec["material_detail"] = True
    if snapshot:
        spec["snapshot"] = True
    if background_life:
        spec["background_life"] = True
    if moment:
        spec["moment"] = True

    skin = [str(k) for k in (form.get("skin_features") or []) if str(k)]
    if skin:
        spec["skin_features"] = skin

    if overrides:
        spec["overrides"] = overrides

    detailed = bool(form.get("detailed", False))
    anatomy_guard = bool(form.get("anatomy_guard", False))

    kind = bev.subject_kind(ev_bank, raw_subject or subject)
    prompt, selected = bp.compose(
        bank,
        spec,
        detailed=detailed,
        weights=history.weights(),
        anatomy_guard=anatomy_guard,
    )
    checks = rl.checks_for(prompt, bank, selected, kind)
    passed_layers = sum(1 for c in checks[:8] if c["passed"])

    # Derived notes (purpose_note, light_note, physical_note)
    purpose_note = _build_purpose_note(bank, spec, purpose_key, purpose_custom, shot_key, shot_custom, aspect)
    light_note = _build_light_note(sl_bank, match_light, spec.get("setting", ""), lighting)
    physical_note = _build_physical_note(
        ct_bank, mt_bank, sn_bank, spec, kind,
        contact_detail, material_detail, background_life, moment
    )

    return {
        "spec": spec,
        "prompt": prompt,
        "kind": kind,
        "lint": {
            "score": passed_layers,
            "total": 8,
            "passed": all(c["passed"] for c in checks[:9]),
            "checks": checks,
        },
        "notes": {
            "purpose": purpose_note,
            "light": light_note,
            "physical": physical_note,
        },
    }


def _build_purpose_note(bank, spec, purpose_key, purpose_custom, shot_key, shot_custom, aspect):
    explicit_shot = bool(shot_key or shot_custom)
    explicit_aspect = bool(aspect)
    if not purpose_key:
        if purpose_custom:
            missing = []
            if not explicit_shot:
                missing.append("shot")
            if not explicit_aspect:
                missing.append("aspect")
            note = 'Your own placement: "{}". Recorded with the spec.'.format(purpose_custom)
            if missing:
                note += " It supplies no {} — set {} below.".format(
                    " or ".join(missing), "them" if len(missing) == 2 else "it"
                )
            else:
                note += " Shot and aspect are your own."
            return note
        return "No purpose set. Shot and aspect are whatever you choose below."
    cfg = bank.get("purposes", {}).get(purpose_key, {})
    notes = bp.purpose_conflicts(bank, spec)
    if notes:
        return "Heads up: " + "; ".join(notes) + ". Your choice is being used."
    supplied = []
    if cfg.get("shot") and not explicit_shot:
        supplied.append("shot {}".format(cfg["shot"]))
    if cfg.get("aspect") and not explicit_aspect:
        supplied.append("aspect {}".format(cfg["aspect"]))
    detail = cfg.get("note", "")
    return ("Supplying " + ", ".join(supplied) + ". " if supplied else "") + detail


def _build_light_note(sl_bank, match_light, setting, chosen_lighting):
    if not match_light:
        return ""
    notes = bsl.conflicts_with(sl_bank, setting, chosen_lighting)
    if notes:
        return "Heads up: " + "; ".join(notes) + ". Your choice is being used."
    place, time_of_day = bsl.read_scene(sl_bank, setting)
    if not (place or time_of_day):
        return (
            "Scene light: name a place or time of day in Setting and the light will "
            "follow it. Shadows are kept consistent either way."
        )
    where = " at ".join(x for x in (place, time_of_day) if x).replace("-", " ")
    if chosen_lighting:
        return "Scene light ({}): your lighting is used, plus the scene's bounce and shadows.".format(where)
    return "Scene light ({}): {}.".format(where, bsl.source_phrase(sl_bank, setting))


def _build_physical_note(ct_bank, mt_bank, sn_bank, spec, kind, contact_on, material_on, bg_on, moment_on):
    parts = []
    if contact_on:
        _phrase, keys = bct.read_contact(ct_bank, spec, kind=kind)
        if keys:
            tables = dict(ct_bank["supports"], **ct_bank["actions"])
            parts.append("Contact: " + ", ".join(tables[k]["label"].lower() for k in keys))
        elif kind != "place":
            parts.append("Contact: a general weight cue - name what they sit, lie or lean on")
    if material_on:
        _phrase, keys = bmt.read_materials(mt_bank, spec)
        if keys:
            parts.append(
                "Materials: " + ", ".join(mt_bank["materials"][k]["label"].lower() for k in keys)
            )
        else:
            parts.append("Materials: none named yet (glass, wool, coffee...)")
    if bg_on:
        _phrase, place = bsn.background_line(sn_bank, spec)
        if place == "plain":
            parts.append("Background: plain backdrop, left alone")
        elif place:
            parts.append("Background: " + sn_bank["backgrounds"][place]["label"].lower())
        else:
            parts.append("Background: name a place in Setting (street, cafe, park...)")
    if moment_on:
        _phrase, key = bsn.moment_line(sn_bank, spec, kind)
        parts.append("Moment: " + (key or "a small default"))
    return " · ".join(parts)

