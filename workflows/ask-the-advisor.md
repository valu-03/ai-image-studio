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
