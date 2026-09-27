# Workflow: cat story video

**Goal:** a short-form cat video that someone watches to the end. Two different genres live
under this one workflow now — pick the **Format** first, everything else follows from it.

| Format | What it makes | Shape |
|---|---|---|
| **Story** | a narrative arc — one cat, an idea escalating over 5-9 scenes | captions, narration, a different camera move every scene |
| **Working cats** | two cats in costume doing a real job until it goes wrong | one **locked-off** take per gag, no words at all |

**Source:** the Kling movement toolkit and the realism vocabulary the Story format builds on
are from the course (`motion_bank.json`, `prompt_bank.json`). **Neither format's structure is
transcribed from the course.** The course's *Cats Niche*, *Storytelling & Scriptwriting* and
*Mastering CapCut* lessons are video files, and the Phase 9 PDFs are caption pages. The
**Working cats** format is not general craft either — it was **measured**: four AI cat videos
in `Downloads/video` were frame-sampled and cut-detected (`ffmpeg select=gt(scene,0.1)`),
which found *zero cuts* inside two of them and one in a third. Every reference video is a
single unbroken take with the camera locked off. `story_bank.json`'s `formats.trade` block —
the default 10-second clip, the locked-off camera phrase, the costume-and-job vocabulary in
`trades` — encodes exactly that, not an invented idea of the genre.

**Inputs:** a format, an idea, the cast (a cat, or a pair), and a place.
**Outputs:** N scenes with still prompts and motion prompts (plus captions and narration for
Story); a sound sheet; and a CapCut edit sheet with the trim points.

---

## The rule the whole section turns on

**A scene is exactly one clip.** Kling 3.0 generates any whole second from 3 to 15, so the
clip length is what the scene keeps, rounded up to a second. The hook window is 3 seconds and
3 is also Kling's minimum, so the opening is a real 3-second clip with nothing thrown away.

What absorbs a long runtime is the **scene count**, not the scene length:

| You choose | The app derives |
|---|---|
| the arc | the *shape* — hook, setup, escalation, twist, payoff |
| the runtime | how many scenes that shape needs |
| the clip length | the ceiling on any one scene |

A 30-second Classic at 5-second clips is **seven** scenes, because the repeatable Escalation
beat repeats until nothing needs longer than one clip. Ask for shorter clips and you get more
scenes; ask for longer ones and you get fewer, longer takes.

> **This is the bug that was here.** An earlier version kept the scene count fixed at the
> arc's beats and stretched each scene instead, computing `clip = length x ceil(share/length)`.
> Short at the default 30 seconds produced **three scenes of 15 seconds** — a length no video
> model will generate. The gate missed it because it accepted any *multiple* of a legal length,
> and the test asserted the same wrong rule. Three things agreed with each other and all three
> disagreed with Kling.

The timeline on the Scenes tab still draws both bars — what you generate on top, what survives
underneath — and the gap between them is now a rounding rather than half your money. The panel
prints the ratio; anything above 1.3x means the plan is buying seconds it discards.

## Step 1 — Pick the format, then the cast, the place, the shape

**Cats → Story → Format.** This decides almost everything else on the tab.

### Story

Describe the cat once; it is locked across every scene from here on.

| Arc | Scenes | When |
|---|---|---|
| Short | 3 | hook, escalation, payoff. Hardest to get wrong |
| Classic | 5 | the default: setup, escalation, turn, land it |
| Escalating | 7 | three rising escalations — each must top the last |
| Epic | 9 | only when the escalation genuinely has four steps |

The number in that table is the shape's *minimum*. The runtime and the clip length decide how
many scenes it actually becomes — see the rule above.

**Pick the look.** *Photoreal* is a real-looking cat committing completely to a human goal —
it reuses the 8/8 realism gate, **scored as an animal**. *Stylised* is a 3D
animated short-film look, and it is judged by its own check, because every word of it
(`3d render`, `animation`, `cartoon`) is on `realism_lint`'s banned list and correctly so.
**One look per story.** A photoreal cut next to an animated one reads as a mistake.

