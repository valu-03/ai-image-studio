# Workflow: Relighting and camera angles

**Goal:** take one existing photo and produce new versions of it — different lighting,
different camera angle, or both — without inventing a new scene.

**Source:** AI Video Bootcamp Phase 3, two real, distinct lessons applied together —
*Image Editing With Nanobanana* (existing-photo relighting/re-angling) and *Creating AI
Avatars* (its multi-angle turnaround-sheet technique). Neither lesson names a single
"relight-and-angles" technique; this workflow is an honest synthesis of the two, not a
transcription of one unified lesson. See `tools/relight_bank.json`'s own `source` field
for the exact quotes.

**Inputs:** a spec describing one existing photo, and the photo itself.
**Outputs:** a scene-locked spec, and a batch of relit/re-angled prompts (and stills,
once generated).

---

## The mechanism

This is the **inverse** of [consistent-character.md](consistent-character.md)'s lock.
There, the face is fixed and everything else (scene, wardrobe, pose, angle) is free to
change. Here, the **scene is fixed** — same subject, wardrobe, setting and pose as the
source photo — and only the **lighting and/or camera angle** change.

`build_prompt.py` supplies the language (`--lock-scene`), `generate_image.py` supplies
the image (`--reference`), exactly the same two-halves-required mechanism
consistent-character.md already established — a reference image alone gets restyled;
the lock language alone drifts.

## Step 1 — Choose the source photo

Copy it somewhere durable:

```
temp/resources/images/<slug>-ref.png
```

Front-facing, evenly lit and sharp beats dramatic — the model needs to read the actual
scene, not admire the shot.

## Step 2 — Describe the photo once

Build `temp/resources/images/<slug>.json` with `subject`/`wardrobe`/`setting`/`action`
matching exactly what is in the photo. **Do not add a `variation` block** — that
mechanism exists for describing a *new* scene, and this workflow's whole point is not
describing a new scene.

## Step 3 — Pick what varies

```
python tools/build_relight.py --list
```

Three named sets, sourced differently:

| Set | Varies | Source |
|---|---|---|
| `avatar-turnaround` | angle only (4 shots) | *Creating AI Avatars*' turnaround technique, mapped onto this app's own side axis |
| `relight-pass` | lighting only (4 shots) | *Nanobanana*'s existing-photo relighting demo |
| `full-set` | both together (4 shots) | both lessons combined, one distinct pair per shot |

Or build your own list of shots (any subset of `lighting_setup`/`vertical`/`side`/`size`
per shot — see `tools/build_lighting.py --list` and `tools/build_camera_angle.py --list`
for the vocabulary) and pass it as `--shots <path.json>` instead of `--set`.

## Step 4 — Build

```
python tools/build_relight.py --spec temp/resources/images/<slug>.json \
    --reference temp/resources/images/<slug>-ref.png --set avatar-turnaround
```

## Step 5 — Lint

```
python tools/relight_lint.py --relight temp/outputs/prompts/<file>.json
```

Five checks: realism (8/8, or 7/8 with only the camera layer missing on a shot that
also asked for an angle — the same documented tradeoff `build_camera_angle.py` already
accepts, since its composed phrase can legitimately name no capture device), the scene
lock surviving into the prompt, the requested lighting/angle actually being detectable,
no two shots sharing the same combo, and subject/wardrobe/setting/action staying
byte-identical across the batch.

## Step 6 — Generate

```
python tools/generate_image.py --provider kie \
    --prompt-file temp/outputs/prompts/<shot>.txt \
    --reference temp/resources/images/<slug>-ref.png
```

Once per shot. **This needs Kie**, same as consistent-character.md — Higgsfield's Soul
endpoint has no reference input at all, so the same command there is refused rather than
sent without the source photo.

## Step 7 — Judge

Did *only* the lighting and/or angle change? If the scene itself drifted, the lock
failed, not the generation.

| What went wrong | Fix |
|---|---|
| Wardrobe/setting/pose drifted | The reference photo is too weak, or the scene-lock clause did not survive into the prompt — check Step 5's `lock_scene` result |
| Angle did not read | The picked phrase named no real camera position (the same honest tradeoff `build_camera_angle.py` documents) |
| Lighting looks unchanged | The picked setup is too close to the source photo's own exposure — pick a more different one from `--list` |
| The subject's face looks like a different person | This workflow does not lock identity — if that matters too, use [consistent-character.md](consistent-character.md) instead, or layer both locks deliberately |

Add a row to `workflows/README.md`'s index, status **ready**, once this holds together
on a real photo.
