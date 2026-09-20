# Pet sitcom series

**Makes:** one 15-second episode of a repeating two-character pet comedy — five stills, five clips,
a five-layer sound sheet, a CapCut edit sheet, and the post to put it out with.

**Inputs:** a cast, a premise, and the words for five stages.

**Not pure transcription.** This workflow and the `sitcom` format encode a series brief supplied by
the user, not an AI Video Bootcamp lesson. `tools/story_bank.json`'s `formats.sitcom.source` says so,
and so do `tools/safety_bank.json`, `tools/pet_sound_bank.json` and `tools/social_bank.json`. The
Kling camera rules it inherits through `motion_bank.json` *are* course material; nothing else here is.

---

## The mechanism

A series is recognisable because three things never change: who is in it, what room it happens in,
and the shape of the joke. The format holds all three.

**The shape** is five stages across 10–15 seconds — hook, tantrum, discipline, reset, lecture. At the
format's default of 3 seconds a stage, a 15-second episode generates exactly 15 seconds and throws
none of it away. That is the only lossless length; a 10-second episode generates 15 and bins a third
of it, which the Scenes tab's cost note will tell you.

**The cast** is a named entry in `story_bank.json`. Two cats reach the model as ONE subject string
starting with the word "two" — the mechanism the `trade` format proved — plus a relative-scale
sentence riding `spec["extra"]`. That scale sentence is load-bearing: an identity lock describes one
subject and carries no notion of the ratio between two, so without it the kitten drifts to the size
of its mother and the visual joke disappears.

**The room** is the cast's `setting`, and the camera is locked off for every take. A push-in re-stages
the living room every episode; holding still is what makes ten videos look like one show.

**The gate is different from every other format's.** `sitcom` is the only one that runs
`safety_lint.py`, the app's first content check. Every other linter here judges how an image is made;
this one judges what it depicts — injury, distress, hazards, and contact that nobody softened.

---

## Steps

### 1 — Pick the cast and the premise

**Cats → Story.** Set Format to *Pet sitcom*. The Cast row appears:

- **The kitten and the mother cat** — the brief's default pair.
- **Tommy (solo, with an unseen owner)** — one cat, with the foil played by an unseen owner's hand.
  The brief sanctions this ("an unseen owner's hand confiscating a phone"), and it is what makes a
  solo cast work at all: something has to deliver the discipline beat.

Then pick a **Premise**. Fifty seeds ship in the bank; picking one fills the Idea box. It is a
starting point, not a script.

### 2 — Write the five stages

Either type them into the script box, or press **Auto-fill the whole story**.

One block per stage, headed `[hook]`, `[tantrum]`, `[discipline]`, `[reset]`, `[lecture]`. Each takes
three fields:

```
[discipline]
caption: Bap.
lead_action: still mid-roll, all four paws in the air
foil_action: delivering one soft cartoon-like paw tap, claws in
```

`lead_action` and `foil_action` are authored separately and joined into one action clause with
"while", because `build_prompt` renders exactly one action and two characters need two.

**Say the contact is soft in the same phrase as the contact.** `safety_lint` scans staging fields for
a contact word without a softener beside it, and "swatting the kitten off the table" fails where "a
soft cartoon-like paw tap, claws in" passes. The scope is per field on purpose: a "soft daylight" in
the setting cannot vouch for a swat in the action.

### 3 — Read the gate

**Cats → Scenes.** Sixteen checks for this format. Four are its own:

| Check | What it means |
|---|---|
| The cast turns up | Every on-screen member's token survived into the subject. An offscreen hand is exempt — it has an action but nothing to appear as. |
| Relative size is stated | Two characters need their size gap named. Passes trivially, and says so, for a solo cast. |
| Every scene is captioned | Built to read on mute. Narrower than the story format's `words`, which also wants narration this format does not have. |
| Nothing depicted is harmful | `safety_lint`: injury, distress, hazard, unsoftened contact. |

