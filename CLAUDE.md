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
- **Run `python tests/run_all.py` before calling anything done.** 1273 checks, all green
  (`test_history.py`, `test_lighting_bank.py`, `test_elevenlabs.py` and `test_composition_bank.py`
  are all now in `tests/run_all.py`'s `ORDER` - `test_elevenlabs.py` existed for a while but was
  never actually wired in, so it silently never ran as part of the suite until it was noticed),
  no dependencies beyond PyQt6, Qt runs offscreen.

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

The GUI is organised by category: **Images** (Compose + Variants), **Lighting** (named
portrait setups, or direction + quality + source composed independently, plus opt-in realism
techniques - Apply to Compose writes straight into Compose's own lighting override),
**Composition** (the same seven framing geometries Compose's own combo already offers,
browsable, plus opt-in realism techniques - negative space, lead room, depth layering, ... -
stacked on top; Apply to Compose writes the result in as custom framing text), **Videos**
(the Kling camera-movement toolkit and the film glossary — builds the prompt and, since Phase 3,
can generate the real clip too), **Ads** (the five-beat UGC advert: brief, storyboard, hook A/B,
checklist, publishing), **Cats** (a story in scenes plus its CapCut edit sheet, and a Custom Prompt tab for a
hand-written shot instead), **Sound**
(the 100 ElevenLabs prompts, three layers per scene, and - with a real key - actual generated
sound effects, text-to-speech and voice cloning; Ads and Cats can voice their own copy/scenes
the same way), **Brief** (the text-model helpers),
then History, Insights and Settings.

This doc previously said clip generation and UGC ads/consistent characters were "not built
yet" - that had gone stale against the code; all of it ships. Genuinely not built (later
course phases, still stubs in `workflows/README.md`): `relight-and-angles.md` (Phase 2) and
`static-ad.md` (Phase 7).
