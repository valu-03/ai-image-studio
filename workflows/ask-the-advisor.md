# Workflow: Ask the in-app expert (Advisor)

**Goal:** get specific, actionable advice on *using AI Video Studio itself* to reach a
premium-quality, photorealistic image - which nav section, which bank entry, which field -
instead of generic photography tips that don't map onto a real control here.

**Source:** built on lesson 1's six-part brief framework (see `write-a-brief.md`), extended
with the one thing this project has never had before: a running conversation.

**Inputs:** whatever you want to ask - a vague "how do I make this look better?" is fine, the
advisor asks a clarifying question rather than guessing.
**Outputs:** advice in plain conversation, and optionally a ready-to-use character spec once
there's enough to build one.

---

## Where it lives

`tools/advisor.py` builds the system brief (`advisor_brief()`) and runs one turn of the
conversation (`chat()`). `ui/views/advisor.py` is the transcript - open **Advisor** in the
app, or run it from the command line:

```
python tools/advisor.py show                              # read the system brief, no key needed
python tools/advisor.py chat "how do I get better skin texture"
python tools/advisor.py chat "and then?" --history-file turns.json
```

## What makes this different from Brief

`tools/brief.py`'s four actions (idea, upgrade, critique, analyze) are each one shot: a fresh
system message, one user message, no memory. The Advisor remembers the whole conversation -
`ask_llm.ask()`'s new `history` parameter threads every prior turn back in, so a follow-up
like "and what about the lighting?" is answered in context instead of from scratch.

It is also the one place in the app that is deliberately told about *everything* -
`advisor_brief()` is built live from `prompt_bank.json`'s 8 realism layers, the composition
guides, and all five technique banks (Lighting, Composition, Color Grading, Posing, Camera
Angle), so a bank edit is reflected in the very next reply, never re-typed by hand.

## The fenced-spec convention

Most replies are just conversation - a section to open, a technique to try. When, and only
when, the advisor has enough to propose a whole character, it ends its reply with:

```
```spec
{"subject": "...", "wardrobe": "...", ...}
```
```

`advisor.py` looks specifically for that fence (`extract_spec_block()`) - it does not scan the
whole reply for any `{...}`, because a conversational answer routinely has other braces or
prose around a spec block. No fence, or a malformed one, is a normal outcome (plain
conversation, nothing to apply), not an error.

## Autofilling every section, not just the core spec

Describe an avatar with enough detail and the advisor doesn't stop at `subject`/`wardrobe`/
`setting` - it also proposes one pick for every one of the five technique sections (Lighting,
Composition, Color Grading, Posing, Camera Angle), inside the same fenced block:

```
```spec
{"subject": "...", "shot": "portrait",
 "sections": {
   "lighting": {"setup": "old-hollywood"},
   "composition": {"guide": "rule-of-thirds", "techniques": ["lead-room"]},
   "color": {"mood": "melancholy-lonely"},
   "posing": {"pose": "forward-lean", "techniques": ["relaxed-hands"]},
   "camera_angle": {"vertical": "eye-level", "side": "three-quarter", "size": "medium-close-up"}
 }}
```
```

Every field name and value matches that section's own real `compose_X()` parameters exactly,
and every value has to be one of the real bank keys the brief already listed the advisor -
never an invented one. `_finalize_sections()` validates each section's picks against that
section's OWN bank (`build_lighting.setups()`, `build_posing.poses()`, and so on) and composes
the phrase through that section's OWN `compose_X()` - the advisor never writes phrasing of its
own, so a suggested lighting phrase is byte-identical to what Lighting's own "Apply to Compose"
button would have produced from the same pick. A section whose picks don't validate, or whose
own composer refuses them, is simply left out of the reply - it never fails the whole turn.

**One click, everything the advisor proposed.** The Advisor's Apply button fires both the core
spec and every section suggestion together - `MainWindow.apply_advisor_sections()` routes each
section's phrase to the exact same `SpecEditor.set_X_override()` its own section view's Apply
button already calls, so nothing here writes to a field through a second path.

**`shot` and `sections.camera_angle` write to the same field, on purpose.** A shot preset also
carries lens and framing language a bare angle phrase doesn't; if a reply proposes both, the
preset wins and the angle pick is dropped, rather than silently costing the camera realism
layer the way choosing an angle-only shot always legitimately can (see `build_camera_angle.py`'s
own "honest tradeoff"). Ask specifically for an angle-driven shot and the advisor is told to
prefer the angle instead.

## Pasting a full prompt: inspiration, not reproduction

The chat input takes any length of text, so you can paste an already-written, fully-detailed
prompt instead of a short idea - one of your own from another tool, or an example you found
somewhere. By default the advisor treats it as a **style reference, not something to
reproduce**: it carries over the vibe, mood and technique direction (the kind of lighting, pose,
composition it's going for) but invents a subject who is a clearly different person - a
different name, different physical features, different specific wardrobe and setting details.
It says so plainly in the reply rather than silently substituting a new person in.

**An explicit instruction always overrides that default.** Say "keep the setting" or "same
wardrobe, change everything else" - in the same message or a follow-up turn - and it keeps
exactly what you asked to be kept, the same "an explicit choice beats a generic fill" rule
every other suggestion in this app already follows. A follow-up works because `history` already
threads the whole conversation turn to turn - nothing new was needed for that half of this.

The five technique sections never have this problem in the first place: `_finalize_sections()`
only ever composes from that section's own real bank vocabulary, never the model's free
phrasing, so a lighting/composition/colour/posing/camera-angle suggestion can't literally echo
a pasted prompt's sentences even before this rule existed - only the free-text
subject/wardrobe/setting/action/mood half needed the explicit "invent someone else" instruction.

## The gate still decides. Always.

**The model suggests; `realism_lint` decides - the same rule every AI feature in this project
follows, with no exception for arriving inside a chat.** A fenced spec block is whitelisted
against exactly the same keys `brief.spec_from_idea()`/`autofill_spec()` accept (`subject`,
`wardrobe`, `setting`, `action`, `mood`, `shot`, `purpose`, `aspect`, `extra`) - `seed`,
`reference`, `lock_identity` and `overrides` are never accepted from a reply, no matter how the
model phrases it. The accepted fields are recomposed through `build_prompt.compose()` and
re-scored through `realism_lint.lint()` before the app ever shows a number - the advisor itself
never states a score in prose, because it never computed one.

If a suggestion scores below 8/8 or carries a banned term, that is shown plainly (`needs work`,
not hidden or silently rounded up) - the same honesty every other AI-suggestion surface in this
app already practises.

## Context, for free

If you already have a prompt composed, the Advisor folds its real score into the conversation
automatically (`[app context, not typed by the user - current prompt scores 6/8; missing:
...]`) - computed by `realism_lint`, never guessed by the model. This is what lets it diagnose
what your current prompt is actually missing instead of giving generic advice that ignores it.

## Attaching a photo

Vision works the same way it already does for Brief's Critique/Analyze tabs - attach a photo
and ask "why doesn't this look real?" A photo is scoped to the turn you attach it on; the
conversation's history stays text-only, so a long chat never silently re-uploads every earlier
photo on every later turn.

## Applying a suggestion

Once a reply carries a validated, passing (or at least scored) spec, an Apply button appears
with the real number. Applying it routes into Compose exactly the way Brief's Idea tab already
does - it is a suggestion offered for review, not something written into your working spec
automatically.
