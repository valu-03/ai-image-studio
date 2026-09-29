"""Generate an image from a prompt.

Usage:
    python tools/generate_image.py --prompt-file temp/outputs/prompts/x.txt
    python tools/generate_image.py --prompt "..." --out hero.png
    python tools/generate_image.py --prompt-file x.txt \
        --reference temp/resources/characters/ada/ref.png        # lock the face
    python tools/generate_image.py --prompt "..." --dry-run

Providers and the key each needs (set them in .env at the project root):
    kie         KIE_API_KEY                 Nano Banana Pro and the rest of the
                                            Kie market - the default
    higgsfield  HIGGSFIELD_API_KEY_ID       Higgsfield Soul. Needs BOTH the id
              + HIGGSFIELD_API_KEY_SECRET   and the secret.

Both providers are asynchronous: the request creates a *job*, the job is polled
until it finishes, and the finished job hands back a URL that is downloaded.
That is three round trips, not one, so expect a generation to take a while and
watch the stage messages on stderr.

Reference images (character consistency) work on **kie only** - Higgsfield's
Soul endpoint documents no reference input, so asking for one there is refused
rather than silently dropped. A dropped reference produces a different person,
which is the whole failure the consistent-character workflow exists to prevent.

Model ids change; override without touching code by setting KIE_IMAGE_MODEL or
HIGGSFIELD_IMAGE_MODEL in .env.

On success the saved path is printed to stdout as "[image] <path>" - that line
is the machine-readable result the GUI reads.

Key values are never printed, logged, or written to temp/. Standard library only.
"""

import argparse
import base64
import json
import mimetypes
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Overridable so tests can point at a temp file instead of the real .env. Without
# this, a suite that simulates "no key" by clearing the process environment would
# start failing the moment a real key is written to .env - read_env() wins.
ENV_PATH = Path(os.environ.get("AIVS_ENV_FILE") or (ROOT / ".env"))
OUT_DIR = ROOT / "temp" / "outputs" / "images"

TIMEOUT = 180
# How long to wait for an async job, and how often to ask.
JOB_TIMEOUT = int(os.environ.get("AIVS_JOB_TIMEOUT") or 300)
# Overridable so the GUI suite does not spend real seconds asleep.
POLL_INTERVAL = float(os.environ.get("AIVS_POLL_INTERVAL") or 3)
MAX_IMAGE_BYTES = 40 * 1024 * 1024

# Both of Kie's file hosts sit behind Cloudflare and answer 403 (error 1010) to
# the default "Python-urllib/3.x" agent. Found by the first real run: the whole
# generation succeeded and only the download failed, and the reference upload
# failed the same way. Sent on every request, which is what an API client should
# do anyway.
USER_AGENT = "Mozilla/5.0 (compatible; AIVideoStudio/1.0)"

# Kie's uploader lives on a different host from its job API, so it is not
# derived from `base` - but it still honours AIVS_API_BASE so tests can catch it.
KIE_UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"

PROVIDERS = {
    "kie": {
        "key": "KIE_API_KEY",
        "where": "https://kie.ai/api-key",
        "model_var": "KIE_IMAGE_MODEL",
        "default_model": "nano-banana-pro",
        "base": "https://api.kie.ai",
        "label": "Nano Banana Pro via Kie",
        "references": True,
    },
    "higgsfield": {
        "key": "HIGGSFIELD_API_KEY_ID",
        "secret": "HIGGSFIELD_API_KEY_SECRET",
        "where": "https://higgsfield.ai/settings/api",
        "model_var": "HIGGSFIELD_IMAGE_MODEL",
        "default_model": "soul/v2/standard",
        "base": "https://api.higgsfield.ai",
        "label": "Higgsfield Soul",
        "references": False,
    },
}

DEFAULT_PROVIDER = "kie"


def read_env():
    """Minimal .env reader. Returns {name: value}; never prints a value."""
    values = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("\"'")
    return values


