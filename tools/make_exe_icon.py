"""Pack assets/icons/app.png into assets/icons/app.ico for the Windows build.

Usage:
    python tools/make_exe_icon.py

Writes six frames (256, 128, 64, 48, 32, 16), each resampled straight from the
512px app.png with Lanczos rather than chained down from the previous frame,
so the small sizes Explorer and the taskbar use stay as sharp as a raster
source allows. Needs Pillow only.
"""

import struct
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG_PATH = ROOT / "assets" / "icons" / "app.png"
ICO_PATH = ROOT / "assets" / "icons" / "app.ico"
SIZES = (16, 32, 48, 64, 128, 256)


def build(png_path: Path = PNG_PATH, ico_path: Path = ICO_PATH) -> Path:
    source = Image.open(png_path).convert("RGBA")
    frames = [source.resize((size, size), Image.Resampling.LANCZOS) for size in SIZES]

    ico_path.parent.mkdir(parents=True, exist_ok=True)
    _write_ico(frames, ico_path)
    return ico_path


def _write_ico(frames: list[Image.Image], out_path: Path) -> None:
    """A minimal, correct multi-size ICO container with PNG compressed frames."""
    entries = []
    frame_bytes = []
    for im in frames:
        buf = BytesIO()
        im.save(buf, format="PNG")
        data = buf.getvalue()
        frame_bytes.append(data)
        w = im.width if im.width < 256 else 0
        h = im.height if im.height < 256 else 0
        entries.append((w, h, len(data)))

    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    directory = b""
    for (w, h, size), data in zip(entries, frame_bytes):
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, offset)
        offset += len(data)

    with open(out_path, "wb") as fh:
        fh.write(header)
        fh.write(directory)
        for data in frame_bytes:
            fh.write(data)


if __name__ == "__main__":
    path = build()
    print(f"[icon] Wrote multi-frame ICO to {path}")

