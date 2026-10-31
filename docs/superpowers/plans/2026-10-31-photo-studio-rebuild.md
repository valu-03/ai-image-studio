# Photo Studio Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AI Video Studio into a one-page Darkroom photo studio (Look + Image only):
- a picture-reading "Does this look real?" check with click-to-Fix;
- better default realism, reaching Skit Studio's stills too.

**Architecture:**
- `tools/` stays the stdlib engine. Three new pure modules sit beside it:
  - `giveaways` (the vision rubric);
  - `look_cards` (six Feynman cards, defaults, fixes);
  - `pricing`.
- A new `studio/` package is a FastAPI app server. It uses the engine, holds the page's Look state, and starts the unchanged-contract Local API on 8785 in-process.
- A pywebview window shows the React page from `web/dist`. The PyQt `ui/` is deleted last.

**Tech Stack:**
- Python 3.13: stdlib tools, plus fastapi, uvicorn and pywebview (with pythonnet), plus httpx for tests.
- Web: React 18.3.1, Vite 6, TypeScript, Tailwind v4 (`@tailwindcss/vite`), lucide-react, vitest.

**Spec:** `docs/superpowers/specs/2026-10-31-photo-studio-rebuild-design.md`

## Global Constraints

- **Local API.**
  - Routes, fields, port `8785` (`AIVS_LOCAL_API_PORT`) and token (`AIVS_LOCAL_API_TOKEN`) are unchanged. `tests/test_local_api.py` keeps passing; only the prompt-text expectations change (Task 3).
  - `python tools/local_api.py --serve` keeps working.
- **`tools/` modules** stay standard-library only, deterministic, and runnable as `python tools/<name>.py --help`.
- **"A text model suggests, a linter decides."** Vision output is whitelisted, display-only, and never pasted into a prompt.
- **Spending.**
  - Nothing is spent except by `POST /api/photos` (Make photo) or `POST /api/photos/{id}/fix` (Fix), each from a user click.
  - The page never auto-retries; API callers keep `refine` 0–2.
  - Make/Fix price = image price + check price, shown on the button before the click.
- **Never remove, alter or fake provenance metadata.** No C2PA stripping, no watermark removal, no "detector evasion" wording or features. Saved files are written byte-for-byte as the provider returned them.
- **Copy** is English only, in plain words. Every card and option has `plain` (what it does) and `example` (an everyday picture), Feynman-style. No unexplained jargon on screen.
- **Darkroom tokens:**
  - colours: ground `#141414`, surface `#1F1F1F`, raised `#2A2A2A`, hairline `#2C2C2C`, text `#E8E8E8`, muted `#8A8A8A` (AA on the ground), accent `#F5C451` with on-accent text `#141414`, danger `#F87171`, ok `#34D399`;
  - font: Inter from `assets/fonts`;
  - photo area background: neutral `#0E0E0E`.
- **Layout:** the left column must fit without scrolling at 1366×768 when Advanced is closed.
- **Tests.**
  - Python suites are plain scripts in `tests/` using the existing `check(name, cond)` / `fails` pattern, listed in `tests/run_all.py` `ORDER`.
  - Run everything with `python tests/run_all.py`. No real network or spend: use `tests/mock_api.py` and injected fake `ask`.
  - Web: `npx vitest run` in `web/`.
- **Ports:** the app server binds `127.0.0.1` on a free port. Avoid 8765, 3900, 8770, 8780, 8785 (the Local API), 8791 and 8799.
- **Git.**
  - Work on branch `photo-studio` created from `realism-gate-and-ad-vocabulary`. Commit per task with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - In `Skit Studio/` (branch `main`, which has unrelated uncommitted edits), stage and commit only the files Task 4 touches.
- `.superpowers/` goes in `.gitignore`.

## Review Focus

1. **The OpenRouter key is missing, or the vision reply is malformed or off-schema.**
   - The photo still shows and the check says plainly that it couldn't run.
   - Never "looks real" and never a crash.
   - Test: Task 1 (`test_giveaways.py`) and Task 6 (`test_studio_photos.py::check_without_key`).
2. **Generation fails** (missing Kie key, HTTP 402 out of credits, timeout).
   - The page shows `generate_image`'s plain remedy text, and the Make button becomes clickable again.
   - Test: Task 6 (`failed_job_reports_error`) and Task 9 (`MakeButton re-enables after error`).
