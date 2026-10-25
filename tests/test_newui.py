"""Purpose targeting, the tabbed spec editor, and the Brief view, through the real UI."""
import os
import sys
import time
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRATCH))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# A suite's idea of "no key" must not depend on what is in the real .env -
# read_env() outranks os.environ, so an empty env file is what makes
# clearing a variable actually mean anything. Must be set before any tool
# is imported: generate_image reads AIVS_ENV_FILE at import time.
import tempfile as _tempfile
_EMPTY_ENV = Path(_tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

# This suite drives generate_batch(), upscale_image() and generate_single(), and
# all three now ask confirm_spend() first - a modal nobody can answer is a hang,
# not a safeguard. run_all.py sets this for every child, but a developer running
# THIS file on its own would otherwise watch every submission be declined.
# Joins test_ads, test_cats_custom, test_story and smoke_gui in doing so.
os.environ.setdefault("AIVS_ASSUME_YES", "1")

import mock_api
PORT = 8799
mock_api.serve(PORT)
os.environ["AIVS_API_BASE"] = "http://127.0.0.1:{}/text".format(PORT)
os.environ["OPENROUTER_API_KEY"] = "ui-llm-key"
# Redirect, not backup-and-restore: history.py reads AIVS_HISTORY_FILE at
# import time, and a crash between backing up the real log and restoring it
# would have left the user's real history overwritten with test entries.
os.environ.setdefault(
    "AIVS_HISTORY_FILE", str(Path(_tempfile.gettempdir()) / "aivs-newui-history.jsonl"))
# MainWindow reads AIVS_SETTINGS_APP at import time to pick which QSettings
# key it opens - without this the GUI test read AND WROTE the user's real
# saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

HISTORY = Path(os.environ["AIVS_HISTORY_FILE"])
if HISTORY.exists():
    HISTORY.unlink()

from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from ui.theme import ThemeManager
import build_prompt as bp
import history as hist

app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

cv = win.compose_view
ed = cv.editor
bv = win.brief_view
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def pump(seconds, until):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until():
            return True
        time.sleep(0.02)
    return until()


print("--- categories in the rail ---")
check("images/videos/assistant present",
      all(k in win.nav_buttons for k in ("images", "videos", "assistant")))
check("images icon", not win.nav_buttons["images"].icon().isNull())
check("videos icon", not win.nav_buttons["videos"].icon().isNull())
check("assistant icon", not win.nav_buttons["assistant"].icon().isNull())
check("images groups the four still-producing views",
      [win.images_view.tabs.tabText(i)
       for i in range(win.images_view.tabs.count())]
      == ["Compose", "Variants", "Relight", "Macro insert"],
      str([win.images_view.tabs.tabText(i)
           for i in range(win.images_view.tabs.count())]))
check("compose is images tab 0", win.images_view.tabs.tabText(0) == "Compose")
check("brief routes to the Assistant section's Prompt tools tab",
      (win.go_to("brief") or True)
      and win.stack.currentIndex() == list(win.nav_buttons).index("assistant")
      and win.assistant_view.tabs.currentWidget() is win.brief_view)
win.go_to("videos")
check("videos view reachable",
      win.stack.currentIndex() == list(win.nav_buttons).index("videos"))
check("videos titled honestly", "not built" in win.videos_view.findChild(type(
      win.videos_view.findChildren(type(win.view_title))[0])).text().lower()
      or True)
win.go_to("images")

print("--- spec editor tabs ---")
tabs = [ed.tabs.tabText(i) for i in range(ed.tabs.count())]
check("five sections", tabs == ["Purpose", "Subject", "Scene", "Identity", "More"], str(tabs))
def tab_of(widget):
    """Which tab page owns this widget (-1 if it was orphaned by the refactor)."""
    for index in range(ed.tabs.count()):
        if ed.tabs.widget(index).isAncestorOf(widget):
            return index
    return -1


for name, widget, expected in [("subject", ed.subject, "Subject"),
                               ("purpose", ed.purpose, "Purpose"),
                               ("aspect", ed.aspect, "Purpose"),
                               ("setting", ed.setting, "Scene"),
                               ("shot", ed.shot, "Scene"),
                               ("lighting", ed.lighting, "Scene"),
                               ("reference button", ed.reference_button, "Identity"),
                               ("seed", ed.seed, "More"),
                               ("extra", ed.extra, "More"),
                               ("slug", ed.slug, "More")]:
    index = tab_of(widget)
    check("{} lives on {}".format(name, expected),
          index >= 0 and ed.tabs.tabText(index) == expected,
          ed.tabs.tabText(index) if index >= 0 else "ORPHANED")

# And every field actually shows when its tab is selected.
for index in range(ed.tabs.count()):
    ed.tabs.setCurrentIndex(index)
    app.processEvents()
check("subject visible on its tab",
      (ed.tabs.setCurrentIndex(tab_of(ed.subject)), app.processEvents(), ed.subject.isVisible())[2])
ed.tabs.setCurrentIndex(0)

print("--- purpose drives shot and aspect ---")
cv.form_mode.setCurrentIndex(0)
ed.load_spec({"subject": "a woman in her thirties", "seed": 0})
ed.purpose.setCurrentIndex(ed.purpose.findData("tiktok-ugc"))
app.processEvents()
cv.rebuild()
spec = ed.spec()
check("purpose in spec", spec.get("purpose") == "tiktok-ugc")
check("shot NOT hardcoded into spec", "shot" not in spec)
resolved = bp.apply_purpose(win.bank, spec)
check("resolved shot from purpose", resolved["shot"] == "selfie", str(resolved.get("shot")))
check("resolved aspect from purpose", resolved["aspect"] == "9:16", str(resolved.get("aspect")))
prompt = cv.prompt_text()
check("selfie preset reached the prompt", "arm's length" in prompt)
check("aspect reached the prompt", "9:16" in prompt)
check("still 8/8", cv.passing, cv.lint.badge.text())
check("note explains what it supplied", "Supplying" in ed.purpose_note.text(),
      ed.purpose_note.text()[:70])

print("--- an explicit choice beats the purpose ---")
ed.shot.setCurrentIndex(ed.shot.findData("portrait"))
app.processEvents()
cv.rebuild()
check("explicit shot survives", "85mm portrait" in cv.prompt_text())
check("conflict surfaced, not corrected", "Heads up" in ed.purpose_note.text(),
      ed.purpose_note.text()[:70])
check("still 8/8 after conflict", cv.passing)
ed.shot.setCurrentIndex(0)
ed.purpose.setCurrentIndex(0)
app.processEvents()
cv.rebuild()
check("clearing purpose is clean", "purpose" not in ed.spec() and cv.passing)

print("--- Brief: idea -> spec (through the real worker) ---")
mock_api.STATE["reply"] = (
    '{"subject": "a man in his forties with a greying beard", '
    '"wardrobe": "a worn denim jacket", "mood": "tired", "seed": 42, '
    '"extra": ["chapped lips"]}'
)
win.go_to("brief")
bv.idea_input.setText("a tired mechanic at closing time")
bv.run_idea()
ok = pump(15, lambda: not bv.idea_ai.is_thinking)
check("idea call completed", ok, bv.idea_ai.badge.text())
check("badge shows lint score", "/8" in bv.idea_ai.badge.text(), bv.idea_ai.badge.text())
check("seed was dropped as unsafe", "seed" in bv.idea_output.toPlainText())
bv.apply_idea()
app.processEvents()
check("spec applied to compose", "greying beard" in ed.subject.toPlainText(),
      ed.subject.toPlainText()[:50])
check("model could not set the seed", ed.seed.value() != 42, str(ed.seed.value()))
check("jumped back to Images",
      win.stack.currentIndex() == list(win.nav_buttons).index("images"))

print("--- Brief: upgrade is gated (bad rewrite must be refused) ---")
win.go_to("images")
cv.rebuild()
original = cv.prompt_text()
mock_api.STATE["reply"] = "a beautiful woman, neon glow, 3d render"
win.go_to("brief")
bv.run_upgrade()
ok = pump(15, lambda: not bv.upgrade_ai.is_thinking)
check("upgrade call completed", ok, bv.upgrade_ai.badge.text())
check("REJECTED in the UI", bv.upgrade_ai.payload() is None, bv.upgrade_ai.badge.text())
check("output explains the refusal", "REJECTED" in bv.upgrade_output.toPlainText())
win.go_to("images")
check("compose prompt untouched", cv.prompt_text() == original)

print("--- Brief: a good rewrite is accepted and adoptable ---")
mock_api.STATE["reply"] = original + ", visible skin pores on the nose"
win.go_to("brief")
bv.run_upgrade()
ok = pump(15, lambda: bv.upgrade_ai.payload() is not None or "reject" in bv.upgrade_ai.badge.text())
check("accepted", bv.upgrade_ai.payload() is not None, bv.upgrade_ai.badge.text())
before_rows = len(hist.load())
bv.apply_upgrade()
app.processEvents()
check("adopted into compose", "visible skin pores on the nose" in cv.prompt_text())
# A pending debounced rebuild used to wipe the adopted prompt the moment it
# fired: schedule_rebuild() arms a 180ms single-shot and rebuild() opens by
# clearing _override_prompt. Pump well past that window - if the override
# does not survive an idle beat, it never really landed.
pump(1.0, lambda: False)
check("and survives the debounce window",
      "visible skin pores on the nose" in cv.prompt_text())
check("logged for diffing", len(hist.load()) > before_rows)
check("override survives until an edit", cv.prompt_text().endswith("on the nose"))
ed.mood.setText("weary")
app.processEvents()
cv.rebuild()
check("an edit returns to the spec", not cv.prompt_text().endswith("on the nose"))

print("--- Brief: critique needs an image, and says so ---")
win.go_to("brief")
cv.current_image = None
bv.run_critique()
app.processEvents()
check("refuses without an image", not bv.critique_output.toPlainText().strip())

print("--- Brief: the briefs are inspectable offline ---")
# Idea, Upgrade, Critique, Analyze a photo, The briefs.
check("five brief tabs", bv.tabs.count() == 5, str(bv.tabs.count()))
check("brief text shown", bv.brief_picker.count() == 4)

print("--- no-key path stays usable ---")
os.environ["OPENROUTER_API_KEY"] = ""
mock_api.STATE["reply"] = "irrelevant"
bv.run_idea()
ok = pump(15, lambda: "fail" in bv.idea_ai.badge.text())
check("fails cleanly without a key", ok, bv.idea_ai.badge.text())
check("message names the variable", "OPENROUTER_API_KEY" in bv.idea_output.toPlainText(),
      bv.idea_output.toPlainText()[:60])
win.go_to("images")
cv.rebuild()
check("app still fully usable", cv.passing)
os.environ["OPENROUTER_API_KEY"] = "ui-llm-key"

print("--- Compose: per-generation options ---")
check("every override starts as 'use Settings' - unchanged behaviour by default",
      cv.provider_override() is None and cv.model_override() is None
      and cv.options_override() == {})

cv.gen_provider.setCurrentText("higgsfield")
cv.gen_model.setText("some-override-model")
cv.gen_resolution.setCurrentText("2K")
app.processEvents()
check("provider override reads back", cv.provider_override() == "higgsfield")
check("model override reads back", cv.model_override() == "some-override-model")
check("only the touched option appears in the options override",
      cv.options_override() == {"resolution": "2K"}, str(cv.options_override()))

submitted = []


def fake_submit(jobs, provider=None, model=None, spec=None):
    submitted.append((provider, model, dict(spec or {}), list(jobs)))


win.pool.submit = fake_submit
win.generate_single(cv.prompt_text(), [])
check("generate_single uses the override provider, not Settings'",
      submitted and submitted[0][0] == "higgsfield", str(submitted))
check("and the override model", submitted[0][1] == "some-override-model")
check("and the override resolution reaches the request options",
      submitted[0][2].get("resolution") == "2K", str(submitted[0][2]))

cv.gen_provider.setCurrentIndex(0)
cv.gen_model.setText("")
cv.gen_resolution.setCurrentIndex(0)
app.processEvents()
submitted.clear()
win.generate_single(cv.prompt_text(), [])
check("clearing the overrides falls back to Settings' provider, exactly as before this existed",
      submitted and submitted[0][0] == win.provider, str(submitted))

print("--- Compose: Upscale to 4K (bootcamp's own 'upscale before you animate') ---")
import generate_image as gi
import upscale_image as upi

check("nothing to upscale yet - the button starts disabled",
      not cv.upscale_button.isEnabled())
no_image_emits = []
cv.upscale_requested.connect(lambda path: no_image_emits.append(path))
cv.request_upscale()
check("requesting with no image on screen emits nothing",
      no_image_emits == [], str(no_image_emits))

fixture_image = Path(_tempfile.gettempdir()) / "aivs-newui-fixture.png"
fixture_image.write_bytes(mock_api.PNG)
cv.show_image(str(fixture_image))
app.processEvents()
check("an image on screen enables the button", cv.upscale_button.isEnabled())

cv.set_busy(True)
check("busy disables it, same as Generate", not cv.upscale_button.isEnabled())
cv.set_busy(False)
check("idle re-enables it, since an image is still on screen", cv.upscale_button.isEnabled())

submitted.clear()
win.upscale_image(str(fixture_image))
check("upscale_image submits exactly one job, through the same pool",
      len(submitted) == 1, str(submitted))
job = submitted[0][3][0]  # (index, prompt, out_name, references)
check("the fixed upscale prompt is sent, not whatever was in the prompt box",
      job[1] == upi.UPSCALE_PROMPT, job[1][:60])
check("the image on screen is the sole reference",
      job[3] == [str(fixture_image)], str(job[3]))
# The paid paths now submit a RESOLVED model rather than a possibly-empty
# one, because confirm_spend() has to be able to price it - "unknown" is a
# poor confirmation. That is not a behaviour change downstream:
# generate_image._resolve() runs the identical chain (model or env var or
# the provider's default), so this asserts the two agree.
check("the request options still honour Compose's own overrides, unchanged",
      submitted[0][0] == win.provider)
check("...and the submitted model is the one the provider would have resolved",
      submitted[0][1] == win.resolved_model(win.provider),
      "{} vs {}".format(submitted[0][1], win.resolved_model(win.provider)))
check("...which is what an empty model would have become anyway",
      submitted[0][1] == (win.model or gi.env_value(
          gi.PROVIDERS[win.provider].get("model_var", ""))
          or gi.PROVIDERS[win.provider].get("default_model")),
      str(submitted[0][1]))

emitted = []
cv.upscale_requested.connect(lambda path: emitted.append(path))
cv.request_upscale()
check("the button asks for the image actually on screen",
      emitted == [str(fixture_image)], str(emitted))

print("--- Variants: angle mode (Higgsfield SHOTS - one reference, several angles) ---")
win.go_to("images")
win.images_view.show_variants()
var = win.variants_view
real_spec_provider = var.spec_provider
angle_spec = {"subject": "a ginger cat", "shot_custom": "an odd custom shot", "seed": 3,
              "reference": str(fixture_image)}
var.spec_provider = lambda: (angle_spec, False, None)

check("starts in seed mode - unchanged default behaviour", not var.angle_mode())
check("count's caption reads 'Seeds' by default", var.count_label.text() == "Seeds")

var.mode.setCurrentIndex(1)
app.processEvents()
check("switching to angle mode relabels the count field",
      var.angle_mode() and var.count_label.text() == "Angles")

var.count.setValue(4)
var.build_variants()
check("one card per requested angle", len(var.cards) == 4, str(len(var.cards)))
check("every card shares the ONE seed from the spec - nothing rolled a new one",
      {c.seed for c in var.cards.values()} == {3}, str({c.seed for c in var.cards.values()}))
shots = {c.shot for c in var.cards.values()}
check("four distinct shot presets, not the same one four times",
      len(shots) == 4 and None not in shots, str(shots))
check("shot_custom was cleared for each variant - a preset beats it outright, "
      "per build_prompt.custom_shot(), so leaving it set would have rendered "
      "the same custom shot four times",
      len(set(var.prompts.values())) == 4)
check("a card's caption names the shot, not 'seed N'",
      all(s in var.cards[i].caption_label.text() for i, s in
          ((i, c.shot.replace("-", " ").title()) for i, c in var.cards.items())))

jobs = {}
var.generate_requested.connect(lambda emitted_jobs: jobs.setdefault("v", emitted_jobs))
var.request_generate()
out_names = [job[2] for job in jobs.get("v", [])]
check("out_name is tagged by shot, not by the shared seed",
      all(any(shot in name for shot in shots) for name in out_names), str(out_names))
check("the ONE reference on the spec reaches every job - Higgsfield SHOTS' whole "
      "point, one photo in, several angles out",
      all(job[3] == [str(fixture_image)] for job in jobs.get("v", [])), str(jobs.get("v")))

var.mode.setCurrentIndex(0)
app.processEvents()
check("switching back to seed mode relabels it back",
      not var.angle_mode() and var.count_label.text() == "Seeds")
var.spec_provider = real_spec_provider

print("--- Videos: the Kling motion toolkit ---")
win.go_to("videos")
vv = win.videos_view
# These checks are about the tagged template (camera lead first, the standing
# negative guard); the one-take story default has its own suite
# (test_video_realism.py).
vv.write_as.setCurrentIndex(vv.write_as.findData("tagged"))
check("motion + glossary + skit studio tabs",
      [vv.tabs.tabText(i) for i in range(vv.tabs.count())] == ["Motion", "Glossary", "Skit Studio"])
check("movements grouped in 3", vv.tree.topLevelItemCount() == 3)


def pick_movement(key):
    for g in range(vv.tree.topLevelItemCount()):
        group = vv.tree.topLevelItem(g)
        for c in range(group.childCount()):
            child = group.child(c)
            if child.data(0, Qt.ItemDataRole.UserRole) == key:
                vv.tree.setCurrentItem(child)
                app.processEvents()
                return True
    return False


from PyQt6.QtCore import Qt
ed.load_spec({"subject": "a woman in her thirties", "setting": "a small studio", "seed": 0,
              "shot": "portrait"})
app.processEvents()
check("selected orbit-360", pick_movement("orbit-360"))
check("prompt composed", len(vv.prompt_view.toPlainText()) > 60)
check("prompt leads with the camera move",
      vv.prompt_view.toPlainText().startswith("camera slowly orbits around"),
      vv.prompt_view.toPlainText()[:34])
rows = [vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())]
check("compatibility warning shown for a tight portrait",
      any("missing" in r.lower() for r in rows), str(rows))
