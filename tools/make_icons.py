"""Generate the SVG icon set into assets/icons/.

Each icon is emitted twice — a muted variant for the resting state and an accent
variant for the active/selected state — because QIcon cannot recolour an SVG at
runtime. Re-run after changing a glyph or a palette colour:

    python tools/make_icons.py

Standard library only.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"

MUTED = "#94A3B8"
ACCENT = "#38BDF8"

# 24x24 stroke glyphs. {c} is substituted with the stroke colour.
GLYPHS = {
    "compose": '<path d="M4 20h16M6 16l9.5-9.5a2.1 2.1 0 0 0-3-3L3 13v3h3z"/>',
    "images": (
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/>'
        '<path d="M21 15l-5-5L5 21"/>'
    ),
    "videos": (
        '<rect x="2" y="5" width="14" height="14" rx="2"/>'
        '<path d="M16 10l6-3v10l-6-3z"/>'
    ),
    "brief": (
        '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
        '<path d="M14 3v5h5M9 13h6M9 17h4"/>'
    ),
    # A speech bubble (a running conversation, distinct from "brief"'s single
    # page) with a small four-point spark inside it - the one detail that
    # reads as "the expert one," not just "chat."
    "advisor": (
        '<path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 4v-4H6'
        'a2 2 0 0 1-2-2z"/>'
        '<path d="M13.5 6.2l.7 1.7 1.7.7-1.7.7-.7 1.7-.7-1.7-1.7-.7 1.7-.7z"/>'
    ),
    "variants": (
        '<rect x="3" y="3" width="8" height="8" rx="2"/>'
        '<rect x="13" y="3" width="8" height="8" rx="2"/>'
        '<rect x="3" y="13" width="8" height="8" rx="2"/>'
        '<rect x="13" y="13" width="8" height="8" rx="2"/>'
    ),
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 4v4h4"/><path d="M12 7v5l3 2"/>',
    "insights": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1'
        'M19.1 4.9L17 7M7 17l-2.1 2.1"/>'
    ),
    "generate": '<path d="M12 2l2.2 6.4L21 10l-6.8 1.6L12 18l-2.2-6.4L3 10l6.8-1.6z"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    "save": (
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<path d="M17 21v-8H7v8M7 3v5h8"/>'
    ),
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "shuffle": '<path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/>',
    "star": '<path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "ads": (
        '<path d="M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1z"/>'
        '<path d="M17 9.5a3.5 3.5 0 0 1 0 5"/>'
        '<path d="M20 7a7 7 0 0 1 0 10"/>'
    ),
    # Ears, head, eyes, whiskers. The ears are what make it read as a cat at
    # 20px rather than as a generic animal.
    "cats": (
        '<path d="M6.5 7.6 L5.4 3.4 L9.6 5.6"/>'
        '<path d="M17.5 7.6 L18.6 3.4 L14.4 5.6"/>'
        '<circle cx="12" cy="13" r="6.8"/>'
        '<path d="M9.6 12h.01M14.4 12h.01"/>'
        '<path d="M3.6 13.6h2.6M17.8 13.6h2.6"/>'
    ),
    # A level meter rather than a speaker: the ads glyph is already a speaker
    # with waves, and two horns in one rail is one too many.
    "sound": '<path d="M4 10v4M8 6.5v11M12 3v18M16 7.5v9M20 10.5v3"/>',
    # A lightbulb, not a sun - "settings" already owns the sun/gear shape
    # (a circle with 8 radiating spokes), and a second sun-like glyph two
    # rows away would read as a duplicate rather than a distinct category.
    "lighting": (
        '<path d="M9 18h6M10 21h4"/>'
        '<path d="M12 3a6 6 0 0 0-3 11.2c.6.4 1 1.1 1 1.8h4c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3z"/>'
    ),
    # A rule-of-thirds grid, the frame's own edge plus two guide lines each way,
    # with a small ring on one intersection - the subject placed on a third
    # rather than centred. Small stroked circle, no local fill override, the
    # same convention "images"' own lens-dot glyph already uses. Distinct from
    # "variants"' four separate rounded tiles (no gaps here, one continuous
    # frame) and from "settings"' circular sun/gear mark.
    "composition": (
        '<rect x="3" y="3" width="18" height="18" rx="1.5"/>'
        '<path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>'
        '<circle cx="9" cy="9" r="1.3"/>'
    ),
    # A simple stick figure - head, spine, arms angled out, legs in a
    # walking stance rather than straight down, so it reads as a POSE
    # rather than a generic person/user icon.
    "posing": (
        '<circle cx="12" cy="4.2" r="2.1"/>'
        '<path d="M12 7.3v6.5M12 9.5l-4 2.5M12 9.5l4 2.5M12 13.8l-3.4 6.2M12 13.8l3.4 6.2"/>'
    ),
    # A painter's palette outline with three small paint-dot wells - reads as
    # "color" distinctly from "composition"'s grid and "lighting"'s bulb.
    "color": (
        '<path d="M12 3a9 9 0 1 0 4.5 16.8c1-.6.7-2-.4-2.3-1-.3-1.6-1.2-1.3-2.2'
        '.3-1 1.3-1.5 2.3-1.3A3 3 0 0 0 20 12a9 9 0 0 0-8-9z"/>'
        '<circle cx="8" cy="10.5" r="1.1"/>'
        '<circle cx="12" cy="8" r="1.1"/>'
        '<circle cx="16" cy="10.5" r="1.1"/>'
    ),
    # A small camera body low in the frame with a curved arrow above it
    # sweeping from low to high - reads as "camera position/angle" distinct
    # from "videos"' own plain camera-with-play-wedge glyph.
    "camera_angle": (
        '<rect x="4" y="13" width="12" height="8" rx="1.5"/>'
        '<path d="M16 16l4-2v6l-4-2"/>'
        '<path d="M6 10.5A8 8 0 0 1 18 5"/>'
        '<path d="M15.5 3.8 18 5l-1 2.7"/>'
    ),
    # A persona/contact card - a rounded card, an avatar circle with shoulders,
    # two text lines - reads as "a saved profile" distinctly from "posing"'s
    # walking stick figure and "cats"'s animal glyph.
    "influencer_studio": (
        '<rect x="3" y="4" width="18" height="16" rx="2"/>'
        '<circle cx="8.5" cy="10.3" r="2.2"/>'
        '<path d="M5 16c0-1.9 1.6-3 3.5-3s3.5 1.1 3.5 3"/>'
        '<path d="M14.5 9h4M14.5 12.5h4"/>'
    ),
    # An eye - the "Look" section is literally about how the image looks.
    # Distinct from every other rail glyph; no filled iris, matching the
    # small stroked-ring convention "images"/"composition" already use.
    "look": (
        '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    # A speech bubble with three dots - a helper you talk to, one step
    # simpler than "advisor"'s bubble-with-spark (which is now a tab inside
    # this section, not its own rail entry).
    "assistant": (
        '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.2'
        'A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/>'
        '<path d="M9 12h.01M12.5 12h.01M16 12h.01"/>'
    ),
    # An activity pulse line - "Activity" groups History and What works.
    # Distinct from "insights"' static bar chart.
    "activity": '<path d="M3 12h3.5l2.5 7 4.5-15 3 8H21"/>',
}

TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

# --------------------------------------------------------------------------- #
# The application mark
# --------------------------------------------------------------------------- #
# A camera aperture whose opening is a play triangle: stills becoming video,
# which is what this app does. Unlike the nav glyphs this one is filled rather
# than stroked, because it has to survive being drawn at 16px in a taskbar
# where hairline strokes disappear.
#
# The background gradient is `tokens.py`'s own `primary_gradient` colours
# (#38BDF8 -> #8B5CF6, the exact pair reserved for the app's one CTA-gradient
# per view and the credits/busy badge) rather than the mono-blue pair this
# mark used before - the icon is the single outermost brand mark, the one
# place that signature gradient belongs at full strength, not a second
# invented palette living next to it.
INK = "#0B0E14"
GRADIENT_FROM = "#38BDF8"    # tokens.DARK["primary"]
GRADIENT_TO = "#8B5CF6"      # tokens.DARK["accent2"]
INK_HIGHLIGHT = "#232C3D"    # tokens.DARK["surface_variant_high"] - play-triangle sheen

# Three chords of the ring, 120 degrees apart, each 7px from the centre. Three
# such chords enclose a triangle, and set this way its vertex points right - so
# the aperture's opening IS the play triangle rather than a shape laid on top of
# one. Each blade is collinear with a triangle edge and runs on to the ring,
# which is what an iris actually looks like; radial spokes read as spikes.
#
#   ring r=20, chord offset d=7  ->  half-length sqrt(400-49) = 18.73
#   opening: (46,32) right vertex, (25,19.88) and (25,44.12)
#
# Drawn at half-length 18 rather than the full 18.73 so that the round cap ends
# just inside the ring instead of poking through it. This geometry is proven
# (it is what reads correctly down to 16px) and untouched by the polish pass
# below - only how it is coloured and what surrounds it changed.
_BLADES = (
    '<path d="M19.91 47.06 L51.09 29.06"/>'
    '<path d="M25 50 L25 14"/>'
    '<path d="M19.91 16.94 L51.09 34.94"/>'
)
# A second, thinner ring just inside the main one - a coated-lens rim detail,
# purely decorative at r=17.4 so it never intersects the blade/play geometry
# above, which is all keyed off the outer r=20 ring.
_INNER_RING = '<circle cx="32" cy="32" r="17.4" stroke-width="1.1" opacity="0.55"/>'
_RING = '<circle cx="32" cy="32" r="20"/>'
_PLAY = (
    '<path d="M25 19.88 L25 44.12 L46 32 Z" fill="url(#play)" stroke="none"/>'
)

APP_MARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
    'viewBox="0 0 64 64">'
    '<defs>'
    '<linearGradient id="g" x1="2" y1="2" x2="62" y2="62" '
    'gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/>'
    '</linearGradient>'
    # The play triangle's own subtle gradient - flat ink read as a hole
    # punched in the mark; a near-black-to-slightly-lighter fill reads as a
    # lens with actual depth instead.
    '<linearGradient id="play" x1="25" y1="20" x2="46" y2="44" '
    'gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="{ink}"/><stop offset="1" stop-color="{ink_hi}"/>'
    '</linearGradient>'
    # A soft glass highlight in the upper-left, the way a real camera lens'
    # coating catches light - clipped to the rounded square so it can never
    # spill past the mark's own edge.
    '<radialGradient id="sheen" cx="0.28" cy="0.22" r="0.55">'
    '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.38"/>'
    '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>'
    '</radialGradient>'
    # A faint bottom vignette for grounding - the same reasoning modern
    # Fluent/macOS marks use a soft inner shadow at the base for.
    '<linearGradient id="vignette" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0.55" stop-color="#000000" stop-opacity="0"/>'
    '<stop offset="1" stop-color="#000000" stop-opacity="0.16"/>'
    '</linearGradient>'
    '<clipPath id="clip"><rect x="0" y="0" width="64" height="64" rx="16"/></clipPath>'
    '</defs>'
    '<g clip-path="url(#clip)">'
    '<rect x="0" y="0" width="64" height="64" rx="16" fill="url(#g)"/>'
    '<rect x="0" y="0" width="64" height="64" fill="url(#sheen)"/>'
    '<rect x="0" y="0" width="64" height="64" fill="url(#vignette)"/>'
    '<g fill="none" stroke="{ink}" stroke-width="3.8" stroke-linecap="round">'
    '{body}</g>'
    '</g>'
    '</svg>'
)


# Every name this module writes a resting/active pair for. ui/assets.py has to
# register all of them; the two tables are hand-maintained and assets.icon()
# returns an empty QIcon rather than raising, so a name in one and not the other
# shows up as a silently blank icon. tests/test_layout.py asserts the subset.
ICON_NAMES = set(GLYPHS) | {"app"}


def app_mark():
    """The application mark, as SVG. One version: it reads down to 16px."""
    body = _RING + _INNER_RING + _BLADES + _PLAY
    return APP_MARK.format(a=GRADIENT_FROM, b=GRADIENT_TO, ink=INK,
                            ink_hi=INK_HIGHLIGHT, body=body)


def build():
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in GLYPHS.items():
        for suffix, colour in [("", MUTED), ("-active", ACCENT)]:
            path = ICON_DIR / "{}{}.svg".format(name, suffix)
            path.write_text(TEMPLATE.format(c=colour, body=body), encoding="utf-8")
            written.append(path)

    # The mark is full-colour, so both states are the same file rather than a
    # muted/accent pair - but both names exist so assets.icon("app") behaves
    # like every other entry. No separate small variant: rendered at 16px the
    # blades still read, so a second file would be an asset nothing uses.
    for suffix in ("", "-active"):
        path = ICON_DIR / "app{}.svg".format(suffix)
        path.write_text(app_mark(), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    files = build()
    print("Wrote {} icons to {}".format(len(files), ICON_DIR))
