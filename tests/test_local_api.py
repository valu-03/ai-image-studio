"""tools/local_api.py - the server Skit Studio talks to while this app is open.

Runs in-process against mock_api (Kie), with a throwaway .env and History file
so nothing real is read, spent or logged. The API itself binds port 0, so it
can never collide with a running copy of the app on 8785.
"""
import base64
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

import mock_api  # noqa: E402

MOCK_PORT = 8815
mock_api.serve(MOCK_PORT)
TMP = Path(tempfile.mkdtemp(prefix="aivs-local-api-"))
ENV = TMP / ".env"
ENV.write_text("KIE_API_KEY=fake-kie\nAIVS_API_BASE=http://127.0.0.1:{}\n".format(MOCK_PORT),
               encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(ENV)
os.environ["AIVS_HISTORY_FILE"] = str(TMP / "history.jsonl")
os.environ["AIVS_POLL_INTERVAL"] = "0.05"

import history  # noqa: E402
import local_api as la  # noqa: E402

fails = []
written = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def call(base, method, path, body=None, token=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def wait(base, job_id, seconds=15):
    deadline = time.time() + seconds
    while time.time() < deadline:
        _code, job = call(base, "GET", "/api/v1/images/" + job_id)
        if job.get("state") in ("done", "failed"):
            return job
        time.sleep(0.05)
    return job


CURRENT = {"lighting": "soft window light from the left", "style": "pixar style 3D render",
           "capture": ["shot on Kodak Portra 400"], "camera": "", "color": ""}

print("Look tools")
options = la.look_options()
check("all eight Look parts listed", set(options) == set(la.LOOK_KEYS), str(sorted(options)))
check("lighting setups come from the bank", len(options["lighting"]["setups"]) > 5)
check("styles carry their group",
      all(s["group"] in ("photoreal", "stylised") for s in options["style"]["styles"]))
setup = options["lighting"]["setups"][0]
phrases, warnings = la.compose_look({"lighting": {"setup": setup["key"]},
                                     "color": "teal and orange"})
check("a setup composes to its bank phrase", phrases.get("lighting") == setup["phrase"])
check("a plain string is used as the phrase", phrases.get("color") == "teal and orange")
try:
    la.compose_look({"lighting": {"setup": "no-such-setup"}})
    check("an unknown key is refused", False)
except la.LookError as exc:
    check("an unknown key is refused, naming the part", str(exc).startswith("lighting"))
prompt = la.assemble_prompt("A cat on a sofa, wide shot. No text, no captions, no watermark.",
                            {"style": "pixar style", "lighting": "soft light"})
check("style leads the prompt", prompt.startswith("pixar style."), prompt)
check("the no-text sentence stays last", prompt.endswith("No text, no captions, no watermark."))
check("look phrases sit after the scene", prompt.index("soft light") > prompt.index("sofa"))

print("Server")
api = la.start(port=0, current_look=lambda: CURRENT, token="")
BASE = "http://127.0.0.1:{}".format(api.port)
done_events = []
api.jobs.on_image = done_events.append

code, health = call(BASE, "GET", "/api/v1/health")
check("health answers", code == 200 and health.get("app") == "AI Image Studio", str(health))
check("health says the Kie key is set", health.get("providers", {}).get("kie") is True)
check("health says a look is applied", health.get("look_current") is True)
code, current = call(BASE, "GET", "/api/v1/look/current")
check("current look returns every part", set(current) == set(la.LOOK_KEYS))
check("capture list flattened", current["capture"] == "shot on Kodak Portra 400")
code, opts = call(BASE, "GET", "/api/v1/look/options")
check("options route", code == 200 and "lighting" in opts)
code, composed = call(BASE, "POST", "/api/v1/look/compose", {"style": {"style": "no-such"}})
check("compose rejects a bad style with 400", code == 400, str(composed))

code, manual = call(BASE, "POST", "/api/v1/prompt",
                    {"prompt": "A pug on a skateboard.", "look": "current"})
check("prompt route returns the finished prompt with the current look",
      code == 200 and manual["prompt"].startswith("pixar style 3D render.")
      and "soft window light" in manual["prompt"], str(manual))
check("prompt route spends nothing", mock_api.STATE["last"] is None)

ref = base64.b64encode(mock_api.PNG).decode()
code, sub = call(BASE, "POST", "/api/v1/images",
                 {"prompt": "A ginger cat on a sofa. No text, no captions, no watermark.",
                  "look": "current", "aspect": "9:16", "tag": "skit-test",
                  "references": [{"name": "cat.png", "b64": ref}]})
check("image job accepted", code == 202 and sub.get("id"), str(sub))
job = wait(BASE, sub["id"])
check("image job finishes", job.get("state") == "done", str(job))
if job.get("file"):
    written.append(Path(job["file"]))
body = (mock_api.STATE["last"] or {}).get("body", {})
sent = body.get("input", {})
check("Kie got the look-assembled prompt", sent.get("prompt", "").startswith("pixar style"),
      sent.get("prompt", "")[:80])
check("Kie got the aspect", sent.get("aspect_ratio") == "9:16")
check("Kie got the uploaded reference", len(sent.get("image_input", [])) == 1)
code, data = call(BASE, "GET", "/api/v1/images/{}/file".format(sub["id"]), raw=True)
check("file route returns the image", code == 200 and data == mock_api.PNG)
entries = history.load()
check("History has one Skit Studio row",
      len(entries) == 1 and entries[0]["note"] == la.HISTORY_NOTE, str(len(entries)))
check("History row keeps the image", entries and entries[0]["image"] == job.get("file"))
check("on_image was called", len(done_events) == 1 and done_events[0]["state"] == "done")
check("the reference temp file was removed", not list(la.REF_DIR.glob(sub["id"] + "-*")))

code, bad = call(BASE, "POST", "/api/v1/images", {"prompt": ""})
check("an empty prompt is refused", code == 400)
code, bad = call(BASE, "POST", "/api/v1/images", {"prompt": "x", "look": 7})
check("a bad look is refused", code == 400)
code, bad = call(BASE, "POST", "/api/v1/images", {"prompt": "x", "references": [{"name": "a"}]})
check("a reference without data is refused", code == 400)
code, bad = call(BASE, "GET", "/api/v1/images/abc123")
check("an unknown job is 404", code == 404)

print("Realism (the Images tab's switches on a typed prompt)")
SCENE = ("Photorealistic smartphone footage, natural light, real fur texture, shallow depth of "
         "field, candid home-video feel. Bartholomew, the Golden Retriever, sits on a plush rug "
         "pawing at a tablet on the coffee table. Medium shot. No text, no captions, no watermark.")
REAL = {"subject": "Bartholomew, a Golden Retriever, golden fur", "species": "dog",
        "kind": "animal", "action": "sits on a plush rug pawing at a tablet on the coffee table",
        "setting": "a cozy living room with a couch and a coffee table", "shot": "medium shot"}
code, real = call(BASE, "POST", "/api/v1/prompt", {"prompt": SCENE, "realism": REAL})
report = real.get("realism") or {}
check("realism lifts a typed prompt to 8/8", code == 200 and report.get("score") == 8
      and report.get("before", 8) < 8, str(report))
check("a breed with a species reads as an animal", report.get("kind") == "animal")
check("fur words, never skin words, on a dog",
      "skin" not in real["prompt"].lower() and "pores" not in real["prompt"].lower())
check("the switches added their lines", len(report.get("lines", [])) >= 4, str(report.get("lines")))
check("a coffee table brings no steaming coffee", "steam" not in real["prompt"].lower())
check("the phone look keeps a phone camera", "iphone" in real["prompt"].lower()
      and "dslr" not in real["prompt"].lower())
check("the no-text sentence still ends the prompt",
      real["prompt"].endswith("No text, no captions, no watermark."))
check("realism spends nothing", mock_api.STATE["last"] is None or
      mock_api.STATE["last"]["body"].get("input", {}).get("prompt") != real["prompt"])
sheet = dict(REAL, action="", setting="", phone=True, **{k: False for k in la.REALISM_SWITCHES
                                                          if k != "face_detail"})
code, plain = call(BASE, "POST", "/api/v1/prompt", {"prompt": "Character reference portrait of "
                   "Bartholomew, a Golden Retriever. Plain light-grey background.", "realism": sheet})
check("switched-off switches add nothing", (plain.get("realism") or {}).get("lines", [None])[0:1]
      and "passing" not in plain["prompt"] and "background" not in
      " ".join(plain["realism"]["lines"]), str(plain.get("realism")))
check("`phone` keeps a sheet off the DSLR words", "dslr" not in plain["prompt"].lower()
      and "chiaroscuro" not in plain["prompt"].lower()
      and plain["realism"]["score"] == 8, plain["prompt"][-200:])
code, styled = call(BASE, "POST", "/api/v1/prompt", {"prompt": SCENE, "realism": REAL,
                    "look": {"style": {"style": "anime-manga"}}})
check("a stylised Look gets no photo-realism words", styled.get("realism") is None
      and any("stylised" in w for w in styled.get("warnings", [])), str(styled.get("warnings")))
code, bad = call(BASE, "POST", "/api/v1/prompt", {"prompt": "x", "realism": {"kind": "robot"}})
check("an unknown subject kind is refused", code == 400)
code, bad = call(BASE, "POST", "/api/v1/images", {"prompt": "x", "refine": 5})
check("more than two Refine retries is refused", code == 400)

import scene_variety as sv  # noqa: E402

code, cat = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat eats from a bowl.",
                                                 "realism": {"subject": "a cat"}})