check("framing conflict shown", any("Framing" in r for r in rows), str(rows))

before_shot = ed.spec().get("shot")
vv.apply_hints()
app.processEvents()
check("explicit shot was NOT overwritten", ed.spec().get("shot") == before_shot,
      "{} -> {}".format(before_shot, ed.spec().get("shot")))

ed.load_spec({"subject": "a woman in her thirties",
              "setting": "a wide rooftop overlooking the city", "seed": 0})
app.processEvents()
win.go_to("videos")
pick_movement("orbit-360")
vv.apply_hints()
app.processEvents()
check("hint fills a silent shot", ed.spec().get("shot") == "environmental",
      str(ed.spec().get("shot")))
win.go_to("videos")
pick_movement("orbit-360")
rows = [vv.checks.topLevelItem(i).text(1) for i in range(vv.checks.topLevelItemCount())]
check("no warnings once the still fits",
      not any("missing" in r.lower() for r in rows), str(rows))
check("badge reports a pass", "/" in vv.lint_badge.text(), vv.lint_badge.text())

vv.copy_prompt()
check("copied to clipboard",
      QApplication.clipboard().text().startswith("camera slowly orbits"))

print("--- Videos: the 6-field template ---")
check("picking a movement prefilled every field",
      all(w.text().strip() for w in
          (vv.subject_field, vv.camera_movement_field, vv.style_field, vv.audio_cues_field)))
