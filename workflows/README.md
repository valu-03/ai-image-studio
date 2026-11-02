# Workflows — the W in WAT

A workflow is a step-by-step procedure that orchestrates one job. The agent reads a workflow
and follows it; it does not invent a procedure on the spot. If a job is worth doing twice,
it's worth a workflow file.

## Index

| Workflow | Does | Status |
|---|---|---|
| [create-realistic-avatar.md](create-realistic-avatar.md) | Idea → linted Nano Banana Pro prompt → photo that reads as a real camera image | **ready** |
| [consistent-character.md](consistent-character.md) | Lock one pet or person's identity across angles, outfits and locations via a reference image | **ready** |
| [capture-realism.md](capture-realism.md) | Film stock, lens artefacts, exposure and evidence of a hand on the camera — the properties of the CAMERA rather than the subject | **ready** |

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
