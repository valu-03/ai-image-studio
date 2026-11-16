"""studio/desktop.py - free_port, start_local_api, and current_look wiring."""
import json
import os
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TMP = Path(tempfile.mkdtemp(prefix="aivs-studio-desktop-"))
ENV = TMP / ".env"
ENV.write_text("KIE_API_KEY=fake-kie\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(ENV)
os.environ["AIVS_OUTPUTS_DIR"] = str(TMP / "outputs")
os.environ.pop("AIVS_HISTORY_FILE", None)

from fastapi.testclient import TestClient  # noqa: E402

import look_cards  # noqa: E402
from studio.desktop import RESERVED_PORTS, free_port, start_local_api  # noqa: E402
from studio.server import create_app  # noqa: E402
from studio.state import LookState  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("Desktop local API")
port = free_port()
check("free_port avoids reserved ports", port > 0 and port not in RESERVED_PORTS, str(port))

state = LookState()
api, err = start_local_api(state, False)
check("disabled_returns_none_no_error", api is None and err is None, str((api, err)))

blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
blocker.bind(("127.0.0.1", 0))
blocker.listen(1)
taken_port = blocker.getsockname()[1]
os.environ["AIVS_LOCAL_API_PORT"] = str(taken_port)
try:
    api, err = start_local_api(state, True)
    expected = "Local API couldn't start: port {} is in use".format(taken_port)
    check("port_taken_reports", api is None and err == expected, str((api, err)))
finally:
    blocker.close()

live_port = free_port()
os.environ["AIVS_LOCAL_API_PORT"] = str(live_port)
api, err = start_local_api(state, True)
check("local api starts on free port", api is not None and err is None, str(err))
try:
    app = create_app(None, state)
    app.state.local_api = {"running": True, "error": ""}
    client = TestClient(app)
    client.post("/api/describe", json={"text": "my white Persian cat"})

    with urllib.request.urlopen(
        "http://127.0.0.1:{}/api/v1/look/current".format(live_port), timeout=5
    ) as resp:
        before = json.loads(resp.read().decode("utf-8"))
    check("untouched look is all empty strings on Local API",
          all(v == "" for v in before.values()), str(before))

    light_opts = [c for c in look_cards.cards("animal") if c["id"] == "light"][0]["options"]
    chosen = light_opts[0]
    client.put("/api/look", json={"card": "light", "option": chosen["key"]})

    with urllib.request.urlopen(
        "http://127.0.0.1:{}/api/v1/look/current".format(live_port), timeout=5
    ) as resp:
        after = json.loads(resp.read().decode("utf-8"))
    check("current_look_wired",
          bool(after.get("lighting")) and all(after[k] == "" for k in after if k != "lighting"),
          str(after))
finally:
    if api is not None:
        api.stop()

print("FAILED: {}".format(fails) if fails else "ALL OK")
sys.exit(1 if fails else 0)