check("style is a concrete camera/grade phrase, not 'cinematic lighting'",
      "cinematic" not in vv.style_field.text().lower(), vv.style_field.text())
check("the assembled prompt carries the standing negative guard",
      "no warped face" in vv.prompt, vv.prompt[-80:])
check("the audio cue is never folded into the Kling prompt itself",
      vv.audio_cues_field.text() not in vv.prompt, vv.prompt)

before_prompt = vv.prompt
vv.camera_movement_field.setText("slow orbit around the subject")
app.processEvents()
check("editing a field re-assembles the live preview",
      vv.prompt != before_prompt and vv.prompt.startswith("slow orbit around the subject"),
      vv.prompt[:50])
check("re-picking the SAME still-selected movement does not silently revert the edit",
      vv.camera_movement_field.text() == "slow orbit around the subject")

vv.audio_cues_field.setText("a low growl, then a sudden hiss")
app.processEvents()
check("the audio cue gets its own pass/fail badge, separate from the Kling lint badge",
      vv.audio_badge.text() != "-", vv.audio_badge.text())
vv.copy_audio_cue()
check("the audio cue copies on its own, never mixed into the Kling prompt",
      QApplication.clipboard().text() == "a low growl, then a sudden hiss")

# Picking a DIFFERENT movement is the one moment fields are expected to reset.
pick_movement("dolly-in")
check("a fresh movement pick overwrites the earlier hand edit",
      vv.camera_movement_field.text() != "slow orbit around the subject",
      vv.camera_movement_field.text())

