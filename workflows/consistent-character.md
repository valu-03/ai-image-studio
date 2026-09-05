# Workflow: Consistent character across shots

**Goal:** take one avatar you're happy with and put *that same person* in new
scenes, outfits, angles and lighting — without the face drifting.

**Source:** AI Video Bootcamp Phase 5 (SHAPESHIFTER), built on the Phase 2 realism method.

**Inputs:** a character spec, and one image of that character you're happy with.
**Outputs:** a reference-locked spec, and a set of shots that are recognisably one person.

**Prerequisite:** finish [create-realistic-avatar.md](create-realistic-avatar.md) first.
You cannot lock a face you haven't produced yet.

---

## The mechanism

Consistency is not a prompt trick — it is a **reference image passed to the model
alongside the prompt**, plus language telling the model the face is fixed. Both halves
are required. The prompt alone will drift; the image alone gets restyled.

`build_prompt.py` supplies the language (`--lock-identity`), `generate_image.py`
supplies the image (`--reference`).

## Step 1 — Choose the hero image

Pick the single best image of the character. It becomes the source of truth for that
face. Front-facing, evenly lit and sharp beats dramatic — the model needs to read the
bone structure, not admire the shot.

Copy it somewhere durable:

```
temp/resources/characters/<slug>-ref.png
```

`temp/outputs/` is disposable. A reference image is an asset — it does not live there.

## Step 2 — Attach it to the spec

Add to `temp/resources/characters/<slug>.json`:

```json
"reference": "temp/resources/characters/<slug>-ref.png",
"lock_identity": true
```

In the GUI: **Compose → Set reference**. The caption changes to
"Identity locked to …" and the prompt gains the lock clause immediately.

## Step 3 — Describe the variation, not the person

This is the step people get wrong. Do **not** re-describe the face — that invites the
model to reinterpret it. Change only what should change:

```json
"variation": {
  "shot": "talking-head",
  "wardrobe": "a charcoal wool coat",
  "setting": "a rainy city street at dusk",
  "action": "walking toward camera mid-sentence"
}
```

`apply_variation()` folds these over the base spec, leaves `subject` untouched, and sets
the identity lock. The subject line is the identity; the variation is everything else.

## Step 4 — Build and lint

```
python tools/build_prompt.py --spec temp/resources/characters/<slug>.json --lock-identity
python tools/realism_lint.py temp/outputs/prompts/<file>.txt
```

Still 8/8. The lock clause adds identity constraints — it does not excuse a weak prompt.

## Step 5 — Generate with the reference attached

```
python tools/generate_image.py --provider kie \
    --prompt-file temp/outputs/prompts/<file>.txt \
    --reference temp/resources/characters/<slug>-ref.png
```

**This step needs Kie.** Kie takes reference images as URLs, so the file is uploaded first
and the returned URL travels with the prompt. Higgsfield's Soul endpoint has no reference
input at all, so the same command there is *refused* rather than sent without the face.

That refusal is deliberate. **Omitting `--reference` silently produces a different person** —
the lock language alone cannot do it — so a provider that would quietly ignore one is the
same bug wearing a different hat.

## Step 6 — Judge identity, not quality

A shot can be beautiful and still be the wrong person. Check, in this order:

- [ ] Eye shape, spacing and colour
- [ ] Nose bridge and tip
- [ ] Jawline and chin
- [ ] Hairline and hair texture
- [ ] Distinguishing marks — freckles, moles, scars
- [ ] Apparent age — models drift young; this is the most common failure

If identity slipped:

| What drifted | Fix |
|---|---|
| Face subtly different | Use a cleaner, more front-facing reference |
| Looks younger / airbrushed | The lock sentence covers this — check it survived into the prompt |
| Right face, wrong vibe | Change `mood` and `action`, not `subject` |
| Drifts only in one setting | That setting's lighting is fighting the reference; change the lighting term |

## Step 7 — Rate it

Rate the shot in the GUI, or `python tools/history.py rate <id> <1-5>`. Consistency
runs are the most valuable ratings you have — they are the ones where you know exactly
what the right answer looked like.

## Step 8 — Build the set

Repeat steps 3–7 per shot. A usable character set is roughly:

- one clean portrait (the reference itself)
- one three-quarter and one profile
- two environments with different lighting
- one selfie-framed shot for UGC use

Once that set exists and holds together, you have an AI influencer rather than a
one-off image, and the Phase 6 ad workflows become possible.
