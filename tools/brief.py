"""The six-part brief framework, as code.

From AI Video Bootcamp lesson 1 (*How to write Prompts*): a strong prompt is a
mini-brief made of Purpose, Role, Structure/Format, Style/Tone, Constraints, and
Example+Action. `build_brief()` assembles exactly that; the three functions below
are the briefs this project actually needs.

Usage:
    python tools/brief.py idea "a tired barista closing up late"
    python tools/brief.py upgrade temp/outputs/prompts/avatar-x.txt
    python tools/brief.py critique temp/outputs/prompts/avatar-x.txt image.png
    python tools/brief.py show upgrade        # print the brief without calling out

THE RULE: the model suggests, realism_lint decides. Every reply is validated
before it is accepted — an "upgraded" prompt that drops below 8/8 or introduces a
banned term is rejected and the original kept. Without that gate the text model
silently defeats the quality standard the whole project exists to enforce.
"""

import argparse
import json
import sys
from pathlib import Path

import ask_llm
import build_prompt as bp
import realism_lint as rl

ROOT = Path(__file__).resolve().parent.parent

# Only these may come back from a model and be written into a spec. Seed,
# reference, overrides and lock_identity are the user's machinery, not the
# model's to set.
SPEC_KEYS = {"subject", "wardrobe", "setting", "action", "posing", "mood", "shot",
             "aspect", "purpose", "extra", "slug"}

# `purpose_custom` is deliberately NOT here. A model-invented purpose is
# already dropped on the way back (see the validate_purpose() filter below),
# and letting it arrive under the custom key would be a way around exactly
# that check. A user may name a placement; a model may only pick a listed
# one. It is still SHOWN to the model by _describe_current().

MAX_UPGRADE_WORDS = 320

# Auto-fill may additionally *suggest* these two. They are not in SPEC_KEYS and
# never land in a spec here: composition geometry and lighting are opt-in by an
# explicit decision, so the app hands them to the user as a suggestion and lets
# them apply it. See autofill_spec().
SUGGEST_KEYS = {"composition_guide", "lighting"}


def build_brief(purpose, role, structure, tone=None, constraints=(), examples=()):
    """Assemble a system message from the six parts. Empty parts are omitted."""
    blocks = [
        ("PURPOSE", purpose),
        ("ROLE", role),
        ("STRUCTURE / FORMAT", structure),
        ("STYLE / TONE", tone),
    ]
    out = []
    for label, body in blocks:
        if body:
            out.append("{}\n{}".format(label, body.strip()))
    if constraints:
        out.append("CONSTRAINTS\n" + "\n".join("- " + c for c in constraints))
    if examples:
        out.append("EXAMPLES\n" + "\n\n".join(examples))
    return "\n\n".join(out)


def _bank_vocabulary(bank):
    lines = []
    for name, cfg in bank["layers"].items():
        lines.append("{}: {}".format(name, "; ".join(cfg["terms"])))
    return "\n".join(lines)


def _examples(bank, limit=2):
    """The worked examples from the bank — few-shot material for the model."""
    return ['{}\n{}'.format(e["name"], e["text"]) for e in bank.get("examples", [])[:limit]]


def _taught_examples(bank, limit=3):
    """Worked examples with their lessons, where the bank records them.

    An example the model is told *why* it works is worth several it has to infer
    from. Examples carrying a `teaches` list are preferred and come first.
    """
    taught = [e for e in bank.get("examples", []) if e.get("teaches")]
    plain = [e for e in bank.get("examples", []) if not e.get("teaches")]
    out = []
    for entry in (taught + plain)[:limit]:
        block = "{}\n{}".format(entry["name"], entry["text"])
        if entry.get("teaches"):
            block += "\nwhy it works:\n" + "\n".join(
                "  - " + line for line in entry["teaches"])
        out.append(block)
    return out


# --------------------------------------------------------------------------- #
# The three briefs
# --------------------------------------------------------------------------- #
def idea_brief(bank):
    return build_brief(
        purpose=(
            "Turn a one-line character idea into a complete character spec for a "
            "photorealistic avatar image."
        ),
        role=(
            "You are a casting director working with a portrait photographer. You "
            "think in concrete, observable detail — what a camera would actually "
            "see — never in adjectives about personality."
        ),
        structure=(
            "Reply with a single JSON object and nothing else. Keys, all optional "
            "except subject:\n"
            '  subject   (string) who they are, physically. Age range, hair, skin, '
            'distinguishing marks.\n'
            "  wardrobe  (string) what they are wearing\n"
            "  setting   (string) where they are, and the time of day\n"
            "  action    (string) what they are physically doing\n"
            "  posing    (string) how the body is arranged - weight, shoulders, hands\n"
            "  mood      (string) expression, in two or three words\n"
            "  shot      (string) one of: " + ", ".join(bank["shot_presets"]) + "\n"
            "  purpose   (string) one of: " + ", ".join(bank.get("purposes", {})) + "\n"
            "  extra     (array of short strings) small realism details"
        ),
        tone="Plain, concrete, photographic. No marketing language.",
        constraints=[
            "Use ONLY the keys listed above. Any other key is discarded.",
            "Do not write camera, lens, lighting, grain or colour terms — the app "
            "adds those from its own vocabulary.",
            "Include at least one natural imperfection in `extra` (a blemish, eye "
            "bags, stray hairs, worn fabric).",
            "Never use these words: " + ", ".join(bank["banned"]) + ".",
            "Real, ordinary-looking people. Not models, not idealised faces.",
        ],
        examples=[
            'idea: "a tired barista closing up late"\n'
            '{"subject": "a man in his early thirties with stubble, tired eyes and '
            'short dark hair pushed back", "wardrobe": "a creased black apron over a '
            'grey t-shirt", "setting": "a small coffee shop after closing, lit by one '
            'window", "action": "wiping down the counter", "mood": "worn out, absent", '
            '"shot": "environmental", "extra": ["faint coffee stains on the apron", '
            '"shadows under the eyes"]}'
        ],
    )


