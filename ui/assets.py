"""Asset configuration table.

Every path the UI loads from disk is declared here as a global, so no widget
constructs a path inline. Regenerate the SVGs with `python tools/make_icons.py`.
"""

from pathlib import Path

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets"
ICON_DIR = ASSET_DIR / "icons"

CHARACTERS_DIR = ROOT / "temp" / "resources" / "characters"
# Influencer Studio's own roster - a lighter, structured JSON shape (name,
# gender, age range, style tags, hair/eye colour, details, reference image
# paths) than a full character spec, so it gets its own folder rather than
# being crammed into CHARACTERS_DIR. Reference images stay a local mood
# board here; they are never copied elsewhere and never touch
# SpecEditor.set_reference()/lock_identity.
PERSONAS_DIR = ROOT / "temp" / "resources" / "personas"
PROMPTS_DIR = ROOT / "temp" / "outputs" / "prompts"
IMAGES_DIR = ROOT / "temp" / "outputs" / "images"
VIDEOS_DIR = ROOT / "temp" / "outputs" / "videos"
SOUND_DIR = ROOT / "temp" / "outputs" / "sound"
VOICE_DIR = ROOT / "temp" / "outputs" / "voice"
OUTPUTS_DIR = ROOT / "temp" / "outputs"
ENV_PATH = ROOT / ".env"

# Every folder a generation of any kind writes into - named here for reference
# and by ensure_output_dirs() below. Before VIDEOS_DIR was added, this table
# had no entry for generate_video.py's own temp/outputs/videos/ at all, so
# nothing created it until the first clip was ever rendered and Settings had
# no "Open Videos folder" button to offer. SOUND_DIR/VOICE_DIR follow the same
# rule from day one of the ElevenLabs integration, not added after the fact.
ALL_OUTPUT_DIRS = (CHARACTERS_DIR, PERSONAS_DIR, PROMPTS_DIR, IMAGES_DIR, VIDEOS_DIR,
                   SOUND_DIR, VOICE_DIR)


def ensure_output_dirs():
    """Create every declared output folder. Safe to call every launch.

    Reads the module attributes live rather than closing over `ALL_OUTPUT_DIRS`
    at import time - tests repoint `assets.CHARACTERS_DIR` at a temp directory
    for isolation, and this must follow that redirection, not the original.
    """
    for name in ("CHARACTERS_DIR", "PERSONAS_DIR", "PROMPTS_DIR", "IMAGES_DIR",
                 "VIDEOS_DIR", "SOUND_DIR", "VOICE_DIR"):
        globals()[name].mkdir(parents=True, exist_ok=True)

ICON_SIZE = QSize(20, 20)
NAV_ICON_SIZE = QSize(20, 20)
STAR_ICON_SIZE = QSize(18, 18)
BRAND_ICON_SIZE = QSize(24, 24)

# name -> (resting svg, active svg)
ICONS = {
    # The application mark - window, taskbar and the rail's brand row. Both
    # entries are the same file: it is full-colour, so it has no muted state.
    "app": (ICON_DIR / "app.svg", ICON_DIR / "app-active.svg"),
    # Navigation-rail categories
    "images": (ICON_DIR / "images.svg", ICON_DIR / "images-active.svg"),
    "videos": (ICON_DIR / "videos.svg", ICON_DIR / "videos-active.svg"),
    "brief": (ICON_DIR / "brief.svg", ICON_DIR / "brief-active.svg"),
    "advisor": (ICON_DIR / "advisor.svg", ICON_DIR / "advisor-active.svg"),
    "ads": (ICON_DIR / "ads.svg", ICON_DIR / "ads-active.svg"),
    "cats": (ICON_DIR / "cats.svg", ICON_DIR / "cats-active.svg"),
    "sound": (ICON_DIR / "sound.svg", ICON_DIR / "sound-active.svg"),
    "lighting": (ICON_DIR / "lighting.svg", ICON_DIR / "lighting-active.svg"),
    "composition": (ICON_DIR / "composition.svg", ICON_DIR / "composition-active.svg"),
    "posing": (ICON_DIR / "posing.svg", ICON_DIR / "posing-active.svg"),
    "color": (ICON_DIR / "color.svg", ICON_DIR / "color-active.svg"),
    "camera_angle": (ICON_DIR / "camera_angle.svg", ICON_DIR / "camera_angle-active.svg"),
    "influencer_studio": (ICON_DIR / "influencer_studio.svg",
                          ICON_DIR / "influencer_studio-active.svg"),
    # Actions and sub-views
    "compose": (ICON_DIR / "compose.svg", ICON_DIR / "compose-active.svg"),
    "variants": (ICON_DIR / "variants.svg", ICON_DIR / "variants-active.svg"),
    "history": (ICON_DIR / "history.svg", ICON_DIR / "history-active.svg"),
    "insights": (ICON_DIR / "insights.svg", ICON_DIR / "insights-active.svg"),
    "settings": (ICON_DIR / "settings.svg", ICON_DIR / "settings-active.svg"),
    "generate": (ICON_DIR / "generate.svg", ICON_DIR / "generate-active.svg"),
    "copy": (ICON_DIR / "copy.svg", ICON_DIR / "copy-active.svg"),
    "save": (ICON_DIR / "save.svg", ICON_DIR / "save-active.svg"),
    "search": (ICON_DIR / "search.svg", ICON_DIR / "search-active.svg"),
    "shuffle": (ICON_DIR / "shuffle.svg", ICON_DIR / "shuffle-active.svg"),
    "star": (ICON_DIR / "star.svg", ICON_DIR / "star-active.svg"),
    "folder": (ICON_DIR / "folder.svg", ICON_DIR / "folder-active.svg"),
}


def icon(name, active=False):
    """QIcon for a named asset. Missing files yield a null icon, never a crash."""
    pair = ICONS.get(name)
    if not pair:
        return QIcon()
    path = pair[1] if active else pair[0]
    return QIcon(str(path)) if path.exists() else QIcon()
