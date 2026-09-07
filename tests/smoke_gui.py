"""Full offscreen smoke test: all five features through the real UI."""
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
# A modal "are you sure" nobody can click is a hang, not a safeguard, so the
# spend confirmation is answered for us. It still prints the estimate.
os.environ.setdefault("AIVS_ASSUME_YES", "1")

import mock_api

PORT = 8793
mock_api.serve(PORT)
os.environ["AIVS_API_BASE"] = "http://127.0.0.1:{}/text".format(PORT)
os.environ["KIE_API_KEY"] = "smoke-key"
# Generation is an async poll now; don't sleep 3s per check in a smoke test.
os.environ["AIVS_POLL_INTERVAL"] = "0"
os.environ["OPENROUTER_API_KEY"] = "smoke-llm-key"

# Wherever history.py has actually been pointed, which is NOT always the real
# log: AIVS_HISTORY_FILE redirects it. Keeping a second, hardcoded idea of that
# path meant this suite deleted the user's live log while the app under test
# wrote somewhere else entirely - and read back a temp file that accumulated
# across runs, so "exactly one winner" became two, then three.
HISTORY = Path(os.environ.get("AIVS_HISTORY_FILE")
               or (ROOT / "temp" / "outputs" / "history.jsonl"))
backup = HISTORY.read_bytes() if HISTORY.exists() else None

# Everything already in the output folder, so the cleanup at the end can remove
# only what this run created. It used to delete *.png outright, which threw away
# the user's real generations along with the mock's 1x1 test pixels.
IMAGES_DIR = ROOT / "temp" / "outputs" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
PRE_EXISTING = set(p.name for p in IMAGES_DIR.glob("*.png"))
if HISTORY.exists():
    HISTORY.unlink()

# Same reasoning as AIVS_ENV_FILE/AIVS_HISTORY_FILE above, one layer further
# in: MainWindow reads AIVS_SETTINGS_APP at import time to pick which
# QSettings key it opens. Without this, every GUI test read AND WROTE the
# user's real saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from ui.theme import ThemeManager
import history as hist

