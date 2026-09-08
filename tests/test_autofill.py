"""Custom shot, custom composition, and the one-press auto-fill.

Three claims are load-bearing here and each gets an explicit assertion:

  1. A custom *composition* can never cost the prompt its composition layer.
     It pins slot 0 and a bank term still fills slot 1, so whatever is typed,
     the layer scores. This is what makes free text safe there.
  2. A custom *shot* replaces the camera slot, so it CAN drop the camera layer
     when it names no capture device - and that is correct behaviour, reported
     by the gate rather than hidden.
  3. Auto-fill never overwrites a field the user has filled, and never applies a
     composition guide or a lighting source on its own.

Standard library plus PyQt6. The model is always a stand-in; no network.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

bank = bp.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def fake(reply, error=None):
    def _ask(prompt, system=None, images=(), **kw):
        return (None, error) if error else (reply, None)
    return _ask


def score(spec):
    prompt, layers = bp.compose(bank, spec)
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    return prompt, layers, len(present), banned


BASE = {"subject": "a woman tanning on a tropical beach", "seed": 7}

# --------------------------------------------------------------------------- #
print("=== CUSTOM COMPOSITION: pinned, never destructive ===")
CUSTOM = "framed to include a clear sky, bright blue water and a woven beach bag behind her"
prompt, layers, got, banned = score(dict(BASE, composition_guide_custom=CUSTOM))
check("the typed text reaches the prompt", CUSTOM in prompt)
check("it takes the first slot", layers["composition"][0] == CUSTOM,
      layers["composition"][0])
check("the bank still fills the rest", len(layers["composition"]) == 2,
      str(layers["composition"]))
check("a bank term survives", layers["composition"][1] in bank["layers"]["composition"]["terms"],
      layers["composition"][1])
check("still 8/8", got == 8, "{}/8".format(got))

# The claim in full: nothing you can type here costs you the layer.
worst = ["", "x", "!!!", "aaaa " * 40, "no composition at all", "12345"]
kept = []
for text in worst:
    if not text.strip():
        continue
    prompt_i, _, _, _ = score(dict(BASE, composition_guide_custom=text))
    present_names = {n for n, _, _ in rl.lint(prompt_i.lower(), bank)[0]}
    kept.append("composition" in present_names)
check("no typed text can drop the composition layer", all(kept), str(kept))

print()
print("=== CUSTOM SHOT: replaces the camera slot, and says so ===")
GOOD_SHOT = "close-up iPhone-style photo"
prompt, layers, got, _ = score(dict(BASE, shot_custom=GOOD_SHOT))
check("the typed shot reaches the prompt", GOOD_SHOT in prompt)
check("it owns the camera slot", layers["camera"] == [GOOD_SHOT], str(layers["camera"]))
check("naming a camera still scores 8/8", got == 8, "{}/8".format(got))

_, _, got_bad, _ = score(dict(BASE, shot_custom="over-the-shoulder from behind"))
check("a shot naming no camera honestly costs the layer", got_bad == 7, "{}/8".format(got_bad))

# A preset and a custom shot are alternatives; the typed one wins outright,
# which is what stops a preset quietly re-supplying lens and composition.
_, layers_both, _, _ = score(dict(BASE, shot="selfie", shot_custom=GOOD_SHOT))
check("a typed shot suppresses the preset", layers_both["camera"] == [GOOD_SHOT],
      str(layers_both["camera"]))
check("so the preset's lens does not leak in",
      "natural phone camera sharpness" not in layers_both["lens"],
      str(layers_both["lens"]))

# overrides are the lower-level control and must still win.
_, layers_ov, _, _ = score(dict(BASE, shot_custom=GOOD_SHOT,
                                overrides={"camera": ["DSLR photography"]}))
check("an explicit override still outranks it",
      layers_ov["camera"] == ["DSLR photography"], str(layers_ov["camera"]))

print()
print("=== PURPOSE PRECEDENCE ===")
merged = bp.apply_purpose(bank, dict(BASE, purpose="tiktok-ugc", shot_custom=GOOD_SHOT))
check("a purpose does not fill the shot behind a custom one", "shot" not in merged,
      str(merged.get("shot")))
check("but it still supplies the aspect", merged.get("aspect") == "9:16",
      str(merged.get("aspect")))
notes = bp.purpose_conflicts(bank, dict(BASE, purpose="tiktok-ugc", shot_custom=GOOD_SHOT))
check("the disagreement is reported, not fixed", any("typed your own" in n for n in notes),
      str(notes))

print()
print("=== THE BANK, v8 ===")
check("version bumped", bank["version"] == 8, str(bank["version"]))
for cam in ["shot on an ARRI Alexa", "shot on a Sony Venice 2", "shot on a RED V-Raptor",
            "shot on a Hasselblad medium format camera"]:
    check("'{}' is in the camera layer".format(cam), cam in bank["layers"]["camera"]["terms"])
    _, _, got_cam, banned_cam = score(dict(BASE, overrides={"camera": [cam]}))
    check("and it scores 8/8".format(cam), got_cam == 8 and not banned_cam,
          "{}/8".format(got_cam))
check("phone-candid exists", "phone-candid" in bank["shot_presets"])
check("it is a rear camera, not a selfie",
      "selfie" not in bank["shot_presets"]["phone-candid"]["camera"].lower(),
      bank["shot_presets"]["phone-candid"]["camera"])
_, _, got_preset, banned_preset = score(dict(BASE, shot="phone-candid"))
check("phone-candid scores 8/8", got_preset == 8 and not banned_preset, "{}/8".format(got_preset))
check("hard light is available now",
      "harsh midday sunlight" in bank["layers"]["lighting"]["terms"])
_, _, got_hard, _ = score(dict(BASE, overrides={"lighting": ["harsh midday sunlight",
                                                             "realistic shadows"]}))
check("and it scores", got_hard == 8, "{}/8".format(got_hard))
names = [e["name"] for e in bank["examples"]]
check("the influencer prompt is few-shot material", "influencer beach candid" in names,
      str(names))
taught = brief._taught_examples(bank, 3)
check("its lessons travel with it", any("occlusion" in b or "hat covers" in b for b in taught))

print()
print("=== AUTO-FILL: the gate and the boundaries ===")
REPLY = json.dumps({
    "subject": "a woman in her late twenties with freckles",
    "wardrobe": "a straw hat and a striped swimsuit",
    "setting": "a tropical beach at midday",
    "action": "lying on her stomach reading",
    "mood": "unhurried",
    "shot": "phone-candid",
    "purpose": "tiktok-ugc",
    "extra": ["the hat brim shades her eyes", "grains of sand on her shoulder"],
    "lighting": "harsh midday sunlight",
    "composition_guide": "golden-spiral",
    "seed": 999,
    "reference": "/etc/passwd",
    "lock_identity": True,
    "overrides": {"core": ["nonsense"]},
})

r = brief.autofill_spec(bank, {"subject": "a woman tanning on a tropical beach"},
                        ask=fake(REPLY))
check("succeeds", r["ok"], str(r.get("error")))
for forbidden in ("seed", "reference", "lock_identity", "overrides"):
    check("the model cannot set {}".format(forbidden), forbidden not in r["spec"])
check("what it can set arrives", r["spec"]["wardrobe"].startswith("a straw hat"))

# The confirmed decision: suggest, do not apply.
check("composition is held back", "composition_guide" not in r["spec"])
check("lighting is held back", "lighting" not in r["spec"])
check("both are offered as suggestions",
      r["suggestions"] == {"composition_guide": "golden-spiral",
                           "lighting": "harsh midday sunlight"}, str(r["suggestions"]))

r2 = brief.autofill_spec(bank, {}, ask=fake(json.dumps(
    {"subject": "a man", "composition_guide": "not-a-real-guide"})))
check("an invented guide is dropped, not suggested",
      "composition_guide" not in r2["suggestions"], str(r2["suggestions"]))
check("and it is reported", any("not-a-real-guide" in d for d in r2["dropped"]),
      str(r2["dropped"]))

r3 = brief.autofill_spec(bank, {}, ask=fake(json.dumps(
    {"subject": "a man", "shot": "bogus-shot"})))
check("an invented shot is dropped", "shot" not in r3["spec"])

r4 = brief.autofill_spec(bank, {}, ask=fake(None, error="OPENROUTER_API_KEY is not set"))
check("a missing key is an error, not a crash", not r4["ok"] and "OPENROUTER" in r4["error"])

r5 = brief.autofill_spec(bank, {}, ask=fake("I'd rather not."))
check("non-JSON is refused", not r5["ok"])

# The brief must carry what the user already wrote, or the model cannot work
# around it.
captured = {}


def capturing(prompt, system=None, images=(), **kw):
    captured["prompt"] = prompt
    captured["system"] = system
    return (json.dumps({"mood": "calm"}), None)


brief.autofill_spec(bank, {"subject": "a barista", "setting": "a closed cafe"},
                    ask=capturing)
check("the existing fields are sent as the brief",
      "a barista" in captured["prompt"] and "a closed cafe" in captured["prompt"])
check("and marked as untouchable", "do not change" in captured["prompt"].lower())
check("the brief names the occlusion rule", "occlusion" in captured["system"].lower()
      or "hides or breaks up the face" in captured["system"].lower())

print()
print("=== THE FORM: fill blanks, keep yours ===")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.spec_editor import SpecEditor  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
ed = SpecEditor(bank)
ed.load_spec({"subject": "a barista I already wrote", "mood": "tired"})

filled = ed.apply_partial({"subject": "SOMETHING ELSE", "mood": "OVERWRITTEN",
                           "wardrobe": "a green apron", "setting": "a cafe"},
                          fill_blanks_only=True)
spec = ed.spec()
check("my subject survived", spec["subject"] == "a barista I already wrote", spec["subject"])
check("my mood survived", spec["mood"] == "tired", spec["mood"])
check("the empty fields were filled", spec["wardrobe"] == "a green apron")
check("it reports what it filled", filled == ["setting", "wardrobe"], str(filled))

ed.load_spec({"subject": "a barista", "mood": "tired"})
ed.apply_partial({"mood": "OVERWRITTEN"}, fill_blanks_only=False)
check("without the flag it still overwrites", ed.spec()["mood"] == "OVERWRITTEN")

# The placeholder subject nearly made auto-fill useless: spec() substitutes
# "a person" so a prompt can always be composed, and every "is this filled in?"
# test read that as a real answer. The result was that the model's subject was
# rejected on an empty form - the one field that most needed filling.
print()
print("=== THE PLACEHOLDER SUBJECT IS NOT AN ANSWER ===")
ed.load_spec({})
check("spec() still substitutes it", ed.spec()["subject"] == "a person")
check("but the box is empty", ed.subject.toPlainText().strip() == "")
check("and it does not count as filled", "subject" not in ed.filled_keys(),
      str(sorted(ed.filled_keys())))

ed.load_spec({})
applied = ed.apply_partial({"subject": "a woman with freckles"}, fill_blanks_only=True)
check("so an empty subject CAN be filled",
      ed.spec()["subject"] == "a woman with freckles", ed.spec()["subject"])
check("and it is reported as filled", "subject" in applied, str(applied))

ed.load_spec({})
ed.apply_partial({"mood": "calm"}, fill_blanks_only=True)
check("the placeholder is never written into the box",
      ed.subject.toPlainText().strip() == "", repr(ed.subject.toPlainText()))

captured.clear()
brief.autofill_spec(bank, {"subject": "a person", "seed": 0}, ask=capturing)
check("the brief does not pin the placeholder as untouchable",
      "a person" not in captured["prompt"], captured["prompt"])
check("it says the form is empty instead", "nothing yet" in captured["prompt"])

print()
print("=== THE FORM: custom values round-trip ===")
ed.load_spec({"subject": "a woman", "shot_custom": GOOD_SHOT,
              "composition_guide_custom": CUSTOM})
check("custom shot shown as typed", ed.shot.currentText() == GOOD_SHOT, ed.shot.currentText())
check("custom composition shown as typed", ed.composition.currentText() == CUSTOM)
spec = ed.spec()
check("custom shot survives a round trip", spec.get("shot_custom") == GOOD_SHOT)
check("custom composition survives", spec.get("composition_guide_custom") == CUSTOM)
check("and no preset key is invented", "shot" not in spec)
check("nor a guide key", "composition_guide" not in spec)

ed.load_spec({"subject": "a woman", "shot": "selfie", "composition_guide": "phi-grid"})
check("a preset still selects its item", ed.spec().get("shot") == "selfie")
check("a guide still selects its item", ed.spec().get("composition_guide") == "phi-grid")
check("and no custom key appears", "shot_custom" not in ed.spec())

ed.load_spec({"subject": "a woman", "shot": "not-a-preset"})
check("an unknown preset falls back to auto, not to free text",
      "shot" not in ed.spec() and "shot_custom" not in ed.spec(), str(ed.spec()))

print()
print("=== TYPING a listed name still means that listed thing ===")
# The combo's index does not move when text is typed rather than picked, so
# currentData() alone reported "portrait" as free text - which replaced the
# camera slot with the bare word "portrait" and threw the preset's lens and
# composition away, costing a lint point for no reason.
from PyQt6.QtTest import QTest  # noqa: E402


def type_into(combo, text):
    ed.load_spec({"subject": "a woman"})
    combo.setCurrentIndex(0)
    combo.lineEdit().selectAll()
    QTest.keyClicks(combo.lineEdit(), text)
    app.processEvents()
    return ed.spec()


s = type_into(ed.shot, "portrait")
check("typing a preset name selects the preset", s.get("shot") == "portrait", str(s.get("shot")))
check("and it is not also custom", "shot_custom" not in s)
_, layers_typed = bp.compose(bank, dict(s, seed=1))
check("so the preset's camera is used",
      layers_typed["camera"] == ["studio portrait photography"], str(layers_typed["camera"]))

check("matching ignores case", type_into(ed.shot, "PORTRAIT").get("shot") == "portrait")
check("a prefix stays custom", type_into(ed.shot, "port").get("shot_custom") == "port")
check("a preset name inside a phrase stays custom",
      type_into(ed.shot, "selfie on a boat").get("shot_custom") == "selfie on a boat")

s = type_into(ed.composition, "Rule of Thirds")
check("typing a guide's label selects the guide",
      s.get("composition_guide") == "rule-of-thirds", str(s.get("composition_guide")))
s = type_into(ed.composition, "rule-of-thirds")
check("typing its key works too", s.get("composition_guide") == "rule-of-thirds",
      str(s.get("composition_guide")))
s = type_into(ed.composition, "framed to include the sky")
check("anything else is still custom",
      s.get("composition_guide_custom") == "framed to include the sky")

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL AUTOFILL / CUSTOM CHECKS PASSED")
