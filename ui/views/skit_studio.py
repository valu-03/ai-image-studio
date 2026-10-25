"""Videos -> Skit Studio: make a talking-pet skit through Skit Studio.

Skit Studio is a separate app (..\\Skit Studio) with its own REST API;
this tab is a client of it, nothing more. Every call goes through
tools/skit_client.py on a worker thread (ui/workers.py SkitTask), so the window
never waits on the network, and no skit logic lives here: writing, linting,
pricing and filming all happen in Skit Studio.

The cost gate is kept visible: "Write the skit" spends nothing paid; the estimate
and lint score appear, and only "Approve & film" spends Kie credits.
"""

import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QThreadPool, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import skit_client as sc  # noqa: E402

from .. import tokens as T  # noqa: E402
from ..widgets import Badge, Card, MutedLabel, TitleLabel, set_empty_hint  # noqa: E402
from ..workers import SkitTask  # noqa: E402

POLL_MS = 2000
STATE_STATUS = {"done": "success", "failed": "danger", "cancelled": "danger", "awaiting_approval": "warning"}


class SkitStudioView(QWidget):
    status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.job = None
        self._tasks = set()
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self._poll)
        self.setup_ui()

    # -- layout ------------------------------------------------------------- #
    def setup_ui(self):
        left = Card()
        head = QHBoxLayout()
        head.addWidget(TitleLabel("Talking-pet skit"))
        head.addStretch(1)
        self.server_badge = Badge("checking...", "quiet")
        head.addWidget(self.server_badge)
        left.body.addLayout(head)
        left.body.addWidget(MutedLabel(
            "One idea in, one finished talking-pet video out - written, priced and filmed by "
            "Skit Studio (Kling clips, VoiceStudio voices, meme captions). Writing is free; "
            "nothing is filmed until you approve the estimate."))

        self.idea = QPlainTextEdit()
        self.idea.setPlaceholderText("A cat who is convinced the robot vacuum is his rival...")
        self.idea.setMaximumHeight(96)
        left.body.addWidget(self.idea)
        self.idea_btn = QPushButton("Auto-generate idea")
        self.idea_btn.setToolTip("Skit Studio's writer invents a fresh idea (builds on what you typed)")
        self.idea_btn.clicked.connect(self.auto_idea)
        self._shown_ideas = []
        left.body.addWidget(self.idea_btn)

        form = QFormLayout()
        self.seconds = QSpinBox()
        self.seconds.setRange(10, 60)
        self.seconds.setSingleStep(5)
        self.seconds.setValue(30)
        self.seconds.setSuffix(" s")
        self.style = QComboBox()
        self.style.addItems(["photoreal", "pixar", "claymation"])
        self.voices = QComboBox()
        self.voices.addItems(["auto", "voicestudio", "elevenlabs"])
        self.voices.setToolTip("auto = VoiceStudio when it is running (free), else ElevenLabs")
        self.mode = QComboBox()
        self.mode.addItems(["std", "pro", "4K"])
        self.mode.setToolTip("Kling tier (4K only through Kie)")
        self.clips = QComboBox()
        for key, text in sc.VIDEO_MODELS:
            self.clips.addItem(text, key)
        self.clips.setToolTip("Which model films the clips. Kling 3.0 on Higgsfield is the cheapest strong one.")
        form.addRow("Length", self.seconds)
        form.addRow("Style", self.style)
        form.addRow("Voices", self.voices)
        form.addRow("Clips", self.clips)
        form.addRow("Kling tier", self.mode)
        left.body.addLayout(form)

        self.write_btn = QPushButton("Write the skit")
        self.write_btn.setProperty("class", "primary")
        self.write_btn.clicked.connect(self.write)
        left.body.addWidget(self.write_btn)

        left.body.addWidget(TitleLabel("Recent skits"))
        self.jobs = QListWidget()
        self.jobs.setMinimumHeight(120)
        self.jobs.itemSelectionChanged.connect(self._on_pick)
        set_empty_hint(self.jobs, "Skits you write appear here.", "videos")
        left.body.addWidget(self.jobs, 1)
        refresh = QPushButton("Refresh")
        refresh.setProperty("class", "ghost")
        refresh.clicked.connect(self.refresh)
        left.body.addWidget(refresh)

        right = Card()
        top = QHBoxLayout()
        self.title = TitleLabel("No skit selected")
        top.addWidget(self.title, 1)
        self.state_badge = Badge("", "quiet")
        top.addWidget(self.state_badge)
        right.body.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        right.body.addWidget(self.progress)
        self.message = MutedLabel("")
        right.body.addWidget(self.message)
        self.script = QPlainTextEdit()
        self.script.setReadOnly(True)
        right.body.addWidget(self.script, 1)

        row = QHBoxLayout()
        self.approve_btn = QPushButton("Approve && film")
        self.approve_btn.setProperty("class", "primary")
        self.approve_btn.clicked.connect(self.approve)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("class", "danger")
        self.cancel_btn.clicked.connect(self.cancel)
        self.open_btn = QPushButton("Open in browser")
        self.open_btn.setToolTip("Open this skit in Skit Studio's own web UI")
        self.open_btn.clicked.connect(self.open_web)
        self.download_btn = QPushButton("Save video")
        self.download_btn.clicked.connect(self.download)
        for b in (self.approve_btn, self.cancel_btn, self.open_btn, self.download_btn):
            row.addWidget(b)
        right.body.addLayout(row)

        # The form scrolls rather than crushing its rows at the minimum window size.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(left)
        split = QSplitter()
        split.addWidget(scroll)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, T.SPACE["sm"], 0, 0)
        layout.addWidget(split)
        self._show_job(None)

    def showEvent(self, event):
        # Reach the server only when the tab is actually opened: a request started
        # at construction outlives short-lived windows (every GUI test builds one).
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()

    # -- worker plumbing ---------------------------------------------------- #
    def _run(self, fn, *args, on_ok=None, on_error=None):
        task = SkitTask(fn, *args)
        self._tasks.add(task)
        task.signals.finished.connect(lambda r: on_ok and on_ok(r))
        task.signals.failed.connect(lambda e: (on_error or self._fail)(e))
        task.signals.done.connect(lambda _=0, t=task: self._tasks.discard(t))
        self.pool.start(task)

    def _fail(self, error):
        self.status.emit(error)
        self.message.setText(error)

    # -- actions ------------------------------------------------------------ #
    def refresh(self):
        def up(_):
            self.server_badge.set_status("success", "connected")
            self._run(sc.list_tasks, on_ok=self._fill_jobs)

        def down(error):
            self.server_badge.set_status("danger", "not running")
            self.message.setText(error)
        self._run(sc.health, on_ok=up, on_error=down)

    def _fill_jobs(self, tasks):
        current = self.job["id"] if self.job else None
        self.jobs.blockSignals(True)
        self.jobs.clear()
        for t in tasks:
            item = QListWidgetItem("{}  -  {}".format(t["title"] or t["id"], t["state"].replace("_", " ")))
            item.setData(256, t["id"])
            self.jobs.addItem(item)
            if t["id"] == current:
                item.setSelected(True)
        self.jobs.blockSignals(False)

    def _on_pick(self):
        items = self.jobs.selectedItems()
        if items:
            self._load(items[0].data(256))

    def _load(self, task_id):
        self._run(sc.get, task_id, on_ok=self._show_job)

    def write(self):
        idea = self.idea.toPlainText().strip()
        if len(idea) < 3:
            self.status.emit("Give the writer an idea first.")
            return
        self.write_btn.setEnabled(False)
        self.message.setText("Writing the skit...")

        def ok(result):
            self.write_btn.setEnabled(True)
            self._load(result["task_id"])
            self.refresh()
            self.timer.start()

        def err(error):
            self.write_btn.setEnabled(True)
            self._fail(error)
        self._run(sc.create, idea, self.seconds.value(), self.style.currentText(), self.mode.currentText(),
                  self.voices.currentText(), False, True, self.clips.currentData(), on_ok=ok, on_error=err)

    def auto_idea(self):
        typed = self.idea.toPlainText().strip()
        hint = "" if typed in self._shown_ideas else typed
        self.idea_btn.setEnabled(False)
        self.idea_btn.setText("Thinking...")

        def done():
            self.idea_btn.setEnabled(True)
            self.idea_btn.setText("Auto-generate idea")

        def ok(result):
            done()
            found = (result or {}).get("ideas") or []
            if not found:
                return self._fail("Skit Studio's writer had no idea this time - try again.")
            self._shown_ideas.append(found[0]["idea"])
            self.idea.setPlainText(found[0]["idea"])

        def err(error):
            done()
            self._fail(error)
        self._run(sc.ideas, 1, hint, self._shown_ideas, on_ok=ok, on_error=err)

    def approve(self):
        if not self.job:
            return
        est = (self.job.get("estimate") or {}).get("summary", "an unknown cost")
        if QMessageBox.question(self, "Film this skit?",
                                "This spends real credits:\n\n{}\n\nFilm it?".format(est)) != QMessageBox.StandardButton.Yes:
            return
        self._run(sc.approve, self.job["id"], on_ok=lambda j: (self._show_job(j), self.timer.start()))

    def cancel(self):
        if self.job:
            self._run(sc.cancel, self.job["id"], on_ok=self._show_job)

    def open_web(self):
        webbrowser.open(sc.web_url(self.job["id"] if self.job else None))

    def download(self):
        if not self.job:
            return
        self.download_btn.setEnabled(False)

        def ok(path):
            self.download_btn.setEnabled(True)
            self.status.emit("Saved {}".format(Path(path).name))
            self.message.setText("Saved to temp/outputs/skit_studio/{}".format(Path(path).name))
        self._run(sc.download, self.job["id"], on_ok=ok,
                  on_error=lambda e: (self.download_btn.setEnabled(True), self._fail(e)))

    def _poll(self):
        if not self.job:
            self.timer.stop()
            return
        self._load(self.job["id"])

    # -- display ------------------------------------------------------------ #
    def _show_job(self, job):
        self.job = job
        has = job is not None
        state = job.get("state") if has else None
        self.title.setText(((job.get("skit") or {}).get("title") or "Writing...") if has else "No skit selected")
        self.state_badge.set_status(STATE_STATUS.get(state, "accent"), (state or "").replace("_", " "))
        self.state_badge.setVisible(has)
        self.progress.setValue(job.get("progress", 0) if has else 0)
        self.message.setText(job.get("message", "") if has else
                             "Write a skit, or pick one from the list.")
        self.script.setPlainText(sc.summary(job) if has else "")
        resting = state in sc.RESTING
        lint_ok = bool(has and job.get("lint") and job["lint"]["passed"])
        self.approve_btn.setEnabled(has and state in ("awaiting_approval", "failed", "cancelled") and lint_ok
                                    and not job.get("running"))
        self.cancel_btn.setEnabled(has and not resting)
        self.open_btn.setEnabled(True)
        self.download_btn.setEnabled(bool(has and (job.get("urls") or {}).get("final")))
        if has and resting and not job.get("running"):
            if self.timer.isActive():
                self.timer.stop()
                self.refresh()
        elif has:
            self.timer.start()
