"""Cats / Custom Prompt: a hand-written prompt split, refined, and generated.

Every other Cats suite covers a prompt the app BUILDS from story_bank.json's
beats. This one covers the opposite direction - a prompt the user already
wrote, ingested and restructured - so it needs its own fixtures rather than
reusing build_story's.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)
os.environ.setdefault("AIVS_ASSUME_YES", "1")
# A test must never write to the user's live outcome log - set before any
# import that could touch history.py, same rule every other GUI suite follows.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(tempfile.gettempdir()) / "aivs-tests-history.jsonl"))
# Same rule, one layer further in: MainWindow reads AIVS_SETTINGS_APP at
# import time to pick which QSettings key it opens.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication

import brief
import build_prompt as bp
import realism_lint as rl
from ui.main_window import MainWindow
from ui.theme import ThemeManager
from ui.views.cats_custom import assemble_prompt

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = bp.load_bank()

GOPRO_PROMPT = (
    "Subject: An extreme wide-angle, low-angle GoPro-style selfie taken by a "
    "brown and white tabby cat standing on its hind legs in a winter park. "
    "The cat holds a camera/selfie stick out toward the viewer with its "
    "right paw, while its left paw holds a partially bitten, bright orange "
    "hot dog / sausage upright like a microphone.\n\n"
    "Background: A paved park path beside a partially frozen lake with ice "
    "patches floating in the water. In the background, a man in a dark "
    "winter coat walks a Siberian Husky on a leash away from the camera.\n\n"
    "Style & Atmosphere: Ultra-realistic, hyper-detailed photo, sharp focus "
    "on the cat's detailed fur, whiskers, and paws, natural cold winter "
    "daylight, dynamic perspective."
)

PASSING_STYLE = (
    "photorealistic, ultra-realistic, lifelike details, DSLR photography, "
    "35mm lens, shallow depth of field, "
    "natural daylight with realistic shadows, visible skin pores, natural "
    "fabric grain, film grain, sharp focus, eye-level shot, natural color "
    "grading, realistic contrast, no cgi"
)


def fake(reply):
    def _ask(prompt, system=None, images=(), **kw):
        return reply, None
    return _ask


def two_replies(first, second):
    calls = {"n": 0}

    def _ask(prompt, system=None, images=(), **kw):
        calls["n"] += 1
        return (first if calls["n"] == 1 else second), None
    return _ask


# --------------------------------------------------------------------------- #
print("--- realism_lint.checks_for ---")
checks = rl.checks_for("nothing realistic here", bank)
check("ten rows - eight layers, banned terms, and the soft warn list",
      len(checks) == 10, str(len(checks)))
check("every row has the GateTree shape",
      all({"key", "label", "passed", "fix", "ok_text"} <= set(c) for c in checks))
check("only the warn row carries the extra state key",
      [c["key"] for c in checks if "state" in c] == ["warn"])
check("an empty prompt fails every layer", not any(c["passed"] for c in checks[:8]))

full_pass = "Subject: a cat. Background: a park. Style & Atmosphere: " + PASSING_STYLE
checks2 = rl.checks_for(full_pass, bank)
check("a prompt with every layer's language passes all ten",
      all(c["passed"] for c in checks2), str([c["key"] for c in checks2 if not c["passed"]]))

banned = rl.checks_for(full_pass + ", 3d render", bank)
check("a positively-used banned term fails only the banned-terms row",
      not banned[8]["passed"] and all(c["passed"] for c in banned[:8]))

# The warn row never fails - it reports. A prompt stuffed with empty
# superlatives still passes, and that is the point: these were invisible in the
# GUI before, riding along inside a green 8/8.
warned = rl.checks_for(full_pass + ", 8k masterpiece, award-winning", bank)
check("warn terms are reported, not failed", warned[9]["passed"])
check("and the row names them", warned[9]["state"] == "warn" and "8k" in warned[9]["fix"])

# --------------------------------------------------------------------------- #
print("--- assemble_prompt ---")
p1 = assemble_prompt("a cat", "a park", "photoreal")
check("deterministic three-part join",
      p1 == "Subject: a cat\n\nBackground: a park\n\nStyle & Atmosphere: photoreal", p1)
check("blank fields still produce the three headings",
      assemble_prompt("", "", "").count(":") == 3)
check("whitespace is trimmed", assemble_prompt("  a cat  ", "x", "y").startswith("Subject: a cat\n"))

# --------------------------------------------------------------------------- #
print("--- brief.analyze_custom_prompt ---")
r = brief.analyze_custom_prompt(
    bank, GOPRO_PROMPT,
    ask=fake(json.dumps({
        "subject": "a tabby cat holding a selfie stick and a hot dog",
        "background": "a winter park by a lake, a man walking a husky",
        "style": "ultra-realistic, GoPro selfie, low angle",
        "seed": 7,
    })))
check("splits into the three fields", r["ok"] and set(r["fields"]) == {"subject", "background", "style"})
check("a key outside the whitelist is dropped and reported", r["dropped"] == ["seed"])

r_empty = brief.analyze_custom_prompt(bank, "   ", ask=fake("irrelevant"))
check("an empty prompt is refused before any call goes out", not r_empty["ok"])

r_bad_json = brief.analyze_custom_prompt(bank, "text", ask=fake("not json at all"))
check("a non-JSON reply fails cleanly, not with an exception", not r_bad_json["ok"])

r_missing = brief.analyze_custom_prompt(bank, "text", ask=fake(json.dumps({"subject": "a cat"})))
check("a reply missing background/style still returns ok - blanks, not a failure",
      r_missing["ok"] and r_missing["fields"]["background"] == "" and r_missing["fields"]["style"] == "")

# --------------------------------------------------------------------------- #
print("--- brief.refine_custom_prompt ---")
current = {"subject": "a grey tabby cat", "background": "a winter park",
          "style": "ultra-realistic, GoPro selfie"}
r2 = brief.refine_custom_prompt(
    bank, current, "make it a golden retriever instead of a husky",
    ask=fake(json.dumps({
        "subject": current["subject"], "background": "a winter park, a man walking a golden retriever",
        "style": current["style"], "lock_identity": True,
    })))
check("only the touched field changes, per the model's own reply",
      r2["ok"] and "golden retriever" in r2["fields"]["background"]
      and r2["fields"]["subject"] == current["subject"])
check("a spec-only key like lock_identity is dropped and reported",
      r2["dropped"] == ["lock_identity"])

r3 = brief.refine_custom_prompt(bank, current, "", image_path=None)
check("no instruction and no image is refused before any call goes out", not r3["ok"])

r4 = brief.refine_custom_prompt(
    bank, current, "", image_path="some/reference.png",
    ask=fake(json.dumps({"subject": "x", "background": "y", "style": "z"})))
check("a reference image alone is enough, with no instruction text", r4["ok"])

r5 = brief.refine_custom_prompt(
    bank, current, "change something",
    ask=fake(json.dumps({"subject": "", "background": "", "style": ""})))
check("a key blanked in the reply falls back to the current value, not empty",
      r5["ok"] and r5["fields"] == current, str(r5["fields"]))

r6 = two_replies(json.dumps({"subject": "a", "background": "b", "style": "c"}),
                 json.dumps({"subject": "a2", "background": "b2", "style": "c2"}))
first = brief.refine_custom_prompt(bank, current, "first change", ask=r6)
second = brief.refine_custom_prompt(bank, first["fields"], "second change", ask=r6)
check("refining twice compounds onto the previous result, not the original",
      second["fields"]["subject"] == "a2", str(second["fields"]))

# --------------------------------------------------------------------------- #
print("--- the real UI ---")
app = QApplication.instance() or QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()
ct = win.cats_view.custom_tab


def pump(seconds=10, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return until() if until else True


check("the tab exists on the Cats view",
      "Custom Prompt" in [win.cats_view.tabs.tabText(i) for i in range(win.cats_view.tabs.count())])
check("starts idle, generate disabled", not ct.gate.all_passed() and not ct.generate_button.isEnabled())

ct.subject_box.setPlainText("a tabby cat")
ct.background_box.setPlainText("a winter park")
ct.style_box.setPlainText(PASSING_STYLE)
app.processEvents()
check("editing a field re-assembles the full prompt live",
      ct.full_prompt_view.toPlainText().startswith("Subject: a tabby cat"))
check("a passing style makes the gate pass and enables Generate",
      ct.gate.all_passed() and ct.generate_button.isEnabled())

ct.style_box.setPlainText(PASSING_STYLE + ", 3d render")
app.processEvents()
check("a banned term reintroduced by hand fails the gate and disables Generate again",
      not ct.gate.all_passed() and not ct.generate_button.isEnabled())
ct.style_box.setPlainText(PASSING_STYLE)
app.processEvents()

# analyze/refine through the real LlmTask dispatch, on the real QThreadPool -
# is_thinking as the wait condition, never a rendered-text comparison, per the
# documented lesson. No OpenRouter key is set, so ask_llm.ask fails fast with
# no network call, and the worker thread settles within the pump's timeout.
ct.paste_box.setPlainText(GOPRO_PROMPT)
ct.analyze()
check("analyze finishes on the real worker thread",
      pump(10, until=lambda: not ct.analyze_badge.is_thinking))
check("a real key with no OpenRouter key set fails cleanly, not with an exception",
      ct.analyze_badge.badge.property("status") == "danger")

check("clearing the reference restores the no-reference caption",
      ct.reference_label.text().startswith("No reference"))
ct._reference_path = "some/reference.png"
ct.clear_reference()
check("clear_reference drops the stored path",
      ct._reference_path == "" and ct.reference_label.text().startswith("No reference"))

# --------------------------------------------------------------------------- #
print("--- generation routes to this tab, not Compose ---")
submitted = []


def fake_submit(jobs, provider=None, model=None, spec=None):
    submitted.append((list(jobs), dict(spec or {})))


win.pool.submit = fake_submit
ct.aspect.setCurrentText("9:16")
ct.request_generate()
app.processEvents()
check("one job goes out", len(submitted) == 1 and len(submitted[0][0]) == 1)
check("no reference is carried into generation - the reference image here "
      "informs wording only", submitted[0][0][0][3] == [], str(submitted[0][0][0][3]))
check("the chosen aspect reaches the request options",
      submitted[0][1].get("aspect") == "9:16", str(submitted[0][1]))
check("the batch is routed back to the Custom Prompt tab, not Compose",
      win._batch is not None and win._batch.target is ct)

win.on_item_finished(0, str(ROOT / "temp" / "outputs" / "images" / "custom-prompt-test.png"))
app.processEvents()
check("the result lands on this tab's own ResultCard, not Variants",
      ct.current_image is not None)

win.on_batch_finished()
app.processEvents()
check("set_busy(False) re-enables Generate once the batch finishes",
      ct.generate_button.isEnabled())

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL CATS CUSTOM PROMPT CHECKS PASSED")
sys.exit(0)
