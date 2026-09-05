"""Canvas views, grouped by category behind the navigation rail.

images    -> Compose + Variants   (stills)
videos    -> the Kling motion toolkit and the film glossary
ads       -> the five-beat UGC advert
cats      -> a cat story in scenes, with its CapCut edit sheet
sound     -> ElevenLabs sound-effect prompts
brief     -> the text-model helpers
history / insights / settings
"""

from .ads import AdsView
from .brief_view import BriefView
from .cats import CatsView
from .compose import ComposeView
from .history_view import HistoryView
from .images import ImagesView
from .insights import InsightsView
from .settings import SettingsView
from .sound import SoundView
from .variants import VariantsView
from .videos import VideosView

__all__ = [
    "ImagesView", "ComposeView", "VariantsView", "VideosView", "AdsView",
    "CatsView", "SoundView", "BriefView",
    "HistoryView", "InsightsView", "SettingsView",
]
