"""Build the official AI Image Studio logo kit.

Usage:
    python assets/logo/build_logo.py

Generates:
  assets/logo/
    ai-image-studio-symbol.svg
    ai-image-studio-symbol-small.svg
    ai-image-studio-symbol-reversed.svg
    ai-image-studio-horizontal.svg
    ai-image-studio-horizontal-reversed.svg
    ai-image-studio-stacked.svg
    ai-image-studio-stacked-reversed.svg
    ai-image-studio-wordmark.svg
    ai-image-studio-wordmark-reversed.svg
    export/
      ... (single-colour variants, web icons, favicons, app icons)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
EXPORT_DIR = HERE / "export"
SCRATCH_SKILL = Path(r"C:\Users\Valentin\.gemini\antigravity\brain\ed201ea8-e0f7-4a37-a24e-84a936c975cd\scratch\logo-design\scripts")

# Brand Palette:
# Charcoal ground, Safelight gold / darkroom amber, Crisp white
CHARCOAL = "#141413"
AMBER = "#F5C451"
WHITE = "#FFFFFF"

WORD_HEIGHT = 96
GAP = 40


def wordmark_path(text: str = "AI Image Studio"):
    """Outline `text` from Inter-SemiBold.ttf into (svg_d, (x, y, w, h)) with y down."""
    font_path = next((ROOT / "web").rglob("Inter-SemiBold*.ttf"))
    font = TTFont(str(font_path))
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    pen = SVGPathPen(glyphs)
    bounds = BoundsPen(glyphs)
    x = 0
    for ch in text:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, -1, x, 0)))
        x += hmtx[name][0]
    x0, y0, x1, y1 = bounds.bounds
    return pen.getCommands(), (x0, y0, x1 - x0, y1 - y0)


def circle_subpath(cx: float, cy: float, r: float) -> str:
    """Closed circle path as two exact 180-deg arcs."""
    x_left = cx - r
    x_right = cx + r
    return (
        f"M {x_left:.2f} {cy:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 1 {x_right:.2f} {cy:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 1 {x_left:.2f} {cy:.2f} Z"
    )


def make_symbol_path(
    box_min: float,
    box_max: float,
    arm_len: float,
    t: float,
    r_out: float,
    r_in: float,
    dot_cx: float,
    dot_cy: float,
    dot_r: float,
) -> str:
    """Parametric construction of the Off-Centre Frame mark on a 256 grid.

    Four bold viewfinder corner brackets framing an intentionally off-centre
    subject dot at the rule-of-thirds point.
    """
    # Top-left bracket
    tl = (
        f"M {box_min + r_out:.2f} {box_min:.2f} "
        f"H {box_min + arm_len:.2f} "
        f"V {box_min + t:.2f} "
        f"H {box_min + t + r_in:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 0 0 {box_min + t:.2f} {box_min + t + r_in:.2f} "
        f"V {box_min + arm_len:.2f} "
        f"H {box_min:.2f} "
        f"V {box_min + r_out:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 0 1 {box_min + r_out:.2f} {box_min:.2f} Z"
    )
    # Top-right bracket
    tr = (
        f"M {box_max - arm_len:.2f} {box_min:.2f} "
        f"H {box_max - r_out:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 0 1 {box_max:.2f} {box_min + r_out:.2f} "
        f"V {box_min + arm_len:.2f} "
        f"H {box_max - t:.2f} "
        f"V {box_min + t + r_in:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 0 0 {box_max - t - r_in:.2f} {box_min + t:.2f} "
        f"H {box_max - arm_len:.2f} "
        f"V {box_min:.2f} Z"
    )
    # Bottom-right bracket
    br = (
        f"M {box_max - t:.2f} {box_max - arm_len:.2f} "
        f"H {box_max:.2f} "
        f"V {box_max - r_out:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 0 1 {box_max - r_out:.2f} {box_max:.2f} "
        f"H {box_max - arm_len:.2f} "
        f"V {box_max - t:.2f} "
        f"H {box_max - t - r_in:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 0 0 {box_max - t:.2f} {box_max - t - r_in:.2f} "
        f"V {box_max - arm_len:.2f} Z"
    )
    # Bottom-left bracket
    bl = (
        f"M {box_min:.2f} {box_max - arm_len:.2f} "
        f"H {box_min + t:.2f} "
        f"V {box_max - t - r_in:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 0 0 {box_min + t + r_in:.2f} {box_max - t:.2f} "
        f"H {box_min + arm_len:.2f} "
        f"V {box_max:.2f} "
        f"H {box_min + r_out:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 0 1 {box_min:.2f} {box_max - r_out:.2f} "
        f"V {box_max - arm_len:.2f} Z"
    )
    subject = circle_subpath(dot_cx, dot_cy, dot_r)
    return " ".join([tl, tr, br, bl, subject])


def make_symbol_svg(title: str, path_d: str, colour: str = CHARCOAL) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" '
        'role="img" aria-labelledby="title">\n'
        f"  <title id=\"title\">{title}</title>\n"
        f"  <path id=\"symbol\" fill=\"{colour}\" fill-rule=\"evenodd\" d=\"{path_d}\"/>\n"
        "</svg>\n"
    )


def make_horizontal_svg(
    title: str,
    sym_d: str,
    wm_d: str,
    wm_bbox: tuple[float, float, float, float],
    colour: str = CHARCOAL,
) -> str:
    x, y, w, h = wm_bbox
    s = WORD_HEIGHT / h
    word_w = w * s
    tx = 256 + GAP - x * s
    ty = 128 - (y + h / 2.0) * s
    total_w = int(math.ceil(256 + GAP + word_w + 16))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 256" width="{total_w}" height="256" '
        'role="img" aria-labelledby="title">\n'
        f"  <title id=\"title\">{title}</title>\n"
        f"  <path id=\"symbol\" fill=\"{colour}\" fill-rule=\"evenodd\" d=\"{sym_d}\"/>\n"
        f"  <path id=\"wordmark\" fill=\"{colour}\" fill-rule=\"evenodd\" "
        f"transform=\"translate({tx:.1f} {ty:.1f}) scale({s:.5f})\" d=\"{wm_d}\"/>\n"
        "</svg>\n"
    )


def make_stacked_svg(
    title: str,
    sym_d: str,
    wm_d: str,
    wm_bbox: tuple[float, float, float, float],
    colour: str = CHARCOAL,
) -> str:
    x, y, w, h = wm_bbox
    s = 72.0 / h
    word_w = w * s
    word_h = h * s
    sw = int(math.ceil(max(word_w + 48, 280)))
    gap_y = 36.0
    sh = int(math.ceil(256 + gap_y + word_h + 24))
    sx = (sw - 256) / 2.0
    tx = (sw - word_w) / 2.0 - x * s
    ty = 256 + gap_y - y * s
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {sw} {sh}" width="{sw}" height="{sh}" '
        'role="img" aria-labelledby="title">\n'
        f"  <title id=\"title\">{title}</title>\n"
        f"  <path id=\"symbol\" fill=\"{colour}\" fill-rule=\"evenodd\" "
        f"transform=\"translate({sx:.1f} 0)\" d=\"{sym_d}\"/>\n"
        f"  <path id=\"wordmark\" fill=\"{colour}\" fill-rule=\"evenodd\" "
        f"transform=\"translate({tx:.1f} {ty:.1f}) scale({s:.5f})\" d=\"{wm_d}\"/>\n"
        "</svg>\n"
    )


def make_wordmark_svg(
    title: str,
    wm_d: str,
    wm_bbox: tuple[float, float, float, float],
    colour: str = CHARCOAL,
) -> str:
    x, y, w, h = wm_bbox
    s = WORD_HEIGHT / h
    word_w = int(math.ceil(w * s))
    word_h = int(math.ceil(h * s))
    tx = -x * s
    ty = -y * s
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {word_w} {word_h}" width="{word_w}" height="{word_h}" '
        'role="img" aria-labelledby="title">\n'
        f"  <title id=\"title\">{title}</title>\n"
        f"  <path id=\"wordmark\" fill=\"{colour}\" fill-rule=\"evenodd\" "
        f"transform=\"translate({tx:.1f} {ty:.1f}) scale({s:.5f})\" d=\"{wm_d}\"/>\n"
        "</svg>\n"
    )


def build_masters() -> dict[str, str]:
    HERE.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Geometry variants
    # Regular cut: optical balance on 256 grid
    sym_regular = make_symbol_path(
        box_min=24, box_max=232, arm_len=76, t=28, r_out=36, r_in=14, dot_cx=148, dot_cy=108, dot_r=36
    )
    # Small cut: heavier for <=32px displays, thicker arms, wider corners
    sym_small = make_symbol_path(
        box_min=20, box_max=236, arm_len=84, t=36, r_out=40, r_in=10, dot_cx=146, dot_cy=110, dot_r=42
    )
    # Reversed cut: thinned ~4% to offset visual irradiation on dark surfaces
    sym_reversed = make_symbol_path(
        box_min=24, box_max=232, arm_len=76, t=26, r_out=36, r_in=15, dot_cx=148, dot_cy=108, dot_r=34.5
    )

    wm_d, wm_bbox = wordmark_path("AI Image Studio")

    masters = {
        "ai-image-studio-symbol.svg": make_symbol_svg("AI Image Studio symbol", sym_regular, CHARCOAL),
        "ai-image-studio-symbol-small.svg": make_symbol_svg("AI Image Studio symbol (small sizes)", sym_small, CHARCOAL),
        "ai-image-studio-symbol-reversed.svg": make_symbol_svg("AI Image Studio symbol (on dark)", sym_reversed, AMBER),
        "ai-image-studio-horizontal.svg": make_horizontal_svg("AI Image Studio logo", sym_regular, wm_d, wm_bbox, CHARCOAL),
        "ai-image-studio-horizontal-reversed.svg": make_horizontal_svg(
            "AI Image Studio logo (on dark)", sym_reversed, wm_d, wm_bbox, AMBER
        ),
        "ai-image-studio-stacked.svg": make_stacked_svg("AI Image Studio logo (stacked)", sym_regular, wm_d, wm_bbox, CHARCOAL),
        "ai-image-studio-stacked-reversed.svg": make_stacked_svg(
            "AI Image Studio logo (stacked, on dark)", sym_reversed, wm_d, wm_bbox, AMBER
        ),
        "ai-image-studio-wordmark.svg": make_wordmark_svg("AI Image Studio wordmark", wm_d, wm_bbox, CHARCOAL),
        "ai-image-studio-wordmark-reversed.svg": make_wordmark_svg(
            "AI Image Studio wordmark (on dark)", wm_d, wm_bbox, AMBER
        ),
    }

    for name, content in masters.items():
        (HERE / name).write_text(content, encoding="utf-8")
        print(f"wrote master: {name}")

    return masters


def export_svg_and_web_variants():
    """Run export_variants tool to generate clean SVGs, icons, favicons and manifest."""
    export_tool = SCRATCH_SKILL / "export_variants.py"
    if not export_tool.exists():
        print(f"Warning: {export_tool} not found, skipping automated export script")
        return

    # Export symbol variants
    subprocess.run(
        [
            sys.executable,
            str(export_tool),
            str(HERE / "ai-image-studio-symbol.svg"),
            "--favicon-source",
            str(HERE / "ai-image-studio-symbol-small.svg"),
            "--mono",
            AMBER,
            "--icon-bg",
            CHARCOAL,
            "--icon-fg",
            AMBER,
            "--icon-scale",
            "0.62",
            "--title",
            "AI Image Studio",
            "--web-icons",
            "--out-dir",
            str(EXPORT_DIR),
        ],
        check=True,
    )

    # Export horizontal variants
    subprocess.run(
        [
            sys.executable,
            str(export_tool),
            str(HERE / "ai-image-studio-horizontal.svg"),
            "--only",
            "black",
            "white",
            "mono",
            "--mono",
            AMBER,
            "--title",
            "AI Image Studio",
            "--out-dir",
            str(EXPORT_DIR),
        ],
        check=True,
    )

    # Export stacked variants
    subprocess.run(
        [
            sys.executable,
            str(export_tool),
            str(HERE / "ai-image-studio-stacked.svg"),
            "--only",
            "black",
            "white",
            "mono",
            "--mono",
            AMBER,
            "--title",
            "AI Image Studio",
            "--out-dir",
            str(EXPORT_DIR),
        ],
        check=True,
    )


def sync_web_public_assets():
    """Copy web icons to web/public so Vite serves and embeds them cleanly."""
    web_public = ROOT / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)

    items = [
        "favicon.ico",
        "favicon.svg",
        "favicon-16.png",
        "favicon-32.png",
        "favicon-48.png",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "maskable-512.png",
        "site.webmanifest",
    ]
    for item in items:
        src = EXPORT_DIR / item
        if src.exists():
            shutil.copy2(src, web_public / item)
            print(f"synced to web/public: {item}")


def generate_app_icon_jpeg():
    """Generate a crisp high-res 1200x1200 JPEG to replace assets/icon_logo/ai_image_studio_logo.jpg."""
    from PIL import Image

    icon_logo_dir = ROOT / "assets" / "icon_logo"
    icon_logo_dir.mkdir(parents=True, exist_ok=True)
    target_jpg = icon_logo_dir / "ai_image_studio_logo.jpg"

    # Use the 512x512 rendered icon-512.png and compose on dark ground
    icon_png = EXPORT_DIR / "icon-512.png"
    if icon_png.exists():
        im = Image.open(icon_png).convert("RGBA")
        # Canvas 1200x1200 with #141413 ground
        canvas = Image.new("RGB", (1200, 1200), (20, 20, 19))
        im_resized = im.resize((840, 840), Image.Resampling.LANCZOS)
        offset = ((1200 - 840) // 2, (1200 - 840) // 2)
        canvas.paste(im_resized, offset, im_resized)
        canvas.save(str(target_jpg), "JPEG", quality=95)
        print(f"Generated official brand JPEG: {target_jpg}")


def run_audit():
    audit_tool = SCRATCH_SKILL / "svg_audit.py"
    if not audit_tool.exists():
        return
    for svg_file in HERE.glob("ai-image-studio*.svg"):
        res = subprocess.run([sys.executable, str(audit_tool), str(svg_file)], capture_output=True, text=True)
        print(f"Audit {svg_file.name}: {res.stdout.strip()}")


if __name__ == "__main__":
    build_masters()
    export_svg_and_web_variants()
    sync_web_public_assets()
    generate_app_icon_jpeg()
    run_audit()