def autofill_brief(bank):
    """Fill a whole character form from whatever is already in it.

    The difference from idea_brief: this one is told what the user has already
    written and must work *around* it, and it may propose a lighting source and
    a composition guide as suggestions. Its realism guidance comes from the
    bank's worked examples, which is where the influencer-photo lessons live.
    """
    guide_keys = ", ".join(bp.guides(bank)) or "(none available)"
    return build_brief(
        purpose=(
            "Complete a character spec for a photorealistic avatar image. Some fields "
            "are already filled in; fill the empty ones so the whole thing describes "
            "one coherent photograph."
        ),
        role=(
            "You are a photographer scouting a shot. You think in what the camera "
            "would actually see - a specific person, in a specific place, doing a "
            "specific thing - never in adjectives about personality."
        ),
        structure=(
            "Reply with a single JSON object and nothing else. Keys, all optional:\n"
            "  subject   (string) who they are, physically\n"
            "  wardrobe  (string) what they are wearing\n"
            "  setting   (string) where they are, and the time of day\n"
            "  action    (string) what they are physically doing\n"
            "  posing    (string) how the body is arranged - weight, shoulders, hands\n"
            "  mood      (string) expression, in two or three words\n"
            "  shot      (string) one of: " + ", ".join(bank["shot_presets"]) + "\n"
            "  purpose   (string) one of: " + ", ".join(bank.get("purposes", {})) + "\n"
            "  aspect    (string) one of: 1:1, 4:5, 3:2, 16:9, 9:16\n"
            "  extra     (array of short strings) scene-bound realism details\n"
            "  lighting  (string) a light SOURCE in plain words, e.g. \"harsh midday "
            "sunlight\" - a suggestion only\n"
            "  composition_guide (string) one of: " + guide_keys + " - a suggestion only"
        ),
        tone="Plain, concrete, photographic. No marketing language.",
        constraints=[
            "Do NOT change or restate any field the user has already filled in. Work "
            "around them - they are the brief.",
            "Use ONLY the keys listed above. Any other key is discarded.",
            "Do not write camera, lens, grain, colour or texture terms - the app adds "
            "those from its own vocabulary.",
            # Straight out of the influencer beach photo: these are the four things
            # that separate a convincing photo from a generic one.
            "Put at least one detail in `extra` that partly hides or breaks up the "
            "face - a hat brim over the eyes, hair across the cheek, sunglasses, a "
            "hand. A fully lit, fully visible face is the clearest AI tell.",
            "Put at least one imperfection in `extra` that belongs to THIS scene - "
            "sand on skin, a sweat-damp hairline, creases where the fabric sat - not "
            "a generic 'skin detail'.",
            "Put at least one ordinary prop in the scene that implies a story - an "
            "open book, a half-drunk coffee, a bag set down.",
            "Never use these words: " + ", ".join(bank["banned"]) + ".",
            "Real, ordinary-looking people. Not models, not idealised faces.",
        ],
        examples=_taught_examples(bank, 3),
    )


def upgrade_brief(bank):
    return build_brief(
        purpose=(
            "Rewrite a compact image prompt into a richer one that produces a more "
            "convincing photograph. This is the 'make this prompt way more detailed' "
            "step from the course."
        ),
        role=(
            "You are a cinematographer describing a frame to a camera operator who "
            "cannot see it. You describe light physically — direction, quality, what "
            "it does to skin and fabric."
        ),
        structure=(
            "Reply with the rewritten prompt as one flowing paragraph. No preamble, "
            "no headings, no bullet points, no quotation marks around it."
        ),
        tone="Photographic and specific. Restrained — realism is restraint.",
        constraints=[
            "Every one of the eight realism layers present in the original must "
            "survive: core realism, camera, lens, lighting, texture, colour, "
            "composition, grain.",
            "Keep the negative block at the end.",
            "Do not change who the subject is, what they wear, or where they are.",
            "Never introduce: " + ", ".join(bank["banned"]) + ".",
            "Under {} words.".format(MAX_UPGRADE_WORDS),
            "Describe light and texture physically, not with adjectives like "
            "'beautiful' or 'stunning'.",
        ],
        examples=_examples(bank, 2),
    )


def critique_brief(bank):
    layers = ", ".join(bank["layers"].keys())
    return build_brief(
        purpose=(
            "Diagnose why a generated image does not look like a real photograph, "
            "and say which part of the prompt to strengthen."
        ),
        role=(
            "You are a photo editor who has spent years spotting retouched images. "
            "You are blunt and specific about what gives an image away."
        ),
        structure=(
            "Reply with a single JSON object and nothing else:\n"
            '{"verdict": "<one sentence: does this read as a real photo?>",\n'
            ' "failing_layers": ["<layer names from: ' + layers + '>"],\n'
            ' "fixes": ["<a phrase to add or change, one per problem>"]}'
        ),
        tone="Direct. No praise, no hedging.",
        constraints=[
            "Judge only what is visible. Do not guess at the prompt beyond it.",
            "Name layers only from this list: " + layers + ".",
            "Every fix must be a concrete phrase that could be pasted into a prompt.",
            "Never suggest a different model or tool — the fix is always the prompt.",
            "If it genuinely looks real, say so and return empty arrays.",
        ],
    )


def analyze_photo_brief(bank):
    """The brief for reverse-engineering a spec from an uploaded photo.

    Different precondition from critique_brief: critique_image() already knows
    the prompt an image came from and asks what's wrong with it. This has no
    prompt at all - an arbitrary photo, possibly not from this app, possibly a
    real photograph with nothing wrong with it. So the model's two jobs are
    read what's actually in the frame (mapped onto this app's own spec
    fields, whitelisted the same way idea_brief's are) and separately judge
    it - those are different questions and get different keys in the reply.
    """
    return build_brief(
        purpose=(
            "Look at a photo and (1) describe what's in it as a character spec for "
            "this app's own photorealistic-avatar pipeline, and (2) judge it as a "
            "photograph - what's working, what's off, what would improve it."
        ),
        role=(
            "You are a portrait photographer and photo editor doing two jobs at "
            "once: reading a scene the way a photographer would describe planning "
            "it, and critiquing the image the way an editor spots what's wrong "
            "with a photo, real or fake."
        ),
        structure=(
            "Reply with a single JSON object and nothing else:\n"
            '{"subject": "<string, physically - age range, hair, skin, distinguishing '
            'marks>",\n'
            ' "wardrobe": "<string, optional>",\n'
            ' "setting": "<string, optional - where and when>",\n'
            ' "action": "<string, optional - what they are physically doing>",\n'
            ' "posing": "<string, optional - how the body is arranged>",\n'
            ' "mood": "<string, optional - expression, two or three words>",\n'
            ' "shot": "<optional, one of: ' + ", ".join(bank["shot_presets"]) + '>",\n'
            ' "analysis": "<2-4 sentences: what is good about this photo, what is '
            'off or fake-looking if anything, what would improve it>"}"'
        ),
        tone="Plain, concrete, photographic. No marketing language, no hedging.",
        constraints=[
            "Use ONLY the keys listed above for the spec fields. Any other key is "
            "discarded.",
            "Describe only what is actually visible. Do not invent a backstory.",
            "Do not write camera, lens, lighting, grain or colour terms into the "
            "spec fields - the app adds those from its own vocabulary. Lighting "
            "observations belong in `analysis`, in plain words, not the spec.",
            "`analysis` is your honest judgement, not a sales pitch - if the photo "
            "already looks fully real, say so plainly rather than inventing a flaw.",
            "Never use these words in the spec fields: " + ", ".join(bank["banned"]) + ".",
        ],
    )


# --------------------------------------------------------------------------- #
# The three actions, each with its validation gate
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Ad copy - the five beats, written to sell the feeling
# --------------------------------------------------------------------------- #
COPY_KEYS = {"pain", "relatable", "shift", "solution", "proof"}