3. **Double-click on Make photo or Fix.**
   - Exactly one job is submitted.
   - Test: Task 6 (`second_make_while_running_is_409`) and Task 9 (button disabled while pending).
4. **Port 8785 is already taken** (an old app or a headless server).
   - The window still opens, and Settings shows "Skit Studio connection couldn't start: port 8785 is in use".
   - Test: Task 7 (`test_studio_desktop.py::port_taken_reports`).
5. **A bad reference file** (not an image, over 20 MB, HEIC).
   - Rejected with a plain message before any spend.
   - Test: Task 6 (`bad_reference_rejected_before_spend`).

---

### Task 1: Giveaway rubric (the picture-reading check)

**Files:**
- Create: `tools/giveaway_bank.json`, `tools/giveaways.py`, `tests/test_giveaways.py`
- Modify: `tests/run_all.py` (add to `ORDER` after `test_vision_lint.py`), `.gitignore` (`.superpowers/`)

**Setup:** `git switch -c photo-studio` from `realism-gate-and-ad-vocabulary`.

**Interfaces:**
- Produces:
  - `giveaway_bank.json`: `{"version": 1, "giveaways": {key: {"label", "plain", "example", "kinds": ["animal","human",...], "fix": {card_id: option_key} | {}, "fix_phrase": str}}}`.
  - Keys, exactly:
    - `posed_centre`: dead centre, posing at the lens
    - `too_clean`: fur or skin airbrushed or too clean
    - `generic_room`: stock "sunny window, wooden furniture" room
    - `painted_mess`: dirt, mess or wear that looks drawn on
    - `studio_light`: light too perfect for the place
    - `anatomy`: odd hands, paws, eyes, teeth or ears
    - `artefacts`: glints, smears, melted details
    - `bad_text`: garbled lettering
  - `giveaways.load_bank() -> dict`
  - `giveaways.build_prompt(kind: str, has_reference: bool) -> str`: asks the vision model for JSON `{key: {"seen": bool, "where": str}}` for exactly the keys whose `kinds` include `kind`.
  - `giveaways.check(image_path, kind, reference_path=None, model=None, ask=None) -> (list[dict] | None, str | None)`.
    - Each dict is `{"key", "label", "plain", "where", "fixable": bool}`, for each key the model marked `seen: true`, in bank order.
    - Exactly one of the two return values is None.
    - `ask` defaults to `ask_llm.ask`.
    - Unknown keys are ignored. Non-JSON, or a JSON value that isn't an object, gives error `"The picture check didn't answer in a form we can read."`.
    - A missing OpenRouter key gives `ask_llm`'s own error.
  - CLI: `python tools/giveaways.py --image X --kind animal`.

- [ ] **Step 1: Write failing tests** in `tests/test_giveaways.py`, with a `fake_ask(reply)` like `tests/test_vision_lint.py`:
  - `seen_keys_come_back_in_bank_order`: the reply marks `too_clean` and `posed_centre` as seen, and the result keys equal `["posed_centre", "too_clean"]`.
  - `unknown_keys_ignored`: a reply with `{"looks_ai": {"seen": true}}` gives `[]` and no error.
  - `non_json_is_error_not_pass`: a reply `"looks great!"` gives `(None, "The picture check didn't answer in a form we can read.")`.
  - `prompt_names_only_kind_keys`: `build_prompt("human", False)` contains `"bad_text"` and `"anatomy"`, and the animal-only wording ("fur") is absent where the bank says human-only.
  - `missing_key_passes_error_through`: a fake ask that returns `(None, "OPENROUTER_API_KEY not set")` gives `(None, that message)`.
  - `every_giveaway_has_plain_copy`: every bank entry has a non-empty `label`, `plain` and `example`.
- [ ] **Step 2:** `python tests/test_giveaways.py`. Expected: fails on import.
- [ ] **Step 3:** Write the bank (Feynman copy, e.g. `too_clean.plain` = "Real fur clumps, sheds and catches dust; here it looks brushed by a computer.") and the module.
- [ ] **Step 4:** `python tests/test_giveaways.py` all OK; `python tests/run_all.py giveaways` OK.
- [ ] **Step 5:** Commit `feat(tools): giveaway rubric - a check that reads the picture`.

### Task 2: Look cards (six Feynman cards, defaults, fixes)

