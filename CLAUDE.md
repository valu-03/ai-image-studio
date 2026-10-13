# AI Video Studio

An AI video and avatar production workspace, built on the method from the AI Video Bootcamp
(`C:\Users\Valentin\Downloads\Daniel Riley - AI Video Bootcamp\`). The course knowledge lives
in PDFs; this project turns it into something executable — repeatable procedures and small
scripts, so producing a convincing avatar or ad shot is a command, not a memory exercise.

Read this file at the start of every session. It is the map.

---

## The WAT framework

This project is organised around three parts. Everything here belongs to exactly one of them.

### W = Workflows
Step-by-step procedures that **orchestrate the work**. They live in `/workflows/`, one
Markdown file per job. A workflow has numbered steps, states its inputs and outputs
explicitly, and names the tool each step calls. Workflows are the source of truth for *how a
job is done* — they exist so the same job produces the same quality twice.

### A = Agent
**Claude Code** — the agent that reads, plans, and executes. The agent's job in this project:

1. Read this file.
2. Match the request to a workflow in `/workflows/`.
3. Read that workflow and follow it step by step.
4. Call tools from `/tools/`; do not reimplement their logic inline.
5. Write results to `/temp/outputs/` and report the path back.

If no workflow matches, say so and offer to write one — don't improvise a one-off procedure
that vanishes when the session ends.

### T = Tools
Scripts and integrations the agent **uses to get things done**. They live in `/tools/`. Each
tool does one job, runs from the command line, and is deterministic. Tools hold the logic;
workflows hold the sequence; the agent connects them.

### The GUI is a fourth thing, and it is not a fourth letter
`gui.py` plus `ui/` is a **front end over W and T for the human**, for when you'd rather turn
a dial than retype a command. It composes prompts by calling `build_prompt.compose()`, scores
them with `realism_lint.lint()`, logs outcomes through `history.py` and generates through
`generate_image.py` — the exact functions the CLI uses. It must never grow its own copy of
that logic: if the GUI and the CLI could ever disagree about what a good prompt is, the
framework has been broken. New logic goes in `/tools/`, and the GUI calls it.

Its build contract is `pyqt6_system_prompt.md` — navigation rail, top utility bar,
`QStackedWidget` canvas, the mandated dark palette, `QRunnable` workers for anything
network- or disk-bound. Read it before touching `ui/`.

### The loop that makes this more than a prompt builder
The linter scores whether a realism term is **present**. The history log records whether it
**worked**. Rating a generation feeds `history.weights()`, which biases future vocabulary
selection. Every rating makes the next prompt better informed, so the bank becomes calibrated
to your results rather than to a PDF. Encourage rating — an unrated generation is a wasted
experiment.

---

## Folder map

```
AI Video Studio\
  CLAUDE.md            this file — read every session
  .env                 API keys and secrets. NEVER commit. NEVER print its values.
  .env.example         committed template showing which keys exist
  gui.py               desktop front end — `python gui.py`
  pyqt6_system_prompt.md   the GUI's build contract; ui/ implements it
  ui\                  PyQt6 UI layer (tokens, assets, theme, widgets, workers, views)
  assets\icons\        generated SVG icon set (`python tools/make_icons.py`)
  workflows\           W — step-by-step procedures (see workflows/README.md for the index)
  tools\               T — scripts and integrations (see tools/README.md for the index)
  tests\               every suite; `python tests/run_all.py` runs them all
  temp\
    outputs\           generated artifacts. Disposable — safe to clear.
      prompts\         built prompts, ready to paste
      images\          generated images
      history.jsonl    the outcome log — what was made and how good it was
    resources\         reference INPUTS the agent reads from. NOT disposable.
      characters\      character spec JSON — reusable avatar identities
```

`temp/outputs/` is scratch — anything there can be regenerated. `temp/resources/` is the
opposite: it holds the inputs you've invested in (character sheets, reference photos, briefs).
Never delete or overwrite anything in `temp/resources/` without being asked.

---

## How to run a job

1. **Identify the workflow.** Check `workflows/README.md`.
2. **Read the workflow file in full** before starting. Don't work from its title.
3. **Gather inputs** from `temp/resources/`, or ask the user for what's missing — ask only
   for what you genuinely can't infer from the brief.
4. **Run the tools** the workflow names, in order.
5. **Write outputs** to `temp/outputs/`.
6. **Report the output path** so the user can open the file.

---

## Conventions

- **Output naming**: `<workflow>-<slug>-<YYYYMMDD-HHMM>.<ext>`
  e.g. `avatar-skincare-ugc-20260828-1430.txt`
- **Tools are self-documenting**: every tool answers `python tools/<name>.py --help`.
- **Tools are stdlib-only** unless a dependency is unavoidable and stated in `tools/README.md`.
- **New capability = new workflow file** plus an entry in `workflows/README.md`. A capability
  that isn't written down doesn't exist.
- **Paths in workflows are relative** to this project root.

---

## Rules

- Never commit `.env`, never print or echo a key's value, never paste a key into a prompt or
  a file under `temp/`.
- Never write outside `temp/` unless the user asks for it, or a workflow says to.
- Never delete anything in `temp/resources/` yourself. The one sanctioned path is the
  character library's Delete button, which is user-initiated and confirmed. The rule still
  binds you: do not remove a character spec because it looks unused.
- **Live as of 2026-08-30.** Kie and OpenRouter both have real keys, and the whole path has
  been run end to end: submit, poll, download, a reference upload, and an LLM rewrite the gate
  correctly rejected. Two things only a real call could find needed fixing - Kie's file hosts
  answer 403 to the default urllib agent, so every request now sends a User-Agent.
- The default image model is **Nano Banana Pro**, now reached through **Kie** rather than
  Google directly. Kie and Higgsfield are the only image providers; both are asynchronous
  (submit a job, poll it, download a URL), so a generation takes a while by design.
- **OpenRouter is text-only and optional.** It powers the Brief tab and nothing else. No
  key means no prompt helpers; everything else still works.
- **Video is Kling 3.0 through Kie**, on the same job API as the images
  (`createTask` -> `recordInfo` -> download). `tools/generate_video.py` holds no transport of
  its own: it reuses `generate_image.py`'s `post_json`, `poll`, `download`,
  `upload_kie_reference` and both Kie parsers, so the two can never disagree about how the
  provider is spoken to. Clips default to `mode=std` and `sound=false` - the cheapest pair
  that still looks right, and Kling's own audio would fight the ElevenLabs layers.
- **Reference images are Kie-only.** Higgsfield's Soul endpoint has no reference input, so
  generating with a reference set there is refused, never silently dropped - a dropped
  reference quietly produces a different person.
- **Every avatar prompt must pass `tools/realism_lint.py` (8/8, no banned terms) before it is
  handed to the user.** A prompt that scores lower gets fixed, not shipped.
- When an image comes back looking fake, the fix is a **prompt** change — name which realism
  layer to strengthen. Don't reach for a different model first.
- **The text model suggests; `realism_lint` decides.** Never write a model's output straight
  into a prompt or a spec. `tools/brief.py` re-lints every rewrite and rejects it below 8/8
  or on any banned term, and whitelists spec keys so a model can't set `seed`, `reference`,
  `lock_identity` or `overrides`. Any new LLM feature validates its reply the same way — the
  quality gate is the point of this project, and a text model must not be the hole in it.
- **State the purpose before the settings.** `purpose` supplies `shot` and `aspect`; an
  explicit choice always wins, and a disagreement is reported, never silently corrected.
- **Composition rules are opt-in. Never impose one.** The composition layer's terms and the
  shot presets carry framing language only - no grid, ratio or spiral. A geometry reaches a
  prompt only when the user picks one of the eight `composition_guides` or types their own;
  the default is `(none)`, not `(auto)`. Do not add a geometric term to the layer's `terms` or
  to a shot preset - that is exactly the behaviour this design removed. Auto-fill obeys the
  same rule: it may *suggest* a guide and a lighting source, and the user applies them.
- **A chosen guide is a pin, not a replacement.** It takes the first composition slot and the
  bank fills the rest, so the layer never drops below its normal strength - and because it is
  applied last, it outranks the shot preset and any camera-move hint. Every new guide needs a
  detection keyword in `realism_lint.py`, or a deliberate choice would silently fail the
  8/8 gate.
- **Shot, lighting and composition accept free text, and `pick` decides what happens to
  it.** A `pick: 1` layer can be replaced by an explicit value (lighting, and a custom shot
  taking the camera slot); a `pick: 2` layer is pinned, never replaced (composition). That is
  why a typed composition can never cost the prompt its composition layer, while a typed shot
  naming no camera legitimately drops it to 7/8 - which the panel reports rather than hides.
  Preset keys and free text are separate spec keys (`shot` vs `shot_custom`) so a misspelt
  preset is still rejected instead of becoming a custom phrase.
- **A story scene is exactly one clip, and the SCENE COUNT absorbs a long runtime.** Kling 3.0
  generates any whole second from 3 to 15. So the arc gives the *shape* and the runtime gives
  the *number of scenes*: `beat_sequence()` repeats the beats marked `repeatable` until no
  scene needs longer than one clip. A 30-second classic is seven scenes, not five.
  `clip_seconds` and `edit_seconds` still differ - a clip is a whole second and a scene rarely
  is - but by a rounding, not by half.
- **Cats has two FORMATS, not one arc with options.** `story` (one cat, an escalating
  narrative, a camera move every scene) and `trade` (two cats in costume doing a real job,
  one locked-off take per gag, no words at all) are different genres, not variations of the
  same one. `build_story.beats/arcs/scene_fields/default_clip/default_seconds` all take an
  optional `fmt` and fall back to the bank's top level, so `story` needed no data moved when
  `trade` was added. **`trade` was measured, not designed**: four reference videos in
  `Downloads/video` were cut-detected (`ffmpeg select=gt(scene,0.1)`), which found *zero cuts*
  inside two of them and one in a third - every one is a single locked-off ~10s take. Guessing
  the format from the ask ("costumed working cats") without measuring the actual videos would
  have produced a plausible-sounding format that did not match what was asked for.
- **The locked-off camera lives in the format block, not in `motion_bank.json`.** That bank
  is hashed to prove the shared gate is never widened; adding a movement there for one format
  would be the exact mistake the stylised-look-stays-out-of-`prompt_bank.json` rule exists to
  prevent. `story_bank.formats.trade.camera` supplies the phrase directly.
- **A format's own checks replace the default list, they do not add to it.**
  `story_lint.checks_for(bank, fmt)` reads `formats[fmt].checks`; `trade` drops `hook`,
  `moves_vary` and `words` (a full 10s take has no 3-second window, no varying camera by
  design, and no captions) and adds `costume`, `pair`, `locked_off`, `tasks_vary`. A trade
  story scoring 12/12 with no captions is correct, not a hole in the gate.
- **A view built once at construction cannot show format-dependent content** - the CapCut
  "Assembling it" panel and the script-box help text were built as static widgets before any
  format existed to ask about, so switching format left them showing `story`'s hook-trim
  advice under a `trade` story. Anything that depends on the chosen format needs a
  `refresh_*()` called from `on_format_changed()`, not a value baked in at `setup_ui()`.
- **`isVisible()` is always False on a widget tree that was never `.show()`n** - it reflects
  the whole ancestor chain, not the explicit call. A test asserting a row's visibility after
  switching format must check `isHidden()` instead, which reflects the explicit `setVisible()`
  regardless of whether the window itself is on screen.
- **Membership, not divisibility.** `check_clip_lengths` asks whether a clip length is *in*
  3..15. It used to accept any multiple of a legal length, on the theory that a long scene was
  "two clips" - but nothing downstream ever split one, so a 15-second scene was one image, one
  motion prompt and one impossible request. The planner, the linter and the test all agreed
  with each other and all disagreed with Kling, which is why it survived a full green suite.
  When three things agree, check them against the thing outside the program.
- **Never send a value the provider's docs do not list.** `build_kie_submit` and
  `generate_video.build_submit` validate every field against its documented enum and *report*
  what they dropped. Kling's `duration` is a STRING; sending the integer fails at the provider
  with an error that does not explain itself.
- **Results go to the view that asked for them.** `_batch_target` and `_video_target` exist
  because generation used to be routed to the Images/Variants grid whoever asked, and that
  grid silently drops any index it has no tile for - so a whole generated story was written to
  disk and shown nowhere. A batch handler that cannot find its row must say so, never `return`.
- **A locked sequence runs in two phases.** The reference cannot exist before shot 1 does, so
  shot 1 goes out alone and the rest carry its real file. Passing an empty reference list while
  refusing providers that lack reference support is the bug that made five shots five
  different people.
- **Say what a batch will cost before it runs.** `pricing.json` is seeded from a marketing page
  and says so; `recordInfo`'s `creditsConsumed` is the only measured figure, and it overwrites
  the guess. `AIVS_ASSUME_YES` skips the confirmation for suites and scripted runs - a modal
  nobody can click is a hang, not a safeguard.
- **The stylised look must never enter `prompt_bank.json`.** That bank bans `cartoon style`,
  `cgi` and `3d render`, which is correct for every other section. The animated style lives in
  `story_bank.json` and arrives through `spec["overrides"]`; photoreal scenes are judged by
  `realism_lint`, stylised ones by `story_lint`'s own style check. If a stylised prompt fails,
  fix the style block - do not loosen the shared gate. `tests/test_story.py` hashes
  `prompt_bank.json` and `realism_lint.py` so that cannot happen quietly.
- **ElevenLabs makes sound EFFECTS.** Not music, not speech. `sound_lint` rejects both before
  a generation is spent. Its other rules were MEASURED across the course's 100 examples, not
  guessed - the first version guessed and rejected 31 of them. Those 100 are the fixture: if
  the linter ever rejects one, the linter is wrong, the same logic as LumaWash for ads.
- **A scene needs three sound layers, not one.** Ambience (never noticed), key effect (lands
  on the action frame), accent (one per scene at most). Two accents cancel each other out.
- **Ad timing is capped, never a percentage.** The checklist demands the product appear
  within 5-10 seconds, and no proportional split survives a longer ad. `build_ad.beat_timings()`
  caps the setup in absolute seconds; beat 4 absorbs the rest. Do not "simplify" it to weights.
- **In an advert, beats 1-3 sell the feeling and beat 4 sells the mechanism.** "Zero sulfates"
  is correct in beat 4 and wrong in beat 1, so `ad_lint`'s emotion check is scoped to the first
  three beats. The course's LumaWash example is the fixture: if it ever scores below 9/9, the
  linter has drifted into rejecting correct ads.
- **A locked sequence needs Kie.** Beats 2-5 carry beat 1's face by reference; a provider
  without reference input would give five different people, so the batch is refused there.
- **Choose the camera move before finishing the still.** A tight portrait cannot be orbited.
  `build_motion.check_compatibility()` says what a move needs from the frame; the same
  precedence rule applies — the movement fills gaps, your choice wins, conflicts are reported.
- **Bump `version` in `prompt_bank.json` whenever you change the term lists.** Ratings
  reference vocabulary by name; without a version bump, old ratings silently come to mean
  something else and `weights()` returns confident nonsense.
- **Layout is a gate, not an opinion.** `tests/test_layout.py` walks every section and
  sub-tab in both themes at 1100x700 and 1440x900 and fails on overlapping widgets, clipped
  labels, anything spilling out of its card, **controls crushed below their minimum height**,
  and **paragraphs given fewer lines than their text needs**. Judge layout by running it, not
  by looking at a screenshot.
- **A layout that runs out of room does not refuse - it crushes everything.** Two tall cards
  stacked in one `QVBoxLayout` asked for 700px of a 537px page, so Qt shared the shortfall out
  and violated every minimum at once: fields 9px tall with their text sliced through the
  middle. Nothing overlapped and nothing was too narrow, so the first four checks all passed.
  When a form and a text area both want the full height, put them **side by side** with the
  form in a `QScrollArea`; a page of stacked cards (Settings) scrolls as a whole.
- **A `QTreeWidget` will not wrap.** `setWordWrap(True)` does nothing without a custom
  delegate - a row stays one line tall and clips mid-word, and turning off `TextElideMode`
  only removes the ellipsis. Prose belongs in labels, not in tree columns. Cats, Ads and Sound
  each solved this the same way independently before the design rebuild; it is now
  `ui/widgets.GateTree` - rows in a tree, the selected (or first-failing) row's reason in a
  label beneath it. Adopt it where a gate's own detail strings actually run long (Ads' and
  Cats' gates do, 50-70+ characters); a gate with short one-line details (Sound's, Videos')
  gains nothing from it and is left as a plain tree on purpose - GateTree is not a mandate,
  it is what to reach for once a detail string stops fitting a column.
- **Never let a scaled pixmap drive a widget's size hint.** A QLabel reports its pixmap's size
  as its hint, so a label that scales its pixmap to fit itself feeds its layout a hint that
  grows every pass. In a resizable QScrollArea that does not converge - with 9:16 images it
  grew until Qt died. `ImagePreview` pins both hints to its minimum size; keep it that way.
- **A test must never WRITE to the user's live data either.** `AIVS_HISTORY_FILE` redirects
  the outcome log, and every suite that drives a generate path must set it. Ratings feed
  `history.weights()`, which biases the vocabulary the app suggests, so a handful of synthetic
  8/8 rows silently tilts it - twenty-one of them got in while the Cats generation test was
  being written. Same reasoning as `AIVS_ENV_FILE`: the test should not be able to reach the
  live data at all, rather than being trusted to clean up afterwards.
- **The same is true of `tools/pricing.json`, and it had no seam at all.** A real clip
  generated once through the CLI to verify a feature - correct, intended behaviour, the whole
  point of the `confidence: measured` field - permanently overwrites the tracked seed numbers.
  `test_video.py` assumed the file was always still `estimated`/27 and broke twice on two
  different real charges before this was fixed. `AIVS_PRICING_FILE` now redirects
  `generate_video.PRICING_PATH` the same way `AIVS_HISTORY_FILE` redirects the outcome log;
  `run_all.py` seeds a disposable copy for every suite and `test_video.py` seeds its own
  literal fixture too, so it stays safe run standalone. If `pricing.json` on disk ever reads
  `measured` with no corresponding real clip in `temp/outputs/videos/` to explain it, that is
  this bug recurring some other way, not a value to trust.
- **A test must never destroy the user's live data either.** `temp/outputs/` being
  "disposable" is not a licence for a test to dispose of it. `smoke_gui.py` deleted every PNG
  in `temp/outputs/images/` rather than the ones it made, and `run_all.py` unlinked the whole
  of `history.jsonl` while calling every row synthetic - which wiped every rating the user had
  given, and those ratings are what `history.weights()` runs on. Both now snapshot first and
  remove only what the run added.
- **A GUI suite must call `win.show()` before it does anything else, even offscreen.**
  Skipping it does not fail loudly - the suite runs, every check passes, and then the
  interpreter crashes with an access violation on exit, intermittently (observed at roughly a
  third to a half of runs). `test_cats_custom.py` was written without it and flaked in exactly
  that shape; adding `win.show(); app.processEvents()` right after constructing `MainWindow`,
  the same line every other GUI suite already had, made it disappear over a dozen consecutive
  runs. Something about `QT_QPA_PLATFORM=offscreen` leaves a widget only half-initialised
  until its first show/layout pass, and that half-initialised state is what segfaults at
  teardown - not anything about the widgets a particular suite happens to build. If a suite's
  checks all pass but `run_all.py` still marks it failed with no FAIL lines and a garbage
  return code, look for a missing `win.show()` before chasing the feature code.
- **A test must never depend on the user's live data.** Two suites asserted things about
  `temp/resources/characters/` - one that a fixture file existed, one that the first saved
  character had no composition guide. Both broke the moment the user used the app. Load a
  fixed spec instead.
- **Say when something is NOT from the course.** The Kling toolkit, the ad checklist, the
  realism layers and the 100 sound prompts are transcribed from it. The cat story structure and
  the CapCut steps are not - those lessons are video files - and `workflows/cat-story-video.md`
  and the CapCut panel both say so. Do not quietly promote general craft to course material.
- **The higgsfield.ai-inspired look is additive, not a repaint.** `ui/tokens.py` gained a
  second accent hue (`accent2`) and a `primary_gradient` built from the two, plus
  `surface_glass`, on top of the mandated dark palette from `pyqt6_system_prompt.md` §2 -
  every named token from that mandate still holds its original value. The gradient is reserved
  for the one primary action per view (generate/draft/apply) and the credits/busy badge; a
  semantic colour (success/warning/error) never becomes a gradient, or the colour stops meaning
  what it says. `theme.hover_elevate()`/`theme.pulse()` animate a `QGraphicsDropShadowEffect`'s
  blur, never a layout-managed widget's own geometry - Qt's layout system re-fights any
  animation that tries to change a widget's size or position on every frame.
- **The nav rail's checked state stays a flat chip, not the new gradient.** The active icon is
  drawn in the flat accent colour (`make_icons.ACCENT`); putting that same icon on the new
  blue-to-violet gradient background nearly loses it against the blue half. The chip gets a
  border and a soft accent-tinted glow instead - the gradient is for large, high-contrast CTAs,
  not small icon-plus-text rows where legibility is the whole point.
- **One `WorkerPool` now underlies stills, clips and the credits check** (`ui/workers.py`) -
  three independently-sized, independently-counted `QThreadPool`s before. `GenerationPool` and
  the new `VideoPool` are thin wrappers with their own signal names, kept for every existing
  call site; only the counting logic moved. `MainWindow`'s nine scattered batch/video-tracking
  attributes (`_batch_target`, `_sequence_rest`, `_video_seconds`, `_video_done`, ...) are two
  objects now (`BatchSession`, `VideoSession`, both in `workers.py`), replaced wholesale by
  `None` between batches rather than five-to-nine fields cleared by hand on every path.
- **`AiSuggestionBadge` and `ResultCard`** (`ui/widgets.py`) are the shared shapes for "call the
  model, offer to apply what came back" (Compose autofill, Cats' write-story, Ads' draft-copy,
  all three of Brief's tabs) and "one generated result: status, thumbnail, rating" (Variants'
  grid; Compose's own single big preview stays `ImagePreview` - a tile and a one-up preview are
  different shapes and forcing them to match would hurt one of the two). `AiSuggestionBadge`
  tracks a real `is_thinking` flag - a wait condition that instead compares the badge's
  rendered text against a hardcoded "still thinking" string breaks the moment two callers pass
  different gerunds ("Drafting…" vs "Rewriting…"), which is exactly what happened the first
  time this shipped.
- **Cats' Custom Prompt tab is the one place in the app a prompt is INGESTED, not composed.**
  Every other prompt anywhere in the app is built outward from a spec by `build_prompt.compose()`
  (or `build_story.compose_story()`, which calls it per scene) - a small set of structured
  fields going in, a realism-gated prompt coming out. This tab runs the opposite direction: the
  user already has a fully-written shot description and wants it split into Subject/Background/
  Style & Atmosphere, then adapted by a change instruction, a reference image, or both. It does
  not touch `build_story.py`'s beat/arc engine and is not a fourth scene format - it is one
  shot, generated through the same `realism_lint` 8/8 gate as everywhere else
  (`realism_lint.checks_for()`, feeding a `GateTree`), just never expressed as `spec` fields.
  `tools/brief.py`'s `analyze_custom_prompt`/`refine_custom_prompt` follow the same whitelist
  rule as every other AI-suggestion feature (`CUSTOM_PROMPT_KEYS` - a model cannot smuggle in
  `seed`, `reference` or `lock_identity` through this door either), and the reference image is
  read by the vision-capable `ask_llm.ask(images=...)` path `brief.critique_image` already
  used - it informs wording only, and is deliberately never carried into the generation
  request as an identity-lock reference the way Compose's own reference is.
- **Videos' Motion tab and Cats' Prompts tab both build the Kling prompt from the same
  hands-on template now**: `[SHOT TYPE] + [SUBJECT] + [ACTION] + [STYLE] + [CAMERA MOVEMENT] +
  [AUDIO CUES]`, six editable fields replacing what used to be a read-only, auto-composed box
  (Videos) or fully automatic per-beat text with no control at all (Cats). Picking a movement
  (Videos) or opening a scene's card for the first time (Cats) prefills every field; after that,
  only picking a *different* movement, or a story rebuild that then re-renders the Prompts tab,
  resets them - a hand edit otherwise survives (`build_motion.assemble_template()`, `ui/views/
  videos.py`, `CatsView.custom_motion` in `ui/views/cats.py`). The assembled text always leads
  with camera movement regardless of the fields' on-screen order - `motion_lint`'s rule 1 is a
  Kling-toolkit PDF rule, not a style choice, and it fails the moment anything else opens the
  prompt.
- **Audio Cues means two different things depending on where it is, on purpose.** Cats already
  has a real per-scene sound system (three ElevenLabs layers, gated by `sound_lint`); there, the
  field's text becomes that scene's *key-effect* layer (`build_sound.scene_sound()`'s new
  `key_override` param - explicit choice wins, same precedence rule as shot/lighting/
  composition), and shows up in the actual CapCut sheet. Videos' Motion tab has no scene or
  sound sheet to attach to at all, so there it is a standalone suggestion - built and scored the
  same way (`sound_lint`), shown with its own badge and its own "Copy sound cue" button - and
  it is never sent to Kling and never persisted. Kling's own native audio stays off either way;
  see the "two soundtracks fight" rule above.
- **A video prompt's default style is a named camera and colour grade, not "cinematic
  lighting."** That phrase, and "professional," "high quality," are exactly the vague words a
  video model has nothing to act on - `motion_bank.json`'s new `style_presets` list gives it
  something concrete instead (`build_motion.style_preset()`, cycled by seed the same
  reproducible way `build_sound.accent_for()` cycles accents). Every prompt - hand-built through
  the template or still auto-composed by `compose()` for a story that never visits the Prompts
  tab - also always closes with a standing negative guard now (`negative_tail()`,
  `motion_bank.json`'s `negatives` list: warped faces, floating limbs, distorted hands, and
  the other specific artifact classes a video model actually fails on, not a vague "no bad
  quality" plea). `motion_lint` also gained a sixth check, **"One action, not a chain"** -
  "walking while talking while eating" confuses a video model exactly the way two competing
  camera movements do, so it is rejected the same way. None of this was guessed: it is lifted
  directly from a widely-read "10,000 AI videos" retrospective, cross-checked against what this
  app already did before changing anything.
- **Compose's provider, model, resolution and output format are per-generation choices now, not
  only account-wide Settings.** Every `SpecEditor` field was already free-text/overridable;
  these four were the one thing in the whole Images tab that was not. `ui/views/compose.py`
  gained `provider_override()`/`model_override()`/`options_override()`, read by
  `MainWindow.generate_single()` and falling back to Settings' values when left on "(use
  Settings)" - today's behaviour, unchanged, when nobody touches them. Scoped to Compose's own
  single-image path on purpose; Variants' batch still uses Settings' values.
- **Every output folder is created at launch, not the first time something writes into it.**
  `ui/assets.ensure_output_dirs()`, called from `MainWindow.__init__`, covers
  characters/prompts/images/videos. `VIDEOS_DIR` was missing from `ui/assets.py`'s path table
  entirely until this pass - `generate_video.py` had its own separate `temp/outputs/videos/`
  constant that nothing else in the app knew about, so Settings had no "Open Videos folder"
  button and the folder did not exist until the first clip was ever rendered.
- **A combo camera movement's own lead/detail text is exempt from the "one action, not a
  chain" check.** The Kling Camera PDF names 4 "combo movements" as a legitimate technique
  (`motion_bank.json`'s `category: "combo"` - Push-In + Tilt Up, Crane Down + Orbit, POV +
  Handheld + Fall, Track Behind + Push-In; 30 core + 6 niche + 4 combo = the bank's 40).
  Their own phrasing legitimately uses "while"/"and" ("descending while circling") - the check
  exists to catch a chained SUBJECT action ("walking while talking while eating"), not one
  continuous camera technique, so `motion_lint.chains_actions()` strips the movement's lead/
  detail text before looking for a chain marker. Shipped and fixed in the same pass: 3 of the
  bank's own 40 sanctioned movements failed this check the moment it landed, found by cross-
  referencing the Kling Camera PDF against the actual bank rather than guessing.
- **`tools/upscale_image.py` is the bootcamp's own "upscale before you animate" rule, not a new
  provider path.** Phase 2's upscaling lesson gives an exact 4K prompt template and the pipeline
  rule that a still should be upscaled before it goes to Videos or Cats - the app had no upscale
  feature at all. It is nothing more than `generate_image.generate()` with the image being
  upscaled as the sole reference and `UPSCALE_PROMPT` (the course's template, verbatim) instead
  of a user-written prompt - no new transport, no new job shape. Compose's "Upscale to 4K"
  button (`compose_view.upscale_requested` -> `MainWindow.upscale_image()`) submits through the
  same `GenerationPool` `generate_single()` already uses, so the result routes back to
  `compose_view.show_image()` the same way any other single-image job does.
- **Variants can vary `shot`, not only `seed` - "N angles, same seed" (Higgsfield SHOTS'
  technique).** Before this, the only thing a batch could ever sample was the seed at a fixed
  spec; the bootcamp's own multi-angle lesson is the opposite - one reference image held fixed,
  the camera angle varied. `VariantsView.angle_mode()` iterates `bank["shot_presets"]` instead
  of a seed range, with `seed` fixed and `shot_custom` explicitly cleared per variant (a custom
  shot beats a preset outright per `build_prompt.custom_shot()` - left set, every "angle" would
  render the same shot four times). Card captions, output filenames and status messages name
  the shot instead of "seed N" when a card carries one (`card.shot`, `None` in seed mode);
  everything else downstream (`ResultCard`, rating, `history.append`, the reference attachment
  in `request_generate()`) is unchanged - a card is still one entry keyed by index regardless of
  what varied to produce it.
- **Videos' Motion tab attaches a first frame now - the actual cause of "not the video I
  want."** Kling is image-to-video underneath; the still constrains composition and identity
  far more than the prompt does, and every clip made here used to start from text alone
  (`"image": None`, always) while Cats' own per-scene clips already attached one correctly. No
  new transport was needed - `generate_video.generate(image=...)`, `VideoTask`, and
  `VideoPool.submit()` already read a real path through untouched. `VideosView._resolved_still()`
  defaults to whatever `MainWindow.compose_view.current_image` is (wired the same way `context`
  already reads Compose's spec) and an explicit "Choose still..." pick overrides it - same
  precedence rule as everywhere else. Generating with genuinely nothing attached is the one
  place in this view that gets a hard confirmation, not just a warning badge, since it is the
  literal failure mode being fixed.
- **A test that calls a view's own `request_video()`/`generate_requested`-style method on a real
  `MainWindow` fires the REAL signal chain wired at construction - straight into a background
  `QThreadPool` job with no mock underneath it.** This had never been exercised before
  (`smoke_gui.py` never drives Kling video generation either), and the first test that did
  crashed the interpreter with no traceback - a native access violation, not a Python exception,
  because the real job ran against a fake endpoint from a worker thread while the test process
  moved on. Patch the instance method itself before calling the real trigger (`win.generate_videos
  = lambda *a, **k: None`, restored after) - the same `win.pool.submit = fake_submit` pattern
  already used for Compose's per-generation overrides, just for the video pool's entry point.
- **`AIVideoStudio.spec` ships `tools/` as loose data files, never as PyInstaller-analysed
  modules.** Every `ROOT =` in this codebase is `Path(__file__).resolve().parent(.parent)`, and
  `tools/` has no `__init__.py` - every module there is imported as a bare top-level name
  (`import build_prompt as bp`) via a runtime `sys.path.insert()`. The first attempt used
  `pathex=["tools"]` so PyInstaller's analyser could find those imports, and it built fine - but
  a pathex-discovered module with no package path is flattened to look like it lives directly
  beside the exe, not inside `tools/`: `Path(__file__).resolve().parent` (one parent, `tools/*.py`'s
  own bank-file lookup) pointed AT the app root instead of `tools/`, and `Path(__file__).resolve()
  .parent.parent` (every `tools/*.py`'s own `ROOT`) pointed ONE LEVEL ABOVE the app root entirely -
  `temp/outputs/` would have been created as a sibling of the whole distribution folder, not
  inside it. Caught by actually running the built exe, not by reading the spec. The fix ships
  `tools/` as real, loose `.py` + `.json` files (`datas=[("tools", "tools"), ...]`, no `pathex`) -
  each module's `__file__` is then a real on-disk path exactly where it is in the source repo, so
  every existing `ROOT` computation resolves exactly as it does in dev mode. `--contents-directory .`
  (the spec's `EXE(contents_directory=".")`) is what makes this possible at all - it restores the
  pre-6.0 flat layout, without which even a correct `tools/` would land inside a `_internal/`
  subfolder a level away from where `.env`/`temp/` are expected to sit.
- **A `realism_lint.py` `DETECT` key is deliberately broader than what `prompt_bank.json` can
  generate** - a prompt may say "shot on a full-frame camera" by hand and still satisfy the lens
  layer, even though no bank term produces that exact phrase. Most such gaps are intentional
  (free-text headroom, drawn from the bootcamp PDF's worked-example prose rather than its
  canonical per-category bullet list). One genuinely was not: `"subtle rim light"` is in the
  PDF's own 8-item lighting list and in `DETECT`, but `prompt_bank.json`'s `lighting.terms` had
  swapped it out for two bank-invented additions - detectable, never generatable. Found by
  auditing every layer's `DETECT` list against the PDF's canonical list, not by guessing; fixed
  by adding the missing term and bumping `prompt_bank.json`'s `version`. Before adding a term
  "to be safe," check whether the gap is this kind (a real, PDF-sourced omission) or the
  intentional free-text-headroom kind - widening `DETECT` further is never the fix either way.
- **Video prompts are now gated on the negative-tail guard actually being present, the same way
  images always have been.** `build_motion.compose()`/`assemble_template()` always append
  `negative_tail(bank)`, but nothing ever checked that it survived - a hand edit or a future
  code path that forgot to call it would still score a clean PASS. `motion_lint.negatives_present()`
  (rule 7) checks for the bank's literal negative terms, not a phrasing pattern - a Kling prompt's
  tail is always the same comma-joined bank phrases, unlike an image prompt's freely-worded "no
  X," so exact-term matching is the correct check here, not a weaker one.
- **`motion_bank.json`'s `style_presets` grew from 6 to 16** (version 2 -> 3), combining the same
  PDF camera/lighting/grade vocabulary the image side already had (DSLR/mirrorless/smartphone/
  documentary/vintage-film/handheld camera types x golden-hour/window-light/overcast-daylight
  lighting x muted/earthy/warm colour grades) - richer photographic language per Kling clip, not
  just the original 6 phrases cycling on repeat. Style vocabulary only; `MOTION_VERBS`,
  `CONTRADICTIONS` and the 40 movements themselves are untouched. Two early drafts used "cinematic
  color balance," which an existing test already banned (the Reddit-retrospective rule against
  vague words like "cinematic"/"professional"/"high quality") - `prompt_bank.json`'s own colour
  layer uses that exact phrase and gets away with it because it names a real, specific grade in
  context there; the lesson is that a word banned in one bank is not automatically safe to reuse
  in a different one just because it looks concrete in isolation.
- **`tools/refine_image.py` closes the one loop that was still 100% manual: generate -> notice
  it's off -> figure out which realism layer is weak -> re-prompt by hand.** It does not invent a
  new critique mechanism - `brief.critique_image()` already asks a vision model which of the 8
  named `realism_lint` layers look weak, already whitelisted against exactly those 8 names (the
  same discipline as every other AI-assisted feature's key whitelist). `refine_image.refine()`
  adds the missing back half: act on the critique. `strengthen()` pulls MORE of a weak layer's own
  already-vetted terms via `spec["overrides"]` for a `pick > 1` layer (core/lens/texture/colour/
  composition/grain - stacking more never contradicts), but SWAPS to a different single term for a
  `pick: 1` layer (camera/lighting) instead of stacking, because `prompt_bank.json`'s own lighting
  note warns that mixing two sources contradicts itself the same way two cameras would - "strengthen
  this layer" cannot mean the same operation for both kinds without breaking that rule. Capped at
  2 retries (3 generations total, confirmed by cost before running, same `confirm_spend()`/
  `pricing.json` machinery every other batch already uses) - opt-in via Compose's "Refine until
  real" button, never automatic, since every retry is a real paid generation. Every attempt is
  logged through `history.append()`'s new optional `note` param (purely additive - every existing
  call site is unaffected) so a refine-loop attempt is traceable in the outcome log later.
- **`RefineTask` (`ui/workers.py`) runs on its own small `QThreadPool`, not `MainWindow.pool`
  (`GenerationPool`).** The refine loop is one call that can take several minutes and makes its
  own decisions about whether to submit another generation - the opposite of `GenerationPool`'s
  job shape (many independent single-image jobs dispatched at once). This is the same reasoning
  Brief/Compose's autofill/upgrade `LlmTask` calls already follow, each on their own local
  `QThreadPool` rather than the per-job pool - a multi-step or long-running call gets its own
  small pool; `GenerationPool`/`VideoPool` stay for what they were built for, parallel single jobs.
- **`tools/midjourney_export.py` is a text-only reformat, not a new provider.** Midjourney has no
  official public API - every third-party service that automates it puppets the Discord bot,
  against Midjourney's own terms. `to_midjourney()` takes an already-built, already-`realism_lint`-
  passed prompt and appends Midjourney's own parameter syntax (`--ar` from `spec["aspect"]`,
  `--style raw --stylize 50` as a photoreal-leaning default, `--no <terms>` translated from
  `prompt_bank.json`'s own sentence-form negatives, `--v 6.1`) for the user to paste into
  Midjourney themselves - the same spirit as Cats' "Copy sound cue" button. It deliberately does
  NOT strip the negatives/aspect-ratio prose `compose()` already appended to the prompt before
  adding the MJ-native versions: `prompt` is natural-language text, not structured data, and
  trimming the tail of an already-assembled sentence to remove what looks redundant is exactly the
  fragile text-surgery this project avoids elsewhere (see `AiSuggestionBadge`'s hardcoded-string
  lesson, above). Seeing the same instruction twice - once as prose, once as a native parameter -
  is redundant, not wrong. A reference image gets a plain-text note naming the file to attach by
  hand in Discord, never an automated `--cref`/`--sref` URL, since that would need hosting the
  image somewhere - out of scope for a text-only export.
- **A GUI suite that loads "whichever character is first in the library" depends on the user's
  live data, and it can silently HANG, not just fail.** `smoke_gui.py` and `test_lighting.py`
  both did `library.setCurrentRow(0); load_selected()` to get a base spec - fine while the
  library was empty, but the moment a real saved character exists whose `shot_custom` names no
  capture device (a legitimate 7/8, per the `pick`-precedence rule above), `ComposeView.
  request_generate()`'s `confirm_if_failing()` pops a real `QMessageBox.question()` with nobody
  offscreen to click it. That is a genuine hang (confirmed: ~14 minutes of wall time against
  1.7s of CPU time, no open sockets - not a slow computation, a blocked wait), not merely a
  wrong score - and it was sitting latent the whole time this project had an empty character
  library, surfaced only once the user had one real saved character. Fixed both suites to
  `editor.load_spec({"subject": "...", "seed": 0})` a fixed spec instead (the same "a test must
  never depend on the user's live data" rule as everywhere else), and `smoke_gui.py` additionally
  monkeypatches `QMessageBox.question` to auto-answer, belt-and-braces, so a future spec that
  happens to score below 8/8 fails a check instead of hanging the whole suite.
- **`tests/test_layout.py`'s overlap/spill scans used to be blind inside a nested layout added
  via `addLayout()`.** They walked `QWidget.layout()`'s direct items only - a widget added through
  a layout-inside-a-layout (`right_card.body.addLayout(buttons_col)`, `buttons_col.addWidget(...)`)
  was invisible, because `buttons_col` itself is never a `QWidget` `findChildren()` can reach.
  Real consequence, not a theoretical one: cramming a 4th button into Compose's result column this
  way left all four **genuinely overlapping on screen** (confirmed directly with the exact
  `QRect.intersects()` call the scan itself uses) while `test_layout.py` reported zero overlaps.
  **Now actually closed**, not just documented: `layout_overlaps()`/`overflowing()` use a shared
  `leaf_widgets()` helper that recurses through `item.layout()` (an `addLayout()` nesting stays in
  the same widget's coordinate space, so geometry is still directly comparable) and only stops at
  a real `item.widget()` - which `findChildren()` will visit separately as its own parent anyway.
  Re-running the improved gate immediately surfaced a second, real, pre-existing overlap it had
  never been able to see: Videos' Motion tab `prompt_card` at the 1100x700 floor, where
  `form_scroll`'s own 220px minimum plus the four rows and cost note after it demanded more height
  than the card had, and a `QVBoxLayout` forced smaller than its own minimum does not shrink - it
  lets later rows draw on top of earlier ones. Fixed the same way as the Compose case: everything
  in `prompt_card` below the two title labels now scrolls as one `QScrollArea` unit instead.
- **`tests/test_layout.py` never checked a `QPushButton`'s own width against its text.**
  `clipped_labels()` only ever covered `QLabel`; a button has zero shrink tolerance
  (`minimumSizeHint() == sizeHint()` for `QPushButton`), so anything narrower than its sizeHint
  silently elides or clips the label with no error anywhere. Added `clipped_buttons()`, the same
  shape as `clipped_labels()`, wired into the same per-size/theme sweep. It immediately found real,
  pre-existing elision in six different rows across the app at the 1100x700 floor (some persisting
  even at the 1440x900 default) - "Reshuffle"/"Copy" and "Save character"/"Rename"/"Delete" in
  Compose, "Build prompts"/"Generate all"/"Pick as winner" in Variants, "Draft the copy with AI" in
  Ads, "Auto-fill the whole story" and "Generate every scene" in Cats - all invisible to every
  other check because nothing overlapped and nothing was too narrow, a button just silently drew
  less text than it was told to. Fixed per-case: Ads/Cats' single-button-plus-badge cards got a
  self-healing `setMinimumWidth(max(<old guess>, button.sizeHint().width() + badge.sizeHint().width()
  + spacing + 2*CARD_PADDING + slack))`, the same pattern `ads.py`'s own caption-width floor already
  used; Variants' seven-widget `controls` row split into a settings row (mode/count) and an actions
  row; Compose's `controls` row (Form/combo/Reshuffle/Copy) and its library card's button rows
  (Load/Save, New/Rename/Delete) don't have that kind of slack to spend - they sit inside a
  `QSplitter` whose per-pane floors already sum to the window's own minimum width - so those went
  vertical instead (each button on its own line, or paired only where the pair's combined sizeHint
  actually fits), which then cost height instead of width and had to be balanced against
  `library_card`'s own tight vertical budget (New+Rename share a row, only Delete gets its own, to
  keep the added height inside what the card already had).
- **A resizable `QScrollArea` never shrinks its content below that content's own minimum size -
  unlike a plain layout, which will squeeze content smaller and let it overlap instead, a
  scroll area just clips silently, and with the horizontal scrollbar off that clipping is
  invisible.** Found by actually looking at real screenshots of the Motion tab (offscreen Qt
  renders no text, but box geometry is still visible) after the `below_title_scroll` fix above:
  the five-field form plus four action rows plus cost note wanted 705px and the column's own
  `QScrollArea` viewport was 407px - 298px of the form's OWN fields (Shot type, Subject, Action,
  Style, Camera movement) were silently cut off the right edge with no scrollbar to reach them,
  every time, on every launch, at the declared minimum window size. Root cause: `actions`,
  `audio_row`, `still_row` and `options` each paired a big non-shrinking button
  (`apply_button` 372px, `copy_cue_button`, `choose_still_button`/`clear_still_button`,
  `generate_button` 279px - `QPushButton.minimumSizeHint() == sizeHint()`, zero give) with other
  controls in one row, and the row's true minimum (not just its sizeHint) exceeded the viewport.
  Fixed by splitting each of those four rows in two - the big button gets its own row, the
  shrinkable controls (badges, combos, the flexible `audio_cues_field`) share the other - which
  dropped the content's real minimum from 705px to 407px, an exact fit. Also switched
  `below_title_scroll`'s horizontal scrollbar from `AlwaysOff` to `AsNeeded` as a safety net: if a
  future row regresses this, a scrollbar appears rather than silently clipping a field again.
  Lesson for review, not just this file: an "all green" `test_layout.py` run is necessary but was
  not sufficient here - it checks widget-level geometry, not whether a `QScrollArea`'s chosen
  content is actually the size the viewport can show. A quick real screenshot of anything wrapped
  in a new scroll area is worth taking before calling a layout fix done.
- **The offscreen Qt platform used for every test in this project has an EMPTY font database -
  zero families, not a substitute font.** `QFontDatabase.families()` returns `[]` under
  `QT_QPA_PLATFORM=offscreen`; every `sizeHint()` measured that way (which is most of the button-
  width work two bullets up) comes from Qt's built-in synthetic fallback, which gave `'W'` and
  `'i'` the identical 13px advance width - nothing like the real, installed "Inter" font
  (`exactMatch: True` under the native `windows` platform) this app actually renders with, which
  measured the same strings meaningfully narrower. Confirmed directly: re-running the native
  platform (no `QT_QPA_PLATFORM` override at all - this machine is real Windows, not a headless
  CI box) against the exact buttons flagged in a user screenshot showed them fitting comfortably
  (best case 462px available against a 161px need), meaning the pixel-level width numbers this
  session computed offscreen do not reflect the real font at all, only the RELATIVE reasoning
  ("put the big non-shrinking button on its own row") - which still holds, since that conclusion
  doesn't depend on exact character widths. **Not fixed** - no attempt was made to give the
  offscreen platform a real font database in this pass; take offscreen-measured pixel widths as a
  directional signal only, and prefer a native-platform (or real-screenshot) check before trusting
  an exact number from `sizeHint()` in this environment.
- **Every GUI test that builds a `MainWindow` was reading AND WRITING the user's real, live
  `QSettings` - provider, model, theme, form_mode, learned, and the saved window geometry -
  through the entire history of this project, in all nine suites that construct one.**
  `MainWindow.__init__` opened `QSettings("AI Video Studio", "Studio")` unconditionally; nothing
  redirected it, unlike every other piece of live state this project is careful about
  (`AIVS_ENV_FILE`, `AIVS_HISTORY_FILE`, `AIVS_PRICING_FILE`, `assets.CHARACTERS_DIR`). Confirmed
  destructively, by accident, investigating the bug below: a probe script that simulated a saved
  narrow window by writing to the SAME real `QSettings` key left the user's actual saved geometry
  erased once removed again. Fixed by a new `AIVS_SETTINGS_APP` env var (`ui/main_window.py`'s
  `SETTINGS_APP` module constant, read once at import time, same shape as the other seams) - every
  suite that builds a `MainWindow` now sets it before that import, `tests/run_all.py` sets a
  central default too. **If you write a new suite that imports `ui.main_window`, set
  `AIVS_SETTINGS_APP` first** - the central default only protects suites run through
  `run_all.py`, not a standalone `python tests/whatever.py`.
- **Two suites (`test_composition.py`, `test_lighting.py`) wrote real variant-build rows straight
  into the REAL `history.jsonl` and deleted exactly those rows back out afterward - correct only
  as long as nothing crashed in between.** Neither had ever set `AIVS_HISTORY_FILE`, unlike every
  other suite that touches history; a failed `check()` partway through would have left synthetic
  8/8 rows permanently mixed into the user's real outcome log, silently biasing
  `history.weights()`. Two more (`test_autofill_gui.py`, `test_newui.py`) did the safer-looking
  backup-the-real-file-then-restore-it pattern, which has the same crash-shaped hole. All four now
  redirect to their own isolated `AIVS_HISTORY_FILE` instead, matching the pattern every other
  history-touching suite already used - a full redirect, not a backup, is the only version of this
  that survives a crash.
- **A restored window geometry can be narrower than a `setMinimumSize` already in force, and
  nothing in this codebase noticed.** `MainWindow.restore_state()` calls `self.restoreGeometry()`
  from a value `QSettings` last saved - if that was ever a size smaller than today's 1100x700 floor
  (an older build, or the window manually resized down before this session's newest content was
  added), `restoreGeometry()` hands the window back a size the constructor's own
  `setMinimumSize(1100, 700)` was supposed to rule out. Confirmed directly: writing a synthetic
  saved 900x600 geometry reproduced the exact symptom from a user's real screenshot (a Result card
  and options row cropped mid-word, on a build whose own offscreen tests all reported 0 elided
  buttons) - the app was not too narrow, the RESTORED window was. This is precisely why the
  measured pixel-width bugs above never surfaced through any test: every suite constructs a fresh
  `MainWindow` and calls `.resize()` or `.show()` at the declared floor - none of them go through
  `restore_state()`'s geometry-restoring path at all, so this class of bug is structurally
  invisible to the whole test suite. Fixed by re-asserting the floor immediately after
  `restoreGeometry()` in `restore_state()` rather than trusting it to have respected the minimum.
- **THE bug behind the cut-off buttons, and the reason every check above missed it: a resizable
  `QScrollArea` with `ScrollBarAlwaysOff` does not squeeze, wrap or scroll content that is too
  wide - it CLIPS, silently.** Compose's result card had a 188px viewport around 462px of content
  whose minimum could not shrink, so **274px of every button - frame included - was drawn off the
  right-hand edge on every launch, at every window size, in both themes**. Nothing detected it
  because nothing was wrong by any existing measure: every widget got exactly the geometry it
  asked for, nothing overlapped, no label was too narrow, no control was crushed, no button
  elided. They were simply painted outside the visible rectangle. Two causes, both fixed:
  (1) four `QComboBox`es in one row, each reporting its widest item ("(use Settings)") as its
  minimum width, pinned the content at 462px - combos now carry
  `setSizeAdjustPolicy(AdjustToMinimumContentsLengthWithIcon)` + `setMinimumContentsLength(6)` +
  a 56px floor so they can compress, and sit in a 2x2 `QGridLayout` rather than 1x4;
  (2) the result column was starved - `setSizes()` scales its arguments PROPORTIONALLY when they
  overflow the canvas, so the ratio, not `setMinimumWidth`, decided the real width (a 230px floor
  still came out ~219px). Sizes now sum near the real 838px canvas instead of 1150.
  **The rule: never `ScrollBarAlwaysOff` on a resizable QScrollArea.** All eight in this codebase
  are now `AsNeeded`; `test_layout.py`'s new `clipped_scrollareas()` check fails the build on any
  new one, and it caught three further live instances (Ads 144px, Cats 260px and 99px) the moment
  it was written.
- **Also fixed while in there:** `ImagePreview` never called `setWordWrap(True)`, so its "No image
  yet..." placeholder ran off the edge instead of reflowing; the four result-card buttons were
  stacked 1x4, which pushed the primary **Generate** button below the fold of its own scroll area
  (now 2x2); and their labels are now short (Generate/Upscale/Refine/Copy (MJ)) with the full
  description in the tooltip.
- **The Sound tab's ElevenLabs prompts now generate for real, and so does speech.**
  `tools/generate_sound.py`/`generate_speech.py`/`elevenlabs_voices.py` are a new provider, not
  a new architecture - ElevenLabs' sound-effect and TTS endpoints are simpler than Kie/
  Higgsfield/Kling's submit-then-poll shape: one synchronous POST, audio bytes straight back.
  `generate_sound.py` owns the shared transport (headers, the binary-response POST, error
  parsing, multipart encoding for voice samples) the other two import, the same relationship
  `generate_video.py` already has to `generate_image.py`. A sound-effect prompt is gated on
  `sound_lint` before a generation is spent by default (`force=True`/`--force` to override
  deliberately) - the same "score before you spend a generation" rule `realism_lint` enforces
  for images. TTS has no equivalent content gate (spoken text isn't a layered prompt); the
  safeguard there is `generate_speech.estimate_cost()`'s character/credit count, shown before
  a real call, reading `pricing.json`'s new `elevenlabs` block through `generate_video.py`'s
  own `PRICING_PATH`/`load_pricing()` rather than a second hardcoded constant.
- **The Sound Compose tab guides instead of going silently blank** (same fix as Posing's).
  `build_sound.compose()` is unchanged - a sound-effect prompt genuinely needs a source and
  an action, and Where/How alone are not one - but `SoundView.rebuild_compose()` no longer
  just clears the Result and shows a bare "0/4" when Source and Action are both empty: with
  Where or How filled it puts "Fill in Source and Action..." in `compose_advice`, and the
  output box carries a placeholder naming the four fields. Also fixed: `__init__` now calls
  `rebuild_compose()`, so the Generate button starts disabled rather than enabled-with-
  nothing-composed. Covered by `tests/test_sound_gui.py` (new - Sound had no GUI suite).
- **Voice cloning is the one place in this app's ElevenLabs integration with a real-world
  consequence for someone who isn't the user.** `elevenlabs_voices.clone_voice()` refuses to
  run without `consented=True` - enforced by the function itself, not only Sound's Voices tab
  consent checkbox, so a scripted call cannot bypass it either. The GUI's Clone button stays
  disabled until a name, at least one sample, and the checkbox are all present.
- **Real audio generation is entirely local to the view that offers it, unlike images/video.**
  Compose/Ads/Cats generation routes through `MainWindow` because it needs shared provider/
  spec/credits state; a sound effect or a spoken line needs none of that, so `SoundView`,
  `AdsView` and `CatsView` each own a small `QThreadPool` and call `SoundTask`/`SpeechTask`/
  `VoiceListTask`/`VoiceCloneTask` (`ui/workers.py`) directly - no new `MainWindow` wiring was
  needed for this feature at all. Settings gained its own small pool for the same reason
  (`VoiceListTask`/`VoiceDeleteTask`, managing cloned voices).
- **Adding real rows to Sound's Compose/Scenes tabs immediately reproduced the QScrollArea-
  clipping bug this project had already found and fixed once** (see the "THE bug behind the
  cut-off buttons" entry above) - neither tab had ever been wrapped in a `QScrollArea` at all,
  so they had zero slack the moment a Generate/Play/Open-folder row was added, and
  `clipped_scrollareas()` didn't catch it because there was no scroll area yet to be wrong
  about; the failure showed up as plain overlap and crush instead. Fixed by wrapping all three
  Sound tabs' content in `_scrolled()` (`AsNeeded`, matching Settings' own established pattern)
  rather than trusting a page to keep fitting forever just because it fit today. Ads' new
  per-beat voiceover control hit the *other* half of that same lesson from a different angle:
  the Storyboard tab's `gate` card had zero spare height at the 1100x700 floor already, so even
  one new fixed-height row crushed `identity_note` and the gate's own detail text - fixed by
  sharing the existing Generate button's row instead of adding a new one, not by finding more
  space. **The general lesson, restated**: a card that passes `test_layout.py` today is not
  proof it has slack for tomorrow's row - run the gate again after every addition, not just
  once at the end.
- **The application mark was redesigned onto the app's own real brand gradient, not a second
  invented palette.** `make_icons.py`'s `APP_MARK` used a mono-blue pair (#38BDF8 -> #0EA5E9)
  that matched nothing else in the app; `tokens.py`'s `primary_gradient` (#38BDF8 -> #8B5CF6,
  the exact pair reserved for one CTA per view and the credits/busy badge) is the app's actual
  signature look, and the outermost brand mark is the one place that belongs at full strength.
  The proven aperture-ring/play-triangle geometry (documented trig, reads down to 16px) is
  untouched - only its colouring and surroundings changed: a glass-highlight radial gradient,
  a soft bottom vignette for depth, a thin decorative inner ring, and a subtle gradient on the
  play triangle itself instead of flat ink. `tools/make_exe_icon.py` (new) rasterizes it into
  `assets/icons/app.ico` for the Windows build - six sizes rendered separately from the vector
  (a single downscaled 256px frame turns to mush at 16px), hand-packed into the ICO container
  rather than trusting Pillow's `sizes=`/`append_images=` ICO writer, which silently kept only
  the first frame when this was tried the straightforward way - confirmed by parsing the file's
  own directory table afterward, not by assuming the call worked.
- **`AIVideoStudio.spec` now points `EXE()` at that `.ico`**, and doing so surfaced a real,
  previously-latent packaging gap: `tools/` ships as unanalysed data (see the header comment),
  so a stdlib module imported ONLY from inside `tools/` - never from anything `ui/`/`gui.py`
  itself imports - is invisible to PyInstaller's static analysis and silently missing from the
  frozen build. `uuid` (used only by `generate_sound.py`'s multipart boundary) was exactly that
  case; the built .exe raised `ModuleNotFoundError` on the very first view that imports the
  ElevenLabs tools, found by actually launching the built .exe, not by reading the spec. Fixed
  with an explicit `hiddenimports = ["uuid"]`. If a future `tools/*.py` file imports a stdlib
  module nothing else in the project already uses, add it here too rather than assuming
  PyInstaller's analysis will find it - it structurally cannot, by this spec's own design.
- **`history.weights()` is a real bandit now (UCB1), not a shrunk average.** The exploit half
  is the original shrinkage estimate, unchanged; a new explore half
  (`EXPLORATION_C * sqrt(log(layer_total + 2) / (n + 1))`, scored per realism layer since
  `build_prompt.pick()` draws each layer as its own independent competition) is added on top,
  largest for a term with few or no ratings and shrinking as it accumulates them. Before this,
  a term that got exactly one great rating stayed permanently outweighed by a mediocre term
  with twenty ratings, and a term nobody had ever picked sat at flat neutral forever with no
  mechanism that could ever prefer it - `weights()` used to only emit entries for terms that
  already had at least one rating, so an untried term fell through to `pick()`'s neutral-1.0
  fallback with no way to rise above it. The candidate set is now the FULL bank vocabulary per
  layer (`bank["layers"][name]["terms"]`, read via the new `load_prompt_bank()`), not only
  previously-rated terms - that is the change that makes exploration real, not cosmetic.
  Signature is backward compatible (`weights(entries=None, bank=None)`); all three real call
  sites (`ui/views/compose.py`, `ui/main_window.py`, `build_prompt.py`'s `--learned` CLI)
  needed zero changes. **`EXPLORATION_C` is 0.08, not a rounder-looking 0.4** - a first attempt
  at 0.4 passed every check except one: the exploit half is bounded (a perfect 5-star mean
  asymptotes to 1.667, so the whole meaningful spread is under 0.7), but the bonus grows with
  `sqrt(log(layer_total))`, which is unbounded and grows forever however slowly - past roughly
  14 total ratings in one layer, 0.4 let an UNTRIED term permanently outrank even a perfectly-
  rated, heavily-confirmed one, because the bonus alone already exceeded the entire exploit
  range. Caught by `tests/test_history.py` (new), not by reasoning about the formula on paper -
  the same lesson as everywhere else in this file about checking a claim rather than assuming
  it. That suite also locks down the one claim that is not obvious from reading the formula:
  with zero ratings anywhere, every term in a layer gets an identical bonus, which is
  mathematically the same as `build_prompt.pick()`'s Efraimidis-Spirakis weighted sampling
  degenerating to plain uniform - checked with 20,000 trials against a tolerance, not assumed.
- **Lighting is now a real photographic taxonomy, its own nav section, not a single flat
  combo.** `tools/lighting_bank.json` follows `composition_guides`' own established shape
  (opt-in, `label`/`phrase`/`note`, jargon paired with what it does to the frame): 8 portrait
  directions (Rembrandt, split, loop, butterfly, ...), hard/soft quality, 10 natural/artificial
  sources, 8 named setups, and 7 physically-grounded `realism_techniques` (catchlights, colour-
  temperature consistency, motivated sources, falloff, subsurface translucency, specularity,
  fill ratio). Two paths to a phrase: a `setup` is a pre-vetted, hand-written recipe that can
  never contradict itself; direction + quality + source composed independently is the deep path
  and IS checked against a `conflicts` list (hard light from an overcast sky, for instance) -
  warned, never silently composed. `realism_techniques` stack additively on either path. The
  result lands in `spec["overrides"]["lighting"]` - the exact slot `ui/spec_editor.py`'s
  existing lighting combo already writes to (`SpecEditor.set_lighting_override()`, new), so
  nothing about how Compose consumes an override changed. Compose's own combo stays as the
  fast/simple path - a new "Open Lighting section →" link sits next to it, the same
  relationship Videos' standalone Audio Cue field already has to the full Sound section.
- **Every one of `lighting_bank.json`'s phrases needed a detection keyword, checked, not
  assumed.** The same rule composition guides already established: a phrase `build_lighting.py`
  can generate but `realism_lint.py` cannot detect would silently fail the 8/8 gate the moment
  someone picked it. `tests/test_lighting_bank.py`'s own audit (systematic, the same shape used
  once already for the original 8 layers) found 31 of 31 new phrases undetectable on the first
  pass - fixed by extending `DETECT["lighting"]["keys"]`, re-run until zero gaps remained.
- **A hash-lock test can itself be wrong, and this one was, on a Windows checkout specifically.**
  `tests/test_story.py`'s `HASHES` dict guards `prompt_bank.json`/`realism_lint.py`/
  `motion_bank.json` against being silently loosened. Adding the Lighting section's DETECT keys
  correctly bumped one entry - but investigating the *other* two (`motion_bank.json` failing
  with no diff anywhere, `prompt_bank.json` failing the moment the fix touched it) found the
  real bug: `core.autocrlf=true` converts every text file to CRLF on checkout, which changes a
  SHA-256 of the raw bytes on every single line without changing one character of content. One
  of the three recorded hashes had even been copied from a CRLF-mangled disk read in the first
  place, not the real committed content. Fixed once, at the source: the check now normalises
  `\r\n` -> `\n` before hashing, confirmed against `git show HEAD:<path>` directly rather than
  assumed - not three separate one-off "just update the number" edits that would have left the
  same platform-dependent fragility for the next person who touches any of these three files.
- **Composition got the same treatment as Lighting, but reuses rather than duplicates.**
  `tools/composition_bank.json` holds only `techniques` (negative space, lead room, depth
  layering, frame within a frame, visual balance, scale contrast, pattern and repetition) - the
  seven named geometries themselves stay put in `prompt_bank.json`'s `composition_guides` and
  are read via `build_prompt.guides()`, not copied into a second bank that would need to be kept
  in sync forever. `build_composition.compose_composition()` mirrors `compose_lighting()`'s
  `(phrase, warnings)` shape for interface parity, but `warnings` is always `[]`: unlike
  lighting's quality x source, the seven guides are already mutually exclusive by construction
  (one combo, one pin) and none of the seven techniques fights a guide or each other, so there
  is no `conflicts` list. Custom typed text always beats a picked guide - the same precedence
  `apply_composition_guide()` already enforces - so `SpecEditor.set_composition_override()`
  (new) can just write the composed phrase in as custom text; no changes to `build_prompt.py`
  were needed at all. `tests/test_composition_bank.py` (new) audits the seven technique phrases
  against `realism_lint.py` and leaves `tests/test_composition.py` (the pre-existing combo/pin
  suite) untouched.
- **Dynamic Symmetry is the eighth composition GUIDE, not a technique.** It is a framing
  geometry (Hambidge: the frame's diagonal plus a reciprocal crossing it at 90°), the same kind
  of thing as the other seven, so it lives in `prompt_bank.json`'s `composition_guides`
  (version 12 -> 13) and every surface that reads `build_prompt.guides()` picked it up with no UI
  code. Two phrasing decisions to keep: (1) it is told apart from Harmonic Armature, which uses
  the same lines, by what it asks for - armature puts the subject ON a crossing point, dynamic
  symmetry ALIGNS lines and gestures with the diagonal; (2) the word "symmetry" pulls an image
  model toward a centred, mirrored frame, the opposite of the technique, so the phrase ends
  "energetic rather than mirrored or centred" and `tests/test_composition.py` asserts that
  clause stays. `realism_lint.py` gained a `"dynamic symmetry"` composition key (a pinned guide
  that the gate cannot see could zero the layer), and `tests/test_story.py`'s pins for both files
  were re-taken with a comment.
- **Three improvements mined from a real photography-course library, not guessed.** Surveyed
  `E:\Library Of Courses\Photography` (~2,600 files) for material that could extend the
  app's prompt vocabulary the way earlier lessons became `prompt_bank.json`/
  `lighting_bank.json`/`composition_bank.json`. Most of it is video/captions with nothing
  extractable, but two sources were genuine cheat-sheet material: Lindsay Adler's *Master
  Studio Lighting* and Dani Diamond's *Retouching Notes*/Earth Oliver's *Advanced Texture
  Cleanup* (read as skin-realism LANGUAGE, not retouching steps - this app only ever writes
  prompts, it never touches pixels). Three pieces shipped:
  1. **A new Posing bank/section** (`tools/posing_bank.json`/`build_posing.py`,
     `ui/views/posing.py`) - the single clearest outright gap: nothing in the app addressed
     body/hand/gaze posing before this, "action" was a bare free-text field. 21 named poses
     across 5 categories (portrait/editorial/headshot/group/candid) plus 5 opt-in posing-
     realism techniques. Deliberately **not** one of `realism_lint.py`'s 8 gated layers -
     posing is descriptive spec content like wardrobe/setting/mood, so it carries no
     `DETECT` requirement; `tests/test_posing_bank.py` instead confirms a posed action field
     never interferes with the 8 layers that ARE gated. Apply to Compose writes into the
     Subject tab's Posing field (`SpecEditor.set_posing_override()` - a plain
     `QLineEdit`, already wired to `changed`, so `setText()` alone was enough, no new signal
     plumbing needed). **A base pose is recommended but NOT required** (fixed after a repeat
     of the "no prompt below" report): `compose_posing()` composes from any of pose /
     technique / free-text phrase and only raises `PosingError` on a wholly empty request;
     `PosingView` then shows an `EMPTY_HINT` line (not a blank label) and tracks real-vs-hint
     state in `self._has_result` so Copy/Apply don't fire on the hint text. The combo's
     empty label is `"(none - or type your own pose here)"` - the old `"...below"` wording
     sent users to type their pose into the technique field directly beneath it.
  2. **Deepened the existing Lighting bank**, not a new section - four more named setups
     (Clam shell, Beauty box, Checkerboard, Old Hollywood hard light) and a light-shaping
     modifier vocabulary (silver/white reflector, direct/diffused/bounced) folded into the
     SAME `realism_techniques` dict/`techniques_` stacking mechanism rather than a second
     parallel one, since mechanically they behave identically to the existing realism cues.
  3. **Four new `layers.texture.terms`** in `prompt_bank.json` (version 6 -> 7) translating
     retouching-realism language into how a photo should LOOK ("natural skin texture
     retained under light retouching", "authentic pores visible, not airbrushed smooth", ...)
     - all four confirmed detectable by the EXISTING `DETECT["texture"]["keys"]`, so this
     piece needed zero `realism_lint.py` changes.

  Piece 1's `PosingView`/`build_posing.compose_posing()` mirror Composition's shape (one base
  value + stacked techniques, no deep-path triplet) but take Lighting's newest pattern for
  the base picker itself: a single editable combo, pick-or-type, resolved through a
  `_resolved()` static method that is a direct copy of `LightingView`'s own (which itself
  mirrors `SpecEditor._listed()`) - not a fourth reimplementation of the same 15 lines.