def ad_copy_brief(ad_bank, platform, emotion=None):
    """The brief for drafting the five beats of a UGC ad."""
    import build_ad as ba

    cfg = ba.platforms(ad_bank).get(platform, {})
    feeling = ba.emotions(ad_bank).get(emotion or "", {})

    beat_lines, examples = [], []
    for beat in ba.beats(ad_bank):
        beat_lines.append("  {}  ({}) {}".format(
            beat["key"], beat["label"], beat["must_do"]))
        for line in beat.get("examples", [])[:1]:
            examples.append("{}: {}".format(beat["key"], line))

    constraints = [
        "Use ONLY these keys: " + ", ".join(sorted(COPY_KEYS)) + ". Any other key is discarded.",
        "Beats 1-3 must sell the FEELING. Never list ingredients, specifications, "
        "percentages or technology there - that is what beat 4 is for.",
        "Beat 4 names the product and says plainly what it is. Specifics belong here.",
        "Beat 5 must contain BOTH social proof AND a reason to act now. Proof alone "
        "is the common failure and it reads finished.",
        "Include a call to action.",
        "Write for {} - {}".format(cfg.get("label", platform), cfg.get("tone", "")),
        "One or two short sentences per beat. This is spoken out loud.",
        "Second person. Talk to one viewer, not an audience.",
    ]
    if feeling:
        constraints.append(
            "Target the emotion '{}': {}. Say things like \"{}\", never \"{}\".".format(
                feeling.get("label", emotion), feeling.get("feeling", ""),
                feeling.get("say", ""), feeling.get("not", "")))

    return build_brief(
        purpose=(
            "Write the five beats of a short-form UGC advert, as spoken lines. This is "
            "the Social Media AD Structure from the course."
        ),
        role=(
            "You are a direct-response copywriter who has watched a thousand people "
            "scroll past adverts. You open on the problem in the viewer's own words."
        ),
        structure=(
            "Reply with a single JSON object and nothing else:" + chr(10)
            + chr(10).join(beat_lines)
        ),
        tone="Plain, spoken, specific. No marketing language, no superlatives.",
        constraints=constraints,
        examples=examples,
    )


def copy_from_idea(ad_bank, bank, product, audience, platform, emotion=None,
                   seconds=None, base_spec=None, ask=None):
    """Product + audience -> the five beats of copy, gated by ad_lint.

    Same rule as everywhere else: the model suggests, the linter decides. A reply
    that opens on specifications, or that forgets urgency, is rejected and
    reported rather than written into the ad.
    """
    import ad_lint as al
    import build_ad as ba

    ask = ask or ask_llm.ask
    request = ("product: {}" + chr(10) + "audience: {}" + chr(10)
               + "platform: {}").format(
        (product or "").strip(), (audience or "").strip(), platform)
    text, error = ask(request, system=ad_copy_brief(ad_bank, platform, emotion))
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": text}

    copy = {k: str(v).strip() for k, v in payload.items() if k in COPY_KEYS and str(v).strip()}
    dropped = sorted(set(payload) - COPY_KEYS)
    missing = sorted(COPY_KEYS - set(copy))
    if missing:
        return {"ok": False, "error": "The model skipped: " + ", ".join(missing), "raw": text}

    seconds = seconds or ba.default_length(ad_bank, platform)
    spec = dict(base_spec or {"subject": "a person", "seed": 0})
    shots = ba.compose_ad(ad_bank, spec, platform, seconds, copy=copy, image_bank=bank)
    results = al.lint(ad_bank, shots, platform, seconds)
    got, total = al.score(results)
    failures = [(label, detail) for _, label, passed, detail in results if not passed]

    return {
        "ok": True,
        "accepted": got == total,
        "copy": copy,
        "shots": shots,
        "dropped": dropped,
        "score": got,
        "total": total,
        "failures": failures,
        "reason": "" if got == total else "rejected - " + "; ".join(
            "{}: {}".format(label, detail) for label, detail in failures),
    }


# The stand-in the editor puts in `subject` when the box is empty. Listing it as
# something the user wrote would tell the model to keep a meaningless subject.
PLACEHOLDER_SUBJECT = "a person"


def _describe_current(spec):
    """What the user has already written, as the brief the model works from."""
    lines = []
    for key in ("subject", "wardrobe", "setting", "action", "posing", "mood", "shot",
                "shot_custom", "purpose", "purpose_custom", "aspect"):
        value = str(spec.get(key) or "").strip()
        if key == "subject" and value == PLACEHOLDER_SUBJECT:
            continue
        if value:
            lines.append("{}: {}".format(key, value))
    for line in spec.get("extra", []) or []:
        lines.append("extra: {}".format(line))
    return lines


def autofill_spec(bank, current=None, ask=None):
    """Fill the empty fields of a character spec. Nothing filled is overwritten.

    Returns `spec` (safe to merge) and `suggestions` (NOT merged - lighting and
    composition are the user's to turn on, so they are reported and applied only
    on request). The model still cannot set seed, reference, lock_identity or
    overrides: `lighting` arrives as a plain string and the *app* turns it into
    an override, which is what keeps that rule true rather than nearly true.
    """
    ask = ask or ask_llm.ask
    current = dict(current or {})
    written = _describe_current(current)
    request = (
        "Already filled in (do not change these):" + chr(10)
        + (chr(10).join("  " + line for line in written) if written else "  (nothing yet)")
        + chr(10) + chr(10) + "Fill in the rest."
    )
    text, error = ask(request, system=autofill_brief(bank))
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": text}

    spec = {k: v for k, v in payload.items() if k in SPEC_KEYS}
    dropped = sorted(set(payload) - SPEC_KEYS - SUGGEST_KEYS)
    if isinstance(spec.get("extra"), str):
        spec["extra"] = [spec["extra"]]

    # Anything the model invented for shot/purpose has to be real, or dropped -
    # the same treatment spec_from_idea() gives them.
    for field, validator in (("shot", bp.validate_shot), ("purpose", bp.validate_purpose)):
        if spec.get(field) and validator(bank, spec[field]):
            dropped.append("{}={}".format(field, spec.pop(field)))

    # Held back on purpose. A guide the user did not choose must never reach a
    # prompt - that is the rule the composition work was built around.
    suggestions = {}
    guide = str(payload.get("composition_guide") or "").strip()
    if guide and not bp.validate_guide(bank, guide):
        suggestions["composition_guide"] = guide
    elif guide:
        dropped.append("composition_guide={}".format(guide))
    lighting = str(payload.get("lighting") or "").strip()
    if lighting:
        suggestions["lighting"] = lighting

    # Score what merging would actually produce, so the number shown is the
    # number the user would get. The placeholder subject counts as empty here
    # too, or the preview would score a prompt about "a person".
    merged = dict(current)
    if merged.get("subject") == PLACEHOLDER_SUBJECT:
        merged.pop("subject")
    merged.update({k: v for k, v in spec.items() if v and not merged.get(k)})
    prompt, _ = bp.compose(bank, dict(merged, seed=merged.get("seed", 0)))
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    return {
        "ok": True,
        "spec": spec,
        "suggestions": suggestions,
        "dropped": dropped,
        "score": len(present),
        "passed": len(present) == 8 and not banned,
        "banned": banned,
    }


# --------------------------------------------------------------------------- #
# Cat stories - a scene at a time, gated by story_lint
# --------------------------------------------------------------------------- #
SCENE_KEYS = {"caption", "narration", "action"}


CAST_KEYS = {"subject", "setting"}
TRADE_SCENE_KEYS = {"task", "mishap"}
SITCOM_SCENE_KEYS = {"caption", "lead_action", "foil_action"}


def brief_kind(story_bank, fmt=None):
    """Which brief a format wants, declared by the format itself.

    This used to be three separate `scene_fields(...) == ["task", "mishap"]`
    comparisons in this file - a test for one specific format, written in three
    places, which a third format could only join by adding a fourth branch to
    each. The format names its own brief now.
    """
    import build_story as bs

    return bs.format_cfg(story_bank, fmt).get("brief") or (
        "trade" if bs.scene_fields(story_bank, fmt) == ["task", "mishap"] else "story")


