"""tools/giveaways.py: the picture-reading check, with a fake vision model.

No network: every call injects a fake `ask`. The claims worth defending: only
keys the bank names are ever trusted, a reply that isn't a JSON object is an
error (never a pass, never a crash), a missing key passes straight through,
and the prompt only asks about giveaways that apply to the subject kind.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import giveaways as gv  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake_ask(reply_text, error=None):
    def ask(prompt, system=None, images=(), model=None, base=None,
            max_tokens=2048, history=()):
        ask.last_prompt = prompt
        ask.last_images = list(images)
        return reply_text, error
    return ask


print("=== SEEN KEYS COME BACK IN BANK ORDER ===")
reply = json.dumps({
    "too_clean": {"seen": True, "where": "on the back"},
    "posed_centre": {"seen": True, "where": "middle of the frame"},
    "studio_light": {"seen": False, "where": ""},
})
found, error = gv.check("img.png", "animal", ask=fake_ask(reply))
check("no error", error is None, str(error))
check("keys follow bank order", [g["key"] for g in found] == ["posed_centre", "too_clean"],
      str([g["key"] for g in found or []]))
first = found[0]
check("carries where", first["where"] == "middle of the frame")
check("carries plain copy", bool(first["plain"]) and bool(first["label"]))
check("fixable is true when the bank has a fix", first["fixable"] is True)

print()
print("=== UNKNOWN KEYS ARE IGNORED ===")
found, error = gv.check("img.png", "animal",
                        ask=fake_ask(json.dumps({"looks_ai": {"seen": True}})))
check("empty list, no error", found == [] and error is None, str((found, error)))

print()
print("=== NON-JSON IS AN ERROR, NOT A PASS ===")
msg = "The picture check didn't answer in a form we can read."
check("prose reply", gv.check("img.png", "animal", ask=fake_ask("looks great!")) == (None, msg))
check("JSON list reply", gv.check("img.png", "animal", ask=fake_ask("[1, 2]")) == (None, msg))

print()
print("=== THE PROMPT NAMES ONLY THE KIND'S KEYS ===")
human = gv.build_prompt("human", False)
check("human prompt has bad_text and anatomy", "bad_text" in human and "anatomy" in human)
check("human prompt has no animal-only wording", not re.search(r"\bfur\b", human.lower()))
check("animal prompt does mention fur", bool(re.search(r"\bfur\b", gv.build_prompt("animal", False).lower())))
bank = gv.load_bank()["giveaways"]
for kind in ("animal", "human", "object", "place"):
    p = gv.build_prompt(kind, False)
    for key, g in bank.items():
        check("{} prompt {} {}".format(kind, "has" if kind in g["kinds"] else "omits", key),
              (key in p) == (kind in g["kinds"]))
check("reference wording only with a reference",
      "SECOND" not in gv.build_prompt("human", False) and "SECOND" in gv.build_prompt("human", True))

print()
print("=== A MISSING KEY PASSES THROUGH ===")
res = gv.check("img.png", "animal", ask=fake_ask(None, "OPENROUTER_API_KEY not set"))
check("error passes through", res == (None, "OPENROUTER_API_KEY not set"), str(res))

print()
print("=== EVERY GIVEAWAY HAS PLAIN COPY ===")
check("eight keys in order", list(bank) == [
    "posed_centre", "too_clean", "generic_room", "painted_mess",
    "studio_light", "anatomy", "artefacts", "bad_text"])
for key, g in bank.items():
    check(key + " has label, plain, example",
          all(str(g.get(f, "")).strip() for f in ("label", "plain", "example")))
    check(key + " kinds valid", g["kinds"] and set(g["kinds"]) <= {"animal", "human", "object", "place"})
    check(key + " fix is empty or has a fix_phrase",
          (not g["fix"]) or bool(g["fix_phrase"].strip()))
    check(key + " fix cards valid",
          set(g["fix"]) <= {"light", "camera", "framing", "colour", "pose", "details"})

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL GIVEAWAYS CHECKS PASSED")
