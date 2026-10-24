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
    "tab": (12, 600),       # tab labels: was the 11px caption, which read as fine print
    "caption": (11, 500),
    "mono": (13, 400),      # prompt text and other code-like fields
}

# Settings > Appearance "Text size": every TYPO size is multiplied by one of
# these when the sheet is built (ThemeManager.set_text_scale).
TEXT_SCALES = (1.0, 1.15, 1.3)

# The fonts the UI names, shipped in assets/fonts (SIL OFL, licences beside
# them) so every machine renders the same face rather than whatever Segoe or
# Consolas fallback it happens to have.
FONT_FILES = ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf",
              "JetBrainsMono-Regular.ttf", "JetBrainsMono-Medium.ttf")

# --- Motion ------------------------------------------------------------ #
# Shared timings for QPropertyAnimation so hover/press/toggle feel the same
# everywhere rather than each view picking its own duration.
MOTION_FAST = 120     # hover/press micro-interactions, ms
MOTION_MED = 220       # card elevate, badge/theme crossfade, ms
# Settings > Appearance "Reduce motion" turns these off: theme.motion_ms()
# returns 0 and the looping pulse() glow is not started.

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
    "outline_strong": "#64748B",        # derived — control edges (checkbox), 3.7:1 on surface
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

# Derived light counterpart; same accent hue, inverted grounds. Each text/fill
# pair here clears WCAG AA (4.5:1) on the grounds it is drawn on - the sky-600
# accent and emerald-600 success the first version used came out at 4.1:1 and
# 3.8:1 on white, and slate-500 muted text at 4.3:1 inside an input.
LIGHT = {
    "bg": "#F7F9FC",
    "surface": "#FFFFFF",
    "surface_variant": "#F1F5F9",
    "surface_variant_high": "#E2E8F0",
    "outline_variant": "#E2E8F0",
    "outline": "#CBD5E1",
    "outline_strong": "#7C8AA0",        # control edges (checkbox), 3.5:1 on surface
    "text": "#0B0E14",
    "text_muted": "#5B6B80",            # 5.0:1 on surface_variant
    "primary": "#0369A1",               # 5.9:1 on white, 4.9:1 on primary_fixed
    "primary_container": "#075985",
    "primary_fixed": "#DBEAFE",
    "on_primary": "#FFFFFF",
    "success": "#047857",               # 5.5:1
    "warning": "#B45309",
    "error": "#DC2626",
    # --- additive: gradient accent pair + glass surface -------------------- #
    "accent2": "#7C3AED",
    "primary_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                         " stop:0 #0369A1, stop:1 #7C3AED)",
    "surface_glass": "rgba(255, 255, 255, 0.72)",
    "glow_primary": "rgba(3, 105, 161, 70)",
}

PALETTES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"