def cast_brief(story_bank, style=None, fmt=None, trade=None, cast=None):
    """The brief for inventing the cat (or the pair) and the place.

    `cast`, when the format has one, names WHICH cast to brief for - the GUI's
    own Cast picker value. Falls back to the format's declared default only
    when no cast was chosen, never silently defaulting once one has been.
    """
    import build_story as bs

    style_cfg = bs.styles(story_bank).get(style or "", {})
    trade_cfg = bs.trades(story_bank).get(trade or "", {})

    # The trade format is two cats working together, and one reference image has
    # to carry BOTH - so the subject is written as a pair from the start rather
    # than a second character being bolted on later.
    if brief_kind(story_bank, fmt) == "sitcom":
        cast_cfg = bs.casts(story_bank).get(
            cast or bs.default_cast(story_bank, fmt) or "", {})
        constraints = [
            "Reply with a single JSON object and nothing else.",
            'Exactly two keys: "subject" and "setting".',
            "  subject - the cast, as ONE phrase. " + (
                cast_cfg.get("subject") and
                "Keep it recognisably this cast: " + cast_cfg["subject"] or
                "Two cats of obviously different sizes, starting with the word \"two\"."),
            "  setting - the one room the whole series happens in, in a few words.",
            "Both under 30 words. No camera, lens, lighting or composition terms.",
            "This is a repeating series: the cast and the room are the same in every "
            "episode, so describe them as fixtures, not as a one-off scene.",
        ]
        return build_brief(
            purpose="Name the recurring cast and the one room the series lives in.",
            role="You cast a short-form comedy series and dress its single standing set.",
            structure='{"subject": "two cats - ...", "setting": "..."}',
            tone="Concrete and plain.",
            constraints=constraints,
        )

    if brief_kind(story_bank, fmt) == "trade":
        constraints = [
            "Reply with a single JSON object and nothing else.",
            'Exactly two keys: "subject" and "setting".',
            "  subject - TWO cats, described as one phrase, starting with the word "
            "\"two\". Give each of them a colour and one distinguishing feature, so "
            "the same pair is recognisable in every shot.",
            "  setting - the one workplace they are in, in a few words.",
            "Both under 25 words. No camera, lens, lighting or composition terms, and "
            "no clothing - the app adds the uniform.",
            "They are a working pair, so make them look like they belong together: "
            "two adult cats, not a kitten and an adult.",
        ]
        if trade_cfg:
            constraints.append("The job is {}: {}".format(
                trade_cfg.get("label", trade), trade_cfg.get("setting", "")))
        example = ('idea: "two cats working on a building site"' + chr(10)
                   + json.dumps({"subject": "two cats - a broad grey tabby with a torn "
                                            "ear and a lean ginger tom with white paws",
                                 "setting": "a half-built concrete floor, rebar and "
                                            "scaffolding, a grey city skyline behind"},
                                indent=1))
        return build_brief(
            purpose="Cast the two animals a short workplace comedy is about, and where "
                    "they work.",
            role="You cast animals for short comedy videos. You pick specific, "
                 "recognisable creatures rather than generic ones.",
            structure='{"subject": "two cats - ...", "setting": "..."}',
            tone="Concrete and plain.",
            constraints=constraints,
            examples=[example],
        )

    constraints = [
        "Reply with a single JSON object and nothing else.",
        'Exactly two keys: "subject" and "setting".',
        "  subject - the animal, described so the same one is recognisable in "
        "every scene: species, colour, markings, one distinguishing feature.",
        "  setting - the one place the story happens, in a few words.",
        "Both under 15 words. No camera, lens, lighting or composition terms - "
        "the app owns all of those and will add them.",
        "One distinguishing feature is what makes the cat the same cat across "
        "nine images. 'a cat' is not an answer.",
    ]
    if style_cfg:
        constraints.append("The look will be {}, so pick a subject that suits it.".format(
            style_cfg.get("label", style)))
    return build_brief(
        purpose="Invent the animal a short-form video is about, and where it happens.",
        role="You cast animals for short comedy videos. You pick specific, "
             "recognisable creatures rather than generic ones.",
        structure='{"subject": "...", "setting": "..."}',
        tone="Concrete and plain.",
        constraints=constraints,
        examples=[
            'idea: "a cat that raids the fridge"' + chr(10)
            + json.dumps({"subject": "a heavy ginger tabby with one torn ear",
                          "setting": "a suburban kitchen at night"}, indent=1)
        ],
    )


def trade_brief(story_bank, arc, style=None, seconds=None, clip_length=None, trade=None):
    """The brief for a set of one-take working-cat gags.

    Deliberately NOT story_brief with different words. This format has no
    captions, no narration and no arc to escalate along - each take is a whole
    joke on its own, so the model is asked for a job and the thing that goes
    wrong, and nothing else.
    """
    import build_story as bs

    beats = bs.beats(story_bank, "trade")
    cfg = bs.trades(story_bank).get(trade or "", {})
    scene_lines = []
    for key in bs.scene_keys(story_bank, arc, seconds, clip_length, "trade"):
        beat_key = key.split("-")[0]
        beat = beats.get(beat_key, {})
        scene_lines.append("  \"{}\"  ({}) {}".format(
            key, beat.get("label", beat_key), beat.get("must_do", "")))

    constraints = [
        "Use ONLY these scene keys: " + ", ".join(
            '"{}"'.format(line.split('"')[1]) for line in scene_lines) + ".",
        "Each scene is an object with exactly two fields: task, mishap.",
        "  task   - the job they are doing, as a phrase. Something a real tradesperson "
        "does, described plainly.",
        "  mishap - the one physical thing that goes wrong, as a phrase.",
        "Every scene's `task` must be a DIFFERENT job. Two takes of the same job is "
        "padding, and it is where people scroll.",
        "The whole beat happens in ONE continuous shot: they work, it goes wrong, they "
        "react. Never describe a cut, a camera move or a close-up - the camera is "
        "locked off and does not move.",
        "No dialogue, no captions, no narration. Nobody speaks in these videos.",
        "The cats take the job completely seriously. The comedy is the deadpan "
        "competence meeting an accident, never the cats being silly on purpose.",
        "Do not describe clothing - the app puts them in uniform.",
    ]
    if cfg:
        constraints.append("The trade is {}. Real tasks there: {}.".format(
            cfg.get("label", trade), "; ".join(cfg.get("tasks", [])[:3])))
    style_cfg = bs.styles(story_bank).get(style or "", {})
    if style_cfg:
        constraints.append("Visual style is {}: {}".format(
            style_cfg.get("label", style), style_cfg.get("note", "")))

    return build_brief(
        purpose="Write a set of one-take gags about two cats doing a real job badly.",
        role="You write physical comedy for short vertical video. You write what the "
             "camera sees, never what anyone says.",
        structure=("Reply with a single JSON object and nothing else. One key per scene:"
                   + chr(10) + chr(10).join(scene_lines)),
        tone="Deadpan. Plain description. No jokes in the writing - the joke is the event.",
        constraints=constraints,
        examples=[
            'idea: "cats on a building site"' + chr(10)
            + json.dumps({
                "task": {"task": "shovelling wet cement beside a green wheelbarrow",
                         "mishap": "one shoves the other and it lands flat on its back"},
                "task-2": {"task": "smoothing wet plaster onto a wall with a trowel",
                           "mishap": "the other walks through it and leaves paw prints"},
            }, indent=1)
        ],
    )


