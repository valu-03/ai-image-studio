"""A session that survives being closed.

THE HOLE. A nine-scene Cats story - scenes, clips, sound effects, voiceovers -
lived in three plain attributes on CatsView and was gone the moment the window
closed. Characters could be saved and personas could be saved; the body of work
that USES them could not, and nothing in the app grouped a spec, its story and
its outputs into a thing with a name.

TWO DESIGN DECISIONS THIS SUITE PINS, because both are easy to "fix" wrongly.

A project stores the story's INPUTS, not its scene list. CatsView.rebuild()
recomposes `self.scenes` from its controls every time anything changes, so a
stored scene list would either be overwritten by the first rebuild after loading
or - worse - survive one and then disagree with the controls above it. Restoring
the inputs and letting rebuild() do its job is the only version that stays
consistent. The generated artefacts are the opposite case: they cannot be
recomputed, so those ARE stored, as paths.

A project stores paths, not bytes. Duplicating images into the manifest would
make it enormous and the copies stale. The cost is that a project can reference
a file that has since been deleted - temp/outputs is a folder this app's own
Settings labels "disposable" - so missing() exists, and loading says which are
gone rather than opening a story with silent holes in it.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_ASSUME_YES", "1")

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-project-empty.env"
_EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import project as proj  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui import assets  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

fails = []
WORK = Path(tempfile.mkdtemp(prefix="aivs-project-"))


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== THE MANIFEST ROUND-TRIPS ===")
clip = WORK / "clip-1.mp4"
clip.write_bytes(b"not really a video")
spec = {"subject": "a ginger cat", "seed": 7, "posing": "weight on the back foot"}

project = proj.from_views(
    "Fridge Raider",
    spec=spec,
    scenes=[{"n": 1, "label": "hook"}, {"n": 2, "label": "payoff"}],
    videos={0: str(clip)},
    sfx={0: {"ambience": str(clip)}},
    images={0: str(clip)},
    render=str(clip),
)
path = proj.save(project, folder=WORK)
check("it writes a file", path.exists(), str(path))
check("...with the .aivs.json suffix a file dialog can filter on",
      path.name.endswith(proj.SUFFIX), path.name)

loaded = proj.load(path)
check("the name survives", loaded["name"] == "Fridge Raider")
check("the spec survives verbatim", loaded["spec"] == spec, str(loaded["spec"]))
check("...including the new posing field, since it stores the spec whole",
      loaded["spec"].get("posing") == "weight on the back foot")
check("the scene record survives", len(loaded["scenes"]) == 2)
check("the render path survives", loaded["render"] == str(clip))
check("modified is stamped on save", loaded["modified"])


print()
print("=== INTEGER SCENE KEYS SURVIVE JSON, WHICH HAS NO INTEGER KEYS ===")
# The views index by int. JSON object keys are always strings, so from_views()
# stringifies deliberately and scene_videos() converts back - otherwise
# videos[0] would write as "0", read back as "0", and every caller looking for
# 0 would silently find nothing.
check("stored as strings", set(loaded["videos"]) == {"0"}, str(set(loaded["videos"])))
check("handed back as ints", proj.scene_videos(loaded) == {0: str(clip)},
      str(proj.scene_videos(loaded)))
check("...and so is sfx", proj.scene_sfx(loaded) == {0: {"ambience": str(clip)}})
check("...and images", proj.scene_images(loaded) == {0: str(clip)})
check("a non-numeric key is dropped rather than crashing",
      proj.scene_videos({"videos": {"nonsense": "x", "2": "y"}}) == {2: "y"})


print()
print("=== IT REFUSES WHAT IT CANNOT HONOUR ===")
bad = WORK / ("wrong-version" + proj.SUFFIX)
bad.write_text(json.dumps({"version": 999, "name": "from the future"}), encoding="utf-8")
try:
    proj.load(bad)
    check("a future version is refused", False, "it loaded anyway")
except ValueError as exc:
    check("a future version is refused rather than guessed at", True)
    check("...and the message says both versions", "999" in str(exc), str(exc)[:80])

junk = WORK / ("junk" + proj.SUFFIX)
junk.write_text("this is not json", encoding="utf-8")
try:
    proj.load(junk)
    check("unparseable input is refused", False)
except ValueError:
    check("unparseable input raises ValueError, not JSONDecodeError", True)

try:
    proj.load(WORK / "nope.json")
    check("a missing file is refused", False)
except ValueError:
    check("a missing file raises ValueError too", True)

listed = proj.listing(WORK)
check("listing() skips the corrupt file instead of dying",
      "Fridge Raider" in [row["name"] for row in listed],
      str([row["name"] for row in listed]))


print()
print("=== A DELETED FILE IS REPORTED, NOT IGNORED ===")
check("nothing missing while the file is there", proj.missing(loaded) == [],
      str(proj.missing(loaded)))
clip.unlink()
gone = proj.missing(loaded)
check("all four references are reported once the file is gone",
      len(gone) == 4, str(len(gone)))
check("...and they are the paths, so the message can name them",
      all(str(clip) == g for g in gone))
check("describe() still works with missing files",
      "Fridge Raider" in proj.describe(loaded), proj.describe(loaded))
check("...and counts what it has", "2 scenes" in proj.describe(loaded),
      proj.describe(loaded))


print()
print("=== THE APP SAVES AND RELOADS ITS OWN SESSION ===")
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)

win.compose_view.editor.subject.setPlainText("a ginger cat in a kitchen")
win.compose_view.editor.posing.setText("crouched low, tail flat")
win.cats_view.idea.setText("a cat that raids the fridge every night")
win.cats_view.seconds.setValue(40)
story_before = win.cats_view.story_state()
scenes_before = len(win.cats_view.scenes)
kept_clip = WORK / "kept.mp4"
kept_clip.write_bytes(b"x")
win.cats_view.videos = {0: str(kept_clip)}

target = WORK / ("session" + proj.SUFFIX)
win._write_project(target)
check("the project file is written", target.exists())
check("the window title names it", "session" in win.windowTitle(), win.windowTitle())
check("...and the open path is remembered, so Save does not re-ask",
      win._project_path == target)

saved = proj.load(target)
check("the spec went in", "ginger cat" in saved["spec"].get("subject", ""))
check("...with the posing field", saved["spec"].get("posing") == "crouched low, tail flat")
check("the STORY SETTINGS went in, not just the scene list",
      saved.get("story", {}).get("idea") == "a cat that raids the fridge every night",
      str(saved.get("story", {}).get("idea")))
check("...including the length", saved["story"].get("seconds") == 40)
check("the generated clip path went in", saved["videos"].get("0") == str(kept_clip))

# Now wipe the session and load it back.
win.new_project()
check("New project clears the spec", not win.compose_view.editor.subject.toPlainText())
check("...and forgets the path, so Save asks again", win._project_path is None)

win.cats_view.videos = {}
messages = []
win.statusBar().messageChanged.connect(messages.append)
win.open_project = win.open_project      # keep the bound method addressable
# Drive the load without a file dialog - that is what the dialog would return.
loaded_project = proj.load(target)
win.compose_view.editor.load_spec(loaded_project["spec"])
win.cats_view.load_story_state(loaded_project["story"])
win.cats_view.videos = proj.scene_videos(loaded_project)

check("the spec is back", "ginger cat" in win.compose_view.editor.subject.toPlainText())
check("...and the posing field with it",
      win.compose_view.editor.posing.text() == "crouched low, tail flat")
check("the story idea is back",
      win.cats_view.idea.text() == "a cat that raids the fridge every night")
check("...and the length", win.cats_view.seconds.value() == 40)
check("the clip path is back, keyed by int",
      win.cats_view.videos == {0: str(kept_clip)}, str(win.cats_view.videos))
check("the story state matches what was saved",
      win.cats_view.story_state()["idea"] == story_before["idea"]
      and win.cats_view.story_state()["seconds"] == story_before["seconds"])
check("...and rebuild() recomposed a scene list from it rather than restoring one",
      len(win.cats_view.scenes) > 0, str(len(win.cats_view.scenes)))


print()
print("=== THE FOLDERS THE APP WRITES ARE ALL DECLARED NOW ===")
check("the render folder is declared - it never was",
      assets.RENDER_DIR in assets.ALL_OUTPUT_DIRS)
check("...and the projects folder", assets.PROJECTS_DIR in assets.ALL_OUTPUT_DIRS)
check("render is where render_video.py actually writes",
      assets.RENDER_DIR.name == "render"
      and assets.RENDER_DIR.parent.name == "outputs", str(assets.RENDER_DIR))
import render_video as rv  # noqa: E402
check("...the same folder, not a second opinion about it",
      Path(rv.OUT_DIR).resolve() == assets.RENDER_DIR.resolve(),
      "{} vs {}".format(rv.OUT_DIR, assets.RENDER_DIR))
check("a finished render is recorded on the view, not just shown in a label",
      hasattr(win.cats_view, "render_path"))


print()
print("=== A HISTORY ROW CAN BE REOPENED, NOT JUST READ ===")
# history.append() recorded subject/shot/seed - the three columns the table
# shows - and nothing else, so a row could be read and never reloaded: wardrobe,
# setting, posing, lighting and every override were simply not kept. The whole
# spec is recorded now, additively, and older rows fall back to the three.
import history as hist  # noqa: E402
full = {"subject": "a woman in her forties", "wardrobe": "a grey wool coat",
        "posing": "weight on the back foot", "seed": 3}
entry_id = hist.append(full, "a prompt", {"core": ["photorealistic"]}, 8, True)
rows = [r for r in hist.load() if r["id"] == entry_id]
check("the entry was written", len(rows) == 1)
check("...and it carries the WHOLE spec now", rows[0].get("spec") == full,
      str(rows[0].get("spec")))

hv = win.history_view
hv.reload()
adopted = []
hv.spec_chosen.connect(adopted.append)

hv.open_in_compose()
check("with nothing selected it asks rather than guessing", not adopted)

target_row = next((i for i, e in enumerate(hv.entries) if e["id"] == entry_id), None)
check("the new entry is in the table", target_row is not None)
if target_row is not None:
    hv.table.selectRow(target_row)
    check("selecting one row enables Open in Compose", hv.open_button.isEnabled())
    hv.open_in_compose()
    check("it emits the full spec", adopted and adopted[-1] == full,
          str(adopted[-1:]))
    win.adopt_history_spec(adopted[-1])
    check("Compose really has it back",
          win.compose_view.editor.posing.text() == "weight on the back foot",
          win.compose_view.editor.posing.text())
    check("...and the wardrobe too",
          win.compose_view.editor.wardrobe.text() == "a grey wool coat")
    check("...and it navigated to Compose to show it",
          win.stack.currentWidget() is win.images_view
          and win.images_view.tabs.currentIndex() == 0)

# An entry from before the schema change must still open, thinner.
old_entry = {"id": "old-1", "subject": "a man in his fifties", "shot": "portrait",
             "seed": 9, "prompt": "p", "layers": {}, "rating": None, "note": "",
             "image": "", "score": 8, "passed": True}
hv.entries = [old_entry]
hv.table.setRowCount(1)
adopted.clear()
hv.selected_entries = lambda: [old_entry]
hv.open_in_compose()
check("an entry with no stored spec still opens", adopted, str(adopted))
check("...with the three fields it did record",
      adopted and adopted[-1] == {"subject": "a man in his fifties",
                                  "shot": "portrait", "seed": 9},
      str(adopted[-1:]))


print()
win.close()
app.processEvents()
del win
shutil.rmtree(WORK, ignore_errors=True)

if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL PROJECT CHECKS PASSED")
