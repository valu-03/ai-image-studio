# Workflow: Still to video

**Goal:** turn a finished still into a clip with a camera move that actually works.

**Source:** AI Video Bootcamp Phase 3 (DIRECTOR) — *Kling AI Cinematic Camera Movement
Toolkit*, plus *The Modern Cinematic Glossary*.

**Inputs:** a character spec, and an intended camera move.
**Outputs:** a Kling-ready prompt in `temp/outputs/prompts/motion-*.txt`, and a still that
supports it.

**Not automated:** the app does not generate clips. You paste the prompt into Kling's own
interface — which is where the work happens anyway, and it costs nothing to be wrong here.
(The old `fal` seam is gone; the image providers are Kie and Higgsfield, and neither is
wired for video here.)

---

## The order is backwards from what you expect

The instinct is: make a nice image, then animate it. The toolkit says the opposite:

> *"Always create your images in a way that will complement the camera movement... if you say
> 'tracking over the shoulder' but there is no character in your scene, or 'the camera dives
> underwater' but there is no water nearby, Kling will get confused. Think ahead!"*

**Choose the move first.** A tight portrait cannot be orbited — there is nowhere for the
camera to go. A face-on shot cannot be tracked from behind. Deciding the motion after the
still is finished is how you end up regenerating the still.

## Step 1 — Choose the movement

**Videos → Motion.** 40 moves, grouped:

| Group | What it's for |
|---|---|
| Core (30) | the everyday vocabulary — dolly, orbit, crane, track, pan, POV |
| Niche (6) | water, fire, portals, falling — strong effects with strict scene requirements |
| Combo (4) | two moves layered; the only case where two movements in one prompt is correct |

Each move states what it does and what the frame must contain.

## Step 2 — Read the compatibility panel before generating anything

The **Will this shot work?** panel checks two different things, and the difference matters:

- **Green/red rows** — the *prompt*: does it lead with the camera move, name a subject,
  use one move, describe motion, avoid contradictions. These are the toolkit's own rules.
- **Amber rows** — the *still*: what the image is missing for this move, and how to fix it.

A prompt can be perfect and still fail, because the image can't support it. That's the amber
half, and it's the one people skip.

## Step 3 — Fix the still, not the prompt

Press **Apply framing to the still**. The movement fills in the shot and composition it
needs — and, exactly like `purpose`, it only fills what you left blank. An explicit choice of
yours is never overwritten; a disagreement is reported instead.

Then go back to **Images**, confirm the still is still 8/8, and generate it.

Common fixes, in order of how often they're needed:

| Amber warning | What to change |
|---|---|
| room around the subject | switch the shot to `environmental` |
| the subject seen from behind | rewrite the Action: "walking away from camera" |
| a described setting | fill in Setting — the move reveals surroundings, so it needs some |
| water / fog / a portal | add it to Setting; the move cannot invent it |
| sky, height, something to descend from | the scene needs vertical scale |

## Step 4 — Generate the still, then build the motion prompt

Generate the image first (Images → Generate). Then return to Videos and press
**Copy for Kling**. The prompt is built from the same character spec, so the clip describes
the same person as the still.

Or from the command line:

```
python tools/build_motion.py --movement orbit-360 --spec temp/resources/characters/<slug>.json
python tools/motion_lint.py <that file> --movement orbit-360 --spec <same spec>
```

## Step 5 — Paste into Kling with the still attached

Image-to-video, with your generated still as the input frame and this text as the prompt.
The camera move must be the opening words — the tools guarantee that, so don't reorder it
when you paste.

## Step 6 — Judge the motion, not the image

The still was already judged in Images. Here, look only at movement:

- [ ] The camera does what you asked, once, in one direction
- [ ] The subject stays the same person for the whole clip
- [ ] Nothing warps at the frame edges as the camera travels
- [ ] Hands and faces survive the movement
- [ ] The move ends somewhere — it reveals or arrives, rather than drifting

| What went wrong | Fix |
|---|---|
| The camera barely moves | the move was buried mid-prompt; it must be the first words |
| It moves the wrong way | two movement words are competing — the linter flags this |
| The subject morphs mid-clip | the still was too tight; give the camera more room |
| It ignored the move entirely | the scene lacked what the move needs — recheck the amber rows |

## Step 7 — Log it

The image is already in the history log. Note the movement key in the entry so you learn
which moves work for which shots — the same feedback idea as the image side, applied to
motion.

## Optional — Auto multi-shot

**Source:** AI Video Bootcamp's Kling 3.0 update lesson.

Kling 3.0 can vary its own camera angles/cuts within one generation instead of holding a
single continuous shot. Videos → Generate has a **"multi-shot (auto)"** checkbox next to
audio for this — toggle it on and Kling decides the cuts itself; there is no extra cost
multiplier for it. This is Kling's *Auto* multi-shot only. Kling's separate *Custom* mode
(choosing exactly when each cut happens and writing a different prompt per cut) is not
implemented here — if you need that level of control, build the sequence in Kling's own
interface directly.

## Optional — the Contrast Trick, after you export

**Source:** AI Video Bootcamp's "Removing the 'AI' Look" / "Contrast Trick" lessons.

Raw AI video often reads as fake for reasons no prompt fixes: punchy contrast, over-clean
saturation, and a camera that's too stable to feel handheld. For UGC-style or social clips,
the course's fix is a short pass in CapCut on the *exported* clip, not the prompt — this app
does no video post-processing itself, so this step happens after Step 7, outside the app:

1. Add an adjustment layer/filter over the clip.
2. Lower contrast until it stops reading as a render.
3. Reduce saturation slightly — just enough to take the digital edge off, not grey it out.
4. Lift highlights a touch if the image feels dense.
5. Add a shake effect, then turn it down until it's barely noticeable — visible shake reads
   as an effect, not as a handheld camera.

This is a finishing pass for clips that need to feel native to social, not something every
clip needs.

## What is not here

Editing and sound (Phase 4) — the glossary tab defines the terms (L cut, J cut, match cut,
foley, diegetic), but the app does nothing with them. Assembly happens in CapCut.