def autofill_story(story_bank, bank, idea, current=None, arc="classic", style=None,
                   seconds=None, clip_length=None, ask=None, fmt=None, trade=None,
                   cast=None):
    """Idea -> the cat, the place, and every scene. Blanks only, then gated.

    Two calls, because they are two different jobs: cast the animal, then write
    the story about it. The first is merged BLANKS-ONLY - a subject already
    typed in survives and becomes part of the brief for the second - and the
    second is `story_from_idea`, which already re-scores through story_lint and
    reports rather than accepts a near miss.

    The whitelist rule holds throughout: the model may set `subject`, `setting`
    and the scene words. It cannot set seed, reference, lock_identity or
    overrides, here or anywhere else.

    `cast` names which sitcom cast this is for - the GUI's own Cast picker
    value. A cast that already declares both subject and setting (every
    sitcom cast does) needs no model call to invent them at all: skip it, and
    leave both keys unset so apply_cast() fills them in deterministically
    later, inside compose_story(). Without this a click of "Auto-fill the
    whole story" always spent a real call inventing a subject, ALWAYS briefed
    on the format's default cast (cast_brief() had no way to hear which one
    was actually picked) - so selecting "tommy" and autofilling silently
    produced the default pair instead. See CatsView.base_spec()'s own
    _cast_supplies_subject() for the matching rule on the GUI's typed-field
    side.
    """
    import build_story as bs

    ask = ask or ask_llm.ask
    current = dict(current or {})
    if current.get("subject") == PLACEHOLDER_SUBJECT:
        current.pop("subject")

    kind = brief_kind(story_bank, fmt)
    cast_cfg = (bs.casts(story_bank).get(cast or bs.default_cast(story_bank, fmt) or "", {})
               if kind == "sitcom" else {})
    cast_supplies_both = bool(cast_cfg.get("subject") and cast_cfg.get("setting"))

    filled = {k: v for k, v in current.items() if k in CAST_KEYS and str(v or "").strip()}
    cast_fields, cast_dropped = {}, []
    if len(filled) < len(CAST_KEYS) and not cast_supplies_both:
        request = 'idea: "{}"'.format((idea or "").strip())
        if filled:
            request += chr(10) + "Already chosen (do not change): " + json.dumps(filled)
        text, error = ask(request, system=cast_brief(story_bank, style, fmt, trade, cast))
        if error:
            return {"ok": False, "error": error}
        payload = ask_llm.extract_json(text)
        if not isinstance(payload, dict):
            return {"ok": False, "error": "The model did not return JSON.", "raw": text}
        cast_dropped = sorted(set(payload) - CAST_KEYS)
        for key in CAST_KEYS:
            value = str(payload.get(key) or "").strip()
            # Blanks only. What he typed is the brief, not a suggestion.
            if value and not filled.get(key):
                cast_fields[key] = value

    spec = dict(current)
    spec.update(cast_fields)
    # The pair format needs two animals in the subject or its own gate refuses
    # it, so the fallback names two rather than one - but only when nothing
    # else will fill it in. A sitcom cast that supplies its own subject must
    # win this fallback, not lose to it: apply_cast() is what actually fills
    # it, downstream in compose_story(), and it only runs when the key is
    # still absent here.
    if kind in ("trade", "sitcom") and not cast_cfg.get("subject"):
        spec.setdefault("subject", "two cats")
    elif kind not in ("trade", "sitcom"):
        spec.setdefault("subject", "a cat")
    spec.setdefault("seed", 0)

    result = story_from_idea(story_bank, bank, idea, arc=arc, style=style,
                             seconds=seconds, clip_length=clip_length,
                             base_spec=spec, ask=ask, fmt=fmt, trade=trade, cast=cast)
    result["cast"] = cast_fields
    result["spec"] = spec
    result["dropped"] = sorted(set(result.get("dropped") or []) | set(cast_dropped))
    return result


def sitcom_brief(story_bank, arc, style=None, seconds=None, clip_length=None, cast=None):
    """The brief for one episode of a two-character pet sitcom.

    Deliberately NOT story_brief with different words. This format has no
    narration (it is built to read on mute), it has TWO characters whose
    actions are authored separately, and it has a content gate - safety_lint -
    that no other format runs. Asking the story brief for this would get
    narration nobody uses and staging the gate would reject.

    The harmlessness rules are restated here as constraints rather than left to
    the linter alone. A linter that only rejects teaches nothing; a brief that
    states the rule up front gets a usable first draft, and safety_lint is
    still what decides.

    `cast`, when given, is which cast the episode is for - without it this
    silently briefed every sitcom autofill on the format's DEFAULT cast's
    lead/foil labels, so picking "tommy" (lead: Tommy, foil: the unseen
    owner's hand) still got the model told to write for "The kitten" and
    "The mother cat".
    """
    import build_story as bs

    beats = bs.beats(story_bank, "sitcom")
    cast_key = cast or bs.default_cast(story_bank, "sitcom") or ""
    cast_cfg = bs.casts(story_bank).get(cast_key, {})
    members = {m.get("role"): m for m in cast_cfg.get("members", [])}
    lead = members.get("lead", {}).get("label", "the troublemaker")
    foil = members.get("foil", {}).get("label", "the authority")

    scene_lines = []
    for key in bs.scene_keys(story_bank, arc, seconds, clip_length, "sitcom"):
        beat_key = key.split("-")[0]
        beat = beats.get(beat_key, {})
        scene_lines.append('  "{}"  ({}) {}'.format(
            key, beat.get("label", beat_key), beat.get("must_do", "")))

    constraints = [
        "Use ONLY these scene keys: " + ", ".join(
            '"{}"'.format(line.split('"')[1]) for line in scene_lines) + ".",
        "Each scene is an object with exactly three fields: caption, lead_action, "
        "foil_action.",
        "  caption     - the on-screen words. Under 8 words. This is what the viewer "
        "reads; the last scene's caption is the punchline.",
        "  lead_action - what {} does, as a phrase.".format(lead),
        "  foil_action - what {} does, as a phrase.".format(foil),
        "Every scene's lead_action must be DIFFERENT. The same action twice is one "
        "shot repeated, which is where people scroll.",
        "There is no narration and nobody speaks. The captions carry every word.",
        "The camera is locked off and never moves. Never describe a cut, a zoom or a "
        "camera move.",
        # The content gate, stated rather than only enforced.
        "HARMLESSNESS, and this is checked by a linter that will reject the reply: "
        "the physical comedy is a soft, cartoon-like paw tap with the claws IN. "
        "Whenever you describe contact, say so in the same phrase - 'a soft "
        "cartoon-like paw tap, claws in' rather than 'a swat'.",
        "Never describe injury, pain, blood, fear, cowering, trembling or punishment. "
        "The drama is PERFORMED outrage, and the relationship underneath it is "
        "affectionate.",
        "Never put anything sharp, hot, toxic, electrical or high in the scene - no "
        "knives, stoves, medication, chocolate, balconies or cables. Props are safe "
        "miniatures: a rubber phone, a plush toy, a soft silicone bottle.",
    ]
    return build_brief(
        purpose="Write one episode of a repeating two-character pet sitcom.",
        role="You write 15-second physical comedy that reads on mute.",
        structure="Scenes, in order:\n" + "\n".join(scene_lines),
        constraints=constraints,
    )