**Files:**
- Create: `tools/look_cards.json`, `tools/look_cards.py`, `tests/test_look_cards.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Consumes: `giveaways.load_bank()`. `local_api.compose_look(choices) -> ({part: phrase}, warnings)` and `local_api.LOOK_KEYS`.
- Produces:
  - `look_cards.json`: `{"version": 1, "cards": [{"id", "title", "plain", "example", "kinds", "options": [{"key", "label", "plain", "example", "look": {LOOK_KEY: compose-choice-or-phrase}, "kinds"}], "advanced_part": LOOK_KEY | null}]}`.
  - Card ids, in this order: `light`, `camera`, `framing`, `colour`, `pose`, `details`.
  - Each card has 4–6 curated options drawn from the existing banks. Options with `kinds` limit to animal or human. For example, `details` has fur/whisker options for animals, and pore, flyaway-hair and fabric-crease options for humans.
  - `look_cards.cards(kind: str) -> list[dict]`: cards and options filtered to `kind` (`"object"` and `"place"` use the human list minus person-only options).
  - `look_cards.defaults(kind: str, seed: int, avoid: list[dict] = ()) -> dict[str, str]`: `{card_id: option_key}`.
    - Deterministic for a given seed.
    - `light` and `details` rotate through options, skipping any choice equal to one in `avoid` (the last 5 states) when another exists.
    - `framing` defaults to an off-centre, caught-mid-moment option.
    - `pose` defaults to a candid, not-at-lens option.
  - `look_cards.to_look(state: dict[str, str], kind: str) -> dict`: a `local_api.compose_look` choices dict. It raises `ValueError` naming the card for an unknown option.
  - `look_cards.apply_fix(state: dict, giveaway_key: str, kind: str) -> (dict, str)`: returns the new state plus an extra phrase (the giveaway's `fix_phrase`, which may be empty). Unknown keys raise `ValueError`.
  - `look_cards.phrases(state, kind) -> dict[str, str]`: `compose_look(to_look(...))[0]`.

- [ ] **Step 1: Write failing tests:**
  - `six_cards_in_order`: `[c["id"] for c in cards("animal")] == ["light","camera","framing","colour","pose","details"]`.
  - `kind_filters_options`: no `cards("animal")` option has `kinds == ["human"]`, and vice versa.
  - `defaults_deterministic`: `defaults("animal", 7) == defaults("animal", 7)`.
  - `defaults_vary_and_avoid`: over seeds 0–9, `light` takes at least 3 distinct values; `defaults("human", s, avoid=[d])["light"] != d["light"]` for `d = defaults("human", s)`.
  - `default_framing_not_centred`: the default framing option's phrase does not contain "centered" or "centred", and contains "off-center" or "candid".
  - `every_option_composes`: for every kind and every option, `phrases()` returns a non-empty phrase for that card's part with no `LookError`.
  - `fix_changes_mapped_card`: `apply_fix(defaults("animal",1), "posed_centre", "animal")[0]["framing"]` equals the bank's mapped option.
  - `unmappable_fix_returns_phrase`: `apply_fix(s, "anatomy", "human")` leaves the state unchanged, and the phrase is non-empty.
  - `feynman_copy_present`: every card and option has non-empty `plain` and `example`, and `plain` is at most 120 characters.
- [ ] **Step 2:** Run. Expected: FAIL (import).
- [ ] **Step 3:** Write the JSON (copy from the banks' own phrases; plain/example written fresh) and the module.
- [ ] **Step 4:** Run. All OK.
- [ ] **Step 5:** Commit `feat(tools): six Look cards with Feynman copy, varied defaults, fixes`.

### Task 3: Realism defaults reach every prompt (Local API included)

**Files:**
- Modify: `tools/prompt_bank.json` (core layer; `version` 13 → 14), `tools/local_api.py` (`fill_layers`, `parse_prompt_request`), `tests/test_realism_lint.py`, `tests/test_local_api.py`, plus any suite asserting the old core terms.
- Create: `tools/scene_variety.py`, `tests/test_scene_variety.py`

**Interfaces:**
- Produces:
  - `scene_variety.pick(key: str, kind: str) -> dict[str, str]`: `{"light": phrase, "place": phrase}`. Deterministic per `key` (sha256 of key → index). Different keys spread across at least 5 combinations. Phrases name real, varied situations ("overcast afternoon through a north window", "kitchen strip light at night", ...), never sunny-window-plus-wood.
  - `local_api.parse_prompt_request` behaviour change: when `realism` is set and the base prompt names no light source, the light phrase from `scene_variety.pick(tag or base, kind)` is added before the tail. A skit's shots share a `tag`, so they share light.

- [ ] **Step 1: Write failing tests:**
  - `test_realism_lint.py::core_has_no_photorealistic_opener`: `"photorealistic"`, `"ultra-realistic"` and `"cinematic realism"` are not in `prompt_bank["layers"]["core"]["terms"]`, and the core layer still passes `pick` terms.
  - `test_local_api.py::realism_prompt_does_not_lead_with_photorealistic`: a `/prompt` result with `realism: {"subject": "a cat"}` doesn't start with "Photorealistic", and "photorealistic" appears nowhere the API added it.
  - `test_local_api.py::same_tag_same_light`: two `/prompt` calls with `tag: "skit-1"` and different scene text produce the same added light phrase, while `tag: "skit-2"` may differ.
  - `test_scene_variety.py`: `deterministic`, `spread_ge_5` over 50 keys, `no_sunny_wood` (no phrase contains both "sun" and "wood").
- [ ] **Step 2:** Run the three suites. Expected: the new checks FAIL.
- [ ] **Step 3:**
  - Replace the core terms with camera-truth terms: "real-world photography", "natural imperfections", "true-to-life textures", "unretouched", "candid snapshot".
  - Bump the bank version so `history.usable()` treats old ratings as stale.
  - Add `scene_variety.py`.
  - Wire it into `parse_prompt_request`.
  - Update the existing fixtures that expected the old terms.
- [ ] **Step 4:** `python tests/run_all.py` is fully green.
- [ ] **Step 5:** Commit `feat(tools): drop the "photorealistic" opener, vary light per skit`.

### Task 4: Skit Studio's photoreal preset (separate repo)

**Files:**
- Modify: `../Skit Studio/tools/write_skit.py:49-50` (`STYLES["photoreal"]`), and `../Skit Studio/tests/test_tools.py` (add the check there, in its existing style).

**Interfaces:**
- Produces:
  - `STYLES["photoreal"]` no longer contains "Photorealistic", "smartphone footage" stacked with "shallow depth of field", or any centred or posed framing.
  - New value: `"Candid phone snapshot of a real home, mixed everyday light, natural fur with clumps and stray hairs, slightly imperfect framing caught mid-moment"`.

- [ ] **Step 1:** Add the test `photoreal_preset_has_no_ai_tells`: the preset lacks "Photorealistic" (any case) and contains "candid".
- [ ] **Step 2:** `cd "../Skit Studio" && python tests/run_all.py`. Expected: the new check FAILs.
- [ ] **Step 3:** Change the string.
- [ ] **Step 4:** `python tests/run_all.py` in Skit Studio. Green, apart from failures that already exist from its uncommitted edits; record those failures before and after, and the counts must match.
- [ ] **Step 5:** `git add tools/write_skit.py tests/test_tools.py` only, then commit `fix(style): photoreal preset without AI tells`.

### Task 5: History learns from card choices; pricing moves to a kept module

**Files:**
- Create: `tools/pricing.py`, `tests/test_pricing.py`
- Modify: `tools/history.py`, `tools/pricing.json` (add `"openrouter-vision-check": {"label": "Picture check", "unit": "check", "credits_per_unit": null, "usd_per_unit": 0.01, "confidence": "estimated"}`), `tools/generate_video.py` and `tools/generate_speech.py` (re-import from `pricing`), `tests/test_history.py`

**Interfaces:**
- Produces:
  - `pricing.load_pricing() -> dict` and `pricing.estimate(model, units, pricing=None, **options) -> (credits|None, confidence, note)`, moved verbatim from `generate_video`.
  - `pricing.photo_price(provider: str, resolution: str = "1K") -> {"image": {"credits": float|None, "usd": float|None, "confidence": str}, "check": {"usd": float, "confidence": "estimated"}, "label": str}`.
    - Kie uses `nano-banana-pro`, with usd = credits × 0.005.
    - Higgsfield gives credits None and label `"unknown, billed by Higgsfield"`.
  - `history.append(..., look=None)`: stores `entry["look"] = {"kind": str, "cards": {card_id: option_key}}` when given.
  - `history.recent(limit=30) -> list[dict]`: newest first, only entries whose `image` file exists.
  - `history.THUMBS = {"up": 5, "down": 1}`.
  - `history.card_weights(entries=None) -> {card_id: {option_key: float}}`: the mean rating per option with a neutral prior of 3 and weight 2, current bank version only.
  - `look_cards.defaults` gains `weights=None`. On ties, it prefers the higher-weight option without breaking `avoid`. Add a test `weights_tilt_ties` to `test_look_cards.py`.

- [ ] **Step 1: Write failing tests:**
  - `test_pricing.py::kie_price`: `photo_price("kie")["image"]["credits"] == 24`.
  - `higgsfield_unknown`: the label contains "unknown".
  - `estimate_moved`: `pricing.estimate("nano-banana-pro", 2)[0] == 48`.
  - `test_history.py::look_stored_and_weighted`: two entries using `light: "overcast"` rated 5 and one using `light: "lamp"` rated 1 give `card_weights()["light"]["overcast"] > card_weights()["light"]["lamp"]`.
  - `recent_skips_missing_files`.
  - `weights_tilt_ties`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `python tests/run_all.py` green.
- [ ] **Step 5:** Commit `feat(tools): pricing module, history stores card choices and learns from thumbs`.

### Task 6: `studio/` app server

**Files:**
- Create: `studio/__init__.py`, `studio/state.py`, `studio/server.py`, `tests/test_studio_look.py`, `tests/test_studio_photos.py`
- Modify: `requirements.txt` (add `fastapi>=0.115`, `uvicorn>=0.30`, `httpx>=0.27`, `pywebview>=5.3`, `pythonnet>=3.0.5`; keep PyQt6 until Task 10), `tests/run_all.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 3 and 5. `local_api.parse_image_request`, `local_api.Jobs`, `local_api.record_history`. `generate_image.read_env/env_value/write_env_value/PROVIDERS`. `build_evidence.subject_kind`.
- Produces (`studio/state.py`):
  - `LookState`, thread-safe:
    - `.kind`, `.cards: dict`, `.touched: set[str]`, `.extra: list[str]`;
    - `set_card(card, option, deliberate=True)`, `reset(kind, seed, avoid, weights)`;
    - `current_phrases() -> dict[str,str]`: only the touched cards, as LOOK_KEY phrases. This is what the Local API's `current_look` returns.
