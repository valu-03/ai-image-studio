"""history.weights() is UCB1, not a plain average - verified against a
synthetic history so nothing here depends on (or can corrupt) the user's own.

The claim worth defending: a term nobody has ever picked gets a REAL
exploration bonus and a real entry in the returned dict (where it used to be
silently absent, defaulting to flat neutral in build_prompt.pick()'s fallback
with no way to ever rise above it), the exploit half of the original formula
still dominates once a term has real evidence, and - the one claim not
obviously true just from reading the formula - zero history degrades to
exactly today's plain uniform sampling, not something new and unverified.
"""
import os
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# This suite never calls history.load()/append() - every check below passes
# its own synthetic `entries` list straight to weights(), so no disk I/O to
# the real log happens at all. Set anyway, defensively, the same way every
# other suite that imports history.py does - a future change to this file
# that starts calling load() should not be the first thing that notices the
# real log was reachable.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(tempfile.gettempdir()) / "aivs-history-test.jsonl"))

import build_prompt as bp  # noqa: E402
import history as hist  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bp.load_bank()
VERSION = hist.current_bank_version()


def rating_rows(term, rating, count, layer="lighting"):
    return [{"rating": rating, "bank_version": VERSION, "layers": {layer: [term]}}
            for _ in range(count)]


lighting_terms = bank["layers"]["lighting"]["terms"]
GOOD, MEDIOCRE, LUCKY = lighting_terms[0], lighting_terms[1], lighting_terms[2]
UNTRIED = [t for t in lighting_terms if t not in (GOOD, MEDIOCRE, LUCKY)]

entries = (
    rating_rows(GOOD, 5, 15)
    + rating_rows(MEDIOCRE, 2, 3)
    + rating_rows(LUCKY, 5, 1)
)

print("=== a term never picked gets a real entry and a real bonus ===")
w = hist.weights(entries)
for term in UNTRIED:
    check("'{}' appears in the output".format(term), term in w)
check("an untried term scores above the flat-neutral fallback (1.0)",
      all(w[t] > 1.0 for t in UNTRIED),
      str({t: round(w[t], 3) for t in UNTRIED}))

print()
print("=== exploitation still works: real evidence still wins ===")
check("15x-rated-5 term outranks everything else in its layer",
      w[GOOD] == max(w[t] for t in lighting_terms), str(round(w[GOOD], 3)))
check("15x-rated-5 beats an untried term", w[GOOD] > max(w[t] for t in UNTRIED))
check("a 3x-rated-2 (mediocre) term scores below an untried term",
      w[MEDIOCRE] < min(w[t] for t in UNTRIED),
      "{:.3f} vs {:.3f}".format(w[MEDIOCRE], min(w[t] for t in UNTRIED)))

print()
print("=== the bonus shrinks as a term's own n grows (holding layer_total roughly fixed) ===")
w_more = hist.weights(entries + rating_rows(LUCKY, 5, 20))
lucky_exploit_only_grew = w_more[LUCKY] != w[LUCKY]
check("scoring LUCKY again after 20 more ratings changes its own score",
      lucky_exploit_only_grew)
# With 21 total ratings and a perfect mean, LUCKY should now clearly outrank
# an untried term by exploitation alone, not just a bonus edge.
check("LUCKY now clearly outranks an untried term once it has real evidence",
      w_more[LUCKY] > max(w_more[t] for t in UNTRIED) + 0.05,
      "{:.3f} vs {:.3f}".format(w_more[LUCKY], max(w_more[t] for t in UNTRIED)))

print()
print("=== layer_total is scored per layer, not globally ===")
# Camera layer has zero ratings in `entries`; lighting has 19. If bonuses were
# scored off a shared global total, camera's untried terms would carry
# lighting's much larger N baked into their own bonus.
camera_terms = bank["layers"]["camera"]["terms"]
w_camera = hist.weights(entries)
lighting_untried_bonus = w_camera[UNTRIED[0]] - 1.0   # exploit half is exactly 1.0 at n=0
camera_untried_bonus = w_camera[camera_terms[0]] - 1.0
check("an untried lighting term's bonus differs from an untried camera term's "
      "(different layer_total, not a shared global one)",
      abs(lighting_untried_bonus - camera_untried_bonus) > 1e-9,
      "{:.4f} vs {:.4f}".format(lighting_untried_bonus, camera_untried_bonus))
check("the layer with more total ratings gives its untried terms the bigger bonus",
      lighting_untried_bonus > camera_untried_bonus)