def story_brief(story_bank, arc, style=None, seconds=None, clip_length=None):
    """The brief for writing one cat story, scene by scene."""
    import build_story as bs

    beats = bs.beats(story_bank)
    scene_lines = []
    for key in bs.scene_keys(story_bank, arc, seconds, clip_length):
        beat_key = key.split("-")[0]
        cfg = beats.get(beat_key, {})
        scene_lines.append("  \"{}\"  ({}) {}".format(
            key, cfg.get("label", beat_key), cfg.get("must_do", "")))

    style_cfg = bs.styles(story_bank).get(style or "", {})
    constraints = [
        "Use ONLY these scene keys: " + ", ".join(
            '"{}"'.format(line.split('"')[1]) for line in scene_lines) + ".",
        "Each scene is an object with exactly three fields: caption, narration, action.",
        "  caption   - the on-screen text. Under 8 words. Not a description of the shot.",
        "  narration - one spoken line. Under 15 words. Written to be read aloud.",
        "  action    - what the cat is physically DOING in this scene, as a phrase.",
        "Every scene's `action` must be different. A story where the cat does the "
        "same thing five times is one shot repeated, and it is where people scroll.",
        "The hook is about {} seconds on screen. Write its caption to work in that "
        "long.".format(int(story_bank.get("hook_seconds", 3))),
        "Do not write camera moves, shot types, lighting or lens terms - the app "
        "owns all of those.",
        "Keep the cat the same cat throughout. Do not change its colour or breed.",
        "The comedy is behavioural: a real cat committing completely to a human "
        "goal. Never have the cat talk.",
    ]
    if style_cfg:
        constraints.append("Visual style is {}: {}".format(
            style_cfg.get("label", style), style_cfg.get("note", "")))

    return build_brief(
        purpose=(
            "Write a short-form cat video, scene by scene: what happens, what it says "
            "on screen, and what the voiceover reads."
        ),
        role=(
            "You are a short-form comedy writer. You write behaviour, not jokes - the "
            "funny part is always what the animal does, played completely straight."
        ),
        structure=(
            "Reply with a single JSON object and nothing else. One key per scene:"
            + chr(10) + chr(10).join(scene_lines)
        ),
        tone="Deadpan. Short sentences. No exclamation marks, no puns.",
        constraints=constraints,
        examples=[
            'idea: "a cat that keeps stealing from the fridge"' + chr(10)
            + json.dumps({
                "hook": {"caption": "He has done this before.",
                         "narration": "Every night. Same time.",
                         "action": "staring at the fridge handle"},
                "setup": {"caption": "Meet Gary.",
                          "narration": "Nine kilos of determination.",
                          "action": "padding across the kitchen tiles"},
                "escalation": {"caption": "He has a system.",
                               "narration": "The handle first, then the shelf.",
                               "action": "hauling the fridge door open with both paws"},
                "twist": {"caption": "He was not alone.",
                          "narration": "The dog had been watching for a while.",
                          "action": "freezing mid-reach with his ears back"},
                "payoff": {"caption": "They split it.",
                           "narration": "Settled like adults.",
                           "action": "sitting beside a dog sharing a slice of ham"},
            }, indent=1)
        ],
    )


def story_from_idea(story_bank, bank, idea, arc="classic", style=None, seconds=None,
                    clip_length=None, base_spec=None, ask=None, fmt=None, trade=None,
                    cast=None):
    """An idea -> a whole story, gated by story_lint.

    Same rule as everywhere else: the model suggests, the linter decides. A story
    whose scenes all do the same thing, or whose hook has no words, is reported
    rather than written in.

    `cast` passes straight through to compose_story() - without it, a format
    with more than one cast (sitcom) always fell back to its bank-declared
    default there, no matter which one the caller actually meant.
    """
    import build_story as bs
    import story_lint as stl

    ask = ask or ask_llm.ask
    fields = bs.scene_fields(story_bank, fmt)
    # A format brings its own brief and its own scene fields. Asking a
    # one-take gag for a caption and a narration line would get both, and both
    # would be wrong: these videos have no words in them at all.
    kind = brief_kind(story_bank, fmt)
    if kind == "trade":
        system = trade_brief(story_bank, arc, style, seconds, clip_length, trade)
        allowed = TRADE_SCENE_KEYS
    elif kind == "sitcom":
        system = sitcom_brief(story_bank, arc, style, seconds, clip_length, cast)
        allowed = SITCOM_SCENE_KEYS
    else:
        system = story_brief(story_bank, arc, style, seconds, clip_length)
        allowed = SCENE_KEYS

    request = 'idea: "{}"'.format((idea or "").strip())
    text, error = ask(request, system=system)
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": text}

    # One source for this list: the runtime, not the arc alone, decides how many
    # scenes there are, so asking the model for the arc's five beats when the
    # story needs seven would leave two scenes wordless.
    wanted = bs.scene_keys(story_bank, arc, seconds, clip_length, fmt)

    script, dropped = {}, sorted(set(payload) - set(wanted))
    for key in wanted:
        block = payload.get(key)
        if isinstance(block, dict):
            script[key] = {k: str(v).strip() for k, v in block.items()
                           if k in allowed and str(v).strip()}
    missing = [k for k in wanted if not script.get(k)]
    if missing:
        return {"ok": False, "error": "The model skipped: " + ", ".join(missing),
                "raw": text}

    spec = dict(base_spec or {"subject": "a cat", "seed": 0})
    scenes = bs.compose_story(story_bank, spec, arc=arc, seconds=seconds,
                              clip_length=clip_length, style=style, script=script,
                              reference="scene-1.png", image_bank=bank,
                              fmt=fmt, trade=trade, cast=cast)
    results = stl.lint(story_bank, scenes, arc, seconds, image_bank=bank, fmt=fmt)
    got, total = stl.score(results)
    failures = [(label, detail) for _, label, passed, detail in results if not passed]

    return {
        "ok": True,
        "accepted": got == total,
        "script": script,
        "scenes": scenes,
        "dropped": dropped,
        "score": got,
        "total": total,
        "failures": failures,
        "reason": "" if got == total else "rejected - " + "; ".join(
            "{}: {}".format(label, detail) for label, detail in failures),
    }


# --------------------------------------------------------------------------- #
# Custom prompts - a hand-written prompt in, its three parts editable, adapted
# by instruction or by reference image
# --------------------------------------------------------------------------- #
CUSTOM_PROMPT_KEYS = {"subject", "background", "style"}


def custom_prompt_analyze_brief(bank, has_image=False):
    """The brief for splitting a hand-written prompt into its three parts."""
    constraints = [
        "Use ONLY the keys subject, background, style. Any other key is discarded.",
        "Do not invent a detail that was not already in the text.",
        "Do not add a composition guide (rule of thirds, phi grid, golden spiral, "
        "...) that the original text did not already name.",
        "Never use these words: " + ", ".join(bank["banned"]) + ".",
    ]
    if has_image:
        constraints.append(
            "A reference image is attached. The text is what this prompt is "
            "based on - let the image confirm or sharpen physical detail where "
            "the text is vague, but do not invent beyond what it shows."
        )
    return build_brief(
        purpose=(
            "Split a fully-written image prompt into the three parts this app "
            "edits separately: Subject, Background, Style & Atmosphere."
        ),
        role=(
            "You are a photo editor's assistant who reads a shot description and "
            "files each sentence into the right one of three buckets, without "
            "losing or inventing detail."
        ),
        structure=(
            "Reply with a single JSON object and nothing else:\n"
            '  {"subject": "...", "background": "...", "style": "..."}\n'
            "  subject    - who/what is in frame: appearance, pose, expression, "
            "what they are holding or wearing.\n"
            "  background - the setting: place, other people or animals present, "
            "weather, time of day, anything happening behind the subject.\n"
            "  style      - camera, lens, lighting, mood, and any realism/quality "
            "language."
        ),
        tone="Keep the writer's own words wherever they already fit. Sort, don't rewrite.",
        constraints=constraints,
    )


