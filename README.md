<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo/ai-image-studio-horizontal-reversed.svg">
  <img alt="AI Image Studio" src="assets/logo/ai-image-studio-horizontal.svg" width="420">
</picture>

![Windows](https://img.shields.io/badge/Windows-desktop_app-0078d4?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React_18-Vite_6-61dafb?style=flat-square&logo=react&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-server-8b5cf6?style=flat-square)

A desktop photo studio for making realistic AI photos of pets and people. After each photo, a picture-reading check lists what gives it away as AI, and each problem it finds has a button that adjusts the settings and makes the photo again.

[Features](#features) • [Getting started](#getting-started) • [How it works](#how-it-works) • [Local API and MCP](#local-api-and-mcp-server) • [Development](#development)

</div>

> [!IMPORTANT]
> Making photos costs money on your own API accounts. The **Make photo** button shows the estimated price before anything is spent, and nothing is charged without that click.

## Features

- One page: describe the photo on the left, see the result and its realism check on the right.
- Six Look cards (Light, Camera, Framing, Colour, Pose, Small details) start from realistic defaults for a pet or a person, picked from what you typed.
- Every technical term is underlined. Click it for a plain-words explanation and an everyday example.
- An optional reference photo keeps the same pet or person across shots.
- The "Does this look real?" check reads the finished image against 8 giveaways, such as dead-centre framing, studio-perfect light or airbrushed skin and fur. Each one comes with a **Fix** button that adjusts the matching Look card and remakes the photo.
- Thumbs up or down on recent photos teaches the app which card choices work for you.
- An MCP server lets AI agents (Claude Code, Codex, Gemini CLI, Cursor and other MCP clients) build prompts with your Look cards and generate images, whether the app is open or not.

## Getting started

### Prerequisites

- Windows 10 or 11
- [Python](https://www.python.org/) 3.11 or newer (CI runs the tests on 3.11)
- [Node.js](https://nodejs.org/) 18 or newer, to build the interface
- An API key for at least one image model (see below)

### Install and run

```powershell
git clone https://github.com/valu-03/ai-image-studio.git
cd ai-image-studio
pip install -r requirements.txt
start.bat
```

On first launch `start.bat` installs the web dependencies (`npm ci`), builds the interface into `web/dist`, starts the local server and opens the **AI Image Studio** window. Later launches only rebuild the interface, so it never goes stale.

### API keys

Add your keys in **Settings** (the gear at the top right) or copy `.env.example` to `.env`. The app never shows a stored key on screen.

| Key | Used for | Approximate cost |
|---|---|---|
| `KIE_API_KEY` | Nano Banana Pro, the default image model. It accepts a reference photo. | about $0.12 per photo |
| `OPENROUTER_API_KEY` | The "Does this look real?" check. Without it, photos still generate and the panel says the key is missing. | about $0.01 per check |
| `HIGGSFIELD_API_KEY_ID`, `HIGGSFIELD_API_KEY_SECRET` | Higgsfield Soul, an optional second image model. It cannot use a reference photo. | |

> [!NOTE]
> Kie publishes no price list through its API, so the photo price starts as an estimate. After the first real charge for a model, the app shows the measured cost instead.

## How it works

1. Describe what's in the photo. The app works out whether it shows a pet or a person and sets the six Look cards.
2. Adjust any card. Each choice is a photography decision (light source, lens, framing, colour, pose, small lived-in details) written into the prompt.
3. Click **Make photo**. The button shows the cost, including the realism check.
4. When the photo arrives, the check lists the giveaways it found. Click **Fix** on one and the app changes that Look card and makes the photo again.
5. Rate the result. Ratings are stored in `temp/outputs/history.jsonl` and steer future defaults.

The realism comes from photography choices only. AI Image Studio never removes, alters or fakes provenance metadata such as C2PA or watermarks, and it saves images exactly as the provider returns them.

## Local API and MCP server

The MCP server in `mcp_server/server.py` lets AI agents use the app's image engine. To register it with every AI client on your PC, run this from the project folder:

```powershell
python mcp_server/install.py
```

The installer first runs the server's self-test, then adds it to Claude Code, Codex, Gemini CLI, Cursor, Claude Desktop and Windsurf, whichever of them are installed. Each entry uses the full path of the Python that ran the installer and of `server.py`, so it works from any folder and on any PC. Restart the client afterwards.

| Command | What it does |
|---|---|
| `python mcp_server/install.py --only claude,codex` | Registers with the clients you name |
| `python mcp_server/install.py --print` | Prints the config block to paste into any other MCP client, changing nothing |
| `python mcp_server/install.py --uninstall` | Removes the entries again |
| `python mcp_server/server.py --check` | Shows which Python, engine and API keys the server sees |

While the app is open, the server talks to the app's Local API on `http://127.0.0.1:8785`, so `look="current"` uses the Look on screen. With the app closed, the server starts its own copy of the engine on a free port, so the app can still be opened later. Photos made this way appear in the recent strip with an **API** badge, where you can check and rate them too. To run the Local API on its own for scripts, use `python tools/local_api.py --serve`.

| Tool | What it does | Spends money |
|---|---|---|
| `avs_status` | Checks the connection and which keys are set | no |
| `look_options`, `look_current`, `look_compose` | Lists the Look choices, reads the current Look, builds one | no |
| `prompt_preview` | Returns the finished prompt | no |
| `image_generate` | Makes an image. It returns the price first and only generates when called again with `approved=True`. | yes |
| `image_wait`, `image_get`, `image_cancel` | Follows, fetches or cancels a running image. `image_wait` returns after 45 seconds so it stays inside Codex's 60-second tool limit; call it again until the image is done. | no |

## Development

```powershell
dev.bat
```

`dev.bat` runs the API with auto-reload on port 8790 and the Vite dev server on port 5178, so interface changes show up live.

Both test suites use local mock servers and spend nothing:

```powershell
python tests/run_all.py
npm --prefix web test
```

To build a Windows `.exe` with PyInstaller:

```powershell
pyinstaller AIImageStudio.spec
```

> [!WARNING]
> The built app reads its keys from a `.env` file next to the `.exe`. Never commit `dist/`; it is in `.gitignore` for that reason.

### Project structure

```text
studio/        FastAPI app server, Look state and the pywebview desktop window
web/           React 18 + Vite 6 + TypeScript + Tailwind v4 interface
tools/         prompt building, Look cards, realism check, pricing, history, Local API
mcp_server/    MCP server over the Local API
workflows/     step-by-step procedures for agents (avatars, consistent characters, realism)
tests/         Python suites; run_all.py runs them all
assets/        logo, app icons and fonts (Inter, JetBrains Mono)
```

`CLAUDE.md` holds the full project notes for AI coding agents, and `AGENTS.md` is a short version for Codex and others.
