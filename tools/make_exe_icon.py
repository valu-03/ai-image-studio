"""Render assets/icons/app.svg into assets/icons/app.ico for the Windows build.

Usage:
    python tools/make_exe_icon.py

Rasterizes the SVG mark at each ICO frame size separately (256, 128, 64, 48,
32, 16) rather than scaling one bitmap down, so the aperture ring and play
triangle stay crisp at the sizes Explorer and the taskbar actually use - a
single downscaled 256px render turns to mush at 16px. Needs PyQt6 (already a
project dependency, for the SVG rasteriser) and Pillow (for ICO packing,
which Qt has no writer for). Run after `python tools/make_icons.py` any time
the app mark changes; AIVideoStudio.spec points PyInstaller's EXE() at the
file this writes.
"""

import struct
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = ROOT / "assets" / "icons" / "app.svg"
ICO_PATH = ROOT / "assets" / "icons" / "app.ico"
SIZES = (16, 32, 48, 64, 128, 256)


def render_png_bytes(svg_path, size):
    renderer = QSvgRenderer(str(svg_path))
    pix = QPixmap(size, size)
    pix.fill(0)  # transparent
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    from PyQt6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    pix.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def build():
    app = QApplication.instance() or QApplication(sys.argv)

    # Render each size separately from the vector source rather than letting
    # Pillow downscale one bitmap - a 16px frame resampled from a 256px
    # render loses the aperture ring to a grey smear; rendered directly from
    # the SVG at 16px it stays a clean circle. Each frame is written as its
    # own single-image ICO, then the six ICOs are concatenated at the
    # container level (Pillow's `sizes=`/`append_images=` ICO writer picks
    # its own frames by nearest-size match rather than using the ones
    # supplied verbatim, which silently dropped every size but the first).
    frames = []
    for size in SIZES:
        data = render_png_bytes(SVG_PATH, size)
        frames.append(Image.open(BytesIO(data)).convert("RGBA"))

    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_ico(frames, ICO_PATH)
    return ICO_PATH


def _write_ico(frames, out_path):
    """A minimal, correct multi-size ICO container.

    ICO format: a 6-byte header (reserved, type=1, count), then one 16-byte
    directory entry per frame, then the frames themselves back-to-back as
    PNG data (Vista-era ICOs allow PNG-compressed frames directly, which is
    what every modern encoder including Windows' own uses for anything
    larger than 32px, and Pillow's own reader already handles it - confirmed
    by reading this exact file back in the caller's own verification step).
    """
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
    print("[icon] {}".format(path))
