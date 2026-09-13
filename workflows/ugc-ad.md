# Workflow: UGC advert

**Goal:** a five-beat short-form advert where one presenter carries every shot, the product
lands on time, and the ad passes its own checklist before a single credit is spent.

**Source:** AI Video Bootcamp Phase 6 — *AI Advertisement Workflow Checklist*, the *Social
Media AD Structure*, and the five-step method: know your target · format and placement ·
A/B testing · sell the feeling · speed and scale.

**Inputs:** a product, an audience, a platform, and a presenter (a character spec).
**Outputs:** five timed shots with copy, prompts and camera moves — and, if you want them, five
generated stills of the same person.

---

## The rule that decides the whole thing

The checklist asks one question that is mechanically checkable:

> *"Is your product or offer shown within 5–10 seconds?"*

Beat 4 is the product. Split five beats evenly across a 30-second ad and beat 4 starts at
18 seconds — the ad fails its own checklist while looking perfectly well formed. Even a
front-loaded 52% split puts it at 31 seconds in a minute-long ad.

**So the setup is capped in absolute seconds, not shared as a percentage.** Beats 1–3 get at
most 9 seconds between them however long the ad is, and beat 4 absorbs the rest — because the
product demonstration is the part that should grow with the runtime. The hook and the CTA do
not need more room in a longer ad.

The timeline strip on the Storyboard tab draws that deadline. If the green marker sits left of
the product block, the ad is late.

## Step 1 — Know your target

**Ads → Brief.** Product, then audience in the specific: age, the pain, what they have already
tried and why it failed. "Women 25–40" is a demographic; "women who have already bought three
shampoos that made it worse" is an audience.

**Optional — a product photo.** Attach one alongside the presenter's own locked identity, and
it rides along too, from beat 2 on (beat 1 has nothing generated yet to lock to). This is the
same split the AI Video Bootcamp Skool's avatar-ad prompt craft teaches for Seedance — a
character reference for identity, a separate product reference for exact packaging, colour,
label and logo — applied here through this app's own existing multi-reference generation
(Kie/Nano-Banana-Pro), not anything Seedance-specific.

## Step 2 — Format and placement

Pick the platform. It sets the aspect ratio, the length, the hook window and the pacing, and it
maps to a `purpose` in the image bank so the shots come out framed for where they will run.

| Platform | Shape | What it wants |
|---|---|---|
| TikTok / Reels | 9:16, 15–30s | vertical, fast, hook first — native beats polished |
| YouTube | 16:9, 30–60s | longer, value-driven, storytelling |
| Instagram | 4:5, 15–30s | aesthetic, polished, brand-heavy |
| Meta / Google | 4:5, 15–30s | transactional, clickable, concise |

The same ad is not the same ad on two of these. Change the platform and re-read the beats.

## Step 3 — Write the five beats

Either type them, or press **Draft the copy with AI** and let OpenRouter propose them — every
reply is re-scored by `ad_lint` before it is accepted, so the model suggests and the gate
decides, exactly as on the image side.

| # | Beat | What it must do |
|---|---|---|
| 1 | Call out the pain | The specific daily version of the problem, not the category |
| 2 | Make it relatable | Name what they already tried and why it failed |
| 3 | Offer a shift | Turn it around — without naming the product yet |
| 4 | Introduce the product | Name it, then say plainly what it is |
| 5 | Proof and urgency | Numbers **and** a reason to act now |

## Step 4 — Sell the feeling, in the right places

Beats 1–3 are written in feeling. Beat 4 is where specifications belong — *"zero sulfates,
zero harsh chemicals"* is correct there and wrong in beat 1. The linter is scoped accordingly:
it fails an ad that **opens** on a spec sheet, and leaves beat 4 alone.

Beat 5 is two requirements. Proof without urgency is the common failure, and it reads finished.

## Step 5 — Read the gate before generating anything

**Ads → Storyboard.** Nine checks, all named. Green means the ad is structurally sound; a red
row tells you which beat and what to change. Fix it here — the prompt costs nothing and the
image costs a credit.

## Step 6 — A/B the hook

**Ads → Variants.** Write three competing openers and check them together. The hook is the only
part worth testing first: everything after it is only seen by people the hook already kept.

## Step 7 — Generate, at speed

**Generate all five shots.** Beat 1 creates the presenter; beats 2–5 lock to that face through
the reference machinery, so it is one person across the ad rather than five strangers. If a
product photo was attached in Step 1, those same four beats carry it too, alongside the face.

**This needs Kie.** Higgsfield's Soul endpoint takes no reference image, so the app refuses the
batch there rather than quietly producing five different people.

## Step 8 — Work the checklist

**Ads → Checklist.** Ticked rows are checked by the app. Open rows are yours — whether a client
approved it, whether the visuals stop a scroll, whether you previewed on a phone. The split is
deliberate: a checklist that claims to have verified something it has not is worse than none.

## Step 9 — Publish

**Ads → Publishing** is reference only, in the way the film glossary defines terms without
acting on them. Export 1080p30 rather than 4K60, four hashtags at most, first clip under three
seconds, watch time is the metric that matters.

| What went wrong | Fix |
|---|---|
| Nobody watches past the first second | The hook is the problem, not the offer. Rewrite beat 1 and A/B it |
| It feels like an advert | Beats 1–3 are selling features. Move them to beat 4 |
| Views but no clicks | Beat 5 has proof and no urgency, or there is no CTA |
| The presenter changes face | The reference did not travel — check the provider supports it |
| The product arrives too late | Shorten the ad, or check the timeline strip against the 10s line |

## What is not here

Clip generation, voice and editing. The app produces stills, prompts and structure; assembly
happens in CapCut, and the motion prompts go into Kling by hand (see `image-to-video.md`).
