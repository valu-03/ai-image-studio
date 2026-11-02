# AI Image Studio

A one-page Darkroom photo studio for making realistic photos of pets and people, with a picture-reading check that points out what gives an AI image away and lets you fix it with one click.

## Quick start

Double-click **`start.bat`** (or run it from a terminal):

```bat
start.bat
```

On first launch it installs the web dependencies (`npm ci`), builds the interface (`web/dist`), starts the local server and Skit Studio connection (`127.0.0.1:8785`), and opens the **AI Image Studio** desktop window.

For live reload while editing the UI:

```bat
dev.bat
```

## API keys

Open **Settings** (top-right gear) or copy `.env.example` to `.env`:

- `KIE_API_KEY` — Nano Banana Pro image generation (default, ~$0.12 per photo, supports a reference photo to lock pet/person identity).
- `OPENROUTER_API_KEY` — runs the **"Does this look real?"** vision check (~$0.01 per check). If omitted, photos still generate normally and the check panel notes that the key is missing.
- `HIGGSFIELD_API_KEY_ID` and `HIGGSFIELD_API_KEY_SECRET` — optional Higgsfield Soul image maker (cannot use a reference photo).

Keys are stored in `.env` and are never displayed on screen.

## How it works

1. **Describe** what's in the photo on the left. The app detects whether it's a pet or person photo and picks realistic defaults for the six **Look cards** (*Light*, *Camera*, *Framing*, *Colour*, *Pose*, *Lived-in details*).
2. Every technical term is underlined — click it (or press Enter/Space) for a plain-words Feynman explanation and an everyday example.
3. Click **Make photo** (the button shows the estimated cost including the picture check). Nothing is ever spent without your click.
4. When the photo finishes, the **"Does this look real?"** check reads the image and lists any giveaways (such as dead-centre framing, studio-perfect light, or airbrushed fur/skin), each with a **Fix** button that adjusts the matching Look card and remakes the photo on click.
5. Rate photos with 👍/👎 in the recent strip at the bottom to teach the app which card choices work best for you.

## Skit Studio & MCP connection

While AI Image Studio is open (or when running headless with `python tools/local_api.py --serve`), the Local API listens on `http://127.0.0.1:8785`:

- **Skit Studio** uses it to generate character sheets and scene stills with the Look cards you deliberately chose on the page (`/api/v1/look/current`), and those stills appear in the Recent strip with a **Skit Studio** badge so you can check and rate them too.
- The **MCP server** (`python mcp_server/server.py`) exposes `avs_status`, `look_options`, `look_current`, `look_compose`, `prompt_preview`, and `image_generate`.

## Provenance

Realism comes from photography choices (natural light, lens behaviour, framing, and lived-in texture) only. AI Image Studio never removes, alters, or fakes provenance metadata (such as C2PA or watermarks); saved image files are written byte-for-byte as returned by the provider.

## Tests

```bat
python tests/run_all.py
npm --prefix web test
```

All suites use local mock servers and spend nothing.