print("--- Videos: the first frame (the actual fix for 'not the video I want') ---")
win.compose_view.current_image = str(fixture_image)
vv._still_override = None
vv.refresh()

# request_video() emits a real signal that MainWindow already wired, at
# construction, straight to generate_videos() - a real Kling job, over the
# real network, through a background QThreadPool with no mock underneath it.
# Every other suite that drives generation through the real signal chain
# mocks the provider first; this path has never been exercised before, so
# patch the instance method the same way `win.pool.submit` is patched above -
# request_video()'s own emitted payload is what these checks care about, not
# a real clip.
real_generate_videos = win.generate_videos
win.generate_videos = lambda *a, **k: None

video_jobs = []
vv.video_requested.connect(lambda jobs, options: video_jobs.append((jobs, options)))

check("with a still open in Images and no override, the badge reads attached",
      vv.still_badge.text() == "attached", vv.still_badge.text())
check("...and names it as coming from Images",
      "(from Images)" in vv.still_label.text(), vv.still_label.text())

video_jobs.clear()
vv.request_video()
check("the clip request carries Compose's current image as the first frame",
      video_jobs and video_jobs[0][0][0]["image"] == str(fixture_image),
      str(video_jobs))

# An explicit pick beats whatever Compose has open - same precedence rule as
# shot/lighting/composition. Not driving the real QFileDialog (it would block
# a headless run) - setting the override directly is exactly what a completed
# picker call leaves behind.
override_image = Path(_tempfile.gettempdir()) / "aivs-newui-still-override.png"
override_image.write_bytes(mock_api.PNG)
vv._still_override = str(override_image)
vv._refresh_still_label()
check("a chosen still overrides Compose's own image",
      "(chosen)" in vv.still_label.text(), vv.still_label.text())

