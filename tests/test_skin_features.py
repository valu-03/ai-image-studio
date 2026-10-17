"""tools/skin_features_bank.json + build_skin_features.py + the Subject tab's chips.

Freckles used to appear in prompts nobody asked for them in - the AI helpers
were shown freckled worked examples. Skin features are opt-in now, so:

  * off (the default) composes a byte-identical prompt;
  * on, a feature reaches the prompt for a person, scaled to the shot - a tier
    the bank sets to null is left out of a wide frame;
  * never for a cat or an object, never twice when the Subject already says it;
  * every phrase is free of banned/warn terms and a spec carrying all six still
    scores 8/8 across a seed sweep;
  * nothing the AI helpers are shown mentions freckles any more, and each
    brief carries the "never add skin features" rule;
  * the Subject tab's checkboxes round-trip through spec()/load_spec(),
    because freckles are part of who a character is.

Offscreen Qt, no network.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TMP = Path(tempfile.mkdtemp(prefix="aivs-skin-"))
_EMPTY = TMP / "empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ["AIVS_HISTORY_FILE"] = str(TMP / "history.jsonl")

import advisor  # noqa: E402
import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_skin_features as bsf  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bsf.load_bank()
IMAGE_BANK = bp.load_bank()
KEYS = list(BANK["features"])

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


PERSON = {"subject": "a woman in her thirties with short dark hair", "setting": "a kitchen",
          "shot": "portrait", "seed": 3}


def text(spec):
    return bp.compose(IMAGE_BANK, spec)[0]


print("=== OFF IS BYTE-IDENTICAL ===")
plain = text(dict(PERSON))
check("an empty skin_features list changes nothing",
      text(dict(PERSON, skin_features=[])) == plain)
check("no freckles in a plain prompt", "freckl" not in plain.lower())

print()
print("=== ON, FOR A PERSON, SCALED TO THE SHOT ===")
for key in KEYS:
    for shot, tier in (("portrait", "mid"), ("environmental", "wide")):
        prompt = text(dict(PERSON, shot=shot, skin_features=[key]))
        phrase = BANK["features"][key][tier]
        if phrase:
            check("{} reaches a {} shot".format(key, tier), phrase in prompt)
        else:
            check("{} is left out of a {} shot".format(key, tier),
                  BANK["features"][key]["mid"] not in prompt
                  and BANK["features"][key]["close"] not in prompt)
close = text(dict(PERSON, shot="", shot_custom="extreme close-up beauty portrait",
                  skin_features=["freckles"]))
check("an extreme close-up gets the close freckles phrase",
      BANK["features"]["freckles"]["close"] in close)
both = bsf.compose_skin_features(BANK, ["redness", "freckles"], "a man", "portrait")[0]
check("features come out in bank order, whatever order they were ticked",
      both.index("freckles") < both.index("flush"), both)
check("unknown keys are ignored", bsf.compose_skin_features(BANK, ["tattoo"], "a man")[0] == "")

print()
print("=== PEOPLE ONLY; THE SUBJECT'S OWN WORDS WIN ===")
cat = text({"subject": "a ginger tabby cat", "seed": 1, "skin_features": KEYS})
check("a cat gets no skin features", all(BANK["features"][k]["mid"] not in cat for k in KEYS))
mug = text({"subject": "a ceramic mug on a table", "seed": 1, "skin_features": KEYS})
check("an object gets no skin features", all(BANK["features"][k]["mid"] not in mug for k in KEYS))
own = text(dict(PERSON, subject="a woman with freckles and red hair",
                skin_features=["freckles"]))
check("a Subject already saying freckles is not told twice", own.lower().count("freckl") == 1, own)
explicit = text(dict(PERSON, skin_features=["freckles"],
                     overrides={"skin_features": ["a single tiny scar"]}))
check("an explicit overrides['skin_features'] wins",
      "a single tiny scar" in explicit and BANK["features"]["freckles"]["mid"] not in explicit)

print()
print("=== THE GATE ===")
banned = [t.lower() for t in IMAGE_BANK["banned"] + IMAGE_BANK["warn"]]
for key, cfg in BANK["features"].items():
    for tier in ("close", "mid", "wide"):
        phrase = (cfg.get(tier) or "").lower()
        hits = [t for t in banned if t in phrase]
        check("{} {} has no banned/warn term".format(key, tier), not hits, str(hits))
low = []
for seed in range(40):
    for shot in ("portrait", "selfie", "environmental"):
        prompt = text(dict(PERSON, seed=seed, shot=shot, skin_features=KEYS))
        present, _missing, hit, _warn, _neg = rl.lint(prompt, IMAGE_BANK)
        if len(present) < 8 or hit:
            low.append((seed, shot, len(present)))
check("all six features on still scores 8/8 across 120 specs", not low, str(low[:3]))

print()
print("=== THE AI HELPERS ARE NOT SHOWN FRECKLES ANY MORE ===")
examples = " ".join(e["text"] for e in IMAGE_BANK["examples"]).lower()
check("no worked example mentions freckles", "freckl" not in examples)
check("no worked example mentions eye bags", "eye bags" not in examples)
for name, text in (("idea", brief.idea_brief(IMAGE_BANK)),
                   ("autofill", brief.autofill_brief(IMAGE_BANK)),
                   ("upgrade", brief.upgrade_brief(IMAGE_BANK)),
                   ("advisor", advisor.advisor_brief(IMAGE_BANK))):
    check("the {} brief carries the skin-features rule".format(name),
          brief.skin_features_rule() in text)
    stray = text.lower().replace(brief.skin_features_rule().lower(), "")
    check("the {} brief mentions freckles nowhere else".format(name), "freckl" not in stray)
check("skin_features is not model-settable", "skin_features" not in brief.SPEC_KEYS)

print()
print("=== THE SUBJECT TAB ===")
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from ui.spec_editor import SpecEditor  # noqa: E402

editor = SpecEditor(IMAGE_BANK)
editor.show()
app.processEvents()
check("one checkbox per feature, in bank order", list(editor.skin_features) == KEYS)
check("all off by default", not any(b.isChecked() for b in editor.skin_features.values()))
check("off: no skin_features key in the spec", "skin_features" not in editor.spec())
fired = []
editor.changed.connect(lambda: fired.append(1))
editor.skin_features["freckles"].setChecked(True)
check("ticking one emits changed", bool(fired))
editor.skin_features["under-eye"].setChecked(True)
check("spec() carries the ticked keys in bank order",
      editor.spec().get("skin_features") == ["freckles", "under-eye"],
      str(editor.spec().get("skin_features")))
saved = editor.spec()
editor.load_spec({"subject": "someone else"})
check("a spec without the key unticks them (character data)",
      not any(b.isChecked() for b in editor.skin_features.values()))
editor.load_spec(saved)
check("loading a saved character restores them", editor.skin_feature_keys() == ["freckles", "under-eye"])
editor.apply_partial({"wardrobe": "a grey hoodie"}, fill_blanks_only=True)
check("an auto-fill merge keeps them", editor.skin_feature_keys() == ["freckles", "under-eye"])
editor.close()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL SKIN FEATURE CHECKS PASSED")
