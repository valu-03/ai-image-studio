"""Cut the application mark out of the full logo into assets/icons/app.png.

Usage:
    python tools/make_app_icon.py

assets/icons/app-source.jpg is the user's full logo: the "AI" + film-strip
play mark with "AI VIDEO STUDIO" lettered underneath, on a near-white
background. At icon sizes (16-48px) that lettering is unreadable noise, so
only the mark is used: it is found by its ink (anything clearly darker than
the background) above the lettering, then centred on a white rounded tile.
The tile is the logo's own background - without it the navy "AI" all but
disappears on a dark taskbar or the dark theme's rail.

Run tools/make_exe_icon.py afterwards to refresh app.ico for the .exe.
Needs Pillow only.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icons" / "app-source.jpg"
OUT = ROOT / "assets" / "icons" / "app.png"
SIZE = 512
CORNER = 0.22          # tile corner radius, as a share of the side
MARK_WIDTH = 0.82      # the mark's width, as a share of the side
INK = 200              # a pixel whose darkest channel is below this is mark, not background
LETTERING_GAP = 0.62   # the lettering starts below this share of the logo's height


def mark_box(logo):
    """Bounding box of the mark: the ink above the lettering."""
    top = logo.crop((0, 0, logo.width, int(logo.height * LETTERING_GAP)))
    darkest = top.convert("L").point(lambda v: 255 if v < INK else 0)
    box = darkest.getbbox()
    if box is None:
        raise SystemExit("No mark found in {}".format(SOURCE))
    pad = 4
    return (max(box[0] - pad, 0), max(box[1] - pad, 0),
            min(box[2] + pad, logo.width), min(box[3] + pad, top.height))


def build():
    logo = Image.open(SOURCE).convert("RGB")
    mark = logo.crop(mark_box(logo))
    # The background behind the mark is 254,254,254 rather than pure white;
    # lift anything that close to white so no faint box shows on the tile.
    mark = ImageChops.add(mark, Image.new("RGB", mark.size, (2, 2, 2)))

    scale = SIZE * MARK_WIDTH / mark.width
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)),
                       Image.Resampling.LANCZOS)

    tile = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
    tile.paste(mark, ((SIZE - mark.width) // 2, (SIZE - mark.height) // 2))

    # Round the corners with a 4x supersampled mask so the edge is smooth.
    big = SIZE * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1),
                                           radius=int(big * CORNER), fill=255)
    tile.putalpha(mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS))

    tile.save(OUT)
    return OUT


if __name__ == "__main__":
    print("[icon] {}".format(build()))