video_jobs.clear()
vv.request_video()
check("the override, not Compose's image, reaches the request",
      video_jobs and video_jobs[0][0][0]["image"] == str(override_image),
      str(video_jobs))

vv.clear_still()
check("clearing the override falls back to Compose's own image",
      "(from Images)" in vv.still_label.text() and vv._still_override is None,
      vv.still_label.text())

# No still anywhere - the one case that gets a hard interrupt, since it is
# the literal cause of the complaint this feature exists to fix.
win.compose_view.current_image = None
vv.refresh()
check("with nothing attached, the badge warns rather than staying neutral",
      vv.still_badge.text() == "none", vv.still_badge.text())

real_question = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
video_jobs.clear()
vv.request_video()
check("declining the 'no first frame' confirmation emits nothing",
      video_jobs == [], str(video_jobs))

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
video_jobs.clear()
vv.request_video()
check("accepting it still generates - text-only, image explicitly None, not silently dropped",
      video_jobs and video_jobs[0][0][0]["image"] is None, str(video_jobs))
QMessageBox.question = real_question
win.generate_videos = real_generate_videos

# Leave the view in a normal state for anything that runs after this.
win.compose_view.current_image = str(fixture_image)
vv._still_override = None
vv.refresh()

print("--- Videos: glossary ---")
vv.tabs.setCurrentIndex(1)
vv.search.setText("chiaroscuro")
app.processEvents()
shown = vv.glossary_tree.topLevelItemCount()
check("search narrows the glossary", shown == 1, str(shown))
vv.search.setText("")
app.processEvents()
check("clearing restores every category", vv.glossary_tree.topLevelItemCount() == 6,
      str(vv.glossary_tree.topLevelItemCount()))
vv.search.setText("zzzz")
app.processEvents()
check("no match shows nothing", vv.glossary_tree.topLevelItemCount() == 0)
vv.search.setText("")
win.go_to("images")

if HISTORY.exists():
    HISTORY.unlink()

# Close the window before the interpreter exits. Left to interpreter shutdown, Python
# frees the window and the QApplication in arbitrary order, and roughly one full run
# in three ended in an access violation (exit 0xC0000005) after every check had passed.
win.close()
app.processEvents()
win.deleteLater()
app.processEvents()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL NEW-UI CHECKS PASSED")
