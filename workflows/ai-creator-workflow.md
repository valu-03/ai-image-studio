# Workflow: The AI Creator Workflow — the whole pipeline, in order

**Goal:** know which stage you're in, and what "done" looks like at each one, before jumping
ahead. This is an overview, not a new procedure — every stage below is already a real workflow
or tool; this doc just states the order and the one rule that ties them together.

**Source:** AI Video Bootcamp's *"The AI Creator Workflow"* lesson: *"generating is step three
of a six-step process... Idea → Chat → Image → Refine → Video → Edit & Post."* Also draws the
per-platform aspect-ratio guide from the course's *"AI Models"* lesson.

**Inputs:** an idea (a sentence is enough).
**Outputs:** a shipped piece of content — a still, or a still plus a clip, depending on where
the pipeline ends for this asset.

---

## The six stages, and where each one already lives in this app

| # | Stage | What "done" looks like | Where it happens here |
|---|---|---|---|
| 1 | **Idea** | A specific outcome, not a vague desire — what you're making, for whom, on which platform | Step 1 of [create-realistic-avatar.md](create-realistic-avatar.md), or just a one-line brief |
| 2 | **Chat** | The idea developed into a real spec — subject, wardrobe, setting, action, mood, shot | **Images → Auto-fill** (`tools/brief.py::spec_from_idea`/`autofill_spec`), or a real back-and-forth in **Assistant → Chat** ([ask-the-advisor.md](ask-the-advisor.md)) |
| 3 | **Image** | A prompt that scores **8/8, no banned terms** on `tools/realism_lint.py` | Steps 3–5 of [create-realistic-avatar.md](create-realistic-avatar.md) |
| 4 | **Refine** | Specific issues fixed, then upscaled to 4K *before* it goes anywhere near video | Compose's **Refine** button (`tools/refine_image.py`) for realism fixes, then `tools/upscale_image.py` — "upscale before you animate," verbatim from the bootcamp's own upscaling lesson |
| 5 | **Video** | A camera move chosen to fit the still, not the other way round | [image-to-video.md](image-to-video.md) — read its "the order is backwards from what you expect" note first |
| 6 | **Edit & Post** | Pacing, captions, sound, export | **Not this app.** CapCut (or your own editor) is external, on purpose — this app writes prompts and generates stills/clips, it doesn't cut timelines |

Stage 6 is the one deliberate gap: it's named here only so the pipeline reads as one thing end to
end, not because it's missing from this app by oversight.

## The one rule that applies at every stage

> **If the composition, character, concept or camera angle is fundamentally wrong, go back and
> fix the prompt. Don't spend time editing, retrying, or upscaling a broken image.**

This is the bootcamp's own rule from the Refine stage of its lesson, generalised: it isn't only
about image editing — the same judgement call applies whenever a result "just feels off." The
existing, narrower version of this already lives in
[create-realistic-avatar.md](create-realistic-avatar.md)'s header (*"don't substitute another
model because a result came back looking fake — fix the prompt instead"*) and its **Step 6**
review checklist, which names the exact layer to strengthen and rebuild from. Use that table to
decide what to fix before reaching for Refine or Upscale — both cost a real generation, and
neither can fix a prompt whose subject, setting or composition was wrong from the start.

## Aspect ratio — already automatic, just worth knowing

Picking a `purpose` in Compose already sets the right aspect ratio for you
(`tools/prompt_bank.json`'s `purposes` table, applied by `build_prompt.apply_purpose()`); an
explicit aspect pick always wins over the purpose's default. The bootcamp's own simple rule,
for reference:

| Ratio | Use it for |
|---|---|
| **9:16** | TikTok, Reels, Shorts — short-form vertical video |
| **4:5** | Instagram feed posts, static ads, influencer photos |
| **1:1** | Safe, simple, works-almost-everywhere graphics |
| **16:9** | YouTube, websites, cinematic horizontal content |
