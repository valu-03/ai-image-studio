# Workflows — the W in WAT

A workflow is a step-by-step procedure that orchestrates one job. The agent reads a workflow
and follows it; it does not invent a procedure on the spot. If a job is worth doing twice,
it's worth a workflow file.

## Index

| Workflow | Does | Status |
|---|---|---|
| [ai-creator-workflow.md](ai-creator-workflow.md) | The whole pipeline in order — Idea → Chat → Image → Refine → Video → Edit & Post — and where each stage already lives in this app | **ready** |
| [create-realistic-avatar.md](create-realistic-avatar.md) | Idea → linted Nano Banana Pro prompt → avatar that reads as a real photo | **ready** |
| [consistent-character.md](consistent-character.md) | Lock one avatar's face across angles, outfits and locations via a reference image (Phase 5) | **ready** |
| [write-a-brief.md](write-a-brief.md) | The six-part prompt framework (lesson 1), and how `tools/brief.py` applies it — including why every model reply is validated | **ready** |
| [ask-the-advisor.md](ask-the-advisor.md) | A running conversation with the in-app expert on the whole studio — the fenced-spec convention, and why the gate still decides | **ready** |
| [build-an-influencer.md](build-an-influencer.md) | Define a reusable persona (name/gender/age/style/hair/eye/details, mood-reference images) and apply the composed description into Compose's Subject field | **ready** |
| [image-to-video.md](image-to-video.md) | Still → Kling clip: pick the camera move first, then make the still support it (Phase 3) | **ready** |
| [relight-and-angles.md](relight-and-angles.md) | Change the lighting and/or camera angle of an existing photo, scene locked (Phase 3, two lessons synthesised) | **ready** |
| [macro-insert.md](macro-insert.md) | One face → a full-face beauty macro, then extreme-macro inserts of its eye, mouth and cheek, each scoped to preserve its own feature (community-supplied, not course material) | **ready** |
| [ugc-ad.md](ugc-ad.md) | Product + audience → five timed beats, one presenter across all of them, gated by the ad checklist (Phase 6) | **ready** |
| [cat-story-video.md](cat-story-video.md) | Idea → a story in scenes, each a still and a camera move, plus a CapCut edit sheet | **ready** |
| [pet-sitcom-series.md](pet-sitcom-series.md) | A repeating two-character pet comedy: a locked cast, one standing set, a five-stage curve in 15s, the app's first content gate, and the post to publish it with (user-supplied series brief, not course material) | **ready** |
| [sound-design.md](sound-design.md) | Scene → three layers of ElevenLabs sound-effect prompts, scored before you spend a generation | **ready** |
| [static-ad.md](static-ad.md) | Product photo → a studio composite, a lifestyle composite, or both (Phase 3, studio half is this app's own naming) | **ready** |

Every workflow above is built. A blank row here would be a placeholder, not a promise —
build one only when you reach that phase of the course, so it encodes what the lesson
actually taught.

Five are not pure transcription, and each says so at its own top:

- `cat-story-video.md` — its three source lessons are video files, so its story
  structure and CapCut steps are general craft rather than transcription.
- `relight-and-angles.md` — no single lesson teaches "relighting and camera angles"
  together; it honestly synthesises two separate lessons (Nanobanana's existing-photo
  relighting, and Creating AI Avatars' multi-angle turnaround technique).
- `static-ad.md` — the course never pairs "studio" against "lifestyle" as an ad-type
  split; the lifestyle half transcribes a real lesson, the studio half reuses this app's
  own existing `studio-lighting` style rather than inventing new vocabulary.
- `macro-insert.md` — the course teaches no beauty-macro or feature-insert technique at
  all. Its vocabulary is community-supplied (a user-contributed macro/beauty-portrait
  prompt), and its lighting and shot-size halves are resolved through this app's own
  existing `lighting_bank.json` and `camera_angle_bank.json` rather than inventing new
  vocabulary. Its bank's `source` field says so.
- `pet-sitcom-series.md` — the course teaches no series format at all. The whole thing
  encodes a user-supplied brief for a two-cat comedy series: `story_bank.json`'s
  `formats.sitcom`, plus four banks written for this app rather than transcribed
  (`safety_bank.json`, `pet_sound_bank.json`, `social_bank.json`, and the `casts` and
  `premises` blocks). Each carries a `source` field saying so. What it DOES inherit from
  the course is the Kling camera vocabulary, through `motion_bank.json`, and the
  effects-only sound pattern, through `sound_bank.json` — neither of which it modifies.

## Writing a new workflow

Follow the shape of `create-realistic-avatar.md`:

1. **Header** — goal in one sentence, the course lesson it comes from, inputs, outputs.
2. **Numbered steps** — each one says what to do and, where relevant, the exact command.
3. **Named tools** — if a step needs logic, it calls something in `/tools/`. If the tool
   doesn't exist yet, write the tool rather than inlining the logic in the workflow.
4. **A quality gate** — a concrete pass/fail check before anything is handed over.
5. **A fix table** — when the output is wrong, what to change. This is the part that makes a
   workflow worth more than a memory.

Then add a row to the index above.
