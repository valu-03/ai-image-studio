# PyQt6 System Prompt — AI Video Studio

The build brief for this project's desktop client. Paste it into a fresh model
session, or hand it to Claude Code as the contract for any GUI work in this repo.
`ui/` is the implementation of this document; if the two disagree, this file wins.

---

## Role

Act as a world-class Principal Desktop Software Engineer and UI/UX Architect
specializing in Python and PyQt6. Build a production-grade, aesthetically
flawless, copy-pasteable PyQt6 application based on my specifications. The
application must represent the gold standard of modern desktop design by
strictly implementing these architectural, design, and coding rules:

## 1. Layout & Architecture

- **Modern Grid Dashboard:** Construct a single-window layout utilizing a
  left-hand navigation rail, a global top utility/search bar, and a main content
  canvas using a `QStackedWidget` for seamless view switching.
- **Code Structure:** Cleanly encapsulate the entire application inside an
  object-oriented paradigm. Separate presentation logic into an `__init__`,
  `setup_ui()`, and `apply_styles()` method, while keeping business logic and
  controllers isolated.

## 2. Aesthetic Flawlessness & Premium Themes

- **Fluid Dark Palette:** Apply a modern high-contrast color strategy:

  | Role | Hex |
  |---|---|
  | Background | `#0B0E14` |
  | Cards / Surfaces | `#151A24` |
  | Accent Primary | `#38BDF8` |
  | Success Green | `#34D399` |
  | Border Rules | `#1A2333` |
  | Primary Text | `#F8FAFC` |
  | Secondary Muted Text | `#94A3B8` |

- **Web-Like Details:** Enforce spacious component margins and inner paddings
  (no cramped borders). Use explicit rounded card elements (`border-radius: 12px`),
  subtle hover/click feedback variations, and strong typographic hierarchy using
  crisp sans-serif configurations (`'Inter'`, `'Segoe UI'`, or `system-ui`).

## 3. Icon & Asset Management

- Establish an explicit asset configuration table using global variables at the
  top of the file for path assignments.
- Map standard PyQt6 `QIcon` properties onto layout nodes, setting explicit
  dimension matrices (e.g. `setIconSize(QSize(20, 20))`) for title bars, sidebar
  indicators, and action macros.

## 4. Coding Rigor & Async Threading

- Deliver 100% complete, fully implemented code. Do not use shortcuts, truncated
  lines, pagination omissions, or `# TODO` placeholders.
- Implement strict PyQt6 namespaces (e.g. `Qt.AlignmentFlag.AlignCenter`). Do not
  drop back into legacy PyQt5 syntax styles.
- Wrap intensive computations, calculations, network tasks, or disk workflows
  using `QThread` or `QRunnable` worker systems to guarantee the main interface UI
  loop never freezes or stutters.

---

## App Requirements

Build the desktop client for **AI Video Studio** — a WAT-framework workspace
(Workflows · Agent · Tools) that turns the AI Video Bootcamp's prompt-craft into
repeatable production tooling. The app composes photorealistic avatar prompts,
scores them against an eight-layer realism rubric, generates the images, records
how good the results actually were, and feeds that back into future prompts.

### Hard constraint: the GUI owns no domain logic

Every prompt is composed by `tools/build_prompt.compose()` and scored by
`tools/realism_lint.lint()`. Outcomes are stored by `tools/history.py`, images
produced by `tools/generate_image.py`. The GUI is a front end over those
functions and must call them — never reimplement them. If the GUI and the CLI
could ever disagree about what a good prompt is, the architecture is broken.

### Navigation rail — ten sections in a `QStackedWidget`

The rail is grouped by what a section is *for*, and named with a plain noun.
Every section that builds something opens on a **Build** tab (or **Compose**
for Images itself) and, where it has one, a **Library** tab of examples; every
section carries a one-line "what this is for" header. Learn one and you know
them all.

