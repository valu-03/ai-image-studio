"""Score a GENERATED IMAGE against its spec - the missing half of realism_lint.py.

tools/realism_lint.py checks the prompt TEXT before generation; this checks the
picture that actually comes back, using a vision-capable text model through
ask_llm.py (already wired for images - see ask_llm.ask's `images` argument,
unused for this purpose until now).

Same house rule as everywhere else an LLM touches this project: the model only
ever SUGGESTS - "a text model suggests, a linter decides." Here the model is
doing the LOOKING (no deterministic pixel judge exists to call instead), but
its reply is still parsed and whitelisted exactly like every other LLM JSON
reply in this codebase (see ask_llm.extract_json, and brief.py's COPY_KEYS
pattern this copies): only recognized keys are ever read, a malformed or
off-schema reply is reported as an error - never a false pass, never a crash -
and the result never writes back into the prompt or spec. It is display-only
and history-only, the same authority as a human star rating.

Usage:
    python tools/vision_lint.py --image temp/outputs/images/x.png \\
        --subject "a woman" --shot "medium shot" --lighting "soft window light"
    python tools/vision_lint.py --image x.png --reference ref.png --subject "..."

Key:   OPENROUTER_API_KEY in .env, same as ask_llm.py - optional everywhere.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask_llm  # noqa: E402

LABELS = {
    "subject": "Subject", "wardrobe": "Wardrobe", "setting": "Setting",
    "mood": "Mood", "shot": "Shot", "lighting": "Lighting",
    "composition": "Composition", "identity": "Identity match",
}
FIELD_KEYS = ("subject", "wardrobe", "setting", "mood", "shot", "lighting", "composition")


def _spec_field(spec, key):
    """Pull one field out of a Compose spec dict (see ui/spec_editor.py:spec()).

    A couple of fields have a "_custom" override that wins when set - the same
    rule the prompt builder itself follows, so the question asked here matches
    what the prompt actually said.
    """
    if key == "shot":
        return spec.get("shot_custom") or spec.get("shot") or ""
    if key == "composition":
        return spec.get("composition_guide_custom") or spec.get("composition_guide") or ""
    if key == "lighting":
        return (spec.get("overrides") or {}).get("lighting", "")
    return spec.get(key, "")


def build_prompt(spec, has_reference):
    lines = ["Compare the FIRST image to this shot description, field by field:"]
    for key in FIELD_KEYS:
        value = _spec_field(spec, key)
        lines.append("- {}: {}".format(LABELS[key], value or "(not specified)"))
    keys = list(FIELD_KEYS)
    if has_reference:
        lines.append(
            "- Identity: the SECOND image is a reference character. Does the "
            "first image show the same person/character?")
        keys.append("identity")
    lines.append("")
    lines.append(
        "Return ONLY a JSON object, no prose, no markdown fences, with one entry "
        "per field above using these exact keys: {}.".format(", ".join(keys)))
    lines.append(
        'Each value is {"match": true|false, "note": "a short reason, one sentence"}.')
    return "\n".join(lines)


def check(image_path, spec, reference_path=None, model=None, ask=None):
    """(checks, score, total, error) - exactly one of (checks, error) is None.

    checks: [{"key", "label", "passed": bool, "fix": str, "ok_text": str}, ...],
    the same shape tools/realism_lint.py:checks_for() produces, so ui/lint_panel.py
    can render either one with the same widget.

    `ask`, like every other LLM-calling function in this codebase (see
    brief.py), defaults to ask_llm.ask and exists so a test can inject a fake
    without touching real network code or monkeypatching the module.
    """
    ask = ask or ask_llm.ask
    keys = list(FIELD_KEYS)
    images = [image_path]
    if reference_path:
        images.append(reference_path)
        keys.append("identity")

    prompt = build_prompt(spec, has_reference=bool(reference_path))
    text, error = ask(prompt, images=images, model=model)
    if error:
        return None, 0, len(keys), error

    payload = ask_llm.extract_json(text)
    if not isinstance(payload, dict):
        return None, 0, len(keys), "The vision model did not return JSON."

    checks = []
    for key in keys:
        entry = payload.get(key)
        entry = entry if isinstance(entry, dict) else {}
        passed = bool(entry.get("match"))
        note = str(entry.get("note", "")).strip()
        checks.append({
            "key": key,
            "label": LABELS[key],
            "passed": passed,
            "fix": note or "The model flagged this as not matching the spec.",
            "ok_text": note or "Matches the spec.",
        })
    score = sum(1 for c in checks if c["passed"])
    return checks, score, len(checks), None


# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True)
    parser.add_argument("--reference", help="a locked character's reference image")
    parser.add_argument("--subject", default="")
    parser.add_argument("--wardrobe", default="")
    parser.add_argument("--setting", default="")
    parser.add_argument("--mood", default="")
    parser.add_argument("--shot", default="")
    parser.add_argument("--lighting", default="")
    parser.add_argument("--composition-guide", default="")
    parser.add_argument("--model", help="override the vision model id for this call")
    args = parser.parse_args(argv)

    spec = {
        "subject": args.subject, "wardrobe": args.wardrobe, "setting": args.setting,
        "mood": args.mood, "shot": args.shot,
        "composition_guide": args.composition_guide,
        "overrides": {"lighting": args.lighting},
    }
    checks, score, total, error = check(args.image, spec, args.reference, args.model)
    if error:
        print(error, file=sys.stderr)
        return 3
    for c in checks:
        mark = "PASS" if c["passed"] else "FAIL"
        print("[{}] {}: {}".format(mark, c["label"], c["ok_text"] if c["passed"] else c["fix"]))
    print("{}/{}".format(score, total))
    return 0 if score == total else 1


if __name__ == "__main__":
    sys.exit(main())