print()
print("=== every bank term appears, across all 8 layers ===")
w_full = hist.weights(entries)
missing = []
for layer in hist.LAYERS:
    for term in bank["layers"][layer]["terms"]:
        if term not in w_full:
            missing.append("{}/{}".format(layer, term))
check("no bank term is missing from weights()'s output", not missing,
      ", ".join(missing[:10]))

print()
print("=== call-site contract: never None, works with build_prompt.compose() ===")
check("weights() returns a dict", isinstance(hist.weights(), dict))
check("weights([]) returns a dict, not None", isinstance(hist.weights([]), dict))
try:
    prompt, layers = bp.compose(bank, {"subject": "a man in his thirties", "seed": 0},
                                weights=hist.weights(entries))
    composed_ok = bool(prompt)
except Exception as exc:  # pragma: no cover - failure is the point of the check
    composed_ok = False
    print("    exception: {}".format(exc))
check("compose() runs end to end with a real weights() dict", composed_ok)

print()
print("=== zero history degrades to today's plain uniform sampling ===")
w_zero = hist.weights([])
values = {round(w_zero[t], 9) for t in lighting_terms}
check("every term in a layer gets an identical weight with no history at all",
      len(values) == 1, str(values))

rng = random.Random(7)
TRIALS = 20000
counts = {t: 0 for t in lighting_terms}
for _ in range(TRIALS):
    for term in bp.pick(rng, lighting_terms, 2, w_zero):
        counts[term] += 1
total_picks = sum(counts.values())
expected = total_picks / len(lighting_terms)
# A generous tolerance - this is a statistical check on a random process, not
# an exact-equality one. 8% either side of expected across 20000 trials/9
# terms is comfortably outside normal sampling noise if the code were biased,
# and comfortably inside it if the distribution really is uniform.
worst_ratio = max(abs(c - expected) / expected for c in counts.values())
check("pick() over zero-history weights matches uniform sampling within tolerance",
      worst_ratio < 0.08, "worst deviation {:.1%}".format(worst_ratio))

print()
print("=== _fmt_row tolerates a corrupt rating/id/seed field ===")
# load() skips a corrupt LINE; _fmt_row must also survive a corrupt FIELD in
# an otherwise-parseable row, or one hand-edited entry makes `history list`
# unrunnable.
for bad in ({"rating": "5"}, {"rating": 4.0}, {"rating": 99}, {"rating": -1},
            {"seed": None}, {}):
    try:
        row = hist._fmt_row(dict({"id": "x", "score": 8}, **bad))
        check("_fmt_row survives {!r}".format(bad), isinstance(row, str))
    except Exception as exc:
        check("_fmt_row survives {!r}".format(bad), False,
              "{}: {}".format(type(exc).__name__, exc))

print()
print("=== CARD CHOICES ===")
_ver = hist.current_bank_version()


def _e(light, rating):
    return {"id": light + str(rating), "rating": rating, "bank_version": _ver,
            "look": {"kind": "animal", "cards": {"light": light}}}


_ents = [_e("overcast", 5), _e("overcast", 5), _e("lamp", 1),
         dict(_e("lamp", 5), bank_version=_ver - 1)]
_w = hist.card_weights(_ents)
check("look_stored_and_weighted", _w["light"]["overcast"] > _w["light"]["lamp"], str(_w))
check("stale_bank_ignored", abs(_w["light"]["lamp"] - (6 + 1) / 3) < 1e-9)
check("thumbs", hist.THUMBS == {"up": 5, "down": 1})

with tempfile.TemporaryDirectory() as _d:
    _old = hist.HISTORY
    hist.HISTORY = Path(_d) / "h.jsonl"
    _img = Path(_d) / "a.png"
    _img.write_bytes(b"x")
    _a = hist.append({"seed": 1}, "p", {}, 5, True, image=str(_img),
                     look={"kind": "animal", "cards": {"light": "lamp"}})
    _b = hist.append({"seed": 2}, "p", {}, 5, True, image=str(Path(_d) / "gone.png"))
    _c = hist.append({"seed": 3}, "p", {}, 5, True, image=str(_img))
    _r = hist.recent()
    check("recent_skips_missing_files", [e["id"] for e in _r] == [_c, _a], str([e["id"] for e in _r]))
    check("look_saved_on_entry", _r[1]["look"] == {"kind": "animal", "cards": {"light": "lamp"}})
    check("recent_limit", len(hist.recent(1)) == 1)
    hist.HISTORY = _old

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL HISTORY CHECKS PASSED")

sys.exit(1 if fails else 0)