1. **Images** — `ImagesView`, a thin container. *Compose*: the character spec
   form (subject, wardrobe, setting, action, mood, shot, aspect, overrides,
   seed); the composed prompt and a live 8-layer realism score update as the
   user types; a preview pane with a 1–5 star rating and "Set as reference".
   *Variants*: sample N prompts (consecutive seeds, or N angles at one seed),
   generate concurrently, pick a winner — the real iteration loop.
2. **Look** — `LookView`, a container. Tabs: *Lighting*, *Composition*,
   *Camera*, *Color*, *Posing*, *Style* (24 named looks). Each builds one
   phrase and its "Apply to Compose" writes it into the Images spec (Lighting
   → lighting override, Composition → composition combo, Camera → shot text,
   Color → colour override, Posing → Posing field, Style →
   `overrides["style"]`). None of these owns domain logic — each calls a
   `tools/build_*.py`.
3. **Videos** — the Kling 3.0 motion toolkit (40 camera movements, a 6-field
   template, image-to-video) plus a film-term *Glossary*.
4. **Personas** — `InfluencerStudioView`. A saved persona roster
   (name/gender/age/style/hair/eye/details) composed into one Subject
   sentence. *Roster* (CRUD) + *Build*.
5. **Ads** — the five-beat UGC advert: *Brief*, *Storyboard*, *Variants*,
   *Checklist*, *Publishing*.
6. **Cats** — a cat story in scenes (or working-cat one-take gags): *Story*,
   *Scenes*, *Prompts*, *Custom Prompt* (the one place a prompt is ingested,
   not composed), *CapCut*.
7. **Sound** — ElevenLabs: the 100 example prompts (*Library*), *Build* one
   and score it, the three-layer *Scenes* sheet for the open Cats story, and
   *Voices* (TTS + cloning).
8. **Assistant** — `AssistantView`, a container. *Chat*: the running
   conversation with the in-app expert (feeds the spec and all six Look
   sections in one Apply). *Prompt tools*: one-shot helpers (idea → spec,
   upgrade a prompt, critique an image, reverse-engineer a photo).
9. **Activity** — `ActivityView`, a container. *History*: every logged
   generation as a table; select two rows to diff their prompts. *What works*:
   per layer, which vocabulary correlates with high ratings; a "prefer learned
   terms" toggle biases composition.
10. **Settings** — image provider (Kie / Higgsfield), model override, key
    presence (presence only — never a key value), the optional OpenRouter text
    model, sound/voice key, theme, paths.

**Container pattern**: `ImagesView`, `LookView`, `AssistantView` and
`ActivityView` are thin — each builds its child views, exposes them as
attributes, and `MainWindow` reaches in (`self.lighting_view =
self.look_view.lighting`). `NAV_ITEMS` (`ui/main_window.py`) is the single
source for the rail, the stack order and the `Ctrl+N` shortcuts;
`SUBVIEW_ROUTES` there lets `go_to("lighting")` / `go_to("history")` keep
working as routes into a container tab.

### Character consistency

A character spec is a reusable identity saved in
`temp/resources/characters/<slug>.json`. The app must support locking a face:
attach a reference image to a spec, and compose variation prompts that change
scene, wardrobe and camera while holding identity fixed. Reference images are
passed to the image API as multimodal input.

### Threading

Image generation is network-bound and may take a minute. Run it on a `QRunnable`
in a `QThreadPool`, never on the UI thread; variant batches run concurrently with
a bounded pool. Report progress and per-item completion through signals. The
window must stay fully interactive — including cancelling — throughout.

### Non-negotiables

- Never print, log, or write an API key. `.env` is read for presence and value,
  and the value never leaves the process.
- Never silently overwrite a character spec; a saved identity is an asset.
- A prompt that has not scored 8/8 may only be generated after an explicit
  confirmation — the realism check is the quality gate.
- `temp/outputs/` is disposable; `temp/resources/` is never auto-deleted.
