"""tools/realism_lint.py: the gate itself.

Every satellite bank in this project has a suite that audits its phrases
against this linter - test_lighting_bank.py, test_color_bank.py,
test_macro_insert.py, test_camera_angle_bank.py and the rest. The linter they
all point at had no suite of its own, which is how three separate holes sat in
it: a prompt could NEGATE a layer and still score it, eight unrelated words
scored a full 8/8, and the word "wearing" - which build_prompt writes into
nearly every prompt this app composes - silently satisfied the texture layer.

Each of those is a named case below, written as the failing string first so a
regression reads as the hole reopening rather than as an abstract assertion.

Standard library only, no network, no Qt - this is a CLI suite.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = json.loads((ROOT / "tools" / "prompt_bank.json").read_text(encoding="utf-8"))

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def score(text, selected=None):
    present, _missing, banned, _warn, _neg = rl.lint(text, BANK, selected)
    return len(present), (len(present) == 8 and not banned)


def layers_of(text, selected=None):
    present, _m, _b, _w, _n = rl.lint(text, BANK, selected)
    return [name for name, _cfg, _hit in present]


print("=== A NEGATED LAYER DOES NOT SCORE ===")
# is_negated() existed from the start but was wired only into find_terms(), so
# it guarded banned terms and never the layer keys. This prompt rules out three
# layers in plain English and used to score all three, for a full 8/8 PASS.
NEGATED = ("photorealistic portrait, DSLR photography, no bokeh, avoid film grain, "
           "soft window light, no texture, flat color grading, eye-level shot")
got, passed = score(NEGATED)
check("a prompt that rules out three layers does not pass", not passed, "{}/8".format(got))
present = layers_of(NEGATED)
for layer, phrase in [("lens", "no bokeh"), ("grain", "avoid film grain"), ("texture", "no texture")]:
    check("'{}' does not fill the {} layer".format(phrase, layer), layer not in present)

check("a POSITIVE use of the same word still scores",
      "lens" in layers_of("shot on a 35mm lens, shallow depth of field, natural bokeh"))

# A comma ends the negator's reach - this is the rule is_negated() already had
# for banned terms, and it must hold identically for layer keys.
check("a comma ends the negation window",
      "grain" in layers_of("no plastic skin, subtle film grain"))
# ...and so does a colon. Without this, "hard light, not soft: sunlight casting
# hard shadows" read as a negation of sunlight and dropped the lighting layer,
# though the sentence is asking for exactly that light.
check("a colon ends the negation window too",
      "lighting" in layers_of("hard light, not soft: sunlight casting hard shadows"))


print()
print("=== 'wearing' NO LONGER SATISFIES THE TEXTURE LAYER ===")
# The whole reason this one mattered: build_prompt.subject_clause() emits
# "wearing <wardrobe>" for every spec that sets wardrobe, so the layer
# prompt_bank.json itself calls the single biggest defence against the plastic
# AI look was being auto-satisfied by a function word in most real prompts.
check("'a woman wearing a red dress' scores the texture layer never",
      "texture" not in layers_of("a woman wearing a red dress"))
check("and scores nothing at all", score("a woman wearing a red dress")[0] == 0)
check("'streetwear' does not either", "texture" not in layers_of("luxury streetwear"))

# Both-end anchoring, not just start-anchoring. Each of these contains a layer
# key as a prefix and means something else entirely.
check("'textureless' does not fill texture", "texture" not in layers_of("a textureless plastic doll"))
check("'hazel eyes' does not fill composition",
      "composition" not in layers_of("a woman with hazel eyes"))

# ...while the inflections a real prompt actually uses must still MATCH. These
# assert the key, not the layer: texture needs two distinct keys to score, so
# one phrase can never fill the layer by itself and asking whether it does
# would be testing the threshold, not the anchoring.
for word, layer in [("visible skin pores", "texture"), ("slight imperfections", "texture"),
                    ("fine wrinkles", "texture"), ("faint freckles", "texture"),
                    ("natural textures", "texture"), ("candid moments", "composition"),
                    ("warm catchlights", "lighting")]:
    check("'{}' still matches a {} key".format(word, layer),
          bool(rl.layer_hits(rl.DETECT[layer]["keys"], word)))


print()
print("=== ONE KEYWORD IS NOT A LAYER ===")
# Eight unrelated words, no subject, no scene, no sentence. This scored 8/8 and
# exited 0, which is the clearest single statement of what was wrong.
SALAD = "lifelike iphone aperture sunlight texture high contrast close-up sharp focus"
got, passed = score(SALAD)
check("word salad does not pass", not passed, "{}/8".format(got))
check("core needs more than one trigger word", "core" not in layers_of(SALAD))
check("texture needs more than one word", "texture" not in layers_of(SALAD))

check("core asks for three distinct keys", rl.required_hits("core") == 3)
check("texture asks for two", rl.required_hits("texture") == 2)
check("every other layer asks for one",
      all(rl.required_hits(n) == 1 for n in rl.LAYER_ORDER if n not in ("core", "texture")))


print()
print("=== THE GATE NEVER REJECTS THE BUILDER'S OWN OUTPUT ===")
# The counts above are calibrated against compose(), not guessed. If a future
# change to prompt_bank.json's terms makes the builder unable to clear its own
# gate, that is a bug in the pair and this is where it surfaces.
spec_base = {"subject": "a tired barista closing up late",
             "wardrobe": "a worn apron", "setting": "an empty cafe"}
compact_fails, detailed_fails = [], []
for seed in range(120):
    spec = dict(spec_base, seed=seed)
    prompt, selected = bp.compose(BANK, spec)
    if not score(prompt)[1]:
        compact_fails.append(seed)
    prompt_d, selected_d = bp.compose(BANK, dict(spec), detailed=True)
    if not score(prompt_d, selected_d)[1]:
        detailed_fails.append(seed)
check("120 seeds of compact compose() all pass", not compact_fails, str(compact_fails[:5]))
check("120 seeds of detailed compose() all pass when judged on their terms",
      not detailed_fails, str(detailed_fails[:5]))

# Every composable term must be detectable by its OWN layer. The satellite bank
# suites assert exactly this for their banks; nobody asserted it for the core.
undetected = [(layer, term) for layer, cfg in BANK["layers"].items()
              for term in cfg["terms"]
              if not rl.layer_hits(rl.DETECT[layer]["keys"], term.lower())]
check("every prompt_bank term is detected by its own layer",
      not undetected, str(undetected[:3]))


print()
print("=== DETAILED MODE DOES NOT SCORE ITS OWN BOILERPLATE ===")
# build_detailed() wraps the selected terms in fixed prose that says "bounce
# light", "micro-texture", "color grading", "separation" and "sensor noise".
# Scored as text, five of the eight layers passed with every user-selected term
# blanked out - the template was certifying itself.
prompt_d, selected_d = bp.compose(BANK, dict(spec_base, seed=1, detailed=True))
blanked = {name: [] for name in rl.LAYER_ORDER}
check("with every term blanked, detailed prose scores nothing",
      score(prompt_d, blanked)[0] == 0, "{}/8".format(score(prompt_d, blanked)[0]))
check("but the real terms still pass", score(prompt_d, selected_d)[1])
check("free-text callers are unaffected by the new parameter",
      score(prompt_d)[0] == score(prompt_d, None)[0])


print()
print("=== checks_for(): THE GateTree CONTRACT ===")
rows = rl.checks_for("nothing realistic here", BANK)
check("ten rows - eight layers, banned, warn", len(rows) == 10, str(len(rows)))
check("every row carries the five keys GateTree reads",
      all({"key", "label", "passed", "fix", "ok_text"} <= set(r) for r in rows))
check("the layer rows come in the fixed layer order",
      [r["key"] for r in rows[:8]] == rl.LAYER_ORDER)
check("an all-miss prompt fails every layer row", not any(r["passed"] for r in rows[:8]))

# The warn list is reported, never blocking: making it fail would reject
# prompts this app has already shipped.
warned = rl.checks_for(
    "photorealistic, ultra-realistic, lifelike details, DSLR photography, "
    "shot on a 35mm lens, natural bokeh, soft window light, visible skin pores, "
    "slight imperfections, natural color grading, eye-level shot, subtle film grain, "
    "8k masterpiece, award-winning", BANK)
warn_row = [r for r in warned if r["key"] == "warn"][0]
check("the warn row passes", warn_row["passed"])
check("the warn row is marked as a warn state", warn_row["state"] == "warn")
check("and it names the terms it found", "8k" in warn_row["fix"] and "masterpiece" in warn_row["fix"])
check("warn terms do not stop the prompt passing", all(r["passed"] for r in warned))
check("a clean prompt's warn row is not in the warn state",
      [r for r in rl.checks_for("photorealistic, ultra-realistic, lifelike details", BANK)
       if r["key"] == "warn"][0]["state"] == "ok")

banned_rows = rl.checks_for("photorealistic, 3d render", BANK)
check("a banned term fails the banned row", not banned_rows[8]["passed"])
check("and 'no 3d render' does not", rl.checks_for("photorealistic, no 3d render", BANK)[8]["passed"])




print()
if fails:
    print("{} passed, {} failed".format("?", len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL REALISM_LINT CHECKS PASSED")