- Produces (`studio/server.py`): `create_app(static_dir: Path|None, state: LookState) -> FastAPI`, with these routes (JSON):
  - **Look.**
    - `GET /api/cards?kind=` → `look_cards.cards(kind)`.
    - `POST /api/describe {text}` → `{"kind"}`. It resets defaults when the kind changes.
    - `GET /api/look` → `{kind, cards, touched}`.
    - `PUT /api/look {card, option}` → the same; marks the card touched.
  - **Price.** `GET /api/price?provider=` → `pricing.photo_price`.
  - **Photos.**
    - `POST /api/photos {text, provider, reference_b64?, reference_name?}` → `{id}`. 409 `{"error":"busy"}` if a page job is running; 400 for a bad reference.
    - `GET /api/photos/{id}` → `{state, stage, error, file_url, history_id, giveaways, check_error}`. When the job is done, the check runs on the server automatically for page jobs.
    - `POST /api/photos/{id}/fix {giveaway}` → `{id}` (a new job, after `apply_fix` and a touched card).
    - `POST /api/photos/{id}/rate {thumb: "up"|"down"}`.
    - `GET /api/recent` → `history.recent()` mapped to `{history_id, file_url, note, rating, source: "page"|"api"}`.
    - `POST /api/recent/{history_id}/check` runs the check on an API photo (a user click).
    - `GET /files/{name}` serves `temp/outputs/images/*` only (path-traversal safe).
  - **Settings.**
    - `GET /api/settings` → `{keys: {KIE_API_KEY: bool, HIGGSFIELD_API_KEY_ID: bool, HIGGSFIELD_API_KEY_SECRET: bool, OPENROUTER_API_KEY: bool}, provider, local_api: {enabled, running, error}}`.
    - `PUT /api/settings/key {name, value}` (only those four names).
    - `PUT /api/settings {provider?, local_api_enabled?}`.
  - **Static:** `web/dist` is served at `/` when `static_dir` is set.
  - `python -m studio.server --port N [--static web/dist]` runs uvicorn on 127.0.0.1 for dev and screenshots. `AIVS_HOME_OUTPUTS` or a temp dir overrides `temp/outputs` for tests.