def custom_prompt_refine_brief(bank, has_image=False):
    """The brief for adapting the three parts to an instruction, a reference
    image, or both."""
    constraints = [
        "Use ONLY the keys subject, background, style. Any other key is discarded.",
        "Change only what the instruction (or the reference image) asks for. Do "
        "not rewrite parts it does not touch.",
        "Do not add a composition guide (rule of thirds, phi grid, golden spiral, "
        "...) unless explicitly asked for.",
        "Never use these words: " + ", ".join(bank["banned"]) + ".",
    ]
    if has_image:
        constraints.append(
            "A reference image is attached - look at it and adapt the wording to "
            "match what it shows, only where the instruction (or, if there is no "
            "instruction, the image itself) asks you to."
        )
    return build_brief(
        purpose=(
            "Adapt a three-part image prompt (Subject, Background, Style & "
            "Atmosphere) to a change instruction, a reference image, or both."
        ),
        role=(
            "You are a photo editor's assistant revising a shot description. You "
            "change only what was asked for and leave everything else exactly as "
            "written."
        ),
        structure=(
            "Reply with a single JSON object and nothing else, all three keys "
            "every time - echo back any part that was not touched:\n"
            '  {"subject": "...", "background": "...", "style": "..."}'
        ),
        tone="Match the tone and level of detail already in the text.",
        constraints=constraints,
    )


def analyze_custom_prompt(bank, text, image_path=None, ask=None):
    """A hand-written prompt (+ an optional reference image) -> its three parts.

    A first pass the user is expected to review and hand-edit, not a final
    answer - a key missing from the reply defaults to an empty string rather
    than failing the whole call.
    """
    ask = ask or ask_llm.ask
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Paste a prompt first."}

    request = "PROMPT TO SPLIT:\n{}".format(text)
    images = [image_path] if image_path else ()
    reply, error = ask(
        request, system=custom_prompt_analyze_brief(bank, bool(image_path)), images=images)
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(reply)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": reply}

    fields = {k: str(payload.get(k) or "").strip() for k in CUSTOM_PROMPT_KEYS}
    dropped = sorted(set(payload) - CUSTOM_PROMPT_KEYS)
    return {"ok": True, "fields": fields, "dropped": dropped}


def refine_custom_prompt(bank, fields, instruction, image_path=None, ask=None):
    """Current {subject, background, style} + an instruction and/or a
    reference image -> the updated three fields.

    Either the instruction or the image is enough on its own - a photo with no
    words still says what to match. The model returns all three keys every
    time, echoing back whatever was not touched; a key missing from the reply
    falls back to the field's current value rather than being blanked.
    """
    ask = ask or ask_llm.ask
    instruction = (instruction or "").strip()
    if not instruction and not image_path:
        return {"ok": False, "error": "Say what to change, or attach a reference image, first."}

    current = {k: str((fields or {}).get(k) or "") for k in CUSTOM_PROMPT_KEYS}
    request = (
        "CURRENT:\n" + json.dumps(current, indent=1)
        + "\n\nINSTRUCTION:\n" + (instruction or "(none - go by the reference image)")
    )
    images = [image_path] if image_path else ()
    reply, error = ask(
        request, system=custom_prompt_refine_brief(bank, bool(image_path)), images=images)
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(reply)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": reply}

    dropped = sorted(set(payload) - CUSTOM_PROMPT_KEYS)
    fields_out = dict(current)
    for key in CUSTOM_PROMPT_KEYS:
        value = str(payload.get(key) or "").strip()
        if value:
            fields_out[key] = value
    return {"ok": True, "fields": fields_out, "dropped": dropped}


def spec_from_idea(bank, idea, ask=None):
    """One line -> a validated character spec. Unknown keys are dropped."""
    ask = ask or ask_llm.ask
    text, error = ask('idea: "{}"'.format(idea.strip()), system=idea_brief(bank))
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if payload is None:
        return {"ok": False, "error": "The model did not return JSON.", "raw": text}

    spec = {k: v for k, v in payload.items() if k in SPEC_KEYS}
    dropped = sorted(set(payload) - SPEC_KEYS)

    if not spec.get("subject"):
        return {"ok": False, "error": "The model returned no subject.", "raw": text}
    if isinstance(spec.get("extra"), str):
        spec["extra"] = [spec["extra"]]

    # Anything the model invented for shot/purpose has to be real, or dropped.
    for field, validator in (("shot", bp.validate_shot), ("purpose", bp.validate_purpose)):
        if spec.get(field) and validator(bank, spec[field]):
            dropped.append("{}={}".format(field, spec.pop(field)))

    prompt, _ = bp.compose(bank, dict(spec, seed=0))
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    return {
        "ok": True,
        "spec": spec,
        "dropped": dropped,
        "score": len(present),
        "passed": len(present) == 8 and not banned,
        "banned": banned,
    }


def upgrade_prompt(bank, prompt, ask=None):
    """Rewrite a prompt — but only accept a rewrite that still passes the gate."""
    ask = ask or ask_llm.ask
    before_present, _, _, _, _ = rl.lint(prompt.lower(), bank)
    before_score = len(before_present)

    text, error = ask(prompt, system=upgrade_brief(bank))
    if error:
        return {"ok": False, "accepted": False, "prompt": prompt, "error": error,
                "before_score": before_score}

    candidate = text.strip().strip('"').strip()
    present, _, banned, _, _ = rl.lint(candidate.lower(), bank)
    score = len(present)

    if banned:
        reason = "rejected — the rewrite introduced: {}".format(", ".join(banned))
    elif score < 8:
        missing = [cfg["label"] for _, cfg, _ in _missing(candidate, bank)]
        reason = "rejected — the rewrite dropped to {}/8 (lost: {})".format(
            score, ", ".join(missing)
        )
    elif len(candidate.split()) > MAX_UPGRADE_WORDS * 1.5:
        reason = "rejected — the rewrite ran to {} words".format(len(candidate.split()))
    else:
        return {"ok": True, "accepted": True, "prompt": candidate,
                "before_score": before_score, "score": score,
                "reason": "accepted — {}/8, {} words".format(score, len(candidate.split()))}

    # Rejected: the original stands. This is the gate doing its job.
    return {"ok": True, "accepted": False, "prompt": prompt, "candidate": candidate,
            "before_score": before_score, "score": score, "reason": reason}


def _missing(text, bank):
    _, missing, _, _, _ = rl.lint(text.lower(), bank)
    return missing


