# PyInstaller build spec for AI Video Studio.
#
# Build:
#     pip install pyinstaller
#     pyinstaller AIVideoStudio.spec
#
# Result: dist\AI Video Studio\AI Video Studio.exe
#
# Why this is written by hand rather than generated from CLI flags, and why it
# looks the way it does - see the plan this came from (or CLAUDE.md's own
# rule, once transcribed there): every module in tools/ and ui/ computes its
# own project root as Path(__file__).resolve().parent(.parent), and derives
# BOTH the read-only bundled banks/assets AND the user's real data (.env,
# temp/outputs/, temp/resources/characters/) from that one root. A one-file
# build re-extracts to a fresh temp folder every launch, which would silently
# lose the character library and generation history on every close. Modern
# PyInstaller's default one-folder layout also nests everything a level
# deeper than expected, inside a _internal/ subfolder.
#
# contents_directory="." below restores the pre-6.0 flat layout instead:
# everything lands directly beside the .exe, exactly mirroring today's dev
# checkout (tools/, assets/, and - once created - .env and temp/ all sit in
# the same folder the executable is in). That is what lets every existing
# Path(__file__).resolve().parent(.parent) computation keep working completely
# unmodified; none of the ~20 files that compute ROOT need to change for this.
#
# tools/ is shipped as DATA (real, loose .py + .json files copied into a real
# tools/ subfolder), not analysed and frozen as importable modules the way
# ui/ is. This was tried the other way first (pathex=["tools"], so PyInstaller
# would resolve "import build_prompt as bp" as a top-level module) and it
# broke ROOT math: tools/ has no __init__.py, so a pathex-discovered module is
# flattened to look like it lives directly beside the exe, not inside tools/ -
# Path(__file__).resolve().parent then pointed AT the app root instead of
# tools/, and Path(__file__).resolve().parent.parent (every tools/*.py's own
# ROOT) pointed one level ABOVE the app root entirely. Shipping tools/ as
# loose files instead means each module's __file__ is a real on-disk path
# exactly where it is in the source repo, so every existing ROOT computation
# resolves exactly as it does today - the runtime sys.path.insert() every
# ui/*.py already does finds and imports them completely normally. PyInstaller
# will warn that it "cannot find" build_prompt/generate_image/etc. during the
# build (its static analysis has no pathex pointing at them any more) - that
# warning is expected and harmless, since the files are on disk via `datas`
# at exactly the path the runtime sys.path trick already looks for them.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
# The .exe's own icon (Explorer, taskbar-before-launch, shortcuts) is separate
# from the PNG QIcon the running app sets on its window - PyInstaller's EXE()
# needs a real .ico file at build time, which tools/make_exe_icon.py packs
# from assets/icons/app.png. Re-run that script (after tools/make_app_icon.py,
# if the logo itself changed) before rebuilding if app.ico is stale.
ICON_PATH = ROOT / "assets" / "icons" / "app.ico"

datas = [
    ("tools", "tools"),
    ("assets", "assets"),
    # The in-app Guides dialog reads these at runtime. Without this line the
    # frozen build has no onboarding at all: ui/views/guides.py falls back to
    # a source-tree path that does not exist beside the .exe.
    ("workflows", "workflows"),
    (".env.example", "."),
]
binaries = []
# tools/ is unanalysed (see the header comment above), so a stdlib module (or
# third-party package) imported ONLY from inside tools/ - never from anything
# ui/ or gui.py itself imports - is invisible to PyInstaller's static analysis
# and is silently left out of the frozen build. `uuid` is exactly that case:
# tools/generate_sound.py's multipart boundary is the only place in this
# project that imports it. Found by actually launching the built .exe, not
# by reading the spec - it raised ModuleNotFoundError on the very first
# import of a view that reaches elevenlabs_voices.py -> generate_sound.py.
# The other stdlib modules the new ElevenLabs tools use (json, mimetypes,
# urllib.*, datetime, argparse, pathlib) were already proven safe by the
# existing tools that also use them (generate_image.py, generate_video.py).
# `imageio_ffmpeg` is the same trap: only tools/render_video.py imports it.
# Unlike `uuid`, this one needs no manual `binaries` entry alongside it -
# imageio_ffmpeg ships its own PyInstaller hook, which only runs once this
# hiddenimports entry makes PyInstaller aware the package is used at all, and
# that hook bundles the real ffmpeg.exe at its normal package-relative path
# (imageio_ffmpeg/binaries/ffmpeg-*.exe) on its own - confirmed by inspecting
# a real build's dist/ folder, not assumed from the package's docs.
# The Local API for Skit Studio (tools/local_api.py, tools/skit_client.py) is the only user of
# these stdlib modules - unanalysed like every tools/ file, so they are named here.
hiddenimports = ["uuid", "imageio_ffmpeg", "http.server", "socketserver", "hmac", "mimetypes",
                 "concurrent.futures", "urllib.parse", "urllib.request", "urllib.error", "base64"]

# The app renders every icon from SVG at runtime (QIcon(str(svg_path)) in
# ui/assets.py), which depends on Qt's SVG icon-engine plugin. Rather than
# chasing missing-plugin errors one at a time, collect everything PyQt6 ships -
# the standard robust approach for a PyQt app.
for package in ("PyQt6",):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI Video Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # First build: leave this True. A console window shows any import/plugin
    # error instead of the app just failing to appear with nothing to go on.
    # Once a clean run is confirmed, flip to False and rebuild for daily use.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # The flat layout this whole spec exists for - see the file header.
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
    name="AI Video Studio",
)
