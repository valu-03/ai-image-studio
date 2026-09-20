# Workflow: Beauty macro and feature inserts

**Goal:** produce a full-face beauty macro, then extreme-macro inserts of that same face's
eye, mouth and cheek — each one recognisably the *same* face, magnified.

**Source:** community-supplied reference material — a four-part macro/beauty-portrait prompt
contributed by the user. **Not AI Video Bootcamp course material**; see
`tools/macro_insert_bank.json`'s own `source` field. The source prompt's "8K" and
"hyper-detailed" framing was deliberately dropped: `tools/prompt_bank.json` already lists both
in `warn` as low-value filler. What was harvested is the physical detail — pore-level skin,
peach fuzz, subsurface scattering, per-zone tonal variation — not the resolution boasting.

**Inputs:** a character spec. For stage two, the generated full-face image.
**Outputs:** up to four macro prompts (and stills, once generated).

**This needs Kie.** The inserts pass a reference image, and Higgsfield's Soul endpoint has no
reference input at all — the same hard dependency `consistent-character.md` and
`relight-and-angles.md` both carry.

---

## The mechanism

This runs in **two stages, and the order is the whole point.**

**Stage one — `full-face` creates the face.** It takes no reference and sets no identity lock,
because there is nothing yet to lock to. This is the photograph the other three are cut from.

**Stage two — the inserts derive from it.** `eye`, `mouth` and `cheek` each require that
generated image as `--reference`, set the identity lock, and carry their own *feature-scoped*
`preserve` phrase. That second, narrower lock is what makes this work:
`build_prompt.LOCK_COMPACT` says "identical face, bone structure, eye colour, hairline, skin
tone and distinguishing marks" — it never says **gaze**, **lip proportions** or **undertone**.
The `preserve` phrase does.

One deliberate difference from [relight-and-angles.md](relight-and-angles.md): there, the
composed camera phrase goes into `shot_custom` and *replaces* the `pick: 1` camera slot, which
is why those angle shots accept 7/8. Here the shot-size phrase goes into the `pick: 2`
composition layer, which **pins** rather than replaces, so the camera slot keeps a real capture
device and every shot holds a **strict 8/8**.

## Step 1 — Describe the face once

`temp/resources/characters/<slug>.json` — `subject` and `mood` only. Do **not** set `shot` and
do **not** add a `variation` block; the tool strips both, because a preset would fight the
composed camera/lens/composition overrides and `variation` exists to describe a *new scene*.

## Step 2 — Generate the full face (stage one)

```
python tools/build_macro_insert.py --spec temp/resources/characters/<slug>.json \
    --set full-face-only
python tools/generate_image.py --provider kie --prompt-file temp/outputs/prompts/<shot>.txt
```

Judge the skin here, before spending three more generations on crops of it. If the pores and
peach fuzz do not read at full-face size, they will not survive magnification.

## Step 3 — Keep the frame you like

Save it somewhere durable:

```
temp/resources/characters/<slug>-face.png
```

`temp/outputs/` is disposable. This image is now the source of truth for stage two.

## Step 4 — Build the inserts (stage two)

```
python tools/build_macro_insert.py --spec temp/resources/characters/<slug>.json \
    --reference temp/resources/characters/<slug>-face.png --set inserts-only
```

Or pick individually: `--insert eye --insert mouth` (repeatable). Omitting `--reference` when
any insert is requested is refused outright, rather than quietly producing a stranger's eye.

| Insert | Frames | Preserves |
|---|---|---|
| `eye` | one eye, brow and cheekbone cropped away | eye colour, eye shape, lash line, **direction of gaze** |
| `mouth` | the mouth, nose and chin cropped away | lip shape, lip proportions, expression |
| `cheek` | one cheek and jawline, no eye or mouth in shot | skin tone, undertone, surface texture |

## Step 5 — Lint

```
python tools/macro_insert_lint.py --macro temp/outputs/prompts/<file>.json
```

Nine checks. Realism is a **strict 8/8** here with no floor — and `no_shot_takes_the_camera_slot`
is what keeps that honest, failing the batch if anything ever reintroduces `shot_custom` rather
than quietly relaxing the gate.

## Step 6 — Generate

```
python tools/generate_image.py --provider kie \
    --prompt-file temp/outputs/prompts/<shot>.txt \
    --reference temp/resources/characters/<slug>-face.png
```

Once per insert.

## Step 7 — Judge

Is it the same person at every magnification, and does the skin hold up under the crop?

| What went wrong | Fix |
|---|---|
| The eye or mouth reads as a different person's | The `preserve` phrase did not survive into the prompt — check Step 5's `feature_scope` row |
| Skin looks plastic or smoothed | The reference image is itself retouched and the lock is faithfully reproducing it. Fix the reference, not the prompt |
| Gaze drifted in the eye insert | The one thing `LOCK_COMPACT` never names; it lives only in the `eye` entry's `preserve` — confirm it is in the text |
| The crop is not tight enough | The framing phrase did not read — tighten that entry's `overrides.composition`, not the `size` key |
| Macro detail reads as noise rather than skin | `beauty-box` is too flat for the cheek insert — swap that entry's `lighting_setup` for `butterfly` or `clam-shell` to rake the peach fuzz across the surface |
| A shot scores 7/8 on camera | Something set `shot_custom` and took the camera slot; Step 5's `no_custom_shot` row names it |
| The whole face changed, not just the crop | This workflow locks identity, not the *scene* — that is [relight-and-angles.md](relight-and-angles.md). Do not layer both; they assert opposite things |