**Why "as an animal" is a separate mode.** `realism_lint` is a human-portrait detector, and
pointed at a cat it was *inverted*: a prompt naming guard hairs, vibrissae and nose leather
scored 7/8 and failed, while this app's own cat scenes — which opened with "realistic skin
textures of a ginger tabby cat" — passed at a full 8/8. Deleting every fur phrase from the
photoreal style changed that score by nothing, because none of them scored anything. The
photoreal style now declares `subject_kind: animal`, which routes two things:

- **The gate** swaps its `core` and `texture` layers for coat vocabulary (`guard hair`,
  `undercoat`, `vibrissae`, `nose leather`, `tapetum`) and *bans* the human-anatomy words
  that are simply wrong on an animal — `skin pores`, `hairline`, `skin tone`. The human key
  lists are untouched, so no human prompt scores differently. Switching, not widening.
- **The identity lock** becomes `LOCK_ANIMAL_COMPACT`. Every locked cat scene this app built
  before used to say *"the exact same **person** … identical face, bone structure, eye colour,
  **hairline**, **skin tone**"*. It now names what actually holds a cat together across shots:
  coat pattern and markings, eye colour, ear shape and notches, tail length and kink, muzzle
  and chin colouring.

The coat vocabulary itself lives in `tools/pet_realism_bank.json` and is **keyed into**, never
copied — the same rule `macro_insert_bank.json` follows for lighting. `tests/test_pet_realism.py`
checks every phrase is visible to the gate, per phrase, because a bank the gate cannot see is
decoration, which is exactly what the four phrases it replaced turned out to be.

### Working cats

Describe **the pair**, not one cat — the field relabels itself to "The cats" and the placeholder
shows the shape ("two cats - a broad grey tabby and a lean ginger tom"). One reference image
carries both, the same identity-lock machinery Story uses, applied to a pair instead of one.

**Pick the job.** The **Job** combo fills the costume, the location and the props from
`story_bank.trades` — construction, woodcutting, kitchen, garage, delivery or farm. Anything
you have already typed in Where or the script survives; the trade only fills what is blank.

| Arc | Takes | When |
|---|---|---|
| One take | 1 | a single ~10s gag — most of the reference videos are exactly this |
| A shift | 2 | two tasks, two mishaps — the reference construction video, exactly |
| A day's work | 4+ | arrive, work, work, sit in the wreckage |

There is no look to pick — every reference video is photoreal, and the camera is **always**
locked off. That is not a default you can turn off; it is what the whole format is.

## Step 2 — Write the scenes

Either type them, or press **Auto-fill the whole story**. From the idea it invents the cast and
the place *if you have left them blank* (one cat for Story, a pair for Working cats), then
writes every scene — two model calls, because casting an animal and writing a story are two
different jobs. **Anything you have already typed survives** and becomes part of the brief for
the rest, exactly as the Compose auto-fill behaves.

The script box's own fields switch with the format:

- **Story**: `caption` (on-screen text), `narration` (one spoken line), `action`
- **Working cats**: `task` (the job), `mishap` (the one thing that goes wrong) — nothing else.
  Nobody speaks in these videos, and there is nothing on screen to read.

Every reply is re-scored by `story_lint` before it is accepted, and the model can set only the
subject, the setting and the scene words — never `seed`, `reference`, `lock_identity` or
`overrides`. A near miss is shown as a draft with the failing rows named, not thrown away.

**Actions (Story) or tasks (Working cats) must differ between scenes.** Repeating either is
one shot playing twice, and it is where people scroll. The gate checks it either way.

## Step 3 — Read the gate before generating anything

**Cats → Scenes.** Twelve checks — but not the *same* twelve. A format's checks replace the
default list rather than adding to it, because some of Story's rules describe something
Working cats deliberately does not do.

| Story only | Why |
|---|---|
| Opens in 3 seconds | the hook window, judged against captions/narration |
| Camera varies | a different move every scene is the point |
| Narration and captions | words are how Story tells you what is happening |