- Page jobs:
  - Prompt = `local_api.parse_image_request({"prompt": text, "look": look_cards.to_look(...) + touched-or-default, "realism": {"subject": text}, "refine": 0, "tag": "page-"+session_seed, "provider": ..., "references": [...]})`, plus `state.extra` phrases.
  - Recorded with `history.append(..., look=...)` and note `"Studio"`.
  - The check uses `giveaways.check` with `ask` injectable via `app.state.ask`.

- [ ] **Step 1: Write failing tests** with `fastapi.testclient.TestClient`, `tests/mock_api.py` for Kie, and a fake `ask`:
  - `test_studio_look.py`:
    - `describe_sets_kind`: "my white Persian cat" → `animal`; "a woman at a bus stop" → `human`.
    - `put_marks_touched`.
    - `current_phrases_only_touched`: right after `describe`, `current_phrases() == {}`; after `PUT light`, it has exactly the light's LOOK_KEY.
    - `settings_never_returns_key_values`: no value from the `.env` fixture appears in the response text.
    - `unknown_key_name_rejected`.
  - `test_studio_photos.py`:
    - `make_runs_one_job_and_check`: after polling, state is `done`, `giveaways` is a list, and the mock got exactly 1 generate call.
    - `second_make_while_running_is_409`.
    - `fix_applies_card_and_spends_once`: the mapped card changed, it's in `touched`, and there was exactly 1 more generate call.
    - `check_without_key`: the fake ask returns an error; `giveaways` is None, `check_error` is non-empty, and the photo `file_url` is still set.
    - `failed_job_reports_error`: the mock returns 402, so `state == "error"` and the error text contains the remedy.
    - `bad_reference_rejected_before_spend`: non-image bytes, and separately 21 MB, each give 400 with 0 generate calls.
    - `recent_includes_api_photos`: a history row with note "Skit Studio" appears with `source: "api"`.
    - `files_route_blocks_traversal`: `/files/..%2F.env` gives 404.
    - `no_route_spends_on_get`: no GET route causes a generate call.
