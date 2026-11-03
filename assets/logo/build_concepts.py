"""Build the three AI Image Studio logo concepts and lockups on a 256 grid.

    python assets/logo/build_concepts.py

All three concepts use pure filled <path> geometry (zero <text>, zero strokes,
exact 0/30/45/60/90 deg angles, true circular arcs) and an outlined wordmark
cut from Inter-SemiBold.ttf via fontTools.
"""

from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONCEPTS_DIR = HERE / "concepts"
CHARCOAL = "#141413"
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


def circle_subpath(cx: float, cy: float, r: float, ccw: bool = False) -> str:
    """Closed circle path as two exact 180-deg arcs."""
    sweep = 0 if ccw else 1
    x_left = cx - r
    x_right = cx + r
    return (
        f"M {x_left:.2f} {cy:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 {sweep} {x_right:.2f} {cy:.2f} "
        f"A {r:.2f} {r:.2f} 0 1 {sweep} {x_left:.2f} {cy:.2f} Z"
    )


def rounded_rect_subpath(x: float, y: float, w: float, h: float, r: float, ccw: bool = False) -> str:
    """Closed rounded rectangle path using exact 90-deg circular arcs."""
    x0, y0, x1, y1 = x, y, x + w, y + h
    if not ccw:
        return (
            f"M {x0 + r:.2f} {y0:.2f} "
            f"H {x1 - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x1:.2f} {y0 + r:.2f} "
            f"V {y1 - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x1 - r:.2f} {y1:.2f} "
            f"H {x0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0:.2f} {y1 - r:.2f} "
            f"V {y0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + r:.2f} {y0:.2f} Z"
        )
    return (
        f"M {x0 + r:.2f} {y0:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 0 {x0:.2f} {y0 + r:.2f} "
        f"V {y1 - r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 0 {x0 + r:.2f} {y1:.2f} "
        f"H {x1 - r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 0 {x1:.2f} {y1 - r:.2f} "
        f"V {y0 + r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 0 {x1 - r:.2f} {y0:.2f} "
        f"H {x0 + r:.2f} Z"
    )


def concept_a_offcentre_frame() -> str:
    """Concept A — Off-Centre Frame.

    Four bold viewfinder corner brackets (outer 24..232, inner 52..204,
    arm length 76, gap 56) framing an intentionally off-centre subject dot at
    the upper-right rule-of-thirds intersection (148, 108), r=34.
    All corners are exact 90-deg or circular arcs.
    """
    r_out = 36
    r_in = 14
    t = 28  # bracket stroke thickness
    # Top-left L-bracket: outer (24,24) to (100, 100)
    tl = (
        f"M {24 + r_out} 24 H 100 V {24 + t} H {52 + r_in} "
        f"A {r_in} {r_in} 0 0 0 52 {52 + r_in} V 100 H 24 V {24 + r_out} "
        f"A {r_out} {r_out} 0 0 1 {24 + r_out} 24 Z"
    )
    # Top-right L-bracket: outer (156..232, 24..100)
    tr = (
        f"M 156 24 H {232 - r_out} A {r_out} {r_out} 0 0 1 232 {24 + r_out} "
        f"V 100 H 204 V {52 + r_in} A {r_in} {r_in} 0 0 0 {204 - r_in} 52 "
        f"H 156 V 24 Z"
    )
    # Bottom-right L-bracket: outer (156..232, 156..232)
    br = (
        f"M 204 156 H 232 V {232 - r_out} A {r_out} {r_out} 0 0 1 {232 - r_out} 232 "
        f"H 156 V 204 H {204 - r_in} A {r_in} {r_in} 0 0 0 204 {204 - r_in} "
        f"V 156 Z"
    )
    # Bottom-left L-bracket: outer (24..100, 156..232)
    bl = (
        f"M 24 156 H 52 V {204 - r_in} A {r_in} {r_in} 0 0 0 {52 + r_in} 204 "
        f"H 100 V 232 H {24 + r_out} A {r_out} {r_out} 0 0 1 24 {232 - r_out} "
        f"V 156 Z"
    )
    # Off-centre subject circle at upper-right rule-of-thirds point (148, 108)
    subject = circle_subpath(148, 108, 36)
    return " ".join([tl, tr, br, bl, subject])


