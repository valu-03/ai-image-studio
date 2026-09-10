"""Canvas views, behind the navigation rail.

Ten rail sections, each a plain noun:

images    -> Compose + Variants (stills)
look      -> LookView: Lighting / Composition / Camera / Color / Posing
             (Style is added later) - each builds a phrase you Apply into the
             Images prompt
videos    -> the Kling motion toolkit and the film glossary
influencer_studio -> "Personas": a saved persona roster composed into one
             Subject description
ads       -> the five-beat UGC advert
cats      -> a cat story in scenes, with its CapCut edit sheet
sound     -> ElevenLabs sound-effect prompts, TTS and voice cloning
assistant -> AssistantView: Chat (the running conversation) + Prompt tools
             (the one-shot text helpers)
activity  -> ActivityView: History + What works (the term-to-rating payoff)
settings  -> provider / model / keys / theme / paths

LookView, AssistantView and ActivityView are thin containers (like ImagesView):
each child view keeps its own logic and signals, and MainWindow reaches in for
`self.lighting_view` / `self.advisor_view` / `self.history_view` etc.
"""

from .activity import ActivityView
from .ads import AdsView
from .advisor import AdvisorView
from .assistant import AssistantView
from .brief_view import BriefView
from .camera_angle import CameraAngleView
from .cats import CatsView
from .color_grading import ColorGradingView
from .compose import ComposeView
from .composition import CompositionView
from .history_view import HistoryView
from .images import ImagesView
from .influencer_studio import InfluencerStudioView
from .insights import InsightsView
from .lighting import LightingView
from .look import LookView
from .posing import PosingView
from .settings import SettingsView
from .sound import SoundView
from .variants import VariantsView
from .videos import VideosView

__all__ = [
    "ImagesView", "ComposeView", "VariantsView", "LookView", "VideosView", "AdsView",
    "CatsView", "SoundView", "LightingView", "CompositionView", "ColorGradingView",
    "PosingView", "CameraAngleView", "InfluencerStudioView", "AssistantView",
    "BriefView", "AdvisorView", "ActivityView", "HistoryView", "InsightsView",
    "SettingsView",
]
