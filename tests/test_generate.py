"""generate_image.py against a mock of the two providers.

Both are asynchronous, so the thing worth defending is the whole three-step
pipeline - submit, poll until done, download - not just one request body. The
mock reports "still working" on the first status check, so a passing run proves
the poll loop actually ran.

Keys are fake strings passed through the child environment, and a temp .env via
AIVS_ENV_FILE keeps the real one out of it - otherwise "no key" scenarios would
start failing the moment a real key is written to .env, since read_env() wins.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
TOOL = ROOT / "tools" / "generate_image.py"
IMAGES = ROOT / "temp" / "outputs" / "images"

import mock_api

PORT = 8791
mock_api.serve(PORT)
BASE = "http://127.0.0.1:{}".format(PORT)

# An empty .env, so a cleared process variable really means "no key".
EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-empty.env"
EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")

KIE = {"KIE_API_KEY": "kie-key"}
HF = {"HIGGSFIELD_API_KEY_ID": "hf-id", "HIGGSFIELD_API_KEY_SECRET": "hf-secret"}

fails = []
written = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def run(args, env_extra=None, poll_fast=True):
    env = dict(os.environ)
    env["AIVS_ENV_FILE"] = str(EMPTY_ENV)
    for name in list(KIE) + list(HF):
        env.pop(name, None)
    env.update(env_extra or {})
    mock_api.reset()
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + args,
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    return proc


def headers_of(record):
    # urllib capitalises header names; HTTP headers are case-insensitive.
    return {k.lower(): v for k, v in (record or {}).get("headers", {}).items()}


def saved(name):
    path = IMAGES / name
    written.append(path)
    return path


print("=== dry run needs no key, and leaks none ===")
for provider, secret in (("kie", "kie-key"), ("higgsfield", "hf-secret")):
    p = run(["--provider", provider, "--prompt", "hello", "--dry-run"])
    check("{} dry-run exits 0".format(provider), p.returncode == 0, p.stderr[:120])
    check("{} redacts auth".format(provider), "<redacted>" in p.stdout, p.stdout[:120])
    check("{} prints no key".format(provider),
          secret not in p.stdout and secret not in p.stderr)

print()
print("=== missing credentials ===")
p = run(["--provider", "kie", "--prompt", "x", "--base-url", BASE])
check("kie exits 1", p.returncode == 1, str(p.returncode))
check("names the variable", "KIE_API_KEY" in p.stderr)
check("offers the prompt to paste", "paste this prompt" in p.stderr)
check("no traceback", "Traceback" not in p.stderr)

# Higgsfield needs BOTH halves; one alone must not look like "configured".
p = run(["--provider", "higgsfield", "--prompt", "x", "--base-url", BASE],
        {"HIGGSFIELD_API_KEY_ID": "hf-id"})
check("id without secret exits 1", p.returncode == 1, str(p.returncode))
check("names the missing secret", "HIGGSFIELD_API_KEY_SECRET" in p.stderr, p.stderr[:160])
check("does not name the one that is set",
      "HIGGSFIELD_API_KEY_ID is" not in p.stderr and
      p.stderr.count("HIGGSFIELD_API_KEY_ID") == 0, p.stderr[:160])

print()
print("=== kie: submit -> poll -> download ===")
p = run(["--provider", "kie", "--prompt", "an ultra-realistic portrait",
         "--base-url", BASE, "--aspect", "4:5", "--out", "test-kie.png"], KIE)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("prints the marker", p.stdout.startswith("[image] "), p.stdout[:80])
img = saved("test-kie.png")
check("file written", img.exists())
check("real PNG bytes", img.exists() and img.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
check("polled at least once", "Still rendering" in p.stderr or "Waiting" in p.stderr,
      p.stderr[:160])
sent = mock_api.STATE["last"]
check("hit createTask", "createTask" in (sent or {}).get("path", ""), str(sent and sent["path"]))
check("bearer auth", headers_of(sent).get("authorization") == "Bearer kie-key")
check("model in body", (sent or {})["body"].get("model") == "nano-banana-pro",
      json.dumps((sent or {}).get("body", {}))[:120])
check("prompt in input", "ultra-realistic" in json.dumps((sent or {})["body"]["input"]))
check("aspect passed through", (sent or {})["body"]["input"].get("aspect_ratio") == "4:5")
check("status poll authenticated",
      headers_of(mock_api.STATE["last_status"]).get("authorization") == "Bearer kie-key",
      str(headers_of(mock_api.STATE["last_status"]).get("authorization")))
check("no key in output", "kie-key" not in p.stdout)

print()
print("=== higgsfield: submit -> poll status_url -> download ===")
p = run(["--provider", "higgsfield", "--prompt", "an editorial portrait",
         "--base-url", BASE, "--out", "test-hf.png"], HF)
check("exits 0", p.returncode == 0, p.stderr[:200])
img = saved("test-hf.png")
check("file written", img.exists())
check("real PNG bytes", img.exists() and img.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
sent = mock_api.STATE["last"]
check("hit the soul endpoint", "soul/v2/standard" in (sent or {}).get("path", ""),
      str(sent and sent["path"]))
check("key:secret auth", headers_of(sent).get("authorization") == "Key hf-id:hf-secret")
check("prompt in body", "editorial" in json.dumps((sent or {})["body"]))
check("status poll authenticated",
      headers_of(mock_api.STATE["last_status"]).get("authorization") == "Key hf-id:hf-secret",
      str(headers_of(mock_api.STATE["last_status"]).get("authorization")))
check("no secret in output", "hf-secret" not in p.stdout and "hf-secret" not in p.stderr)

print()
print("=== references ===")
ref = saved("test-kie.png")
p = run(["--provider", "kie", "--prompt", "same person, different angle",
         "--base-url", BASE, "--reference", str(ref), "--out", "test-kie-ref.png"], KIE)
check("kie accepts a reference", p.returncode == 0, p.stderr[:200])
saved("test-kie-ref.png")
check("uploaded then referenced",
      "image_input" in json.dumps(mock_api.STATE["last"]["body"]["input"]),
      json.dumps(mock_api.STATE["last"]["body"]["input"])[:160])

# The one that must never fail silently: a dropped reference means a different
# person, which is the whole failure consistent-character.md exists to prevent.
p = run(["--provider", "higgsfield", "--prompt", "same person",
         "--base-url", BASE, "--reference", str(ref)], HF)
check("higgsfield refuses a reference", p.returncode != 0, str(p.returncode))
check("says why", "reference" in p.stderr.lower(), p.stderr[:200])
check("wrote no image", "[image]" not in p.stdout)

p = run(["--provider", "kie", "--prompt", "x", "--base-url", BASE,
         "--reference", "nope.png"], KIE)
check("missing reference file refused", p.returncode != 0)
check("names the file", "not found" in p.stderr.lower(), p.stderr[:120])

print()
print("=== failure modes ===")
for provider, env in (("kie", KIE), ("higgsfield", HF)):
    p = run(["--provider", provider, "--prompt", "x", "--base-url", BASE + "/boom",
             "--model", "bogus-model"], env)
    check("{} API error exits 3".format(provider), p.returncode == 3, str(p.returncode))
    check("{} surfaces the message".format(provider), "model not found" in p.stderr,
          p.stderr[:160])

    p = run(["--provider", provider, "--prompt", "x", "--base-url", BASE + "/fails"], env)
    check("{} job failure exits 3".format(provider), p.returncode == 3, str(p.returncode))

    p = run(["--provider", provider, "--prompt", "x", "--base-url", BASE + "/noimage"], env)
    check("{} no image exits 4".format(provider), p.returncode == 4, str(p.returncode))

    if provider == "kie":
        p = run(["--provider", provider, "--prompt", "x",
                 "--base-url", BASE + "/pollerr"], env)
        check("kie: a 4xx during polling exits 3, not a 5-minute timeout",
              p.returncode == 3, str(p.returncode))
        check("kie: the poll error is surfaced", "Status check failed 429" in p.stderr,
              p.stderr[:200])

    p = run(["--provider", provider, "--prompt", "x",
             "--base-url", "http://127.0.0.1:9"], env)
    check("{} unreachable exits 3".format(provider), p.returncode == 3, str(p.returncode))
    check("{} no traceback".format(provider), "Traceback" not in p.stderr, p.stderr[:160])

check("kie suggests the model var", "KIE_IMAGE_MODEL" in run(
    ["--provider", "kie", "--prompt", "x", "--base-url", BASE + "/boom"], KIE).stderr)

print()
print("=== the poll loop itself (in process, no waiting) ===")
sys.path.insert(0, str(ROOT / "tools"))
import generate_image as gi  # noqa: E402

calls = {"n": 0}


def never_done():
    calls["n"] += 1
    return False, None, None


try:
    gi.poll(never_done, timeout=0.05, interval=0, sleep=lambda _s: None)
    check("timeout raises", False, "no error raised")
except gi.GenerationError as exc:
    check("timeout raises", True)
    check("timeout is exit 5", exc.code == 5, str(exc.code))
    check("polled more than once", calls["n"] > 1, str(calls["n"]))

cancelled = {"stop": False}


def then_cancel():
    cancelled["stop"] = True
    return False, None, None


try:
    gi.poll(then_cancel, interval=0, should_cancel=lambda: cancelled["stop"],
            sleep=lambda _s: None)
    check("cancel stops the loop", False, "no error raised")
except gi.GenerationError as exc:
    check("cancel stops the loop", "Cancelled" in str(exc), str(exc))

print()
print("=== video shares the poll path: a 4xx mid-render is surfaced, not a timeout ===")
import generate_video as gv  # noqa: E402

_saved = {k: os.environ.get(k) for k in ("AIVS_ENV_FILE", "KIE_API_KEY")}
os.environ["AIVS_ENV_FILE"] = str(EMPTY_ENV)   # ignore the real .env
os.environ["KIE_API_KEY"] = "kie-key"
try:
    path, err, _credits = gv.generate(
        prompt="slow push in on the cat", base=BASE + "/pollerr")
finally:
    for k, v in _saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
check("video generate returns an error, not a path", path is None and err is not None)
check("and it names the poll status, not a timeout",
      "Status check failed 429" in str(err) and "Timed out" not in str(err), str(err))

print()
print("=== parsers, without a network ===")
check("kie accepts taskId", gi.parse_kie_submit({"data": {"taskId": "a"}}) == "a")
check("kie accepts task_id", gi.parse_kie_submit({"data": {"task_id": "b"}}) == "b")
check("kie resultJson is a JSON string",
      gi.parse_kie_status({"data": {"state": "success", "resultJson":
                                    '{"resultUrls":["http://x/y.png"]}'}})
      == (True, "http://x/y.png", None))
done, url, err = gi.parse_kie_status({"data": {"state": "generating"}})
check("kie keeps polling while generating", (done, url, err) == (False, None, None))
done, url, err = gi.parse_kie_status({"data": {"state": "fail", "failMsg": "nope"}})
check("kie failure carries the reason", done and err and "nope" in err, str(err))
done, url, err = gi.parse_higgsfield_status({"status": "nsfw"})
check("higgsfield nsfw is a failure", done and err and "NSFW" in err, str(err))
check("higgsfield reads images[0].url",
      gi.parse_higgsfield_status(
          {"status": "completed", "images": [{"url": "http://x/y.png"}]})
      == (True, "http://x/y.png", None))
check("unknown state keeps polling",
      gi.parse_higgsfield_status({"status": "something-new"}) == (False, None, None))
check("redaction catches any credential header",
      gi.redact_headers({"X-Api-Key": "s", "Authorization": "s", "Accept": "json"})
      == {"X-Api-Key": "<redacted>", "Authorization": "<redacted>", "Accept": "json"})

for path in set(written):
    if path.exists():
        path.unlink()
EMPTY_ENV.unlink(missing_ok=True)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL GENERATE CHECKS PASSED")
sys.exit(0)