- **Four more pieces mined from the AI Video Bootcamp's own camera/framing/color-grading
  lesson documents.** Cross-checked six lesson PDFs against what was already built - most of
  the depth/atmosphere/lead-room/lighting-source material overlapped what Composition/Lighting
  already captured earlier this session (good confirmation, not a gap). Four real pieces
  shipped:
  1. **Color Grading section** (`tools/color_bank.json`/`build_color.py`,
     `ui/views/color_grading.py`) - 12 named moods and 10 film-look references from the
     course's own Mood → Color → Prompt cheat sheet. `spec["overrides"]` already worked
     generically for ANY layer name (confirmed by reading `select_layers()` before building
     anything, not assumed) - `colour` needed zero `build_prompt.py` changes, just a new
     editable "Colour grade" combo on `ui/spec_editor.py`'s Scene tab mirroring the Lighting
     combo exactly. First bank whose source leans stylised (neon cyberpunk, hot pink Barbie)
     rather than restrained - `tests/test_color_bank.py` checks every phrase against
     `banned`/`warn`, not just detectability, because that distinction actually matters here.
  2. **An `atmosphere` technique** added to the existing Composition bank (haze/fog separating
     depth layers, distinct from the already-shipped `depth-layering` technique, which names
     the three LAYERS rather than the air between them) - extension, not a new section.
  3. **Four real named cameras** (ARRI Alexa, Sony Venice 2, RED V-Raptor, Hasselblad) added to
     `layers.camera.terms`, and a `material-response` technique added to Lighting's
     `realism_techniques` (distinct from `specularity`, which is skin-specific - this one is
     every OTHER surface reacting to light in its own physically correct way).
  4. **Camera Angle section** (`tools/camera_angle_bank.json`/`build_camera_angle.py`,
     `ui/views/camera_angle.py`) - three independent axes (vertical/side/size) from the Camera
     Language transcript, no `conflicts` and no `techniques` dict (the three axes fully
     describe camera position on their own - forcing either would have been padding).
     Apply to Compose writes the result as typed custom SHOT text, reusing
     `apply_custom_shot()`'s existing precedence - **documented honestly, not hidden**: a
     pure angle phrase with no camera vocabulary can legitimately score the camera check 0/8,
     the same tradeoff typing any custom shot already has, worded the same way
     `ui/spec_editor.py`'s own shot tooltip already does. `tests/test_camera_angle_bank.py`
     locks this in as an intentional, asserted behaviour rather than an oversight.
