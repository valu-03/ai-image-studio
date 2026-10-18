"""What a person types - or a model replies - always composes a clean prompt.

Found by typing hostile input into every field of every section:

  * a field ending in a comma or full stop composed to "red., in a kitchen" or
    "kitchen, , street photography" - every field is comma-joined;
  * a `null`, a number or a list where text belongs crashed compose(), and a
    model reply carries exactly that: the key whitelist never checked types;
  * a camera lead ending in "of" was followed by a comma in the tagged video
    template - "low-angle cinematic shot of, close-up, a cat";
  * the Cats premise went into titles raw - "A woman,... STOP ACTING".

Only the EDGES of a value are tidied; the words inside are never changed, and
an intended "..." survives. No network, no Qt.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

TMP = Path(tempfile.mkdtemp(prefix="aivs-hygiene-"))
(TMP / "empty.env").write_text("#\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(TMP / "empty.env")
os.environ["AIVS_HISTORY_FILE"] = str(TMP / "history.jsonl")

import advisor  # noqa: E402
import brief  # noqa: E402
import build_motion as bm  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_social as bs  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def text(spec, detailed=False):
    return bp.compose(BANK, spec, detailed=detailed)[0]


BASE = {"subject": "a woman in her thirties", "setting": "a kitchen", "seed": 1}

print("=== clean_text: edges only ===")
for raw, want in (("a woman in red.", "a woman in red"), ("in a kitchen,", "in a kitchen"),
                  ("calm;", "calm"), (" , leading", "leading"), ("wait...", "wait..."),
                  ("a, b. ", "a, b"), ("line one\nline two", "line one line two"),
                  (",,, .", ""), ("   ", ""), (None, ""), (5, "5"), (["x"], ""), (True, "")):
    got = bp.clean_text(raw)
    check("{!r} -> {!r}".format(raw, want), got == want, repr(got))

print()
print("=== ordinary input is byte-identical ===")
for spec in (dict(BASE), dict(BASE, wardrobe="a grey hoodie", action="reading", mood="calm",
                              extra=["a loose thread at the cuff"], shot="portrait")):
    check("clean_spec leaves a tidy spec alone", bp.clean_spec(spec) == spec)

print()
print("=== a trailing comma or full stop never doubles punctuation ===")
for key in ("subject", "wardrobe", "setting", "action", "posing", "mood", "shot_custom",
            "composition_guide_custom"):
    for tail in (",", ".", " , ", ";"):
        spec = dict(BASE, **{key: "something here" + tail})
        for detailed in (False, True):
            prompt = text(spec, detailed)
            bad = [m for m in (", ,", ",,", "., ", ",.") if m in prompt]
            check("{} ending {!r} ({})".format(key, tail, "detailed" if detailed else "compact"),
                  not bad, str(bad))
typed = text(dict(BASE, overrides={"lighting": ["soft lamp light,", "realistic shadows"],
                                   "colour": "warm tones."}))
check("typed Lighting / Colour text ending in punctuation stays clean",
      not any(m in typed for m in (",,", ", ,", "., ")), typed)
check("blank Extra lines leave no empty commas",
      ",  ," not in text(dict(BASE, extra=["   ", "", "real line"])))
check("an empty subject falls back to 'a person'",
      "details of a person" in text(dict(BASE, subject="")) or
      "of a person" in text(dict(BASE, subject="")))

print()
print("=== wrong types never crash compose() ===")
for key in ("subject", "wardrobe", "setting", "action", "posing", "mood", "shot", "purpose",
            "aspect", "extra", "composition_guide", "seed", "skin_features"):
    for value in (None, 5, ["a", "list"], {"a": 1}, True):
        try:
            prompt = text(dict(BASE, **{key: value}))
            ok = bool(prompt) and "None" not in prompt
        except Exception as exc:  # noqa: BLE001
            ok = False
            prompt = "{}: {}".format(type(exc).__name__, exc)
        check("{} = {!r}".format(key, value), ok, prompt[:80] if not ok else "")
check("a single string for extra becomes one line",
      "one extra line" in text(dict(BASE, extra="one extra line")))

print()
print("=== a model reply with bad types is cleaned before anything uses it ===")
reply = json.dumps({"subject": "a nurse in her forties,", "wardrobe": None, "setting": 7,
                    "action": ["not", "text"], "extra": "one line.", "shot": ["portrait"],
                    "purpose": {"x": 1}, "mood": "tired."})
for name, call in (("autofill", lambda ask: brief.autofill_spec(BANK, {}, ask=ask)),
                   ("idea", lambda ask: brief.spec_from_idea(BANK, "a nurse", ask=ask))):
    try:
        result = call(lambda *a, **k: (reply, None))
        spec = result.get("spec") or {}
        ok = (result.get("ok") is not False and spec.get("subject") == "a nurse in her forties"
              and "wardrobe" not in spec and spec.get("extra") == ["one line"]
              and "shot" not in spec and "purpose" not in spec)
        check("{} cleans and drops the bad values".format(name), ok, json.dumps(result)[:200])
    except Exception as exc:  # noqa: BLE001
        check("{} cleans and drops the bad values".format(name), False,
              "{}: {}".format(type(exc).__name__, exc))
try:
    out = advisor._finalize_spec(BANK, json.loads(reply))
    check("the advisor's spec block is cleaned the same way",
          (out or {}).get("spec", {}).get("subject") == "a nurse in her forties", str(out)[:200])
except Exception as exc:  # noqa: BLE001
    check("the advisor's spec block is cleaned the same way", False,
          "{}: {}".format(type(exc).__name__, exc))

print()
print("=== video prompts: a lead ending in 'of' takes its object, not a comma ===")
MB = bm.load_bank()
leads = {k: m["lead"] for k, m in MB["movements"].items()}
tagged = bm.assemble_template(MB, "close-up", "a ginger cat,", "jumps.", leads["low-angle"],
                              "shot on a DSLR", negatives=False)
check("tagged template: 'shot of a ginger cat'", tagged.startswith(leads["low-angle"] + " a ginger cat"),
      tagged)
check("tagged template: no ' of,' anywhere", " of," not in tagged, tagged)
check("tagged template still leads with the camera", tagged.startswith("low-angle"))
alone = bm.compose(MB, "low-angle", {})[0]
check("a lead with nothing to name gets 'the scene'", " of," not in alone and "of the scene" in alone,
      alone[:80])
for key, lead in leads.items():
    prompt = bm.assemble_template(MB, "medium shot", "a woman", "", lead, "", negatives=False)
    if bm.CONNECTOR_END.search(lead):
        check("{}: subject follows the lead with a space".format(key),
              prompt.startswith(lead + " a woman"), prompt[:80])
prefilled = ", ".join((leads["low-angle"], MB["movements"]["low-angle"]["detail"]))
tagged = bm.assemble_template(MB, "close-up", "a cat", "", prefilled, "", negatives=False)
check("the prefilled 'lead, detail' camera field takes the subject after the lead",
      tagged.startswith(leads["low-angle"] + " a cat, ") and " of," not in tagged, tagged[:90])
story = bm.assemble_story(MB, "low-angle", "a cat,", ["jumps up.", "lands,"], end_state="asleep.")
check("story mode: no doubled punctuation", not any(m in story for m in (",.", "..", ",,")), story)

print()
print("=== Cats titles and caption ===")
SB = bs.load_bank()
titles = bs.compose_titles(SB, "a cat steals the ham, ")
check("no comma before '...' in a title", not any(",." in t or ", ." in t for t in titles), str(titles))
caption = bs.compose_caption(SB, "a cat steals the ham,")
check("no ',.' in the caption", ",." not in caption, caption)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL INPUT HYGIENE CHECKS PASSED")
