"""studio/ app server - photos, check, fix, recent, files (mock Kie, fake ask, no spend)."""
import base64
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import mock_api  # noqa: E402

MOCK_PORT = 8816
mock_api.serve(MOCK_PORT)
TMP = Path(tempfile.mkdtemp(prefix="aivs-studio-photos-"))
ENV = TMP / ".env"
BASE = "http://127.0.0.1:{}".format(MOCK_PORT)


def write_env(base=BASE):
    ENV.write_text("KIE_API_KEY=fake-kie\nAIVS_API_BASE={}\n".format(base), encoding="utf-8")


write_env()
os.environ["AIVS_ENV_FILE"] = str(ENV)
os.environ["AIVS_OUTPUTS_DIR"] = str(TMP / "outputs")
os.environ["AIVS_POLL_INTERVAL"] = "0.2"
os.environ.pop("AIVS_HISTORY_FILE", None)

from fastapi.testclient import TestClient  # noqa: E402

import history  # noqa: E402
from studio.server import create_app  # noqa: E402
from studio.state import LookState  # noqa: E402

# The seam must have moved history too, or this suite would touch real data.
assert str(history.HISTORY).startswith(str(TMP)), history.HISTORY

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


state = LookState()
app = create_app(None, state)
SEEN = ('{"studio_light": {"seen": true, "where": "on the sofa"}, '
        '"posed_centre": {"seen": false, "where": ""}}')
app.state.ask = lambda prompt, images=(), model=None, **kw: (SEEN, None)
client = TestClient(app)
PNG = base64.b64encode(mock_api.PNG).decode()


def make(text="my white Persian cat asleep on a sofa", **extra):
    return client.post("/api/photos", json=dict({"text": text, "provider": "kie"}, **extra))


def wait(photo_id, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        job = client.get("/api/photos/" + photo_id).json()
        if job["state"] in ("done", "error"):
            return job
        time.sleep(0.05)
    return job


print("Make")
mock_api.reset()
r = make()
check("make accepted", r.status_code == 200 and r.json().get("id"), r.text)
first = r.json()["id"]
r2 = make()
check("second make while running is 409", r2.status_code == 409
      and r2.json() == {"error": "busy"}, r2.text)
job = wait(first)
check("job done with a giveaways list", job["state"] == "done"
      and isinstance(job["giveaways"], list) and job["giveaways"][0]["key"] == "studio_light",
      str(job))
check("exactly one generate call", mock_api.STATE["creates"] == 1, str(mock_api.STATE["creates"]))
check("photo url and history id set", job["file_url"].startswith("/files/") and job["history_id"])
served = client.get(job["file_url"])
check("photo is served byte for byte",
      served.status_code == 200 and served.content == mock_api.PNG)
row = history.load()[-1]
check("history row is a Studio row with its look", row["note"] == "Studio"
      and row["look"]["kind"] == "animal" and "light" in row["look"]["cards"],
      str(row.get("look")))

print("Rate")
r = client.post("/api/photos/{}/rate".format(first), json={"thumb": "up"})
check("thumb up stores a 5", r.status_code == 200 and history.load()[-1]["rating"] == 5, r.text)
check("bad thumb rejected", client.post("/api/photos/{}/rate".format(first),
                                        json={"thumb": "meh"}).status_code == 400)

print("Fix")
client.put("/api/look", json={"card": "light", "option": "window_daylight"})
before = mock_api.STATE["creates"]
r = client.post("/api/photos/{}/fix".format(first), json={"giveaway": "studio_light"})
check("fix accepted", r.status_code == 200 and r.json().get("id"), r.text)
fixed = wait(r.json()["id"])
look = client.get("/api/look").json()
check("fix changed the mapped card and touched it",
      look["cards"]["light"] == "practical_mixed" and "light" in look["touched"]
      and look["cards"]["colour"] == "muted_natural", str(look))
check("fix spends exactly once", mock_api.STATE["creates"] == before + 1)
check("fix photo done", fixed["state"] == "done", str(fixed))
check("unfixable giveaway rejected", client.post(
    "/api/photos/{}/fix".format(first), json={"giveaway": "nope"}).status_code == 400)

print("Check without a key")
app.state.ask = lambda prompt, images=(), model=None, **kw: (
    None, "OPENROUTER_API_KEY is not set in .env")
r = make("a ginger cat on a windowsill")
nokey = wait(r.json()["id"])
check("photo still shows, check says why", nokey["state"] == "done" and nokey["giveaways"] is None
      and nokey["check_error"] and nokey["file_url"], str(nokey))
app.state.ask = lambda prompt, images=(), model=None, **kw: ("not json at all", None)
r = make("a ginger cat on a windowsill")
junk = wait(r.json()["id"])
check("off-schema reply is an error, not 'looks real'",
      junk["giveaways"] is None and junk["check_error"], str(junk))
app.state.ask = lambda prompt, images=(), model=None, **kw: (SEEN, None)

print("Failed generation")
write_env(BASE + "/nocredit")
mock_api.reset()
r = make("a ginger cat on a windowsill")
bad = wait(r.json()["id"])
check("402 reports the remedy", bad["state"] == "error" and "out of credit" in bad["error"]
      and bad["file_url"] is None, str(bad))
write_env()
r = make("a ginger cat")
check("make works again after an error", r.status_code == 200, r.text)
wait(r.json()["id"])

print("References")
mock_api.reset()
big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (21 * 1024 * 1024)).decode()
heic = base64.b64encode(b"\x00\x00\x00\x18ftypheic" + b"0" * 40).decode()
for label, ref in (("not an image", base64.b64encode(b"hello, not a picture").decode()),
                   ("21 MB", big), ("not base64", "!!!"), ("HEIC", heic)):
    r = make(reference_b64=ref, reference_name="r.png")
    check("bad reference ({}) is 400 before spend".format(label), r.status_code == 400, r.text)