- **A 5th Brief tab, "Analyze a photo," is the missing case `critique_image` structurally
  cannot cover.** `critique_image(bank, prompt, image_path)` requires an already-known prompt
  ("this image was generated from X, what's wrong with it") - exactly what an arbitrary
  uploaded photo, not necessarily made by this app at all, doesn't have. `brief.
  analyze_uploaded_image(bank, image_path, ask=None)` (new) is `spec_from_idea()`'s shape with
  an image standing in for the idea text: one vision call, a whitelisted spec suggestion
  (`SPEC_KEYS` - the exact whitelist `autofill_spec`/`spec_from_idea` already enforce, so a
  reply can no more smuggle in `seed`/`reference`/`lock_identity` here than anywhere else) plus
  a free-text `analysis` (commentary, not spec data, so it is returned as-is rather than
  whitelisted). **The model's read of the photo is never the final prompt** - it is recomposed
  through `build_prompt.compose()` and rescored through `realism_lint.lint()` exactly like
  every other AI-suggested spec in this project, and can legitimately come back below 8/8 if
  the photo doesn't map cleanly onto all 8 layers - that is the gate working, not a bug to
  paper over. Apply reuses the existing `spec_suggested` signal/`apply_suggested_spec` path
  verbatim - no new `MainWindow` wiring was needed for this feature at all.
- **Not NEAT.** Asked what else could improve the app, "maybe NEAT?" (neuroevolution of network
  topology) doesn't fit anything here - there is no live control/simulation loop to evolve a
  policy against. The UCB upgrade above is the actual real version of that instinct: a bandit
  algorithm, applied to the one place this project already had an explore/exploit problem.
- **Lighting's deep path and both sections' technique lists became genuinely customizable, not
  just a closed dropdown.** `direction_combo`/`quality_combo`/`source_combo` in
  `ui/views/lighting.py` are now editable (`QComboBox(editable=True)`, matching
  `ui/spec_editor.py`'s own shot/lighting/composition combos) - a bank entry is a tested
  starting point, not a closed world. `build_lighting._resolve()` (new) accepts EITHER a bank
  key OR literal typed text for direction/quality/source; `setup` and a named `--technique`
  stay strict-key, since those are complete recipes to pick from, not slots to customize. The
  `conflicts` check now only fires when both quality and source resolve to recognised bank keys
  - custom text for either one was never in that table to begin with, so it's skipped rather
  than guessed at. Both Lighting and Composition also gained a `technique_custom` free-text
  field alongside their checkbox lists, so a realism cue isn't limited to the seven predefined
  ones either. `LightingView._resolved()` mirrors `SpecEditor._listed()`'s exact logic for
  resolving a typed/picked combo value to its underlying key.
- **The Advisor is the one AI feature in this project that is a running conversation, not a
  one-shot brief - and the validation gate still holds without exception.**
  `ask_llm.ask()`/`build_request()` gained an optional `history` param (a list of prior
  `{role, content}` turns, threaded in between the system message and the new one; every call
  that omits it - every existing caller - gets today's exact single-shot request, unchanged).
  `tools/advisor.py`'s `advisor_brief()` is built live from `prompt_bank.json`'s 8 layers, the
  composition guides and all five technique banks (`_technique_banks_summary()`, the same
  reasoning `brief._bank_vocabulary()` already applies to `prompt_bank.json`), so a bank edit
  is reflected in the very next reply, never re-typed by hand. A reply may propose a ready spec
  by ending with a fenced ` ```spec {...} ``` ` block - `extract_spec_block()` looks
  specifically for that fence rather than scanning the whole reply for any `{...}` the way
  `ask_llm.extract_json()` does, because a conversational answer routinely has other braces or
  prose around a spec block. The fenced block is whitelisted, recomposed and relinted through
  the exact same tail `brief.autofill_spec()`/`spec_from_idea()` already use (`seed`,
  `reference`, `lock_identity` and `overrides` are never accepted, no matter how the model
  phrases the request) - written fresh in `advisor.py` rather than refactored out of `brief.py`,
  the same small, view-local duplication every `_scrolled()` helper in `ui/views/` already
  tolerates. The advisor itself never states a realism score in prose - it doesn't compute one;
  `_context_note()` folds the CURRENT composed prompt's real, `realism_lint`-computed score into
  every turn automatically (via the same `() -> (prompt, image)` context callable `BriefView`
  already used, zero new plumbing), so advice is grounded in what the user actually has rather
  than generic. An attached photo (`ui/views/advisor.py`'s "Choose photo…", reusing
  `ImagePreview` and the same vision path `brief.critique_image()` already uses) is scoped to
  its own turn only - `history` itself stays text-only, so a long conversation never silently
  re-uploads every earlier photo on every later turn.
- **A conversation is inherently ordered, and disabling only the Send button did not stop a
  second turn starting before the first one answered.** `AdvisorView.send()` disabled
  `send_button` but not the `QLineEdit` itself, and `returnPressed` isn't gated by a button's
  enabled state - pressing Enter twice quickly (before the first reply landed) dispatched two
  turns at once, both reading and writing one shared `self._last_sent` attribute. Reproduced
  directly: send "A", then "B" before "A" answers, and the transcript's history ended up
  `[{"user": "B"}, {"assistant": "reply to A"}, {"user": "B"}, {"assistant": "reply to B"}]` -
  a reply logged against the wrong user turn, and that corrupted pairing is exactly what gets
  threaded into every later turn's context. Fixed two ways at once: a `self._busy` flag refuses
  a second `send()` outright (checked first, before even reading the input box) and the pool
  itself is capped at 1 concurrent turn (`BriefView`'s 4 independent one-shot tabs correctly
  run 2; a single ordered transcript should never run more than 1) - and the sent message is
  now bound into the `finished` callback via the lambda's own default argument rather than read
  back from shared instance state at completion time, so correctness does not depend on the
  guard alone. `tests/test_advisor_gui.py` (new) reproduces the exact scenario against a real
  `MainWindow` and the mock API, confirmed to fail against the pre-fix code with
  `AttributeError: 'AdvisorView' object has no attribute '_busy'` before passing after the fix -
  found by testing the actual signal-driven flow, not by reasoning about `advisor.chat()` in
  isolation (which takes `history` as an explicit argument and had nothing to race).
- **An editable `QComboBox`'s `currentData()` goes stale the moment the user types over a
  picked item, and a `currentData()`-first fast path trusted it anyway - found live in four
  places at once, not just where it was reported.** Reported as "Posing: custom text shows no
  prompt." Root cause: picking an item moves `currentIndex` (so `currentData()` becomes that
  item's key), but typing over the text afterward does NOT move it back - Qt leaves
  `currentIndex` exactly where it was. `PosingView._resolved()` and the byte-identical
  `LightingView._resolved()` both did `data = combo.currentData(); if data: return data` before
  a text-based fallback, so once any entry had ever been picked, that stale key was returned
  forever after, silently freezing the composed phrase on the OLD choice no matter what was
  typed next - no exception, no `PosingError`, just a wrong answer that looks like nothing is
  happening. **The same pattern was in `ui/spec_editor.py` too** - `shot_value()`
  (`self.shot.currentData() or self._listed(...)`) and `composition_guide()`, the CORE Compose
  form's Shot and Composition fields. Verified directly: pick the "portrait" preset, retype a
  completely different shot over it, and `shot_value()` kept returning `"portrait"` - the typed
  text was silently discarded and the OLD preset (with its own lens and composition language)
  kept being sent to `compose()`. `SpecEditor._listed()` itself, which both call sites already
  delegated to on the fallback path, was always correct - it resolves purely from
  `combo.findText()`/`findData()` against the CURRENT text, never touching `currentIndex()` at
  all; it was the `currentData()` shortcut wrapped around it that reintroduced the staleness.
  Fixed the same way in all four places: drop the `currentData()` fast path entirely, resolve
  only from the current text. Every other editable combo checked (`self.lighting`,
  `self.colour`, `self.aspect`) reads `currentText()` directly with no key-resolution step, so
  it was never exposed to this; every section that pairs a non-editable combo with a *separate*
  `custom_field` (`ColorGradingView`, `CameraAngleView`, `CompositionView`'s own guide combo) is
  structurally immune to this whole class of bug, which is the shape to reach for, not an
  editable combo doing double duty. `tests/test_combo_resolve.py` (new) reproduces the exact
  pick-then-retype scenario in all four locations - confirmed to fail with 8 FAILs against the
  pre-fix code before passing after.
- **The Advisor autofills every technique section now, not just the core spec - one click,
  everything at once.** The same fenced `\`\`\`spec\`\`\`` block gains one more optional key,
  `"sections"`, whose schema matches each section's own real `compose_X()` parameters exactly
  (`lighting`: `setup` or `direction`+`quality`+`source`; `composition`: `guide`; `color`:
  `mood` or `film_look`; `posing`: `pose`; `camera_angle`: any subset of
  `vertical`/`side`/`size` - all five accept an optional `techniques` list too).
  `_finalize_sections()` validates every field against that section's OWN real bank keys (never
  free text - unlike a section's own "Apply to Compose", which is the user's explicit deep-path
  override, a *suggested* pick has to stay inside vocabulary the model was actually shown) and
  composes it through that section's OWN `compose_X()`, so a suggested phrase is byte-identical
  to what that section's own button would have produced from the same pick - nothing here
  writes phrasing of its own. A section that doesn't validate, or whose own composer refuses
  the picks, is simply left out of the reply rather than failing the turn, the same treatment
  an invalid `shot` already gets. **`shot` and `sections.camera_angle` collide on purpose** -
  both write the Shot field, and a bare angle phrase names no camera at all, so proposing both
  in one reply used to cost the camera realism layer and drop an otherwise-8/8 full autofill to
  7/8; now the shot preset wins and the angle pick is silently dropped, confirmed directly (a
  full autofill with a preset scores 8/8; the same autofill with no preset correctly still
  applies the angle at the honest 7/8 cost). `AdvisorView`'s one Apply button fires both
  `spec_suggested` and the new `sections_suggested(dict)` together -
  `MainWindow.apply_advisor_sections()` routes each phrase to the exact same
  `SpecEditor.set_X_override()` each section's own Apply button already calls, via a small
  `ADVISOR_SECTION_SETTERS` name map (posing → `set_posing_override`, camera_angle →
  `set_shot_override` - not a 1:1 name match, since posing is descriptive spec content and an
  angle lands as typed custom shot text, exactly like every other section's own precedent).
- **Influencer Studio is a persona builder, not a second character-spec system.** No structured
  gender/age/hair/eye slot exists anywhere in `tools/brief.py`'s `SPEC_KEYS` or
  `build_prompt.subject_clause()` - every other section in this app that has ever needed one of
  those concepts (the course's own worked examples included) has folded it into `subject` as
  prose, so `tools/persona_bank.json`/`build_persona.py`'s job is to compose structured picks
  (name, one of 4 genders, one of 8 age ranges, any number of 10 aesthetic style tags, one of 15
  hair colours, one of 8 eye colours, plus free-text details) into exactly that: one flowing
  Subject sentence, never a new spec key. `compose_persona()` never raises - unlike a technique
  section's own composer (`LightingError`/`ColorError`/... for an over-specified pick), there is
  no invalid *combination* here, so an unrecognised key (gender, age range, hair/eye colour) is
  simply dropped and the whole thing falls back to `"a person."`, the same default
  `SpecEditor.PLACEHOLDER_SUBJECT` already uses for an empty Subject box. `SpecEditor.
  set_subject_override()` (new, the same five-line shape as the other five `set_X_override()`
  setters) writes the composed sentence into Subject wholesale, the same "typed text wins
  outright" precedence every Apply-to-Compose button already follows. The roster itself
  (`temp/resources/personas/<slug>.json`) is a parallel, lighter-weight copy of
  `ui/views/compose.py`'s own character-library CRUD shape (`reload_roster()`/`load_selected()`/
  `save_persona()`/`new_persona()`/`rename_persona()`/`delete_persona()`), in its own folder
  rather than crammed into `assets.CHARACTERS_DIR` - a persona and a full character spec are
  different JSON shapes with different lifecycles (a persona feeds *into* a character's Subject,
  it is not itself one).
- **Reference images in Influencer Studio are a mood board, never an identity lock, and no
  attractiveness/face-shape/body-shape control exists here, on purpose.** Both were decided
  in-conversation before any code was written, not discovered as bugs afterward. Up to 8 images
  (drag-and-drop - the first drag-and-drop handling anywhere in this codebase - or
  `QFileDialog.getOpenFileNames`) are stored as raw paths on the persona's own JSON and rendered
  as small thumbnails; they are never passed to `SpecEditor.set_reference()`/`lock_identity`,
  the app's actual face-lock mechanism, confirmed directly (`SpecEditor.reference()` stays `""`
  through a full build-save-load-apply cycle in `tests/test_influencer_studio_gui.py`). Every
  other structured field here describes an aesthetic or a fact (gender, age, colour, style) or
  routes to free-text prose (Additional Details) for anything else, including a face or build -
  never a slider tuned toward an idealised standard, unlike the sexualized "indistinguishable
  from real photography" content this feature was explicitly scoped away from when it was asked
  for.
