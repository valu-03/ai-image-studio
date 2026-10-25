"""tools/skit_client.py and the Videos -> Skit Studio tab, against a fake Skit Studio.

The claim worth defending: AI Video Studio speaks Skit Studio's REST contract
exactly (create -> poll -> approve -> download), reports "not running" in plain words
instead of crashing, and the tab never enables "Approve & film" for a skit that fails
its lint gate - the button that spends money stays behind the same gate as the web UI.

No real network: a stdlib HTTP server on a free localhost port plays Skit Studio.
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

JOB = {
    "id": "20261025-1200-cat-abcd", "state": "awaiting_approval", "progress": 10,
    "message": "Ready - approve to film it", "running": False, "error": None, "urls": {},
    "skit": {"title": "The Robotic Rival", "cast": [{"id": "mittens", "name": "Mittens"}],
             "scenes": [{"n": 1, "beat": "hook", "seconds": 3, "speaker": "mittens", "line": "My nemesis."}]},
    "lint": {"passed": True, "score": 17, "total": 17, "errors": []},
    "estimate": {"summary": "~363 Kie credits (~$1.81)"},
}
calls = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        calls.append(("GET", self.path, self.headers.get("Authorization")))
        if self.path == "/api/v1/health":
            return self._send(200, {"status": "ok", "keys": {"kie": True}})
        if self.path.startswith("/api/v1/tasks?"):
            return self._send(200, {"tasks": [{"id": JOB["id"], "state": JOB["state"], "progress": JOB["progress"],
                                               "title": "The Robotic Rival"}]})
        if self.path == "/api/v1/tasks/" + JOB["id"]:
            return self._send(200, JOB)
        if self.path.endswith("/files/final.mp4"):
            return self._send(200, b"\x00\x00\x00\x18ftypmp42fake", "video/mp4")
        self._send(404, {"detail": "No such job."})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        calls.append(("POST", self.path, body))
        if self.path == "/api/v1/skits":
            return self._send(200, {"task_id": JOB["id"], "state": "queued"})
        if self.path == "/api/v1/ideas":
            seen = body.get("avoid") or []
            idea = "A parrot runs a fake weather service." if seen else "A corgi files a complaint."
            return self._send(200, {"ideas": [{"idea": idea, "cast": "a corgi"}]})
        if self.path.endswith("/approve"):
            JOB.update(state="done", progress=100, urls={"final": "/api/v1/tasks/{}/files/final.mp4".format(JOB["id"])})
            return self._send(200, JOB)
        self._send(404, {"detail": "nope"})


server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
env_file = Path(tempfile.gettempdir()) / "aivs-skit-studio-test.env"
env_file.write_text("SKIT_API_BASE=http://127.0.0.1:{}\nSKIT_API_TOKEN=tok\n".format(server.server_address[1]),
                    encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(env_file)

import skit_client as sc  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("  {} {}{}".format("OK  " if ok else "FAIL", name, "" if ok else "  - " + str(detail)))
    if not ok:
        fails.append(name)


# --- the client ---------------------------------------------------------- #
result, error = sc.health()
check("health answers", error is None and result["status"] == "ok", error)
check("the bearer token is sent", calls[-1][2] == "Bearer tok", calls[-1])

result, error = sc.create("cat vs vacuum", 20, "pixar", "std", "voicestudio")
check("create posts the idea and returns a task id", result == {"task_id": JOB["id"], "state": "queued"}, error)
sent = calls[-1][2]
check("create sends the REST fields", sent["idea"] == "cat vs vacuum" and sent["seconds"] == 20
      and sent["style"] == "pixar" and sent["voice_provider"] == "voicestudio", sent)
check("create leaves the clip engine to Skit Studio by default", sent.get("video_model") is None, sent)
sc.create("cat vs vacuum", 20, video_model="seedance-2.5")
check("create can pick a clip engine", calls[-1][2]["video_model"] == "seedance-2.5", calls[-1][2])
found, error = sc.ideas(1, "a dog", ["old"])
check("ideas returns an idea", error is None and found["ideas"][0]["idea"], error)
check("ideas sends hint and avoid", calls[-1][2]["hint"] == "a dog" and calls[-1][2]["avoid"] == ["old"],
      calls[-1][2])

job, error = sc.get(JOB["id"])
text = sc.summary(job)
check("summary shows the line, lint and cost", "Mittens: My nemesis." in text and "lint 17/17" in text
      and "363 Kie credits" in text, text)

_, error = sc.get("missing")
check("a 404 is a readable error", error and "404" in error, error)

tasks, error = sc.list_tasks()
check("list_tasks returns rows", tasks and tasks[0]["id"] == JOB["id"], error)

# --- the tab (offscreen Qt) ---------------------------------------------- #
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from ui.views.skit_studio import SkitStudioView  # noqa: E402

JOB.update(state="awaiting_approval", progress=10, urls={})
view = SkitStudioView()
view._show_job(dict(JOB))
check("Approve is enabled for a passing skit at the gate", view.approve_btn.isEnabled())
blocked = dict(JOB, lint={"passed": False, "score": 15, "total": 17, "errors": ["hook_first"]})
view._show_job(blocked)
check("Approve stays disabled when lint blocks", not view.approve_btn.isEnabled())
check("Save video is disabled without a final cut", not view.download_btn.isEnabled())
view.idea.setPlainText("")
view.auto_idea()
view.pool.waitForDone(5000)
app.processEvents()
check("Auto-generate idea fills the idea box", view.idea.toPlainText() == "A corgi files a complaint.",
      view.idea.toPlainText())
view.auto_idea()
view.pool.waitForDone(5000)
app.processEvents()
check("a second press asks for a different idea", view.idea.toPlainText() == "A parrot runs a fake weather service.",
      view.idea.toPlainText())
check("the clip picker offers all five engines", view.clips.count() == 5 and view.clips.itemData(0) == "kling-3.0")

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
view._show_job(dict(JOB))
view.approve()
view.pool.waitForDone(5000)
app.processEvents()
check("approving through the tab hits /approve", any(c[1].endswith("/approve") for c in calls if c[0] == "POST"))
check("the tab shows the finished job", view.job and view.job["state"] == "done", view.job and view.job["state"])
check("Save video is enabled once the cut exists", view.download_btn.isEnabled())

out = Path(tempfile.mkdtemp())
path, error = sc.download(JOB["id"], out)
check("download saves the mp4", path and path.read_bytes().startswith(b"\x00\x00\x00\x18ftyp"), error)
view.timer.stop()

# --- not running --------------------------------------------------------- #
server.shutdown()
_, error = sc.health()
check("a stopped server is reported in plain words", error and "not running" in error, error)

print("{} failed".format(len(fails)) if fails else "all passed")
sys.exit(1 if fails else 0)