def concept_b_safelight_loupe() -> str:
    """Concept B — Safelight Loupe.

    A photographer's inspection loupe: heavy circular ring at (112, 112),
    R_out=84, R_in=52, with a 45-deg handle extending to bottom-right (224, 224)
    and an off-centre crescent lens glint inside.
    """
    cx, cy = 112.0, 112.0
    r_out = 84.0
    r_in = 52.0
    # Outer ring + 45-deg handle merged into one silhouette:
    # Handle runs at 45 deg from the ring's SE quadrant with half-width w=20.
    # Tangent intersections with r_out=84 at 45 deg +/- asin(20/84):
    w = 22.0
    alpha = math.asin(w / r_out)
    a1 = math.radians(45.0) - alpha
    a2 = math.radians(45.0) + alpha
    p1x, p1y = cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)
    p2x, p2y = cx + r_out * math.cos(a2), cy + r_out * math.sin(a2)
    # Handle length along 45 deg to tip centre (208, 208), capped by semicircle r=w
    ux, uy = math.cos(math.radians(45.0)), math.sin(math.radians(45.0))
    nx, ny = math.sin(math.radians(45.0)), -math.cos(math.radians(45.0))  # (+1/sqrt2, -1/sqrt2)
    tip_cx, tip_cy = 204.0, 204.0
    q1x, q1y = tip_cx + w * nx, tip_cy + w * ny
    q2x, q2y = tip_cx - w * nx, tip_cy - w * ny

    outer_with_handle = (
        f"M {p1x:.2f} {p1y:.2f} "
        f"L {q1x:.2f} {q1y:.2f} "
        f"A {w:.2f} {w:.2f} 0 0 1 {q2x:.2f} {q2y:.2f} "
        f"L {p2x:.2f} {p2y:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 1 1 {p1x:.2f} {p1y:.2f} Z"
    )
    hole = circle_subpath(cx, cy, r_in, ccw=True)
    # Off-centre focal dot inside the loupe at (98, 98), r=20
    glint = circle_subpath(98.0, 98.0, 20.0, ccw=False)
    return " ".join([outer_with_handle, hole, glint])


def concept_c_window_prism_a() -> str:
    """Concept C — Window Light AI Monogram.

    A bold geometric 'A' + 'I' built inside a 256 grid where:
    - The left leg of A slopes at exact 60 deg from bottom-left (28, 224) to apex (108, 32)
      Wait: dx=80, dy=192 -> to keep exact 60 deg (tan 60 = sqrt(3) = 1.73205):
      Let's use an architectural darkroom window frame where a 45-deg sunlight beam
      carves the letter A and illuminates the vertical pillar I!
    Let's check the exact coordinates (all 0/90/45 deg angles):
    - Left block forms a bold structural 'A' with a 45-deg slanted roof/beam:
      Outer contour of A: (28, 224) -> (28, 108) -> 45-deg slope to (108, 28) ->
      (148, 28) -> (148, 224) -> (112, 224) -> (112, 156) -> (64, 156) -> (64, 224) Z
      Counter (window opening inside A, 45-deg top):
      (64, 124) -> (112, 124) -> (112, 68) -> (64, 116) Z
    - Right pillar 'I' with off-centre circular sun/safelight disc above:
      Vertical bar x=180..220, y=100..224
      Circle above at (200, 56), r=24.
    Every segment is strictly horizontal (0 deg), vertical (90 deg), or 45 deg!
    """
    a_outer = (
        "M 28 224 V 108 L 108 28 H 148 V 224 H 112 V 160 H 64 V 224 H 28 Z"
    )
    a_window_hole = (
        "M 64 128 H 112 V 68 L 64 116 V 128 Z"
    )
    i_stem = "M 180 100 H 220 V 224 H 180 V 100 Z"
    i_dot = circle_subpath(200.0, 56.0, 24.0)
    return " ".join([a_outer, a_window_hole, i_stem, i_dot])


def make_symbol_svg(title: str, path_d: str, colour: str = CHARCOAL) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" '
        'role="img" aria-labelledby="title">\n'
        f"  <title id=\"title\">{title}</title>\n"
        f"  <path id=\"symbol\" fill=\"{colour}\" fill-rule=\"evenodd\" d=\"{path_d}\"/>\n"
        "</svg>\n"
    )


def make_lockup_svg(title: str, sym_d: str, wm_d: str, wm_bbox: tuple[float, float, float, float], colour: str = CHARCOAL) -> str:
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


def main() -> None:
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    wm_d, wm_bbox = wordmark_path("AI Image Studio")

    concepts = [
        ("a", "AI Image Studio — Off-Centre Frame", concept_a_offcentre_frame()),
        ("b", "AI Image Studio — Safelight Loupe", concept_b_safelight_loupe()),
        ("c", "AI Image Studio — Window Light AI", concept_c_window_prism_a()),
    ]
    for code, title, sym_d in concepts:
        sym_file = CONCEPTS_DIR / f"{code}-symbol.svg"
        lock_file = CONCEPTS_DIR / f"{code}-lockup.svg"
        sym_file.write_text(make_symbol_svg(title, sym_d), encoding="utf-8")
        lock_file.write_text(make_lockup_svg(title, sym_d, wm_d, wm_bbox), encoding="utf-8")
        print(f"Wrote {sym_file.name} and {lock_file.name}")


if __name__ == "__main__":
    main()
