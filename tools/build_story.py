"""Build a cat story: idea -> scenes, each a still prompt plus a camera move.

Usage:
    python tools/build_story.py --subject "a ginger tabby" --arc classic --seconds 30
    python tools/build_story.py --subject "a ginger tabby" --style stylised --clip 10
    python tools/build_story.py --list

THE RULE THIS TURNS ON: a scene is exactly one clip.

    clip_seconds   what Kling generates. 3 to 15 whole seconds.
    edit_seconds   what survives the cut in CapCut.

The two still differ, because a trim is sometimes wanted - but they are now
within a second of each other instead of differing by half. An earlier version
of this file assumed Kling only made 5s and 10s clips and multiplied up to reach
a longer scene, which produced "15 second clips" that no API will accept. The
scene COUNT is what absorbs a long runtime now: the arc gives the shape, and its
repeatable beat expands until every scene fits inside one clip.

One cat across every scene: scene 1 invents it, scenes 2..N carry lock_identity
plus scene 1's image as a reference. That is the existing consistent-character
mechanism applied along a sequence, and it needs a provider with reference-image
input, which today means Kie.

Style is applied as spec["overrides"], which is the precedence mechanism
build_prompt already has - so the stylised look never touches prompt_bank.json
and cannot weaken the 8/8 gate the rest of the app depends on.

Standard library only. No API keys, no network.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_motion as bm  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = Path(__file__).resolve().parent / "story_bank.json"
OUT_DIR = ROOT / "temp" / "outputs" / "prompts"


def load_bank():
    with BANK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Formats
#
# A format is a whole way of making one of these videos, not a coat of paint.
# `story` is the narrative arc: one cat, escalating beats, captions and
# narration, a different camera move every scene. `trade` is what the reference
# videos in Downloads/video actually do: two cats in costume doing a real job,
# one LOCKED-OFF take per gag, no words at all.
#
# Each format may bring its own beats and arcs; anything it does not define
# falls back to the bank's top level, so the story format needed no data moved.
# --------------------------------------------------------------------------- #
DEFAULT_FORMAT = "story"


def formats(bank):
    return bank.get("formats", {})


def format_cfg(bank, fmt=None):
    key = fmt or bank.get("default_format", DEFAULT_FORMAT)
    return formats(bank).get(key, {})


def validate_format(bank, fmt):
    if fmt and fmt not in formats(bank):
        return "Unknown format '{}'. Available: {}".format(fmt, ", ".join(formats(bank)))
    return None


def scene_fields(bank, fmt=None):
    """The per-scene words this format asks for."""
    return list(format_cfg(bank, fmt).get("scene_fields")
                or ["caption", "narration", "action"])


def locked_camera(bank, fmt=None):
    """The format's own camera phrase, or None when it uses motion_bank.

    The locked-off camera lives here rather than as a new movement in
    motion_bank.json, for the same reason the stylised look lives here rather
    than in prompt_bank.json: that bank is hashed to prove the shared gate is
    never quietly widened.
    """
    camera = format_cfg(bank, fmt).get("camera")
    return camera if isinstance(camera, dict) else None


def capcut_cfg(bank, fmt=None):
    """The assembly reference for this format, falling back to the bank's own.

    `trade` needed its own: the bank's default steps say "trim to the hook,
    3 seconds" and "add the caption per scene" - a one-take gag has neither.
    """
    return format_cfg(bank, fmt).get("capcut") or bank.get("capcut", {})


def trades(bank):
    return bank.get("trades", {})


def validate_trade(bank, trade):
    if trade and trade not in trades(bank):
        return "Unknown trade '{}'. Available: {}".format(trade, ", ".join(trades(bank)))
    return None


def arcs(bank, fmt=None):
    return format_cfg(bank, fmt).get("arcs") or bank.get("arcs", {})


def beats(bank, fmt=None):
    return format_cfg(bank, fmt).get("beats") or bank.get("beats", {})


def styles(bank):
    return bank.get("styles", {})


def clip_range(bank):
    """(min, max) whole seconds one generated clip may run to."""
    cfg = bank.get("clip_seconds", {})
    return int(cfg.get("min", 3)), int(cfg.get("max", 15))


def default_seconds(bank, fmt=None):
    """How long this format's videos usually run.

    20 for `trade`, because the reference construction video is two ten-second
    takes; 30 for a narrative arc, which needs more beats to escalate along.
    """
    per_format = format_cfg(bank, fmt).get("default_seconds")
    if per_format:
        return int(per_format)
    return int(bank.get("default_seconds", 30))


def default_clip(bank, fmt=None):
    """The clip length this format works in.

    `trade` defaults to 10 because every reference take runs about that long;
    `story` to 5, which gives a narrative arc more cuts to work with.
    """
    per_format = format_cfg(bank, fmt).get("default_clip")
    if per_format:
        return int(per_format)
    return int(bank.get("clip_seconds", {}).get("default", 5))


def clip_lengths(bank):
    """Every legal clip length, for a list the UI can offer.

    This used to be the bank's literal [5, 10]. It is derived now, so the range
    is stated once - and a scene of 7 seconds stopped being a thing the app
    refused to make.
    """
    low, high = clip_range(bank)
    return list(range(low, high + 1))


# The video model the story section generates with. Named here rather than in
# the UI so the bank's enums, the request builder and the option row all agree.
DEFAULT_VIDEO_MODEL = "kling-3.0/video"


def video_models(bank):
    return bank.get("video_models", {})


def validate_arc(bank, arc, fmt=None):
    if arc and arc not in arcs(bank, fmt):
        return "Unknown arc '{}'. Available: {}".format(
            arc, ", ".join(arcs(bank, fmt)))
    return None


def validate_style(bank, style):
    if style and style not in styles(bank):
        return "Unknown style '{}'. Available: {}".format(style, ", ".join(styles(bank)))
    return None


def validate_clip(bank, clip):
    low, high = clip_range(bank)
    if clip and not (low <= int(clip) <= high and int(clip) == clip):
        return "Kling generates whole clips of {} to {} seconds, not {}s.".format(
            low, high, clip)
    return None


# --------------------------------------------------------------------------- #
# Timing - the rule the whole design turns on
# --------------------------------------------------------------------------- #
def beat_sequence(bank, arc, seconds=None, clip_length=None, fmt=None):
    """The beat keys for one story, expanded to fit the runtime.

    The arc gives the SHAPE - hook, setup, escalation, twist, payoff - and the
    runtime decides how many scenes that shape needs. A beat may not run longer
    than one clip, so when the budget per scene would exceed the clip length the
    repeatable beat is repeated until every scene fits.

    This is what stops the planner emitting a "15 second clip". The old version
    kept the beat count fixed and stretched each scene instead, which produced
    durations no video model will generate.
    """
    cfg = arcs(bank, fmt).get(arc) or {}
    keys = list(cfg.get("beats", []))
    if not keys:
        return []

    total = float(seconds or default_seconds(bank, fmt))
    low, high = clip_range(bank)
    clip = max(low, min(high, int(clip_length or default_clip(bank, fmt))))
    hook_cap = float(bank.get("hook_seconds", 3.0))
    beat_cfg = beats(bank, fmt)

    # The hook is fixed-length, so it is not part of the budget the rest shares.
    capped = sum(min(_beat_cap(beat_cfg, key, hook_cap) or clip, clip)
                 for key in keys if _beat_cap(beat_cfg, key, hook_cap) is not None)
    free_keys = [k for k in keys if _beat_cap(beat_cfg, k, hook_cap) is None]
    if not free_keys:
        return keys

    # How many free scenes are needed so none of them exceeds one clip.
    budget = max(0.0, total - capped)
    needed = max(len(free_keys), int(-(-budget // clip)))    # ceil division

    repeatable = [k for k in free_keys if beat_cfg.get(k, {}).get("repeatable")]
    if not repeatable:
        # Nothing may repeat, so the arc simply cannot hold this runtime. Return
        # the arc as written; check_clip_lengths reports it rather than the
        # planner inventing a beat the story does not have.
        return keys

    # Grow the repeatable beats in place, round-robin, so the order still reads
    # hook -> setup -> escalation... -> twist -> payoff.
    extra = needed - len(free_keys)
    grown, cursor = list(keys), 0
    for _ in range(extra):
        target = repeatable[cursor % len(repeatable)]
        cursor += 1
        grown.insert(_last_index(grown, target) + 1, target)
    return grown


def _beat_cap(beat_cfg, key, hook_cap):
    """The hard ceiling on a beat's kept seconds, or None if it shares the budget."""
    cap = beat_cfg.get(key, {}).get("max_edit_seconds")
    if key == "hook":
        # The hook's limit is stated twice - on the beat and as bank.hook_seconds,
        # which is what story_lint checks. Taking the smaller means editing either
        # one alone can never make the planner produce a hook the gate rejects.
        cap = hook_cap if cap is None else min(cap, hook_cap)
    return cap


