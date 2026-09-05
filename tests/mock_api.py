"""Mock provider API - verifies generate_image.py without a real key or network.

Kie and Higgsfield are both asynchronous: submit, poll until done, then download
a URL. So this mock is a small state machine rather than a lookup table - a job
reports "still working" on its first status check and only then succeeds. A mock
that returned success immediately would leave the polling loop untested, which
is most of the new code.

Error scenarios are selected by a path segment injected into the base URL, the
same trick the synchronous providers used: BASE + "/boom" (HTTP 400),
"/noimage" (finishes with no image URL), "/fails" (the job reports failure),
"/forever" (never leaves the queue), "/empty" (text route returns no content).
"""
import base64
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# 1x1 red PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

STATE = {"last": None, "last_get": None, "last_status": None,
         "reply": "mock reply text", "polls": {}}


def reset():
    STATE["last"] = None
    STATE["last_get"] = None
    STATE["last_status"] = None
    STATE["polls"] = {}


def _flag(path, name):
    return name in path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_png(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PNG)))
        self.end_headers()
        self.wfile.write(PNG)

    @property
    def _origin(self):
        return "http://{}".format(self.headers.get("Host", "127.0.0.1"))

    # -- POST: submit a job, upload a reference, or answer the text route ---- #
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        STATE["last"] = {"path": self.path, "headers": dict(self.headers), "body": body}

        if _flag(self.path, "boom"):
            return self._send(400, {"error": {"message": "model not found: bogus-model"}})

        # Text route (ask_llm). Requires BOTH the prefix and the chat path so it
        # cannot swallow another provider's URL under the same base.
        if self.path.startswith("/text") and "chat/completions" in self.path:
            if _flag(self.path, "empty"):
                return self._send(200, {"choices": [{"message": {"content": ""}}]})
            return self._send(200, {"choices": [
                {"message": {"role": "assistant", "content": STATE["reply"]}}
            ]})

        if "file-base64-upload" in self.path:
            return self._send(200, {"success": True, "data": {
                "fileUrl": self._origin + "/uploads/reference.png"}})

        if "createTask" in self.path:
            return self._send(200, {"code": 200, "msg": "success",
                                    "data": {"taskId": "task_mock_1"}})

        if "soul" in self.path:
            request_id = "req_mock_1"
            return self._send(200, {
                "status": "queued",
                "request_id": request_id,
                # Absolute, exactly as the real API returns it.
                "status_url": "{}{}/requests/{}/status".format(
                    self._origin, self._prefix(), request_id),
            })

        self._send(404, {"error": {"message": "unknown route"}})

    def _prefix(self):
        """The scenario segment injected into the base URL, if any."""
        for flag in ("/boom", "/noimage", "/fails", "/forever", "/empty"):
            if flag in self.path:
                return flag
        return ""

    # -- GET: poll a job, or serve the finished image ----------------------- #
    def do_GET(self):
        STATE["last_get"] = {"path": self.path, "headers": dict(self.headers)}
        path = urllib.parse.urlparse(self.path).path

        if path.endswith(".png") or "/uploads/" in path:
            return self._send_png()

        if "recordInfo" in self.path:
            STATE["last_status"] = STATE["last_get"]
            return self._send(200, {"code": 200, "msg": "success",
                                    "data": self._kie_state()})

        if path.endswith("/status"):
            STATE["last_status"] = STATE["last_get"]
            return self._send(200, self._higgsfield_state())

        self._send(404, {"error": {"message": "unknown route"}})

    def _count(self, key):
        """How many times this job has been polled, starting at 1."""
        STATE["polls"][key] = STATE["polls"].get(key, 0) + 1
        return STATE["polls"][key]

    def _kie_state(self):
        attempt = self._count("kie")
        if _flag(self.path, "fails"):
            return {"taskId": "task_mock_1", "state": "fail",
                    "failCode": "500", "failMsg": "the model refused"}
        if _flag(self.path, "forever") or attempt < 2:
            # First check is always "still working" - that is what exercises poll().
            return {"taskId": "task_mock_1", "state": "generating", "progress": 40}
        if _flag(self.path, "noimage"):
            return {"taskId": "task_mock_1", "state": "success",
                    "resultJson": json.dumps({"resultUrls": []})}
        return {"taskId": "task_mock_1", "state": "success",
                "resultJson": json.dumps(
                    {"resultUrls": [self._origin + "/results/out.png"]})}

    def _higgsfield_state(self):
        attempt = self._count("higgsfield")
        base = {"status": "queued", "request_id": "req_mock_1"}
        if _flag(self.path, "fails"):
            return dict(base, status="failed")
        if _flag(self.path, "forever") or attempt < 2:
            return base
        if _flag(self.path, "noimage"):
            return dict(base, status="completed", images=[])
        return dict(base, status="completed",
                    images=[{"url": self._origin + "/results/out.png"}])


def serve(port):
    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    serve(port)
    print("mock api on {}".format(port), flush=True)
    threading.Event().wait()
