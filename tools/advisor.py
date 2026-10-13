"""The in-app expert - a running conversation, not a one-shot brief.

Every other AI feature in this project (brief.py's four actions) is single-shot:
one system message, one user message, no memory of what came before. This is
the one exception - a real back-and-forth about how to use AI Video Studio
itself to get a premium-quality image - but it inherits brief.py's central rule
unchanged: the model suggests, realism_lint decides. A reply may propose a
ready spec by fencing it as ```spec {...}```; nothing else in a reply is ever
trusted or written into a prompt, and the fenced block itself is whitelisted,
recomposed and relinted exactly like every other AI-suggested spec in this app.

Usage:
    python tools/advisor.py show
    python tools/advisor.py chat "how do I get better skin texture"
    python tools/advisor.py chat "and then?" --history-file turns.json
    python tools/advisor.py chat "why doesn't this look real" --image out.png
    python tools/advisor.py chat "hello" --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

import ask_llm
import brief
import build_camera_angle as bca
import build_color as bcol
import build_composition as bc
import build_evidence as bev
import build_lighting as bl
import build_posing as bpo
import build_prompt as bp
import realism_lint as rl

ROOT = Path(__file__).resolve().parent.parent

# The optional second half of a fenced spec block: picks for the five
# technique sections, each validated against that section's own bank and
# composed by that section's own compose_X(). See _finalize_sections().
SECTIONS_KEY = "sections"
SECTION_NAMES = ("lighting", "composition", "color", "posing", "camera_angle", "evidence")

# Optional, per-turn persona overlays for the Chat tab's "Ask as..." picker -
# a curated subset of the AI Video Bootcamp "AI Chat Cheat Sheet" 's 20 named
# role-play chat templates, narrowed to the ones actually relevant to an
# avatar/video generation tool (the rest - Brand Strategist, Landing Page
# Expert, Email Marketing Expert, Business Consultant, Personal Brand Coach,
# Offer Strategist, Sales Page Critic, Customer Research Expert, Product
# Description Writer - are general small-business/marketing coaching, outside
# this app's scope). Each overlay ADDS to advisor_brief()'s system prompt for
# one turn only - it never replaces the core rules (bank-only vocabulary, the
# gate decides, ask before guessing), the same way `image_path` and
# `context_prompt` are already scoped to a single turn rather than the whole
# conversation.
PERSONAS = {
    "idea-generator": {
        "label": "Idea Generator",
        "when": "Stuck for a concept.",
        "overlay": (
            "For this turn, lead with breadth: offer 3-5 clearly different "
            "concept directions (different angle, mood or setting), each one "
            "sentence, before narrowing to any one spec - let the user pick "
            "first."
        ),
    },
    "creative-director": {
        "label": "Creative Director",
        "when": "A rough idea needs to be stronger, not just described.",
        "overlay": (
            "For this turn, be direct about what's weak, predictable or "
            "generic in the idea as described, then propose one sharper, "
            "more specific version of it before building a spec."
        ),
    },
    "hook-writer": {
        "label": "Scroll-Stopping Hook Writer",
        "when": "Need a stronger opening line for a caption, ad or video.",
        "overlay": (
            "For this turn, focus on the opening: offer 3-5 concrete hook-"
            "line options for whatever this is captioning or advertising, "
            "before anything else."
        ),
    },
    "ugc-scriptwriter": {
        "label": "UGC Scriptwriter",
        "when": "A natural, believable short-form ad script.",
        "overlay": (
            "For this turn, write like the line a real person would "
            "actually say on camera - casual, specific, never a paid-actor "
            "or corporate-ad tone. Avoid generic influencer phrases like "
            "\"game changer,\" \"you need this,\" \"I'm obsessed,\" or "
            "\"this changed my life\" unless they genuinely fit what the "
            "user described. Never invent a transformation, result or "
            "claim - medical, financial or otherwise - the user did not "
            "actually describe. This complements Ads' own five-beat "
            "structure, so keep any script short-form."
        ),
    },
    "script-doctor": {
        "label": "Script Doctor",
        "when": "A script or caption feels boring or robotic.",
        "overlay": (
            "For this turn, name specifically what sounds robotic, generic "
            "or cringe in what the user pasted, then rewrite it tighter - "
            "cut filler, keep the meaning."
        ),
    },
    "brutally-honest-reviewer": {
        "label": "Brutally Honest Reviewer",
        "when": "Real feedback instead of praise.",
        "overlay": (
            "For this turn, lead with what's weak or generic before saying "
            "what works - candid, not encouraging by default, the way a "
            "tough but fair mentor would review this."
        ),
    },
}

# The AI Chat Cheat Sheet's "follow-up commands" - short, reusable phrases
# meant to be sent as the next chat turn to push a first draft further rather
# than accepting it. (label, phrase): `label` is short enough for a button,
# `phrase` is the full text actually sent as the chat turn - the same split
# every bank entry here already makes between a short `label` and the fuller
# text it stands for. Exposed as a plain list (not a bank - this is
# conversational text, not vocabulary the realism gate needs to know about),
# so the Chat tab can render `label` as a one-click quick reply; clicking one
# just sends `phrase` as an ordinary user turn through chat() below, no new
# plumbing needed.
FOLLOW_UPS = [
    ("Specific", "Make this more specific."),
    ("Realistic", "Make this more realistic."),
    ("Original", "Make this less generic."),
    ("Hook", "Make the hook stronger."),
    ("Simplify", "Simplify this - it feels too busy."),
]


def persona_overlay(persona):
    """The extra system-prompt text for `persona`, or "" for None/unknown -
    unknown is silently ignored rather than raising, the same tolerance
    `_picked()` already gives an invalid bank key elsewhere in this file."""
    cfg = PERSONAS.get(persona)
    if not cfg:
        return ""
    return "\n\nFOR THIS TURN ONLY, ALSO ASK AS: {} - {}".format(cfg["label"], cfg["overlay"])


# One line each - the nav rail's own map, labels matching NAV_ITEMS. tools/
# never imports the GUI layer, so this is kept here rather than read from
# ui/main_window.py; if a section is added to NAV_ITEMS there, add its line
# here too (tests/test_advisor.py asserts every label appears in the brief).
NAV_MAP = [
    ("Images", "Compose a still (the character spec form, live prompt, generate) and "
               "Variants (sample several, pick a winner)."),
    ("Look", "The prompt-tuning toolkits as tabs - Lighting (8 directions, quality, 10 "
             "sources, named setups + techniques), Composition (7 framing geometries + "
             "techniques), Camera (vertical/side/size axes), Color (12 moods, 10 film "
             "looks + techniques), Posing (21 poses by shot type + techniques), Style "
             "(24 named looks), Capture (film stock, lens artefacts, exposure), Evidence "
             "(lived-in details with a cause - a sunglasses dent, shed hairs on a cushion, a "
             "thumbprint on gloss). Each builds a phrase you Apply into the Images prompt."),
    ("Videos", "The Kling 3.0 motion toolkit - 40 camera movements, image-to-video, a "
               "timed beat line (0-2s: ...) and an ENDS ON end state so the clip does not drift."),
    ("Personas", "A saved persona roster (name/gender/age/style/hair/eye/details) "
                 "composed into one Subject description."),
    ("Ads", "The five-beat UGC advert structure."),
    ("Cats", "A cat story in scenes, or working-cat one-take gags."),
    ("Sound", "ElevenLabs sound-effect prompts (three layers per scene), TTS, voice cloning."),
    ("Assistant", "Chat (a running conversation with the in-app expert), Prompt tools "
                  "(one-shot helpers: idea -> spec, upgrade a prompt, critique an image, "
                  "reverse-engineer a photo) and Prompt Bank (the user's own saved image and "
                  "video prompts with their example images, kept exactly as given)."),
    ("Activity", "History (every generated prompt, its rating, what worked) and What "
                 "works (which vocabulary the ratings favour)."),
    ("Settings", "Provider, model and key status."),
]


def _bank_summary(title, entries):
    lines = ["{} ({}):".format(title, len(entries))]
    for key, cfg in entries.items():
        # Every technique/mood/pose/axis entry carries `note`; lighting's
        # `setups` is the one shape that names its explanation `teaches`
        # instead (build_lighting.py's own bank has both a taught setup and
        # a plain technique dict under one module).
        note = cfg.get("note") or cfg.get("teaches", "")
        # The real KEY comes first, not just the label - a "sections"
        # suggestion is validated against exact bank keys, so the model has
        # to be told the key, not just the human-readable name it maps to.
        lines.append("  {} ({}) - {}".format(key, cfg.get("label", ""), note))
    return "\n".join(lines)


def _technique_banks_summary():
    """Every technique bank's own named entries, pulled live so a bank edit is
    picked up automatically and never re-typed here - the same reasoning
    brief._bank_vocabulary() already applies to prompt_bank.json."""
    lighting = bl.load_bank()
    composition = bc.load_bank()
    color = bcol.load_bank()
    posing = bpo.load_bank()
    camera_angle = bca.load_bank()

    blocks = [
        _bank_summary("Lighting setups", bl.setups(lighting)),
        _bank_summary("Lighting techniques", bl.techniques(lighting)),
        _bank_summary("Composition techniques", bc.techniques(composition)),
        _bank_summary("Color moods", bcol.moods(color)),
        _bank_summary("Color film looks", bcol.film_looks(color)),
        _bank_summary("Color techniques", bcol.techniques(color)),
        _bank_summary("Poses", bpo.poses(posing)),
        _bank_summary("Posing techniques", bpo.techniques(posing)),
        _bank_summary("Camera angle - vertical", bca.verticals(camera_angle)),
        _bank_summary("Camera angle - side", bca.sides(camera_angle)),
        _bank_summary("Camera angle - size", bca.sizes(camera_angle)),
    ]
    evidence = bev.load_bank()
    for kind, cfg in evidence["kinds"].items():
        blocks.append(_bank_summary(
            "Evidence - {} (kind '{}')".format(cfg["label"], kind), cfg["options"]))
    return "\n\n".join(blocks)


def advisor_brief(bank):
    """The system message for the chat - build_brief()'s six-part shape, the
    same one every other brief in this project uses, so this stays consistent
    rather than inventing a new form. The bank-derived parts are regenerated
    from live data every call - a bank edit is reflected the next turn."""
    layers = ", ".join(bp.LAYER_ORDER)
    nav = "\n".join("  {} - {}".format(name, desc) for name, desc in NAV_MAP)
    guides_text = "\n".join(
        "  {} ({}) - {}".format(key, cfg["label"], cfg["note"])
        for key, cfg in bp.guides(bank).items())
    shots = ", ".join(bank["shot_presets"])
    purposes = ", ".join(bank.get("purposes", {}))

    structure = (
        "Reply in plain conversational text, 2-6 short sentences or a short dash-"
        "bulleted list. No markdown headers, no walls of text - this renders in a "
        "plain chat bubble.\n\n"
        "When, and only when, you have enough to propose a ready spec, end your "
        "reply with a fenced block:\n"
        "```spec\n{\"subject\": \"...\"}\n```\n"
        "containing nothing but a single JSON object - the app extracts it, scores "
        "it for real, and shows the user the actual number. Never state a realism "
        "score yourself in prose; you do not compute it, the app does, after you "
        "emit a spec.\n\n"
        "Allowed spec keys, all optional except subject: subject, wardrobe, "
        "setting, action, mood, shot (one of: " + shots + "), purpose (one of: "
        + purposes + "), aspect (one of: 1:1, 4:5, 3:2, 16:9, 9:16), extra (array "
        "of short strings). Any other key is discarded before it ever reaches a "
        "prompt - do not bother proposing seed, reference, lock_identity or "
        "overrides, they are the user's own machinery, never the model's to set.\n\n"
        "The same object may ALSO carry one more optional key, \"sections\", to "
        "propose a value for one or more of the six technique sections - use ONLY "
        "the exact keys and bank entries listed further below under each "
        "section's own heading, never an invented one:\n"
        "```\n"
        "\"sections\": {\n"
        "  \"lighting\": {\"setup\": \"<a Lighting setups key>\"} "
        "OR {\"direction\": \"<key>\", \"quality\": \"hard|soft\", \"source\": "
        "\"<key>\"} - either shape, plus an optional \"techniques\": [\"<key>\", ...],\n"
        "  \"composition\": {\"guide\": \"<a composition guide key>\", "
        "\"techniques\": [\"<key>\", ...]},\n"
        "  \"color\": {\"mood\": \"<a Color moods key>\"} OR "
        "{\"film_look\": \"<a Color film look key>\"}, plus an optional "
        "\"techniques\": [\"<key>\", ...],\n"
        "  \"posing\": {\"pose\": \"<a Poses key>\", \"techniques\": [\"<key>\", ...]},\n"
        "  \"camera_angle\": {\"vertical\": \"<key>\", \"side\": \"<key>\", "
        "\"size\": \"<key>\"} - any subset,\n"
        "  \"evidence\": {\"kind\": \"human|animal|object|place\", \"details\": "
        "[\"<an Evidence key of that kind>\", ...]} - two or three at most\n"
        "}\n```\n"
        "Every value must be one of the exact keys named in this brief, not the "
        "human-readable label - keys are the short hyphenated form (e.g. "
        "\"clam-shell\", not \"Clam shell\")."
    )

    body = brief.build_brief(
        purpose=(
            "Help the user get a premium-quality, photorealistic image out of AI "
            "Video Studio, by telling them exactly which section, bank entry, and "
            "field to use in this app - never generic photography advice that "
            "doesn't map onto a real control here."
        ),
        role=(
            "You are the built-in expert on AI Video Studio - you know every nav "
            "section, every bank entry, and the 8-layer realism gate that scores "
            "every prompt before it's trusted. You coach like a working "
            "photographer training someone on gear they've never touched - "
            "concrete, specific, one clear next action at a time, never a lecture."
        ),
        structure=structure,
        tone=(
            "Plain, concrete, encouraging without flattery. Never say 'beautiful', "
            "'stunning' or 'masterpiece' - describe light, texture and framing "
            "physically, the same restraint this app's own prompts already use."
        ),
        constraints=[
            "Only recommend a nav section, bank entry, or field that is actually "
            "listed below - never invent one.",
            "Always use the bank's own exact label (e.g. \"clam-shell\", not "
            "\"clamshell lighting\") so the user can find it in that section's "
            "own Library tab.",
            "Ground every answer in the user's current prompt/score when it is "
            "given below - diagnose what's actually missing, don't give generic "
            "tips that ignore it.",
            "End every substantive reply with one concrete next action: which "
            "section to open, which entry to pick, which button to press.",
            "If the request is too vague to act on (no subject, no scene), ask "
            "one short clarifying question rather than guessing - do not emit a "
            "spec block yet.",
            "Never claim a technique \"guarantees\" realism - the gate decides, "
            "not you.",
            "If asked about something outside this app, answer briefly, then "
            "bring it back to how it applies here.",
            "Never use these words: " + ", ".join(bank["banned"]) + ".",
            "Once you have enough to describe the avatar, don't stop at the core "
            "spec - also propose one entry for every one of the six technique "
            "sections (Lighting, Composition, Color Grading, Posing, Camera Angle, "
            "Evidence) "
            "inside \"sections\", picking whichever single entry per section best "
            "fits what was described. Leave a section out only when the request "
            "genuinely gives you nothing to base a pick on for it.",
            "\"shot\" and \"sections.camera_angle\" write to the same field, so "
            "give one or the other, never both: a shot preset also carries lens "
            "and framing language, while a bare angle phrase names no camera at "
            "all and costs the camera realism layer. Prefer the preset unless the "
            "angle itself is the point of the shot; if both arrive, the preset "
            "wins and the angle is dropped.",
            "A message that reads like an already-written, fully-detailed prompt "
            "(long and descriptive, not a short request) is a STYLE REFERENCE "
            "ONLY by default, not something to reproduce or paraphrase. Pick up "
            "its overall vibe, mood and technique direction - the kind of "
            "lighting, pose, composition it is going for - but invent a subject "
            "who is clearly a different person: a different name (if any), "
            "different identifying physical features (hair, eyes, build, age), "
            "different specific wardrobe and setting details, UNLESS the user "
            "explicitly says what to keep - a stated instruction (\"keep the "
            "setting\", \"same wardrobe, different everything else\", a follow-up "
            "message narrowing it further) always wins over this default, the "
            "same \"an explicit choice beats a generic fill\" rule every other "
            "suggestion in this app already follows. Never copy or closely "
            "restate the pasted prompt's own subject description beyond what "
            "was explicitly asked to be kept. Say plainly that you're using it "
            "as a style reference, not recreating it.",
        ],
        examples=[
            'user: "how do I make my photos look better?"\n'
            "assistant: What kind of shot are you going for - a portrait, a "
            "candid, something editorial? And who's the subject? I can't point "
            "you at the right section without knowing what you're actually "
            "trying to make.",

            'user: "a tired nurse finishing a night shift, portrait, I want it '
            'to look really real"\n'
            "assistant: Two things will move that the most. Open Lighting -> "
            "Compose and try the \"old-hollywood\" setup - it's built for a "
            "tired, worked expression under practical light. Then open Posing -> "
            "Compose, pick \"forward-lean\" from the headshot category, and stack "
            "the \"relaxed-hands\" technique - a stiff pose is one of the fastest "
            "AI tells. I've filled in every section below - review it, then apply.\n"
            "```spec\n"
            '{"subject": "a nurse in her forties, dark circles under her eyes, '
            'hair coming loose from a bun", "wardrobe": "wrinkled blue scrubs", '
            '"setting": "a hospital corridor at dawn, fluorescent light", '
            '"action": "leaning against the wall, eyes closed for a moment", '
            '"mood": "exhausted, relieved", "shot": "portrait", '
            '"sections": {'
            '"lighting": {"setup": "old-hollywood"}, '
            '"composition": {"guide": "rule-of-thirds", "techniques": ["lead-room"]}, '
            '"color": {"mood": "melancholy-lonely"}, '
            '"posing": {"pose": "forward-lean", "techniques": ["relaxed-hands"]}, '
            '"camera_angle": {"vertical": "eye-level", "side": "three-quarter", '
            '"size": "medium-close-up"}, '
            '"evidence": {"kind": "human", "details": ["hair-tie", "strap-crease"]}}}\n'
            "```",

            'user: "Ultra-realistic close-up portrait of Mara, a 29-year-old woman '
            'with long copper-red hair and light freckles, sitting at a window '
            'table in a Parisian cafe at golden hour. She wears a cream wool coat '
            'and a thin gold necklace, resting her chin on one hand, gazing out '
            'the window with a wistful expression. Soft warm sidelight from the '
            'window, shallow depth of field, 85mm lens, muted warm color grade."\n'
            "assistant: That's a strong reference for mood, not a person to "
            "recreate - I'll build a different subject and carry over the "
            "golden-hour window light, the wistful caught-in-thought feel, and "
            "the framed-by-the-window composition. Say the word if you'd rather "
            "I keep any specific piece of the original (the coat, the cafe "
            "setting, anything) instead of changing it too.\n"
            "```spec\n"
            '{"subject": "Elena, a woman in her mid-thirties, short dark bob, a '
            'small scar above one eyebrow", "wardrobe": "a forest-green corduroy '
            'jacket", "setting": "a quiet secondhand bookshop, late-afternoon '
            'light through a dusty window", "action": "leaning against a shelf, '
            'flipping through a paperback", "mood": "wistful, unhurried", '
            '"sections": {'
            '"lighting": {"setup": "loop"}, '
            '"composition": {"guide": "diagonals", "techniques": ["framing-device"]}, '
            '"color": {"mood": "romantic-dreamy"}, '
            '"posing": {"pose": "mid-gesture"}, '
            '"camera_angle": {"vertical": "eye-level", "side": "three-quarter", '
            '"size": "medium"}, '
            '"evidence": {"kind": "human", "details": ["ink-smudge", "lint"]}}}\n'
            "```",
        ],
    )

    return (
        body
        + "\n\nTHE 8 REALISM LAYERS (every prompt is scored against these): " + layers
        + "\n\nNAV SECTIONS:\n" + nav
        + "\n\nCOMPOSITION GUIDES (prompt_bank.json):\n" + guides_text
        + "\n\n" + _technique_banks_summary()
    )


def extract_spec_block(text):
    """Pull a fenced ```spec ... ``` block out of a chat reply, or None.

    Deliberately NOT ask_llm.extract_json()'s whole-text brace scan - a
    conversational reply routinely has other braces or prose around a spec
    block, which that scanner isn't built to skip past. Absent, unfenced or
    malformed all return None rather than an error: most replies are plain
    conversation with nothing to apply, and that is a normal outcome here,
    not a failure.
    """
    if not text:
        return None
    marker = "```spec"
    start = text.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = text.find("```", start)
    if end == -1:
        return None
    try:
        payload = json.loads(text[start:end].strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _picked(table, value):
    """`value` if it names a real entry in `table`, else None.

    A *suggested* pick stays inside the vocabulary the model was actually
    shown - deliberately stricter than each section's own GUI, where a user's
    typed custom text is meant to win. The model has every key in its brief;
    anything outside that list is a mistake, not a creative choice.
    """
    value = str(value or "").strip()
    return value if value in table else None


def _picked_list(table, values):
    """Only the entries of `values` that name real keys in `table`."""
    if isinstance(values, str):
        values = [values]
    return [v for v in (str(x or "").strip() for x in values or ()) if v in table]


def _compose_section(bank, name, block):
    """One section's validated picks -> its composed phrase, produced by that
    section's OWN compose_X(). Nothing here writes phrasing of its own, so a
    suggestion is exactly what that section's "Apply to Compose" button would
    have produced from the same picks. Raises the composer's own error when
    the picks add up to nothing usable.
    """
    if name == "lighting":
        lighting = bl.load_bank()
        setup = _picked(bl.setups(lighting), block.get("setup"))
        techniques_ = _picked_list(bl.techniques(lighting), block.get("techniques"))
        # A setup already encodes its own direction, quality and source, and
        # compose_lighting() refuses the two shapes together on purpose. Rather
        # than drop an otherwise-good suggestion because the reply over-
        # specified, the setup wins and the deep-path fields are ignored - the
        # same precedence build_lighting.py's own docstring argues for.
        if setup:
            return bl.compose_lighting(
                lighting, setup=setup, techniques_=techniques_)[0]
        return bl.compose_lighting(
            lighting,
            direction=_picked(bl.directions(lighting), block.get("direction")),
            quality=_picked(bl.qualities(lighting), block.get("quality")),
            source=_picked(bl.sources(lighting), block.get("source")),
            techniques_=techniques_,
        )[0]

    if name == "composition":
        composition = bc.load_bank()
        return bc.compose_composition(
            bank, composition,
            guide=_picked(bp.guides(bank), block.get("guide")),
            techniques_=_picked_list(bc.techniques(composition), block.get("techniques")),
        )[0]

    if name == "color":
        color = bcol.load_bank()
        mood = _picked(bcol.moods(color), block.get("mood"))
        film_look = _picked(bcol.film_looks(color), block.get("film_look"))
        # Two complete recipes; compose_color() refuses both together. Same
        # reasoning as lighting's setup above - pick one deterministically
        # rather than losing the whole suggestion to an over-specified reply.
        if mood:
            film_look = None
        return bcol.compose_color(
            color, mood=mood, film_look=film_look,
            techniques_=_picked_list(bcol.techniques(color), block.get("techniques")),
        )[0]

    if name == "posing":
        posing = bpo.load_bank()
        return bpo.compose_posing(
            posing,
            pose=_picked(bpo.poses(posing), block.get("pose")),
            techniques_=_picked_list(bpo.techniques(posing), block.get("techniques")),
        )[0]

    if name == "evidence":
        evidence = bev.load_bank()
        kind = _picked(evidence["kinds"], block.get("kind"))
        if not kind:
            raise bev.EvidenceError("no valid kind")
        return bev.compose_evidence(
            evidence, kind, _picked_list(bev.options(evidence, kind), block.get("details")))[0]

    camera_angle = bca.load_bank()
    return bca.compose_camera_angle(
        camera_angle,
        vertical=_picked(bca.verticals(camera_angle), block.get("vertical")),
        side=_picked(bca.sides(camera_angle), block.get("side")),
        size=_picked(bca.sizes(camera_angle), block.get("size")),
    )[0]


def _finalize_sections(bank, payload, spec=None):
    """{section: composed phrase} for every technique section the reply
    proposed and that actually validated - the other half of "the model
    suggests, the app decides", for the five sections the core spec has no
    field for.

    A section whose picks are all invalid, or whose own composer refuses them,
    is dropped from the result rather than failing the turn - the same
    treatment an invalid `shot` already gets in the core spec. Nothing here is
    auto-applied: the caller shows it and the user decides, exactly like
    brief.autofill_spec()'s own held-back `suggestions`.

    `spec` is the already-finalized core spec, and it settles the one real
    conflict between the two halves: `camera_angle` and a `shot` preset write
    to the SAME field, and a bare angle phrase names no capture device, so
    letting both through would silently cost the camera layer and drop an
    otherwise-8/8 suggestion to 7/8. A preset carries lens and composition
    language the angle phrase would throw away, so the preset wins and the
    angle is dropped - the same "an explicit pick beats a generic fill"
    precedence the rest of this project already follows, and the user can
    still open Camera Angle and choose that tradeoff deliberately.
    """
    sections = payload.get(SECTIONS_KEY)
    if not isinstance(sections, dict):
        return {}

    out = {}
    for name in SECTION_NAMES:
        if name == "camera_angle" and (spec or {}).get("shot"):
            continue
        block = sections.get(name)
        if not isinstance(block, dict):
            continue
        try:
            phrase = _compose_section(bank, name, block)
        except (bl.LightingError, bc.CompositionError, bcol.ColorError,
                bpo.PosingError, bca.CameraAngleError, bev.EvidenceError):
            continue
        if phrase and phrase.strip():
            out[name] = phrase.strip()
    return out


def _finalize_spec(bank, payload):
    """Whitelist -> validate -> recompose -> relint, the same tail already in
    brief.autofill_spec()/spec_from_idea(). Written fresh here rather than
    refactoring brief.py for one more caller - the same small, view-local
    duplication every _scrolled() helper in ui/views/ already tolerates,
    rather than risking a heavily-tested file for a new feature.
    """
    spec = {k: v for k, v in payload.items() if k in brief.SPEC_KEYS}
    # "sections" is not a spec field and not a dropped one either - it is
    # handled separately by _finalize_sections(), so reporting it as dropped
    # here would be a lie the user would reasonably act on.
    dropped = sorted(set(payload) - brief.SPEC_KEYS - {SECTIONS_KEY})
    if isinstance(spec.get("extra"), str):
        spec["extra"] = [spec["extra"]]

    for field, validator in (("shot", bp.validate_shot), ("purpose", bp.validate_purpose)):
        if spec.get(field) and validator(bank, spec[field]):
            dropped.append("{}={}".format(field, spec.pop(field)))

    if not spec.get("subject"):
        return None

    prompt, _ = bp.compose(bank, dict(spec, seed=0))
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    return {
        "spec": spec,
        "dropped": dropped,
        "score": len(present),
        "passed": len(present) == 8 and not banned,
        "banned": banned,
    }


def _context_note(bank, prompt):
    """A one-line, clearly-marked note on the CURRENT prompt's real score -
    computed by realism_lint, never guessed by the model. This is what lets
    advisor_brief()'s "ground every answer in the user's current prompt/score"
    constraint actually be followed rather than ignored - the note is folded
    into the turn itself, not left for the model to ask for.
    """
    if not prompt:
        return ""
    present, missing, banned, _warn, _negatives = rl.lint(prompt.lower(), bank)
    bits = "current prompt scores {}/8".format(len(present))
    if missing:
        bits += "; missing: " + ", ".join(cfg["label"] for _, cfg, _ in missing)
    if banned:
        bits += "; banned term(s) present: " + ", ".join(banned)
    return "[app context, not typed by the user - {}]".format(bits)


def chat(bank, history, message, image_path=None, context_prompt=None, persona=None, ask=None):
    """One turn of the advisor conversation.

    Returns {"ok": True, "reply": str, "suggestion": dict_or_None,
    "sections": dict} on success, {"ok": False, "error": str} on failure.
    `suggestion` is the validated result of _finalize_spec() when the reply
    carried a usable fenced spec block, else None; `sections` is
    _finalize_sections()'s {section: composed phrase} for the five technique
    sections, or {} - a reply with nothing to apply is a normal, useful
    outcome, not a lesser one.

    `image_path` is scoped to this turn only: `history` itself stays text-only,
    so a long conversation never silently re-uploads every earlier photo on
    every later turn - the caller re-attaches if a later question still needs
    the image visible.

    `context_prompt` (optional) is the user's currently-composed prompt, if
    any - real-scored here via realism_lint and folded into the turn as a
    clearly-marked note the model did not write and cannot fake. The caller
    (the GUI) still appends its own plain `message`, not this decorated
    version, to its own history - the note is per-turn context, not something
    the user said.

    `persona` (optional) is a PERSONAS key - a one-turn overlay on top of
    advisor_brief()'s system prompt (see persona_overlay()), scoped to this
    turn only, exactly like `image_path` and `context_prompt` above.
    """
    ask = ask or ask_llm.ask
    message = (message or "").strip()
    if not message:
        return {"ok": False, "error": "Say something first."}

    note = _context_note(bank, context_prompt)
    full_message = (note + "\n\n" + message) if note else message

    images = [image_path] if image_path else ()
    system = advisor_brief(bank) + persona_overlay(persona)
    text, error = ask(
        full_message, system=system, images=images, history=list(history or ()))
    if error:
        return {"ok": False, "error": error}

    payload = extract_spec_block(text)
    suggestion = _finalize_spec(bank, payload) if payload else None
    sections = _finalize_sections(
        bank, payload, (suggestion or {}).get("spec")) if payload else {}
    return {"ok": True, "reply": text, "suggestion": suggestion, "sections": sections}


# --------------------------------------------------------------------------- #
# CLI - a debug/test surface, same as brief.py's own. The GUI is the real
# interface for a running conversation.
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Chat with the in-app AI Video Studio expert.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="print the system brief without calling out")

    p_chat = sub.add_parser("chat", help="one turn of the conversation")
    p_chat.add_argument("message")
    p_chat.add_argument("--history-file", help="path to a JSON array of prior turns")
    p_chat.add_argument("--image", help="attach a photo to this turn")
    p_chat.add_argument("--context-prompt-file",
                        help="path to the current composed prompt, real-scored and folded "
                             "into this turn")
    p_chat.add_argument("--persona", choices=sorted(PERSONAS),
                        help="a one-turn persona overlay (see PERSONAS)")
    p_chat.add_argument("--dry-run", action="store_true",
                        help="describe the request without sending it or needing a key")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    bank = bp.load_bank()

    if args.command == "show":
        print(advisor_brief(bank))
        return 0

    history = []
    if args.history_file:
        path = Path(args.history_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("History file not found: {}".format(path))
        history = json.loads(path.read_text(encoding="utf-8"))

    if args.dry_run:
        url, body, headers = ask_llm.build_request(
            ask_llm.DEFAULT_BASE, ask_llm.DEFAULT_MODEL, "DRY-RUN", args.message,
            advisor_brief(bank) + persona_overlay(args.persona), [], history=history)
        redacted = {k: ("<redacted>" if k == "Authorization" else v) for k, v in headers.items()}
        print("POST {}".format(url))
        print("headers: {}".format(json.dumps(redacted)))
        print("history: {} prior turn(s)".format(len(history)))
        print("body bytes: {}".format(len(json.dumps(body))))
        return 0

    context_prompt = None
    if args.context_prompt_file:
        path = Path(args.context_prompt_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Context prompt file not found: {}".format(path))
        context_prompt = path.read_text(encoding="utf-8").strip()

    result = chat(bank, history, args.message, image_path=args.image,
                  context_prompt=context_prompt, persona=args.persona)
    if not result["ok"]:
        print(result["error"], file=sys.stderr)
        return 3

    print(result["reply"])
    for name, phrase in (result.get("sections") or {}).items():
        print("\n[section] {}: {}".format(name, phrase), file=sys.stderr)
    suggestion = result["suggestion"]
    if suggestion:
        print("\n[spec] {}/8 {}".format(
            suggestion["score"], "PASS" if suggestion["passed"] else "needs work"),
            file=sys.stderr)
        if suggestion["dropped"]:
            print("[dropped] {}".format(", ".join(suggestion["dropped"])), file=sys.stderr)
        if suggestion["banned"]:
            print("[banned] {}".format(", ".join(suggestion["banned"])), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
