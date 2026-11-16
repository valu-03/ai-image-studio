# AI Image Studio: notes for Codex and other agents

**Read [CLAUDE.md](CLAUDE.md) first.** It holds this project's full instructions.

## In short
- A one-page Darkroom photo studio (`studio/` FastAPI backend + `web/` React/Vite/Tailwind UI in a `pywebview` desktop window, launched via `start.bat`).
- The left column has the photo description, optional reference photo, six Feynman-explained **Look cards** (`tools/look_cards.py`), and a priced **Make photo** button (`tools/pricing.py`).
- The right column displays the photo, runs the picture-reading giveaway rubric (`tools/giveaways.py`) with click-to-Fix, and shows a recent strip with 👍/👎 ratings that train `tools/history.py`.
- **Local API** on `127.0.0.1:8785` (`tools/local_api.py`) runs while the app is open, or headless with `python tools/local_api.py --serve`. The MCP server (`mcp_server/server.py`, registered by `python mcp_server/install.py`) is a thin client of it.
- **MCP server** (`mcp_server/server.py`) wraps that API: `avs_status`, `look_options`, `look_current`, `look_compose`, `prompt_preview` (free), and `image_generate` (paid: returns the price until `approved=True`), plus `image_wait`, `image_get` and `image_cancel`.
- Run the tests with `python tests/run_all.py` and `npm --prefix web test`. They use local mock servers and spend nothing.
