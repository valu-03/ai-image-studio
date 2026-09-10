"""Application shell — navigation rail, top utility bar, stacked content canvas.

Presentation is built in setup_ui() and painted in apply_styles(). Controller
logic (generation, routing, persistence) is kept in clearly separated methods
below those, and all domain logic lives in tools/.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QThreadPool, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_prompt as bp  # noqa: E402
import generate_image as gi  # noqa: E402
import generate_video as gv  # noqa: E402
import history as hist  # noqa: E402
import upscale_image as up  # noqa: E402
import refine_image as ri  # noqa: E402

from . import assets, tokens as T  # noqa: E402
from .views import (  # noqa: E402
    ActivityView,
    AdsView,
    AssistantView,
    CatsView,
    ImagesView,
    InfluencerStudioView,
    LookView,
    SettingsView,
    SoundView,
    VideosView,
)
from .widgets import Badge, MutedLabel, NavButton  # noqa: E402
from .workers import (  # noqa: E402
    BatchSession,
    CreditsTask,
    GenerationPool,
    RefineTask,
    VideoPool,
    VideoSession,
    WorkerPool,
)

# AIVS_SETTINGS_APP: the same isolation seam as history.py's AIVS_HISTORY_FILE
# and generate_image.py's AIVS_ENV_FILE - every test that builds a MainWindow
# was, until now, reading and writing the user's REAL QSettings (provider,
# model, theme, form_mode, learned, and the saved window geometry) under the
# real "AI Video Studio"/"Studio" key, with nothing redirecting it away. A
# test must not be able to reach the live data at all.
SETTINGS_APP = os.environ.get("AIVS_SETTINGS_APP", "Studio")

# The rail is organised by category: what you are making, then how it looks,
# then the other things you make, then help, then what you learn, then config.
# Ten sections; the tuning toolkits live inside "look", the two model helpers
# inside "assistant", history+insights inside "activity".
NAV_ITEMS = [
    ("images", "Images"),
    ("look", "Look"),
    ("videos", "Videos"),
    ("influencer_studio", "Personas"),
    ("ads", "Ads"),
    ("cats", "Cats"),
    ("sound", "Sound"),
    ("assistant", "Assistant"),
    ("activity", "Activity"),
    ("settings", "Settings"),
]

# Keys that are no longer their own rail entry but still work as go_to()
# targets: (container nav key, tab index inside that container). Every
# existing go_to("lighting") / go_to("history") / SpecEditor.open_*_requested
# / apply_*_phrase caller keeps working unchanged through this.
SUBVIEW_ROUTES = {
    "lighting": ("look", 0),
    "composition": ("look", 1),
    "camera_angle": ("look", 2),
    "color": ("look", 3),
    "posing": ("look", 4),
    "style": ("look", 5),
    "advisor": ("assistant", 0),
    "brief": ("assistant", 1),
    "history": ("activity", 0),
    "insights": ("activity", 1),
}

# tools/advisor.py's own SECTION_NAMES -> the SpecEditor setter each one's
# composed phrase belongs in. Every setter here already exists and is already
# what that section's own "Apply to Compose" button calls; the Advisor reuses
# them rather than growing a second way to write the same fields. Note the
# two that aren't a 1:1 name match on purpose: posing is descriptive spec
# content (it lands in Action, not an override) and a camera angle lands as
# typed custom shot text (see build_camera_angle.py's own docstring).
ADVISOR_SECTION_SETTERS = {
    "lighting": "set_lighting_override",
    "composition": "set_composition_override",
    "color": "set_colour_override",
    "posing": "set_action_override",
    "camera_angle": "set_shot_override",
}


class MainWindow(QMainWindow):
    """Single-window dashboard: rail + top bar + QStackedWidget canvas."""

    status_changed = pyqtSignal(str)

    def __init__(self, theme):
        super().__init__()
        # Every output folder (characters/prompts/images/videos) exists from
        # the first launch, not just once something happens to be generated
        # into it - a view listing or "Open" button hitting an ungenerated
        # section used to have nothing to point at.
        assets.ensure_output_dirs()
        self.theme = theme
        self.bank = bp.load_bank()
        self.settings = QSettings("AI Video Studio", SETTINGS_APP)
        self.pool = GenerationPool(self)
        self.video_pool = VideoPool(2, self)
        self.provider = gi.DEFAULT_PROVIDER
        self.model = None
        # The one running still-image submission, or None between batches. See
        # `workers.BatchSession` - this used to be five separate attributes
        # (`_batch_target`, `_sequence_rest`, `_sequence_reference`,
        # `_sequence_total`, `_batch_offset`) tracked and cleared by hand.
        self._batch = None
        self.credits_left = None
        self._credits_pool = WorkerPool(1, self)
        # The refine loop is a multi-round, potentially minutes-long call - its
        # own small pool, the same way Brief/Compose's autofill/upgrade calls
        # already run on their own local QThreadPool rather than the per-job
        # GenerationPool, which is shaped for parallel single generations.
        self._refine_pool = QThreadPool(self)
        self._refine_pool.setMaxThreadCount(1)
        # The one running clip submission, or None between batches - the video
        # equivalent of `_batch`, replacing `_video_target`/`_video_seconds`/
        # `_video_done`/`_video_total`.
        self._video = None

        self.setup_ui()
        self.apply_styles()
        self.connect_controllers()
        self.restore_state()
        self.refresh_credits()

    # ---------------------------------------------------------------- UI -- #
    def setup_ui(self):
        self.setWindowTitle("AI Video Studio")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.build_nav_rail())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.build_top_bar())
        right_layout.addWidget(self.build_canvas(), 1)
        root_layout.addWidget(right, 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")
        self.build_actions()

    def build_nav_rail(self):
        rail = QFrame()
        rail.setProperty("class", "rail")
        rail.setFixedWidth(T.NAV_RAIL_WIDTH)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(T.SPACE["md"], T.SPACE["lg"], T.SPACE["md"], T.SPACE["lg"])
        layout.setSpacing(T.SPACE["xs"])

        # The mark beside the wordmark, so the rail and the taskbar agree.
        self.brand_mark = QLabel()
        self.brand_mark.setPixmap(assets.icon("app").pixmap(assets.BRAND_ICON_SIZE))
        self.brand_mark.setFixedSize(assets.BRAND_ICON_SIZE)
        brand = QLabel("AI Video Studio")
        brand.setProperty("class", "brand")

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(T.SPACE["sm"])
        brand_row.addWidget(self.brand_mark)
        brand_row.addWidget(brand, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(T.SPACE["lg"])

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for index, (key, label) in enumerate(NAV_ITEMS):
            button = NavButton(key, label)
            self.nav_group.addButton(button, index)
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.rail_hint = MutedLabel("Prompts are gated at 8/8 before generating.")
        layout.addWidget(self.rail_hint)
        return rail

    def build_top_bar(self):
        bar = QFrame()
        bar.setProperty("class", "topbar")
        bar.setFixedHeight(T.TOP_BAR_HEIGHT)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(T.CONTAINER_PADDING, T.SPACE["sm"],
                                  T.CONTAINER_PADDING, T.SPACE["sm"])
        layout.setSpacing(T.SPACE["md"])

        self.view_title = QLabel("Compose")
        self.view_title.setProperty("class", "headline")
        layout.addWidget(self.view_title)

        self.search = QLineEdit()
        self.search.setProperty("class", "search")
        self.search.setPlaceholderText("Search characters and history…")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(420)
        self.search.addAction(assets.icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        layout.addStretch(1)
        layout.addWidget(self.search)

        # What is left to spend, beside what is being spent. Kie is prepaid, so
        # this is the number that decides whether a nine-scene story is a good
        # idea - and it was nowhere in the app.
        self.credits_badge = Badge("credits —", "neutral")
        self.credits_badge.setToolTip("Credits left on the provider account. Click to refresh.")
        self.credits_badge.mousePressEvent = lambda _event: self.refresh_credits(force=True)
        layout.addWidget(self.credits_badge)

        self.busy_badge = Badge("idle", "neutral")
        layout.addWidget(self.busy_badge)
        return bar

    def build_canvas(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(T.CONTAINER_PADDING, T.CONTAINER_PADDING,
                                  T.CONTAINER_PADDING, T.CONTAINER_PADDING)

        self.stack = QStackedWidget()
        self.images_view = ImagesView(self.bank)
        # Compose and Variants keep their own identities; Images just groups them.
        self.compose_view = self.images_view.compose
        self.variants_view = self.images_view.variants

        # Look groups the five tuning toolkits; MainWindow still talks to each
        # one by name, so every apply_*_phrase / ADVISOR_SECTION_SETTERS wire
        # is unchanged.
        self.look_view = LookView(self.theme.palette)
        self.lighting_view = self.look_view.lighting
        self.composition_view = self.look_view.composition
        self.camera_angle_view = self.look_view.camera
        self.color_view = self.look_view.color
        self.posing_view = self.look_view.posing
        self.style_view = self.look_view.style

        self.assistant_view = AssistantView(self.bank)
        self.advisor_view = self.assistant_view.advisor
        self.brief_view = self.assistant_view.brief

        self.activity_view = ActivityView(self.theme.palette)
        self.history_view = self.activity_view.history
        self.insights_view = self.activity_view.insights

        self.videos_view = VideosView(self.theme.palette)
        self.ads_view = AdsView(self.bank, self.theme.palette)
        self.cats_view = CatsView(self.bank, self.theme.palette)
        self.sound_view = SoundView(self.theme.palette)
        self.influencer_studio_view = InfluencerStudioView(self.theme.palette)
        self.settings_view = SettingsView()

        self.views = {
            "images": self.images_view,
            "look": self.look_view,
            "videos": self.videos_view,
            "influencer_studio": self.influencer_studio_view,
            "ads": self.ads_view,
            "cats": self.cats_view,
            "sound": self.sound_view,
            "assistant": self.assistant_view,
            "activity": self.activity_view,
            "settings": self.settings_view,
        }
        for key, _ in NAV_ITEMS:
            self.stack.addWidget(self.views[key])

        layout.addWidget(self.stack)
        return host

    def build_actions(self):
        # Generated from NAV_ITEMS rather than listed again: the hardcoded copy
        # silently drifted out of step every time a section was added. `k=key`
        # binds per iteration - a bare closure would capture the last key.
        # Ctrl+1..9 then Ctrl+0 for the tenth - QKeySequence cannot parse a
        # multi-digit token ("Ctrl+10" is a dead shortcut), and the rail is ten
        # sections now.
        shortcuts = [
            (label, "Ctrl+{}".format((index + 1) % 10), lambda k=key: self.go_to(k))
            for index, (key, label) in enumerate(NAV_ITEMS[:10])
        ] + [
            ("Focus search", "Ctrl+F", self.search.setFocus),
            ("Copy prompt", "Ctrl+Shift+C", self.compose_view.copy_prompt),
            ("Save character", "Ctrl+S", self.compose_view.save_spec),
            ("Reshuffle", "Ctrl+R", self.compose_view.reshuffle),
            ("Generate", "Ctrl+G", self.compose_view.request_generate),
            ("Toggle theme", "Ctrl+T", self.theme.toggle),
        ]
        for label, sequence, slot in shortcuts:
            action = QAction(label, self)
            action.setShortcut(QKeySequence(sequence))
            action.triggered.connect(slot)
            self.addAction(action)

    def apply_styles(self):
        """Per-widget style hooks the global sheet cannot express."""
        self.nav_buttons["images"].setChecked(True)
        self.busy_badge.set_status("neutral", "idle")
        self.compose_view.prompt_view.setProperty("class", "mono")
        for view in self.views.values():
            view.setContentsMargins(0, 0, 0, 0)

    # -------------------------------------------------------- controllers -- #
    def connect_controllers(self):
        self.nav_group.idClicked.connect(self.on_nav_clicked)
        self.search.textChanged.connect(self.on_search)
        self.theme.changed.connect(self.on_theme_changed)

        for view in self.views.values():
            if hasattr(view, "status"):
                view.status.connect(self.statusBar().showMessage)

        self.compose_view.editor.open_lighting_requested.connect(
            lambda: self.go_to("lighting"))
        self.compose_view.editor.open_composition_requested.connect(
            lambda: self.go_to("composition"))
        self.compose_view.editor.open_posing_requested.connect(
            lambda: self.go_to("posing"))
        self.compose_view.editor.open_color_requested.connect(
            lambda: self.go_to("color"))
        self.compose_view.editor.open_camera_angle_requested.connect(
            lambda: self.go_to("camera_angle"))
        self.compose_view.generate_requested.connect(self.generate_single)
        self.compose_view.upscale_requested.connect(self.upscale_image)
        self.compose_view.refine_requested.connect(self.refine_image)
        self.variants_view.spec_provider = self.current_spec_bundle
        self.variants_view.generate_requested.connect(self.generate_batch)
        # The ads view reads the open character so the presenter is the one you
        # are already working on, the same one-directional link Videos uses.
        self.ads_view.context = lambda: self.compose_view.editor.spec()
        self.ads_view.generate_requested.connect(self.generate_ad)
        # One-directional apply-then-navigate, the same shape apply_motion_hints()
        # already uses for a movement's image hints: build the override, load it
        # into the editor, jump to Images so the result is immediately visible.
        self.lighting_view.lighting_applied.connect(self.apply_lighting_phrase)
        self.composition_view.composition_applied.connect(self.apply_composition_phrase)
        self.posing_view.posing_applied.connect(self.apply_posing_phrase)
        self.color_view.color_applied.connect(self.apply_color_phrase)
        self.camera_angle_view.angle_applied.connect(self.apply_camera_angle_phrase)
        self.style_view.style_applied.connect(self.apply_style_phrase)
        self.influencer_studio_view.persona_applied.connect(self.apply_persona_phrase)
        # The sound sheet is generated from whatever story is open in Cats, so
        # the two stay in step without either knowing about the other.
        self.sound_view.context = lambda: self.cats_view.scenes
        self.cats_view.story_changed.connect(self.sound_view.rebuild)
        self.cats_view.generate_requested.connect(self.generate_story)
        # Shaped like Compose's own signal - one still, not one job per scene -
        # so it gets its own connection point rather than overloading
        # generate_requested's list-of-jobs shape.
        self.cats_view.custom_generate_requested.connect(self.generate_custom_still)
        self.cats_view.video_requested.connect(
            lambda jobs, options: self.generate_videos(jobs, options, self.cats_view))
        self.variants_view.cancel_requested.connect(self.cancel_generation)
        self.variants_view.seed_adopted.connect(self.adopt_seed)

        self.videos_view.context = lambda: self.compose_view.editor.spec()
        self.videos_view.image_provider = lambda: self.compose_view.current_image
        self.videos_view.hints_applied.connect(self.apply_motion_hints)
        self.videos_view.video_requested.connect(
            lambda jobs, options: self.generate_videos(jobs, options, self.videos_view))

        self.brief_view.context = self.current_context
        self.brief_view.spec_suggested.connect(self.compose_view.apply_suggested_spec)
        self.brief_view.spec_suggested.connect(lambda _: self.go_to("images"))
        self.brief_view.prompt_upgraded.connect(self.compose_view.use_upgraded_prompt)
        self.brief_view.prompt_upgraded.connect(lambda _: self.go_to("images"))

        self.advisor_view.context = self.current_context
        self.advisor_view.spec_suggested.connect(self.compose_view.apply_suggested_spec)
        self.advisor_view.spec_suggested.connect(lambda _: self.go_to("images"))
        self.advisor_view.sections_suggested.connect(self.apply_advisor_sections)

        self.insights_view.learned_toggled.connect(self.compose_view.set_learned)
        self.settings_view.provider_changed.connect(self.set_provider)
        self.settings_view.model_changed.connect(self.set_model)
        self.settings_view.theme_toggled.connect(self.theme.toggle)

        self.pool.started.connect(self.on_batch_started)
        self.pool.progress.connect(self.on_batch_progress)
        self.pool.item_finished.connect(self.on_item_finished)
        self.pool.item_failed.connect(self.on_item_failed)
        # Async jobs poll for minutes; surface what they are doing.
        self.pool.item_stage.connect(
            lambda _index, message: self.statusBar().showMessage(message))
        self.pool.batch_finished.connect(self.on_batch_finished)

        # Wired once, here, rather than per-task inside generate_videos() -
        # that used to build and connect each VideoTask by hand in a loop,
        # duplicating what GenerationPool already does for stills.
        self.video_pool.item_finished.connect(self.on_video_finished)
        self.video_pool.item_failed.connect(self.on_video_failed)
        self.video_pool.item_stage.connect(
            lambda _index, message: self.statusBar().showMessage(message))
        self.video_pool.progress.connect(self.on_video_progress)
        self.video_pool.batch_finished.connect(self.on_video_batch_finished)

        self.compose_view.rebuild()

    def request_options(self, spec=None):
        """What goes in the request body rather than in the prompt.

        Resolution and output format are account-wide settings; the aspect comes
        from whatever is being generated. None of this reached the provider
        before - the GUI never passed a spec at all.
        """
        options = dict(self.settings_view.image_options())
        aspect = (spec or {}).get("aspect")
        if aspect:
            options["aspect"] = aspect
        return options

    def current_spec_bundle(self):
        """(spec, detailed, weights) — what the Variants view needs to build."""
        spec = self.compose_view.editor.spec()
        detailed = bool(self.compose_view.form_mode.currentData())
        weights = hist.weights() if self.compose_view.use_learned else None
        return spec, detailed, weights

    def go_to(self, key):
        route = SUBVIEW_ROUTES.get(key)
        if route:
            container_key, tab_index = route
            self.go_to(container_key)
            container = self.views[container_key]
            if tab_index < container.tabs.count():
                container.tabs.setCurrentIndex(tab_index)
            return
        button = self.nav_buttons.get(key)
        if button:
            button.setChecked(True)
            self.on_nav_clicked(list(self.nav_buttons).index(key))

    def current_context(self):
        """(prompt, image) — what the Brief view acts on."""
        return self.compose_view.prompt_text(), str(self.compose_view.current_image or "")

    def apply_advisor_sections(self, sections):
        """The Advisor's technique-section picks -> the same SpecEditor
        setters each section's own "Apply to Compose" button already calls.

        No new setter methods: a suggested lighting phrase lands exactly where
        LightingView's own Apply puts one, and so on for all five - which is
        what keeps "the advisor filled it in" and "I picked it myself" from
        ever producing two different results.
        """
        editor = self.compose_view.editor
        for name, phrase in (sections or {}).items():
            setter = ADVISOR_SECTION_SETTERS.get(name)
            if setter and phrase:
                getattr(editor, setter)(phrase)
        if sections:
            self.go_to("images")

    def on_nav_clicked(self, index):
        key, label = NAV_ITEMS[index]
        self.stack.setCurrentIndex(index)
        self.view_title.setText(label)
        view = self.views[key]
        # Every section that needs work on show exposes exactly one of these;
        # the containers (Look / Assistant / Activity) forward to their visible
        # child. Settings is the only leaf with a differently-named hook.
        for hook in ("refresh", "reload", "refresh_key_state"):
            if hasattr(view, hook):
                getattr(view, hook)()
                break

    def on_search(self, text):
        self.compose_view.set_filter(text)
        self.history_view.set_filter(text)

    def apply_motion_hints(self, hints):
        """A movement asking the still to be framed for it.

        Delegates to build_motion.apply_image_hints so the precedence rule lives
        in the tool, not here: the movement fills gaps, an explicit choice wins.
        """
        import build_motion as bm

        editor = self.compose_view.editor
        merged = bm.apply_image_hints(
            self.videos_view.bank, self.videos_view.movement, editor.spec()
        )
        editor.load_spec(merged)
        self.go_to("images")
        self.images_view.show_compose()

    def on_theme_changed(self, name):
        self.compose_view.lint.set_palette_tokens(self.theme.palette)
        self.history_view.set_palette_tokens(self.theme.palette)
        self.videos_view.set_palette_tokens(self.theme.palette)
        self.ads_view.set_palette_tokens(self.theme.palette)
        self.cats_view.set_palette_tokens(self.theme.palette)
        self.sound_view.set_palette_tokens(self.theme.palette)
        self.lighting_view.set_palette_tokens(self.theme.palette)
        self.composition_view.set_palette_tokens(self.theme.palette)
        self.posing_view.set_palette_tokens(self.theme.palette)
        self.color_view.set_palette_tokens(self.theme.palette)
        self.camera_angle_view.set_palette_tokens(self.theme.palette)
        self.style_view.set_palette_tokens(self.theme.palette)
        self.influencer_studio_view.set_palette_tokens(self.theme.palette)
        self.insights_view.set_palette_tokens(self.theme.palette)
        self.statusBar().showMessage("{} theme".format(name.capitalize()))

    def apply_lighting_phrase(self, phrase):
        """Lighting's "Apply to Compose" - one directional, same shape as
        apply_motion_hints(): build the override, load it into the editor,
        jump to Images so the result is immediately visible."""
        self.compose_view.editor.set_lighting_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_composition_phrase(self, phrase):
        """Composition's "Apply to Compose" - identical shape to
        apply_lighting_phrase()."""
        self.compose_view.editor.set_composition_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_posing_phrase(self, phrase):
        """Posing's "Apply to Compose" - identical shape to
        apply_lighting_phrase(), landing in the Action field instead."""
        self.compose_view.editor.set_action_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_color_phrase(self, phrase):
        """Color Grading's "Apply to Compose" - identical shape to
        apply_lighting_phrase(), landing in the new colour override."""
        self.compose_view.editor.set_colour_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_camera_angle_phrase(self, phrase):
        """Camera Angle's "Apply to Compose" - identical shape to
        apply_lighting_phrase(), landing in the Shot field as custom text."""
        self.compose_view.editor.set_shot_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_style_phrase(self, phrase):
        """Style's "Apply to Compose" - identical shape to
        apply_lighting_phrase(), landing in the (widget-less) style override."""
        self.compose_view.editor.set_style_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def apply_persona_phrase(self, phrase):
        """Influencer Studio's "Apply to Compose" - identical shape to
        apply_lighting_phrase(), landing in the Subject field. Reference
        images stay local to the persona - this never touches
        SpecEditor.set_reference()/lock_identity."""
        self.compose_view.editor.set_subject_override(phrase)
        self.go_to("images")
        self.images_view.show_compose()

    def set_provider(self, name):
        self.provider = name
        self.statusBar().showMessage("Provider: {}".format(name))

    def set_model(self, text):
        self.model = text.strip() or None

    def adopt_seed(self, seed):
        self.compose_view.editor.seed.setValue(int(seed))
        self.insights_view.reload()
        self.history_view.reload()
        self.go_to("images")
        self.images_view.show_compose()

    # --------------------------------------------------------- generation -- #
    def generate_single(self, prompt, references):
        if self.pool.busy:
            self.statusBar().showMessage("A generation is already running")
            return
        self._batch = None   # no session = Compose's own single-image path
        self.compose_view.set_busy(True)
        provider = self.compose_view.provider_override() or self.provider
        model = self.compose_view.model_override() or self.model
        options = self.request_options(self.compose_view.editor.spec())
        options.update(self.compose_view.options_override())
        self.pool.submit([(0, prompt, None, references)], provider, model, options)

    def upscale_image(self, path):
        """The bootcamp's own "upscale before you animate" rule, one click.

        Not a new job shape: `tools/upscale_image.upscale()` is `gi.generate()`
        with a fixed instruction prompt and `path` as the sole reference, so
        this is `generate_single()`'s shape with the prompt and references
        swapped for that - same pool, same routing (`_batch = None` means the
        result answers to Compose, same as any other single-image job).
        """
        if self.pool.busy:
            self.statusBar().showMessage("A generation is already running")
            return
        self._batch = None
        self.compose_view.set_busy(True)
        provider = self.compose_view.provider_override() or self.provider
        model = self.compose_view.model_override() or self.model
        options = self.request_options(self.compose_view.editor.spec())
        options.update(self.compose_view.options_override())
        self.pool.submit([(0, up.UPSCALE_PROMPT, None, [path])], provider, model, options)

    def refine_image(self):
        """Compose's opt-in "Refine until real" - critique, strengthen the
        weak layer, retry, up to 2 more times.

        Not a new job shape underneath: `tools/refine_image.refine()` is a
        loop of the exact same `generate_image.generate()` and
        `brief.critique_image()` calls `upscale_image()`/Brief's own critique
        action already use - it runs as one background task rather than
        through `self.pool` because it is a multi-step, multi-minute call,
        not a single independent image job.
        """
        if self.pool.busy or self._refine_pool.activeThreadCount():
            self.statusBar().showMessage("A generation is already running")
            return
        provider = self.compose_view.provider_override() or self.provider
        cfg = gi.PROVIDERS.get(provider, {})
        model = (self.compose_view.model_override() or self.model
                 or gi.env_value(cfg.get("model_var", "")) or cfg.get("default_model"))
        max_retries = 2
        if not self.confirm_spend(model, max_retries + 1, "images (up to)", max_retries + 1):
            self.statusBar().showMessage("Cancelled - nothing was generated")
            return

        spec = self.compose_view.editor.spec()
        self.compose_view.set_refining(True)
        task = RefineTask(
            self.bank, spec, provider=provider, model=model, max_retries=max_retries,
            start_image=self.compose_view.current_image,
            start_prompt=self.compose_view.prompt_text(),
            start_selected=getattr(self.compose_view, "last_layers", {}),
        )
        task.signals.progress.connect(self.statusBar().showMessage)
        task.signals.finished.connect(self.on_refine_finished)
        task.signals.failed.connect(self.on_refine_failed)
        task.signals.done.connect(lambda _n: self.compose_view.set_refining(False))
        self._refine_pool.start(task)

    def on_refine_finished(self, result):
        attempts = result.get("attempts") or []
        final = result.get("result") or {}
        if final.get("image"):
            self.compose_view.show_image(final["image"])

        last = attempts[-1] if attempts else {}
        critique_error = last.get("critique_error")
        if critique_error:
            self.statusBar().showMessage(
                "Generated, but couldn't check it: {}".format(critique_error))
            return

        failing = (last.get("critique") or {}).get("failing_layers", [])
        score = final.get("score", "?")
        if len(attempts) == 1 and not failing:
            self.statusBar().showMessage("Already looks real - no retry needed ({}/8)".format(score))
        elif failing:
            self.statusBar().showMessage(
                "Stopped after {} attempt(s) - still weak on: {} ({}/8)".format(
                    len(attempts), ", ".join(failing), score))
        else:
            self.statusBar().showMessage(
                "Fixed after {} attempt(s) ({}/8)".format(len(attempts), score))

    def on_refine_failed(self, reason):
        self.statusBar().showMessage("Refine failed: {}".format(reason))

    def generate_batch(self, jobs):
        if self.pool.busy:
            self.statusBar().showMessage("A generation is already running")
            return
        self._batch = BatchSession(self.variants_view, len(jobs))
        spec, _detailed, _weights = self.current_spec_bundle()
        self.pool.submit(jobs, self.provider, self.model, self.request_options(spec))

    def generate_custom_still(self, prompt, references):
        """Cats' Custom Prompt tab: one still, routed back to that tab
        specifically - the single-job version of `generate_batch`, not
        `generate_single` (which always answers to Compose)."""
        if self.pool.busy:
            self.statusBar().showMessage("A generation is already running")
            return
        self._batch = BatchSession(self.cats_view.custom_tab, 1)
        aspect = self.cats_view.custom_tab.aspect.currentText().strip()
        spec = {"aspect": aspect} if aspect else {}
        self.pool.submit([(0, prompt, None, references)], self.provider, self.model,
                         self.request_options(spec))

    def generate_ad(self, jobs):
        """The Ads path: one job per beat, locked to beat 1."""
        self.generate_sequence(jobs, self.ads_view, "shots")

    def generate_story(self, jobs):
        """The Cats path: one job per scene, locked to scene 1."""
        self.generate_sequence(jobs, self.cats_view, "scenes")

    def generate_sequence(self, jobs, target, noun="shots"):
        """A locked sequence: shot 1 alone, then the rest carrying its face.

        This used to submit every job at once with an EMPTY reference list -
        immediately after refusing providers that cannot carry a reference,
        because without one the shots would be different characters. The refusal
        was right and the submission ignored it, so every run produced N
        different cats. The reference cannot exist before shot 1 does, which is
        why this runs in two phases rather than one.
        """
        if self.pool.busy:
            self.statusBar().showMessage("A generation is already running")
            return
        if not jobs:
            self.statusBar().showMessage("Nothing to generate yet")
            return
        cfg = gi.PROVIDERS.get(self.provider, {})
        if not cfg.get("references"):
            self.statusBar().showMessage(
                "{} cannot carry a reference, so these would be {} different "
                "characters. Switch to a provider that supports references.".format(
                    cfg.get("label", self.provider), len(jobs)))
            return

        model = self.model or gi.env_value(cfg["model_var"]) or cfg["default_model"]
        if not self.confirm_spend(model, len(jobs), noun, len(jobs)):
            self.statusBar().showMessage("Cancelled - nothing was generated")
            return

        self._batch = BatchSession(target, len(jobs), sequence_rest=jobs[1:])
        first = jobs[0]
        target.set_busy(True, len(jobs))
        self.pool.submit([(first["index"], first["prompt"], first["out_name"], [])],
                         self.provider, self.model,
                         self.request_options(first.get("spec")))
        self.statusBar().showMessage(
            "Queued {} {} - the first one alone, so the rest can lock to it".format(
                len(jobs), noun))

    def _submit_sequence_rest(self, reference_path):
        """Phase two: everything else, carrying shot 1's actual file.

        The local path goes straight in - generate_image uploads it and turns it
        into the URL the provider wants, so there is no second copy of that here.
        """
        jobs, self._batch.sequence_rest = self._batch.sequence_rest, []
        self._batch.offset = 1
        self.pool.submit(
            [(job["index"], job["prompt"], job["out_name"], [reference_path])
             for job in jobs],
            self.provider, self.model, self.request_options(jobs[0].get("spec")))
        self.statusBar().showMessage(
            "Locked to {} - generating the remaining {}".format(
                Path(reference_path).name, len(jobs)))

    # -------------------------------------------------------------- video -- #
    def generate_videos(self, jobs, options, target=None):
        """One Kling clip per scene, priced and confirmed before anything runs.

        Clips are the expensive thing in this app by a wide margin - seconds of
        video against single images - so this is the one path that always asks.
        """
        if self.video_pool.busy:
            self.statusBar().showMessage("Clips are already generating")
            return
        seconds = sum(int(job.get("duration", 0)) for job in jobs)
        if not self.confirm_spend(gv.DEFAULT_MODEL, seconds,
                                  "{} clips".format(len(jobs)), len(jobs), **options):
            self.statusBar().showMessage("Cancelled - nothing was generated")
            return

        # Same rule as the stills: results go to the view that asked for them.
        self._video = VideoSession(
            target, len(jobs),
            {job["index"]: int(job.get("duration", 0)) for job in jobs})
        self.busy_badge.set_status("accent", "clips 0/{}".format(len(jobs)))
        self.video_pool.submit(jobs, aspect_ratio=self.bank.get("aspect") or None, **options)

    def on_video_finished(self, index, path, used):
        if self._video is not None and self._video.target is not None:
            self._video.target.on_video_finished(index, path)
        self.statusBar().showMessage("Clip saved: {}".format(Path(path).name))
        # The provider just said what it really cost. That replaces a figure
        # copied off a marketing page with a measured one.
        if used:
            self._record_measured_cost(gv.DEFAULT_MODEL, index, used)

    def on_video_failed(self, index, reason):
        if self._video is not None and self._video.target is not None:
            self._video.target.on_video_failed(index, reason)
        else:
            self.statusBar().showMessage(reason[:160])

    def _record_measured_cost(self, model, index, used):
        units = self._video.seconds_by_index.get(index) if self._video else None
        if not units:
            return
        try:
            gv.save_measured(model, units, used)
        except OSError:
            pass    # a pricing note that cannot be written is not worth an error

    def on_video_progress(self, completed, total):
        self.busy_badge.set_status("accent", "clips {}/{}".format(completed, total))

    def on_video_batch_finished(self):
        self.busy_badge.set_status("neutral", "idle")
        self._video = None
        self.refresh_credits()

    # ------------------------------------------------------------ credits -- #
    def refresh_credits(self, force=False):
        """Update the balance badge. Silent when there is no key."""
        if self._credits_pool.busy:
            return
        task = CreditsTask(self.provider)
        task.signals.finished.connect(self.on_credits)
        self._credits_pool.submit_tasks([task])
        if force:
            self.statusBar().showMessage("Checking the balance…")

    def on_credits(self, value, error):
        self.credits_left = value
        if value is None:
            self.credits_badge.set_status("neutral", "credits —")
            self.credits_badge.setToolTip(
                "Balance unknown: {}. Click to try again.".format(error or "no key"))
            return
        # Amber, not red: a low balance is a fact about the account, not a fault.
        status = "warning" if value < 500 else "neutral"
        self.credits_badge.set_status(status, "{:,} credits".format(int(value)))
        self.credits_badge.setToolTip(
            "Credits left on the provider account. Click to refresh.")

    def confirm_spend(self, model, units, unit_name, count, **options):
        """Ask before a batch. Returns True to go ahead.

        The one step between choosing the wrong arc and a real bill. The estimate
        comes from pricing.json, which says out loud that its numbers are seeded
        from a marketing page rather than measured.

        AIVS_ASSUME_YES skips the dialog, for a suite or a scripted run - a modal
        nobody can answer is a hang, not a safeguard. It never suppresses the
        estimate itself, which still goes to the status bar.
        """
        total, confidence, note = gv.estimate(model, units, **options)
        if os.environ.get("AIVS_ASSUME_YES"):
            self.statusBar().showMessage("{} {} · about {} credits ({})".format(
                count, unit_name, total if total is not None else "?", confidence))
            return True
        if total is None:
            body = "{} {}.\n\nCost unknown - {} is not in pricing.json.".format(
                count, unit_name, model)
        else:
            body = "{} {} · {} {}\n\nAbout {:,} credits ({}).".format(
                count, unit_name, units,
                "seconds" if unit_name.endswith("clips") else "images",
                total, confidence)
            if self.credits_left is not None:
                body += "\nYou have {:,}.".format(int(self.credits_left))
                if total > self.credits_left:
                    body += "\n\nThat is more than the balance - it will fail part way."
        if note:
            body += "\n\n" + note
        answer = QMessageBox.question(
            self, "Generate?", body,
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok)
        return answer == QMessageBox.StandardButton.Ok

    def cancel_generation(self):
        # Drop the rest of a locked sequence first, or on_batch_finished would
        # read a still-populated sequence_rest and submit phase 2 instead of
        # cleaning up. WorkerPool.cancel() now drives batch_finished, which
        # runs the full reset (badge, busy state, _batch).
        if self._batch is not None:
            self._batch.sequence_rest = []
        self.pool.cancel()
        self.statusBar().showMessage("Cancelled — running requests finish, queued ones drop")

    def _batch_size(self):
        """The whole sequence, not just the phase currently in flight."""
        if self._batch is not None:
            return self._batch.total
        return self.pool.total

    def on_batch_started(self, total):
        total = self._batch_size() or total
        self.busy_badge.set_status("accent", "generating 0/{}".format(total))
        if self._batch is not None and self._batch.target is not None:
            self._batch.target.set_busy(True, total)

    def on_batch_progress(self, completed, total):
        # A locked sequence runs as two batches, so the pool's own count restarts
        # halfway through. The offset keeps the badge counting 1..N once.
        offset = self._batch.offset if self._batch is not None else 0
        done = offset + completed
        whole = self._batch_size() or total
        self.busy_badge.set_status("accent", "generating {}/{}".format(done, whole))
        if self._batch is not None and self._batch.target is not None:
            self._batch.target.set_progress(done, whole)

    def on_item_finished(self, index, path):
        if self._batch is None or self._batch.target is None:
            self.compose_view.show_image(path)
            return
        # Every result reaches the view that asked for it. It used to go to the
        # Variants grid whoever asked, and that grid drops any index it has no
        # tile for - so a whole generated story vanished without an error.
        self._batch.target.on_item_finished(index, path)
        if self._batch.sequence_rest:
            self._batch.sequence_reference = path

    def on_item_failed(self, index, reason):
        if self._batch is None or self._batch.target is None:
            self.statusBar().showMessage(reason)
            return
        self._batch.target.on_item_failed(index, reason)
        if self._batch.sequence_rest:
            # The first one failed, so there is nothing to lock the rest to.
            # Generating them anyway would spend the money and produce a
            # different character in every frame.
            self._batch.sequence_rest = []
            self.statusBar().showMessage(
                "The first shot failed, so the rest were not generated - "
                "there would be nothing to lock them to. " + reason[:100])

    def on_batch_finished(self):
        if self._batch is not None and self._batch.sequence_rest and self._batch.sequence_reference:
            self._submit_sequence_rest(self._batch.sequence_reference)
            return
        self.busy_badge.set_status("neutral", "idle")
        self.compose_view.set_busy(False)
        if self._batch is not None and self._batch.target is not None:
            self._batch.target.set_busy(False)
        self._batch = None
        self.history_view.reload()
        self.refresh_credits()

    # ------------------------------------------------------------- state -- #
    def restore_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            # restoreGeometry can hand back a size smaller than setMinimumSize
            # already in force (it restores raw saved geometry rather than
            # going through the normal resize() path that would clamp it) -
            # a window saved narrow in an older session, or before a tab
            # picked up new controls, stays narrower than today's content
            # needs, and every button in it silently truncates with nothing
            # in this codebase ever detecting it (that only happens on a
            # user's real, persisted geometry - never on a fresh app launch,
            # which is all the test suite ever exercises). Re-assert the
            # floor explicitly rather than trust restoreGeometry to have.
            if self.width() < 1100 or self.height() < 700:
                self.resize(max(self.width(), 1100), max(self.height(), 700))
        # A settings file written before the provider swap names gemini, openrouter
        # or fal - none of which exist now. Migrate rather than boot pointed at a
        # provider that is gone.
        provider = self.settings.value("provider", gi.DEFAULT_PROVIDER)
        if provider not in gi.PROVIDERS:
            provider = gi.DEFAULT_PROVIDER
        self.settings_view.provider.setCurrentText(provider)
        self.provider = provider
        model = self.settings.value("model", "")
        if model:
            self.settings_view.model.setText(model)
        self.compose_view.form_mode.setCurrentIndex(int(self.settings.value("form_mode", 0)))
        learned = self.settings.value("learned", "false") == "true"
        self.insights_view.learned.setChecked(learned)

    def closeEvent(self, event):
        self.pool.cancel()
        self.video_pool.cancel()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("provider", self.provider)
        self.settings.setValue("model", self.model or "")
        self.settings.setValue("form_mode", self.compose_view.form_mode.currentIndex())
        self.settings.setValue(
            "learned", "true" if self.insights_view.learned.isChecked() else "false"
        )
        self.settings.setValue("theme", self.theme.name)
        super().closeEvent(event)
