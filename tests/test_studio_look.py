"""studio/ app server - the Look state and settings routes (no network, no spend)."""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TMP = Path(tempfile.mkdtemp(prefix="aivs-studio-look-"))
ENV = TMP / ".env"
ENV.write_text("KIE_API_KEY=sk-secret-kie-111\nOPENROUTER_API_KEY=sk-secret-or-222\n"
               "HIGGSFIELD_API_KEY_SECRET=sk-secret-hf-333\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(ENV)
os.environ["AIVS_OUTPUTS_DIR"] = str(TMP / "outputs")
os.environ.pop("AIVS_HISTORY_FILE", None)

from fastapi.testclient import TestClient  # noqa: E402

import generate_image as gi  # noqa: E402
import look_cards  # noqa: E402
from studio.server import create_app  # noqa: E402
from studio.state import LookState  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


state = LookState()
client = TestClient(create_app(None, state))

print("Look")
r = client.post("/api/describe", json={"text": "a woman at a bus stop"})
check("describe: a woman is human", r.json() == {"kind": "human"}, r.text)
r = client.post("/api/describe", json={"text": "my white Persian cat"})
check("describe: a cat is animal", r.json() == {"kind": "animal"}, r.text)
check("kind change resets defaults", client.get("/api/look").json()["touched"] == [])
check("cards route", len(client.get("/api/cards", params={"kind": "animal"}).json()) == 6)
check("cards route rejects a bad kind",
      client.get("/api/cards", params={"kind": "x"}).status_code == 400)

check("current_phrases is empty right after describe", state.current_phrases() == {})
light = [c for c in look_cards.cards("animal") if c["id"] == "light"][0]["options"]
pick = next(o for o in light if o["key"] != client.get("/api/look").json()["cards"]["light"])
r = client.put("/api/look", json={"card": "light", "option": pick["key"]})
check("put marks touched", r.json()["touched"] == ["light"]
      and r.json()["cards"]["light"] == pick["key"], r.text)
check("current_phrases has exactly the light's key",
      set(state.current_phrases()) == set(pick["look"]), str(state.current_phrases()))
check("put rejects an unknown option",
      client.put("/api/look", json={"card": "light", "option": "nope"}).status_code == 400)
check("put rejects an unknown card",
      client.put("/api/look", json={"card": "nope", "option": "x"}).status_code == 400)
state.set_card("colour", "warm_film", deliberate=False)
check("non-deliberate set does not touch", "colour" not in state.touched)

opts = client.get("/api/look/options").json()
check("look/options exposes all 8 Look sub-builders",
      set(opts) == {"lighting", "composition", "camera", "color", "posing", "style", "capture", "evidence"})
comp_res = client.post("/api/look/compose", json={
    "part": "lighting",
    "pick": {"setup": opts["lighting"]["setups"][0]["key"]},
    "apply": True,
}).json()
check("look/compose applies override to Look state",
      bool(comp_res["phrases"].get("lighting"))
      and comp_res["look"]["overrides"].get("lighting") == comp_res["phrases"]["lighting"])
clear_res = client.put("/api/look/override", json={"part": "lighting", "phrase": ""}).json()
check("look/override clears override when empty", "lighting" not in clear_res["overrides"])

c_opts = client.get("/api/compose/options").json()
check("compose/options exposes purposes, shots, lighting, colour, guides, skin_features",
      all(k in c_opts for k in ("purposes", "shots", "lighting_terms", "colour_terms", "composition_guides", "skin_features")))
c_prev = client.post("/api/compose/preview", json={
    "form": {
        "subject": "a woman in her late twenties with light freckles",
        "wardrobe": "an oversized cream knit sweater",
        "setting": "a bright apartment kitchen, mid-morning",
        "action": "leaning against the counter with a mug",
        "posing": "weight on the back foot",
        "mood": "calm and unhurried",
    }
}).json()
check("compose/preview builds prompt, lint, and derived notes",
      bool(c_prev["prompt"]) and c_prev["kind"] == "human" and "score" in c_prev["lint"])

print("Settings")
r = client.get("/api/settings")
check("settings has booleans only",
      r.json()["keys"] == {"KIE_API_KEY": True, "HIGGSFIELD_API_KEY_ID": False,
                           "HIGGSFIELD_API_KEY_SECRET": True, "OPENROUTER_API_KEY": True},
      r.text)
check("settings never returns key values",
      not any(v in r.text for v in ("sk-secret-kie-111", "sk-secret-or-222", "sk-secret-hf-333")))
r = client.put("/api/settings/key", json={"name": "KIE_API_KEY", "value": "sk-new-999"})
check("a named key can be written", gi.read_env().get("KIE_API_KEY") == "sk-new-999"
      and "sk-new-999" not in r.text)
r = client.put("/api/settings/key", json={"name": "PATH", "value": "x"})
check("unknown key name rejected", r.status_code == 400 and "PATH" not in gi.read_env())
r = client.put("/api/settings", json={"provider": "higgsfield", "local_api_enabled": False})
check("provider and local api saved", r.json()["provider"] == "higgsfield"
      and r.json()["local_api"]["enabled"] is False, r.text)
check("unknown provider rejected",
      client.put("/api/settings", json={"provider": "bogus"}).status_code == 400)
p = client.get("/api/price", params={"provider": "higgsfield"}).json()
check("higgsfield price is unknown, not a number", p["image"]["usd"] is None
      and "unknown" in p["label"], str(p))
p = client.get("/api/price", params={"provider": "kie"}).json()
check("kie price is a dollar figure", p["label"].startswith("about $"), str(p))

print("FAILED: {}".format(fails) if fails else "ALL OK")
sys.exit(1 if fails else 0)
