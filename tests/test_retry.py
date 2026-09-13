"""generate_image.open_with_retry() and the credits() cache.

The claim worth defending: a transport-level failure (URLError - no response
ever arrived) is retried with backoff and can recover; a real HTTP response
(even an error one) is never retried, because retrying a POST that may have
already started a paid job risks starting it twice. Also: a balance check
answers a second call inside its TTL from cache, not the network, and a key
added or an explicit `use_cache=False` is never left stuck behind a stale one.

No real network: urllib.request.urlopen itself is monkeypatched, the same
"replace the function, restore it in finally" convention test_video.py uses
for gi.get_json/gi.env_value.
"""
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-retry-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

import generate_image as gi  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


import urllib.request as _ur  # noqa: E402

real_urlopen = _ur.urlopen


class FakeResponse:
    def __init__(self, status=200):
        self.status = status
    def read(self, *a):
        return b"{}"
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


print("=== RETRIES A TRANSPORT FAILURE, THEN RECOVERS ===")
calls = {"n": 0}
sleeps = []


def flaky_then_ok(request, timeout=None):
    calls["n"] += 1
    if calls["n"] < 3:
        raise urllib.error.URLError("connection reset")
    return FakeResponse()


_ur.urlopen = flaky_then_ok
try:
    response = gi.open_with_retry(object(), 10, "https://example.invalid",
                                  attempts=5, sleep=lambda s: sleeps.append(s))
finally:
    _ur.urlopen = real_urlopen
check("recovered on the third attempt", calls["n"] == 3, str(calls["n"]))
check("slept twice, with increasing backoff",
      len(sleeps) == 2 and sleeps[1] > sleeps[0], str(sleeps))
check("returned the real response object", isinstance(response, FakeResponse))

print()
print("=== GIVES UP AFTER THE LAST ATTEMPT ===")
calls["n"] = 0


def always_fails(request, timeout=None):
    calls["n"] += 1
    raise urllib.error.URLError("still down")


_ur.urlopen = always_fails
try:
    raised = False
    try:
        gi.open_with_retry(object(), 10, "https://example.invalid",
                           attempts=3, sleep=lambda s: None)
    except urllib.error.URLError:
        raised = True
finally:
    _ur.urlopen = real_urlopen
check("raises once every attempt is exhausted", raised)
check("tried exactly `attempts` times, not more", calls["n"] == 3, str(calls["n"]))

print()
print("=== NEVER RETRIES A REAL HTTP RESPONSE, EVEN AN ERROR ONE ===")
calls["n"] = 0


def http_error(request, timeout=None):
    calls["n"] += 1
    raise urllib.error.HTTPError("https://example.invalid", 500, "server error", {}, None)


_ur.urlopen = http_error
try:
    raised_http = False
    try:
        gi.open_with_retry(object(), 10, "https://example.invalid",
                           attempts=5, sleep=lambda s: fails.append(
                               "slept on an HTTPError - should never happen"))
    except urllib.error.HTTPError:
        raised_http = True
finally:
    _ur.urlopen = real_urlopen
check("an HTTPError is raised immediately", raised_http)
check("exactly one attempt - never retried", calls["n"] == 1, str(calls["n"]))

print()
print("=== THE CREDITS CACHE ===")
gi._credits_cache.clear()
gi.env_value = lambda name, env=None: "FAKE-KEY"
get_json_calls = {"n": 0}
real_get_json = gi.get_json


def counting_get_json(url, headers):
    get_json_calls["n"] += 1
    return 200, {"data": 1000 + get_json_calls["n"]}, ""


gi.get_json = counting_get_json
try:
    first, err1 = gi.credits("kie")
    second, err2 = gi.credits("kie")
    check("the first call hits the network", get_json_calls["n"] == 1, str(get_json_calls["n"]))
    check("a second call inside the TTL reuses the cached value",
          second == first and get_json_calls["n"] == 1,
          "{} {} calls={}".format(first, second, get_json_calls["n"]))
    third, _err3 = gi.credits("kie", use_cache=False)
    check("use_cache=False always hits the network",
          get_json_calls["n"] == 2, str(get_json_calls["n"]))
    check("a different provider is not served the other one's cache",
          gi.credits("higgsfield")[1] is not None and get_json_calls["n"] == 2)
finally:
    gi.get_json = real_get_json
    gi._credits_cache.clear()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL RETRY/CACHE CHECKS PASSED")
