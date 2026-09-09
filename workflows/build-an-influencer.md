# Workflow: Build an influencer persona

**Goal:** define a reusable persona once — name, gender, age range, style, hair/eye colour,
free-text details, optional mood-reference images — and apply the description it composes
straight into Compose's Subject field, the same way every other technique section here already
applies into Compose.

**Source:** NOT from the course. Influencer Studio is app-original tooling, built to give the
existing character-spec system (`temp/resources/characters/`, `SpecEditor`'s Subject field) a
structured front end for the one field the course never broke into pieces — who the person is.

**Inputs:** whatever you know about the persona; every field is optional.
**Outputs:** a saved persona in `temp/resources/personas/<slug>.json`, and (once applied) a
composed description sitting in Compose's Subject field, ready for the normal
`create-realistic-avatar.md` pipeline from there — build, lint, generate.

---

## Where it lives

`tools/persona_bank.json` holds the vocabulary (genders, age ranges, style tags, hair/eye
colours), `tools/build_persona.py` composes it into one sentence
(`compose_persona()`), and **Influencer Studio** in the nav rail is the GUI over both — open it,
or run the tool directly:

```
python tools/build_persona.py --list
python tools/build_persona.py --name Zoe --gender woman --age-range 25-30 \
    --hair-color blonde --eye-color blue --style luxury --style lifestyle \
    --details "a small nose stud, always carries a film camera"
```

## Step 1 — Build the persona

On the **Build** tab: a name, a gender, one age range, any number of style tags, one hair
colour, one eye colour, and free-text Additional Details for anything structured fields don't
cover — a face shape, a build, a tattoo, an accessory. That field is exactly `SpecEditor`'s own
Subject box always has been: plain prose, used as typed.

Every pick is validated against `persona_bank.json`'s own real vocabulary — nothing here invents
phrasing, and an unrecognised key (a stale saved persona field, say) is quietly dropped rather
than smuggled through as free text.

**Deliberately absent: any attractiveness, face-shape or body-shape dial.** Every other control
in this app describes who someone specifically is, or how a shot is technically made — never a
slider tuned toward an idealised standard. If a persona needs a specific face or build, that is
prose in Additional Details, same as everywhere else.

## Step 2 — Read the Result panel before doing anything with it

The composed sentence is shown immediately, live, as you fill the form in — the same "give me
the prompt" shape every other section (Lighting, Posing, ...) already has. Copy it, or move on
to Step 3/4.

## Step 3 — Save it, so it is not typed twice

**Save to roster** writes the persona (structured fields, not just the sentence) to
`temp/resources/personas/<slug>.json`. The **Roster** tab lists every saved persona — double-
click, or select and press **Load**, to bring it back onto the Build tab. Rename and Delete work
the same confirmed-first way the character library's own do.

## Step 4 — Reference images are a mood board, not an identity lock

Up to 8 images, drag-and-dropped or browsed in, for your own reference while describing the
persona in words. **They are never sent anywhere** — not to the model, not into
`SpecEditor`'s reference picker. If you want a real face locked across shots, that is Compose's
own Identity tab (`consistent-character.md`) — a deliberately separate mechanism, so a mood
board can never accidentally become a face-clone.

## Step 5 — Apply to Compose, then continue as normal

**Apply to Compose** writes the composed sentence into Compose's Subject field (replacing
whatever was there, the same "typed text wins outright" rule every other section's Apply
button follows) and jumps to Images. From here it is an ordinary character spec: build, lint
(`realism_lint.py`, the same 8/8 gate as anything else — a persona's own words are descriptive
content, not one of the 8 gated layers, so nothing here scores separately), generate, and
optionally **Save character** to fold it into the full character library too.

## The gate still decides. Always.

Same rule as every AI-adjacent surface in this app, applied here even though nothing here calls
a model: **a persona composes vocabulary you picked, it never scores itself.** The number that
matters is the one `realism_lint.lint()` reports once the description is inside a real Compose
prompt.
