"""Canvas views, grouped by category behind the navigation rail.

images       -> Compose + Variants   (stills)
videos       -> the Kling motion toolkit and the film glossary
ads          -> the five-beat UGC advert
cats         -> a cat story in scenes, with its CapCut edit sheet
sound        -> ElevenLabs sound-effect prompts
lighting      -> the photographic lighting taxonomy (setups, direction/quality/source)
composition   -> the seven framing geometries plus opt-in realism techniques
color_grading -> mood-to-palette presets and film-look references, plus opt-in techniques
posing        -> named poses by shot type, plus opt-in posing realism techniques
camera_angle  -> vertical/side/size, three independent camera-position axes
brief         -> the text-model helpers, one-shot
advisor       -> a running conversation with the in-app expert on the whole studio
history / insights / settings
"""

from .ads import AdsView
from .advisor import AdvisorView
from .brief_view import BriefView
from .camera_angle import CameraAngleView
from .cats import CatsView
from .color_grading import ColorGradingView
from .compose import ComposeView
from .composition import CompositionView
from .history_view import HistoryView
from .images import ImagesView
from .insights import InsightsView
from .lighting import LightingView
from .posing import PosingView
from .settings import SettingsView
from .sound import SoundView
from .variants import VariantsView
from .videos import VideosView

__all__ = [
    "ImagesView", "ComposeView", "VariantsView", "VideosView", "AdsView",
    "CatsView", "SoundView", "LightingView", "CompositionView", "ColorGradingView",
    "PosingView", "CameraAngleView", "BriefView", "AdvisorView", "HistoryView",
    "InsightsView", "SettingsView",
]