- **A `QButtonGroup` with `exclusive=True` refuses to let its OWN currently-checked button be
  unchecked via `setChecked(False)` - found live building "New persona" (blank), not by reading
  Qt's docs first.** `ui/widgets.chip_row()`'s Age Range/Hair Color/Eye Color pickers each sit in
  an exclusive group (Style & Aesthetic does not - it is multi-select, no group at all); calling
  `button.setChecked(False)` on every button in the group, including the one already checked,
  looked like it should clear the selection to none, and every OTHER field in the same reset
  (name, style chips, details) correctly cleared - but the previously-checked Age/Hair/Eye chip
  stayed visibly checked, and its phrase stayed in the composed sentence, because Qt's exclusive
  `QButtonGroup` is written to always keep exactly one button checked once any button in it ever
  has been, and silently ignores a `setChecked(False)` that would leave zero checked. Fixed with
  `InfluencerStudioView._set_exclusive_selection()`: toggle the GROUP's own `setExclusive(False)`
  before clearing, restore `True` after - that is what actually lets zero be a valid state.
  `tests/test_influencer_studio_gui.py` reproduces the exact scenario (load a real persona, then
  New) as a named regression, confirmed against the pre-fix code before the fix (every OTHER
  field cleared correctly in isolation, which is exactly what made this easy to miss without
  running the real "load then New" sequence end to end).
