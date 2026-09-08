"""Mock ElevenLabs API - verifies generate_sound.py / generate_speech.py /
elevenlabs_voices.py without a real key or network.

Unlike tests/mock_api.py's providers, every real ElevenLabs endpoint here is
synchronous - no job/poll state machine, just a request and, on success, raw
audio bytes back (JSON only on error). That is the whole reason this is a
separate mock rather than a route bolted onto mock_api.Handler: audio-body
responses and a DELETE verb don't fit that handler's JSON-only `_send`.

Error scenarios are selected by a path segment injected into the base URL:
BASE + "/boom" (HTTP 400 with ElevenLabs' real {"detail": {...}} shape),
BASE + "/silence" (200 but an empty body).
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# A tiny, real MP3 header-ish byte string is unnecessary - the code under test
# only checks Content-Type and non-empty bytes, never decodes audio.
AUDIO = b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-bytes-for-tests"

STATE = {"last": None, "voices": [
    {"voice_id": "voice_premade_1", "name": "Rachel", "category": "premade"},
]}


def reset():
    STATE["last"] = None
    STATE["voices"] = [
        {"voice_id": "voice_premade_1", "name": "Rachel", "category": "premade"},
    ]


def _flag(path, name):
    return name in path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_audio(self, data=AUDIO):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self, body=None):
        STATE["last"] = {"path": self.path, "headers": dict(self.headers), "body": body}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        content_type = self.headers.get("Content-Type", "")

        if _flag(self.path, "boom"):
            self._record(raw_body)
            return self._send_json(400, {"detail": {
                "status": "invalid_request", "message": "mock rejection"}})

        if "sound-generation" in self.path:
            body = json.loads(raw_body or b"{}")
            self._record(body)
            if _flag(self.path, "silence"):
                return self._send_audio(b"")
            return self._send_audio()

        if "text-to-speech" in self.path:
            body = json.loads(raw_body or b"{}")
            self._record(body)
            return self._send_audio()

        if "voices/add" in self.path:
            # Multipart body - record raw bytes and the boundary so a test can
            # confirm the sample files actually went out, without a full parser.
            self._record({"multipart": True, "raw_len": len(raw_body),
                          "content_type": content_type, "raw": raw_body})
            new_id = "voice_cloned_{}".format(len(STATE["voices"]) + 1)
            STATE["voices"].append({"voice_id": new_id, "name": "cloned", "category": "cloned"})
            return self._send_json(200, {"voice_id": new_id})

        self._send_json(404, {"detail": "unknown route"})

    def do_GET(self):
        self._record()
        if "voices" in self.path:
            return self._send_json(200, {"voices": STATE["voices"]})
        self._send_json(404, {"detail": "unknown route"})

    def do_DELETE(self):
        self._record()
        if _flag(self.path, "boom"):
            return self._send_json(400, {"detail": "cannot delete"})
        voice_id = self.path.rsplit("/", 1)[-1]
        STATE["voices"] = [v for v in STATE["voices"] if v["voice_id"] != voice_id]
        return self._send_json(200, {"status": "ok"})


def serve(port):
    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8796
    serve(port)
    print("mock elevenlabs api on {}".format(port), flush=True)
    threading.Event().wait()
