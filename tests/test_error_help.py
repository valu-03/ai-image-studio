"""An error a user can act on, and a surface wide enough to read it.

Two halves.

FIRST, THE MESSAGE. A bad key read `API error 401: Unauthorized` and stopped
there - true, and useless. Every provider config already carried the env var its
key lives in and a `where` URL to get one; both sat unused at exactly the moment
they were needed. `generate_image.remedy_for()` now appends one actionable line
per status. Only the 400/404 model-id hint existed before.

401 and 402/403 deliberately suggest different things: 401 is about the key
itself ("get one"), 402/403 are about the account behind it ("check the
account"). And 5xx deliberately does NOT say "retry" - `open_with_retry()`
refuses to retry an HTTPError precisely because the server received the request
and may already have started a paid job, so the advice is to check the account
first.

SECOND, THE SURFACE. Every failure path trimmed to 160 characters before
reaching a one-line status bar. That is fine for "pick a movement first" and
actively harmful for the messages that carry the fix - the missing-key message
names the variable, the file, the URL and the whole prompt to paste elsewhere
meanwhile, roughly 400 characters with the remedy at the END. `report_failure()`
switches on LENGTH rather than on caller: short reasons still just go to the
status bar, because a modal for a one-liner would be worse than a truncated one.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_ASSUME_YES", "1")

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-errhelp-empty.env"
_EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import generate_image as gi  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.theme import ThemeManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== EVERY STATUS A USER CAN DO SOMETHING ABOUT HAS A REMEDY ===")
for provider, cfg in gi.PROVIDERS.items():
    for status in (401, 402, 403, 429, 400, 404, 500, 503):
        remedy = gi.remedy_for(status, cfg)
        check("{} / {}: says something".format(provider, status), bool(remedy.strip()),
              remedy.strip()[:50])
        check("{} / {}: starts on its own line".format(provider, status),
              remedy.startswith("\n"), repr(remedy[:3]))
    check("{}: a success carries no remedy".format(provider),
          gi.remedy_for(200, cfg) == "")
    check("{}: nor does a redirect".format(provider), gi.remedy_for(302, cfg) == "")


print()
print("=== THE REMEDY NAMES THINGS THE USER CAN ACTUALLY FIND ===")
for provider, cfg in gi.PROVIDERS.items():
    check("{} / 401 names its key variable".format(provider),
          cfg["key"] in gi.remedy_for(401, cfg), gi.remedy_for(401, cfg).strip()[:60])
    check("{} / 401 links where to get one".format(provider),
          cfg["where"] in gi.remedy_for(401, cfg))
    check("{} / 400 names the MODEL variable, not the key".format(provider),
          cfg["model_var"] in gi.remedy_for(400, cfg)
          and cfg["key"] not in gi.remedy_for(400, cfg),
          gi.remedy_for(400, cfg).strip()[:60])

kie = gi.PROVIDERS["kie"]
check("401 offers a new key; 403 sends you to the account instead",
      "Get one at" in gi.remedy_for(401, kie)
      and "Check the account at" in gi.remedy_for(403, kie))
check("402 is about credit, not about the key",
      "credit" in gi.remedy_for(402, kie) and "typo" not in gi.remedy_for(402, kie),
      gi.remedy_for(402, kie).strip())
check("429 suggests waiting and a smaller batch",
      "Wait" in gi.remedy_for(429, kie) and "smaller" in gi.remedy_for(429, kie))
# The one piece of advice this must NOT give.
check("5xx does not tell you to retry - the job may already be running",
      "retry" not in gi.remedy_for(500, kie).lower()
      and "resubmitting" in gi.remedy_for(500, kie),
      gi.remedy_for(500, kie).strip()[:70])
check("...and says whose fault it is", "provider's side" in gi.remedy_for(500, kie))

check("a config with neither key nor url still returns a usable line",
      gi.remedy_for(401, {}).strip() != "", gi.remedy_for(401, {}).strip()[:60])
check("...and does not print an empty URL", "at \n" not in gi.remedy_for(401, {})
      and not gi.remedy_for(401, {}).rstrip().endswith("at"))


print()
print("=== THE MESSAGE THE PROVIDER PATH ACTUALLY BUILDS ===")
built = "API error {}: {}{}".format(401, "Unauthorized", gi.remedy_for(401, kie))
check("the old message is still the first line",
      built.splitlines()[0] == "API error 401: Unauthorized", built.splitlines()[0])
check("...and the fix is on the lines after it", len(built.splitlines()) > 1)
check("truncating to 160 would have cut the remedy off",
      len(built) > 160, str(len(built)))


print()
print("=== report_failure(): LENGTH DECIDES, NOT THE CALLER ===")
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)

# AIVS_ASSUME_YES is on for this suite, so no box is ever constructed - which is
# what keeps this runnable. What is asserted is the status-bar half and the
# decision, not Qt's dialog.
win.report_failure("Pick a movement first")
check("a one-liner reaches the status bar",
      win.statusBar().currentMessage() == "Pick a movement first",
      win.statusBar().currentMessage())

win.report_failure(built)
check("a multi-line reason shows only its FIRST line in the bar",
      win.statusBar().currentMessage() == "API error 401: Unauthorized",
      win.statusBar().currentMessage())
check("...so the bar never shows a raw newline",
      "\n" not in win.statusBar().currentMessage())

long_single = "x" * 400
win.report_failure(long_single)
check("an over-long single line is still clipped for the bar",
      len(win.statusBar().currentMessage()) <= 160,
      str(len(win.statusBar().currentMessage())))

before = win.statusBar().currentMessage()
win.report_failure("")
check("an empty reason changes nothing at all",
      win.statusBar().currentMessage() == before)
win.report_failure("   \n  ")
check("...nor does whitespace", win.statusBar().currentMessage() == before)


print()
print("=== THE FAILURE PATHS ROUTE THROUGH IT ===")
seen = []
win.report_failure = lambda reason, title="": seen.append((reason, title))

win._batch = None
win.on_item_failed(0, built)
check("a Compose failure reports the whole reason, not 160 characters of it",
      seen and seen[-1][0] == built, str(len(seen)))
check("...with a title naming what failed", "image" in seen[-1][1], seen[-1][1])

win._video = None
win.on_video_failed(0, built)
check("a clip failure does too", seen[-1][0] == built)
check("...with its own title", "clip" in seen[-1][1], seen[-1][1])

win.on_refine_failed(built)
check("so does refine", seen[-1][0] == built)
check("...which no longer prefixes and then truncates", "Refine" in seen[-1][1],
      seen[-1][1])


print()
# Tear the window down explicitly. Left to interpreter exit this suite crashed
# INTERMITTENTLY on Windows (0xC0000409) after printing its results - Qt
# destroying widgets in an order Python's own teardown had already started
# unpicking, made likelier here because report_failure is monkeypatched onto the
# instance above. run_all.py exits non-zero on that, so it is a flaky red build
# rather than a cosmetic one. Closing and dropping the reference first, while
# the interpreter is still whole, is the standard remedy; tests/test_layout.py
# already did this for the same reason.
win.close()
app.processEvents()
del win

if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL ERROR HELP CHECKS PASSED")