def scene_keys(bank, arc, seconds=None, clip_length=None, fmt=None):
    """["hook", "setup", "escalation", "escalation-2", ...] for one story.

    The single source of this list. The UI's script box, brief.py's list of what
    the model must return, and compose_story's own keys all have to agree, and
    they cannot be derived from the arc alone any more - the runtime decides how
    many times a repeatable beat repeats.
    """
    keys, seen = [], {}
    for beat_key in beat_sequence(bank, arc, seconds, clip_length, fmt):
        seen[beat_key] = seen.get(beat_key, 0) + 1
        keys.append(beat_key if seen[beat_key] == 1
                    else "{}-{}".format(beat_key, seen[beat_key]))
    return keys


def _last_index(items, value):
    for index in range(len(items) - 1, -1, -1):
        if items[index] == value:
            return index
    return len(items) - 1


def plan_scenes(bank, arc, seconds=None, clip_length=None, fmt=None):
    """[(beat_key, occurrence, clip_seconds, edit_seconds)] for one arc.

    Every scene is exactly one clip: `clip_seconds` is what the scene keeps
    rounded up to a whole second, clamped into the model's range. The hook is
    capped first - it has a hard ceiling of 3 seconds no matter how long the
    video is, because that is the window, not a proportion of it - and what it
    gives back is shared over the rest rather than shortening the video.
    """
    keys = beat_sequence(bank, arc, seconds, clip_length, fmt)
    if not keys:
        return []

    total = float(seconds or default_seconds(bank, fmt))
    low, high = clip_range(bank)
    clip = max(low, min(high, int(clip_length or default_clip(bank, fmt))))
    hook_cap = float(bank.get("hook_seconds", 3.0))
    beat_cfg = beats(bank, fmt)

    caps = [_beat_cap(beat_cfg, key, hook_cap) for key in keys]
    fixed = sum(cap for cap in caps if cap is not None)
    free = [index for index, cap in enumerate(caps) if cap is None]

    durations = [0.0] * len(keys)
    for index, cap in enumerate(caps):
        if cap is not None:
            durations[index] = float(cap)
    if free:
        share = max(0.0, total - fixed) / len(free)
        for index in free:
            durations[index] = share

    out, seen = [], {}
    for key, duration in zip(keys, durations):
        seen[key] = seen.get(key, 0) + 1
        # A clip is a whole number of seconds and never shorter than the model's
        # minimum, so a 2.4s beat still costs a 3s clip - that is the one place
        # generated and kept still differ. The ceiling is the length that was
        # asked for, which beat_sequence has already guaranteed is enough.
        clip_seconds = max(low, min(clip, int(-(-duration // 1))))
        out.append((key, seen[key], clip_seconds, round(min(duration, clip_seconds), 2)))
    return out


def scene_timings(bank, arc, seconds=None, clip_length=None, fmt=None):
    """[(beat, n, start, clip_seconds, edit_seconds)] with running start times."""
    rows, cursor = [], 0.0
    for key, occurrence, clip_seconds, edit_seconds in plan_scenes(
            bank, arc, seconds, clip_length, fmt):
        rows.append((key, occurrence, round(cursor, 2), clip_seconds, edit_seconds))
        cursor += edit_seconds
    return rows


def total_runtime(bank, arc, seconds=None, clip_length=None, fmt=None):
    """What the finished edit actually runs to, after every trim."""
    return round(sum(row[4] for row in scene_timings(
        bank, arc, seconds, clip_length, fmt)), 2)


def movement_for(bank, beat_key, occurrence, fmt=None):
    """Cycle a repeated beat through its movements so no move runs twice."""
    options = beats(bank, fmt).get(beat_key, {}).get("movements", [])
    if not options:
        return ""
    return options[(occurrence - 1) % len(options)]


# --------------------------------------------------------------------------- #
# Scenes
# --------------------------------------------------------------------------- #
def apply_style(bank, style, spec):
    """Fold a style's vocabulary into the spec as overrides.

    Overrides are build_prompt's own top-precedence slot, so this needs no new
    mechanism - and an override the caller set themselves still wins, because
    the style only fills what is not already there.
    """
    cfg = styles(bank).get(style or "", {})
    if not cfg:
        return spec
    merged = dict(spec)
    overrides = dict(cfg.get("overrides", {}))
    overrides.update(merged.get("overrides", {}))
    if overrides:
        merged["overrides"] = overrides
    extra = list(cfg.get("extra", [])) + list(merged.get("extra", []))
    if extra:
        merged["extra"] = extra
    return merged


def apply_trade(bank, trade, spec):
    """Fold a trade's costume, place and props into the spec.

    `wardrobe` is an existing spec key that build_prompt already renders as
    "wearing ..." - the costume needed no new mechanism, only vocabulary. Like
    the style, it fills only what the caller left empty.
    """
    cfg = trades(bank).get(trade or "", {})
    if not cfg:
        return spec
    merged = dict(spec)
    if cfg.get("wardrobe") and not merged.get("wardrobe"):
        merged["wardrobe"] = cfg["wardrobe"]
    if cfg.get("setting") and not merged.get("setting"):
        merged["setting"] = cfg["setting"]
    if cfg.get("props"):
        merged["extra"] = list(merged.get("extra", [])) + [cfg["props"]]
    return merged


def scene_spec(bank, beat_key, occurrence, base_spec, style, reference=None,
               fmt=None, trade=None):
    """The character spec for one scene's still."""
    beat = beats(bank, fmt).get(beat_key, {})
    spec = dict(base_spec)
    spec["shot"] = base_spec.get("shot") or beat.get("shot")
    if bank.get("aspect") and not spec.get("aspect"):
        spec["aspect"] = bank["aspect"]
    spec["slug"] = "{}-{}{}".format(
        bp.slugify(base_spec.get("slug") or base_spec.get("subject", "cat")),
        beat_key, occurrence if occurrence > 1 else "")
    if reference:
        spec["reference"] = reference
        spec["lock_identity"] = True
    return apply_style(bank, style, apply_trade(bank, trade, spec))


def compose_story(bank, base_spec, arc=None, seconds=None, clip_length=None,
                  style=None, script=None, reference=None,
                  image_bank=None, motion_bank=None, fmt=None, trade=None):
    """Idea -> the whole story as a list of scene dicts.

    `script` maps a scene key ("hook", "escalation-2") to
    {"narration": ..., "caption": ..., "action": ..., "setting": ...}.
    Anything missing is left empty rather than invented here - words are the
    model's job or the user's, and story_lint judges whichever arrives.

    `action` and `setting` are per scene on purpose: a story where every scene
    shares one action is not a story, it is the same shot five times. They flow
    into both the still prompt and the key sound effect.
    """
    image_bank = image_bank or bp.load_bank()
    motion_bank = motion_bank or bm.load_bank()
    fmt = fmt or bank.get("default_format", DEFAULT_FORMAT)
    arc = arc or format_cfg(bank, fmt).get("default_arc") or bank.get("default_arc", "classic")
    style = style or bank.get("default_style", "photoreal")
    script = script or {}
    fields = scene_fields(bank, fmt)
    camera = locked_camera(bank, fmt)

    scenes = []
    rows = scene_timings(bank, arc, seconds, clip_length, fmt)
    for index, (beat_key, occurrence, start, clip_seconds, edit_seconds) in enumerate(rows):
        beat = beats(bank, fmt).get(beat_key, {})
        key = beat_key if occurrence == 1 else "{}-{}".format(beat_key, occurrence)
        lines = script.get(key, {}) if isinstance(script.get(key), dict) else {}

        # A per-scene action or setting replaces the base one for this scene
        # only, so each scene shows something different happening.
        scene_base = dict(base_spec)
        for field in ("action", "setting"):
            if (lines.get(field) or "").strip():
                scene_base[field] = lines[field].strip()

        # A trade scene is written as a task and the thing that goes wrong. Both
        # belong in one continuous action, because that is what a single take
        # shows - splitting them across two clips is the one thing the reference
        # videos never do.
        task = (lines.get("task") or "").strip()
        mishap = (lines.get("mishap") or "").strip()
        if task or mishap:
            scene_base["action"] = " until ".join(part for part in (task, mishap) if part)

        spec = scene_spec(bank, beat_key, occurrence, scene_base, style,
                          reference=reference if (reference and index > 0) else None,
                          fmt=fmt, trade=trade)
        prompt, layers = bp.compose(image_bank, spec)

        # What realism_lint makes of this still, recorded as a fact rather than
        # a verdict: a stylised scene is meant to score low there, and history
        # excludes anything that did not pass, so the vocabulary weights stay
        # photoreal. story_lint is what decides whether the story is shippable.
        present, _, banned, _, _ = rl.lint(prompt.lower(), image_bank)
        score = len(present)
        passed = score == 8 and not banned

        if camera:
            # The format owns the camera. There is no move to be incompatible
            # with, so check_compatibility is not consulted - a locked-off frame
            # cannot fail to contain what a move needs.
            movement = "locked-off"
            motion = "{} {}, {}".format(
                camera["lead"], spec.get("subject", "the subject"), camera["detail"])
            warnings = []
        else:
            movement = movement_for(bank, beat_key, occurrence, fmt)
            motion, warnings = "", []
            if movement in motion_bank.get("movements", {}):
                motion, _ = bm.compose(motion_bank, movement, spec)
                warnings = bm.check_compatibility(motion_bank, movement, spec)

        scenes.append({
            "n": index + 1,
            "key": key,
            "beat": beat_key,
            "occurrence": occurrence,
            "label": beat.get("label", beat_key.title()),
            "role": beat.get("role", ""),
            "must_do": beat.get("must_do", ""),
            "style": style,
            "start": start,
            "clip_seconds": clip_seconds,
            "edit_seconds": edit_seconds,
            "end": round(start + edit_seconds, 2),
            "trim_in": 0.0,
            "trim_out": edit_seconds,
            "format": fmt,
            "fields": fields,
            "narration": lines.get("narration", ""),
            "caption": lines.get("caption", ""),
            "task": task,
            "mishap": mishap,
            "spec": spec,
            "prompt": prompt,
            "layers": layers,
            "score": score,
            "passed": passed,
            "movement": movement,
            "motion_prompt": motion,
            "warnings": warnings,
        })
    return scenes


# --------------------------------------------------------------------------- #
# The edit sheet
# --------------------------------------------------------------------------- #
def cut_between(bank, earlier, later):
    """Which cut to use between two beats, named from the film glossary."""
    cuts = bank.get("capcut", {}).get("cuts", {})
    if later is None:
        return "end"
    key = "{}->{}".format(earlier.get("beat"), later.get("beat"))
    return cuts.get(key, cuts.get("default", "hard cut"))


def export_settings():
    """Read the export rules from ugc_bank rather than keeping a second copy.

    Those numbers are already encoded for the ads section, and two copies of a
    rule is one copy that will silently go stale.
    """
    import build_ad as ba

    items = ba.load_bank().get("publishing", {}).get("items", [])
    wanted = {"Export", "Aspect", "First clip", "On-screen text"}
    return [item for item in items if item.get("topic") in wanted]


def edit_sheet(bank, scenes, sound_sheets=None):
    """Everything CapCut needs, per scene, for THIS story.

    The trim is the part worth printing: every clip is 5 or 10 seconds and most
    of it is thrown away, so the in/out points are the difference between an
    edit that moves and one that drags.
    """
    sound_by_n = {s["n"]: s for s in (sound_sheets or [])}
    rows = []
    for index, scene in enumerate(scenes):
        later = scenes[index + 1] if index + 1 < len(scenes) else None
        sound = sound_by_n.get(scene["n"], {})
        rows.append({
            "n": scene["n"],
            "label": scene["label"],
            "clip": "{}s".format(scene["clip_seconds"]),
            "trim": "{:.1f}s - {:.1f}s".format(scene["trim_in"], scene["trim_out"]),
            "keep": scene["edit_seconds"],
            "timeline": "{:.1f}s - {:.1f}s".format(scene["start"], scene["end"]),
            "caption": scene.get("caption", ""),
            "narration": scene.get("narration", ""),
            # `trade` has no caption to lean on, so the sheet needs its own
            # reminder of what the take shows - without this the CapCut panel
            # for a one-take gag named nothing but timings.
            "brief": " until ".join(part for part in
                                    (scene.get("task"), scene.get("mishap")) if part),
            "cut_out": cut_between(bank, scene, later),
            "sound": [
                {"layer": layer["layer"], "text": layer["text"]}
                for layer in sound.get("layers", [])
            ],
        })
    return rows


def edit_sheet_text(bank, scenes, sound_sheets=None):
    """The sheet as something you can keep open beside CapCut."""
    rows = edit_sheet(bank, scenes, sound_sheets)
    generated = sum(s["clip_seconds"] for s in scenes)
    kept = round(sum(s["edit_seconds"] for s in scenes), 1)

    lines = [
        "CAPCUT EDIT SHEET",
        "{} scenes  ·  {}s generated  ·  {:.0f}s finished".format(
            len(scenes), generated, kept),
        "",
    ]
    for row in rows:
        lines.append("{}. {}".format(row["n"], row["label"]))
        lines.append("   clip      {}, use {} (keep {:.1f}s)".format(
            row["clip"], row["trim"], row["keep"]))
        lines.append("   timeline  {}".format(row["timeline"]))
        if row["caption"]:
            lines.append("   caption   {}".format(row["caption"]))
        if row["narration"]:
            lines.append("   voice     {}".format(row["narration"]))
        if row["brief"]:
            lines.append("   shows     {}".format(row["brief"]))
        for layer in row["sound"]:
            lines.append("   {:<9} {}".format(layer["layer"], layer["text"]))
        lines.append("   cut out   {}".format(row["cut_out"]))
        lines.append("")

    lines.append("EXPORT")
    for item in export_settings():
        lines.append("   {:<14} {}".format(item["topic"], item["text"]))
    return "\n".join(lines).rstrip() + "\n"


def write_edit_sheet(base_spec, scenes, bank, sound_sheets=None):
    slug = bp.slugify(base_spec.get("slug") or base_spec.get("subject", "cat"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "capcut-{}-{}.txt".format(slug, stamp)
    out_path.write_text(edit_sheet_text(bank, scenes, sound_sheets), encoding="utf-8")
    return out_path


def story_script(scenes):
    """The words alone, as something readable.

    Per format: `trade` scenes carry no caption or narration at all - printing
    "(none yet)" for two fields that will never be filled would read as a
    story missing its words, when the format simply has none.
    """
    lines = []
    for scene in scenes:
        lines.append("[{:.1f}-{:.1f}s] {}. {}  (clip {}s, keep {:.1f}s)".format(
            scene["start"], scene["end"], scene["n"], scene["label"],
            scene["clip_seconds"], scene["edit_seconds"]))
        if scene.get("fields") == ["task", "mishap"]:
            lines.append("    task:   " + (scene.get("task") or "(none yet)"))
            lines.append("    mishap: " + (scene.get("mishap") or "(none yet)"))
        else:
            lines.append("    caption:   " + (scene["caption"] or "(none yet)"))
            lines.append("    narration: " + (scene["narration"] or "(none yet)"))
    return "\n".join(lines)


def write_story(base_spec, arc, scenes):
    """Write the whole story to temp/outputs/prompts/ and return the path."""
    slug = bp.slugify(base_spec.get("slug") or base_spec.get("subject", "cat"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "story-{}-{}-{}.txt".format(arc, slug, stamp)

    blocks = []
    for scene in scenes:
        if scene.get("fields") == ["task", "mishap"]:
            words = "task:      {}\nmishap:    {}\n".format(
                scene.get("task") or "(none)", scene.get("mishap") or "(none)")
        else:
            words = "caption:   {}\nnarration: {}\n".format(
                scene["caption"] or "(none)", scene["narration"] or "(none)")
        blocks.append(
            "=== {}. {}   clip {}s, keep {:.1f}s  [{:.1f}-{:.1f}s]\n{}"
            "still:     {}\n"
            "motion:    {}\n".format(
                scene["n"], scene["label"], scene["clip_seconds"], scene["edit_seconds"],
                scene["start"], scene["end"], words,
                scene["prompt"], scene["motion_prompt"] or "(none)"))
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return out_path


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build a cat story: scenes, still prompts and camera moves.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON (the cat)")
    p.add_argument("--subject", help="the cat, if no --spec is given")
    p.add_argument("--setting", help="where it happens")
    p.add_argument("--action", help="what the cat is doing")
    p.add_argument("--format", help="story or trade (see --list)")
    p.add_argument("--trade", help="the job, for --format trade (see --list)")
    p.add_argument("--arc", help="story shape (see --list)")
    p.add_argument("--style", help="photoreal or stylised")
    p.add_argument("--seconds", type=int, help="target runtime")
    p.add_argument("--clip", type=int, help="clip length to generate: 5 or 10")
    p.add_argument("--list", action="store_true", help="print arcs, beats and styles")
    p.add_argument("--no-write", action="store_true", help="print only, do not write a file")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bank = load_bank()

    if args.list:
        print("FORMATS")
        for key, cfg in formats(bank).items():
            print("  {:<12} {:<28} {}".format(key, cfg["label"], cfg.get("note", "")))
        print("\nTRADES")
        for key, cfg in trades(bank).items():
            print("  {:<12} {:<20} {}".format(key, cfg["label"], cfg.get("note", "")))
        print("\nARCS (--format story)")
        for key, cfg in arcs(bank, "story").items():
            print("  {:<12} {:<18} {}".format(key, cfg["label"], cfg["note"]))
        print("\nARCS (--format trade)")
        for key, cfg in arcs(bank, "trade").items():
            print("  {:<12} {:<18} {}".format(key, cfg["label"], cfg["note"]))
        print("\nBEATS")
        for key, cfg in beats(bank).items():
            print("  {:<12} {:<10} {}".format(key, cfg["label"], cfg["role"]))
        print("\nSTYLES")
        for key, cfg in styles(bank).items():
            print("  {:<12} {:<24} {}".format(key, cfg["label"], cfg["note"]))
        low, high = clip_range(bank)
        print("\nCLIP LENGTH   {}-{}s, whole seconds (default {}s)".format(
            low, high, default_clip(bank)))
        for key, cfg in video_models(bank).items():
            print("\nVIDEO MODEL   {}  ({})".format(key, cfg.get("label", key)))
            for field in ("aspect_ratio", "mode"):
                print("  {:<12} {}".format(field, ", ".join(cfg.get(field, []))))
            print("  {:<12} {}".format("defaults", cfg.get("defaults", {})))
        return 0

    for error in (validate_format(bank, args.format), validate_trade(bank, args.trade),
                  validate_arc(bank, args.arc, args.format), validate_style(bank, args.style),
                  validate_clip(bank, args.clip)):
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

    for field in ("setting", "action"):
        value = getattr(args, field, None)
        if value:
            base_spec[field] = value

    fmt = args.format or bank.get("default_format", DEFAULT_FORMAT)
    arc = args.arc or format_cfg(bank, fmt).get("default_arc") or bank.get("default_arc", "classic")
    scenes = compose_story(bank, base_spec, arc=arc, seconds=args.seconds,
                           clip_length=args.clip, style=args.style,
                           fmt=fmt, trade=args.trade)

    runtime = total_runtime(bank, arc, args.seconds, args.clip, fmt)
    generated = sum(s["clip_seconds"] for s in scenes)
    print("{} / {} - {} scenes, {:.1f}s edited from {}s of generated clip".format(
        format_cfg(bank, fmt).get("label", fmt), arcs(bank, fmt)[arc]["label"],
        len(scenes), runtime, generated), file=sys.stderr)
    print(story_script(scenes))

    if not args.no_write:
        path = write_story(base_spec, arc, scenes)
        print("\n[story]   {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
