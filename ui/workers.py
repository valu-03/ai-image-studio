"""Background workers.

Image generation is network-bound and can take a minute. Every call runs on a
QRunnable in a bounded QThreadPool so the UI loop never blocks — including when
a whole variant batch is in flight.

The workers call tools/generate_image.py's functions directly. They do not
re-implement request building, response parsing or file writing.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import advisor as advisor_tool  # noqa: E402
import brief as brief_tool  # noqa: E402
import coherence_lint as cl  # noqa: E402
import elevenlabs_voices as voices_tool  # noqa: E402
import generate_image as gi  # noqa: E402  (path set above)
import generate_sound as gsnd  # noqa: E402
import generate_speech as gspeech  # noqa: E402
import generate_video as gv  # noqa: E402
import refine_image as refine_tool  # noqa: E402
import render_video as rv  # noqa: E402
import vision_lint as vl  # noqa: E402

MAX_CONCURRENCY = 3


class LlmSignals(QObject):
    """Signals for one text-model action."""

    finished = pyqtSignal(str, object)   # action name, result dict
    failed = pyqtSignal(str, str)        # action name, reason
    done = pyqtSignal(str)


class LlmTask(QRunnable):
    """One brief.py action, off the UI thread.

    The validation gates live in brief.py, not here — this only moves the call
    off the main loop and reports what came back.
    """

    ACTIONS = {
        "idea": brief_tool.spec_from_idea,
        "autofill": brief_tool.autofill_spec,
        "upgrade": brief_tool.upgrade_prompt,
        "critique": brief_tool.critique_image,
        "analyze_image": brief_tool.analyze_uploaded_image,
        "ad_copy": brief_tool.copy_from_idea,
        "story": brief_tool.story_from_idea,
        "autofill_story": brief_tool.autofill_story,
        "analyze_custom_prompt": brief_tool.analyze_custom_prompt,
        "refine_custom_prompt": brief_tool.refine_custom_prompt,
        "advisor_chat": advisor_tool.chat,
    }

    def __init__(self, action, bank, *args):
        super().__init__()
        self.action = action
        self.bank = bank
        self.args = args
        self.signals = LlmSignals()

    def run(self):
        try:
            handler = self.ACTIONS.get(self.action)
            if handler is None:
                self.signals.failed.emit(self.action, "Unknown action: " + self.action)
                return
            result = handler(self.bank, *self.args)
            if not result.get("ok"):
                self.signals.failed.emit(self.action, result.get("error", "Unknown failure"))
                return
            self.signals.finished.emit(self.action, result)
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit(self.action, "{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(self.action)


class RefineSignals(QObject):
    """Signals for one refine-loop run - its own class, not LlmSignals, because
    the loop is the one action in this project that reports progress mid-call
    (LlmTask's actions are all a single request; this one is up to N of them)."""

    progress = pyqtSignal(str)         # a stage message, straight from on_stage
    finished = pyqtSignal(object)      # the whole report dict from refine_image.refine()
    failed = pyqtSignal(str)
    done = pyqtSignal(int)             # WorkerPool-shaped, even though this never runs in one


class RefineTask(QRunnable):
    """Compose's "Refine until real" button, off the UI thread.

    Everything that decides what a "weak layer" means, or what to try next,
    lives in tools/refine_image.py - this only moves the (possibly several
    minutes long) call off the main loop and reports what came back.
    """

    def __init__(self, bank, spec, **kwargs):
        super().__init__()
        self.bank = bank
        self.spec = spec
        self.kwargs = kwargs
        self.signals = RefineSignals()

    def run(self):
        try:
            result = refine_tool.refine(
                self.bank, self.spec,
                on_stage=lambda message: self.signals.progress.emit(message),
                **self.kwargs,
            )
            if not result.get("ok"):
                self.signals.failed.emit(result.get("error", "Unknown failure"))
                return
            self.signals.finished.emit(result)
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(0)


class SoundSignals(QObject):
    """Signals for one real ElevenLabs sound-effect generation."""

    finished = pyqtSignal(str)      # saved path
    failed = pyqtSignal(str)
    stage = pyqtSignal(str)
    done = pyqtSignal(int)          # always 0 - WorkerPool-shaped like CreditsTask


class SoundTask(QRunnable):
    """One effect prompt -> one audio file, off the UI thread.

    Same reasoning as RefineTask/CreditsTask: an occasional single call a user
    triggers by hand, not a batch of many parallel jobs, so it gets its own
    small pool rather than GenerationPool. All of the sound_lint gate and the
    ElevenLabs transport live in tools/generate_sound.py - this only moves the
    call off the main loop.
    """

    def __init__(self, text, **kwargs):
        super().__init__()
        self.text = text
        self.kwargs = kwargs
        self.signals = SoundSignals()

    def run(self):
        try:
            path, error = gsnd.generate_effect(
                self.text, on_stage=lambda m: self.signals.stage.emit(m), **self.kwargs)
            if error:
                self.signals.failed.emit(str(error))
                return
            self.signals.finished.emit(str(path))
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(0)


class SpeechSignals(QObject):
    """Signals for one real ElevenLabs text-to-speech generation."""

    finished = pyqtSignal(str)      # saved path
    failed = pyqtSignal(str)
    stage = pyqtSignal(str)
    done = pyqtSignal(int)


class SpeechTask(QRunnable):
    """One line of text -> one spoken audio file, off the UI thread.

    Used by Sound's Voices tab, Ads' per-beat "Generate voiceover" and Cats'
    per-scene voiceover line - all three call this same task rather than each
    re-wrapping tools/generate_speech.py themselves.
    """

    def __init__(self, text, **kwargs):
        super().__init__()
        self.text = text
        self.kwargs = kwargs
        self.signals = SpeechSignals()

    def run(self):
        try:
            path, error = gspeech.generate_speech(
                self.text, on_stage=lambda m: self.signals.stage.emit(m), **self.kwargs)
            if error:
                self.signals.failed.emit(str(error))
                return
            self.signals.finished.emit(str(path))
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(0)


class VoiceListSignals(QObject):
    finished = pyqtSignal(object)   # [{voice_id, name, category}, ...]
    failed = pyqtSignal(str)
    done = pyqtSignal(int)


class VoiceListTask(QRunnable):
    """Refreshes the account's real voice list. Same shape as CreditsTask."""

    def __init__(self):
        super().__init__()
        self.signals = VoiceListSignals()

    def run(self):
        try:
            voices, error = voices_tool.list_voices()
        except Exception as exc:  # a worker must never take the app down
            voices, error = None, "{}: {}".format(type(exc).__name__, exc)
        if error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(voices)
        self.signals.done.emit(0)


class VoiceCloneSignals(QObject):
    finished = pyqtSignal(str)      # new voice_id
    failed = pyqtSignal(str)
    done = pyqtSignal(int)


class VoiceCloneTask(QRunnable):
    """Clones a voice from uploaded samples, off the UI thread.

    `consented` is threaded straight through from the GUI's own checkbox to
    elevenlabs_voices.clone_voice(), which refuses to run without it - the
    task does not add or relax that gate, only carries the value.
    """

    def __init__(self, name, sample_paths, description=None, consented=False):
        super().__init__()
        self.name = name
        self.sample_paths = list(sample_paths)
        self.description = description
        self.consented = consented
        self.signals = VoiceCloneSignals()

    def run(self):
        try:
            voice_id, error = voices_tool.clone_voice(
                self.name, self.sample_paths, description=self.description,
                consented=self.consented)
        except Exception as exc:  # a worker must never take the app down
            voice_id, error = None, "{}: {}".format(type(exc).__name__, exc)
        if error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(voice_id)
        self.signals.done.emit(0)


class VoiceDeleteSignals(QObject):
    finished = pyqtSignal(str)      # the voice_id that was deleted
    failed = pyqtSignal(str)
    done = pyqtSignal(int)


class VoiceDeleteTask(QRunnable):
    """Deletes one cloned voice, off the UI thread. Used by Settings' voice list."""

    def __init__(self, voice_id):
        super().__init__()
        self.voice_id = voice_id
        self.signals = VoiceDeleteSignals()

    def run(self):
        try:
            ok, error = voices_tool.delete_voice(self.voice_id)
        except Exception as exc:  # a worker must never take the app down
            ok, error = False, "{}: {}".format(type(exc).__name__, exc)
        if error or not ok:
            self.signals.failed.emit(str(error) if error else "Delete failed")
        else:
            self.signals.finished.emit(self.voice_id)
        self.signals.done.emit(0)


class GenerationSignals(QObject):
    """Signals for one generation task. QRunnable cannot emit; this can."""

    started = pyqtSignal(int)
    finished = pyqtSignal(int, str)     # index, image path
    failed = pyqtSignal(int, str)       # index, human-readable reason
    done = pyqtSignal(int)              # index, always - success or failure
    # Generation is now an async job that can take minutes; without progress the
    # app would look frozen while it polls.
    stage = pyqtSignal(int, str)        # index, what it is doing right now


class GenerationTask(QRunnable):
    """One prompt -> one image file, off the UI thread.

    All of the provider work - credentials, request building, polling the job and
    downloading the result - lives in generate_image.generate(). This class only
    moves that call off the main loop and reports what came back, so the GUI and
    the CLI can never disagree about how a provider is spoken to.
    """

    def __init__(self, index, prompt, provider=gi.DEFAULT_PROVIDER, out_name=None,
                 references=None, model=None, spec=None):
        super().__init__()
        self.index = index
        self.prompt = prompt
        self.provider = provider
        self.out_name = out_name
        self.references = list(references or [])
        self.model = model
        # The request options - aspect, resolution, output format. This was not
        # passed at all before, so the GUI never sent an aspect ratio and never
        # sent a resolution: every image came back 1:1 at 1K whatever was chosen.
        self.spec = dict(spec or {})
        self.signals = GenerationSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        index = self.index
        try:
            self.signals.started.emit(index)
            if self._cancelled:
                return

            path, error = gi.generate(
                provider=self.provider,
                prompt=self.prompt,
                out_name=self.out_name,
                references=self.references,
                model=self.model,
                spec=self.spec,
                should_cancel=lambda: self._cancelled,
                on_stage=lambda message: self.signals.stage.emit(index, message),
            )
            if self._cancelled:
                return
            if error:
                self.signals.failed.emit(index, str(error))
                return
            self.signals.finished.emit(index, str(path))
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit(index, "{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(index)


class VideoSignals(QObject):
    """Signals for one clip. Same shape as GenerationSignals, plus the cost."""

    started = pyqtSignal(int)
    finished = pyqtSignal(int, str, object)   # index, path, credits used or None
    failed = pyqtSignal(int, str)
    done = pyqtSignal(int)
    stage = pyqtSignal(int, str)


class VideoTask(QRunnable):
    """One motion prompt -> one .mp4, off the UI thread.

    Everything about how Kling is spoken to lives in generate_video.generate();
    this only moves the call off the main loop. `credits` comes back with the
    result because recordInfo reports what the job actually cost, and that real
    number is what turns a guessed price into a measured one.
    """

    def __init__(self, index, prompt, image=None, duration=5, aspect_ratio=None,
                 mode=None, sound=None, multi_shots=None, out_name=None, model=None):
        super().__init__()
        self.index = index
        self.prompt = prompt
        self.image = image
        self.duration = duration
        self.aspect_ratio = aspect_ratio
        self.mode = mode
        self.sound = sound
        self.multi_shots = multi_shots
        self.out_name = out_name
        self.model = model
        self.signals = VideoSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        index = self.index
        try:
            self.signals.started.emit(index)
            path, error, used = gv.generate(
                prompt=self.prompt, out_name=self.out_name, image=self.image,
                duration=self.duration, aspect_ratio=self.aspect_ratio,
                mode=self.mode, sound=self.sound, multi_shots=self.multi_shots,
                model=self.model,
                should_cancel=lambda: self._cancelled,
                on_stage=lambda message: self.signals.stage.emit(index, message),
            )
            if self._cancelled:
                return
            if error:
                self.signals.failed.emit(index, str(error))
                return
            self.signals.finished.emit(index, str(path), used)
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit(index, "{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit(index)


class RenderSignals(QObject):
    """Signals for one render job. No index - a render is one job per story,
    never batched, unlike stills/clips."""

    stage = pyqtSignal(str)
    finished = pyqtSignal(str)   # output path
    failed = pyqtSignal(str)
    done = pyqtSignal()


class RenderTask(QRunnable):
    """Scenes -> one .mp4, off the UI thread.

    Everything about how ffmpeg is spoken to lives in render_video.render();
    this only moves the call off the main loop, the same as VideoTask does for
    generate_video.generate().
    """

    def __init__(self, scenes, out_path, aspect_ratio=None):
        super().__init__()
        self.scenes = scenes
        self.out_path = out_path
        self.aspect_ratio = aspect_ratio
        self.signals = RenderSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            path, error = rv.render(
                self.scenes, self.out_path, aspect_ratio=self.aspect_ratio,
                should_cancel=lambda: self._cancelled,
                on_stage=lambda message: self.signals.stage.emit(message),
            )
            if self._cancelled:
                return
            if error:
                self.signals.failed.emit(str(error))
                return
            self.signals.finished.emit(str(path))
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit()


class VisionQcSignals(QObject):
    """Signals for one post-generation vision QC check. No index - one image,
    checked once, right after it is shown."""

    finished = pyqtSignal(object, int, int)   # checks list, score, total
    failed = pyqtSignal(str)
    done = pyqtSignal()


class VisionQcTask(QRunnable):
    """One generated image -> a vision-model check against its spec, off the
    UI thread. Everything about how the model is asked and its reply
    whitelisted lives in vision_lint.check(); this only moves the call off the
    main loop, the same as every other task in this file."""

    def __init__(self, image_path, spec, reference_path=None, model=None):
        super().__init__()
        self.image_path = image_path
        self.spec = spec
        self.reference_path = reference_path
        self.model = model
        self.signals = VisionQcSignals()

    def run(self):
        try:
            checks, score, total, error = vl.check(
                self.image_path, self.spec, reference_path=self.reference_path,
                model=self.model)
            if error:
                self.signals.failed.emit(str(error))
                return
            self.signals.finished.emit(checks, score, total)
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit()


class CoherenceSignals(QObject):
    """Signals for one semantic coherence check. One prompt, checked once,
    on demand - not on every keystroke like the deterministic gate."""

    finished = pyqtSignal(object, int, int)   # checks list, score, total
    failed = pyqtSignal(str)
    done = pyqtSignal()


class CoherenceTask(QRunnable):
    """One prompt -> a semantic coherence check, off the UI thread.

    Everything about how the model is asked and its reply whitelisted lives
    in coherence_lint.check(); this only moves the call off the main loop,
    the same as VisionQcTask does for vision_lint.check()."""

    def __init__(self, text, model=None):
        super().__init__()
        self.text = text
        self.model = model
        self.signals = CoherenceSignals()

    def run(self):
        try:
            checks, score, total, error = cl.check(self.text, model=self.model)
            if error:
                self.signals.failed.emit(str(error))
                return
            self.signals.finished.emit(checks, score, total)
        except Exception as exc:  # a worker must never take the app down
            self.signals.failed.emit("{}: {}".format(type(exc).__name__, exc))
        finally:
            self.signals.done.emit()


class CreditsSignals(QObject):
    finished = pyqtSignal(object, str)      # credits or None, error text
    done = pyqtSignal(int)                  # always 0 - lets WorkerPool track it like any other task


class CreditsTask(QRunnable):
    """Ask the provider what is left. Network-bound, so not on the UI thread.

    No key is not an error here - it is "unknown". A prepaid balance the app
    cannot see should read as a dash, not as a failure.
    """

    def __init__(self, provider=gi.DEFAULT_PROVIDER):
        super().__init__()
        self.provider = provider
        self.signals = CreditsSignals()

    def run(self):
        try:
            value, error = gi.credits(self.provider)
        except Exception as exc:      # a worker must never take the app down
            value, error = None, "{}: {}".format(type(exc).__name__, exc)
        self.signals.finished.emit(value, error or "")
        self.signals.done.emit(0)


class WorkerPool(QObject):
    """Runs a batch of already-built QRunnables with bounded concurrency.

    Stills, clips and the credits check each sized and counted their own
    QThreadPool independently before (3 threads, 2 threads, 1 thread - three
    copies of the same "how many are done" bookkeeping). This is that
    bookkeeping in one place; a task only needs a `.signals.done` signal
    shaped like `pyqtSignal(int)` - every task in this module already has one.
    """

    batch_started = pyqtSignal(int)
    progress = pyqtSignal(int, int)     # completed, total
    batch_finished = pyqtSignal()

    def __init__(self, max_concurrency=1, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max_concurrency)
        self._tasks = []
        self._done_tasks = set()
        self._total = 0
        self._completed = 0
        self._finished_emitted = False

    @property
    def busy(self):
        return self._completed < self._total

    @property
    def total(self):
        return self._total

    def submit_tasks(self, tasks):
        """`tasks`: already-constructed QRunnables. The caller has already
        wired whatever result signals (finished/failed/stage) it cares about -
        this only tracks progress and start/finish of the batch as a whole.
        """
        self._tasks = list(tasks)
        self._done_tasks = set()
        self._total = len(self._tasks)
        self._completed = 0
        self._finished_emitted = False
        if not self._tasks:
            self._finished_emitted = True
            self.batch_finished.emit()
            return
        for task in self._tasks:
            task.signals.done.connect(lambda _index, t=task: self._task_done(t))
        self.batch_started.emit(self._total)
        for task in self._tasks:
            self.pool.start(task)

    def cancel(self):
        for task in self._tasks:
            cancel = getattr(task, "cancel", None)
            if cancel:
                cancel()
        self.pool.clear()   # drops anything not yet started
        # clear() removes queued runnables that will now never emit `done`, so
        # without this the completed count never reaches the total, `busy`
        # stays True forever and every later generation is refused until the
        # app restarts. Mark every unfinished task done now; a late `done` from
        # a task that was already running is deduped by `_done_tasks`.
        for task in list(self._tasks):
            self._task_done(task)

    def _task_done(self, task):
        if task in self._done_tasks:
            return
        self._done_tasks.add(task)
        self._completed += 1
        self.progress.emit(self._completed, self._total)
        if self._completed >= self._total and not self._finished_emitted:
            self._finished_emitted = True
            self.batch_finished.emit()


class GenerationPool(QObject):
    """Runs a batch of GenerationTasks with bounded concurrency.

    Same public shape as before this class was rebuilt on top of `WorkerPool` -
    every call site elsewhere in the app is unaffected by that change.
    """

    started = pyqtSignal(int)
    item_finished = pyqtSignal(int, str)
    item_failed = pyqtSignal(int, str)
    progress = pyqtSignal(int, int)     # completed, total
    item_stage = pyqtSignal(int, str)   # index, current stage of an async job
    batch_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = WorkerPool(MAX_CONCURRENCY, self)
        self._pool.batch_started.connect(self.started)
        self._pool.progress.connect(self.progress)
        self._pool.batch_finished.connect(self.batch_finished)

    @property
    def busy(self):
        return self._pool.busy

    @property
    def total(self):
        return self._pool.total

    def submit(self, jobs, provider=gi.DEFAULT_PROVIDER, model=None, spec=None):
        """jobs: list of (index, prompt, out_name, references[, spec]).

        `spec` carries the request options shared by the batch; a job may append
        its own to override them, which is how a story scene sends its aspect.
        """
        tasks = []
        for job in jobs:
            index, prompt, out_name, references = job[:4]
            options = dict(spec or {})
            if len(job) > 4 and job[4]:
                options.update(job[4])
            task = GenerationTask(index, prompt, provider, out_name, references,
                                  model, options)
            task.signals.finished.connect(self.item_finished)
            task.signals.failed.connect(self.item_failed)
            task.signals.stage.connect(self.item_stage)
            tasks.append(task)
        self._pool.submit_tasks(tasks)

    def cancel(self):
        self._pool.cancel()


class VideoPool(QObject):
    """Runs a batch of VideoTasks with bounded concurrency.

    The video half of what `GenerationPool` does for stills - previously a raw
    `QThreadPool` built and looped over inline in `MainWindow.generate_videos`,
    sized differently (2 threads) with its own hand-rolled done/total counters
    duplicating `GenerationPool`'s. Now the same shared `WorkerPool` underneath,
    the same as stills and the credits check.
    """

    batch_started = pyqtSignal(int)
    item_finished = pyqtSignal(int, str, object)   # index, path, credits used or None
    item_failed = pyqtSignal(int, str)
    item_stage = pyqtSignal(int, str)
    progress = pyqtSignal(int, int)
    batch_finished = pyqtSignal()

    def __init__(self, max_concurrency=2, parent=None):
        super().__init__(parent)
        self._pool = WorkerPool(max_concurrency, self)
        self._pool.batch_started.connect(self.batch_started)
        self._pool.progress.connect(self.progress)
        self._pool.batch_finished.connect(self.batch_finished)

    @property
    def busy(self):
        return self._pool.busy

    def submit(self, jobs, aspect_ratio=None, **options):
        """jobs: list of dicts with index/prompt/image/duration/out_name."""
        tasks = []
        for job in jobs:
            task = VideoTask(job["index"], job["prompt"], image=job.get("image"),
                             duration=job.get("duration", 5), aspect_ratio=aspect_ratio,
                             out_name=job.get("out_name"), **options)
            task.signals.finished.connect(self.item_finished)
            task.signals.failed.connect(self.item_failed)
            task.signals.stage.connect(self.item_stage)
            tasks.append(task)
        self._pool.submit_tasks(tasks)

    def cancel(self):
        self._pool.cancel()


class BatchSession:
    """Everything about one running (possibly two-phase, locked-reference)
    still-image submission, in one object.

    This replaces what used to be four separate `MainWindow` attributes
    (`_batch_target`, `_sequence_rest`, `_sequence_reference`,
    `_sequence_total`, `_batch_offset`) that every submit/finish path had to
    set and clear together by hand - a natural way for one of the five to be
    forgotten and leave stale state for the next batch to inherit. One object,
    replaced wholesale by `None` when nothing is running, cannot do that.
    """

    def __init__(self, target, total, sequence_rest=None):
        self.target = target
        self.total = total
        self.offset = 0
        self.sequence_rest = list(sequence_rest or [])
        self.sequence_reference = None

    @property
    def is_locked_sequence(self):
        return bool(self.sequence_rest) or self.offset > 0


class VideoSession:
    """Everything about one running clip batch, in one object - the video
    equivalent of `BatchSession` (`_video_target`, `_video_seconds`,
    `_video_done`, `_video_total` collapsed the same way).
    """

    def __init__(self, target, total, seconds_by_index):
        self.target = target
        self.total = total
        self.done = 0
        self.seconds_by_index = dict(seconds_by_index)
