"""Desktop entry: FastAPI served on a local port inside a pywebview window,
plus the in-process Local API on 8785 for Skit Studio and MCP."""

import multiprocessing
import socket
import sys
import threading
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import generate_image as gi  # noqa: E402
import local_api  # noqa: E402
from studio.server import LOCAL_API_VAR, create_app  # noqa: E402
from studio.state import LookState  # noqa: E402

RESERVED_PORTS = frozenset({3900, 8765, 8770, 8780, 8785, 8791, 8799})


def free_port() -> int:
    """Bind 127.0.0.1 on an ephemeral port, avoiding reserved ports."""
    for _ in range(32):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in RESERVED_PORTS:
            return port
    raise RuntimeError("Could not find a free port")


def start_local_api(state: LookState, enabled: bool = True, port: int | None = None,
                    on_image=None):
    """Start the 8785 Local API wired to `state.current_phrases`.

    Returns (LocalApi | None, error_str | None). Never raises if the port is taken.
    """
    if not enabled:
        return None, None
    target_port = local_api.configured_port() if port is None else port
    try:
        api = local_api.start(
            port=target_port,
            current_look=state.current_phrases,
            on_image=on_image,
        )
        return api, None
    except OSError:
        return None, "Skit Studio connection couldn't start: port {} is in use".format(target_port)


def start_server(app, port: int):
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="studio-uvicorn")
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            server.should_exit = True
            raise RuntimeError("AI Image Studio server failed to start within 10 s")
        time.sleep(0.05)
    return server, thread


def main() -> int:
    multiprocessing.freeze_support()
    import webview

    state = LookState()
    static_dir = ROOT / "web" / "dist"
    app = create_app(static_dir if static_dir.is_dir() else None, state)

    env = gi.read_env()
    enabled = gi.env_value(LOCAL_API_VAR, env) != "0"
    api, err = start_local_api(state, enabled)
    app.state.local_api = {"running": api is not None, "error": err or ""}

    port = free_port()
    server, thread = start_server(app, port)
    try:
        webview.create_window(
            "AI Image Studio",
            f"http://127.0.0.1:{port}/",
            width=1440,
            height=900,
            min_size=(1280, 720),
        )
        icon_path = ROOT / "assets" / "icons" / "app.ico"
        webview.start(icon=str(icon_path) if icon_path.exists() else None)
    finally:
        if api is not None:
            api.stop()
        server.should_exit = True
        thread.join(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
