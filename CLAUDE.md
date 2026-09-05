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
  prompt only when the user picks one of the seven `composition_guides` or types their own;
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
- **Run `python tests/run_all.py` before calling anything done.** 1040 checks, no dependencies
  beyond PyQt6, Qt runs offscreen.

---

## Current phase

**Phase 2 — ARCHITECT.** Built and working, avatars through to real video and audio:

- `workflows/create-realistic-avatar.md`
- `workflows/consistent-character.md` — Phase 5, a face locked across shots via a reference
- `workflows/write-a-brief.md`
- `workflows/image-to-video.md` — Phase 3, real Kling 3.0 clips through Kie, not prompts only
- `workflows/ugc-ad.md` — Phase 6, the five-beat advert
- `workflows/cat-story-video.md` — a story in scenes, with its CapCut edit sheet
- `workflows/sound-design.md` — three layers of ElevenLabs prompts per scene

The spec form is tabbed Purpose / Subject / Scene / Identity / More; Scene holds Setting,
Shot, Lighting and Composition.

The GUI is organised by category: **Images** (Compose + Variants), **Videos** (the Kling
camera-movement toolkit and the film glossary — builds the prompt and, since Phase 3, can
generate the real clip too), **Ads** (the five-beat UGC advert: brief, storyboard, hook A/B,
checklist, publishing), **Cats** (a story in scenes plus its CapCut edit sheet, and a Custom Prompt tab for a
hand-written shot instead), **Sound**
(the 100 ElevenLabs prompts, and three layers per scene), **Brief** (the text-model helpers),
then History, Insights and Settings.

This doc previously said clip generation and UGC ads/consistent characters were "not built
yet" - that had gone stale against the code; all of it ships. Genuinely not built (later
course phases, still stubs in `workflows/README.md`): `relight-and-angles.md` (Phase 2) and
`static-ad.md` (Phase 7).
