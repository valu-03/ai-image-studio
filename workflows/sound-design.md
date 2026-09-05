# Workflow: sound design

**Goal:** sound-effect prompts that come back usable the first time.

**Source:** AI Video Bootcamp — *100 ElevenLabs Sound Effects Example Prompts*. All 100 are in
`tools/sound_bank.json` verbatim, and they are this section's test fixture: a linter that
rejects one of them is wrong about it, not the other way round.

**Inputs:** a scene, or just a source and an action.
**Outputs:** prompts to paste into ElevenLabs, scored before you spend a generation.

---

## The pattern, measured rather than guessed

The first version of the linter guessed at what the examples had in common and rejected 31 of
them. Counted properly, across all 100:

| | |
|---|---|
| word count | **4 to 9**, mean 6.5 |
| carries an `-ing` action verb | 81 / 100 |
| carries a preposition | 92 / 100 |
| carries an action, a placement **or** a qualifier | **100 / 100** |

So only the last one is a hard rule: **the prompt must describe an event, not an object.**
"a sword" is a thing; "sword unsheathing with a high-pitched metallic ring" is a sound.

Naming the space is *advice*, not a rule — "Sandbags rustling and barbed wire creaking" states
neither a place nor a treatment and is a perfectly good prompt. The app says so as a note
rather than a failure.

## The one thing that comes back unusable

**This model makes effects.** It does not write music and it does not speak lines. Ask for a
melody or a voiceover and you get something you cannot use, so both are rejected before you
spend the generation.

The word list is deliberately short. "dialogue" is *not* on it, because example 72 is
*"Heartbeat slowing down before emotional dialogue"* — which uses the word to say **when** the
effect plays. A gate that rejects the course's own example is wrong about the example.

## Step 1 — Read ten of them

**Sound → Library.** Nine themes, ten examples each (twenty for magic). Pick the theme nearest
your scene and read them before writing anything — the shape is easier to copy than to
describe.

The **comedy** set is the one that carries an animal video: *"tiny mouse squeak with comedic
echo"*, *"slippery banana peel slip sound"*, *"cartoonish gulp after seeing something scary"*.
Exaggeration is the point.

## Step 2 — Build one

**Sound → Compose.** Four fields: source, action, where, how. It assembles them in the
pattern and scores it as you type.

```
python tools/build_sound.py --source "torch flame" --action crackling --place "a temple hallway"
python tools/sound_lint.py "Torch flame crackling in a temple hallway"
```

## Step 3 — Three layers per scene, not one

This is the part people miss. One effect on its own sounds like a sound effect; three layers
sound like a place.

| Layer | Job | Rule |
|---|---|---|
| **ambience** | the bed under the whole scene | continuous, no events. If you notice it, it is too loud |
| **key** | the action you can actually see | must land on the frame where it happens, not near it |
| **accent** | the punctuation — the cut, the reveal, the punchline | **one per scene at most**; two cancel each other out |

**Sound → Scenes** builds all three for every scene of the story open in Cats, and cycles the
accent so no two neighbouring scenes get the same one — the same joke landing twice in a row
is worse than a duller one that does not repeat.

## Step 4 — Generate and place

Generate each prompt in ElevenLabs. In CapCut, three separate audio tracks:

1. ambience underneath everything, quiet — around -30dB
2. key effects on the action frames
3. accents on the cuts

Then music last, ducked under the narration — never the other way round.

---

| What went wrong | Fix |
|---|---|
| It returned something musical | You asked for music. The gate catches this if you use it |
| It is a vague wash of noise | No action verb. Say what the source is *doing* |
| It does not sound like anywhere | Add the space: "in a temple hallway" |
| Two effects fight each other | Two accents in one scene. Keep one |
| The ambience is distracting | It is too loud, or it has events in it. Ambience never has events |