- [ ] **Step 2:** Run both suites. Expected: FAIL.
- [ ] **Step 3:** Implement `state.py` and `server.py`. Generation runs on `local_api.Jobs`'s executor; the check runs in the job thread after `done`.
- [ ] **Step 4:** `python tests/run_all.py` green.
- [ ] **Step 5:** Commit `feat(studio): app server - look state, photos, check, fix, recent, settings`.

### Task 7: Desktop window + launch

**Files:**
- Create: `studio/desktop.py`, `start.bat`, `dev.bat`, `tests/test_studio_desktop.py`

**Interfaces:**
- Consumes: `create_app`, `LookState`, `local_api.start(port, current_look, on_image)`.
- Produces:
  - `studio.desktop.free_port() -> int`.
  - `studio.desktop.start_local_api(state, enabled: bool) -> (LocalApi|None, str|None)`. The error text for a port in use is exactly `"Skit Studio connection couldn't start: port {port} is in use"`.
  - `studio.desktop.main()`:
    - starts uvicorn on a free port in a daemon thread;
    - starts the Local API with `current_look=state.current_phrases`;
    - opens a pywebview window titled "AI Video Studio" (1440×900, minimum 1280×720) once the server is up;
    - on close, stops the Local API and uvicorn.
  - `start.bat`: `npm ci` if `web/node_modules` is missing, then `npm run build`, then `python -m studio.desktop`.
  - `dev.bat`: uvicorn `--reload` on 8790 plus `npm run dev` on 5178.

- [ ] **Step 1: Write failing tests:**
  - `port_taken_reports`: bind a socket on a free port P, set `AIVS_LOCAL_API_PORT=P`, and check that `start_local_api(state, True)` returns `(None, "Skit Studio connection couldn't start: port P is in use")`.
  - `disabled_returns_none_no_error`.
  - `current_look_wired`: start on a free port, `PUT` a card through the state, and check that `GET /api/v1/look/current` reflects it.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. `pip install -r requirements.txt` and confirm `import webview` works.
- [ ] **Step 4:** Tests green, and a manual `python -m studio.desktop` opens a window (screenshot to `.impeccable/review/t7-window.png`).
- [ ] **Step 5:** Commit `feat(studio): desktop window, start.bat`.

### Task 8: Web shell, Darkroom tokens, Settings