- **The Advisor treats a pasted full prompt as a style reference by default, never a
  reproduction - and an explicit instruction still wins over that default.** Asked for
  directly: "give the advisor a prompt and it fills everything" but "uses the prompt just as
  inspiration... creates something uniquely different," with the explicit follow-up that the
  user can still say what to keep (a setting, a wardrobe piece). This needed no new code path -
  `advisor_brief()`'s `constraints` list gained one instruction telling the model that a long,
  already-detailed message (as opposed to a short idea) is a style reference: carry over vibe/
  mood/technique direction, invent a different name and different identifying physical/wardrobe/
  setting details, UNLESS the user explicitly says what to keep, which outranks the default -
  the same "an explicit choice beats a generic fill" precedence every other suggestion in this
  app already follows, and something `chat()`'s existing `history` threading already supports
  for a follow-up turn with zero changes. The five technique sections never needed this rule at
  all: `_finalize_sections()`/`_compose_section()` already only ever compose from that section's
  OWN real bank vocabulary (never the model's free phrasing), so a section suggestion structurally
  cannot echo a pasted prompt's sentences - only the free-text subject/wardrobe/setting/action/
  mood half could, which is what the new constraint (plus a new worked few-shot example -
  a pasted "Mara" cafe portrait producing an unrelated "Elena" bookshop scene, same golden-hour/
  wistful vibe, different person) actually addresses. Verified for real, not just written: the
  new example's own fenced spec block, pulled straight out of `advisor_brief()`'s text and run
  through the real `_finalize_spec()`/`_finalize_sections()` pipeline, scores a clean 8/8 with
  all 5 sections composing - `tests/test_advisor.py` locks this down as a structural regression
  check (the app-side pipeline handles this input shape correctly), which is the most that can
  be unit-tested here since nothing can assert what a live model chooses to write.
- **Assistant → Prompt Bank is the user's own prompt library, saved EXACTLY as given.** It
  replaced the Anatomy tab (built-in templates split into teaching slots), which was deleted
  on request along with `anatomy_bank.json`, `prompt_anatomy.py` and their suites. One folder
  per prompt under `temp/resources/prompt_bank/<image|video>/<title>/`: `prompt.txt`, written
  byte for byte (`newline=""`, nothing trimmed or reflowed), plus the prompt's example images
  as straight file copies with their original names. No index file. `tools/saved_prompts.py`
  is the one way in - `add --kind --title --file --image`, `attach`, `list`, `show`, `delete` -
  and the tab (`ui/views/prompt_bank.py`) calls the same functions. When the user gives a
  prompt (and its example images) for the app, save it with that tool, verbatim; never tidy
  it. Not to be confused with `tools/prompt_bank.json`, the realism vocabulary - unrelated.
  `AIVS_PROMPT_BANK_DIR` redirects the folder; `tests/test_saved_prompts.py` uses it.
- **A `Card` owns its layout: add widgets to `card.body`, never to `QVBoxLayout(card)`.**
  `ui/widgets.py`'s `Card` builds its own layout in `__init__`; Qt refuses to install a second
  one, so a widget added to that second layout is orphaned - never parented, never laid out,
  never drawn. That shipped once (a whole tab of empty rounded boxes) and no layout check caught
  it, because there was nothing inside the cards to measure. A GUI suite for a card-based view
  should assert the cards actually CONTAIN text, not merely that they exist.
- **`ui/views/cats.py`'s `base_spec()` must never assign `spec["subject"]` a truthy fallback when
  a cast can supply one.** Shipped once, caught only by hand: `base_spec()` set
  `spec["subject"] = "a cat"` whenever the Subject field was blank, and `build_story.apply_cast()`
  only fills that key when it is ABSENT or falsy - `"a cat"` is neither. So through the actual GUI,
  with the field left blank exactly as its own placeholder instructs ("left blank - the cast fills
  this in"), the whole cast mechanism was dead: every sitcom episode silently composed as a
  generic, uncast cat, and `check_pair`/`check_cast` failed on a brand-new story before a user had
  typed a word. Every test written against `build_story.compose_story()` directly missed this,
  because none of them went through `base_spec()` - the bug lived entirely in the GUI's own glue
  code. Fixed by `_cast_supplies_subject()`: the "a cat" fallback now applies only when the active
  cast has no `subject` of its own to give. `tools/build_story.py`'s CLI had the mirror-image gap -
  `--cast` and `--premise` were fully wired into `apply_cast()`/`compose_story()` but never added
  to `argparse`, so the exact command this file's own plan named as a verification step
  (`--format sitcom --cast tommy --premise ...`) could not run. Both are cautionary tales for the
  same reason: a library function tested in isolation proves nothing about the caller that actually
  reaches a user.
- **`build_pet_sound.extra_layers()`'s `who` parameter must stay `None` by default, and no caller
  should force it.** Shipped once: `who` defaulted to `"lead"` and nothing anywhere overrode it, so
  every generated vocal layer played the kitten's voice - including on `discipline` and `lecture`,
  the two beats where `story_bank.json`'s own `must_do` says the FOIL is the one acting ("one
  economical correction from the foil"; "the mother says her piece" - the caption is HER line). Ten
  phrases of foil/foil_offscreen vocabulary in `pet_sound_bank.json` were composed and never once
  reachable. Fixed with `voice_by_beat` in the bank (`discipline`/`lecture` -> `foil`, the rest ->
  `lead`) and `voice_for_beat()`, consulted only when the caller leaves `who` unset - which is what
  every real caller (the CLI, `ui/views/cats.py`) now does.
- **A story FORMAT is the extension seam - do not add a fourth pipeline.** `story_bank.json`'s
  `formats` map holds `story`, `trade` and `sitcom`, and a format may override `default_arc`,
  `default_clip`, `default_seconds`, `default_cast`, `brief`, `scene_fields`, `action_from`,
  `camera`, `checks`, `beats`, `arcs`, `capcut` and `ui`. `story_lint.checks_for()` lets a
  format's `checks` list REPLACE the default set, which is how `sitcom` runs sixteen checks
  while `story` runs thirteen and `trade` twelve. Three things that used to be hardcoded are
  now declared, because two formats fit in a boolean and three do not: the task/mishap join is
  `action_from`, the brief choice is `brief`, and which rows the Cats form shows is `ui`. Adding
  a format should be vocabulary, not branches.
- **Every TEXT-RENDERING function must read a scene's fields generically, not by hardcoded
  format branches.** `build_story.py`'s `story_script()`, `write_story()` and `edit_sheet()` all
  special-cased `scene.get("fields") == ["task", "mishap"]` for `trade` and fell through to
  `caption`/`narration` for anything else - correct while only two formats existed, but `sitcom`
  has no narration at all ("the captions carry every word" - `sitcom_brief`), so its real
  content, `lead_action`/`foil_action`, silently never appeared in the printed script, the
  written story file, or the CapCut sheet's "shows" line, even though `compose_story()` had
  already set both fields correctly on every scene. Not one test caught it: `test_sitcom.py`
  checked that the fields reached the brief and the composed spec, never that they reached the
  RENDERED text. Fixed by driving all three off each scene's own `"fields"` list (already stored
  per scene) and `action_recipe(bank, fmt)` (already existed for `compose_story()`'s own action
  join) instead of a third hardcoded branch - which, as a side effect, also fixed the SAME gap
  for the original `story` format's own `action` field, which had been silently unprinted the
  whole time too.
- **`ui/views/cats.py`'s `self.custom_motion` dict is keyed by scene INDEX, so it must be pruned
  whenever `rebuild()` can change which BEAT sits at an index - which arc, cast, trade and style
  all can.** A hand edit to a scene's video-prompt fields is deliberately meant to survive a
  `rebuild()` triggered by re-editing the script text (see `_build_motion_card_section`'s own
  "a stored hand edit has to win back over that" comment) - but nothing distinguished THAT case
  from an arc/cast switch that reshuffles the beats entirely: `"classic"`'s scene 2 is `setup`,
  `"short"`'s scene 2 is `escalation`, and an edit typed for one silently reappeared, unlabelled,
  on the other. Fixed by tagging each `custom_motion` entry with the scene's own `"key"` at the
  moment it is created, and pruning any entry whose tag no longer matches in `rebuild()` - one
  place, so every reader (`_build_motion_card_section`, `_audio_cue_overrides`,
  `generate_scene_voiceover`) is correct for free rather than needing its own check.
- **`story_bank.json` is where new vocabulary goes, because it is NOT hash-pinned.**
  `tests/test_story.py`'s `HASHES` pins `prompt_bank.json`, `realism_lint.py` and
  `motion_bank.json` only. `build_story.locked_camera`'s docstring states the precedent and it
  holds for everything added since: the sitcom format, its casts, its premises and its safety
  vocabulary all live outside those three files, so none of this session's work needed a hash
  bump. Anything that WOULD need one is a signal you are widening the shared gate.
- **Two characters ride ONE subject string; there is still no second-subject mechanism.**
  `build_prompt.subject_clause()` renders exactly one subject and one action. `trade` proved the
  workaround and `sitcom` reuses it: the subject starts with the word "two", which makes
  `story_lint.check_pair` and `build_motion.DETECTORS["second_subject"]` agree for free because
  they share a word list. Relative scale rides `spec["extra"]` as a sentence - verified to reach
  every composed prompt at 8/8. A real `subject_2` key would leak into `brief.SPEC_KEYS`, the
  Compose form, `autofill_spec` and `history.py`: several surfaces re-risked to
  buy a comma.
- **`safety_lint.py` scans authored fields ONLY, and is opt-in per format.** Two rules, both
  measured rather than assumed. (1) Pointed at a composed prompt it would fail clean photoreal
  work: `crushing` is in `camera_angle_bank.json`, `squash and stretch` in `story_bank.json`'s
  stylised style, `slap`/`smacked` in `sound_bank.json`'s own comedy examples. (2) The softener
  rule is scoped per FIELD and only to staging fields - otherwise a "soft daylight" in the
  setting vouches for an unsoftened swat in the action, and a caption is read by a viewer rather
  than executed by a model (the source brief's own punchline caption is literally "bap bap!").
  It is listed only in `sitcom`'s checks: `trade`'s own shipped mishap "one shoves the other and
  it lands flat on its back" fails the softener rule, so widening the gate to content written
  before it would make a correct linter a nuisance. `safety_lint.py --check-bank` audits the
  vocabulary against every shipped bank, per phrase, with a reviewed `audit_allow` list for the
  handful of real-but-harmless collisions ("Blade Runner" is not a knife). Stems are
  start-anchored and words are whole-word, and where an inflection drops the stem's last letter
  BOTH forms are listed - "shoving" does not contain "shove", and the shorter stem that would
  catch it also catches "shovelling wet cement". The same inflection trap bit a second stem
  later and shipped: the hazard category listed `"boiling"` itself rather than the root `"boil"`,
  so it matched only the literal word "boiling" - "the cat knocks over a pan of **boiled** water"
  and "a pot that **boils** over" both scanned clean. `tests/test_safety_lint.py` now pins all
  three inflections (`boiling`/`boiled`/`boils`), the same way it already pinned `shove`/`shoving`.
  When adding a stem, check what it looks like conjugated, not just what it looks like as written.
- **Take a bank's contents FROM the bank, never from memory.** `sound_lint` rejects the fifteen
  words in `sound_bank.json`'s `not_effects`. An earlier version of this file, and the `music`
  slot in `anatomy_bank.json`, both claimed `beat` was one of them. It is not - "chic upbeat
  lounge hip-hop beat" sails past the music gate and fails `check_event` instead, for naming an
  object rather than a sound. `tests/test_sound.py` now pins the list both ways so the next
  wrong claim fails a test instead of shipping.
- **The gate itself needs a test, and for a long time it was the only thing without one.**
  Every satellite bank had a suite auditing its phrases against `realism_lint`
  (`test_lighting_bank.py`, `test_color_bank.py`, `test_macro_insert.py`, …); the linter they
  all pointed at had none. Three holes sat in it as a result, each reproduced by running the
  tool, not by reading it: (1) `is_negated()` was wired into `find_terms()` for banned terms
  and **never into the layer loop**, so `"no bokeh, avoid film grain, no texture"` scored lens,
  grain AND texture - a full 8/8 PASS on a prompt that ruled out three layers; (2) a plain
  single-word key was anchored only at its START, so `"wear"` fired inside `"wearing"` - and
  `build_prompt.subject_clause()` writes `"wearing <wardrobe>"` into nearly every prompt this
  app composes, so the texture layer was auto-satisfied almost everywhere (the same bug also
  scored `"hazel eyes"` on the COMPOSITION layer, via `haze`); (3) one keyword was one point,
  so eight unrelated words - `"lifelike iphone aperture sunlight texture high contrast
  close-up sharp focus"` - scored 8/8 and exited 0. `tests/test_realism_lint.py` now exists and
  states each hole as the string that used to pass.
- **A density threshold is MEASURED against the builder, never copied from `pick`.**
  `prompt_bank.json` says `pick: 3` for texture, so 3 looked like the obvious requirement - but
  over 300 seeds of `compose()` the bank's own texture picks yielded only 2 distinct DETECT
  keys 16% of the time, because three chosen terms are not three distinct keys when two of them
  both match `"texture"`. A threshold of 3 would have failed this app's own output one time in
  six. `REQUIRED_HITS` is `{"core": 3, "texture": 2}`, and the comment records the measurement.
- **`realism_lint` is a HUMAN-PORTRAIT detector, and pointed at an animal it was inverted.**
  Not merely blind - it rewarded the wrong answer. Measured: a cat prompt naming guard hairs,
  vibrissae, nose leather and slit pupils scored **7/8 and FAILED**, while the app's own
  photoreal cat scene - `"realistic skin textures of a ginger tabby cat"` - **passed 8/8**, and
  deleting all four of `story_bank.json`'s fur phrases left that 8/8 *completely unchanged*
  because none of them scored anything. Meanwhile every locked scene opened with
  `LOCK_COMPACT` verbatim: *"the exact same **person** … identical face, bone structure, eye
  colour, **hairline**, **skin tone**"*, applied to a cat.
- **Species-awareness SWITCHES the gate's keys; it must never widen them.** `DETECT_BY_KIND`
  replaces the `core` and `texture` key lists for `kind="animal"` and adds `ANIMAL_BANNED`
  (`skin pores`, `hairline`, `skin tone`, `bone structure`). The human lists are byte-for-byte
  unchanged, which is the only reason bumping this file's hash pin is honest - adding fur words
  to the human list would have loosened the shared gate for every human prompt in the app,
  which is exactly what that pin exists to catch. An unknown `kind` falls back to human, never
  to something more permissive.
- **Vocabulary a bank can write but the gate cannot see is decoration.** That is what those
  four fur phrases were. `tools/pet_realism_bank.json` is keyed into by `story_bank.json`, never
  copied (the rule `macro_insert_bank.json` already set for `lighting_setup`), and
  `tests/test_pet_realism.py` checks **every** texture phrase is detectable by the animal keys,
  per phrase, audited rather than assumed.
- **A cat's core terms are PINNED, not picked.** `prompt_bank.json`'s core layer can draw
  `"realistic skin textures"`, which is how every photoreal cat scene opened by asking for skin
  on a cat. That term cannot simply be deleted: it is correct for humans, the file is
  hash-pinned, and bumping its `version` would invalidate every rated history entry through
  `history.usable()`. `story_bank.json`'s photoreal style sets `overrides.core` to three terms
  that were **already in `prompt_bank.json`** - an override is `build_prompt`'s own
  top-precedence slot and costs neither the hash nor the ratings.
- **A hidden form row must not stay live.** `cats.py`'s `style_key()` read the Look combo even
  on `trade`, which sets `ui.rows.Look: false` - so picking Stylised on `story` and switching to
  `trade` kept generating stylised scenes with no visible control and no way back.
  `cast_key()` already had exactly this guard; `style_key()` just never got one. When a format
  hides a row, read the bank's default, not the widget.
- **Nothing in this app described the CAPTURE, only the subject.** A repo-wide grep across
  every bank returned zero hits for chromatic aberration, halation, veiling glare, vignetting,
  barrel distortion, ISO, shutter speed, white balance, motion blur and sensor dust, and no
  film stock was nameable anywhere - so output topped out at "well-lit studio photograph",
  plausible and with nothing in it saying a physical camera was involved. Two stranger finds
  from the same grep: `subsurface scattering` and `sensor noise` were already `DETECT` keys, so
  the gate could SEE them while the builder could never WRITE them, and
  `upscale_image.UPSCALE_PROMPT` carries `hair strands`/`fabric fibers` that are composable
  nowhere. `tools/capture_bank.json` + `build_capture.py` + `capture_lint.py` + the Look →
  **Capture** tab close that gap.
- **Capture EXTENDS the other overrides; every other `set_*_override` replaces.** Lighting
  setups are alternatives - one instead of another. A capture artefact is a property of the
  camera that is true at the same time as everything else: "shot on Portra 400" does not cancel
  "soft window light". `SpecEditor.set_capture_overrides()` therefore merges per layer, and it
  takes a **dict**, not a phrase, because one selection strengthens `grain`, `lens`, `lighting`
  and `colour` at once - the only toolkit in Look that does.
- **A group's declared layer is a default, not a claim about every option in it.** In
  `capture_bank.json`, white balance sits in the `exposure` group but is colour temperature and
  belongs to `lighting`; highlight rolloff is tonal and belongs to `colour`. Both override the
  group. `tests/test_capture_bank.py` checks the EFFECTIVE layer per option, so a wrong default
  cannot hide behind a right-looking group.
- **Scope a bank rule to where it means something; do not delete it to reach 100%.**
  `capture_lint.py` requires a hedging word ("faint", "subtle", "slight") because a shouted
  artefact is a filter rather than a photograph, and it initially failed three options. Two
  were real (`around` was simply missing from the hedge list). The third was the rule being
  wrong: a crop is imperfect or it is not, and on-camera flash falls off hard by definition, so
  the `evidence` group carries `"restraint": false` and says why. Weakening the check to pass
  would have been the other thing.
- **A film stock can already contain an artefact.** CineStill 800T's whole signature IS its
  halation, so selecting both produced the phrase twice - which reads as emphasis to the model
  and makes the artefact louder than any real one. Declared as `"implies": ["halation"]` in the
  bank and de-duplicated in `compose_capture()`, not string-matched, so the two cannot drift.
- **Capture is APPENDED to `LookView`'s tabs, never inserted.** `SUBVIEW_ROUTES` maps each
  toolkit to a fixed tab index, so inserting a tab would silently re-point `go_to("style")` and
  every `SpecEditor.open_*_requested` signal at the wrong one. `tests/test_style_gui.py` pins
  the full tab list in order.
- **A "flaky GUI test" was a real race, and the race is in the APP.** `test_newui.py`'s
  `"adopted into compose"` failed on roughly half of full-suite runs and never standalone,
  which reads like a timing artefact of the test harness. It was not.
  `ComposeView.schedule_rebuild()` arms a **180ms single-shot QTimer**, and `rebuild()` opens
  by clearing `_override_prompt` - so a pending debounced rebuild fired straight after
  `use_upgraded_prompt()` and silently reverted the rewrite the user had just adopted. The same
  timing exists for a person who edits a field and clicks Apply within 180ms; there the prompt
  simply changes back with no message. Fixed by stopping the timer in `use_upgraded_prompt()`,
  and `test_newui.py` now pumps a full second past the debounce window instead of checking
  once. **The lesson is the method**: the flake was proven pre-existing by stashing every other
  change and reproducing it on the untouched tree, rather than assumed either way - and
  "intermittent under load" turned out to mean "there is a real race here", not "ignore it".
- **`tools/typography_bank.json` is the first vocabulary in this app for text INSIDE an image.**
  Before it, a repo-wide grep for typography, headline, logo, copy placement, kerning, lockup or
  type hierarchy found nothing about text in a picture anywhere - the only hits were
  `ui/tokens.py`'s own Qt stylesheet fonts and one photographic phrase, `negative-space`, and
  `logo` had **zero hits in `tools/`**. An app that builds advertising could describe the
  photograph and not one word of the advert laid over it. Its phrases land on `composition`,
  and that is not a fudge: reserving an even-toned region of the frame for type IS a
  compositional instruction, and it is the one that decides whether the type ends up legible.
- **A typography phrase written as a REFUSAL is invisible, and nothing else would catch it.**
  `lockup.none` and `restraint.no-legal` were first written "no brand logo in the frame" and
  "no small print or legal line in the frame" - sensible English, and completely unscored,
  because `is_negated()` correctly refuses to credit a key a prompt is ruling out. Both now lead
  with the positive half ("the packaging itself carrying the brand mark", "the type limited to
  what reads at a glance"). `typography_lint.py` carries a `positive` check that
  `capture_lint.py` does not, precisely because typography constantly wants to say what is
  ABSENT - no logo, no small print, no competing subhead - and that is the shape that goes
  silently undetected.
- **A flat hierarchy is caught as a CONTRADICTION, not a heuristic.** "Everything is loud so
  nothing leads" cannot be read out of words, but the two decisions that express it can be
  checked against each other: asking for the type to lead while giving it a tenth of the frame
  is a flat hierarchy stated twice. `compose_typography()` **raises** on that (there is no
  composed answer when two values cannot both be true of one layout) and only **warns** on a
  named conflict like a logo sitting where the headline goes (still a coherent layout, you have
  just been told). Same split `build_color.py` uses refusing `--mood` with `--film-look`.
- **Word caps are a rendering fact, not style advice.** Image models garble long strings, so
  each `ratio` carries `max_words` and `--headline` is checked against it. Anything longer
  belongs in a typesetting tool over a clean plate.
- **Bank order, not argument order - WITHIN a group as well as between them.**
  `build_typography.compose_typography()` shipped briefly with the stackable `restraint` group
  emitting in the order it was typed, so the same two options reversed composed to two
  different strings. `build_capture.py` already had the guard and it was not carried over.
  Caught by a "selection order does not change the output" assertion, which every builder with
  a repeatable group should have.
- **A prompt that names two lighting setups is the commonest way a good prompt goes muddy.**
  Both influencer sources did it: one established warm sconces behind the subject plus indoor
  cinematic light and then appended "ring lighting"; the other said "no dramatic shadows" and
  appended "moody lighting" four clauses later. A model cannot honour both, so it averages them,
  and averaged light is the flat sourceless glow that makes an image look generated. Resolved to
  one setup in the worked example, with the lesson in the slot's `why` and a test on it.
- **A judgement is not a description, and it costs a token that could have named a property.**
  The second influencer source opened with "sexy" and described a chest; both were dropped for
  the same reason "8K" was dropped from `product-campaign` and `candid-editorial` - they are the
  class of token `prompt_bank.json` already lists in `warn` ("masterpiece", "award-winning"):
  they ask the model to flatter rather than to render. What replaced them is what those words
  were standing in for - fabric stretch, where a neckline sits under the weight of the knit.
  Also dropped: "right light" (a typo for rim light - the clause was cut rather than guessed at)
  and "British-style" on overcast daylight, which names nothing "bright, diffuse, no direct
  sunlight" does not already name.
- **The highest-value idea in any of the five prompts was `marks`: evidence, not imperfection.**
  A faint dent on the bridge of the nose means she wore sunglasses; a tan line means a swimsuit,
  weeks ago; a fingerprint smear on the mirror edge is about the surface between camera and
  subject. None of them describe how she looks. This is the flyaway-hair instinct one level
  deeper - imperfection with a CAUSE - and no generator adds any of it unasked.
- **`spec["overrides"][<layer>]` REPLACES the bank's picks for that layer; a non-layer
  override key APPENDS to the free tail.** That is why face micro-detail and lived-in evidence
  ride `overrides["face_detail"]` / `overrides["evidence"]` and not `overrides["texture"]`:
  in the texture slot they would have thrown away the bank's own texture terms and their
  learned `history.weights()`. In the tail they can only ADD keywords - realism_lint scans the
  whole prompt - so neither can lower a score, and `tests/test_evidence_bank.py` /
  `test_face_detail.py` sweep 120 and 90 specs to prove it. Weight & contact and Materials in
  this scene (`overrides["contact"]` / `overrides["material"]`, `build_prompt.apply_physical()`)
  follow the same rule; `tests/test_physical.py` sweeps 90 specs. Materials REPLACES Lighting's
  generic "material response" sentence when it finds real materials - two lines saying the same
  thing is clutter, not more realism. Phone snapshot / Unstaged background / Catch the moment
  (`build_snapshot.py`, `apply_snapshot()`) are the same pattern; `tests/test_snapshot.py`.
- **Video realism lives in `video_realism_bank.json`, never in `motion_bank.json`** (hash-pinned).
  `build_motion.load_bank()` merges its locked-off movement in, so the bank has 41 movements
  while the file still has 40 - `tests/test_motion.py` counts the merged bank,
  `tests/test_video_realism.py` checks the file. `real_motion_line()` / `phone_style()` are
  opt-in params on `compose()` and `assemble_template()` (off = byte-identical); the Videos tab's
  "Real motion (auto)" and "Phone video look" are on by default, and photoreal Cats clips always
  carry real motion. `compose()` used to drop the Subject on a move that frames a place
  (wide-static et al.) - a clip prompt with no subject in it.
- **The Videos tab writes a one-take story by default** (`build_motion.assemble_story()`), the
  shape of the user's own 150k-view prompt: "Static shot, <subject>." then each Timing line as a
  sentence in order (Initially / Then / Soon after / Finally, a typed "Suddenly" kept), closing
  "Subtle, fluid motion." Seconds are dropped. The old comma template is "Tagged list".
  Negatives are OPTIONAL (off for a story, on for tagged); `motion_lint.lint(negatives=False)`
  passes the guard row as "optional". `leads_with_camera()` accepts plain still-camera openers
  ("Static shot", "Fixed camera"...) and, under a still camera, "Describes motion" counts what
  the SUBJECT does. That viral prompt used to score 4/7 here; `tests/test_video_realism.py`
  holds it at full marks verbatim.
- **A non-human subject never gets skin or pore words.** `select_layers()` filters the core and
  texture picks through `SKIN_WORDS` unless the subject is a person - realism_lint bans them on an
  animal, and before this a Compose cat could draw "visible skin pores". `subject_kind()` also
  lets a person or animal word beat a place word: "a ginger street cat" used to read as a PLACE
  and lost every cat-specific line.
- **Bash heredocs turn `\b` into a literal backspace here.** A regex written through a heredoc
  silently never matched. Write patch scripts with the Write tool, then run them.
- **Face detail is scaled by shot distance, never constant.** `build_face_detail.shot_tier()`
  maps a preset or typed shot to close / mid / wide, and the wide tier carries no pore
  language at all: pores at full body are detail no lens resolves, and asking makes a model
  over-sharpen the face into a render. The close tier keys into `macro_insert_bank.json`
  (the user's FULL FACE prompt) rather than copying it. Objects and places get nothing.
- **Evidence, not imperfection.** `evidence_bank.json` holds details that each have a CAUSE
  (sunglasses dent, shed hairs on the cushion it slept on, a dried water ring). An explicit
  Look → Evidence pick is `overrides["evidence"]` and round-trips through `load_spec()`;
  Compose's auto toggle writes `overrides["evidence_auto"]`, a different key, so a saved auto
  pick is never resurrected as an explicit one. The two Compose toggles are working
  preferences - `load_spec()` never flips them.
- **Auto lighting is NARROWED by the Setting, never replaced.** `select_layers()` used to
  draw one of the nine lighting terms at random with no reference to the Setting, so a bar at
  night could get golden-hour sun. With `spec["scene_lighting"]` set (Compose's "Match light
  to the scene", on by default; photoreal Cats scenes) it runs the same weighted `pick()`
  over the subset `build_scene_light.allowed_terms()` allows - `scene_light_bank.json` may
  only name terms `prompt_bank.json` owns, so ratings keep steering it. The source, bounce
  off named materials and shadow coherence ride `overrides["scene_light"]` in the tail; with
  an explicit lighting override the source is left out (a second named light would contradict
  it) but bounce and shadows stay. Without the flag, output is byte-for-byte unchanged, and
  `scene_lighting` is not in `brief.SPEC_KEYS`, so a model cannot set it.
- **Timed beats are a promise about the whole clip, so their checks are conditional.**
  `motion_lint` adds rules 8-10 (beats cover 0→clip length with no gaps, one action per beat,
  an `ENDS ON:` state) only when a prompt contains `0-2s:`-style beats - every untimed prompt
  still scores out of 7, exactly as before. `build_motion.parse_beats()` is shared by the
  Videos tab and the linter so the two cannot disagree; with beats present the untimed Action
  is left out of the subject clause, or the model does the action twice.

- **Run the layout suite with `QT_QPA_FONTDIR` set, or it cannot see layout bugs.**
  Qt's offscreen platform on this machine exposes ZERO font families
  (`QFontDatabase.families()` returns `[]`), so a 12px font reports a 12px line
  box. Any real typeface reports 14 - DejaVu Sans on the CI runner does, Segoe
  UI reports 16 - and every height this app derives from a font is therefore
  measured 2-4px short PER LINE locally. `tests/test_layout.py` passed a
  genuinely broken Compose card for exactly this reason: `setMinimumSize(1100,
  700)` claims that size is supported, and with real metrics `MainWindow`'s own
  minimum was 774px, so Qt shared the 74px shortfall out and the Realism-check
  badge (size policy Fixed) came out 16px of the 22px it asked for. Reproduce
  with `QT_QPA_FONTDIR="C:/Windows/Fonts" python tests/run_all.py`; CI installs
  `fonts-dejavu-core` for the same reason. A green local layout run means less
  than it looks like.
- **CI failures are readable without credentials, by design.** GitHub serves
  Actions job logs only to authenticated callers, so a red run showed nothing
  but "Process completed with exit code 1". `.github/workflows/tests.yml` now
  re-emits the suite's own failing lines as an `::error::` annotation and the
  runner's Python/Qt/font numbers as a `::notice::` - both readable anonymously
  via `/repos/{owner}/{repo}/commits/{sha}/check-runs` and its
  `output.annotations_url`. If a run goes red, read the annotation; do not
  guess from a local run, which uses different fonts.
- **Run `python tests/run_all.py` before calling anything done.** 1718 checks, all green
  across 31 suites (`test_history.py`, `test_lighting_bank.py`, `test_elevenlabs.py`,
  `test_composition_bank.py`, `test_posing_bank.py`, `test_color_bank.py`,
  `test_camera_angle_bank.py`, `test_advisor.py`, `test_advisor_gui.py`,
  `test_combo_resolve.py`, `test_persona_bank.py` and `test_influencer_studio_gui.py` are all
  now in `tests/run_all.py`'s `ORDER` - `test_elevenlabs.py` existed for a while but was never
  actually wired in, so it silently never ran as part of the suite until it was noticed), no
  dependencies beyond PyQt6, Qt runs offscreen.

---

## Current phase

**Phase 2 — ARCHITECT.** Built and working, avatars through to real video and audio:

- `workflows/create-realistic-avatar.md`
- `workflows/consistent-character.md` — Phase 5, a face locked across shots via a reference
- `workflows/write-a-brief.md`
- `workflows/ask-the-advisor.md` — a running conversation with the in-app expert
- `workflows/image-to-video.md` — Phase 3, real Kling 3.0 clips through Kie, not prompts only
- `workflows/ugc-ad.md` — Phase 6, the five-beat advert
- `workflows/cat-story-video.md` — a story in scenes, with its CapCut edit sheet
- `workflows/sound-design.md` — three layers of ElevenLabs prompts per scene

The spec form is tabbed Purpose / Subject / Scene / Identity / More; Scene holds Setting,
Shot, Lighting, Colour and Composition.

**The rail is ten plain-noun sections, grouped by what a section is for** (restructured
from a flat 16 - `pyqt6_system_prompt.md` has the authoritative list). `NAV_ITEMS` in
`ui/main_window.py` is the single source for the rail, the stack order and the `Ctrl+N`
shortcuts (invariant: nav-button order == stack order == NAV_ITEMS order). Every
build-something section opens on a **Build** tab (Images keeps "Compose"), carries a
one-line "what this is for" header, and where it has one, a **Library** tab of examples.

1. **Images** (`ImagesView`, thin container) - Compose + Variants.
2. **Look** (`LookView`, container) - the six prompt-tuning toolkits as tabs: **Lighting**
   (named setups, or direction + quality + source, + realism techniques → lighting
   override), **Composition** (the eight framing geometries + techniques → composition
   combo as custom text), **Camera** (vertical + side + size axes → shot field as custom
   text; a pure angle can honestly score the camera check 0/8), **Color** (12 moods + 10
   film looks + techniques → colour override), **Posing** (poses by shot type + techniques
   → Posing field, not a gated layer), **Style** (24 named looks from the course's Style
   Reference Library → `overrides["style"]`, which `build_prompt.free_overrides()` folds
   into the free trailing segment; stylised looks warn that they fight the realism
   vocabulary), **Capture** (film stock, lens artefacts, exposure), **Evidence** (lived-in
   details with a cause → `overrides["evidence"]`). Each is Library + Build and calls a
   `tools/build_*.py`.
3. **Videos** - the Kling motion toolkit + the film glossary; builds the prompt and can
   generate the real clip.
4. **Personas** (`InfluencerStudioView`) - a saved roster of personas composed into one
   Subject sentence; Apply writes the Subject field wholesale, reference images stay a
   local mood board.
5. **Ads** - the five-beat UGC advert (brief, storyboard, hook A/B, checklist, publishing).
6. **Cats** - a story in scenes + CapCut sheet, plus a Custom Prompt tab (the one place a
   prompt is ingested, not composed).
7. **Sound** - the 100 ElevenLabs prompts, three layers per scene, TTS and voice cloning.
8. **Assistant** (`AssistantView`, container) - **Chat** (the running conversation with the
   in-app expert; one Apply feeds the spec and all six Look sections) + **Prompt tools**
   (the one-shot helpers: idea → spec, upgrade, critique, reverse-engineer a photo) +
   **Prompt Bank** (the user's own prompts and their example images, saved exactly as given).
9. **Activity** (`ActivityView`, container) - **History** + **What works** (the
   term-to-rating payoff; a "prefer learned terms" toggle biases composition).
10. **Settings** - provider / model / key presence / theme / paths.

**Container mechanics**: `LookView`/`AssistantView`/`ActivityView` copy `ImagesView` -
build the children, expose them (`self.lighting = LightingView(...)`), and `MainWindow`
reaches in (`self.lighting_view = self.look_view.lighting`), so every `apply_*_phrase`,
`ADVISOR_SECTION_SETTERS` wire and `win.<x>_view` reference is unchanged. `SUBVIEW_ROUTES`
in `main_window.py` makes `go_to("lighting")` / `go_to("history")` / the
`SpecEditor.open_*_requested` signals resolve to a container + tab index. `on_nav_clicked`
is a generic `refresh`/`reload`/`refresh_key_state` dispatch now, not a 16-way if/elif.
`tests/test_layout.py`'s `tab_paths()` recurses so the nested toolkit Library/Build tabs
and Assistant's nested Brief tabs are still layout-tested. Second rail map to keep in
sync: `tools/advisor.py` `NAV_MAP` (labels == rail labels; `test_advisor.py` checks it).

This doc previously said clip generation and UGC ads/consistent characters were "not built
yet" - that had gone stale against the code; all of it ships. It then said
`relight-and-angles.md` and `static-ad.md` were the two remaining stubs - that has gone stale
too. Both ship (`tools/build_relight.py` + `relight_lint.py` + `relight_bank.json`, and
`tools/build_static_ad.py` + `static_ad_lint.py` + `static_ad_bank.json`), and so does a third
workflow that was never a stub at all: `macro-insert.md` (`tools/build_macro_insert.py` +
`macro_insert_lint.py` + `macro_insert_bank.json`), a beauty macro plus feature-scoped eye/
mouth/cheek inserts built from community-supplied material rather than course content.
**Every row in `workflows/README.md` is now `ready`**; that table, not this paragraph, is the
one to trust - check it before repeating a "not built" claim from here.
