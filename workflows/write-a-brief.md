# Workflow: Write a brief for the text model

**Goal:** get useful output from a text model instead of vague output.

**Source:** AI Video Bootcamp lesson 1 — *How to write Prompts*.

**Inputs:** what you want and what it's for.
**Outputs:** a brief in `tools/brief.py`, or a better one-off prompt.

---

## The six parts

A prompt is a mini-brief. Every part you leave out, the model guesses.

| Part | The question it answers | Example |
|---|---|---|
| **Purpose** | What am I making, and where does it go? | "a 15-second TikTok hook about cold brew" |
| **Role** | Who should the model be? | "act as a world-class film director" |
| **Structure / Format** | How should the answer be laid out? | "five bullets, each under 20 words" / "JSON" |
| **Style / Tone** | How should it sound? | "the tone of a luxury fashion brand" |
| **Constraints** | What are the rules? | "under 100 words", "no jargon", "shot on IMAX" |
| **Example + Action** | What does good look like? | one worked example, then the ask |

Constraints make output better, not worse. That is the part most people skip.

**Weak:** "Write something about productivity."
**Strong:** "Act as a former navy seal turned life coach. Write a motivational
Instagram caption about morning routines, under 100 words, in a bold tone."

## How this project uses it

`tools/brief.py` builds briefs from exactly those six parts, and ships three:

| Brief | What it does |
|---|---|
| `idea_brief` | one line → a character spec |
| `upgrade_brief` | compact prompt → the richer version (lesson 20's "make this way more detailed") |
| `critique_brief` | image + prompt → why it doesn't look real |

Read the rendered text any time — no API key needed:

```
python tools/brief.py show upgrade
```

Or open **Brief → The briefs** in the app. If output is disappointing, fix the
brief, not the individual request. That is the whole point of keeping them in a
file instead of retyping them.

## Step 1 — Name the purpose before anything else

If you can't say what the output is for, no amount of role and tone will save it.
For images this is literal: the **Purpose** tab sets platform and intent, and the
shot and aspect follow from it.

## Step 2 — Give a role with a point of view

"Act as a photographer" is weaker than "act as a photo editor who has spent years
spotting retouched images". The second one has opinions, which is what you want.

## Step 3 — Demand a format you can use

If the answer feeds another tool, ask for JSON and say which keys. `brief.py`
does this, and then **discards any key it didn't ask for** — never trust the shape
of a model's reply.

## Step 4 — Write the constraints as rules, not wishes

"Try to keep it short" is a wish. "Under 320 words" is a rule you can check. Every
constraint in `upgrade_brief` is checkable, which is why the gate below works.

## Step 5 — Show one example

`upgrade_brief` passes the worked examples from `prompt_bank.json`. One good
example moves output further than three more sentences of instruction.

## Step 6 — Validate the reply. Always.

**The model suggests; `realism_lint` decides.**

`upgrade_prompt()` re-lints every rewrite and rejects it if it falls below 8/8,
introduces a banned term, or runs away in length — your prompt is kept and the
reason is shown. `spec_from_idea()` drops unknown keys, and refuses to let a model
set `seed`, `reference`, `lock_identity` or `overrides`.

Without this step a text model quietly becomes the weakest link in a project whose
entire purpose is enforcing a quality standard.

## Step 7 — Improve the brief, not the request

When the answers are consistently off, edit `tools/brief.py`. A fix in the brief
applies to every future call; a fix typed into one request dies with it.