check("no generate call for bad references", mock_api.STATE["creates"] == 0)
r = make(provider="higgsfield", reference_b64=PNG)
check("higgsfield + reference is refused plainly", r.status_code == 400, r.text)
check("still no generate call", mock_api.STATE["creates"] == 0)
r = make(reference_b64=PNG, reference_name="r.png")
check("a real PNG reference is accepted", r.status_code == 200, r.text)
wait(r.json()["id"])

print("Recent / files")
images = Path(os.environ["AIVS_OUTPUTS_DIR"]) / "images"
(images / "api-1.png").write_bytes(mock_api.PNG)
history.append({"subject": "a cat", "slug": "s"}, "p", {}, 8, True,
               image=str(images / "api-1.png"), note="Local API")
rows = client.get("/api/recent").json()
api_row = next((x for x in rows if x["note"] == "Local API"), None)
check("recent includes API photos", api_row and api_row["source"] == "api", str(rows)[:300])
check("recent marks page photos", any(x["source"] == "page" for x in rows))
r = client.post("/api/recent/{}/check".format(api_row["history_id"]))
check("check on an API photo runs on click", r.status_code == 200
      and isinstance(r.json()["giveaways"], list), r.text)
check("files route blocks traversal", client.get("/files/..%2F.env").status_code == 404
      and client.get("/files/../.env").status_code == 404
      and client.get("/files/%2e%2e%5chistory.jsonl").status_code == 404)
check("missing file is 404", client.get("/files/nope.png").status_code == 404)

print("GET never spends")
mock_api.reset()
paths = ["/api/photos/{}".format(first), "/files/x.png", "/api/cards?kind=animal",
         "/api/price?provider=kie"]
for route in app.routes:
    if "GET" in getattr(route, "methods", ()) and "{" not in route.path \
            and route.path not in ("/openapi.json", "/docs", "/docs/oauth2-redirect",
                                   "/redoc", "/api/cards", "/api/price"):
        paths.append(route.path)
for path in paths:
    client.get(path)
check("no GET route generates", mock_api.STATE["creates"] == 0 and len(paths) >= 6, str(paths))

print("FAILED: {}".format(fails) if fails else "ALL OK")
sys.exit(1 if fails else 0)
