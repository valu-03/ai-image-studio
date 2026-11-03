# PyInstaller build spec for AI Image Studio.
#
# Build:
#     pyinstaller AIImageStudio.spec
#
# Result: dist\AI Image Studio\AI Image Studio.exe
#
# Layout:
# contents_directory="." creates a flat one-folder distribution where:
# AI Image Studio.exe, tools/, assets/, web/dist/, .env, temp/
# all sit side-by-side.

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
ICON_PATH = ROOT / "assets" / "icons" / "app.ico"

datas = [
    ("tools", "tools"),
    ("assets", "assets"),
    ("workflows", "workflows"),
    ("mcp_server", "mcp_server"),
    ("web/dist", "web/dist"),
    (".env.example", "."),
]
binaries = []
hiddenimports = [
    "uuid",
    "multipart",
    "pythonnet",
    "clr",
    "PIL",
    "PIL.Image",
    "dotenv",
    "pydantic",
    "studio",
    "studio.desktop",
    "studio.server",
    "studio.state",
    "studio.compose_spec",
]

for package in ("webview", "uvicorn", "fastapi", "starlette"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["desktop_entry.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6", "PyQt5", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI Image Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
    icon=str(ICON_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AI Image Studio",
)

