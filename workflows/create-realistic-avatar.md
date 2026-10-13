# Workflow: Create a realistic avatar

**Goal:** turn a one-line character idea into a prompt that produces a face which reads as a
real photograph, not an AI image.

**Source:** AI Video Bootcamp, Phase 2 (ARCHITECT), lesson 20 — *Creating More Realistic Avatars*.

**Inputs:** a brief (can be one sentence).
**Outputs:** a character spec in `temp/resources/characters/<slug>.json`, a linted prompt in
`temp/outputs/prompts/`, an entry in `temp/outputs/avatar-log.md`.

**Model:** Nano Banana Pro. It is the best model for realistic avatars — don't substitute
another one because a result came back looking fake. Fix the prompt instead (step 6).

---

> **Doing this by hand?** `python gui.py` runs steps 2–5 in one window: edit the spec on the
> left, watch the prompt and the realism score update live on the right, then copy or save.
> The steps below are the same procedure for the agent, and for scripting.

## Step 1 — Capture the brief

Get these six things. Infer what you reasonably can from the brief; ask only for what's
genuinely missing, in one batch:

| Field | Example |
|---|---|
| `subject` | "a woman in her late twenties with freckles and dark wavy hair" |
| `wardrobe` | "an oversized cream knit sweater" |
| `setting` | "a bright minimal apartment kitchen, morning" |
| `action` | "holding a serum bottle toward the camera" |
| `shot` | one of: `portrait`, `selfie`, `talking-head`, `product-demo`, `environmental`, `phone-candid` — or your own words |
| `mood` | "calm, conversational" |

Rule of thumb for `shot`: talking-head for content, selfie for UGC/influencer, product-demo
when a product is in frame, portrait for a clean character reference, **phone-candid** for a
phone photo taken *of* someone (which a selfie is not — that one puts the phone in their hand).

The Shot box also takes free text: `--shot-custom "close-up iPhone-style photo"`. A typed shot
takes the camera slot and suppresses the preset. It must still name a capture device, or the
camera layer scores zero — the linter will tell you, before you spend a credit.

### Or let the model do it

**Images → Auto-fill.** Type a line, press the button, and OpenRouter fills every field you
left empty. Anything you have already typed is untouched and is sent as the brief, so it fills
*around* your work.

Two things it will never do on its own: set a composition guide, or set a lighting source.
Those arrive as a suggestion with a *Use these* button, because a geometry you did not choose
has no business in your prompt. It also cannot set `seed`, `reference`, `lock_identity` or
`overrides` — the same whitelist every model reply goes through.

## Step 2 — Write the character spec

Save it to `temp/resources/characters/<slug>.json`. The shape is the spec keys above plus
`seed`, and optionally `extra`, `purpose`, `aspect`, `shot_custom`,
`composition_guide` / `composition_guide_custom` and an `overrides` block. Easiest route: fill
the form in **Images → Compose** and press *Save character* — that writes a valid file for you.
(This folder is yours; it starts empty and may well be empty.)

This file is the **reusable identity**. Later phases (consistent characters, UGC ads) read
the same spec so the same person shows up across shots. Never overwrite an existing spec —
make a new slug.

## Step 3 — Build the prompt

```
python tools/build_prompt.py --spec temp/resources/characters/<slug>.json
```

Add `--detailed` for the long paragraph form — better for a hero shot, and closer to the
expanded example in the lesson. Add `--seed N` to shuffle the word choices when a prompt
feels stale; the same seed always gives the same prompt.

`--composition-guide <name>` pins one of the eight geometries; `--composition-custom "..."`
pins your own framing instruction instead — *"framed to include a clear sky, bright blue water
and a woven beach bag behind her"* is as good an instruction as a named grid, and often
clearer to the model. Either way it pins the first slot and the bank fills the second, so this
can never cost you the composition layer.

Two additions that describe the *subject* rather than the camera, both opt-in on the CLI and
both carried in the spec's `overrides` (they ride the free tail, so they can only add to the
score):

- **Face micro-detail, scaled to the shot.** `python tools/build_face_detail.py --shot portrait
  --subject "..." --seed N` prints the detail for that distance: pore-level skin for a close
  shot, zonal skin tone and natural asymmetry for a medium one, and no pores at all for a wide
  one, because the camera cannot resolve them and asking makes the face look over-sharpened.
  Put it in the spec as `"overrides": {"face_detail": ["<phrase>"]}`. In the app it is on by
  default (Images → Subject → *Face micro-detail*).
- **Lived-in evidence.** `python tools/build_evidence.py --subject "..." --seed N` (or
  `--kind human --detail sunglasses-dent --detail hair-tie`) prints two or three small details
  that have a cause: evidence, not random imperfection. Put it in the spec as
  `"overrides": {"evidence": ["<phrase>"]}`. In the app: Look → Evidence, or the *Lived-in
  details (auto)* toggle.

- **Light from the scene.** Add `"scene_lighting": true` to the spec and, with no explicit
  lighting, the light is picked from what can exist in the Setting (a bar at night never gets
  golden-hour sun), the source is named, light bounces off the materials the Setting mentions,
  and the shadows are kept consistent. `python tools/build_scene_light.py --setting "..."`
  shows what it will do, and `--lighting "..."` checks an explicit choice against the Setting.
  On by default in the app (Images → Scene → *Match light to the scene*).

The tool assembles all eight layers and appends the negative block. It writes the prompt to
`temp/outputs/prompts/avatar-<slug>-<timestamp>.txt` and prints the next command.

## Step 4 — Lint it

```
python tools/realism_lint.py temp/outputs/prompts/<file>.txt
```

Requirement: **8/8, no banned terms, PASS.** The linter names the missing layer and the exact
phrase to add. Fix and re-run until it passes. Do not hand the user a prompt that hasn't passed.

## Step 5 — Generate

Paste the prompt into Nano Banana Pro. Or, once a key is in `.env`:

```
python tools/generate_image.py --provider kie --prompt-file temp/outputs/prompts/<file>.txt
```

Save what comes back into `temp/outputs/images/` with the same slug.

## Step 6 — Review, and fix the *prompt*

Check the result against this list:

- [ ] Visible skin pores and micro-texture — not smooth or waxy
- [ ] Real imperfections: a blemish, faint redness, eye bags, stray hairs
- [ ] Light has a believable direction, with shadows that fall correctly
- [ ] Colour is restrained — no glow, no over-saturation
- [ ] Eyes and teeth look photographed, not drawn
- [ ] Hands, if visible, are correct
- [ ] Overall it looks *captured*, not rendered

When something fails, name the layer to strengthen and rebuild:

| What's wrong | Layer to push |
|---|---|
| Plastic, waxy, airbrushed skin | **texture** — pores, imperfections, micro-details |
| Looks like a 3D render | **camera** + **grain** — name a real camera, add film grain |
| Flat or glowing light | **lighting** — soft natural daylight, realistic shadows |
| Too colourful, too clean | **colour** — muted tones, natural grading |
| Feels posed and fake | **composition** — candid, unstaged, eye-level |

## Step 7 — Log it

Append to `temp/outputs/avatar-log.md`: the slug, the prompt, the score, and one line on
whether the image worked. Good prompts are the asset — this is what makes the next avatar
faster than this one.
