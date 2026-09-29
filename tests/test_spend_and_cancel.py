"""Nothing spends money without asking, and nothing runs without a way out.

Two invariants, both of which were false before this suite existed.

FIRST, EVERY PAID PATH ASKS. `confirm_spend()` guarded three of seven: refine,
the locked sequence (Ads and Cats share it) and the clips. The four that did not
ask were Compose's Generate, Upscale, Cats' Custom Prompt still, and - worst -
Variants, whose default click sampled SIX paid images with no confirmation and
no cost shown anywhere. This suite drives each path with the confirmation
DECLINED and asserts that nothing was submitted. That is the only phrasing that
cannot pass by accident: asserting a dialog appeared would still pass if the
code ignored the answer.

SECOND, EVERY LONG PATH CAN STOP. workers.WorkerPool.cancel() has always
worked; only Variants offered a button, so a slow run elsewhere left the form
disabled with no recourse but to wait or kill the app. Six views own a
generation now and all six carry a Cancel that enables exactly while busy.

The `AIVS_ASSUME_YES` escape hatch is what makes the first half testable at all,
and this suite is the one place that deliberately turns it OFF - see `declining()`
below. A modal nobody can answer is a hang, not a safeguard, so every other suite
leaves it on.
"""
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_ASSUME_YES", "1")

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-spend-empty.env"
_EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import generate_image as gi  # noqa: E402
import generate_video as gv  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow, _plural  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.compose_view.editor.subject.setPlainText("a woman in her thirties")

FIXTURE = Path(tempfile.gettempdir()) / "aivs-spend-fixture.png"
FIXTURE.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 64)

submitted = []
win.pool.submit = lambda jobs, provider, model, options=None: submitted.append(
    (provider, model, dict(options or {}), list(jobs)))
video_submitted = []
win.video_pool.submit = lambda jobs, **kw: video_submitted.append((list(jobs), dict(kw)))


def idle(pool):
    """Make a pool report not-busy.

    `busy` is a read-only property all the way down - GenerationPool and
    VideoPool both delegate to an inner WorkerPool, whose busy is
    `_completed < _total`. Resetting those two is how you say "nothing is
    running" without monkeypatching a property onto the class.
    """
    inner = getattr(pool, "_pool", pool)
    inner._completed = 0
    inner._total = 0


@contextmanager
def declining():
    """Run with the spend confirmation answered NO.

    The answer is patched rather than left to the platform. Offscreen Qt BLOCKS
    on QMessageBox.question with no event loop to close it, so driving the real
    dialog would hang the suite - and even where it returns, what it returns is
    a platform detail. What is worth testing is that the code HONOURS a No,
    which this asserts directly and deterministically.
    """
    previous = os.environ.pop("AIVS_ASSUME_YES", None)
    original = QMessageBox.question
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Cancel)
    try:
        yield
    finally:
        QMessageBox.question = original
        if previous is not None:
            os.environ["AIVS_ASSUME_YES"] = previous


PAID_PATHS = [
    ("Compose / Generate",
     lambda: win.generate_single("a test prompt", [])),
    ("Compose / Upscale",
     lambda: win.upscale_image(str(FIXTURE))),
    ("Variants / Generate (six images by default)",
     lambda: win.generate_batch([(i, "p{}".format(i), None, []) for i in range(6)])),
    ("Cats / Custom Prompt still",
     lambda: win.generate_custom_still("a cat", [])),
]


print("=== A CANCEL BUTTON ON EVERY VIEW THAT CAN START A GENERATION ===")
VIEWS = [
    ("Compose", win.compose_view),
    ("Variants", win.variants_view),
    ("Ads", win.ads_view),
    ("Cats", win.cats_view),
    ("Cats / Custom Prompt", win.cats_view.custom_tab),
    ("Videos", win.videos_view),
]
for label, view in VIEWS:
    check("{} has a Cancel button".format(label), hasattr(view, "cancel_button"))
    check("{} has a cancel_requested signal".format(label),
          hasattr(view, "cancel_requested"))
    if hasattr(view, "cancel_button"):
        check("{}: Cancel starts disabled - nothing is running yet".format(label),
              not view.cancel_button.isEnabled())
        check("{}: it is a danger button, like Variants' original".format(label),
              view.cancel_button.property("class") == "danger")
        check("{}: the tooltip is honest about already-sent requests".format(label),
              "still finish" in (view.cancel_button.toolTip() or ""),
              (view.cancel_button.toolTip() or "")[:40])


print()
print("=== BUSY ENABLES CANCEL, IDLE DISABLES IT ===")
for label, view in VIEWS:
    try:
        view.set_busy(True, 4)
    except TypeError:
        view.set_busy(True)
    check("{}: busy enables Cancel".format(label), view.cancel_button.isEnabled())
    try:
        view.set_busy(False, 0)
    except TypeError:
        view.set_busy(False)
    check("{}: idle disables it again".format(label), not view.cancel_button.isEnabled())


