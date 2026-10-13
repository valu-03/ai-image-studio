"""snapshot_bank.json + build_snapshot.py + build_prompt.apply_snapshot - the viral phone look.

Built against a reference frame the user supplied: a street cat by an empty
steel bowl, shot low on a phone, passers-by blurred behind. What has to hold:

  * every phrase is safe (nothing banned or warned, nothing an animal prompt
    bans, no refusal wording, no trailing full stop);
  * the phone snapshot replaces the camera and lens with the bank's own phone
    preset, never lands on a cinema camera or cinema core/grain word across
    many seeds, and gets out of the way of a chosen shot, a typed shot, an
    explicit camera or a film stock;
  * the background follows the Setting, a plain backdrop gets nothing;
  * the moment follows the Action for the kind, with a default otherwise;
  * without the flags the prompt is byte-for-byte unchanged;
  * the flags never lower a realism score or add a banned term;
  * the three bugs the reference frame exposed stay fixed: a "street cat" is
    a cat, a "metal bowl" is not ceramic, and nothing outdoors has a "room";
    and a non-human subject never gets skin or pore words.

Standard library only, no network, no Qt.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import brief  # noqa: E402
import build_evidence as bev  # noqa: E402
import build_material as bmt  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_snapshot as bsn  # noqa: E402
import realism_lint as rl  # noqa: E402

BANK = bsn.load_bank()
IMAGE_BANK = bp.load_bank()
CINEMA = ("ARRI", "Alexa", "Venice", "RED V-Raptor", "Hasselblad", "studio portrait photography",
          "cinematic realism", "cinematic grain", "cinematic film still")
STREET_CAT = {"subject": "a chubby ginger street cat",
              "action": "sitting next to an empty metal bowl, staring at it",
              "setting": "a busy shopping street pavement, overcast day", "aspect": "9:16"}
ALL_FLAGS = {"snapshot": True, "background_life": True, "moment": True}

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", text.lower()) is not None


def every_phrase():
    snap = BANK["snapshot"]
    for lines in snap["who"].values():
        yield from lines
    yield snap["processing"]
    for cfg in BANK["backgrounds"].values():
        for part in ("passers", "clutter", "ground"):
            yield from cfg[part]
    for cfg in BANK["moments"]["actions"].values():
        yield from (v for k, v in cfg.items() if k != "keywords")
    for lines in BANK["moments"]["by_kind"].values():
        yield from lines


print("=== PHRASES ARE SAFE ===")
phrases = list(every_phrase())
bad = [p for p in phrases if any(has_term(p, t) for t in IMAGE_BANK["banned"] + IMAGE_BANK["warn"])]
check("no banned or warn term", not bad, str(bad[:2]))
animal = [p for p in phrases if any(has_term(p, t) for t in rl.ANIMAL_BANNED)]
check("nothing an animal prompt bans", not animal, str(animal[:2]))
negated = [p for p in phrases if re.search(r"\b(no|not|never|without|avoid)\b", p.lower())]
check("no phrase is written as a refusal", not negated, str(negated[:2]))
check("no phrase ends in a full stop", not [p for p in phrases if p.rstrip().endswith(".")])
check("the bank says plainly it is not course material", "NOT AI Video Bootcamp" in BANK["source"])
check("the phone preset it borrows exists in prompt_bank.json",
      BANK["snapshot"]["preset"] in IMAGE_BANK["shot_presets"]
      and all(p in IMAGE_BANK["shot_presets"] for p in BANK["snapshot"]["phone_presets"]))
check("every skipped word is a real bank term", all(
    t in IMAGE_BANK["layers"][layer]["terms"]
    for layer, terms in BANK["snapshot"]["layer_skip"].items() for t in terms))

print()
print("=== THE BUGS THE REFERENCE FRAME EXPOSED ===")
check("'a chubby ginger street cat' is an animal, not a place",
      bev.subject_kind(bev.load_bank(), STREET_CAT["subject"]) == "animal")
mat = bmt.load_bank()
check("'a metal bowl' is metal only - no ceramic",
      bmt.read_materials(mat, {"subject": "an empty metal bowl"})[1] == ["metal"])
check("a bowl with no material named still reads as ceramic",
      bmt.read_materials(mat, {"subject": "an empty bowl"})[1] == ["vessel"])
check("no material phrase mentions a room", not [
    c["phrase"] for c in mat["materials"].values() if has_term(c["phrase"], "room")])
skinny = []
for seed in range(60):
    for subject in ("a ginger tabby cat", "a perfume bottle on marble", "a quiet street at night"):
        layers = bp.compose(IMAGE_BANK, dict(subject=subject, seed=seed, snapshot=True))[1]
        texture = layers["core"] + layers["texture"]
        if any(bp.SKIN_WORDS.search(t) for t in texture):
            skinny.append((subject, seed, texture))
check("180 non-human specs: the core and texture picks never say skin or pores", not skinny, str(skinny[:1]))
humans = {t for seed in range(60)
          for t in bp.compose(IMAGE_BANK, {"subject": "a woman", "seed": seed})[1]["texture"]}
check("...while a person still gets them", any(bp.SKIN_WORDS.search(t) for t in humans))

print()
print("=== PHONE SNAPSHOT ===")
check("no shot chosen: phone", bsn.snapshot_mode(BANK, {"subject": "a cat"}) == "phone")
check("a phone preset chosen: keep it, add the line",
      bsn.snapshot_mode(BANK, {"shot": "phone-candid"}) == "keep")
for label, spec, custom in (
        ("a chosen shot", {"shot": "portrait"}, False),
        ("a typed shot", {}, True),
        ("an explicit camera", {"overrides": {"camera": ["shot on a Leica"]}}, False),
        ("a film stock", {"overrides": {"grain": [
            "shot on Kodak Portra 400, fine natural film grain, warm restrained skin tones"]}}, False)):
    check("{} wins: skip".format(label), bsn.snapshot_mode(BANK, spec, custom_shot=custom) == "skip")
cinema_hits = []
for seed in range(200):
    prompt = bp.compose(IMAGE_BANK, dict(STREET_CAT, seed=seed, snapshot=True))[0]
    cinema_hits += [(seed, w) for w in CINEMA if w in prompt]
check("200 seeds: never a cinema camera, core or grain word", not cinema_hits, str(cinema_hits[:3]))
prompt = bp.compose(IMAGE_BANK, dict(STREET_CAT, seed=1, snapshot=True))[0]
check("the phone camera and lens come from the bank's preset",
      "iPhone-style photo" in prompt and "natural phone camera sharpness" in prompt)
check("a cat gets a passer-by / low-phone line", "phone" in prompt and "low" in prompt, prompt[-400:])
check("...and not the preset's 'shot by a friend' line", "shot by a friend" not in prompt)
chosen = bp.compose(IMAGE_BANK, dict(STREET_CAT, seed=1, snapshot=True, shot="portrait"))[0]
check("a chosen shot keeps its own camera and gets no phone line",
      "studio portrait photography" in chosen and "phone" not in chosen)
selfie = bp.compose(IMAGE_BANK, {"subject": "a woman", "seed": 1, "snapshot": True, "shot": "selfie"})[0]
check("the selfie preset keeps its camera and gets only the processing line",
      "smartphone selfie" in selfie and "smartphone sharpening" in selfie and "a friend took" not in selfie)

print()
print("=== UNSTAGED BACKGROUND ===")
for setting, place in (("a busy shopping street pavement", "street"), ("a corner cafe", "cafe"),
                       ("a kitchen at dawn", "kitchen"), ("a city park", "park"),
                       ("a train platform", "station"), ("a white studio backdrop", "plain"),
                       ("an abstract void", "plain"), ("somewhere", None)):
    got = bsn.read_place(BANK, setting)
    check("{!r} reads as {}".format(setting, place), got == place, str(got))
check("no Setting: the Subject is read ('a street cat')",
      bsn.read_place(BANK, "", "a ginger street cat") == "street")
phrase, _place = bsn.background_line(BANK, dict(STREET_CAT, seed=0))
check("one passer-by, one everyday thing, one worn surface", phrase.count(", ") >= 2, phrase)
check("a plain backdrop gets nothing", bsn.background_line(
    BANK, {"setting": "plain white background", "seed": 0}) == ("", "plain"))
check("reproducible by seed", bsn.background_line(BANK, dict(STREET_CAT, seed=3))
      == bsn.background_line(BANK, dict(STREET_CAT, seed=3)))
check("...and seeds differ", len({bsn.background_line(BANK, dict(STREET_CAT, seed=s))[0]
                                  for s in range(20)}) > 1)

print()
print("=== THE MOMENT ===")
phrase, key = bsn.moment_line(BANK, STREET_CAT, "animal")
check("a cat staring at its bowl: an intent stare", key == "stare" and "ears" in phrase, phrase)
phrase, key = bsn.moment_line(BANK, {"action": "laughing with friends"}, "human")
check("a laughing person: just after the laugh", key == "laugh" and "creased" in phrase, phrase)
phrase, key = bsn.moment_line(BANK, {"action": "talking to camera"}, "animal")
check("an action with no phrase for the kind falls back to a default",
      key is None and phrase in BANK["moments"]["by_kind"]["animal"], phrase)
check("a place gets the place default",
      bsn.moment_line(BANK, {"subject": "a quiet street"}, "place")[0]
      in BANK["moments"]["by_kind"]["place"])

print()
print("=== IN A REAL PROMPT ===")
base = dict(STREET_CAT, seed=2)
before = bp.compose(IMAGE_BANK, base)[0]
check("without the flags the prompt is byte-for-byte unchanged",
      before == bp.compose(IMAGE_BANK, dict(base, snapshot=False, background_life=False, moment=False))[0])
flagged = bp.compose(IMAGE_BANK, dict(base, **ALL_FLAGS))[0]
check("all three lines land before the negatives",
      flagged.index("intent stare") < flagged.index("no cartoon style")
      and flagged.index("smartphone sharpening") < flagged.index("no cartoon style"))
explicit = bp.compose(IMAGE_BANK, dict(base, moment=True, overrides={"moment": ["my own moment"]}))[0]
check("an explicit moment override wins", "my own moment" in explicit and "intent stare" not in explicit)

lowered = []
specs = (
    dict(STREET_CAT),
    {"subject": "a woman in her thirties", "action": "laughing", "setting": "a corner cafe"},
    {"subject": "a man", "action": "walking to work", "setting": "a train platform"},
    {"subject": "a golden retriever puppy", "action": "chasing a ball", "setting": "a city park"},
    {"subject": "a perfume bottle", "setting": "on a marble counter in a bathroom"},
    {"subject": "a quiet street at night"},
)
for seed in range(15):
    for spec in specs:
        spec = dict(spec, seed=seed)
        kind = "animal" if bev.subject_kind(bev.load_bank(), spec["subject"]) == "animal" else "human"
        b_present, _m, b_banned, _w, _n = rl.lint(bp.compose(IMAGE_BANK, spec)[0], IMAGE_BANK, kind=kind)
        present, _m, banned, _w, _n = rl.lint(
            bp.compose(IMAGE_BANK, dict(spec, **ALL_FLAGS))[0], IMAGE_BANK, kind=kind)
        added = set(banned) - set(b_banned)
        if len(present) < len(b_present) or added:
            lowered.append((spec["subject"], seed, len(b_present), len(present), added))
check("90 specs: the flags never lower a realism score or add a banned term",
      not lowered, str(lowered[:3]))
present, _m, banned, _w, _n = rl.lint(
    bp.compose(IMAGE_BANK, dict(STREET_CAT, seed=4, face_detail=True, scene_lighting=True,
                                contact_detail=True, material_detail=True, **ALL_FLAGS))[0],
    IMAGE_BANK, kind="animal")
check("the full street-cat prompt is 8/8 on the animal gate", len(present) == 8 and not banned,
      "{} {}".format(len(present), banned))
check("none of the flags is something a model can set",
      not ({"snapshot", "background_life", "moment"} & set(brief.SPEC_KEYS)))

print()
print("=== CLI ===")
run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_snapshot.py"),
                      "--subject", STREET_CAT["subject"], "--action", STREET_CAT["action"],
                      "--setting", STREET_CAT["setting"]], capture_output=True, text=True)
check("build_snapshot.py prints all three", run.returncode == 0
      and all(x in run.stdout for x in ("who:", "background:", "moment:")), run.stderr)
run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_snapshot.py"), "--list"],
                     capture_output=True, text=True)
check("--list works", run.returncode == 0 and "street" in run.stdout)

print()
if fails:
    print("{} failed".format(len(fails)))
    for name in fails:
        print("  - " + name)
    raise SystemExit(1)
print("ALL SNAPSHOT CHECKS PASSED")
