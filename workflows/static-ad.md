# Workflow: Static ad

**Goal:** turn one product photo into ad-ready composites — a clean studio shot, a
lifestyle shot with a presenter, or both — with the label pixel-legible in every one.

**Source:** AI Video Bootcamp Phase 3, *Avatar Product Images & Wise Chat* — its
technique: send a product image and an avatar/scene reference to an AI chat for a
detailed image prompt, always naming the exact label text, and *"give me a detailed
image prompt where the avatar is holding the product towards the camera making sure the
product label is sharp, readable and consistent."* That lesson does **not** teach a
paired "studio vs lifestyle" ad-type split — this workflow's `studio` mode instead reuses
this app's own existing `studio-lighting` style (`tools/style_bank.json`, sourced from
the course's separate Style Reference Library), not new vocabulary invented for it. See
`tools/static_ad_bank.json`'s own `source` field for the full, honest caveat.

**Inputs:** a product description (with its exact label text) and one product photo.
Optionally, a presenter character spec and reference image for the lifestyle mode.
**Outputs:** a studio composite, a lifestyle composite, or both — prompts and, once
generated, stills.

---

## What is different here

Unlike [ugc-ad.md](ugc-ad.md), there is **no time dimension** — no beats, no seconds, no
platform pacing. This is pure image composition: `tools/build_static_ad.py`
deliberately does not import `build_ad.py`'s `beat_timings()`/`product_starts_at()`.

The product photo rides as a plain reference image — **not** an identity or scene lock.
Packaging/label fidelity is carried by the reference image itself (the same multi-image
conditioning `ads.py`'s own `product_reference` already relies on), not by prompt
language claiming to reproduce a face or a scene.

## Step 1 — Source the product photo

Copy it somewhere durable: `temp/resources/images/<slug>-ref.png`. Straight-on, evenly
lit, label fully legible — the reference image is doing the packaging-fidelity work, not
the prompt.

## Step 2 — Describe the product once

Name it exactly, including the label text: `--product "LumaWash shampoo, 250ml amber
bottle, black cap"`. Vague descriptions produce vague labels.

## Step 3 — (Lifestyle only) Choose a presenter

Optional. Pass `--spec <character spec>` for a specific presenter, and
`--presenter-reference <path>` to lock their identity across the shot. Without either,
the lifestyle shot uses a plain, unnamed person.

## Step 4 — Build

```
python tools/build_static_ad.py --product "LumaWash shampoo, 250ml amber bottle" \
    --reference temp/resources/images/lumawash-ref.png
```

`--mode studio`, `--mode lifestyle`, or the default `both`. Lifestyle's `--setting`
defaults to the lesson's own worked example — a bright, modern kitchen — and is free
text, same as anywhere else in this app; the course never taught a closed list of named
lifestyle scenes.

## Step 5 — Lint

```
python tools/static_ad_lint.py --static-ad temp/outputs/prompts/<file>.json
```

Five checks: every requested mode present, realism 8/8, the label-accuracy instruction
present in every shot, a reference image actually attached to every shot, and no
presenter-less (studio) shot accidentally carrying an identity or scene lock.

## Step 6 — Generate

```
python tools/generate_image.py --provider kie \
    --prompt-file temp/outputs/prompts/<shot>.txt \
    --reference temp/resources/images/lumawash-ref.png
```

For a lifestyle shot with a presenter, attach both references — presenter first, product
last — `--reference <presenter>.png --reference <product>.png` — the exact order
`build_static_ad.py`'s own `references` list already carries. **This needs Kie**;
Higgsfield's Soul endpoint takes no reference image at all.

## Step 7 — Judge

Is the product itself pixel-faithful — label legible, correct shape and colour — not
just "looks nice"?

| What went wrong | Fix |
|---|---|
| Label text warps or is missing | The reference photo is too low-res or off-angle, or add an explicit "the label reads exactly '...'" phrase |
| Wrong bottle shape/colour | Re-shoot the reference straight-on, or try the other provider |
| The lifestyle scene swallows the product | Strengthen the composition, or switch to `studio` mode |
| The presenter's face keeps changing | Pass `--presenter-reference` — without it, "a plain, unnamed person" is exactly that, a new person each time |

## What is not here

No automated pixel-diff against the source photo — that judgment stays manual, the same
caveat ugc-ad.md's own "What is not here" section gives for clip assembly.

Add a row to `workflows/README.md`'s index, status **ready**, once this holds together
on a real product photo.
