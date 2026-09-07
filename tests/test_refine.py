"""refine_image.py - the automatic critique-and-retry loop.

Closes the manual loop the app has always required: generate -> notice it's
off -> figure out which realism layer is weak -> re-prompt by hand.
brief.critique_image() already does the "what's wrong" step (tested in
test_brief.py, including its own whitelist against the 8 layer names); this
suite is about what refine_image.py does WITH that critique - strengthen
exactly the flagged layer using only the bank's own vocabulary, stop early on
a clean critique, and never exceed the retry cap. Real image generation goes
through mock_api, same as test_upscale.py; the critique step is injected
directly (ask=), the same pattern test_brief.py uses for brief.py itself -
there is no vision-model mock server, and none is needed since critique_image
already accepts an injectable `ask`.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

# Must be set before generate_image (imported by mock_api/refine_image) reads
# it - the same isolation seam every generate-path suite uses.
_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-refine-empty.env"
_EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)
os.environ["KIE_API_KEY"] = "kie-key"

_HISTORY_FILE = Path(tempfile.gettempdir()) / "aivs-refine-history.jsonl"
if _HISTORY_FILE.exists():
    _HISTORY_FILE.unlink()
os.environ["AIVS_HISTORY_FILE"] = str(_HISTORY_FILE)

import mock_api

PORT = 8801
mock_api.serve(PORT)
BASE = "http://127.0.0.1:{}".format(PORT)

import build_prompt as bp
import history
import realism_lint as rl
import refine_image as ri

bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake(*replies):
    """An injectable stand-in for ask_llm.ask - one reply per call, cycling
    the last one if called more times than replies given."""
    calls = {"n": 0}

    def _ask(prompt, system=None, images=(), **kw):
        i = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        return replies[i], None
    return _ask


import json as _json


def crit(failing=(), verdict="Looks real."):
    return _json.dumps({"verdict": verdict, "failing_layers": list(failing), "fixes": []})


SPEC = {"subject": "a woman in her thirties", "seed": 0}


def reset():
    mock_api.reset()


print("=== strengthen(): bank-only, and respects pick=1 exclusivity ===")
prompt, selected = bp.compose(bank, SPEC)

# texture is pick=3 - stacking one more already-vetted term is safe.
stronger = ri.strengthen(bank, selected, "texture")
check("texture: still only bank terms",
      all(t in bank["layers"]["texture"]["terms"] for t in stronger), str(stronger))
check("texture: grew by exactly one over what was already picked",
      len(stronger) == len(selected["texture"]) + 1, str(stronger))

# lighting is pick=1 - the note explicitly warns against mixing sources, so
# strengthening must SWAP, never stack.
stronger = ri.strengthen(bank, selected, "lighting")
check("lighting: exactly one term (no stacked sources)", len(stronger) == 1, str(stronger))
check("lighting: still a bank term", stronger[0] in bank["layers"]["lighting"]["terms"])
check("lighting: a DIFFERENT term than what was already picked",
      stronger[0] not in selected["lighting"], str((stronger, selected["lighting"])))

check("unknown layer -> None, not a crash", ri.strengthen(bank, selected, "not-a-layer") is None)

print()
print("=== a clean critique stops after ONE generation ===")
reset()
result = ri.refine(bank, dict(SPEC), provider="kie", base=BASE, max_retries=2,
                    ask=fake(crit(failing=())))
check("ok", result["ok"], result.get("error", ""))
check("stopped after exactly 1 attempt", len(result["attempts"]) == 1, str(len(result["attempts"])))
check("no failing layers on the one attempt",
      result["attempts"][0]["critique"]["failing_layers"] == [])
check("every attempt logged through history.append",
      len(history.load()) >= 1)

print()
print("=== a persistently weak layer retries up to the cap, never past it ===")
reset()
before = len(history.load())
result = ri.refine(bank, dict(SPEC), provider="kie", base=BASE, max_retries=2,
                    ask=fake(crit(failing=["texture"])))
check("ok", result["ok"], result.get("error", ""))
check("exactly max_retries+1 attempts, not more", len(result["attempts"]) == 3,
      str(len(result["attempts"])))
check("every attempt still flagged the same weak layer (fake never clears)",
      all(a["critique"]["failing_layers"] == ["texture"] for a in result["attempts"]))
check("three more generations were logged",
      len(history.load()) == before + 3, str(len(history.load()) - before))
check("logged entries are tagged as refine-loop attempts, traceable",
      all("refine-loop" in e.get("note", "") for e in history.load()[-3:]))

print()
print("=== the flagged layer is actually strengthened for the next round ===")
reset()
seen_overrides = []
real_compose = bp.compose


def spying_compose(bank_, spec_, *a, **kw):
    seen_overrides.append(dict(spec_.get("overrides", {})))
    return real_compose(bank_, spec_, *a, **kw)


bp.compose = spying_compose
try:
    ri.refine(bank, dict(SPEC), provider="kie", base=BASE, max_retries=1,
              ask=fake(crit(failing=["lighting"])))
finally:
    bp.compose = real_compose

check("round 0 had no override yet", seen_overrides[0] == {}, str(seen_overrides[0]))
check("round 1 carries a lighting override, and only that layer",
      list(seen_overrides[1]) == ["lighting"], str(seen_overrides[1]))
check("the override is a real bank term, not invented text",
      seen_overrides[1]["lighting"][0] in bank["layers"]["lighting"]["terms"],
      str(seen_overrides[1]))

print()
print("=== a critique failure (no key, bad call) stops cleanly, not with a crash ===")
reset()
result = ri.refine(bank, dict(SPEC), provider="kie", base=BASE, max_retries=2,
                    ask=lambda *a, **k: (None, "OPENROUTER_API_KEY is not set"))
check("ok (a missing key is not a generation failure)", result["ok"], result.get("error", ""))
check("stopped after the one generation that DID happen", len(result["attempts"]) == 1,
      str(len(result["attempts"])))
check("critique is None, the error is carried instead",
      result["attempts"][0]["critique"] is None
      and "OPENROUTER_API_KEY" in result["attempts"][0]["critique_error"])

print()
print("=== a real generation failure is reported, not silently swallowed ===")
reset()
result = ri.refine(bank, dict(SPEC), provider="kie", base=BASE + "/boom", max_retries=2,
                    ask=fake(crit(failing=())))
check("ok is False", not result["ok"])
check("error is carried", bool(result.get("error")))

print()
print("=== dry-run never calls the critique step, never needs a key ===")
reset()
result = ri.refine(bank, dict(SPEC), provider="kie", base=BASE, max_retries=2,
                    dry_run=True, ask=lambda *a, **k: (_ for _ in ()).throw(
                        AssertionError("critique must not be called in dry-run")))
check("ok", result["ok"], result.get("error", ""))
check("exactly one attempt, no retries in dry-run", len(result["attempts"]) == 1)
check("no critique on a dry-run attempt", result["attempts"][0]["critique"] is None)

print()
print("=== start_image/start_prompt: critiquing an already-shown image costs no generation ===")
reset()
existing_prompt, existing_selected = bp.compose(bank, dict(SPEC, seed=7))
present, _, banned, _, _ = rl.lint(existing_prompt.lower(), bank)
result = ri.refine(
    bank, dict(SPEC, seed=7), provider="kie", base=BASE, max_retries=1,
    ask=fake(crit(failing=())),
    start_image="temp/outputs/images/already-shown.png",
    start_prompt=existing_prompt, start_selected=existing_selected,
)
check("ok", result["ok"], result.get("error", ""))
check("round 0 reused the given image, not a fresh generation",
      result["attempts"][0]["image"] == "temp/outputs/images/already-shown.png",
      str(result["attempts"][0]["image"]))
check("still only one attempt - the critique came back clean", len(result["attempts"]) == 1)
check("no mock request was ever sent for round 0",
      mock_api.STATE["last"] is None, str(mock_api.STATE["last"]))

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL REFINE-LOOP CHECKS PASSED")

try:
    _HISTORY_FILE.unlink()
except OSError:
    pass

sys.exit(1 if fails else 0)
