# Workflows — the W in WAT

A workflow is a step-by-step procedure that orchestrates one job. The agent reads a workflow
and follows it; it does not invent a procedure on the spot. If a job is worth doing twice,
it's worth a workflow file.

## Index

| Workflow | Does | Status |
|---|---|---|
| [create-realistic-avatar.md](create-realistic-avatar.md) | Idea → linted Nano Banana Pro prompt → avatar that reads as a real photo | **ready** |
| [consistent-character.md](consistent-character.md) | Lock one avatar's face across angles, outfits and locations via a reference image (Phase 5) | **ready** |
| [write-a-brief.md](write-a-brief.md) | The six-part prompt framework (lesson 1), and how `tools/brief.py` applies it — including why every model reply is validated | **ready** |
| [ask-the-advisor.md](ask-the-advisor.md) | A running conversation with the in-app expert on the whole studio — the fenced-spec convention, and why the gate still decides | **ready** |
| [build-an-influencer.md](build-an-influencer.md) | Define a reusable persona (name/gender/age/style/hair/eye/details, mood-reference images) and apply the composed description into Compose's Subject field | **ready** |
| [image-to-video.md](image-to-video.md) | Still → Kling clip: pick the camera move first, then make the still support it (Phase 3) | **ready** |
| `relight-and-angles.md` | Change the lighting of an existing photo, get multiple camera angles (Phase 2) | not built |
| [ugc-ad.md](ugc-ad.md) | Product + audience → five timed beats, one presenter across all of them, gated by the ad checklist (Phase 6) | **ready** |
| [cat-story-video.md](cat-story-video.md) | Idea → a story in scenes, each a still and a camera move, plus a CapCut edit sheet | **ready** |
| [sound-design.md](sound-design.md) | Scene → three layers of ElevenLabs sound-effect prompts, scored before you spend a generation | **ready** |
| `static-ad.md` | Product photo → studio and lifestyle composites, static ad variants (Phase 7) | not built |

The unbuilt ones are placeholders, not promises — build each when you reach that phase of the
course, so the workflow encodes what the lesson actually taught.

`cat-story-video.md` is the one exception to "encode what the lesson taught": its three
source lessons are video files, so its story structure and CapCut steps are general craft
rather than transcription. It says so at the top, and should keep saying so.

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
