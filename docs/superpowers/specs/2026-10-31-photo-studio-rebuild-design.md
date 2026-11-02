# AI Image Studio → a one-page photo studio: rebuild design

Date: 2026-10-31. Status: draft for approval.

## Intent and the why

AI Image Studio grew into a large PyQt6 workspace. It has:
- about 19k lines of UI and 20k of tools;
- tabs for Compose, Look, Images, Ads, Cats, Sound, Videos, Influencer Studio, Brief, Assistant, Advisor, History, Insights and Skit Studio.

The user wants it **simple to use again**. It should make one thing well: **a photorealistic image that nobody scrolling past would take for AI**, of pets, people, or both. Everything must be explained **Feynman-style**: plain words, then an everyday example. The user said "concentrate on the Image and Look tabs", then "keep just Image and Look, get rid of all the other stuff".

What we saw in the user's own output (`temp/outputs/`, read-only recon):
- **The realism score can't tell good from bad.** All 43 real generations scored 8/8 "passed". `realism_lint` checks that words are present in the prompt and never looks at the picture. None of the 43 was ever rated.
- **The images are close, but have repeat tells:**
  - the same sunny-window, wooden-cabinet, cream-rug room every time;
  - subjects dead centre, posing at the lens (the cat raises a paw like a model);
  - "mess" that looks painted on (stroke-like mud on a muzzle, stamped mud on a rug);
  - airbrushed fur;
  - stray artefacts (an orange glint on a nose).
  - Prompts also open with the literal word "Photorealistic".
- **The UI is a maze.** Look has 8 sub-tabs and Images has 4: about 80 controls across 12 screens. Each Look sub-tab builds a phrase that must be "Applied" into the prompt separately.
- **All real images came through Skit Studio's Local API.** The 895 `avatar-*.png` files are 70-byte test placeholders.

## Goals

1. **One page.**
   - **Left:** "What's in the photo?" (plain text), an optional reference photo, a short set of **Look cards**, then the price and **Make photo**.
   - **Right:** the photo, large, with the **"Does this look real?"** check under it.
2. **A check that looks at the picture.** A vision model reads the generated image and lists concrete **giveaways**:
   - dead-centre or posed subject;
   - too-clean fur or skin;
   - generic or repeated room;
   - painted-on mess;
   - perfect studio-like light;
   - odd hands, paws, eyes or teeth;
   - glints and artefacts;
   - unreadable text.
   Each giveaway is tied to the Look card that fixes it.
3. **Fix on click.** Each giveaway has a **Fix** button. It changes the matching Look card(s) and shows the new price. **Nothing is spent until the user clicks Make photo or Fix**, and there is never an automatic paid retry (user decision). This is the old Refine, made visible and manual.
4. **Look cards that adapt to the subject.** Light, Camera, Framing, Colour, Pose and Lived-in details:
   - pet subjects bring fur, whiskers and mid-movement options;
   - people subjects bring skin texture, uneven hair, hands and clothing creases.
   Each card shows a plain name, one line on what it does and an everyday example (Feynman). Cards start on sensible realistic defaults, so touching them is optional.
5. **Defaults that avoid the tells.**
   - Vary room, light and weather instead of always a sunny window and wood.
   - Frame off-centre and catch the subject mid-moment.
   - Describe mess as real wear, not an added effect.
   - Stop leading with the word "Photorealistic".
6. **A reference photo** for identity lock across shots, so the same pet or person carries through (user decision: keep).
7. **A recent-photos strip** with 👍/👎. Ratings feed `history` so the vocabulary weights learn what works for this user.
8. **Skit Studio's photos get better too** (user decision: "both").
   - The giveaway-avoiding defaults in Goal 5 also apply to photos requested through the Local API.
   - The literal "Photorealistic" opener is removed or replaced at its sources:
     - the `photoreal` preset in `Skit Studio/tools/write_skit.py:49` (a separate repo, edited in scope);
     - the core-layer term in `tools/prompt_bank.json`, which the realism fill draws on.
   - Scene variety must not break a skit's continuity. Within one skit or job, room, light and weather stay fixed; they vary between skits.
   - `realism_lint` tests and `tests/test_local_api.py` fixtures are updated to match.
9. **Settings:** API keys, the Local API on/off switch and the image-maker choice: Nano Banana Pro via Kie (default) or Higgsfield Soul.

## Non-goals

- Ads, Cats/stories, Sound/voices, Videos/Kling, Influencer Studio, Brief, Assistant, Advisor, Insights, the Skit Studio tab, Midjourney export and batch shots. These are **deleted**, with their UI, tools, banks and tests, wherever nothing kept depends on them. Git history keeps them.
- Other languages. **English only for now** (user decision).
- An installer or exe. Launch with `start.bat`.

## Anti-goals (failure even if it works)

- **Removing, faking or evading provenance**, such as C2PA metadata or SynthID-style watermarks, or "beat the AI detector" features. Realism comes from photography (light, lens, texture, imperfection) only.
- Spending money without a click.
- A score that says "8/8 passed" on a photo that obviously looks AI. The check must judge pixels.
- Breaking Skit Studio or the `ai-image-studio` MCP server. Better photos for them is a goal; a broken call is a failure.
- Jargon left unexplained on screen.
- A "kitchen sink" page: if the left column needs scrolling past one screen at 1366×768, there are too many controls.

## Constraints