def critique_image(bank, prompt, image_path, ask=None):
    """Ask why an image doesn't read as real. Falls back to raw text on bad JSON."""
    ask = ask or ask_llm.ask
    path = Path(image_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {"ok": False, "error": "Image not found: {}".format(path)}

    user = (
        "This image was generated from the prompt below. It does not look real "
        "enough. What is giving it away?\n\nPROMPT:\n{}".format(prompt)
    )
    text, error = ask(user, system=critique_brief(bank), images=[str(path)])
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if payload is None:
        return {"ok": True, "verdict": text.strip(), "failing_layers": [], "fixes": [],
                "raw": text}

    known = set(bank["layers"].keys())
    return {
        "ok": True,
        "verdict": str(payload.get("verdict", "")).strip(),
        "failing_layers": [l for l in payload.get("failing_layers", []) if l in known],
        "fixes": [str(f) for f in payload.get("fixes", []) if str(f).strip()],
        "raw": text,
    }


def analyze_uploaded_image(bank, image_path, ask=None):
    """Any local photo -> (a whitelisted spec suggestion, a plain-English verdict).

    The missing case critique_image() can't cover: that function requires an
    already-known prompt ("this was generated from X"), which an arbitrary
    uploaded photo - not necessarily made by this app at all - does not have.
    Same shape as spec_from_idea() otherwise: SPEC_KEYS is the only thing a
    reply can set, the model's read is re-composed through build_prompt.compose()
    and re-scored through realism_lint - "the text model suggests, realism_lint
    decides" applies here exactly as everywhere else, not as an exception to it.
    `analysis` is commentary, not spec data, so it is returned as-is rather
    than whitelisted the way the spec fields are.
    """
    ask = ask or ask_llm.ask
    path = Path(image_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {"ok": False, "error": "Image not found: {}".format(path)}

    text, error = ask(
        "Analyse this photo.", system=analyze_photo_brief(bank), images=[str(path)])
    if error:
        return {"ok": False, "error": error}

    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "The model did not return JSON.", "raw": text}

    spec = {k: v for k, v in payload.items() if k in SPEC_KEYS}
    dropped = sorted(set(payload) - SPEC_KEYS - {"analysis"})
    analysis = str(payload.get("analysis") or "").strip()

    if not spec.get("subject"):
        return {"ok": False, "error": "The model could not read a subject from this "
                "photo.", "raw": text}

    # Anything the model invented for shot has to be real, or dropped - the
    # same treatment spec_from_idea() gives it.
    if spec.get("shot") and bp.validate_shot(bank, spec["shot"]):
        dropped.append("shot={}".format(spec.pop("shot")))

    prompt, _ = bp.compose(bank, dict(spec, seed=0))
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    return {
        "ok": True,
        "spec": spec,
        "analysis": analysis,
        "dropped": dropped,
        "score": len(present),
        "passed": len(present) == 8 and not banned,
        "banned": banned,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Six-part briefs for the text model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_idea = sub.add_parser("idea", help="one line -> character spec JSON")
    p_idea.add_argument("idea")
    p_idea.add_argument("--save", help="write the spec to this path")

    p_up = sub.add_parser("upgrade", help="rewrite a prompt, gated on the linter")
    p_up.add_argument("prompt_file")

    p_cr = sub.add_parser("critique", help="why doesn't this image look real?")
    p_cr.add_argument("prompt_file")
    p_cr.add_argument("image")

    p_an = sub.add_parser("analyze", help="any photo -> a spec suggestion + a verdict")
    p_an.add_argument("image")
    p_an.add_argument("--save", help="write the spec suggestion to this path")

    p_auto = sub.add_parser("autofill", help="fill the empty fields of a spec")
    p_auto.add_argument("spec", nargs="?", help="path to a partial spec JSON")
    p_auto.add_argument("--save", help="write the merged spec to this path")

    p_show = sub.add_parser("show", help="print a brief without calling the model")
    p_show.add_argument("which",
                        choices=["idea", "autofill", "upgrade", "critique", "analyze"])

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    bank = bp.load_bank()

    def read_prompt(path_value):
        path = Path(path_value)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        return path.read_text(encoding="utf-8").strip()

    if args.command == "show":
        print({"idea": idea_brief, "autofill": autofill_brief, "upgrade": upgrade_brief,
               "critique": critique_brief, "analyze": analyze_photo_brief}[args.which](bank))
        return 0

    if args.command == "autofill":
        current = {}
        if args.spec:
            path = Path(args.spec)
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists():
                sys.exit("Spec not found: {}".format(path))
            current = json.loads(path.read_text(encoding="utf-8"))
        result = autofill_spec(bank, current)
        if not result["ok"]:
            print(result["error"], file=sys.stderr)
            return 3
        merged = dict(current)
        merged.update({k: v for k, v in result["spec"].items() if v and not current.get(k)})
        print(json.dumps(merged, indent=2, ensure_ascii=False))
        for key, value in result["suggestions"].items():
            print("[suggest] {}: {}  (not applied)".format(key, value), file=sys.stderr)
        if result["dropped"]:
            print("[dropped] {}".format(", ".join(result["dropped"])), file=sys.stderr)
        print("[lint]    {}/8 {}".format(
            result["score"], "PASS" if result["passed"] else "needs work"), file=sys.stderr)
        if args.save:
            out = Path(args.save)
            if not out.is_absolute():
                out = ROOT / out
            out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print("[written] {}".format(out), file=sys.stderr)
        return 0

    if args.command == "idea":
        result = spec_from_idea(bank, args.idea)
        if not result["ok"]:
            print(result["error"], file=sys.stderr)
            return 3
        print(json.dumps(result["spec"], indent=2, ensure_ascii=False))
        if result["dropped"]:
            print("[dropped] {}".format(", ".join(result["dropped"])), file=sys.stderr)
        print("[lint]    {}/8 {}".format(
            result["score"], "PASS" if result["passed"] else "needs work"), file=sys.stderr)
        if args.save:
            out = Path(args.save)
            if not out.is_absolute():
                out = ROOT / out
            out.write_text(json.dumps(result["spec"], indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print("[written] {}".format(out), file=sys.stderr)
        return 0

    if args.command == "analyze":
        result = analyze_uploaded_image(bank, args.image)
        if not result["ok"]:
            print(result["error"], file=sys.stderr)
            return 3
        print(json.dumps(result["spec"], indent=2, ensure_ascii=False))
        print("\n[analysis] {}".format(result["analysis"]), file=sys.stderr)
        if result["dropped"]:
            print("[dropped]  {}".format(", ".join(result["dropped"])), file=sys.stderr)
        print("[lint]     {}/8 {}".format(
            result["score"], "PASS" if result["passed"] else "needs work"), file=sys.stderr)
        if args.save:
            out = Path(args.save)
            if not out.is_absolute():
                out = ROOT / out
            out.write_text(json.dumps(result["spec"], indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print("[written]  {}".format(out), file=sys.stderr)
        return 0

    if args.command == "upgrade":
        result = upgrade_prompt(bank, read_prompt(args.prompt_file))
        if not result["ok"]:
            print(result["error"], file=sys.stderr)
            return 3
        print(result["prompt"])
        print("[{}] {}".format("ok" if result["accepted"] else "gate", result["reason"]),
              file=sys.stderr)
        return 0 if result["accepted"] else 5

    result = critique_image(bank, read_prompt(args.prompt_file), args.image)
    if not result["ok"]:
        print(result["error"], file=sys.stderr)
        return 3
    print(result["verdict"])
    for layer in result["failing_layers"]:
        print("  weak layer: {}".format(layer))
    for fix in result["fixes"]:
        print("  fix: {}".format(fix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
