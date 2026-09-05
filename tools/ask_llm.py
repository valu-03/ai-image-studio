"""Text-model adapter - the missing half of the toolkit.

generate_image.py talks to image providers; this talks to the one text model,
and reuses that file's env reader, HTTP POST, error description and image
encoder rather than duplicating any of it.

OpenRouter is the only text provider, and it is entirely optional: without a key
every other part of the app still works. It exists to make prompts better, not
to make them possible.

Usage:
    python tools/ask_llm.py --prompt "expand this prompt" --system "You are a ..."
    python tools/ask_llm.py --prompt-file brief.txt --image temp/outputs/images/a.png
    python tools/ask_llm.py --prompt "hello" --dry-run

Key:   OPENROUTER_API_KEY in .env (process environment as a fallback).
Model: OPENROUTER_TEXT_MODEL in .env, or --model. Model ids move; that is why
       this is configurable rather than hardcoded.

Exit codes match generate_image.py: 0 ok, 1 no key, 3 API or network, 4 no
usable content. Key values are never printed, logged or written to temp/.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import generate_image as gi

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = gi.ENV_PATH

KEY_VAR = "OPENROUTER_API_KEY"
MODEL_VAR = "OPENROUTER_TEXT_MODEL"
DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_BASE = "https://openrouter.ai"
KEY_URL = "https://openrouter.ai/keys"


def build_request(base, model, key, prompt, system=None, images=(), max_tokens=2048):
    """Return (url, body, headers) for an OpenRouter chat completion."""
    content = [{"type": "text", "text": prompt}]
    for mime, data in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:{};base64,{}".format(mime, data)},
        })

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    url = "{}/api/v1/chat/completions".format(base.rstrip("/"))
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
    return url, body, headers


def parse_response(payload):
    """Pull the assistant text out of a chat completion, or None."""
    for choice in (payload or {}).get("choices", []):
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        # Some routes return the content as a parts array.
        if isinstance(content, list):
            text = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            ).strip()
            if text:
                return text
    return None


def ask(prompt, system=None, images=(), model=None, base=None, max_tokens=2048):
    """Ask a text model. Returns (text, error) — exactly one is None.

    The in-process entry point: brief.py and the GUI worker both call this, so
    there is one implementation of "talk to a text model".
    """
    env = gi.read_env()
    key = env.get(KEY_VAR) or os.environ.get(KEY_VAR, "")
    if not key:
        return None, (
            "{} is not set in .env — add a key at {} to use the AI helpers. "
            "Everything else in the app works without it.".format(KEY_VAR, KEY_URL)
        )

    model = model or env.get(MODEL_VAR) or os.environ.get(MODEL_VAR) or DEFAULT_MODEL
    base = base or env.get("AIVS_API_BASE") or os.environ.get("AIVS_API_BASE") or DEFAULT_BASE

    encoded = []
    for image in images:
        try:
            encoded.append(gi.encode_reference(image))
        except FileNotFoundError as exc:
            return None, str(exc)

    url, body, headers = build_request(base, model, key, prompt, system, encoded, max_tokens)

    try:
        status, payload, raw = gi.post_json(url, body, headers)
    except RuntimeError as exc:
        return None, str(exc)

    if status >= 400:
        message = gi.describe_api_error(payload, raw)
        if status in (400, 404):
            message += "  (set {}=<id> in .env if the model id is wrong)".format(MODEL_VAR)
        return None, "API error {}: {}".format(status, message)

    text = parse_response(payload)
    if not text:
        return None, "The model returned no text. {}".format(
            gi.describe_api_error(payload, raw)[:200]
        )
    return text, None


def extract_json(text):
    """Best-effort JSON object out of a model reply.

    Models wrap JSON in prose or fences more often than not, so take the outermost
    braces rather than trusting the whole string to parse.
    """
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```")[1] if "```" in candidate[3:] else candidate[3:]
        if candidate.lstrip().lower().startswith("json"):
            candidate = candidate.lstrip()[4:]
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start:end + 1])
    except json.JSONDecodeError:
        return None


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Ask a text model (OpenRouter).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--prompt", help="user message")
    p.add_argument("--prompt-file", help="path to a file holding the user message")
    p.add_argument("--system", help="system message")
    p.add_argument("--system-file", help="path to a file holding the system message")
    p.add_argument("--image", action="append", default=[],
                   help="attach an image for multimodal input (repeatable)")
    p.add_argument("--model", help="override the model id for this call")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--dry-run", action="store_true",
                   help="describe the request without sending it or needing a key")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    def read_arg(value, path_value, label):
        if path_value:
            path = Path(path_value)
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists():
                sys.exit("{} file not found: {}".format(label, path))
            return path.read_text(encoding="utf-8").strip()
        return value

    prompt = read_arg(args.prompt, args.prompt_file, "Prompt")
    system = read_arg(args.system, args.system_file, "System")
    if not prompt:
        sys.exit("Give either --prompt \"...\" or --prompt-file <path>.")

    if args.dry_run:
        env = gi.read_env()
        model = (args.model or env.get(MODEL_VAR)
                 or os.environ.get(MODEL_VAR) or DEFAULT_MODEL)
        base = args.base_url or DEFAULT_BASE
        url, body, headers = build_request(base, model, "DRY-RUN", prompt, system, [])
        redacted = {k: ("<redacted>" if k == "Authorization" else v) for k, v in headers.items()}
        print("POST {}".format(url))
        print("headers: {}".format(json.dumps(redacted)))
        print("model:   {}".format(model))
        print("system:  {}".format("yes" if system else "no"))
        print("images:  {}".format(len(args.image)))
        print("body bytes: {}".format(len(json.dumps(body))))
        return 0

    text, error = ask(
        prompt, system, args.image, args.model, args.base_url, args.max_tokens
    )
    if error:
        print(error, file=sys.stderr)
        if KEY_VAR in error and "not set" in error:
            return 1
        # "returned no text" is a successful call with nothing usable in it,
        # which is exit 4 in this project - not an API failure.
        return 4 if "returned no text" in error else 3

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
