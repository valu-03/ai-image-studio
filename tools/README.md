# Tools — the T in WAT

Scripts the agent calls to get things done. Workflows hold the sequence; tools hold the logic.

## The tool contract

- **One job each.** If a tool needs "and", it's two tools.
- **Command-line invokable**, and every tool answers `--help`.
- **Deterministic.** Same input, same output. Anything random takes a `--seed`.
- **Standard library only**, unless a dependency is unavoidable — and then it's listed here.
- **Reads from `temp/resources/`, writes to `temp/outputs/`.** Never writes elsewhere.
- **Never prints a secret.** Keys are read from `.env` and used, not echoed.

## Index

| Tool | Does | Needs a key? |
|---|---|---|
| `prompt_bank.json` | The lesson-20 cheat-sheet as data: all eight realism layers, negatives, banned terms, shot presets, the eight optional composition guides, and the course's worked examples (including the influencer beach photo, which carries its own `teaches` notes). Not a script — the vocabulary the other tools read. | no |
| `build_prompt.py` | Character spec → layered photorealistic prompt (compact or `--detailed`). Writes to `temp/outputs/prompts/`. | no |
| `realism_lint.py` | Prompt → score out of 8, names the missing layer and the phrase to add, flags banned terms. Exit code 1 on failure so a workflow can gate on it. | no |
| `lighting_bank.json` | The Lighting section's taxonomy: 8 portrait directions (Rembrandt, split, loop, ...), hard/soft quality, 10 natural/artificial sources, 8 named setups combining them, and 7 physically-grounded realism techniques (catchlights, colour temperature, ...). Not a script. | no |
| `build_lighting.py` | A named `setup` (fast path) or direction + quality + source (deep path) → a lighting phrase, `realism_techniques` stacking on either (plus one free-text extra). The deep path's three pieces each accept a bank key OR your own text - a typo isn't rejected, it's just used literally. Checked against the bank's `conflicts` list when both quality and source are recognised keys - a combination that fights itself is warned, not silently composed. Result feeds `spec["overrides"]["lighting"]`, the same slot Compose's own lighting combo already writes to. | no |
| `composition_bank.json` | The Composition section's opt-in realism techniques (negative space, lead room, depth layering, frame within a frame, visual balance, scale contrast, pattern and repetition) stacked on top of a guide. Not a script - the seven named geometries themselves stay in `prompt_bank.json`'s `composition_guides`, read via `build_prompt.guides()`, not duplicated here. | no |
| `build_composition.py` | A named `guide` (from `prompt_bank.json`) or typed custom text - custom always wins, same precedence `build_prompt.apply_composition_guide()` already enforces - plus `techniques` stacking on either (plus one free-text extra). No `conflicts` list: the seven guides are already mutually exclusive by construction and no technique fights one. Result is meant to be typed straight into Compose's own composition combo as custom text. | no |
| `posing_bank.json` | The Posing section's named poses (portrait, editorial, headshot, group, candid) plus opt-in posing-realism techniques (relaxed hands, negative space between limbs, ...) stacked on top. Posing is NOT one of `realism_lint.py`'s 8 gated layers - it's descriptive spec content like wardrobe/setting/mood, so nothing here needs a `DETECT` keyword. Not a script. | no |
| `build_posing.py` | A named `pose` OR your own typed text - a pose is a tested starting point, not a closed world, same as Lighting's deep path - plus `techniques` stacking on either (plus one free-text extra). A base pose is recommended but not required: a lone technique stack or a single free-text phrase composes on its own, only a wholly empty request raises. No `conflicts` list: one pose at a time, nothing to contradict. Result is meant to be typed straight into Compose's own Posing field as custom text. | no |
| `color_bank.json` | The Color Grading section's 12 named moods and 10 film-look references (from the course's own Mood → Color → Prompt cheat sheet), plus opt-in techniques (accent echo, warm/cool contrast). Some source material leans stylised rather than restrained - checked against `banned`/`warn`, not just detectability. Not a script. | no |
| `build_color.py` | A named `mood`, a named `film_look`, or your own typed text - `mood`/`film_look` are two complete recipes, giving both is refused - plus `techniques` stacking on either. Result feeds `spec["overrides"]["colour"]`, which `build_prompt.select_layers()` already handles generically for any layer name - no `build_prompt.py` change was needed. | no |
| `camera_angle_bank.json` | The Camera Angle section's three independent axes: vertical position (eye-level, low/high-angle, worm's-eye, top-down, dutch), side (frontal, three-quarter, profile, back-shot, over-the-shoulder, POV), and shot size (extreme-wide through extreme-close-up) - from the Camera Language lesson. No `conflicts`, no `techniques`: the three axes never contradict each other and fully describe camera position on their own. Not a script. | no |
| `build_camera_angle.py` | Any subset of vertical/side/size, comma-joined, or your own typed text (always wins). Result is typed straight into Compose's own Shot field as custom text, reusing `build_prompt.apply_custom_shot()`'s existing precedence - which means a pure angle phrase with no camera vocabulary can legitimately score the camera check 0/8, same as any other typed shot. That's documented, not hidden. | no |
| `persona_bank.json` | The Influencer Studio section's vocabulary: 4 genders, 8 age ranges, 10 aesthetic style tags, 15 hair colours and 8 eye colours (each hair/eye entry also carries a hex swatch for the picker), all app-original (not from the course). Not a script. | no |
| `build_persona.py` | Name + gender + age range + any number of style tags + hair/eye colour + free-text details -> one flowing Subject description. Every field is optional and an unrecognised key is dropped, never smuggled through as free text - unlike a technique section's own picks, there is no invalid *combination* here, so `compose_persona()` never raises; it falls back to `"a person."` the same way `SpecEditor.PLACEHOLDER_SUBJECT` already does. Result is meant to replace Compose's own Subject field wholesale - `SpecEditor.set_subject_override()` does exactly that. No attractiveness/face-shape/body-shape control exists here, on purpose. | no |
| `generate_image.py` | Image generation for **Kie** (default, Nano Banana Pro) and **Higgsfield Soul**. Both are async: submit a job, poll it, download the result. `--reference` (character consistency) is Kie-only and refused elsewhere. `--dry-run` and an explicit exit code per failure mode. | yes |
| `history.py` | The outcome log. Records every generated prompt with the vocabulary it used, takes a 1–5 rating, reports which terms correlate with good results (`analyze`), and diffs any two prompts. | no |
| `generate_video.py` | Clip generation on **Kling 3.0** through Kie - the same job API as the images, and none of its own transport: `post_json`, `poll`, `download` and both Kie parsers come from `generate_image.py`. `--image` makes it image-to-video, which is what keeps one cat across the cuts. `--price` estimates a batch, `--dry-run` prints the request. | yes |
| `skit_client.py` | Client for **Skit Studio** (`..\Skit Studio`), the separate talking-pet skit app: `create()` writes and prices a skit (optional `video_model`), `ideas()` auto-generates ideas, `get()` polls it, `approve()` passes its cost gate (the only call that spends), `download()` saves the mp4 into `temp/outputs/skit_studio/`. Its REST contract mirrors MoneyPrinterTurbo. `SKIT_API_BASE` / `SKIT_API_TOKEN` in `.env`. Used by Videos -> Skit Studio. | no (Skit Studio holds the keys) |
| `local_api.py` | The **Local API** Skit Studio uses for its images while this app is open (127.0.0.1:8785, the same arrangement as VoiceStudio's 3900). Adds the Look (`look_options()`, `compose_look()`, `assemble_prompt()`) to a caller's prompt and generates through `generate_image.generate()`; results go to History tagged Skit Studio. `POST /api/v1/prompt` returns the finished prompt with no spend, for pasting into Google Flow. `--serve` runs it headless, `--options` prints the Look lists. | yes (KIE_API_KEY, via generate_image) |
| `pricing.json` | What a generation costs, per image and per second, with the date and the page the numbers came from. Seeded and labelled `estimated`; `recordInfo`'s `creditsConsumed` overwrites each one with a measured figure the first time a real job runs. | no |
| `ask_llm.py` | Text-model adapter (OpenRouter - the only text provider, and entirely optional). Reuses `generate_image.py`'s env reader, POST and error handling. Optional `history` param/`--history-file` threads prior turns in between the system message and the new one - every call that omits it gets today's exact single-shot request, unchanged. | yes |
| `brief.py` | The six-part brief framework from lesson 1, the briefs this project uses (idea, autofill, upgrade, critique, **analyze**) **and the validation gates that stop a model output being trusted**. `autofill` fills a form's empty fields only, and holds composition and lighting back as suggestions. `analyze_uploaded_image` reverse-engineers a spec from ANY local photo (not one this app made, and with no known prompt - the case `critique_image` can't cover) plus a plain-English verdict; the spec is whitelisted and recomposed/relinted exactly like `spec_from_idea`'s. | yes (to call out) |
| `advisor.py` | The one AI feature in this project that is a running conversation, not a one-shot brief - `chat()` threads `ask_llm.ask()`'s new `history` param turn to turn. `advisor_brief()` is built live from `prompt_bank.json`'s 8 layers, the composition guides and all five technique banks, so it never goes stale. A reply may propose a ready spec by fencing it as ` ```spec {...} ``` ` (`extract_spec_block()` looks specifically for that fence, not a whole-text brace scan); the fenced block is whitelisted, recomposed and relinted exactly like every other AI-suggested spec - the advisor itself never states a score, it only ever reports one `realism_lint` actually computed. That same object may carry one more key, `"sections"`, proposing a pick for any of the five technique sections (Lighting, Composition, Color Grading, Posing, Camera Angle) - `_finalize_sections()` validates every field against that section's OWN real bank keys and composes it through that section's OWN `compose_X()`, never inventing phrasing; an invalid pick is dropped, never passed through as free text. `shot` and `sections.camera_angle` write to the same field, so a shot preset present in the same reply wins and the angle pick is dropped, rather than silently costing the camera realism layer. A photo attaches to its own turn only, never resent on later turns. See `workflows/ask-the-advisor.md`. | yes (to call out) |
| `motion_bank.json` | The Kling toolkit as data: 40 camera movements, each declaring what the frame must contain and how to frame the still for it. Not a script. | no |
| `build_motion.py` | Spec + movement → a Kling prompt that always leads with the camera move, plus `check_compatibility()` — the "think ahead" rule as code. | no |
| `motion_lint.py` | The video gate: leads with a camera move, names a subject, one move at a time, describes motion, no contradictions, one action, negative guard (7 rules). A prompt carrying timed beats (`0-2s: ...; ENDS ON: ...`) gets three more: the beats cover the clip with no gaps (`--seconds N`), one action per beat, an end state is stated. Same contract as `realism_lint.py`. | no |
| `evidence_bank.json` | Lived-in details with a cause, by subject kind (person, animal, object, place): a sunglasses dent, shed hairs on the cushion it slept on, a ring where the bottle stood wet. Evidence, not imperfection. Not a script. | no |
| `build_evidence.py` | Picked details (max 3), free text, or an auto-pick by seed for the subject's kind (`subject_kind()` reads it from the Subject) → one phrase for `spec["overrides"]["evidence"]`, a non-layer override that rides the free tail - it can only add to a realism score. | no |
| `face_detail_bank.json` | Face/coat micro-detail in three tiers by shot distance - close (pore-level, from the user's FULL FACE prompt), mid (zonal skin tone, asymmetry), wide (no pores at all). Keys into `macro_insert_bank.json` and `pet_realism_bank.json` instead of copying them. Not a script. | no |
| `build_face_detail.py` | Subject + shot (preset or typed) + seed → the tier's detail phrase for `spec["overrides"]["face_detail"]`; nothing for an object or place. Compose applies it automatically while its "Face micro-detail" toggle is on. | no |
| `build_skin_features.py` | `spec["skin_features"]` (freckles, beauty mark, natural redness, faint acne scars, under-eye shadows, uneven skin tone) + shot → one phrase for `spec["overrides"]["skin_features"]`, scaled like face detail (a null tier in `skin_features_bank.json` skips that feature on a wide shot). People only; a feature the Subject already names is skipped. Opt-in from Compose's Subject tab. `--list` prints every phrase. | no |
| `scene_light_bank.json` | Light that comes from the scene: places and times of day, each allowing a subset of `prompt_bank.json`'s own lighting terms and naming the real source (street lamps, the window, sun through leaves); surface materials and the colour they bounce (wood, grass, snow, neon...); shadow-coherence and contact-shadow phrases. Not a script. | no |
| `build_scene_light.py` | Setting → the lighting terms it allows, the named source, up to two bounce phrases and the shadow phrases; `conflicts_with()` reports an explicit lighting choice the Setting contradicts. `build_prompt` uses it when a spec carries `scene_lighting: true` (Compose's "Match light to the scene", on by default; photoreal Cats scenes). | no |
| `contact_bank.json` | Weight and contact: what the subject rests on (sofa, bed, grass, snow, table...) and what it is doing (holding, sitting, lying...), each with one deformation phrase per subject kind - a cushion dipping, fingers pressing into a mug, paws sinking into snow - plus seed-picked defaults by kind. Not a script. | no |
| `build_contact.py` | Subject + Action + Posing + Setting → up to two contact phrases, earliest mention first, only ones written for the subject's kind (a bottle on a table never gets "forearms"). `build_prompt.apply_physical()` adds it as `overrides["contact"]` when a spec carries `contact_detail: true` (Compose's "Weight & contact (auto)", on by default; photoreal Cats scenes). | no |
| `video_realism_bank.json` | Measured from a viral one-take AI cat clip (no cuts, camera perfectly still, only the animals move): a locked-off camera movement (the Cats trade format's own wording), real-motion lines by subject kind (planted weight, follow-through, real-time speed with a ramp, a background that holds) and an ordinary-phone style. Kept out of the hash-pinned `motion_bank.json`; `build_motion.load_bank()` merges its movement in (41 total). Not a script. | no |
| `snapshot_bank.json` | The viral phone-video look, built against a user-supplied street-cat frame: "who took it" lines by subject kind plus phone processing; per-place unstaged backgrounds (a passer-by out of focus, an everyday thing nobody arranged, a worn surface); split-second moments by action and kind. Not a script. | no |
| `build_snapshot.py` | `snapshot_mode()` (phone / keep / skip - a chosen shot, typed shot, camera, lens or film stock wins), `background_line()`, `moment_line()`. `build_prompt.apply_snapshot()` uses them for the `snapshot`, `background_life` and `moment` flags (Compose's "Phone snapshot look", "Unstaged background", "Catch the moment", all on by default; photoreal Cats scenes take the last two). | no |
| `material_bank.json` | How specific materials and foods take the light: glass refraction, a glaze highlight, condensation, knit halo, silk highlights, melted-cheese sheen, uneven browning... `excludes` drops a contradicting match (iced coffee never steams). Not a script. | no |
| `build_material.py` | Subject + Wardrobe + Setting + Action → up to two material phrases; nothing when no material is named. Added as `overrides["material"]` with `material_detail: true` (Compose's "Materials in this scene (auto)"); when it finds something, it also removes `lighting_bank.json`'s generic "material response" technique from an explicit lighting choice so the prompt never says it twice. | no |
| `glossary.json` | 50 filmmaking terms as reference data. Framing/movement/lighting are actionable; editing and sound are reference only. | no |
| `ugc_bank.json` | The advert material as data: four platforms, the five-beat structure with the course's worked example, the emotion vocabulary, the seven-part checklist and the publishing reference. Not a script. | no |
| `build_ad.py` | Brief → five timed shots, each with a still prompt and a camera move, one presenter locked across all of them. Beat timing is capped rather than proportional - see below. | no |
| `ad_lint.py` | The advert gate: nine checks including product-by-10s, feeling-before-features and proof-AND-urgency. Same contract as the other two linters. | no |
| `story_bank.json` | The cat-story material as data: two visual styles (the stylised one lives here so it cannot weaken the shared 8/8 gate), four story arcs, the Kling clip lengths, and the CapCut reference. Not a script. | no |
| `build_story.py` | Idea → scenes, each with a still prompt and a camera move, one cat locked across all of them. Also builds the CapCut edit sheet. Every scene carries TWO durations - see below. | no |
| `story_lint.py` | The story gate. The check list is per FORMAT, not global: 13 for `story`, 12 for `trade`, 16 for `sitcom`. Same contract as the other linters. | no |
| `safety_lint.py` | The app's first CONTENT gate - injury, distress, hazards, and contact nobody softened. Scans human-authored fields ONLY, never a composed prompt. Opt-in per format; today only `sitcom` runs it. `--check-bank` audits its vocabulary against every shipped bank. | no |
| `build_pet_sound.py` | The two extra audio layers the sitcom format adds: an animal vocalisation and the reset snap. No linter of its own - every phrase is scored through `sound_lint` before it is returned. | no |
| `build_social.py` | Premise + captions → three titles, a caption and 15-20 hashtags. Deterministic, no model. | no |
| `social_lint.py` | The post gate: titles sized and actually different, caption sized, hashtags well-formed and counted, no claim language. | no |
| `sound_bank.json` | The course's 100 ElevenLabs example prompts verbatim, tagged by theme, plus the pattern measured across them. Not a script. | no |
| `build_sound.py` | Source + action → one prompt; a scene → its three layers (ambience, key, accent), or five when a format passes `extra=`. Everything it emits is pre-scored by `sound_lint`, extras included. | no |
| `sound_lint.py` | The sound gate: describes an event, short enough, and is an effect rather than music or speech. The 100 examples are its fixture. | no |
| `make_icons.py` | Regenerates the SVG icon set into `assets/icons/`. Run after editing a glyph. `ICON_NAMES` is what `tests/test_layout.py` checks `ui/assets.py` against. (It still writes the old aperture `app.svg`, which nothing uses any more - the app mark is `app.png`, below.) | no |
| `make_app_icon.py` | Cuts the application mark out of the user's logo (`assets/icons/app-source.jpg`), leaving the "AI VIDEO STUDIO" lettering out, and centres it on a white rounded tile as `assets/icons/app.png` (512px), which is the window, taskbar and rail icon. Run after replacing the logo. | no |
| `make_exe_icon.py` | Packs `app.png` into `assets/icons/app.ico` (6 sizes, each resampled straight from the 512px source) for `AIVideoStudio.spec`'s `EXE(icon=...)`. Run after `make_app_icon.py`, before rebuilding the .exe. | no |
| `upscale_image.py` | The course's "upscale before you animate" rule: `generate_image.generate()` with the image being upscaled as its own sole reference and a fixed 4K instruction prompt instead of a written one. | yes |
| `refine_image.py` | Generate, critique the result through `brief.critique_image()`, strengthen whichever realism layer came back weak using only the bank's own vocabulary, and retry - capped at 2 retries. Closes the loop that used to be entirely manual. | yes (Kie/Higgsfield for the image, OpenRouter for the critique) |
| `midjourney_export.py` | Reformats an already-built, already-scored prompt into Midjourney's own `--ar`/`--style`/`--stylize`/`--no`/`--v` syntax, for pasting into Midjourney by hand. Text only - Midjourney has no official API. | no |
| `generate_sound.py` | Real ElevenLabs sound-effect generation - one synchronous POST, audio bytes back, no submit/poll cycle. Gated on `sound_lint` by default (`--force` to skip). Owns the shared ElevenLabs transport `generate_speech.py`/`elevenlabs_voices.py` both import. | yes |
| `generate_speech.py` | Real ElevenLabs text-to-speech. No content gate (spoken text isn't a layered prompt) - the safeguard is `estimate_cost()`'s character/credit count, shown before a real call. | yes |
| `elevenlabs_voices.py` | List/clone/delete ElevenLabs voices. `clone_voice()` refuses to run without `consented=True` - enforced in the tool itself, not only a GUI checkbox. | yes |

### Shared entry points

`build_prompt.py` exposes `compose()`, `write_prompt()`, `validate_shot()` and
`apply_variation()`; `realism_lint.py` exposes `lint()`; `history.py` exposes `append()`,
`rate()`, `weights()` and `diff_prompts()`. The CLI and the GUI both go through these —
that is what keeps the two from ever disagreeing.

### Two gates, one contract

`realism_lint.py` scores a still prompt out of 8; `motion_lint.py` scores a video prompt out
of 7 (leads with camera, names a subject, one dominant movement, describes motion, no
contradictions, one action not a chain, and the negative-artifact guard is actually present).
Both print named fixes and exit 1 on failure, so a workflow or the GUI can gate on either
without special-casing which kind of prompt it is holding.

### Composition guides

`prompt_bank.json` carries eight framing geometries - rule of thirds, phi grid, diagonals,
triangle, golden ratio, golden spiral, harmonic armature, dynamic symmetry. They are **entirely opt-in**: the
composition layer's own terms and the shot presets carry framing language only (eye-level,
candid, unstaged, natural framing, subject separation), so **no compositional rule reaches a
prompt unless the user picks one**. On `(none)` the layer still fills - it is one of the eight
the gate scores and can never be empty - it just imposes no geometry.

A chosen guide is a *pin*, not an override: it takes the first composition slot and the bank
fills the rest, so the layer keeps its usual length. That is the difference from custom
lighting, which is `pick: 1` and can simply take the slot - composition is `pick: 2`, and
replacing it outright would throw away half the layer.

`apply_composition_guide()` runs last in `select_layers()`, so an explicit guide outranks both
a shot preset and a camera-move `image_hint` - the same rule as everywhere else in this
project: defaults fill gaps, an explicit choice wins.

Every guide phrase names the geometry *and* what it does to the frame, because the jargon
alone means little to an image model. Each one also has a detection keyword in
`realism_lint.py`; without that the composition layer would score zero and a deliberate choice
would fail the 8/8 gate. `python tools/build_prompt.py --list-guides` prints them.

The Composition nav section (`ui/views/composition.py`, `build_composition.py`) is a thin layer
over the same eight guides plus a second, additive bank - `composition_bank.json`'s seven
`techniques` (negative space, lead room, depth layering, frame within a frame, visual balance,
scale contrast, pattern and repetition). A guide (or typed custom text - custom always wins,
same precedence as above) is the base; techniques stack on top, opt-in, never required, and
none of them contradicts a guide or each other, so unlike Lighting's `conflicts` list this bank
has none. `compose_composition()`'s result is meant to be typed straight into Compose's own
composition combo as custom text - `SpecEditor.set_composition_override()` does exactly that.

### `pick` decides what a custom value does

Shot, lighting and composition all accept free text. Where that text lands, and whether it is
safe, follows straight from the layer's `pick` count:

| Typed into | Layer | `pick` | What happens |
|---|---|---|---|
| Lighting | `lighting` | 1 | replaces the slot; `realistic shadows` is re-added so the layer still scores |
| Shot | `camera` | 1 | replaces the slot, and suppresses the shot preset entirely |
| Composition | `composition` | 2 | **pins** slot 0; a bank term still fills slot 1 |

The consequence is worth stating plainly, because the two behave differently on purpose. A
custom composition can never cost you the composition layer - something from the bank is always
still in it. A custom shot *can* cost you the camera layer, if what you typed names no capture
device: `--shot-custom "close-up iPhone-style photo"` scores 8/8, `--shot-custom
"over-the-shoulder from behind"` scores 7/8. That is the gate reporting an honest consequence,
not a bug to paper over.

Preset keys and free text are separate spec keys - `shot` and `shot_custom`,
`composition_guide` and `composition_guide_custom` - so `validate_shot()` still rejects a
misspelt preset rather than letting it through as a custom phrase.

### A scene has two durations

Kling generates 5-second and 10-second clips. Nothing else exists. The hook window is 3
seconds. Both numbers are real and they contradict each other, so `build_story` carries both:

| | |
|---|---|
| `clip_seconds` | what you generate — 5 or 10 |
| `edit_seconds` | what survives the cut in CapCut |

The opening is therefore always a 5-second clip trimmed to 3. `story_lint` checks that every
clip is a real length, that no scene keeps more than its clip, that the trims sum to the target
runtime, and that the opening is trimmed. `cost_note()` reports generated-versus-kept, because
a 45-second story cut from 10-second clips generates 90 seconds and nobody notices they are
paying twice.

### Two styles, two gates, one untouched bank

`prompt_bank.json` is photoreal by construction: its banned list forbids `cartoon style`,
`cgi` and `3d render`, and its negative block tells the model not to be any of them. The
stylised look therefore lives in `story_bank.json` and is applied through `spec["overrides"]`,
which is `build_prompt`'s existing top-precedence slot.

Photoreal scenes are judged by `realism_lint` exactly as everything else is. Stylised scenes
are judged by `story_lint` against the style's own `expects` block. **Do not "fix" a stylised
prompt by loosening `realism_lint`** - `tests/test_story.py` hashes that file and
`prompt_bank.json` for exactly this reason.

### Sound: measured, not guessed

`sound_lint`'s rules come from counting all 100 of the course's examples, not from intuition.
The first version guessed and rejected 31 of them. Only one structural property is universal
(an action, a placement or a qualifier), so only that one is a hard check; naming the space is
advice. See the module docstring for the counts.

### Ad timing is capped, not shared

The workflow checklist asks whether the product appears within 5-10 seconds. No percentage
split can hold that: an even split puts beat 4 at 18s in a 30-second ad, and even a
front-loaded 52% split puts it at 31s in a minute. So `build_ad.beat_timings()` caps the setup
in absolute seconds and lets beat 4 absorb the remainder - the product demonstration is the
part that should grow with the runtime, not the hook.

Beat 1 is capped again at the platform's hook window, because the two rules otherwise
contradict each other: a 20s TikTok ad's setup budget hands beat 1 3.1 seconds, and TikTok
wants the first clip under 3. That contradiction was found by running the course's own worked
example through the linter.

### Three gates, one contract

`realism_lint.py` scores a still out of 8, `motion_lint.py` a video prompt out of 7, and
`ad_lint.py` an advert out of 9. All three print named fixes and exit 1 on failure.

`ad_lint`'s two subtle checks are worth knowing. The **emotion check is scoped to beats 1-3**:
beat 4 is where "zero sulfates, zero harsh chemicals" belongs, and a linter that flagged it
would be wrong about a correct ad. And **beat 5 is two requirements** - proof without urgency
is the common failure and it reads finished. The course's LumaWash example is the fixture for
both: it must score 9/9, and `tests/test_ads.py` fails if it ever stops doing so.

### Bank versioning

`prompt_bank.json` carries a `version`, and `history.py` stamps it into every entry. Ratings
reference vocabulary by name, so renaming or removing a term would otherwise make old ratings
quietly mean something else — `weights()` would keep returning numbers, just wrong ones.
`history.usable()` excludes stale entries and reports how many it skipped. **Bump the version
whenever you change the term lists.**

### The feedback loop

`realism_lint.py` scores whether a term is *present*. `history.py` records whether it
*worked*. `history.weights()` turns ratings into selection bias, and
`build_prompt.compose(..., weights=...)` uses it — so the prompt bank stops being a
transcription of someone's PDF and becomes calibrated to your own results. Drive it with
`--learned` on the CLI, or the "Prefer terms that rated well" toggle in Insights.

`weights()` is UCB1, not a plain average: each term's multiplier is an exploit half (a
shrinkage estimate of its rating — no evidence sits at neutral, evidence pulls it away in
proportion to how much of it there is) plus an explore half that is largest for a term with
few or no ratings and shrinks as it accumulates them, scored per realism layer since
`build_prompt.pick()` draws each layer's terms as its own independent competition. Without the
explore half a term that got exactly one great rating stayed permanently outweighed by a
mediocre term with twenty, and a term nobody had ever picked sat at flat neutral forever with
no way to rise above it. With zero ratings anywhere every term in a layer gets an identical
bonus, which degrades to plain uniform sampling — the same behaviour the app has always had
before anything is rated, not something new and unverified on a fresh install.

Tools are standard library only. `PyQt6` is needed for the GUI, not for these.

### Exit codes (`generate_image.py`)

| Code | Meaning |
|---|---|
| 0 | Image saved; the path is printed as `[image] <path>` |
| 1 | A credential is missing (Higgsfield needs both the id and the secret) |
| 3 | Network failure, API error, or the job itself reported failure |
| 4 | The job finished but carried no image |
| 5 | Timed out waiting for the job |

Code 2 is retired along with the `fal` stub.

### Two providers, one pipeline

Kie and Higgsfield are both asynchronous, so a generation is three round trips - submit, poll
until the job leaves its queue, download the URL it hands back - not one request. That whole
pipeline lives in `generate_image.generate()`, and `ui/workers.py` calls exactly that function
rather than repeating it. The GUI and the CLI cannot drift apart about how a provider is spoken to.

| | Kie | Higgsfield |
|---|---|---|
| Credentials | `KIE_API_KEY` | `HIGGSFIELD_API_KEY_ID` **and** `HIGGSFIELD_API_KEY_SECRET` |
| Submit | `POST /api/v1/jobs/createTask` | `POST /higgsfield-ai/soul/v2/standard` |
| Poll | `GET /api/v1/jobs/recordInfo?taskId=` | the `status_url` it returns |
| Reference images | yes (uploaded first, then passed as a URL) | **no** |

Reference images are the asymmetry that matters: Kie takes them as URLs, so a local file is
uploaded first and the returned URL passed on. Higgsfield documents no reference input, so a
request carrying one is refused rather than sent without it - silently dropping a reference
produces a different person, which is the exact failure `consistent-character.md` prevents.

## Examples

```bash
# build, then check
python tools/build_prompt.py --spec temp/resources/characters/<slug>.json
python tools/realism_lint.py temp/outputs/prompts/avatar-<slug>-20260828-1430.txt

# quick one-off without a spec file
python tools/build_prompt.py --subject "a man in his forties, greying beard" --shot portrait

# see what a bad prompt looks like
echo "a beautiful woman, neon glow, 3d render" | python tools/realism_lint.py -
```

## Adding a tool

Write it to the contract above, add a row to the index, and reference it from the workflow
step that needs it. A tool nothing calls is dead weight — delete it.