check("realism_prompt_does_not_lead_with_photorealistic",
      code == 200 and not cat["prompt"].lower().startswith("photorealistic")
      and "photorealistic" not in cat["prompt"].lower(), cat.get("prompt", "")[:200])
check("a prompt with no light gets one light phrase",
      sv.pick("A cat eats from a bowl.", "animal")["light"].lower() in cat["prompt"].lower())
code, one = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat eats from a bowl.", "tag": "skit-1",
                                                 "realism": {"subject": "a cat"}})
code, two = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat leaps onto a chair.", "tag": "skit-1",
                                                 "realism": {"subject": "a cat"}})
light1 = sv.pick("skit-1", "animal")["light"].lower()
check("same_tag_same_light", light1 in one["prompt"].lower() and light1 in two["prompt"].lower(),
      one["prompt"][-250:])
code, lit = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat by the window lamp.", "tag": "skit-1",
                                                 "realism": {"subject": "a cat"}})
check("a prompt that names its light gets no extra one", light1 not in lit["prompt"].lower())

code, out1 = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat walks down the street.", "tag": "skit-1",
                                                  "realism": {"subject": "a cat"}})
code, out2 = call(BASE, "POST", "/api/v1/prompt", {"prompt": "A cat sits on the beach.", "tag": "skit-1",
                                                  "realism": {"subject": "a cat"}})
