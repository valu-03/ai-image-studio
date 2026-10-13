"""The optional composition guide, from the bank through the UI to the prompt.

The guide is a *pin*, not an override: it takes the first composition slot and
the bank fills the rest. That is the behaviour worth defending here, along with
the one that would break the app quietly - a guide the linter cannot detect,
which would drop the composition layer to zero and fail the 8/8 gate.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# Before MainWindow is imported: it reads AIVS_SETTINGS_APP at import time to
# pick which QSettings key it opens. Without this every GUI test read AND
# WROTE the user's real saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
# This suite's own variant-build step below used to write straight into the
# REAL history.jsonl (no redirect existed) and then delete exactly the rows
# it added back out - fine as long as nothing crashed in between, but a
# crash between the write and that cleanup would have left fake rows
# permanently mixed into the user's real log. Redirect instead of trusting
# the cleanup to always run.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(tempfile.gettempdir()) / "aivs-composition-history.jsonl"))

from PyQt6.QtWidgets import QApplication

import build_motion as bm
import build_prompt as bp
import realism_lint as rl
from ui.main_window import MainWindow
from ui.theme import ThemeManager

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bp.load_bank()
guides = bp.guides(bank)
base = {"subject": "a woman in her thirties with freckles", "setting": "a kitchen", "seed": 3}

print("--- the bank ---")
check("eight guides", len(guides) == 8, str(len(guides)))
expected = ["rule-of-thirds", "phi-grid", "diagonals", "triangle",
            "golden-ratio", "golden-spiral", "harmonic-armature", "dynamic-symmetry"]
check("keys as listed", list(guides) == expected, str(list(guides)))
check("every guide has label, phrase, note",
      all({"label", "phrase", "note"} <= set(g) for g in guides.values()))
# "Symmetry" alone pulls a model toward a centred, mirrored frame - the opposite
# of Hambidge's grid. The phrase has to say so, or the name undoes the guide.
check("dynamic symmetry disowns mirroring",
      "rather than mirrored" in guides["dynamic-symmetry"]["phrase"],
      guides["dynamic-symmetry"]["phrase"])
check("bank version bumped past 1", bank["version"] >= 2, str(bank["version"]))

print("--- every guide scores 8/8, in both forms, under every shot ---")
bad = []
for key in guides:
    for shot in [""] + list(bank["shot_presets"]):
        for detailed in (False, True):
            spec = dict(base, composition_guide=key)
            if shot:
                spec["shot"] = shot
            prompt, layers = bp.compose(bank, spec, detailed=detailed)
            present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
            if len(present) != 8 or banned:
                bad.append("{}/{}/{}".format(key, shot or "auto", "long" if detailed else "short"))
check("96 combinations all 8/8", not bad, ", ".join(bad[:4]))

print("--- the linter can see each guide on its own ---")
for key, guide in guides.items():
    # lint() returns (layer_name, cfg, matched_keyword) tuples for the layers it found.
    present, _, _, _, _ = rl.lint(guide["phrase"].lower(), bank)
    hit = next((k for name, _, k in present if name == "composition"), None)
    check("linter detects " + key, hit is not None, str(hit))

print("--- a pin, not a replacement ---")
pick = bank["layers"]["composition"].get("pick", 2)
_, layers = bp.compose(bank, dict(base, composition_guide="triangle"))
check("guide is first", layers["composition"][0] == guides["triangle"]["phrase"])
check("layer keeps its length", len(layers["composition"]) == pick,
      str(layers["composition"]))

print("--- an explicit guide outranks the defaults ---")
_, preset_only = bp.compose(bank, dict(base, shot="portrait"))
_, layers = bp.compose(bank, dict(base, shot="portrait", composition_guide="golden-spiral"))
check("beats the shot preset", layers["composition"][0] == guides["golden-spiral"]["phrase"])
check("it displaced a preset term, not appended",
      len(layers["composition"]) == len(preset_only["composition"]),
      str(layers["composition"]))
hinted = bm.apply_image_hints(bm.load_bank(), "orbit-360",
                              dict(base, composition_guide="triangle"))
_, layers = bp.compose(bank, hinted)
check("beats a camera-move hint", layers["composition"][0] == guides["triangle"]["phrase"])
check("shot hint still applies", hinted.get("shot") == "environmental", str(hinted.get("shot")))

print("--- no duplication ---")
prompt, _ = bp.compose(bank, dict(base, shot="portrait", composition_guide="rule-of-thirds"))
check("'rule of thirds' said once", prompt.lower().count("rule of thirds") == 1,
      str(prompt.lower().count("rule of thirds")))

print("--- (none) imposes no compositional rule at all ---")
plain = bp.compose(bank, dict(base))[0]
check("no guide phrase leaks", not any(g["phrase"] in plain for g in guides.values()))

# The whole point of the opt-in: an unasked-for geometry must never reach a prompt,
# from the bank's own pool or from a shot preset.
GEOMETRY = ["rule of thirds", "phi grid", "golden ratio", "golden spiral",
            "fibonacci", "harmonic armature", "diagonal composition",
            "triangular composition", "dynamic symmetry"]
check("the auto pool holds no geometry",
      not any(g in " ".join(bank["layers"]["composition"]["terms"]) for g in GEOMETRY),
      str(bank["layers"]["composition"]["terms"]))
leaked = []
for shot in [""] + list(bank["shot_presets"]):
    for seed in range(40):
        for detailed in (False, True):
            spec = dict(base, seed=seed)
            if shot:
                spec["shot"] = shot
            text = bp.compose(bank, spec, detailed=detailed)[0].lower()
            hit = next((g for g in GEOMETRY if g in text), None)
            if hit:
                leaked.append("{}/{}:{}".format(shot or "none", seed, hit))
check("480 unguided prompts impose no rule", not leaked, ", ".join(leaked[:4]))
for name, preset in bank["shot_presets"].items():
    check("preset '{}' carries no geometry".format(name),
          not any(g in " ".join(preset.get("composition", [])) for g in GEOMETRY),
          str(preset.get("composition")))
regressions = 0
for shot in bank["shot_presets"]:
    for seed in range(5):
        p, _ = bp.compose(bank, dict(base, shot=shot, seed=seed))
        present, _, banned, _, _ = rl.lint(p.lower(), bank)
        if len(present) != 8 or banned:
            regressions += 1
check("25 preset x seed still 8/8", regressions == 0, str(regressions))

print("--- the validator ---")
check("unknown guide rejected", bp.validate_guide(bank, "spiral-of-doom") is not None)
check("known guide accepted", bp.validate_guide(bank, "phi-grid") is None)
check("empty guide accepted", bp.validate_guide(bank, "") is None)

print("--- CLI parity ---")
args = bp.parse_args(["--subject", "a man", "--composition-guide", "diagonals"])
check("flag parsed", bp.spec_from_args(args)["composition_guide"] == "diagonals")

# ---------------------------------------------------------------- the UI ---- #
app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

cv = win.compose_view
ed = cv.editor
cv.form_mode.setCurrentIndex(0)
# A fixed spec, not whatever happens to be first in the real character library.
# Loading the user's own first character made "defaults to none" depend on
# whether they had ever saved one with a guide set - a test of their data
# rather than of this code.
ed.load_spec({"subject": "a female model in her twenties", "seed": 0})

print("--- the combo ---")
# Open, not closed: the eight named geometries are starting points, and a typed
# framing instruction is as legitimate as a named grid. It still cannot silently
# add an item to the list.
check("open to typed text", ed.composition.isEditable())
check("typing never grows the list",
      ed.composition.insertPolicy() == ed.composition.InsertPolicy.NoInsert)
check("auto plus eight", ed.composition.count() == 9, str(ed.composition.count()))
check("defaults to none", ed.composition_guide() == "", repr(ed.composition_guide()))
check("the empty row reads (none)", ed.composition.itemText(0) == "(none)",
      ed.composition.itemText(0))
check("none adds no key", "composition_guide" not in ed.spec())
check("lives on the Scene tab", ed.tabs.widget(2).isAncestorOf(ed.composition))
check("labels are the readable ones",
      ed.composition.itemText(6) == "Golden Spiral (Fibonacci Spiral)",
      ed.composition.itemText(6))

print("--- choosing one reaches the prompt ---")
ed.composition.setCurrentIndex(ed.composition.findData("golden-spiral"))
app.processEvents()
cv.rebuild()
check("spec carries the key", ed.spec().get("composition_guide") == "golden-spiral")
check("phrase in the prompt", guides["golden-spiral"]["phrase"] in cv.prompt_text())
check("still 8/8", cv.passing, cv.lint.badge.text())

cv.form_mode.setCurrentIndex(1)
cv.rebuild()
check("detailed form too", guides["golden-spiral"]["phrase"] in cv.prompt_text())
check("detailed still 8/8", cv.passing, cv.lint.badge.text())
cv.form_mode.setCurrentIndex(0)
cv.rebuild()

print("--- it coexists with a custom lighting source ---")
ed.lighting.setCurrentText("firelight from a wood stove")
app.processEvents()
spec = ed.spec()
check("lighting override survives",
      spec["overrides"]["lighting"][0] == "firelight from a wood stove")
check("guide survives", spec.get("composition_guide") == "golden-spiral")
cv.rebuild()
check("both in the prompt",
      "firelight from a wood stove" in cv.prompt_text()
      and guides["golden-spiral"]["phrase"] in cv.prompt_text())
check("both together still 8/8", cv.passing, cv.lint.badge.text())
ed.lighting.setCurrentIndex(0)
app.processEvents()

print("--- round-trips through save/load ---")
saved = ed.spec()
ed.load_spec({"subject": "someone else", "seed": 0})
check("cleared on load", ed.composition_guide() == "", repr(ed.composition_guide()))
ed.load_spec(saved)
check("restored", ed.composition_guide() == "golden-spiral", ed.composition_guide())
ed.load_spec(dict(saved, composition_guide="not-a-guide"))
check("unknown value falls back to auto", ed.composition_guide() == "",
      repr(ed.composition_guide()))
ed.load_spec(saved)

print("--- variants inherit it ---")
bundle_spec, _, _ = win.current_spec_bundle()
check("bundle carries the guide", bundle_spec.get("composition_guide") == "golden-spiral")
win.variants_view.count.setValue(3)
win.variants_view.build_variants()
check("3 variants built", len(win.variants_view.cards) == 3)
import history as hist
recent = hist.load()[-3:]
check("all variants use it",
      all(guides["golden-spiral"]["phrase"] in e["prompt"] for e in recent))
check("all variants 8/8", all(e["score"] == 8 for e in recent),
      str([e["score"] for e in recent]))

if hist.HISTORY.exists():
    hist.HISTORY.unlink()

print("--- back to (none) ---")
ed.composition.setCurrentIndex(0)
app.processEvents()
cv.rebuild()
check("none removes the key", "composition_guide" not in ed.spec())
check("none still 8/8", cv.passing)
check("and no geometry in the prompt",
      not any(g in cv.prompt_text().lower() for g in GEOMETRY), cv.prompt_text()[:80])

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL COMPOSITION CHECKS PASSED")
sys.exit(0)
