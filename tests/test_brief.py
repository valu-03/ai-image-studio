"""The validation gates in brief.py, and ask_llm.py against a mock API.

The gate tests are the most important in the change: they prove a text model
cannot talk the app into shipping a prompt that fails the realism standard.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRATCH))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# A suite's idea of "no key" must not depend on what is in the real .env -
# read_env() outranks os.environ, so an empty env file is what makes
# clearing a variable actually mean anything. Must be set before any tool
# is imported: generate_image reads AIVS_ENV_FILE at import time.
import tempfile as _tempfile
_EMPTY_ENV = Path(_tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

import mock_api
PORT = 8797
mock_api.serve(PORT)
BASE = "http://127.0.0.1:{}/text".format(PORT)

import ask_llm
import brief
import build_prompt as bp
import realism_lint as rl

bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake(reply, error=None):
    """An injectable stand-in for ask_llm.ask."""
    def _ask(prompt, system=None, images=(), **kw):
        return (None, error) if error else (reply, None)
    return _ask


# A known-good 8/8 prompt to start from.
GOOD, _ = bp.compose(bank, {"subject": "a woman in her thirties", "seed": 0})
assert len(rl.lint(GOOD.lower(), bank)[0]) == 8

print("=== THE GATE: upgrade_prompt ===")

r = brief.upgrade_prompt(bank, GOOD, ask=fake(GOOD + " with additional visible skin pores"))
check("valid rewrite accepted", r["accepted"], r.get("reason", ""))
check("accepted prompt is the rewrite", "additional visible skin pores" in r["prompt"])

r = brief.upgrade_prompt(bank, GOOD, ask=fake(GOOD + ", neon glow, magical light"))
check("banned term REJECTED", not r["accepted"], r.get("reason", ""))
check("original kept on reject", r["prompt"] == GOOD)
check("reason names the term", "neon glow" in r["reason"], r["reason"])
check("candidate still shown", "neon glow" in r.get("candidate", ""))

r = brief.upgrade_prompt(bank, GOOD, ask=fake("a photorealistic woman, DSLR photography"))
check("dropped layers REJECTED", not r["accepted"], r.get("reason", ""))
check("original kept", r["prompt"] == GOOD)
check("reason names the score", "/8" in r["reason"], r["reason"])

r = brief.upgrade_prompt(bank, GOOD, ask=fake(GOOD + (" more words" * 400)))
check("runaway length REJECTED", not r["accepted"], r.get("reason", "")[:60])
check("original kept", r["prompt"] == GOOD)

# A rewrite that drops every real texture word but happens to say "streetwear"
# used to score the texture layer on the bare "wear" substring and slip
# through at a fake 8/8. The layer check is anchored at both ends now, and
# "wear" is no longer a key at all.
#
# The core terms below are carried at full strength on purpose: core needs
# three distinct keys now, so a one-word "a photorealistic model" fixture would
# fail core as well and this check could no longer tell us anything about
# TEXTURE, which is the loophole it exists to guard.
present = [n for n, _, _ in rl.lint(
    "a photorealistic, ultra-realistic, lifelike model in luxury streetwear and "
    "footwear, DSLR photography, "
    "shot on an 85mm lens with shallow depth of field, soft natural daylight, "
    "rule of thirds, earthy colour grading, subtle film grain", bank)[0]]
check("'streetwear'/'footwear' do NOT satisfy the texture layer",
      "texture" not in present, str(present))
check("the other seven layers still read", len(present) == 7, str(present))
check("'imperfections' still satisfies texture (start-anchored, not exact)",
      "texture" in [n for n, _, _ in rl.lint(
          "with visible skin imperfections and open pores", bank)[0]])
check("'85mm lens' still satisfies the lens layer (multi-token substring kept)",
      "lens" in [n for n, _, _ in rl.lint("shot on an 85mm lens", bank)[0]])

r = brief.upgrade_prompt(bank, GOOD, ask=fake(None, error="OPENROUTER_API_KEY is not set"))
check("no key -> ok False", not r["ok"])
check("prompt untouched", r["prompt"] == GOOD)

r = brief.upgrade_prompt(bank, GOOD, ask=fake('"' + GOOD + ' with visible pores"'))
check("surrounding quotes stripped", r["accepted"], r.get("reason", ""))
check("no stray quote", not r["prompt"].startswith('"'))

print()
print("=== spec_from_idea hygiene ===")

good_json = json.dumps({
    "subject": "a man in his forties with a greying beard",
    "wardrobe": "a worn denim jacket", "mood": "tired",
    "extra": ["chapped lips"],
})
r = brief.spec_from_idea(bank, "a tired mechanic", ask=fake(good_json))
check("spec parsed", r["ok"] and r["spec"]["subject"].startswith("a man"))
check("lint reported", r["score"] == 8 and r["passed"], str(r.get("score")))

dirty = json.dumps({
    "subject": "a woman", "seed": 999, "reference": "/etc/passwd",
    "lock_identity": True, "overrides": {"lighting": ["x"]}, "nonsense": 1,
})
r = brief.spec_from_idea(bank, "x", ask=fake(dirty))
check("unknown keys dropped", set(r["spec"]) <= brief.SPEC_KEYS, str(sorted(r["spec"])))
for danger in ("seed", "reference", "lock_identity", "overrides"):
    check("{} not accepted from model".format(danger), danger not in r["spec"])
check("dropped keys reported", len(r["dropped"]) >= 4, str(r["dropped"]))

r = brief.spec_from_idea(bank, "x", ask=fake(json.dumps({"subject": "a woman", "shot": "bogus"})))
check("invalid shot dropped", "shot" not in r["spec"])
check("drop is reported", any("shot=" in d for d in r["dropped"]), str(r["dropped"]))

r = brief.spec_from_idea(bank, "x", ask=fake(json.dumps({"subject": "a woman", "purpose": "nope"})))
check("invalid purpose dropped", "purpose" not in r["spec"])

fenced = "Here you go:\n```json\n" + good_json + "\n```\nHope that helps!"
r = brief.spec_from_idea(bank, "x", ask=fake(fenced))
check("fenced JSON parsed", r["ok"] and "subject" in r["spec"])

r = brief.spec_from_idea(bank, "x", ask=fake("I can't do that."))
check("non-JSON -> ok False", not r["ok"])
r = brief.spec_from_idea(bank, "x", ask=fake(json.dumps({"mood": "sad"})))
check("missing subject -> ok False", not r["ok"])
r = brief.spec_from_idea(bank, "x", ask=fake(json.dumps({"subject": "a woman", "extra": "one thing"})))
check("string extra coerced to list", r["spec"]["extra"] == ["one thing"])

print()
print("=== critique_image ===")

img = ROOT / "assets" / "icons" / "compose.svg"   # any existing file
crit = json.dumps({"verdict": "Skin is too clean.",
                   "failing_layers": ["texture", "not-a-layer"],
                   "fixes": ["add visible skin pores"]})
r = brief.critique_image(bank, GOOD, str(img), ask=fake(crit))
check("critique parsed", r["ok"] and r["verdict"].startswith("Skin"))
check("unknown layer filtered", r["failing_layers"] == ["texture"], str(r["failing_layers"]))
check("fixes kept", r["fixes"] == ["add visible skin pores"])

r = brief.critique_image(bank, GOOD, str(img), ask=fake("It looks plasticky to me."))
check("non-JSON falls back to raw", r["ok"] and "plasticky" in r["verdict"])

r = brief.critique_image(bank, GOOD, "nope.png", ask=fake(crit))
check("missing image -> error", not r["ok"] and "not found" in r["error"].lower())

print()
print("=== analyze_uploaded_image hygiene ===")
# Same missing-prompt precondition critique_image can't handle - no known
# prompt, so the whitelist/recompose/relint discipline has to be enforced
# entirely on the model's read of the photo itself.

good_photo = json.dumps({
    "subject": "a woman in her late twenties with short curly hair",
    "setting": "a sunlit kitchen", "action": "pouring coffee", "mood": "calm",
    "analysis": "The lighting looks flat and even, which reads as artificial.",
})
r = brief.analyze_uploaded_image(bank, str(img), ask=fake(good_photo))
check("spec parsed", r["ok"] and r["spec"]["subject"].startswith("a woman"))
check("analysis carried through, verbatim", r["analysis"].startswith("The lighting"))
check("lint reported", r["score"] == 8 and r["passed"], str(r.get("score")))

dirty_photo = json.dumps({
    "subject": "a man", "seed": 999, "reference": "/etc/passwd",
    "lock_identity": True, "overrides": {"lighting": ["x"]}, "nonsense": 1,
    "analysis": "Looks fine.",
})
r = brief.analyze_uploaded_image(bank, str(img), ask=fake(dirty_photo))
check("unknown keys dropped", set(r["spec"]) <= brief.SPEC_KEYS, str(sorted(r["spec"])))
for danger in ("seed", "reference", "lock_identity", "overrides"):
    check("{} not accepted from model".format(danger), danger not in r["spec"])
check("dropped keys reported", len(r["dropped"]) >= 4, str(r["dropped"]))
check("analysis is not whitelist-constrained the way spec fields are",
      r["analysis"] == "Looks fine.")

r = brief.analyze_uploaded_image(
    bank, str(img), ask=fake(json.dumps({"subject": "a man", "shot": "bogus"})))
check("invalid shot dropped", "shot" not in r["spec"])
check("drop is reported", any("shot=" in d for d in r["dropped"]), str(r["dropped"]))

r = brief.analyze_uploaded_image(bank, "nope.png", ask=fake(good_photo))
check("missing image -> error, no API call needed", not r["ok"]
      and "not found" in r["error"].lower())

r = brief.analyze_uploaded_image(bank, str(img), ask=fake("I can't do that."))
check("non-JSON -> ok False", not r["ok"])

r = brief.analyze_uploaded_image(bank, str(img), ask=fake(json.dumps({"mood": "sad"})))
check("no readable subject -> ok False", not r["ok"])

print()
print("=== briefs render offline, and carry the six parts ===")
for name, builder in [("idea", brief.idea_brief), ("upgrade", brief.upgrade_brief),
                      ("critique", brief.critique_brief), ("analyze", brief.analyze_photo_brief)]:
    text = builder(bank)
    for part in ("PURPOSE", "ROLE", "STRUCTURE / FORMAT", "CONSTRAINTS"):
        check("{} brief has {}".format(name, part), part in text)
check("upgrade brief uses the dead examples",
      bank["examples"][0]["text"][:40] in brief.upgrade_brief(bank))
check("idea brief lists real shots", "talking-head" in brief.idea_brief(bank))
check("idea brief lists real purposes", "tiktok-ugc" in brief.idea_brief(bank))
check("briefs name every banned term",
      all(t in brief.upgrade_brief(bank) for t in bank["banned"]))

print()
print("=== ask_llm.py against the mock API ===")


def run(args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(ROOT / "tools" / "ask_llm.py")] + args,
                          capture_output=True, text=True, cwd=str(ROOT), env=env)

p = run(["--prompt", "hello", "--dry-run"])
check("dry-run needs no key", p.returncode == 0, p.stderr.strip()[:80])
check("redacts auth", "<redacted>" in p.stdout)

p = run(["--prompt", "hello", "--base-url", BASE], {"OPENROUTER_API_KEY": ""})
check("no key -> exit 1", p.returncode == 1, str(p.returncode))
check("names the variable", "OPENROUTER_API_KEY" in p.stderr)
check("no traceback", "Traceback" not in p.stderr)

mock_api.STATE["reply"] = "a rewritten prompt"
p = run(["--prompt", "rewrite this", "--system", "You are a cinematographer",
         "--base-url", BASE], {"OPENROUTER_API_KEY": "llm-key"})
check("happy path exit 0", p.returncode == 0, p.stderr.strip()[:120])
check("prints the reply", "a rewritten prompt" in p.stdout)
sent = mock_api.STATE["last"]
headers = {k.lower(): v for k, v in sent["headers"].items()}
check("bearer auth sent", headers.get("authorization") == "Bearer llm-key")
check("system message sent", sent["body"]["messages"][0]["role"] == "system")
check("user message sent", sent["body"]["messages"][1]["role"] == "user")
check("key never printed", "llm-key" not in p.stdout and "llm-key" not in p.stderr)

p = run(["--prompt", "look", "--image", str(img), "--base-url", BASE],
        {"OPENROUTER_API_KEY": "llm-key"})
content = mock_api.STATE["last"]["body"]["messages"][-1]["content"]
check("multimodal image attached", any(c.get("type") == "image_url" for c in content),
      str([c.get("type") for c in content]))

# --history-file - the one thing that turns a one-shot ask() into a running
# conversation (advisor.py's own multi-turn chat). Proven at the real wire
# level here, not just against a fake ask= the way test_advisor.py checks it.
history_path = ROOT / "temp" / "outputs" / "aivs-tests-history-turns.json"
history_path.parent.mkdir(parents=True, exist_ok=True)
history_path.write_text(json.dumps([
    {"role": "user", "content": "what's the lighting section for?"},
    {"role": "assistant", "content": "8 light directions and 8 named setups."},
]), encoding="utf-8")
try:
    p = run(["--prompt", "and composition?", "--system", "You are a cinematographer",
             "--history-file", str(history_path), "--base-url", BASE],
            {"OPENROUTER_API_KEY": "llm-key"})
    check("history-file call exits 0", p.returncode == 0, p.stderr.strip()[:120])
    sent_messages = mock_api.STATE["last"]["body"]["messages"]
    check("history lands between system and the new user turn",
          [m["role"] for m in sent_messages] == ["system", "user", "assistant", "user"],
          str([m["role"] for m in sent_messages]))
    check("prior user turn preserved verbatim",
          sent_messages[1]["content"] == "what's the lighting section for?")
    check("new user turn is the current prompt, not the history's",
          sent_messages[3]["content"][0]["text"] == "and composition?")
finally:
    history_path.unlink(missing_ok=True)

p = run(["--prompt", "hello", "--system", "You are a cinematographer", "--base-url", BASE],
        {"OPENROUTER_API_KEY": "llm-key"})
sent_messages = mock_api.STATE["last"]["body"]["messages"]
check("omitting --history-file reproduces today's exact shape",
      [m["role"] for m in sent_messages] == ["system", "user"],
      str([m["role"] for m in sent_messages]))

p = run(["--prompt", "x", "--base-url", BASE + "/empty"], {"OPENROUTER_API_KEY": "llm-key"})
check("empty reply -> non-zero", p.returncode != 0, str(p.returncode))
check("explains", "no text" in p.stderr.lower(), p.stderr.strip()[:80])

p = run(["--prompt", "x", "--base-url", "http://127.0.0.1:{}/boom".format(PORT)],
        {"OPENROUTER_API_KEY": "llm-key"})
check("API error -> exit 3", p.returncode == 3, str(p.returncode))
check("shows API message", "model not found" in p.stderr)
check("suggests the model var", "OPENROUTER_TEXT_MODEL" in p.stderr)

p = run(["--prompt", "x", "--base-url", "http://127.0.0.1:9"], {"OPENROUTER_API_KEY": "k"})
check("unreachable -> exit 3", p.returncode == 3, str(p.returncode))
check("no traceback", "Traceback" not in p.stderr)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL BRIEF CHECKS PASSED")
