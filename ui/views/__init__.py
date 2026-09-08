"""Canvas views, grouped by category behind the navigation rail.

images       -> Compose + Variants   (stills)
videos       -> the Kling motion toolkit and the film glossary
ads          -> the five-beat UGC advert
cats         -> a cat story in scenes, with its CapCut edit sheet
sound        -> ElevenLabs sound-effect prompts
lighting     -> the photographic lighting taxonomy (setups, direction/quality/source)
composition  -> the seven framing geometries plus opt-in realism techniques
brief        -> the text-model helpers
history / insights / settings
"""

from .ads import AdsView
from .brief_view import BriefView
from .cats import CatsView
from .compose import ComposeView
from .composition import CompositionView
from .history_view import HistoryView
from .images import ImagesView
from .insights import InsightsView
from .lighting import LightingView
from .settings import SettingsView
from .sound import SoundView
from .variants import VariantsView
from .videos import VideosView

__all__ = [
    "ImagesView", "ComposeView", "VariantsView", "VideosView", "AdsView",
    "CatsView", "SoundView", "LightingView", "CompositionView", "BriefView",
    "HistoryView", "InsightsView", "SettingsView",
]
