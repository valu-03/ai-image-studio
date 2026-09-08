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
import build_lighting as bl
import build_posing as bpo
import build_prompt as bp
import realism_lint as rl

ROOT = Path(__file__).resolve().parent.parent

# One line each - the nav rail's own map. tools/ never imports the GUI layer,
# so this is kept here rather than read from ui/main_window.py; if a section
# is added to NAV_ITEMS there, add its line here too.
NAV_MAP = [
    ("Images", "Compose a still: the character spec form, live prompt, generate."),
    ("Lighting", "8 portrait light directions, hard/soft quality, 10 sources, 8 named "
                 "setups, 7 lighting-realism techniques."),
    ("Composition", "7 framing geometries (rule of thirds, phi grid, diagonals, triangle, "
                     "golden ratio, golden spiral, harmonic armature) plus opt-in techniques "
                     "(negative space, lead room, depth layering, atmosphere, ...)."),
    ("Color Grading", "12 named colour moods and 10 film-look references, plus opt-in "
                       "colour techniques (accent echo, warm/cool contrast)."),
    ("Posing", "21 named poses by shot type (portrait/editorial/headshot/group/candid), "
               "plus posing-realism techniques."),
    ("Camera Angle", "Vertical position, side and shot size - three independent, freely "
                      "combinable axes."),
    ("Videos", "The Kling 3.0 motion toolkit - 40 camera movements, image-to-video."),
    ("Ads", "The five-beat UGC advert structure."),
    ("Cats", "A cat story in scenes, or working-cat one-take gags."),
    ("Sound", "ElevenLabs sound-effect prompts, three layers per scene."),
    ("Brief", "One-shot AI helpers: idea -> spec, upgrade a prompt, critique an image, "
              "analyze any photo."),
    ("History", "Every generated prompt, its rating, and what worked."),
    ("Insights", "What the ratings say about which vocabulary performs."),
    ("Settings", "Provider, model and key status."),
]


def _bank_summary(title, entries):
    lines = ["{} ({}):".format(title, len(entries))]
    for cfg in entries.values():
        # Every technique/mood/pose/axis entry carries `note`; lighting's
        # `setups` is the one shape that names its explanation `teaches`
        # instead (build_lighting.py's own bank has both a taught setup and
        # a plain technique dict under one module).
        note = cfg.get("note") or cfg.get("teaches", "")
        lines.append("  {} - {}".format(cfg.get("label", ""), note))
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
    return "\n\n".join(blocks)


def advisor_brief(bank):
    """The system message for the chat - build_brief()'s six-part shape, the
    same one every other brief in this project uses, so this stays consistent
    rather than inventing a new form. The bank-derived parts are regenerated
    from live data every call - a bank edit is reflected the next turn."""
    layers = ", ".join(bp.LAYER_ORDER)
    nav = "\n".join("  {} - {}".format(name, desc) for name, desc in NAV_MAP)
    guides_text = "\n".join(
        "  {} - {}".format(cfg["label"], cfg["note"]) for cfg in bp.guides(bank).values())
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
        "overrides, they are the user's own machinery, never the model's to set."
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
            "AI tells.\n"
            "```spec\n"
            '{"subject": "a nurse in her forties, dark circles under her eyes, '
            'hair coming loose from a bun", "wardrobe": "wrinkled blue scrubs", '
            '"setting": "a hospital corridor at dawn, fluorescent light", '
            '"action": "leaning against the wall, eyes closed for a moment", '
            '"mood": "exhausted, relieved", "shot": "portrait"}\n'
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


def _finalize_spec(bank, payload):
    """Whitelist -> validate -> recompose -> relint, the same tail already in
    brief.autofill_spec()/spec_from_idea(). Written fresh here rather than
    refactoring brief.py for one more caller - the same small, view-local
    duplication every _scrolled() helper in ui/views/ already tolerates,
    rather than risking a heavily-tested file for a new feature.
    """
    spec = {k: v for k, v in payload.items() if k in brief.SPEC_KEYS}
    dropped = sorted(set(payload) - brief.SPEC_KEYS)
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


def chat(bank, history, message, image_path=None, context_prompt=None, ask=None):
    """One turn of the advisor conversation.

    Returns {"ok": True, "reply": str, "suggestion": dict_or_None} on success,
    {"ok": False, "error": str} on failure. `suggestion` is the validated
    result of _finalize_spec() when the reply carried a usable fenced spec
    block, else None - a reply with nothing to apply is a normal, useful
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
    """
    ask = ask or ask_llm.ask
    message = (message or "").strip()
    if not message:
        return {"ok": False, "error": "Say something first."}

    note = _context_note(bank, context_prompt)
    full_message = (note + "\n\n" + message) if note else message

    images = [image_path] if image_path else ()
    text, error = ask(
        full_message, system=advisor_brief(bank), images=images, history=list(history or ()))
    if error:
        return {"ok": False, "error": error}

    payload = extract_spec_block(text)
    suggestion = _finalize_spec(bank, payload) if payload else None
    return {"ok": True, "reply": text, "suggestion": suggestion}


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
            advisor_brief(bank), [], history=history)
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
                  context_prompt=context_prompt)
    if not result["ok"]:
        print(result["error"], file=sys.stderr)
        return 3

    print(result["reply"])
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
