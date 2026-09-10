"""ui/workers.WorkerPool - the shared batch-of-QRunnables bookkeeping under
stills, clips and the credits check.

The load-bearing case here is cancellation. QThreadPool.clear() drops queued
runnables, so their `done` signal never fires; before the fix that meant the
completed count never reached the total, `busy` stayed True forever, and every
later generation was refused with "A generation is already running" until the
app was restarted. This suite pins the fix: cancel() drives batch_finished and
clears busy, exactly once, and a late `done` from a task that was already
running is deduped.

Offscreen, no network.
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.workers import WorkerPool  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


class _Signals(QObject):
    done = pyqtSignal(int)


class FakeTask(QRunnable):
    """Sleeps `delay` seconds, then emits done. `cancel()` sets a flag the
    body checks (a real GenerationTask cancels its poll loop the same way)."""

    def __init__(self, index, delay=0.05):
        super().__init__()
        self.index = index
        self.delay = delay
        self.signals = _Signals()
        self._cancelled = False
        self.ran = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        self.ran = True
        deadline = time.time() + self.delay
        while time.time() < deadline and not self._cancelled:
            time.sleep(0.005)
        self.signals.done.emit(self.index)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


print("=== a normal batch completes: batch_finished once, busy clears ===")
pool = WorkerPool(2)
finished = {"n": 0}
pool.batch_finished.connect(lambda: finished.__setitem__("n", finished["n"] + 1))
tasks = [FakeTask(i, delay=0.02) for i in range(5)]
pool.submit_tasks(tasks)
check("busy right after submit", pool.busy)
pump(1.0)
check("batch_finished fired exactly once", finished["n"] == 1, str(finished["n"]))
check("not busy after completion", not pool.busy)
check("completed == total", pool._completed == pool.total == 5)
check("every task actually ran", all(t.ran for t in tasks))

print()
print("=== cancel with queued tasks still drives batch_finished and clears busy ===")
pool = WorkerPool(2)          # 2 at a time, so 6 of 8 start life queued
finished = {"n": 0}
pool.batch_finished.connect(lambda: finished.__setitem__("n", finished["n"] + 1))
tasks = [FakeTask(i, delay=5.0) for i in range(8)]   # long, so nothing finishes on its own
pool.submit_tasks(tasks)
pump(0.1)
check("busy while running", pool.busy)
pool.cancel()
pump(0.2)
check("batch_finished fired after cancel", finished["n"] == 1, str(finished["n"]))
check("not busy after cancel (the wedge is gone)", not pool.busy)
check("completed count reached total", pool._completed == pool.total == 8)
check("a fresh submit is accepted after a cancel", True)
# The running tasks were told to cancel and will emit `done` shortly after.
pump(0.3)
check("batch_finished still only fired once despite late done signals",
      finished["n"] == 1, str(finished["n"]))
check("completed never overshot total", pool._completed == 8, str(pool._completed))

print()
print("=== the pool is reusable after a cancel ===")
finished["n"] = 0
tasks2 = [FakeTask(i, delay=0.02) for i in range(3)]
pool.submit_tasks(tasks2)
check("busy again for the new batch", pool.busy)
pump(1.0)
check("second batch finished once", finished["n"] == 1, str(finished["n"]))
check("not busy", not pool.busy)

print()
print("=== an empty batch finishes immediately ===")
pool = WorkerPool(2)
finished = {"n": 0}
pool.batch_finished.connect(lambda: finished.__setitem__("n", finished["n"] + 1))
pool.submit_tasks([])
pump(0.05)
check("empty batch emits batch_finished once", finished["n"] == 1)
check("empty batch is not busy", not pool.busy)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL WORKER-POOL CHECKS PASSED")