def env_value(name, env=None):
    """.env wins; the process environment is the fallback."""
    env = read_env() if env is None else env
    return env.get(name) or os.environ.get(name, "")


def write_env_value(name, value, path=None):
    """Set one variable in .env, preserving every other line. Returns the path.

    Lives beside read_env() deliberately: the reader strips quotes and ignores
    comments, so the writer has to agree with it about the format, and two
    functions in two modules would eventually disagree.

    A key is a secret, so this NEVER returns or logs the value, and it
    rewrites the file rather than appending - appending a second
    KIE_API_KEY=... line would leave read_env() silently preferring whichever
    came last, which is the sort of thing that looks like an expired key.

    An empty `value` removes the variable instead of writing a blank one, so
    "clear this key" is expressible and does not leave `NAME=` behind for
    env_value() to return as falsy-but-present.
    """
    path = Path(path) if path else ENV_PATH
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    prefix = name + "="
    kept = [line for line in lines
            if not line.strip().startswith(prefix)]
    if value:
        kept.append("{}={}".format(name, value))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return path


def credentials(cfg, env=None):
    """(key, secret) for a provider. `secret` is "" for single-key providers."""
    env = read_env() if env is None else env
    key = env_value(cfg["key"], env)
    secret = env_value(cfg["secret"], env) if cfg.get("secret") else ""
    return key, secret


def missing_credentials(cfg, key, secret):
    """Names of the credential variables that are not set."""
    missing = []
    if not key:
        missing.append(cfg["key"])
    if cfg.get("secret") and not secret:
        missing.append(cfg["secret"])
    return missing


def encode_reference(path):
    """A reference image as (mime, base64) for multimodal request bodies."""
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError("Reference image not found: {}".format(path))
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return mime, base64.b64encode(path.read_bytes()).decode("ascii")


# --------------------------------------------------------------------------- #
# Transport - the only place this project talks HTTP.
# --------------------------------------------------------------------------- #
def describe_api_error(payload, raw):
    """Pull the human-readable message out of an error body."""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return error["message"]
        if isinstance(error, str):
            return error
        for field in ("msg", "message", "failMsg", "detail"):
            if payload.get(field):
                return str(payload[field])
    return (raw or "")[:400]


def remedy_for(status, cfg):
    """The one actionable line for an HTTP status, or "".

    A bad key used to read `API error 401: Unauthorized` and stop there, which
    tells a user what happened and nothing about what to do. Every provider
    config already carries the env var its key lives in AND a `where` URL to get
    one - both were sitting unused at exactly the moment they were needed.

    Only the 400/404 model-id hint existed before; the rest of this table is new.
    Kept here rather than in the GUI because the GUI is not the only caller: the
    CLI tools print these too, and a remedy that only appeared in one of them
    would be the more confusing outcome.
    """
    key_var = cfg.get("key", "the API key")
    where = cfg.get("where", "")
    # Two different suggestions, because 401 is about the key itself and
    # 402/403 are about the account behind it - the same page, a different verb.
    get_one = ("\nGet one at {}".format(where)) if where else ""
    check_account = ("\nCheck the account at {}".format(where)) if where else ""

    if status == 401:
        return ("\n{} is set but the provider rejected it. Check it for a typo or a "
                "trailing space, or issue a new one.{}".format(key_var, get_one))
    if status == 403:
        return ("\nThe key is valid but not allowed to do this. Usually that means no "
                "credit left, or this model is not enabled on the account.{}".format(
                    check_account))
    if status == 402:
        return "\nThe account is out of credit.{}".format(check_account)
    if status == 429:
        return ("\nToo many requests, or the balance ran out mid-batch. Wait a minute "
                "and try a smaller batch.")
    if status in (400, 404):
        return "\nIf the model id is wrong, set {}=<id> in .env.".format(
            cfg.get("model_var", "the model var"))
    if status >= 500:
        # Deliberately not "just retry": open_with_retry() does not retry an
        # HTTPError precisely because the server received the request and may
        # already have started a paid job.
        return ("\nThat is the provider's side, not yours. It may still have started "
                "the job, so check the account before resubmitting.")
    return ""


