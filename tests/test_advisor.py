"""tools/advisor.py - the one AI feature in this project that is a running
conversation rather than a one-shot brief. Two things matter most here: that
`advisor_brief()` actually names every section/bank this app has (an "expert"
that has silently lost a bank is worse than no expert at all), and that the
same validation gate every other AI-suggestion path uses (brief.py's whitelist
+ recompose + relint) still holds for whatever the chat proposes - a spec
arriving inside a conversation is not exempt from it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "advisor.py"
sys.path.insert(0, str(ROOT / "tools"))

# A suite's idea of "no key" must not depend on what is in the real .env -
# read_env() outranks os.environ, so an empty env file is what makes clearing
# a variable actually mean anything, here and in every subprocess call below.
# Must be set before any tool is imported: generate_image reads AIVS_ENV_FILE
# at import time. Same guard test_brief.py's own ask_llm section already uses.
import tempfile as _tempfile
_EMPTY_ENV = Path(_tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

import advisor as adv  # noqa: E402
import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake(reply, error=None, capture=None):
    """An injectable stand-in for ask_llm.ask - the same shape test_brief.py's
    own fake() already uses, extended with an optional `capture` dict so a
    test can inspect exactly what was sent (history, images) for this call."""
    def _ask(prompt, system=None, images=(), history=(), **kw):
        if capture is not None:
            capture["prompt"] = prompt
            capture["system"] = system
            capture["images"] = list(images)
            capture["history"] = list(history)
        return (None, error) if error else (reply, None)
    return _ask


bank = bp.load_bank()
GOOD, _ = bp.compose(bank, {"subject": "a woman in her thirties", "seed": 0})
assert len(rl.lint(GOOD.lower(), bank)[0]) == 8


print("=== advisor_brief() names the whole app ===")

text = adv.advisor_brief(bank)
for part in ("PURPOSE", "ROLE", "STRUCTURE / FORMAT", "CONSTRAINTS", "STYLE / TONE"):
    check("brief has " + part, part in text)
for layer in bp.LAYER_ORDER:
    check("names realism layer '{}'".format(layer), layer in text)

import build_camera_angle as bca  # noqa: E402
import build_color as bcol  # noqa: E402
import build_composition as bc  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_posing as bpo  # noqa: E402

lb = bl.load_bank()
cb = bc.load_bank()
colb = bcol.load_bank()
pb = bpo.load_bank()
cab = bca.load_bank()

checks = [
    ("a lighting setup", next(iter(bl.setups(lb).values()))["label"]),
    ("a lighting technique", next(iter(bl.techniques(lb).values()))["label"]),
    ("a composition technique", next(iter(bc.techniques(cb).values()))["label"]),
    ("a colour mood", next(iter(bcol.moods(colb).values()))["label"]),
    ("a colour film look", next(iter(bcol.film_looks(colb).values()))["label"]),
    ("a pose", next(iter(bpo.poses(pb).values()))["label"]),
    ("a camera-angle vertical", next(iter(bca.verticals(cab).values()))["label"]),
]
for label, needle in checks:
    check("mentions {} ({})".format(label, needle), needle in text, needle)

check("names every nav section", all(name in text for name, _ in adv.NAV_MAP))
check("names every banned term", all(t in text for t in bank["banned"]))
check("names the composition guides", all(
    cfg["label"] in text for cfg in bp.guides(bank).values()))


print()
print("=== extract_spec_block() ===")

good_json = '{"subject": "a woman in her thirties"}'

check("clean fence", adv.extract_spec_block(
    "```spec\n" + good_json + "\n```") == {"subject": "a woman in her thirties"})
check("fence with surrounding prose", adv.extract_spec_block(
    "Sure, here's a spec:\n```spec\n" + good_json + "\n```\nHope that helps!"
) == {"subject": "a woman in her thirties"})
check("no fence at all -> None", adv.extract_spec_block(
    "Open the Lighting section and try clam-shell.") is None)
check("empty text -> None", adv.extract_spec_block("") is None)
check("truncated fence (no closing) -> None", adv.extract_spec_block(
    "```spec\n" + good_json) is None)
check("malformed JSON inside fence -> None", adv.extract_spec_block(
    "```spec\nnot json at all\n```") is None)
check("fenced array, not an object -> None", adv.extract_spec_block(
    "```spec\n[1, 2, 3]\n```") is None)
check("a plain ```json fence (not ```spec) -> None", adv.extract_spec_block(
    "```json\n" + good_json + "\n```") is None)


print()
print("=== the whitelist holds inside a chat reply too ===")

dirty = json.dumps({
    "subject": "a woman", "seed": 999, "reference": "/etc/passwd",
    "lock_identity": True, "overrides": {"lighting": ["x"]}, "nonsense": 1,
})
r = adv.chat(bank, [], "x", ask=fake("```spec\n" + dirty + "\n```"))
check("call ok", r["ok"])
check("suggestion produced", r["suggestion"] is not None)
suggestion = r["suggestion"] or {}
check("unknown keys dropped", set(suggestion.get("spec", {})) <= brief.SPEC_KEYS,
      str(sorted(suggestion.get("spec", {}))))
for danger in ("seed", "reference", "lock_identity", "overrides"):
    check("{} not accepted from a chat spec block".format(danger),
          danger not in suggestion.get("spec", {}))
check("dropped keys reported", len(suggestion.get("dropped", [])) >= 4,
      str(suggestion.get("dropped")))

r = adv.chat(bank, [], "x", ask=fake(
    "```spec\n" + json.dumps({"subject": "a woman", "shot": "bogus"}) + "\n```"))
check("invalid shot dropped", "shot" not in r["suggestion"]["spec"])
check("drop is reported", any("shot=" in d for d in r["suggestion"]["dropped"]),
      str(r["suggestion"]["dropped"]))

r = adv.chat(bank, [], "x", ask=fake(
    "```spec\n" + json.dumps({"mood": "sad"}) + "\n```"))
check("no subject -> suggestion is None, reply still returned",
      r["ok"] and r["suggestion"] is None and r["reply"])


print()
print("=== a plain conversational reply has nothing to apply ===")

r = adv.chat(bank, [], "how do I make my photos look better?",
            ask=fake("What kind of shot are you going for?"))
check("ok", r["ok"])
check("no suggestion from a plain reply", r["suggestion"] is None)
check("reply text passed through", "What kind of shot" in r["reply"])

r = adv.chat(bank, [], "", ask=fake("anything"))
check("empty message -> ok False, no API call", not r["ok"])


print()
print("=== a golden end-to-end spec scores for real ===")

golden = json.dumps({
    "subject": "a man in his forties with a greying beard", "shot": "portrait",
    "wardrobe": "a worn denim jacket", "mood": "tired", "extra": ["chapped lips"],
})
r = adv.chat(bank, [], "build me a spec", ask=fake(
    "Here's a starting point.\n```spec\n" + golden + "\n```"))
check("golden spec parsed", r["suggestion"] is not None)
check("golden spec scores 8/8", r["suggestion"]["score"] == 8 and r["suggestion"]["passed"],
      str(r["suggestion"].get("score")))
check("no banned terms", not r["suggestion"]["banned"])


print()
print("=== chat() actually threads a multi-turn history ===")

prior = [{"role": "user", "content": "what's the lighting section for?"},
        {"role": "assistant", "content": "8 light directions and 8 named setups."}]
cap = {}
r = adv.chat(bank, prior, "and what about composition?", ask=fake("7 framing geometries.", capture=cap))
check("call ok", r["ok"])
check("history forwarded in order", cap["history"] == prior, str(cap["history"]))
check("history is a list, not the original tuple/reference mutated",
      cap["history"] is not prior)

r2 = adv.chat(bank, [], "hello", ask=fake("hi", capture=cap))
check("omitting history sends nothing prior", cap["history"] == [])


print()
print("=== an attached image is scoped to its own turn ===")

img = ROOT / "assets" / "icons" / "compose.svg"   # any existing file
cap = {}
r = adv.chat(bank, [], "why doesn't this look real", image_path=str(img),
            ask=fake("The lighting looks flat.", capture=cap))
check("image threaded through to this turn", cap["images"] == [str(img)])

cap2 = {}
r2 = adv.chat(bank, [], "and now?", ask=fake("Still looks flat.", capture=cap2))
check("a later turn with no image sends none", cap2["images"] == [])


print()
print("=== the context note is real-scored, never guessed ===")

cap = {}
adv.chat(bank, [], "how's my prompt?", context_prompt=GOOD, ask=fake("looks solid", capture=cap))
check("full 8/8 prompt is reported as such", "scores 8/8" in cap["prompt"], cap["prompt"][:120])

partial = "a photorealistic woman, DSLR photography"
present, _, _, _, _ = rl.lint(partial.lower(), bank)
cap2 = {}
adv.chat(bank, [], "how's my prompt?", context_prompt=partial, ask=fake("needs work", capture=cap2))
check("partial prompt reports its real score",
      "scores {}/8".format(len(present)) in cap2["prompt"], cap2["prompt"][:160])
check("missing layers are named", "missing:" in cap2["prompt"], cap2["prompt"][:160])

cap3 = {}
adv.chat(bank, [], "hello", ask=fake("hi", capture=cap3))
check("no context prompt -> no note prepended", cap3["prompt"] == "hello")


print()
print("=== sections: every technique section the reply proposes ===")

ALL_SECTIONS = {
    "lighting": {"setup": "old-hollywood"},
    "composition": {"guide": "rule-of-thirds", "techniques": ["lead-room"]},
    "color": {"mood": "melancholy-lonely"},
    "posing": {"pose": "forward-lean", "techniques": ["relaxed-hands"]},
    "camera_angle": {"vertical": "eye-level", "side": "three-quarter",
                     "size": "medium-close-up"},
}


def sections_for(block, spec=None):
    return adv._finalize_sections(bank, {"sections": block}, spec)


got = sections_for(ALL_SECTIONS)
check("all five sections compose", sorted(got) == sorted(ALL_SECTIONS), str(sorted(got)))
for name in ALL_SECTIONS:
    check("{} produced a non-empty phrase".format(name), bool(got.get(name, "").strip()))

# Composed by the section's OWN composer, never re-worded here - so the phrase
# must be byte-identical to what that section's Apply to Compose would produce.
expected_posing, _ = bpo.compose_posing(
    pb, pose="forward-lean", techniques_=["relaxed-hands"])
check("posing phrase is exactly build_posing's own output",
      got["posing"] == expected_posing, got["posing"][:60])
expected_lighting, _ = bl.compose_lighting(lb, setup="old-hollywood")
check("lighting phrase is exactly build_lighting's own output",
      got["lighting"] == expected_lighting, got["lighting"][:60])

check("an all-invalid section is dropped, not raised",
      sections_for({"lighting": {"setup": "not-a-real-setup"}}) == {})
check("an invalid technique is dropped but a valid pose still composes",
      "posing" in sections_for({"posing": {"pose": "s-curve", "techniques": ["bogus"]}}))
check("an unknown section name is ignored",
      sorted(sections_for({"bogus": {"x": 1}, "posing": {"pose": "s-curve"}})) == ["posing"])
check("a non-dict section block is ignored", sections_for({"lighting": "clam-shell"}) == {})
check("an empty section block is ignored", sections_for({"lighting": {}}) == {})
check("a non-dict sections value is ignored",
      adv._finalize_sections(bank, {"sections": "nope"}) == {})
check("no sections key at all", adv._finalize_sections(bank, {"subject": "x"}) == {})
bare_string_result = sections_for(
    {"posing": {"pose": "s-curve", "techniques": "relaxed-hands"}})
check("a technique given as a bare string (not a list) still resolves",
      "relaxed" in bare_string_result.get("posing", ""), str(bare_string_result))
check("a partial camera-angle subset composes",
      "camera_angle" in sections_for({"camera_angle": {"size": "close-up"}}))

# Both composers refuse their two shapes together; an over-specified reply
# should still yield a usable suggestion rather than losing the whole section.
check("setup wins over deep-path fields rather than dropping lighting",
      sections_for({"lighting": {"setup": "clam-shell", "direction": "rembrandt"}}).get(
          "lighting", "").startswith("clam shell"))
check("mood wins over film_look rather than dropping colour",
      bool(sections_for({"color": {"mood": "epic-heroic", "film_look": "dune"}}).get("color")))

print()
print("=== sections: the shot/camera_angle conflict is settled, not silently paid for ===")

check("camera_angle is dropped when the core spec carries a shot preset",
      "camera_angle" not in sections_for(ALL_SECTIONS, {"shot": "portrait"}))
check("the other four sections survive that drop",
      sorted(sections_for(ALL_SECTIONS, {"shot": "portrait"}))
      == ["color", "composition", "lighting", "posing"])
check("camera_angle applies when there is no shot preset",
      "camera_angle" in sections_for(ALL_SECTIONS, {"subject": "a nurse"}))

# The whole point of the tie-break: a full autofill with a preset shot still
# scores 8/8 rather than losing the camera layer to a bare angle phrase.
full = dict({"subject": "a nurse in her forties, dark circles under her eyes",
             "wardrobe": "wrinkled blue scrubs", "shot": "portrait"},
            sections=ALL_SECTIONS)
r = adv.chat(bank, [], "build it", ask=fake("done\n```spec\n" + json.dumps(full) + "\n```"))
check("a full autofill still scores 8/8", r["suggestion"]["score"] == 8,
      str(r["suggestion"]["score"]))
check("chat() returns the sections dict", sorted(r["sections"])
      == ["color", "composition", "lighting", "posing"], str(sorted(r["sections"])))
check("'sections' is never reported as a dropped spec key",
      "sections" not in r["suggestion"]["dropped"], str(r["suggestion"]["dropped"]))

r = adv.chat(bank, [], "hi", ask=fake("just chatting, no block here"))
check("no fenced block -> sections is an empty dict, not missing", r["sections"] == {})

print()
print("=== sections: the brief teaches the real keys, not just the labels ===")

brief_text = adv.advisor_brief(bank)
check("the schema is documented", "\"sections\"" in brief_text)
for key in ("old-hollywood", "rule-of-thirds", "melancholy-lonely", "forward-lean",
            "medium-close-up"):
    check("brief names the real key '{}'".format(key), key in brief_text)
check("brief warns that shot and camera_angle collide",
      "same field" in brief_text and "camera_angle" in brief_text)

print()
print("=== CLI parity ===")

p = subprocess.run([sys.executable, str(TOOL), "show"], capture_output=True, text=True, cwd=str(ROOT))
check("show exits 0", p.returncode == 0, p.stderr.strip()[:120])
check("show names all 8 layers", all(layer in p.stdout for layer in bp.LAYER_ORDER))

p = subprocess.run(
    [sys.executable, str(TOOL), "chat", "hello", "--dry-run"],
    capture_output=True, text=True, cwd=str(ROOT))
check("dry-run needs no key", p.returncode == 0, p.stderr.strip()[:120])
check("dry-run reports zero prior turns", "history: 0 prior turn(s)" in p.stdout)

history_file = HERE / "aivs-tests-advisor-history.json"
history_file.write_text(json.dumps([
    {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
]), encoding="utf-8")
try:
    p = subprocess.run(
        [sys.executable, str(TOOL), "chat", "and then?", "--history-file",
         str(history_file), "--dry-run"],
        capture_output=True, text=True, cwd=str(ROOT))
    check("history-file dry-run exits 0", p.returncode == 0, p.stderr.strip()[:120])
    check("history-file threads 2 prior turns", "history: 2 prior turn(s)" in p.stdout, p.stdout)
finally:
    history_file.unlink(missing_ok=True)

env = dict(os.environ)
env["OPENROUTER_API_KEY"] = ""
p = subprocess.run(
    [sys.executable, str(TOOL), "chat", "hello"],
    capture_output=True, text=True, cwd=str(ROOT), env=env)
check("no key -> non-zero exit, no traceback", p.returncode != 0 and "Traceback" not in p.stderr)
check("names the variable", "OPENROUTER_API_KEY" in p.stderr, p.stderr.strip()[:120])


print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL ADVISOR CHECKS PASSED")
