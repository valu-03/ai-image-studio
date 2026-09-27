# Capture realism — making it look like a camera took it

**Status:** ready
**Tools:** `tools/build_capture.py`, `tools/capture_lint.py`, `tools/capture_bank.json`
**Section:** Look → Capture

## What this is for

Every other toolkit in this app describes the **subject** and the **scene** — how it is lit,
framed, posed, graded. None of them describe the **capture**. A repo-wide grep across every
bank returned zero hits for chromatic aberration, halation, veiling glare, vignetting, barrel
distortion, ISO, shutter speed, white balance, motion blur and sensor dust, and no film stock
was nameable anywhere.

So output topped out at *"well-lit studio photograph"* — clean, plausible, and with nothing in
it saying a physical camera was ever involved. That absence is most of what remains between a
good generation and a photograph.

Two stranger cases the same grep turned up: `subsurface scattering` and `sensor noise` were
already `realism_lint` DETECT keys — the gate could **see** them, but they appeared in no bank,
so the builder could never **write** them. `tools/upscale_image.py`'s `UPSCALE_PROMPT` likewise
carries `hair strands` and `fabric fibers` that exist nowhere else as composable terms.

## The four groups

| Group | Strengthens | Pick |
|---|---|---|
| **Film stock** | `grain` | at most one — two stocks contradict each other |
| **Lens artefacts** | `lens` | stack freely, they are independent properties of glass |
| **Exposure and sensor** | `grain` (and `lighting`, `colour`) | stack freely |
| **Evidence of a hand** | `composition` | stack freely |

Two options override their group's layer, because a group layer is a default rather than a
claim about every option in it: **tungsten white balance** is colour temperature and belongs to
`lighting`; **highlight rolloff** is tonal and belongs to `colour`.

## Steps

1. **Pick the stock first, if you want one.** It is the broadest decision — a stock implies a
   whole grain structure, colour response and highlight rolloff in two words. Portra 400 is the
   portrait default; CineStill 800T is night and neon; Tri-X 400 is documentary monochrome.
2. **Add artefacts sparingly.** Real ones are faint. `build_capture.compose_capture()` warns
   past four stacked artefacts, and `capture_lint.py` enforces that every phrase in the bank is
   *hedged* — "faint", "subtle", "slight" — so the vocabulary cannot drift toward "heavy
   halation, extreme vignetting" one well-meaning edit at a time.
3. **Apply to Compose.** Unlike every other toolkit, this emits a `{layer: [phrase]}` dict
   rather than one phrase, because a single selection can strengthen `grain`, `lens`,
   `lighting` and `colour` at once. `SpecEditor.set_capture_overrides()` **merges** it with
   whatever the form already says rather than replacing — "shot on Portra 400" does not cancel
   "soft window light", both are true at the same time.
4. **Check the gate.** The prompt must still score 8/8. It will: every one of the bank's
   phrases is detectable by the layer it claims, which is what `capture_lint.py` verifies.

```bash
python tools/build_capture.py --list
python tools/build_capture.py --film-stock cinestill-800t --optic veiling-glare
python tools/build_capture.py --film-stock portra-400 --exposure tungsten-wb --overrides
python tools/capture_lint.py            # 19/19 options clean, exit 0
```

## Why a separate bank

`prompt_bank.json` could not take this vocabulary. It is hash-pinned by `tests/test_story.py`,
and bumping its `version` makes `history.usable()` discard every rated entry recorded against
the old vocabulary — silently resetting the UCB1 weights behind "prefer learned terms". A
separate bank with its own builder costs neither, and is the pattern `lighting_bank.json` /
`color_bank.json` / `style_bank.json` already set.

## The rule this bank is built around

**Vocabulary a bank can write but the gate cannot see is decoration.** `story_bank.json` once
carried four phrases that read exactly like fur vocabulary and scored nothing at all — deleting
all four changed the scene's 8/8 by nothing. `capture_lint.py` exists so this bank cannot
repeat it: every phrase is checked against the layer it claims, per phrase, audited rather than
assumed.
