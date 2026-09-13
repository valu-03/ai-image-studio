"""Kling 3.0 through Kie: the request, the price, and the balance.

The request body is checked field by field against the published spec, because
every field here is a way to spend money incorrectly. `duration` in particular
is a STRING in Kling's schema - sending the integer is the kind of mistake that
fails at the provider with an error that does not explain itself.

The pricing table is treated as what it is: seeded numbers off a marketing page,
labelled `estimated` until a real charge replaces them. The test that matters is
that a measured charge DOES replace them.

Standard library only; no network, no PyQt.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-video-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

# This suite calls record_actual() and asserts the real tools/pricing.json is
# untouched by it - true only if this file cannot reach that path at all, run
# standalone or through run_all.py. A real charge landing in pricing.json (a
# clip generated once through the CLI to verify a feature - correct, intended
# behaviour) silently broke every assertion below it that reads gv.load_pricing()
# and expects the seed numbers, twice, on two different real charges. Written as
# a literal seed rather than a copy of the real file so this suite's pass/fail
# never depends on whatever state that file happens to be in right now.
_TEST_PRICING = Path(tempfile.gettempdir()) / "aivs-video-test-pricing.json"
_TEST_PRICING.write_text(json.dumps({
    "note": "Test fixture - a literal copy of the seed shape, not the real file.",
    "as_of": "2026-08-31",
    "sources": ["https://www.bitdoze.com/kie-ai-review/", "https://kie.ai/pricing"],
    "currency": "credits",
    "models": {
        "nano-banana-pro": {
            "label": "Nano Banana Pro", "unit": "image", "credits_per_unit": 24,
            "multipliers": {"resolution": {"1K": 1.0, "2K": 1.0, "4K": 1.0}},
            "confidence": "estimated", "note": "",
        },
        "kling-3.0/video": {
            "label": "Kling 3.0", "unit": "second", "credits_per_unit": 27,
            "multipliers": {
                "mode": {"std": 1.0, "pro": 2.0, "4K": 3.0},
                "sound": {"false": 1.0, "true": 2.0},
            },
            "confidence": "estimated", "note": "",
        },
    },
}), encoding="utf-8")
os.environ["AIVS_PRICING_FILE"] = str(_TEST_PRICING)

import build_story as bs  # noqa: E402
import generate_image as gi  # noqa: E402
import generate_video as gv  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== THE REQUEST, AGAINST THE PUBLISHED SPEC ===")
url, body, headers, dropped = gv.build_submit(
    "https://api.kie.ai", gv.DEFAULT_MODEL, "KEY", "slow push in on the cat",
    duration=5)
check("posts to createTask", url.endswith("/api/v1/jobs/createTask"), url)
check("names the model", body["model"] == "kling-3.0/video", body["model"])

payload = body["input"]
check("duration is a STRING", isinstance(payload["duration"], str), repr(payload["duration"]))
check("and it is the number asked for", payload["duration"] == "5")
check("carries every documented field",
      set(payload) == {"prompt", "duration", "aspect_ratio", "mode", "sound", "multi_shots"},
      str(sorted(payload)))
check("defaults to the cheap tier", payload["mode"] == "std", payload["mode"])
check("and to silence", payload["sound"] is False)
check("vertical by default", payload["aspect_ratio"] == "9:16", payload["aspect_ratio"])
check("nothing was dropped", not dropped, str(dropped))

_url, body, _h, _d = gv.build_submit(
    "https://api.kie.ai", gv.DEFAULT_MODEL, "KEY", "x",
    image_urls=["https://example.invalid/frame.png"], duration=7)
check("a first frame becomes image_urls",
      body["input"]["image_urls"] == ["https://example.invalid/frame.png"])
check("7 seconds is legal now", body["input"]["duration"] == "7")

print()
print("=== WHAT IT REFUSES TO SEND ===")
for duration, expected in ((2, "3"), (16, "15"), (99, "15"), ("nonsense", "5")):
    _u, body, _h, dropped = gv.build_submit(
        "https://api.kie.ai", gv.DEFAULT_MODEL, "KEY", "x", duration=duration)
    check("duration {!r} is clamped to {}".format(duration, expected),
          body["input"]["duration"] == expected and dropped,
          "{} {}".format(body["input"]["duration"], dropped))

_u, body, _h, dropped = gv.build_submit(
    "https://api.kie.ai", gv.DEFAULT_MODEL, "KEY", "x", mode="ultra", aspect_ratio="4:5")
check("an invented mode is dropped, not sent", body["input"]["mode"] == "std", str(dropped))
check("and an aspect Kling does not take is too",
      body["input"]["aspect_ratio"] == "9:16", str(dropped))
check("both are reported", len(dropped) == 2, str(dropped))

print()
print("=== generate()'s own multi_shots parameter actually reaches the payload ===")
# build_submit() has always accepted/sent multi_shots (the check above already
# covers that) - what was missing was generate() ever forwarding a caller's
# value to it at all, so it was permanently False no matter what a CLI flag
# or a UI checkbox asked for. Patch build_submit to see what generate() sends
# it, rather than assuming the plumbing works from build_submit's own test.
captured = {}
_original_build_submit = gv.build_submit


def _capture_build_submit(*args, **kwargs):
    result = _original_build_submit(*args, **kwargs)
    captured["body"] = result[1]
    return result


gv.build_submit = _capture_build_submit
try:
    gv.generate(prompt="x", multi_shots=True, dry_run=True)
    on_default = dict(captured)
    gv.generate(prompt="x", dry_run=True)
finally:
    gv.build_submit = _original_build_submit
check("generate(multi_shots=True) reaches the built payload",
      on_default.get("body", {}).get("input", {}).get("multi_shots") is True,
      str(on_default.get("body")))
check("generate() with no multi_shots argument still defaults to False",
      captured.get("body", {}).get("input", {}).get("multi_shots") is False,
      str(captured.get("body")))

print()
print("=== the CLI's --multi-shots flag reaches the same payload ===")
TOOL = ROOT / "tools" / "generate_video.py"


def run(args):
    return subprocess.run([sys.executable, str(TOOL)] + args,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--prompt", "x", "--dry-run"])
check("no flag -> multi_shots false in the dry-run payload",
      p.returncode == 0 and "\"multi_shots\": false" in p.stdout, p.stdout[-200:])

p = run(["--prompt", "x", "--dry-run", "--multi-shots"])
check("--multi-shots -> multi_shots true in the dry-run payload",
      p.returncode == 0 and "\"multi_shots\": true" in p.stdout, p.stdout[-200:])

print()
print("=== THE BANK AND THE BUILDER AGREE ===")
bank = bs.load_bank()
cfg = bs.video_models(bank).get(bs.DEFAULT_VIDEO_MODEL, {})
check("the bank names the same model", bs.DEFAULT_VIDEO_MODEL == gv.DEFAULT_MODEL)
check("the same modes", tuple(cfg["mode"]) == gv.MODES, str(cfg["mode"]))
check("the same aspects", tuple(cfg["aspect_ratio"]) == gv.ASPECTS, str(cfg["aspect_ratio"]))
check("the same duration range",
      (cfg["duration"]["min"], cfg["duration"]["max"]) == (gv.DURATION_MIN, gv.DURATION_MAX))
# The clip length a story plans has to be a duration Kling accepts, or the whole
# storyboard is unbuildable - which is exactly the bug this release fixes.
low, high = bs.clip_range(bank)
check("and the story's clip range fits inside it",
      low >= gv.DURATION_MIN and high <= gv.DURATION_MAX, "{}-{}".format(low, high))

print()
print("=== PRICE: seeded, then measured ===")
pricing = gv.load_pricing()
check("the table says when it was written", pricing.get("as_of"))
check("and where the numbers came from", pricing.get("sources"))
check("every model is labelled estimated until proven",
      all(m.get("confidence") == "estimated" for m in pricing["models"].values()),
      str([(k, m.get("confidence")) for k, m in pricing["models"].items()]))

total, confidence, _note = gv.estimate(gv.DEFAULT_MODEL, 35, pricing, mode="std", sound=False)
check("35 seconds of std silent video", total == 945, str(total))
check("labelled as an estimate", confidence == "estimated")
pro, _c, _n = gv.estimate(gv.DEFAULT_MODEL, 35, pricing, mode="pro", sound=False)
check("pro costs more than std", pro > total, "{} vs {}".format(pro, total))
loud, _c, _n = gv.estimate(gv.DEFAULT_MODEL, 35, pricing, mode="std", sound=True)
check("sound costs more than silence", loud > total, "{} vs {}".format(loud, total))
images, _c, _n = gv.estimate("nano-banana-pro", 7, pricing)
check("seven images", images == 168, str(images))
unknown, confidence, _n = gv.estimate("not-a-model", 5, pricing)
check("an unknown model is not guessed at", unknown is None and confidence == "unknown")

# The point of the confidence field: a real charge replaces the guess.
updated = gv.record_actual(gv.DEFAULT_MODEL, 5, 100.0,
                           pricing=json.loads(json.dumps(pricing)))
model = updated["models"][gv.DEFAULT_MODEL]
check("a measured charge overwrites the seeded rate", model["credits_per_unit"] == 20.0,
      str(model["credits_per_unit"]))
check("and it stops calling itself an estimate", model["confidence"] == "measured")
check("recording the date it was measured", model.get("measured_on"))
after, confidence, _n = gv.estimate(gv.DEFAULT_MODEL, 5, updated, mode="std", sound=False)
check("later estimates use the measured rate", after == 100, str(after))
check("and say so", confidence == "measured")

check("pricing.json on disk is untouched by that",
      gv.load_pricing()["models"][gv.DEFAULT_MODEL]["confidence"] == "estimated")

print()
print("=== THE LINE ON THE BUTTON ===")
note = gv.price_note(gv.DEFAULT_MODEL, 35, credits_left=5000, mode="std", sound=False)
check("names the cost and the balance", "945" in note and "5,000" in note, note)
poor = gv.price_note(gv.DEFAULT_MODEL, 35, credits_left=100, mode="std", sound=False)
check("and warns when there is not enough", "not enough" in poor, poor)

print()
print("=== THE BALANCE ===")
value, error = gi.credits("kie")
check("no key reads as unknown, not as a failure", value is None and error == "no key",
      "{} {}".format(value, error))
value, error = gi.credits("higgsfield")
check("a provider with no balance endpoint says so", value is None and "balance" in error,
      str(error))

captured = {}


def fake_get(url, headers):
    captured["url"] = url
    return 200, {"code": 200, "msg": "success", "data": 1234}, ""


real_get, real_env = gi.get_json, gi.env_value
gi.get_json = fake_get
gi.env_value = lambda name, env=None: "KEY"
try:
    value, error = gi.credits("kie")
finally:
    gi.get_json, gi.env_value = real_get, real_env
check("reads data as the balance", value == 1234 and error is None, str(value))
check("from the documented endpoint",
      captured["url"] == "https://api.kie.ai/api/v1/chat/credit", captured["url"])

print()
print("=== WHAT A FINISHED JOB REALLY COST ===")
check("creditsConsumed is read",
      gi.credits_consumed({"data": {"creditsConsumed": 135}}) == 135.0)
check("a job that does not report it returns None",
      gi.credits_consumed({"data": {"state": "success"}}) is None)
check("and nonsense does not raise",
      gi.credits_consumed({"data": {"creditsConsumed": "lots"}}) is None)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL VIDEO CHECKS PASSED")