# A transport-level failure (URLError - DNS, timeout, connection reset: no
# response ever arrived) is retried with backoff; an HTTPError - even a
# 5xx - is not, and never was: the server received and possibly acted on the
# request, and blindly retrying a POST that may have already started a paid
# job risks starting it twice. This distinction is why open_with_retry()
# exists as its own function rather than a loop inside every caller: get it
# right once, here, and every transport (this module's own _send/download,
# generate_sound.py's separate _send/get_json) shares the same judgment call.
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0


def open_with_retry(request, timeout, url, attempts=RETRY_ATTEMPTS, sleep=time.sleep):
    """urllib.request.urlopen(), retried only on a genuine transport failure.

    `sleep` is injectable, the same seam poll() already uses, so a test can
    exercise every retry without a real wait.
    """
    for attempt in range(1, attempts + 1):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError:
            raise   # a real response arrived - never retried here
        except urllib.error.URLError:
            if attempt == attempts:
                raise
            sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5))


def _send(request, url):
    request.add_header("User-Agent", USER_AGENT)
    try:
        with open_with_retry(request, TIMEOUT, url) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach {}: {}".format(url, exc.reason))

    try:
        return status, json.loads(raw), raw
    except json.JSONDecodeError:
        return status, None, raw


def post_json(url, body, headers):
    """POST and return (status, parsed_json_or_None, raw_text)."""
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    return _send(request, url)


def get_json(url, headers):
    """GET and return (status, parsed_json_or_None, raw_text)."""
    request = urllib.request.Request(url, headers=headers, method="GET")
    return _send(request, url)