### 4 — Generate the stills, then the clips

Unchanged from `cat-story-video.md`: scene 1 invents the cast, scenes 2..N carry it as a reference
with `lock_identity`. A provider with reference-image input is required.

**If you are using the Tommy cast, generate scene 1 from the turnaround sheet.** Six angles on white
seamless is the best reference this mechanism can be given — every later angle is already in it.

### 5 — Sound: five layers, not three

`sitcom` adds two layers to the three `sound_bank.json` defines:

| Layer | Where it comes from |
|---|---|
| ambience | `build_sound.ambience_for` |
| **vocal** | `pet_sound_bank.json` — new vocabulary; the cat had no voice before this |
| key | `build_sound.key_for` |
| **contact** | `pet_sound_bank.json`, discipline beat only |
| accent | `sound_bank.json`'s comedy theme |
| **snap** | `sound_bank.json`'s *transition* theme, on the reset cut only |

Every one is scored by `sound_lint` before it reaches the sheet, including the new ones.

**There is no music layer, and that is deliberate.** `sound_bank.json` is an effects bank and
`sound_lint.check_is_an_effect` rejects `music`, `song`, `soundtrack`, `lyrics`, `instrumental` and the
narration words outright — the model returns them unusable. A music bed is a CapCut job, added in
step 7. (Note what is *not* on that list: `beat` and `hip-hop` pass it. Take the list from the bank,
never from memory.)

### 6 — The post

**Cats → Social.** Three titles, a caption and 15–20 hashtags, composed from the premise and the
episode's own captions — no model involved — and gated by `social_lint.py`.

**One conflict is deliberately left visible.** The brief asks for 15–20 hashtags. This app's own
`ugc_bank.json`, transcribed from the course, says *"Four at most. More than that and the algorithm
gets a confused signal about the topic."* The linter enforces the brief because that is what was
asked for; the course's advice is printed under the post every time so the choice stays a choice.

### 7 — Assemble

**Cats → CapCut.** Eight steps for this format. The two that matter most: trim the hook under three
seconds, and cut the reset **on** the frame — the instant-angel cut is the joke, and a few frames of
drift kills it. Music, if you want any, goes on last and ducked.

---

## The quality gate

```
python tools/safety_lint.py --check-bank      # no safety term fires on shipped vocabulary
python tools/build_pet_sound.py --check-bank  # every vocalisation scores 4/4 on sound_lint
python tools/social_lint.py --premise "..."   # the post is 6/6
```

The story gate itself runs in the app, on every keystroke.

---

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| "Contact is softened" fails | A staging field says `swat`/`shove`/`smack` with no softener beside it | Rewrite the phrase, not the linter: "a soft cartoon-like paw tap, claws in". |
| "Relative size is stated" fails | The scale sentence was overwritten | Clear the subject field and let the cast fill it, or put the size gap back into the subject yourself. |
| "The cast turns up" fails | A hand-typed subject dropped a character | The cast only fills fields you left blank. Clear the subject to get it back. |
| The kitten is mother-sized | The scale sentence is present but the model ignored it | Regenerate scene 1. Every later scene locks to it, so a wrong scene 1 is wrong five times. |
| Cost note warns above 1.3x | The runtime is not a multiple of the clip length | 15 seconds at 3s a stage is the only lossless setting. |
| A vocalisation fails `sound_lint` | A hand-edited audio cue | It needs a source, an `-ing` verb and a space or treatment, under 12 words. |
| Titles read as fragments | A hand-typed premise | Pick a bank premise, or pass a short noun-phrase form — a sentence cuts into a fragment. |

---

## What is not here

A music bed, a human voiceover, and batch generation. The first two are deliberate (see step 5, and
`voice_bank.json` holds sixteen human delivery styles, none of which is a cat). The third is the
architecture: every scene costs real money and is scored before it is generated, so there is no
"200 prompts" mode and will not be one.