print()
print("=== DECLINING THE CONFIRMATION SUBMITS NOTHING ===")
for label, run in PAID_PATHS:
    submitted.clear()
    idle(win.pool)
    with declining():
        run()
    check("{}: declined, so nothing was submitted".format(label),
          submitted == [], str(len(submitted)))
    check("...and the status bar says so, rather than failing silently",
          "Cancelled" in win.statusBar().currentMessage(),
          win.statusBar().currentMessage()[:60])

print()
print("=== ACCEPTING IT SUBMITS EXACTLY WHAT WAS PRICED ===")
for label, run in PAID_PATHS:
    submitted.clear()
    idle(win.pool)
    run()
    check("{}: accepted, so it submitted".format(label), len(submitted) == 1,
          str(len(submitted)))
    if submitted:
        check("...with a resolved model, which is what makes a price possible",
              bool(submitted[0][1]), str(submitted[0][1]))

submitted.clear()
idle(win.pool)
win.generate_batch([(i, "p{}".format(i), None, []) for i in range(6)])
check("Variants submits all six jobs once confirmed",
      len(submitted[0][3]) == 6, str(len(submitted[0][3])))


print()
print("=== THE RESOLVED MODEL MATCHES WHAT THE PROVIDER WOULD HAVE PICKED ===")
cfg = gi.PROVIDERS[win.provider]
expected = (win.model or gi.env_value(cfg.get("model_var", ""))
            or cfg.get("default_model"))
check("resolved_model() agrees with generate_image._resolve()'s own chain",
      win.resolved_model() == expected, "{} vs {}".format(win.resolved_model(), expected))
check("an explicit override still wins outright",
      win.resolved_model(override="my-model") == "my-model")
check("...and it is never empty, which is what priced 'unknown' before",
      bool(win.resolved_model()))


print()
print("=== EMPTY WORK IS REFUSED BEFORE A DIALOG, NOT AFTER ===")
submitted.clear()
idle(win.pool)
win.generate_batch([])
check("no jobs means no confirmation and no submission", submitted == [])
check("...and it says what is wrong", "Nothing to generate" in win.statusBar().currentMessage(),
      win.statusBar().currentMessage()[:50])


print()
print("=== CANCEL REACHES THE RIGHT POOL ===")
stopped = {"stills": 0, "clips": 0}
win.pool.cancel = lambda: stopped.__setitem__("stills", stopped["stills"] + 1)
win.video_pool.cancel = lambda: stopped.__setitem__("clips", stopped["clips"] + 1)

for label, view in VIEWS[:-1]:
    view.cancel_requested.emit()
check("the five still views all stop the still pool", stopped["stills"] == 5,
      str(stopped))
check("...and none of them touched the clip pool", stopped["clips"] == 0, str(stopped))

win.videos_view.cancel_requested.emit()
check("Videos stops the CLIP pool, which cancel_generation would never reach",
      stopped["clips"] == 1, str(stopped))
check("...and did not also stop the still pool", stopped["stills"] == 5, str(stopped))


print()
print("=== THE ESTIMATE SETTINGS PROMISES ACTUALLY EXISTS ===")
check("Compose has a cost note", hasattr(win.compose_view, "cost_note"))
check("...and MainWindow filled it in", win.compose_view.cost_note.text().strip() != "",
      win.compose_view.cost_note.text())
note = win.image_cost_note(1)
check("the note prices one image", "credit" in note or "unknown" in note, note)

# Settings used to claim "the estimate on the generate button follows this" when
# there was no estimate on any generate button. There is one now - but the claim
# still needed correcting a second time, because pricing.json rates all three
# resolutions at a multiplier of 1.0. That is the table being honest that nobody
# has measured whether they differ, not a bug; images have no equivalent of the
# save_measured() feedback the clip path gets from the provider.
#
# IF SOMEONE MEASURES AND UPDATES THOSE FACTORS, this check fails on purpose -
# and the tooltip it guards is then the thing to fix.
priced = {r: gv.estimate("nano-banana-pro", 1, resolution=r)[0]
          for r in gi.KIE_RESOLUTIONS}
check("every resolution the picker offers is in the price table",
      all(v is not None for v in priced.values()), str(priced))
check("...and today they are all priced the same - a 1.0 multiplier throughout",
      len(set(priced.values())) == 1,
      str(priced) + "  <- if this changed, update the Settings tooltip")
tip = win.settings_view.resolution.toolTip()
check("Settings no longer claims an estimate that does not exist",
      "estimate on the generate button follows this" not in tip, tip[:70])
check("...it points at the note and the confirmation that do exist",
      "Generate button" in tip and "confirmation" in tip, tip[:80])
check("...and admits the three are currently priced the same",
      "the same" in tip and "measured" in tip, tip[-90:])

check("one image reads as 'image', not 'images'", _plural("image", 1) == "image")
check("...and six read as 'images'", _plural("image", 6) == "images")


print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL SPEND AND CANCEL CHECKS PASSED")