# A modal nobody can click is a hang, not a safeguard - same reasoning as
# AIVS_ASSUME_YES for the cost-confirmation dialog, here for
# ComposeView.confirm_if_failing()'s "this prompt hasn't passed" one. Belt
# and braces: the fixed spec below is chosen to score 8/8 so this should
# never actually fire, but a suite that can hang silently on a future change
# is worse than one that answers "proceed anyway" and lets the real checks
# below catch whatever is actually wrong.
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def pump(seconds=6, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return until() if until else True


print("--- shell (spec 1: rail + top bar + stack) ---")
from ui.main_window import NAV_ITEMS
check("a nav button per section", len(win.nav_buttons) == len(NAV_ITEMS),
      str(len(win.nav_buttons)))
check("a stacked view per section", win.stack.count() == len(NAV_ITEMS),
      str(win.stack.count()))
check("images selected by default", win.nav_buttons["images"].isChecked())
check("top bar has search", win.search is not None)
check("nav icons load", not win.nav_buttons["images"].icon().isNull())
win.go_to("insights")
check("nav switches stack",
      win.stack.currentIndex() == list(win.nav_buttons).index("insights"),
      str(win.stack.currentIndex()))
check("title follows nav", win.view_title.text() == "Insights", win.view_title.text())
win.go_to("images")

print("--- palette (spec 2) ---")
sheet = app.styleSheet()
for hexv in ["#0B0E14", "#151A24", "#38BDF8", "#34D399", "#1A2333", "#F8FAFC", "#94A3B8"]:
    check("palette {}".format(hexv), hexv in sheet)
check("12px card radius", "border-radius: 12px" in sheet)

print("--- compose + live lint ---")
# QSettings persists the last form mode; pin it so the run is deterministic.
win.compose_view.form_mode.setCurrentIndex(0)
# A FIXED spec, not "whichever character happens to be first in the user's
# real library" - `library.setCurrentRow(0); load_selected()` used to load
# that, and a real saved character with a shot_custom naming no camera
# device legitimately scores 7/8 (tools/README.md documents that this is the
# gate working correctly, not a bug) - which used to hang this whole suite
# outright (see the QMessageBox.question patch above) the moment the user's
# library held anything other than an empty one. Same rule as everywhere
# else a test must not depend on the user's live data.
win.compose_view.editor.load_spec({"subject": "a woman in her thirties", "seed": 0})
win.compose_view.rebuild()
check("prompt composed", len(win.compose_view.prompt_text()) > 100)
check("passes 8/8", win.compose_view.passing, win.compose_view.lint.badge.text())
check("score exposed", win.compose_view.lint.score == 8)

print("--- feature 1+3: generation via QThreadPool (mock API) ---")
before = set(p.name for p in (ROOT / "temp" / "outputs" / "images").glob("*.png"))
win.compose_view.request_generate()
ok = pump(10, lambda: not win.pool.busy)
check("batch completed", ok)
after = set(p.name for p in (ROOT / "temp" / "outputs" / "images").glob("*.png"))
new = after - before
check("image produced", len(new) >= 1, str(sorted(new))[:80])
check("preview populated", win.compose_view.current_image is not None)
check("rating enabled after image", win.compose_view.rating.isEnabled())
check("ui not blocked (badge idle)", win.busy_badge.text() == "idle", win.busy_badge.text())

print("--- feature 2: rating writes through to history ---")
win.compose_view.rating.set_value(5, emit=True)
entries = hist.load()
rated = [e for e in entries if e.get("rating") == 5]
check("rating persisted", len(rated) >= 1)
check("image linked to entry", any(e.get("image") for e in rated))

print("--- feature 3: variant grid ---")
win.go_to("images")
win.images_view.show_variants()
win.variants_view.count.setValue(4)
win.variants_view.build_variants()
check("4 thumb cards", len(win.variants_view.cards) == 4, str(len(win.variants_view.cards)))
check("distinct seeds", len({c.seed for c in win.variants_view.cards.values()}) == 4)
win.variants_view.request_generate()
ok = pump(20, lambda: not win.pool.busy)
check("batch completed", ok)
loaded = sum(1 for c in win.variants_view.cards.values() if getattr(c, "image_path", None))
check("all 4 images returned", loaded == 4, "{}/4".format(loaded))
win.variants_view.select_card(2)
check("selection marks card", win.variants_view.cards[2].property("selected") == "true")
win.variants_view.adopt_selected()
entries = hist.load()
winners = [e for e in entries if e.get("note") == "picked as variant winner"]
losers = [e for e in entries if e.get("note") == "not picked"]
check("winner rated 5", len(winners) == 1 and winners[0]["rating"] == 5)
check("losers rated 2", len(losers) == 3, str(len(losers)))
check("seed adopted into compose", win.compose_view.editor.seed.value() == winners[0]["seed"])

print("--- feature 3b: variant grid, angle mode (Higgsfield SHOTS: one seed, N shots) ---")
# A synthetic spec_provider, not editor.load_spec() - the real Compose editor's
# state must survive intact for feature 4 right after this, the same
# "a test must not corrupt state other suites depend on" discipline this
# project already holds run_all.py's history/pricing seams to.
angle_spec = {"subject": "a ginger cat", "shot_custom": "an odd custom shot", "seed": 7}
real_spec_provider = win.variants_view.spec_provider
win.variants_view.spec_provider = lambda: (angle_spec, False, None)
win.variants_view.mode.setCurrentIndex(1)  # "N angles, same seed"
win.variants_view.count.setValue(4)
win.variants_view.build_variants()
check("4 thumb cards", len(win.variants_view.cards) == 4, str(len(win.variants_view.cards)))
check("one shared seed, not four",
      len({c.seed for c in win.variants_view.cards.values()}) == 1)
check("four distinct shot presets",
      len({c.shot for c in win.variants_view.cards.values()}) == 4,
      str({c.shot for c in win.variants_view.cards.values()}))
check("shot_custom was cleared, or every 'angle' would be the same custom shot",
      len(set(win.variants_view.prompts.values())) == 4)
win.variants_view.request_generate()
ok = pump(20, lambda: not win.pool.busy)
check("batch completed", ok)
loaded = sum(1 for c in win.variants_view.cards.values() if getattr(c, "image_path", None))
check("all 4 images returned", loaded == 4, "{}/4".format(loaded))
win.variants_view.mode.setCurrentIndex(0)  # back to seed mode, for anything that follows
win.variants_view.spec_provider = real_spec_provider

print("--- feature 2: learned weighting ---")
w = hist.weights()
check("weights derived", len(w) > 0, "{} terms".format(len(w)))
check("weights differentiate", len(set(round(v, 3) for v in w.values())) > 1)
win.go_to("insights")
win.insights_view.reload()
check("insights populated", win.insights_view.tree.topLevelItemCount() > 0)
check("summary shows rated count", "rated" in win.insights_view.summary.text(),
      win.insights_view.summary.text())
win.insights_view.learned.setChecked(True)
check("learned toggle reaches compose", win.compose_view.use_learned)

print("--- feature 5: history + diff ---")
win.go_to("history")
win.history_view.reload()
check("history table populated", win.history_view.table.rowCount() >= 5,
      str(win.history_view.table.rowCount()))
from PyQt6.QtCore import QItemSelectionModel
table = win.history_view.table
table.clearSelection()
model = table.selectionModel()
for row in (0, 1):
    model.select(
        table.model().index(row, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )
app.processEvents()
sel = win.history_view.selected_entries()
check("two rows selected", len(sel) == 2, str(len(sel)))
check("diff button enabled", win.history_view.diff_button.isEnabled())
win.history_view.show_diff()
text = win.history_view.detail.toPlainText()
check("diff rendered", ("+ " in text or "- " in text or "identical" in text), text[:60])

print("--- feature 4: consistency / identity lock ---")
win.go_to("images")
ref = sorted((ROOT / "temp" / "outputs" / "images").glob("variant-*.png"))
check("have a reference candidate", len(ref) > 0)
if ref:
    win.compose_view.editor.set_reference(str(ref[0]))
    win.compose_view.rebuild()
    prompt = win.compose_view.prompt_text()
    check("identity lock in prompt", "exact same person" in prompt)
    check("lock cites the reference", "reference image" in prompt)
    check("reference label updated", "locked to" in win.compose_view.reference_label.text())
    check("still passes lint", win.compose_view.passing, win.compose_view.lint.badge.text())
    check("compact lock tail", "identity locked" in prompt)
    win.compose_view.form_mode.setCurrentIndex(1)
    win.compose_view.rebuild()
    check("detailed lock sentence", "must not be restyled" in win.compose_view.prompt_text())
    check("detailed still passes", win.compose_view.passing)
    win.compose_view.form_mode.setCurrentIndex(0)
    win.compose_view.rebuild()
    spec = win.compose_view.editor.spec()
    check("spec carries reference", spec.get("reference") == str(ref[0]))
    check("spec sets lock_identity", spec.get("lock_identity") is True)
    win.compose_view.clear_reference()
    win.compose_view.rebuild()
    check("clearing removes lock", "exact same person" not in win.compose_view.prompt_text())

print("--- settings: key presence never shows a value ---")
win.go_to("settings")
win.settings_view.refresh_key_state()
badge = win.settings_view.key_badge.text()
check("shows presence", "KIE_API_KEY" in badge, badge)
check("never shows the key", "smoke-key" not in badge)

print("--- search filters ---")
win.search.setText("zzz-no-match")
app.processEvents()
check("history filtered to none", win.history_view.table.rowCount() == 0,
      str(win.history_view.table.rowCount()))
win.search.setText("")
app.processEvents()
check("filter cleared", win.history_view.table.rowCount() > 0)

print("--- theme toggle ---")
theme.toggle()
app.processEvents()
check("light applied", theme.name == "light")
check("light sheet swapped", "#F7F9FC" in app.styleSheet())
theme.toggle()
check("back to dark", theme.name == "dark" and "#0B0E14" in app.styleSheet())

# Clean up only the images this run produced. Anything that was already here
# is the user's, and temp/outputs being "disposable" is not a licence for a test
# to dispose of it.
for p in IMAGES_DIR.glob("*.png"):
    if p.name not in PRE_EXISTING:
        p.unlink()
check("pre-existing images were not deleted",
      all((IMAGES_DIR / name).exists() for name in PRE_EXISTING),
      "{} were here before".format(len(PRE_EXISTING)))
if backup is not None:
    HISTORY.write_bytes(backup)
elif HISTORY.exists():
    HISTORY.unlink()

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL CHECKS PASSED")
sys.exit(0)