| Working cats only | Why |
|---|---|
| In uniform | an undressed cat is just a cat video — the costume is the genre |
| Two cats in frame | the comedy is the pair, not one animal alone |
| The camera holds still | every reference video is a single locked-off take |
| A different job each take | two takes of the same job is padding |

Shared checks worth understanding either way:

| Check | Why it exists |
|---|---|
| Real clip lengths | there is no 7-second clip; you find out at the provider |
| Opens in 3 seconds | Kling's 5s minimum hides this one |
| Adds up to the target | otherwise the timeline is a guess |
| One cat throughout | scenes 2..N lock to scene 1's face |
| Camera varies | the same move twice running reads as one long drift |
| Moves suit the stills | reuses `build_motion.check_compatibility()` |
| Something new each scene | the actions-repeat failure above |

A red row names the scene and what to change. Fixing it here costs nothing; fixing it after
generating costs a clip.

## Step 4 — Generate the scenes

**Generate every scene.** Scene 1 creates the cat; every later scene locks to that face
through the reference machinery.

**This needs Kie.** Higgsfield's Soul endpoint takes no reference image, so the batch is
refused there rather than quietly producing nine different cats.

## Step 5 — The clips

**Cats → Prompts** shows both prompts for every scene: the still that went to Nano Banana Pro,
and the Kling prompt built by `build_motion`, leading with the camera move as the toolkit
requires. Both are copyable, so pasting them in by hand is always an option.

**Generate the clips** does it for you. Each clip starts from **that scene's generated still**
— image-to-video is what keeps one cat across the cuts — and runs for exactly the
`clip_seconds` the plan assumed, so the timeline and the request cannot drift apart.

| Option | Default | Why |
|---|---|---|
| `mode` | `std` | `pro` and `4K` are higher tiers and cost more per second |
| `sound` | off | Kling's own audio roughly doubles the price, and fights the ElevenLabs layers |

The line under the button says what the batch will cost and what the balance is, and nothing
is submitted until that is confirmed. **The estimate is seeded from a published price list**
(`tools/pricing.json`, stamped with its date) — the first real job replaces it with the figure
the provider actually charged.

## Step 6 — Sound

**Sound → Scenes** builds three prompts per scene: ambience, key effect, accent. See
`sound-design.md`. Generate them in ElevenLabs and keep them in three separate tracks.

## Step 7 — Assemble in CapCut

**Cats → CapCut** prints an edit sheet for *this* story: which clip, which seconds of it to
keep, the caption (Story) or the task/mishap (Working cats), the three sound layers, and the
cut into the next scene. The export settings on it are read from `ugc_bank.publishing` — the
same numbers the ads section uses, not a second copy.

**The steps panel switches with the format too** — `story_bank.formats.trade.capcut` replaces
the bank's default steps rather than adding to them, because "trim to the hook, 3 seconds" and
"add the caption per scene" describe rules Working cats is not judged by. Its own steps talk
about picking the take and cutting on the reaction instead.

The two that matter most, either way:

- **Cut on motion, not on silence.** A cut while something is still moving is invisible; a cut
  on a still frame reads as a mistake.
- **Let the sound cross the cut.** Pull the next scene's audio a few frames ahead of its
  picture. It is the cheapest thing that makes an edit feel professional.

And then watch it once on mute. Most people will — Working cats has no caption to fall back
on, so if the costume and the job are not readable from the first frame alone, it needs a
wider shot or a longer hold before the mishap.

---

## When it does not work

| What went wrong | Fix |
|---|---|
| Nobody watches past the first second | The hook is the problem. It is 3 seconds — rewrite it, do not lengthen it |
| It feels slow | You kept the whole clip. Check the trims on the CapCut sheet |
| The cat changes between shots | The reference did not travel — you were not on Kie |
| The camera barely moves | The move was buried mid-prompt; it must be the first words |
| It reads as five clips, not a story | The actions are too similar. The gate flags this |
| It cost more than expected | 10-second clips. The Scenes tab prints the ratio |

## What is not here

Clip generation and video assembly. The app produces stills, prompts, structure and an edit
sheet; Kling makes the clips and CapCut cuts them together.