- **The Local API contract keeps the same routes, fields, token and port.** The prompt text it produces may change (Goal 8), but nothing the callers parse may change.
  - Address: `127.0.0.1:8785`, with the same token from `.env`.
  - Routes: `GET /api/v1/health`, `/look/options`, `/look/current`; `POST /api/v1/look/compose`, `/prompt`, `/images`, plus the job polling they use.
  - Skit Studio (its client is `Skit Studio/tools/avs.py`; AI Image Studio's own `tools/skit_client.py` belongs to the deleted Skit Studio tab) and `mcp_server/server.py` call it.
  - Today the PyQt `MainWindow` starts it when the app opens. The new app must do the same. `python tools/local_api.py --serve` keeps working headless.
  - `look/current` must return the Look set on the new page.
- **The engine stays.** `tools/` stays standard-library Python and deterministic, with CLIs that document themselves. The WAT rules in `CLAUDE.md` still apply: the GUI is a front end over the same tools, and "a text model suggests, a linter decides". The new vision check is display-only, the same authority as a rating. A Fix changes Look cards through the same builders, never by pasting model text into the prompt.
- **Tools the Local API imports are kept**, even if their tab is deleted. That covers `brief`, `ask_llm`, `build_snapshot`, `build_face_detail`, `history`, `realism_lint`, `generate_image` and the Look builders.
- **Tests:** `python tests/run_all.py` stays the one command and spends nothing (it uses the mock servers). Suites for deleted features go; suites for kept tools stay green.
- **Git:** the repo is on branch `realism-gate-and-ad-vocabulary` (main is behind). Do the rebuild on a new branch from it. `CLAUDE.md`/`AGENTS.md`: commit only when the user asks.
- **Known bug to fix on the way:** `tools/generate_video.py` `_resolve()` ignores `AIVS_API_BASE`. That tool is deleted, so check nothing kept has the same pattern.
- Windows 11, Python 3.13.

## Decided by the user

- Scope: keep only Image and Look; delete the rest.
- Layout: **one page** (option A): describe and choose on the left, photo and check on the right.
- Style: **Darkroom**: neutral charcoal (~#141414 ground, #1F1F1F surfaces), light-grey text and one warm amber accent (~#F5C451) for the primary action and giveaway counts. The photo is the brightest thing on screen; neutral greys keep it from colouring the user's judgement of photo colour.
- English only.
- Paid retries wait for a click.
- Keep the reference photo.
- Feynman explanations everywhere.

## My calls (the user can override)

- **Stack**, the same as Vestora:
  - a pywebview desktop window over a small local Python server, with a React + Vite + TypeScript + Tailwind page inside;
  - launched by `start.bat`, which builds the page if needed.
  - PyQt6 and the `ui/` package are deleted once the new page reaches parity, along with `gui.py`, the PyInstaller spec and `pyqt6_system_prompt.md`.
- The page talks to the app's own backend. The builder chooses between extending the stdlib Local API with new GUI routes and adding a separate app server. Either way, the 8785 contract must stay byte-compatible.
- 👍/👎 maps onto the existing 1–5 rating scale (5 and 1). Today `history.weights()` only feeds `build_prompt.compose()`, and history rows store lint term hits, not card choices. So the page records each photo's Look card choices in history, and card defaults and suggestions read the weights. `weights()` may need extending for that; that's the builder's call.
- **`/look/current`** returns only what the user deliberately set on the page: cards they changed and Fixes they applied. It never includes the untouched defaults or the scene-variety randomness. That way a skit's shots stay consistent and person-only cards never leak into pet skits.
- **Spending.**
  - The **Make photo** click is the consent; there's no extra confirm dialog. Its price includes the "Does this look real?" check, which then runs automatically on the new photo.
  - Each **Fix** button applies its card change and shows the price on the button. Clicking it makes the new photo, plus the check.
  - The Local API's existing `refine` 0–2 automatic retries stay for API callers. "No automatic paid retry" applies to the page.
- **Recent-photos strip.** It also lists images made through the Local API (Skit Studio, MCP), so those can be checked and rated too. That's where nearly all real output comes from. For those photos, the check runs only when the user opens one and clicks Check, with its price shown.
- **Higgsfield Soul** can't take a reference photo and has no entry in `pricing.json`. When Soul is chosen, the reference slot is disabled with a plain explanation, and the price reads "unknown, billed by Higgsfield".
- Look cards are grouped into the six named above. Today's sub-tabs (Lighting, Composition, Camera, Color, Posing, Style, Capture, Evidence; Variants, Relight, Macro insert) fold into them or into an "Advanced" disclosure. Nothing useful is lost, but the first screen shows only the six cards.
- The vision check extends `tools/vision_lint.py`, which already sends an image to an OpenRouter vision model and whitelists the reply. It gets a giveaway rubric next to the existing spec-match check. If `OPENROUTER_API_KEY` is missing, the page says so plainly and the rest still works.
- Each check shows its price if it costs anything.

## Left to the builder

- Exact card contents and defaults, drawn from the existing banks (`*_bank.json`), and the wording of each Feynman line. Final copy is reviewed on screen.
- How the giveaway → card mapping is stored, as a data file next to the banks plus tests.
- Scene-variety mechanics, for example not repeating the last N settings or lights.
- Which tests to port, rewrite or delete.
- The deletion order: delete only after the new page covers what the user keeps.

## Verification

- `python tests/run_all.py` green, plus new tests for:
  - the giveaway rubric parser;
  - the Fix mapping;
  - the scene-variety default;
  - the Local API contract (the existing `test_local_api.py` keeps passing unchanged).
- Skit Studio smoke test: with the new app open, Skit Studio's still generation still works, either through the mock server or one real approved generation.
- The `ai-image-studio` MCP tools still answer (`avs_status`, `look_options`, `prompt_preview`).
- Screenshots of the page:
  - empty state, generating, a result with giveaways, and the missing-key state;
  - at 1366×768 and 1920×1080.
  Reviewed against the impeccable audit.
- One real end-to-end photo, approved by the user, of a pet and of a person, checked by eye for the tells listed above.