**Files:**
- Create: `web/` (Vite React TS: `package.json`, `vite.config.ts` with `base: './'` and a dev proxy `/api` and `/files` → 8790, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/styles/tokens.css`, `src/lib/api.ts`, `src/pages/Settings.tsx`, `src/components/Term.tsx`), `web/src/**/*.test.tsx`
- Modify: `.gitignore` (`web/node_modules`, `web/dist`)

**Interfaces:**
- Produces:
  - `api.ts` has typed wrappers, one per Task 6 route:
    - `getCards(kind)`, `describe(text)`, `getLook()`, `setCard(card, option)`, `getPrice(provider)`;
    - `makePhoto(body)`, `getPhoto(id)`, `fixPhoto(id, giveaway)`, `ratePhoto(id, thumb)`;
    - `getRecent()`, `checkRecent(historyId)`;
    - `getSettings()`, `setKey(name, value)`, `setSettings(patch)`.
    Errors throw `ApiError {status, message}`.
  - `<Term word plain example>` is a dotted-underline button opening a popover ("In plain words … / Like …"). It's keyboard accessible, and Esc closes it.
  - `App` is the one-page layout: a header with the app name and a Settings gear, and a two-column main area (left `min(440px, 36%)`, right flex). Settings opens as a side sheet.
  - `tokens.css` holds the Global Constraints colours as CSS variables plus Inter `@font-face` from `../assets/fonts`.
  - Settings shows each key as "set" or "not set" with a paste field (never showing the value), the image-maker choice (Kie default, Soul with its "can't use a reference photo" note), and the Skit Studio connection on/off with its status or error text.

- [ ] **Step 1: Write failing tests (vitest + Testing Library):**
  - `Settings never renders key values`.
  - `Term opens and closes with keyboard`.
  - `local api error text shown`.
- [ ] **Step 2:** `npx vitest run`. Expected: FAIL.
- [ ] **Step 3:** Implement. `npm run typecheck && npm run build` are clean.
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** Commit `feat(web): darkroom shell, settings, Term popover`.

### Task 9: Left column: describe, reference, Look cards, price, Make photo

**Files:**
- Create: `web/src/pages/studio/{Describe,Reference,LookCards,CardPicker,MakeButton}.tsx` and their tests
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `api.ts` and `Term`.
- Produces: a `useStudio()` hook in `web/src/lib/studio.tsx` that holds `{text, kind, look, price, provider, reference, job, pending}` and exposes `make()` and `fix(key)`.
- Behaviour:
  - Typing in Describe debounces 600 ms, then calls `describe()`. The subject kind shows as a chip ("Pet photo" or "People photo").
  - Each card shows its title with a `Term`-style explanation, the current option label, and a one-line `plain`. Clicking opens `CardPicker`, which lists options with plain/example.
  - "More controls" (Advanced) is collapsed by default.
  - Reference accepts PNG, JPEG and WebP up to 20 MB, client-checked first, then server-checked. A Soul provider disables it, with a reason.
  - `MakeButton` label: `Make photo · ~€{image+check}`, or `Make photo · price unknown` for Soul. It's disabled while `pending`, while the text is empty, or while the image key is missing (with a link to Settings).

- [ ] **Step 1: Write failing tests:**
  - `MakeButton disabled while pending`.
  - `MakeButton re-enables after error`.
  - `MakeButton shows price incl. check`: price `{image: {usd: 0.12}, check: {usd: 0.01}}` gives a label containing "0.13".
  - `Soul disables reference with reason`.
  - `reference over 20 MB rejected without request`.
  - `six cards render with plain line`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tests and typecheck green. Take a screenshot at 1366×768 (headless Edge against `npm run build`, served by `python -m studio.server --port 8790`, using a temp history): `.impeccable/review/t9-left-1366.png`. The left column must not scroll.
- [ ] **Step 5:** Commit `feat(web): describe, reference, six Look cards, priced Make photo`.

### Task 10: Right column: photo, "Does this look real?", Fix, recent strip

**Files:**
- Create: `web/src/pages/studio/{PhotoPanel,RealCheck,RecentStrip}.tsx` and their tests
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `useStudio()`, `getPhoto` polled every 1.5 s while a job runs, `getRecent()` polled every 10 s, `checkRecent`, `ratePhoto`.
- States:
  - **Empty:** a short Feynman intro: "Describe what's in the photo on the left. The app makes it, then looks at it like a sceptical friend would and points out what gives it away."
  - **Generating:** stage text from the job. No fake progress bar.
  - **Done:**
    - The photo is fitted on a `#0E0E0E` ground.
    - `RealCheck`:
      - When there are giveaways: "N things give it away", each with `label`, `plain`, `where`, and a `Fix · ~€x` button (`fixable` false → "Try again with a fix · ~€x" using the phrase).
      - When there are none: "Nothing obvious gives it away. Still look closely: you're the final judge."
      - When the check errored: "The picture check couldn't run: {reason}".
  - **Error:** the plain error text and the Make button re-enabled.
- `RecentStrip`: thumbnails, newest first, with a source badge ("Skit Studio" for API photos) and 👍/👎 buttons (`aria-pressed`). Clicking opens it in the photo panel. API photos show a "Check this photo · ~€0.01" button.

- [ ] **Step 1: Write failing tests:**
  - `zero giveaways never says "real"`: the text doesn't match `/looks real|undetectable|passes/i`.
  - `check error shows reason and keeps photo`.
  - `fix button shows price and calls fixPhoto once on double click`.
  - `api photo shows check button, page photo does not`.
  - `thumb toggles aria-pressed`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tests green. Screenshots at 1366×768 and 1920×1080 of the empty, generating, done-with-giveaways, check-error and missing-key states (temp history plus mock Kie plus a fake ask, via `STUDIO_FAKE_ASK=1`, a test-only env flag honoured in `server.py`): `.impeccable/review/t10-*.png`.
- [ ] **Step 5:** Commit `feat(web): photo panel, picture check with priced Fix, recent strip with thumbs`.

### Task 11: Delete everything else

**Files:**
- Delete: `ui/`, `gui.py`, `AIVideoStudio.spec`, `pyqt6_system_prompt.md`, `build/`, `dist/`, plus every `tools/` module, `*_bank.json` and `workflows/*.md` that the kept set doesn't reach, and their `tests/test_*.py` (including all `*_gui.py`, `smoke_gui.py`, `screenshot_all.py`, `test_newui.py`, `test_layout.py`, `test_ui_polish.py`, `test_design_tokens.py`, `test_workers.py`).
- Create: `tools/keep_set.py` (a script that prints the transitive local-import closure).
- Modify: `requirements.txt` (drop PyQt6; keep `imageio-ffmpeg` only if a kept module imports it), `tests/run_all.py` `ORDER`, `README.md`, `CLAUDE.md` (folder map, current phase), `AGENTS.md`, `.github/workflows/tests.yml`.

**Interfaces:**
- Kept roots: `studio/`, `tools/local_api.py`, `mcp_server/server.py`, `tools/giveaways.py`, `tools/look_cards.py`, `tools/refine_image.py`, `tools/vision_lint.py`, `tools/history.py`, `tools/pricing.py`, `tools/scene_variety.py`, `tools/realism_lint.py`, `tools/generate_image.py`, `tools/upscale_image.py`. Everything they import transitively is kept, along with any `*_bank.json` those modules load.

- [ ] **Step 1:** Write `tools/keep_set.py` (it parses `import x` lines across `tools/` and `studio/`) and run it. Save the delete list to the task report and review it against the spec's Non-goals list. Nothing on the kept list may be deleted.
- [ ] **Step 2:** Delete, then update `ORDER`, requirements and docs. Rewrite README as a short EN guide: what it does, `start.bat`, keys, the Skit Studio link, and the note that it never alters provenance.
- [ ] **Step 3:** `python tests/run_all.py` green. `python tools/local_api.py --serve` answers `/api/v1/health`. In `../Skit Studio`, `python tests/run_all.py test_avs` is unchanged from Task 4's baseline.
- [ ] **Step 4:** `python -c "import PyQt6"` fails or is unused. `grep -r "PyQt6" --include=*.py .` returns nothing.
- [ ] **Step 5:** Commit `chore: remove every tab but Look and Image, and the PyQt GUI`.

### Task 12: Verification and polish pass

**Files:** fixes only, wherever the audit points.

- [ ] **Step 1:** Run the impeccable audit and polish over `web/src` against the Global Constraints:
  - contrast AA;
  - focus rings;
  - `prefers-reduced-motion`;
  - empty, loading and error states;
  - no unexplained jargon (every Look word is a `Term`).
  Fix the findings.
- [ ] **Step 2:** Run the full suites: `python tests/run_all.py`, `npx vitest run`, `npm run typecheck && npm run build`.
- [ ] **Step 3:** MCP smoke test with the app open: `avs_status`, `look_options` and `prompt_preview` answer, and `prompt_preview` doesn't start with "Photorealistic".
- [ ] **Step 4:** Re-take the screenshots from Tasks 9 and 10 and review them by eye.
- [ ] **Step 5:** Ask the user to approve one real pet photo and one real person photo, and record the giveaways for each. Don't spend without that approval.
- [ ] **Step 6:** Commit `chore: verification pass`.
