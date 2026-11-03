"""Generate the application mark (assets/icons/app.png) and call make_exe_icon.

Usage:
    python tools/make_app_icon.py

Generates:
    assets/icons/app.png (512x512 RGBA)
    assets/icons/app.ico (multi-frame ICO: 16, 32, 48, 64, 128, 256)
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_SVG = ROOT / "assets" / "logo" / "export" / "ai-image-studio-symbol-app-icon.svg"
APP_PNG = ROOT / "assets" / "icons" / "app.png"
SCRATCH_RENDER = Path(
    r"C:\Users\Valentin\.gemini\antigravity\brain\ed201ea8-e0f7-4a37-a24e-84a936c975cd\scratch\logo-design\scripts\render_png.py"
)


def build() -> None:
    APP_PNG.parent.mkdir(parents=True, exist_ok=True)
    if SCRATCH_RENDER.exists() and SRC_SVG.exists():
        subprocess.run(
            [sys.executable, str(SCRATCH_RENDER), str(SRC_SVG), "-o", str(APP_PNG), "--size", "512"],
            check=True,
        )
        print(f"[app_icon] Rendered {APP_PNG}")

    # Pack into app.ico
    make_exe_icon = ROOT / "tools" / "make_exe_icon.py"
    if make_exe_icon.exists():
        subprocess.run([sys.executable, str(make_exe_icon)], check=True)


if __name__ == "__main__":
    build()

