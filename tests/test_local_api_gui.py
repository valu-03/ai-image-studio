"""The Local API inside the real MainWindow: the Look snapshot follows the
Compose form, Settings turns the server on and off, and closing the window
frees the port.

Offscreen, no network. The port comes from AIVS_LOCAL_API_PORT=0 (any free
port), so a running copy of the app on 8785 is never touched.
"""
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_ENV = Path(tempfile.gettempdir()) / "aivs-local-api-gui.env"
_ENV.write_text("AIVS_LOCAL_API_PORT=0\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_ENV)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ.setdefault("AIVS_HISTORY_FILE",
                      str(Path(tempfile.gettempdir()) / "aivs-local-api-gui-history.jsonl"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def settle(ms=400):
    """The snapshot follows the form on a short timer - let it fire."""
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def get(port, path):
    with urllib.request.urlopen("http://127.0.0.1:{}{}".format(port, path), timeout=5) as r:
        return json.loads(r.read())


win = MainWindow(ThemeManager(app))
win.show()
check("a test window does not bind the port on its own", win._local_api is None)

print("=== Look snapshot ===")
win.apply_lighting_phrase("hard noon sun from above")
win.apply_style_phrase("claymation, stop-motion texture")
win.apply_capture_overrides({"grain": ["shot on Kodak Portra 400"]})
settle()
look = win.current_look()
check("lighting reaches the snapshot", look["lighting"] == "hard noon sun from above", str(look))
check("style reaches the snapshot", look["style"] == "claymation, stop-motion texture")
check("capture reaches the snapshot", look["capture"] == ["shot on Kodak Portra 400"])
win.apply_camera_angle_phrase("low angle, looking up")
settle()
check("a typed camera angle reaches the snapshot",
      win.current_look()["camera"] == "low angle, looking up")

print("=== Settings toggle ===")
win.settings_view.local_api.setChecked(True)
win.start_local_api()
api = win._local_api
check("start_local_api starts the server", api is not None)
port = api.port if api else 0
check("Settings shows the address",
      str(port) in win.settings_view.local_api_state.text(),
      win.settings_view.local_api_state.text())
current = get(port, "/api/v1/look/current") if api else {}
check("the server serves the window's look", current.get("lighting") == "hard noon sun from above",
      str(current))
win.settings_view.local_api.setChecked(False)
check("unticking stops it", win._local_api is None)
check("Settings says off", win.settings_view.local_api_state.text().endswith("off"))
win.settings_view.local_api.setChecked(True)
check("ticking starts it again", win._local_api is not None)
win.close()
check("closing the window stops it", win._local_api is None)
win.settings.setValue("local_api", "true")

print()
print("{} failed".format(len(fails)) if fails else "ALL PASSED")
sys.exit(1 if fails else 0)