def download(url):
    """Fetch the finished image. Returns (bytes, mime).

    Both providers hand back a URL rather than inline bytes, so this is the last
    step of every generation.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with open_with_retry(request, TIMEOUT, url) as response:
            mime = (response.headers.get("Content-Type") or "").split(";")[0].strip()
            data = response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Could not download the image ({}): HTTP {}".format(url, exc.code))
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not download the image ({}): {}".format(url, exc.reason))

    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError("The image at {} is larger than {} MB".format(
            url, MAX_IMAGE_BYTES // (1024 * 1024)))
    if not data:
        raise RuntimeError("The image at {} was empty".format(url))
    if not mime.startswith("image/"):
        # Content-Type is advisory; fall back to the extension rather than refusing
        # a good image because a CDN mislabelled it.
        mime = mimetypes.guess_type(urllib.parse.urlparse(url).path)[0] or "image/png"
    return data, mime


def save_image(data, mime, out_name=None):
    ext = mimetypes.guess_extension(mime) or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or "avatar-{}{}".format(datetime.now().strftime("%Y%m%d-%H%M%S"), ext)
    path = OUT_DIR / name
    path.write_bytes(data)
    return path


SECRETISH = re.compile(r"auth|key|token|secret", re.IGNORECASE)


def redact_headers(headers):
    """Hide anything that looks like a credential.

    A name-matching rule rather than a fixed allowlist: the previous version
    listed two literal header names, so a provider authenticating with any other
    header would have printed its key to stdout on --dry-run.
    """
    return {k: ("<redacted>" if SECRETISH.search(k) else v) for k, v in headers.items()}


# --------------------------------------------------------------------------- #
# Kie - createTask -> recordInfo -> download
# --------------------------------------------------------------------------- #
def kie_headers(key):
    return {"Content-Type": "application/json", "Authorization": "Bearer " + key}


def upload_kie_reference(key, path, base=None):
    """Upload a local image and return its URL.

    Kie takes reference images as URLs, so a local file needs a home first. This
    is the only reason the reference path involves an extra round trip.
    """
    mime, data = encode_reference(path)
    url = (base.rstrip("/") + "/api/file-base64-upload") if base else KIE_UPLOAD_URL
    body = {
        "base64Data": "data:{};base64,{}".format(mime, data),
        "uploadPath": "images/user-uploads",
        "fileName": Path(path).name,
    }
    status, payload, raw = post_json(url, body, kie_headers(key))
    if status >= 400:
        raise RuntimeError("Reference upload failed ({}): {}".format(
            status, describe_api_error(payload, raw)))
    found = _find_url(payload)
    if not found:
        raise RuntimeError("Reference upload returned no URL: {}".format((raw or "")[:200]))
    return found


def _find_url(payload):
    """First http(s) URL anywhere in a response.

    The upload endpoint's exact field name is not documented; rather than guess
    one key and break, take the first URL and let the caller fail loudly if
    there is none.
    """
    if isinstance(payload, str):
        return payload if payload.startswith("http") else None
    if isinstance(payload, dict):
        for value in payload.values():
            found = _find_url(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _find_url(value)
            if found:
                return found
    return None


# A balance check is read-only and idempotent - unlike a generation call,
# nothing is wrong with answering the third refresh in a minute out of a
# cache rather than the network. The TTL is short (seconds, not minutes)
# specifically so a key added mid-session or a balance that just changed is
# never stale for long - this is here to stop redundant GETs on repeated UI
# refreshes, not to be a real balance tracker.
CREDITS_CACHE_TTL = 20
_credits_cache = {}   # provider -> (monotonic_time, credits, error)


def credits(provider=DEFAULT_PROVIDER, base=None, use_cache=True):
    """Credits left on the account. Returns (credits, error); one is always None.

    No key is not an error - it is "unknown". The badge says so rather than
    showing a red state for an account that simply has not been set up.
    """
    if use_cache:
        cached = _credits_cache.get(provider)
        if cached and time.monotonic() - cached[0] < CREDITS_CACHE_TTL:
            return cached[1], cached[2]

    cfg = PROVIDERS.get(provider, {})
    if provider != "kie":
        return None, "{} does not publish a balance".format(cfg.get("label", provider))
    key = env_value(cfg["key"])
    if not key:
        return None, "no key"
    url = "{}/api/v1/chat/credit".format((base or cfg["base"]).rstrip("/"))
    try:
        status, payload, raw = get_json(url, kie_headers(key))
    except RuntimeError as exc:
        # No network is "unknown", not a failure worth a red badge.
        return None, str(exc)
    if status != 200 or not isinstance(payload, dict):
        result = None, describe_api_error(payload, raw)
        if use_cache:
            _credits_cache[provider] = (time.monotonic(),) + result
        return result
    value = payload.get("data")
    if isinstance(value, dict):
        value = value.get("credit", value.get("credits"))
    try:
        result = int(value), None
        if use_cache:
            _credits_cache[provider] = (time.monotonic(),) + result
        return result
    except (TypeError, ValueError):
        result = None, describe_api_error(payload, raw)
        if use_cache:
            _credits_cache[provider] = (time.monotonic(),) + result
        return result


# Nano Banana Pro's documented input enums. Sending something outside these is
# a rejected request that costs a round trip to discover, so an unknown value is
# dropped and reported rather than passed through hopefully.
KIE_ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
               "9:16", "16:9", "21:9", "auto")
KIE_RESOLUTIONS = ("1K", "2K", "4K")
KIE_OUTPUT_FORMATS = ("png", "jpg")


def build_kie_submit(base, model, key, prompt, reference_urls=(), spec=None):
    """The documented five `input` fields, and nothing invented.

    `resolution` was missing entirely, so every image came back at the 1K
    default however the app was configured.
    """
    spec = spec or {}
    dropped = []

    def pick(value, allowed, default, name):
        text = str(value or "").strip()
        if not text:
            return default
        for option in allowed:
            if text.lower() == option.lower():
                return option
        dropped.append("{}={}".format(name, text))
        return default

    payload = {
        "prompt": prompt,
        "output_format": pick(spec.get("output_format"), KIE_OUTPUT_FORMATS,
                              "png", "output_format"),
        "resolution": pick(spec.get("resolution"), KIE_RESOLUTIONS, "1K", "resolution"),
    }
    aspect = pick(spec.get("aspect"), KIE_ASPECTS, "", "aspect")
    if aspect:
        payload["aspect_ratio"] = aspect
    if reference_urls:
        payload["image_input"] = list(reference_urls)
    url = "{}/api/v1/jobs/createTask".format(base.rstrip("/"))
    body = {"model": model, "input": payload}
    return url, body, kie_headers(key), dropped


def parse_kie_submit(payload):
    """The task id, or None. Accepts either spelling of the field.

    The docs show `task_id` in the getting-started text and `taskId` in the
    response samples, so accept both rather than betting on one.
    """
    data = (payload or {}).get("data") or payload or {}
    if isinstance(data, dict):
        for field in ("taskId", "task_id", "id"):
            if data.get(field):
                return str(data[field])
    return None


def build_kie_status(base, task_id, key):
    url = "{}/api/v1/jobs/recordInfo?taskId={}".format(
        base.rstrip("/"), urllib.parse.quote(task_id))
    return url, kie_headers(key)


def credits_consumed(payload):
    """What the finished job actually cost, or None.

    The real number, straight from the provider. Everything the app says about
    price before a run is an estimate off a published table; this is the only
    figure that is measured, so it is what a cost estimate gets corrected by.
    """
    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        return None
    for field in ("creditsConsumed", "credits_consumed", "credits"):
        if data.get(field) is not None:
            try:
                return float(data[field])
            except (TypeError, ValueError):
                return None
    return None


def parse_kie_status(payload):
    """(done, image_url, error). done=False means keep polling."""
    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        return False, None, None
    state = str(data.get("state") or "").lower()
    if state == "fail":
        reason = data.get("failMsg") or data.get("failCode") or "the job failed"
        return True, None, "Kie reported failure: {}".format(reason)
    if state != "success":
        # waiting / queuing / generating - and anything unrecognised, which is
        # safer to treat as "still working" than as a silent success.
        return False, None, None

    result = data.get("resultJson")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return True, None, "Kie returned an unreadable result: {}".format(result[:200])
    urls = result.get("resultUrls") or [] if isinstance(result, dict) else []
    if not urls:
        return True, None, None
    return True, urls[0], None


# --------------------------------------------------------------------------- #
# Higgsfield - submit -> poll status_url -> download
# --------------------------------------------------------------------------- #
def higgsfield_headers(key, secret):
    return {
        "Content-Type": "application/json",
        "Authorization": "Key {}:{}".format(key, secret),
    }


def build_higgsfield_submit(base, model, key, prompt, secret="", spec=None):
    url = "{}/higgsfield-ai/{}".format(base.rstrip("/"), model.strip("/"))
    body = {"prompt": prompt}
    return url, body, higgsfield_headers(key, secret)


def parse_higgsfield_submit(payload):
    """The status URL to poll, or None."""
    payload = payload or {}
    return payload.get("status_url") or payload.get("statusUrl")


HIGGSFIELD_FAILURES = {
    "failed": "Higgsfield reported failure",
    "nsfw": "Higgsfield rejected the result as NSFW",
    "canceled": "The Higgsfield job was cancelled",
    "cancelled": "The Higgsfield job was cancelled",
}


def parse_higgsfield_status(payload):
    """(done, image_url, error). done=False means keep polling."""
    payload = payload or {}
    status = str(payload.get("status") or "").lower()
    if status in HIGGSFIELD_FAILURES:
        return True, None, HIGGSFIELD_FAILURES[status]
    if status != "completed":
        return False, None, None
    images = payload.get("images") or []
    for image in images:
        url = image.get("url") if isinstance(image, dict) else image
        if url:
            return True, url, None
    return True, None, None


# --------------------------------------------------------------------------- #
# The shared pipeline
# --------------------------------------------------------------------------- #
class GenerationError(Exception):
    """Carries the exit code the CLI should return."""

    def __init__(self, message, code=3):
        super().__init__(message)
        self.code = code


def poll(fetch, timeout=JOB_TIMEOUT, interval=POLL_INTERVAL,
         should_cancel=None, on_stage=None, sleep=time.sleep):
    """Call `fetch()` until it reports done. Returns the image URL.

    `fetch` returns (done, image_url, error) - the shape both parse_*_status
    functions produce, so one loop serves both providers.
    """
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        if should_cancel and should_cancel():
            raise GenerationError("Cancelled.", 3)
        done, image_url, error = fetch()
        if error:
            raise GenerationError(error, 3)
        if done:
            if not image_url:
                raise GenerationError("The finished job carried no image.", 4)
            return image_url
        attempt += 1
        if time.monotonic() >= deadline:
            raise GenerationError(
                "Timed out after {}s waiting for the job. It may still finish on the "
                "provider's side.".format(timeout), 5)
        if on_stage:
            on_stage("Still rendering... ({}s)".format(attempt * interval))
        sleep(interval)


def _resolve(provider, model=None, base=None):
    cfg = PROVIDERS[provider]
    env = read_env()
    key, secret = credentials(cfg, env)
    model = model or env_value(cfg["model_var"], env) or cfg["default_model"]
    base = base or env_value("AIVS_API_BASE", env) or cfg["base"]
    return cfg, key, secret, model, base


def generate(provider=DEFAULT_PROVIDER, prompt="", out_name=None, references=(),
             model=None, base=None, dry_run=False, should_cancel=None,
             on_stage=None, spec=None):
    """Prompt -> saved image path. Returns (path, error); exactly one is None.

    The single entry point: the CLI below and ui/workers.py both call this, so
    request building, polling and file writing exist in exactly one place.
    """
    def stage(message):
        if on_stage:
            on_stage(message)

    if provider not in PROVIDERS:
        return None, GenerationError("Unknown provider: {}".format(provider), 3)

    cfg, key, secret, model, base = _resolve(provider, model, base)
    references = list(references)

    if references and not cfg.get("references"):
        return None, GenerationError(
            "{} has no reference-image input, so the face would be invented rather than "
            "kept. Switch to a provider that supports references, or clear the reference "
            "before generating.".format(cfg["label"]), 3)

    missing = missing_credentials(cfg, key, secret)
    if missing and not dry_run:
        return None, GenerationError(
            "{} not set in {} - cannot reach {}.\nGet a key at {}\n\nMeanwhile, paste this "
            "prompt into the provider's own interface:\n\n{}".format(
                " and ".join(missing), ENV_PATH, cfg["label"], cfg["where"], prompt), 1)

    try:
        if provider == "kie":
            # The uploader lives on its own host, so it only follows `base` when
            # the caller has actually overridden it (tests, or AIVS_API_BASE).
            upload_base = base if base != cfg["base"] else None
            reference_urls = []
            for path in references:
                stage("Uploading reference...")
                reference_urls.append(upload_kie_reference(key, path, upload_base))
            url, body, headers, dropped = build_kie_submit(
                base, model, key or "DRY-RUN", prompt, reference_urls, spec)
            if dropped:
                # Reported, never silently sent: an unknown resolution would
                # otherwise come back as a 1K image with no explanation.
                stage("Ignored (not a documented value): " + ", ".join(dropped))
        else:
            url, body, headers = build_higgsfield_submit(
                base, model, key or "DRY-RUN", prompt, secret or "DRY-RUN", spec)
    except (FileNotFoundError, RuntimeError) as exc:
        return None, GenerationError(str(exc), 3)

    if dry_run:
        return None, None  # the caller describes the request; nothing was sent

    try:
        stage("Submitting...")
        status, payload, raw = post_json(url, body, headers)
        if status >= 400:
            message = "API error {}: {}".format(status, describe_api_error(payload, raw))
            message += remedy_for(status, cfg)
            return None, GenerationError(message, 3)

        if provider == "kie":
            task_id = parse_kie_submit(payload)
            if not task_id:
                return None, GenerationError(
                    "Kie accepted the request but returned no task id: {}".format(
                        (raw or "")[:200]), 3)
            status_url, status_headers = build_kie_status(base, task_id, key)
            parse_status = parse_kie_status
        else:
            status_url = parse_higgsfield_submit(payload)
            if not status_url:
                return None, GenerationError(
                    "Higgsfield accepted the request but returned no status URL: {}".format(
                        (raw or "")[:200]), 3)
            status_headers = higgsfield_headers(key, secret)
            parse_status = parse_higgsfield_status

        def fetch():
            code, body_json, body_raw = get_json(status_url, status_headers)
            if code >= 400:
                raise GenerationError("Status check failed {}: {}".format(
                    code, describe_api_error(body_json, body_raw)), 3)
            return parse_status(body_json)

        stage("Waiting for the job...")
        image_url = poll(fetch, should_cancel=should_cancel, on_stage=on_stage)

        stage("Downloading...")
        data, mime = download(image_url)
    except GenerationError as exc:
        return None, exc
    except RuntimeError as exc:
        return None, GenerationError(str(exc), 3)

    return save_image(data, mime, out_name), None


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Generate an image from a prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--provider", choices=sorted(PROVIDERS), default=DEFAULT_PROVIDER)
    p.add_argument("--prompt", help="prompt text")
    p.add_argument("--prompt-file", help="path to a prompt .txt file")
    p.add_argument("--out", help="output filename inside temp/outputs/images/")
    p.add_argument(
        "--reference", action="append", default=[],
        help="reference image to keep the character consistent (repeatable; kie only)",
    )
    p.add_argument("--model", help="override the model id for this call")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument("--aspect", help="aspect ratio to request, e.g. 4:5")
    p.add_argument(
        "--dry-run", action="store_true",
        help="build and describe the request without sending it or needing a key",
    )
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.prompt and not args.prompt_file:
        sys.exit("Give either --prompt \"...\" or --prompt-file <path>.")

    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Prompt file not found: {}".format(path))
        prompt = path.read_text(encoding="utf-8").strip()
    else:
        prompt = args.prompt.strip()

    for reference in args.reference:
        candidate = Path(reference)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.exists():
            sys.exit("Reference image not found: {}".format(candidate))

    spec = {"aspect": args.aspect} if args.aspect else None
    cfg, key, secret, model, base = _resolve(args.provider, args.model, args.base_url)

    if args.dry_run:
        if args.reference and not cfg.get("references"):
            print("{} has no reference-image input.".format(cfg["label"]), file=sys.stderr)
            return 3
        if args.provider == "kie":
            url, body, headers, dropped = build_kie_submit(
                base, model, key or "DRY-RUN", prompt,
                ["https://example.invalid/reference.png"] * len(args.reference), spec)
            if dropped:
                print("ignored: {}".format(", ".join(dropped)))
        else:
            url, body, headers = build_higgsfield_submit(
                base, model, key or "DRY-RUN", prompt, secret or "DRY-RUN", spec)
        print("POST {}".format(url))
        print("headers: {}".format(json.dumps(redact_headers(headers))))
        print("model:   {}".format(model))
        print("references: {}".format(len(args.reference)))
        print("body bytes: {}".format(len(json.dumps(body))))
        return 0

    print("Generating with {} ({})...".format(model, args.provider), file=sys.stderr)
    path, error = generate(
        provider=args.provider, prompt=prompt, out_name=args.out,
        references=args.reference, model=args.model, base=args.base_url,
        on_stage=lambda message: print(message, file=sys.stderr), spec=spec,
    )
    if error:
        print(str(error), file=sys.stderr)
        return error.code

    print("[image] {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