outl = sv.pick("skit-1", "animal", True)["light"].lower()
check("outdoor prompt gets an outdoor light", outl in out1["prompt"].lower(), out1["prompt"][-250:])
check("same tag, outdoor scenes share the outdoor light", outl in out2["prompt"].lower())
check("an outdoor prompt gets no indoor light", light1 not in out1["prompt"].lower())
check("an indoor prompt still gets the indoor light", light1 in one["prompt"].lower()
      and outl not in one["prompt"].lower())

print("Refine")
code, sub = call(BASE, "POST", "/api/v1/images", {"prompt": SCENE, "refine": 2})
check("refine without an OpenRouter key falls back to one image",
      code == 202 and sub.get("refine") == 0 and any("OPENROUTER" in w for w in sub["warnings"]),
      str(sub))
wait(BASE, sub["id"])
verdicts = iter([
    {"ok": True, "verdict": "fur looks plastic", "failing_layers": ["texture", "grain"], "fixes": []},
    {"ok": True, "verdict": "worse", "failing_layers": ["texture", "grain", "colour"], "fixes": []},
    {"ok": True, "verdict": "close", "failing_layers": ["grain"], "fixes": []},
])
seen_prompts = []
la.refine_available = lambda: True
la.brief.critique_image = lambda bank, prompt, path, ask=None: (seen_prompts.append(prompt)
                                                               or next(verdicts))
code, sub = call(BASE, "POST", "/api/v1/images", {"prompt": SCENE, "realism": REAL, "refine": 2})
check("refine accepted", code == 202 and sub.get("refine") == 2, str(sub))
job = wait(BASE, sub["id"])
for attempt in job.get("attempts") or []:
    written.append(Path(attempt["file"]))
check("three attempts at most", len(job.get("attempts") or []) == 3, str(job.get("attempts")))
check("the attempt the critique liked best is kept", job.get("chosen") == 3
      and job.get("file") == job["attempts"][2]["file"], str(job.get("chosen")))
check("each retry strengthens the layer it was told was weak",
      len(seen_prompts) == 3 and seen_prompts[1] != seen_prompts[0]
      and len(seen_prompts[2]) > len(seen_prompts[1]))
check("a phone-look retry never adds cinema words", "cinematic" not in seen_prompts[-1].lower())
check("retries stay before the no-text sentence",
      seen_prompts[-1].endswith("No text, no captions, no watermark."))
verdicts = iter([{"ok": True, "verdict": "real", "failing_layers": [], "fixes": []}])
code, sub = call(BASE, "POST", "/api/v1/images", {"prompt": SCENE, "refine": 2})
job = wait(BASE, sub["id"])
written.extend(Path(a["file"]) for a in job.get("attempts") or [])
check("a real-looking first image stops the loop - no retry spent",
      len(job.get("attempts") or []) == 1 and job.get("state") == "done", str(job.get("attempts")))
code, ok = call(BASE, "POST", "/api/v1/images/{}/cancel".format(sub["id"]))
check("cancel answers", code == 200)
code, health = call(BASE, "GET", "/api/v1/health")
check("health lists the switches and Refine", health.get("realism") == list(la.REALISM_SWITCHES)
      and health.get("max_refine") == 2)
api.stop()

print("Token")
api = la.start(port=0, current_look=lambda: {}, token="s3cret")
BASE = "http://127.0.0.1:{}".format(api.port)
code, _ = call(BASE, "GET", "/api/v1/health")
check("no token is 401", code == 401)
code, _ = call(BASE, "GET", "/api/v1/health", token="s3cret")
check("the right token passes", code == 200)
api.stop()

for path in written:
    try:
        path.unlink()
    except OSError:
        pass

print()
print("{} failed".format(len(fails)) if fails else "ALL PASSED")
sys.exit(1 if fails else 0)
