"""Design tokens — the single source of colour, type, spacing and radius.

The dark palette is the one mandated by pyqt6_system_prompt.md §2 and is the
application default; every named token from that mandate keeps its value here.
The light palette is derived from it for the optional toggle; the accent,
success and semantic hues are held constant across both so a screenshot reads
the same either way.

The `accent2` / `primary_gradient` / `surface_glass` tokens are additive — a
second higgsfield.ai-inspired accent hue for gradient CTAs and glass surfaces,
layered on top of the mandated palette rather than replacing any of it.

Nothing in the UI hardcodes a colour or a pixel gap. It reads from here.
"""

# --- Spacing: strict 4px grid, spacious end of it -------------------------- #
SPACE = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 40}
CONTAINER_PADDING = SPACE["lg"]    # 24 — outer canvas breathing room
CARD_PADDING = 20                  # inner card padding, never cramped
COLUMN_GAP = SPACE["md"]           # 16

# --- Radius ---------------------------------------------------------------- #
RADIUS = {"sm": 4, "md": 8, "card": 12, "lg": 12, "xl": 16, "pill": 999}

# --- Typography ------------------------------------------------------------ #
FONT_UI = '"Inter", "Segoe UI Variable", "Segoe UI", system-ui, Arial, sans-serif'
FONT_MONO = '"JetBrains Mono", "Cascadia Mono", "Consolas", monospace'

TYPO = {
    "hero": (32, 750),      # section-opening headline, higgsfield-style scale
    "display": (26, 700),
    "headline": (19, 650),
    "title": (15, 600),
    "body": (14, 400),
    "body_sm": (13, 400),
    "label": (12, 600),
    "caption": (11, 500),
}

# --- Motion ------------------------------------------------------------ #
# Shared timings for QPropertyAnimation so hover/press/toggle feel the same
# everywhere rather than each view picking its own duration.
MOTION_FAST = 120     # hover/press micro-interactions, ms
MOTION_MED = 220       # card elevate, badge/theme crossfade, ms

# --- Layout ---------------------------------------------------------------- #
NAV_RAIL_WIDTH = 212
TOP_BAR_HEIGHT = 60
ICON_SIZE = 20
NAV_ICON_SIZE = 20

# --- Palettes -------------------------------------------------------------- #
# Mandated dark palette (pyqt6_system_prompt.md §2).
DARK = {
    "bg": "#0B0E14",                    # Background
    "surface": "#151A24",               # Cards / Surfaces
    "surface_variant": "#1B2230",       # derived — raised rows, inputs
    "surface_variant_high": "#232C3D",  # derived — pressed / hover ground
    "outline_variant": "#1A2333",       # Border Rules
    "outline": "#2A3648",               # derived — stronger dividers
    "text": "#F8FAFC",                  # Primary Text
    "text_muted": "#94A3B8",            # Secondary Muted Text
    "primary": "#38BDF8",               # Accent Primary
    "primary_container": "#0EA5E9",     # derived — pressed accent
    "primary_fixed": "#16344A",         # derived — selection ground
    "on_primary": "#061018",            # derived — text on accent
    "success": "#34D399",               # Success Green
    "warning": "#FBBF24",               # derived
    "error": "#F87171",                 # derived
    # --- additive: gradient accent pair + glass surface -------------------- #
    "accent2": "#8B5CF6",               # violet — second gradient stop
    "primary_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                         " stop:0 #38BDF8, stop:1 #8B5CF6)",
    "surface_glass": "rgba(21, 26, 36, 0.72)",
    "glow_primary": "rgba(56, 189, 248, 90)",
}

# Derived light counterpart; same accent, inverted grounds.
LIGHT = {
    "bg": "#F7F9FC",
    "surface": "#FFFFFF",
    "surface_variant": "#F1F5F9",
    "surface_variant_high": "#E2E8F0",
    "outline_variant": "#E2E8F0",
    "outline": "#CBD5E1",
    "text": "#0B0E14",
    "text_muted": "#64748B",
    "primary": "#0284C7",
    "primary_container": "#0369A1",
    "primary_fixed": "#DBEAFE",
    "on_primary": "#FFFFFF",
    "success": "#059669",
    "warning": "#B45309",
    "error": "#DC2626",
    # --- additive: gradient accent pair + glass surface -------------------- #
    "accent2": "#7C3AED",
    "primary_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                         " stop:0 #0284C7, stop:1 #7C3AED)",
    "surface_glass": "rgba(255, 255, 255, 0.72)",
    "glow_primary": "rgba(2, 132, 199, 70)",
}

PALETTES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"
