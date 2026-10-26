# AI Video Studio: notes for Codex and other agents

**Read [CLAUDE.md](CLAUDE.md) first.** It holds this project's full instructions. They were
written for Claude Code and apply to you just the same.

## In short
- A PyQt6 app for AI images, video and ads. The Compose tab builds image prompts from banks
  and lints them to 8/8 realism. The Look tab builds lighting, composition, camera, color,
  posing, style, capture and evidence. Refine retries the weak layer after a vision critique.
- **Local API** on 127.0.0.1:8785 (`tools/local_api.py`) while the app is open, or run it
  headless with `python tools/local_api.py --serve`. Skit Studio uses it for its stills.
- **MCP server** `ai-video-studio` (`mcp_server/server.py`) wraps that API: `avs_status`,
  `look_options`, `look_current`, `look_compose`, `prompt_preview` (free), and
  `image_generate` (paid: it returns the price until `approved=True`), plus `image_wait`,
  `image_get` and `image_cancel`.
- Run the tests with `python tests/run_all.py`. They use local mock servers and spend nothing.
- Git: work is on branch `realism-gate-and-ad-vocabulary`; `main` is behind. This branch has
  uncommitted realism and Refine work for the Local API. Commit only when asked.
- Known bug, reported and not fixed: `tools/generate_video.py` `_resolve()` ignores
  `AIVS_API_BASE`.
