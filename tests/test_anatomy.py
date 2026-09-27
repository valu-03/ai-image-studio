"""tools/anatomy_bank.json + prompt_anatomy.py - the prompt SKELETON, taught
and detected.

The rule this suite exists to hold: a slot that names one of the eight gated
realism layers must borrow tools/realism_lint.py's OWN DETECT keys, never a
second copy of them. A duplicated keyword list is a list that silently drifts.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "prompt_anatomy.py"
sys.path.insert(0, str(ROOT / "tools"))

import prompt_anatomy as pa  # noqa: E402
import realism_lint as rl  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = pa.load_bank()

print("=== the bank is well-formed ===")
check("eleven templates", len(pa.templates(bank)) == 11, str(sorted(pa.templates(bank))))
for name, cfg in pa.templates(bank).items():
    check("'{}' has label and summary".format(name), bool(cfg.get("label")) and bool(cfg.get("summary")))
    check("'{}' has slots".format(name), bool(cfg.get("slots")))
    for slot in cfg["slots"]:
        check("'{}/{}' has does/why/example".format(name, slot["key"]),
              all(slot.get(f) for f in ("key", "label", "does", "why", "example")))
        # Every slot must be detectable SOMEHOW - a gated layer, another
        # linter's table borrowed by name, or its own keys.
        check("'{}/{}' has a detection path".format(name, slot["key"]),
              bool(slot.get("layer")) or bool(slot.get("borrow")) or bool(slot.get("detect")))
        check("'{}/{}' resolves to real keywords".format(name, slot["key"]),
              bool(pa.slot_keywords(slot)))
        if slot.get("layer"):
            check("'{}/{}' names a real realism layer".format(name, slot["key"]),
                  slot["layer"] in rl.DETECT, slot["layer"])
            # The no-duplication rule: a layer slot must NOT also carry its own copy.
            check("'{}/{}' does not duplicate layer keywords".format(name, slot["key"]),
                  not slot.get("detect") and not slot.get("borrow"))
        if slot.get("borrow"):
            check("'{}/{}' borrows a known table".format(name, slot["key"]),
                  slot["borrow"] in pa.BORROW, slot["borrow"])

check("every summary mentions slots", all("slot" in cfg["summary"].lower()
                                          for cfg in pa.templates(bank).values()))

print()
print("=== every template declares which kind of prompt it produces ===")
for name, cfg in pa.templates(bank).items():
    check("'{}' declares a kind".format(name), cfg.get("kind") in ("image", "video"),
          repr(cfg.get("kind")))
check("image_templates() and video_templates() partition every template, no overlap",
      set(pa.image_templates(bank)) | set(pa.video_templates(bank)) == set(pa.templates(bank))
      and not set(pa.image_templates(bank)) & set(pa.video_templates(bank)),
      "{} / {}".format(sorted(pa.image_templates(bank)), sorted(pa.video_templates(bank))))
check("the seven still-image templates are grouped as 'image'",
      set(pa.image_templates(bank)) == {"beauty-macro", "macro-insert", "photoreal-portrait",
                                        "product-campaign", "candid-editorial",
                                        "influencer-series", "inventory-selfie"},
      str(sorted(pa.image_templates(bank))))
check("the four video templates are grouped as 'video'",
      set(pa.video_templates(bank)) == {"video-sequence", "video-shot", "action-commercial",
                                        "selfie-monologue"},
      str(sorted(pa.video_templates(bank))))

print()
print("=== a layer slot borrows realism_lint's own keys, never a copy ===")
for name, cfg in pa.templates(bank).items():
    for slot in cfg["slots"]:
        if slot.get("layer"):
            check("'{}/{}' keywords ARE realism_lint's".format(name, slot["key"]),
                  pa.slot_keywords(slot) == list(rl.DETECT[slot["layer"]]["keys"]))

print()
print("=== a borrowing slot borrows motion_lint's own verbs, never a copy ===")
import motion_lint as ml  # noqa: E402

for name, cfg in pa.templates(bank).items():
    for slot in cfg["slots"]:
        if slot.get("borrow") != "motion-verbs":
            continue
        keys = pa.slot_keywords(slot)
        # Own keys first, borrowed verbs last - see slot_keywords()'s docstring:
        # a bare verb like "push" matches "sunglasses pushed on head", so it
        # must not be the phrase analyse() quotes back when a better one hit.
        check("'{}/{}' ends with MOTION_VERBS".format(name, slot["key"]),
              keys[-len(ml.MOTION_VERBS):] == list(ml.MOTION_VERBS))
        check("'{}/{}' searches its own keys first".format(name, slot["key"]),
              keys[:len(slot.get("detect", []))] == list(slot.get("detect", [])))
        # Its own extras must be things motion_lint does NOT already cover -
        # an extra that duplicates a verb is the drift this path prevents.
        check("'{}/{}' adds no duplicate of a verb".format(name, slot["key"]),
              not [k for k in slot.get("detect", []) if k in ml.MOTION_VERBS])

print()
print("=== the video templates carry the three separate locks ===")
video = pa.slots(bank, "video-sequence")
locks = [s["key"] for s in video if s["key"].endswith("-lock")]
check("character, outfit and environment are separate slots",
      locks == ["character-lock", "outfit-lock", "environment-lock"], str(locks))
# The music/sound split is not cosmetic: sound_bank.json is effects-only and
# sound_lint.py rejects music vocabulary, so a single "audio" slot would teach
# a prompt this app's own sound gate refuses.
music = next(s for s in video if s["key"] == "music")
check("the music slot says why it is separate from sound",
      "sound_bank" in music["why"] and "sound_lint" in music["why"])
seq = next(s for s in video if s["key"] == "shot-sequence")
check("the shot-sequence slot warns about clip vs edit seconds",
      "clip_seconds" in seq["why"] and "edit_seconds" in seq["why"])

print()
print("=== analyse: the worked examples fill their own slots ===")
for name, cfg in pa.templates(bank).items():
    text = " ".join(slot["example"] for slot in cfg["slots"])
    rows = pa.analyse(bank, name, text)
    filled, total = pa.coverage(rows)
    missed = [s["key"] for s, present, _h in rows if not present]
    check("'{}' own examples fill every slot".format(name), filled == total,
          "{}/{} missing {}".format(filled, total, missed))

print()
print("=== scaffold: a pasteable skeleton, in the right shape per template ===")
for name, cfg in pa.templates(bank).items():
    blank = pa.scaffold_lines(bank, name, filled=False)
    filled = pa.scaffold_lines(bank, name, filled=True)
    check("'{}' scaffolds blank and filled".format(name), bool(blank) and bool(filled))
    check("'{}' blank scaffold has a placeholder per slot".format(name),
          "\n".join(blank).count("<") >= len(cfg["slots"]))
    body = [line for line in filled if not line.startswith("#") and line.strip()]
    check("'{}' filled scaffold carries every example".format(name),
          all(s["example"].split(",")[0] in "\n".join(body) for s in cfg["slots"]))
    if cfg.get("scaffold") == "inline":
        # The whole point of the inline layout: no slot heading may reach the
        # prompt text, or motion_lint's lead-with-camera rule fails on it.
        check("'{}' inline scaffold is one line".format(name), len(body) == 1, str(len(body)))
        check("'{}' inline scaffold emits no slot headings".format(name),
              not [s for s in cfg["slots"] if s["label"].upper() + ":" in body[0]])
    else:
        check("'{}' banded scaffold is one line per slot".format(name),
              len(body) == len(cfg["slots"]), str(len(body)))
        check("'{}' banded scaffold never doubles a heading".format(name),
              not [line for line in body if line.count(":") and
                   line.split(":")[0].strip() == line.split(":")[1].strip()])

# A filled inline scaffold is a real prompt, so the one that mirrors
# build_prompt.py's own output must still clear the 8/8 gate.
text = [line for line in pa.scaffold_lines(bank, "photoreal-portrait", filled=True)
        if not line.startswith("#") and line.strip()][0]
present, _m, banned, _w, _n = rl.lint(text.lower(), rl.json.load(
    (ROOT / "tools" / "prompt_bank.json").open(encoding="utf-8")))
check("the photoreal scaffold still scores 8/8", len(present) == 8,
      "{}/8".format(len(present)))
check("the photoreal scaffold trips no banned term", not banned, str(banned))

# The product-campaign template is BANDED, so its filled scaffold is twelve
# lines rather than one - but every one of them is meant to be pasted, so the
# whole brief has to clear the same gate a composed prompt does. An example a
# reader is told to use should not be one the app would refuse to generate.
pc_lines = [line for line in pa.scaffold_lines(bank, "product-campaign", filled=True)
            if not line.startswith("#") and line.strip()]
pc_text = " ".join(pc_lines)
pc_present, _m, pc_banned, pc_warn, _n = rl.lint(pc_text.lower(), rl.json.load(
    (ROOT / "tools" / "prompt_bank.json").open(encoding="utf-8")))
check("the product-campaign brief scores a full 8/8", len(pc_present) == 8,
      "{}/8 missing {}".format(len(pc_present), [x[0] for x in _m]))
check("...trips no banned term", not pc_banned, str(pc_banned))
# The source prompt asked for "8K quality"; prompt_bank lists "8k" in warn.
# Dropping it was a deliberate editorial call and this is what holds it.
check("...and no soft warn term either, 8K included", not pc_warn, str(pc_warn))
check("the brief is one line per band", len(pc_lines) == 12, str(len(pc_lines)))

# Its PRODUCT band is the only one of its kind in the bank, and the reason the
# template exists - a static ad lives or dies on whether the pack is legible.
# candid-editorial is INLINE, so its filled scaffold is one flowing prompt -
# the same shape photoreal-portrait's is, and the same obligation follows. Its
# source asked for "8K, ultra-high resolution"; that was dropped because
# prompt_bank lists "8k" in warn, and the no-warn assertion is what holds it.
ce_lines = [line for line in pa.scaffold_lines(bank, "candid-editorial", filled=True)
            if not line.startswith("#") and line.strip()]
check("the candid-editorial scaffold is one flowing line", len(ce_lines) == 1, str(len(ce_lines)))
ce_present, _m2, ce_banned, ce_warn, _n2 = rl.lint(ce_lines[0].lower(), rl.json.load(
    (ROOT / "tools" / "prompt_bank.json").open(encoding="utf-8")))
check("the candid-editorial prompt scores a full 8/8", len(ce_present) == 8,
      "{}/8 missing {}".format(len(ce_present), [x[0] for x in _m2]))
check("...trips no banned term", not ce_banned, str(ce_banned))
check("...and no warn term either, 8K included", not ce_warn, str(ce_warn))

# It is NOT a second beauty-macro. That one is a studio macro; this one is
# explicitly anti-studio, and the two slots that prove it are found light and a
# real background - neither of which a studio has.
ce_keys = [s["key"] for s in pa.slots(bank, "candid-editorial")]
bm_keys = [s["key"] for s in pa.slots(bank, "beauty-macro")]
check("candid-editorial keeps its own slot vocabulary", set(ce_keys) != set(bm_keys))
check("...and its negatives refuse the studio look specifically",
      any("studio" in k for s in pa.slots(bank, "candid-editorial")
          if s["key"] == "negatives" for k in s["detect"]))

check("product-campaign is the only template with a product band",
      [n for n, c in pa.templates(bank).items()
       if any(sl["key"] == "product" for sl in c["slots"])] == ["product-campaign"])

# The two newest image templates are INLINE, so the same obligation
# candid-editorial carries applies to both: a filled scaffold is a real prompt
# somebody is told to paste, so it has to clear the gate this app would apply
# to its own output - 8/8, nothing banned, and no soft warn term either.
for name, lines_wanted in [("influencer-series", 1), ("inventory-selfie", 1)]:
    lines = [line for line in pa.scaffold_lines(bank, name, filled=True)
             if not line.startswith("#") and line.strip()]
    check("the {} scaffold is one flowing line".format(name),
          len(lines) == lines_wanted, str(len(lines)))
    got, _m, bad, soft, _n = rl.lint(lines[0].lower(), rl.json.load(
        (ROOT / "tools" / "prompt_bank.json").open(encoding="utf-8")))
    check("the {} prompt scores a full 8/8".format(name), len(got) == 8,
          "{}/8 missing {}".format(len(got), [x[0] for x in _m]))
    check("...{} trips no banned term".format(name), not bad, str(bad))
    check("...{} trips no warn term either".format(name), not soft, str(soft))

# influencer-series exists for ONE band the other six image templates have no
# equivalent of: an instruction that the light, the room and the camera come
# back identical on the next shot. If that slot is ever dropped, the template
# is just a seventh portrait recipe.
lock = [s for s in pa.slots(bank, "influencer-series") if s["key"] == "series-lock"]
check("influencer-series carries a series lock", len(lock) == 1)
check("...and it is the only template that does",
      [n for n, c in pa.templates(bank).items()
       if any(sl["key"] == "series-lock" for sl in c["slots"])] == ["influencer-series"])
check("...it comes last, so it governs every slot above it",
      pa.slots(bank, "influencer-series")[-1]["key"] == "series-lock")
# It locks the frame and frees the performance. A lock that froze the pose too
# would return the same photograph N times, which is not a series either, and
# that distinction is the only thing making the slot useful rather than harmful.
check("...and it says what it does NOT lock",
      all(w in lock[0]["example"].lower() for w in ("identical", "free to change")),
      lock[0]["example"][:70])
# Both source prompts named a second, contradicting lighting setup. Resolving
# that to one setup was an editorial call; this is what records it.
light_why = next(s for s in pa.slots(bank, "influencer-series")
                 if s["key"] == "light")["why"].lower()
check("...and its light slot teaches the one-setup rule",
      "one setup" in light_why and "contradict" in light_why)

# inventory-selfie's method is named detail, not camera argument - so it must
# NOT read as a second copy of the editorial templates' slot list.
inv_keys = [s["key"] for s in pa.slots(bank, "inventory-selfie")]
check("inventory-selfie keeps its own slot vocabulary",
      {"props", "marks", "jewellery"} <= set(inv_keys), str(inv_keys))
check("...and no other template carries an evidence band",
      [n for n, c in pa.templates(bank).items()
       if any(sl["key"] == "marks" for sl in c["slots"])] == ["inventory-selfie"])

print()
print("=== the selfie video template: the two locks it lives on ===")
selfie = pa.slots(bank, "selfie-monologue")
selfie_keys = [s["key"] for s in selfie]
check("it is the largest template in the bank",
      len(selfie) == max(len(c["slots"]) for c in pa.templates(bank).values()),
      "{} slots".format(len(selfie)))
# The band no other template in this bank needs: the device filming cannot
# appear inside its own image. Without it a model renders a second phone in
# the visible hand and films the whole thing from across the room.
own = next(s for s in selfie if s["key"] == "camera-ownership")
check("it forbids the filming device appearing in its own image",
      "no physical smartphone visible" in own["example"].lower())
check("...and names which single hand may enter frame",
      "only hand allowed on screen" in own["example"].lower())
check("...and the only-one-hand rule is repeated where it actually breaks",
      "never two hands" in next(s for s in selfie
                                if s["key"] == "free-hand")["example"].lower())

# The two source prompts are ONE template because their own authors said the
# body roll replaces the phone slip. That merge is a judgement call, so the
# slot carrying both settings has to say so - otherwise the next reader adds
# a second template and the bank grows a near-duplicate.
event = next(s for s in selfie if s["key"] == "event")
check("the event slot carries both settings, slip and roll",
      "slip" in event["why"].lower() and "roll" in event["why"].lower())
check("...and records that one replaces the other",
      "replaces" in event["why"].lower())

# The one band in either source that arithmetic can check.
pacing = next(s for s in selfie if s["key"] == "pacing")
check("the pacing slot names a word count AND a rate",
      "79 words" in pacing["example"] and "words per minute" in pacing["example"])

# Phone-camera behaviour - autofocus hunting, exposure breathing - is
# vocabulary no linter in this repo owns, so this slot uses its own keys
# rather than claiming a realism layer. If someone later adds those keys to
# realism_lint, this is the slot to convert.
optics = next(s for s in selfie if s["key"] == "optics")
check("the optics slot owns its keywords rather than claiming a layer",
      optics.get("detect") and not optics.get("layer"))
check("...and says why no layer fits", "realism_lint" in optics["why"])

# The exact inverse of the ownership lock, one bank apart: the mirror-selfie
# template deliberately puts the phone IN the frame. Holding both is what
# stops either being read as a general rule about phones.
props = next(s for s in pa.slots(bank, "inventory-selfie") if s["key"] == "props")
check("the mirror selfie puts the phone in frame on purpose",
      "phone in the other hand" in props["example"].lower())
check("...and says it is the opposite of the video lock",
      "selfie-monologue" in props["why"])

print()
print("=== analyse: an empty-ish prompt fills almost nothing ===")
rows = pa.analyse(bank, "beauty-macro", "a nice picture of someone")
filled, total = pa.coverage(rows)
check("a bare prompt fills few slots", filled <= 2, "{}/{}".format(filled, total))

print()
print("=== the lens-detection regression this tool surfaced ===")
# "mm lens" is a plain substring, so a word between the millimetres and the
# lens used to hide the phrase - including this app's own portrait preset.
for phrase in ("shot on a 100mm macro portrait lens",
               "shot on an 85mm portrait lens",
               "50mm macro lens"):
    present, _m, _b, _w, _n = rl.lint(phrase.lower(), rl.json.load(
        (ROOT / "tools" / "prompt_bank.json").open(encoding="utf-8")))
    hit = next((h for n, _c, h in present if n == "lens"), None)
    check("lens layer sees '{}'".format(phrase), hit is not None, str(hit))

print()
print("=== CLI ===")


def run(args, stdin=None):
    return subprocess.run([sys.executable, str(TOOL)] + args, input=stdin,
                          capture_output=True, text=True, cwd=str(ROOT))


p = run(["--list"])
check("--list exits 0", p.returncode == 0, p.stderr[:160])
check("--list names every template", all(k in p.stdout for k in pa.templates(bank)))
check("--list groups image prompts under their own heading",
      "IMAGE PROMPTS" in p.stdout and "VIDEO PROMPTS" in p.stdout)
check("--list prints the image heading before the video heading",
      p.stdout.index("IMAGE PROMPTS") < p.stdout.index("VIDEO PROMPTS"))
check("--list keeps every video template after the VIDEO PROMPTS heading",
      all(p.stdout.index(k) > p.stdout.index("VIDEO PROMPTS") for k in pa.video_templates(bank)))

p = run(["--help"])
check("--help exits 0", p.returncode == 0, p.stdout[:120])

p = run(["--template", "beauty-macro"])
check("--template explains, exits 0", p.returncode == 0, p.stderr[:160])
check("explain prints every slot label",
      all(s["label"] in p.stdout for s in pa.slots(bank, "beauty-macro")))
check("explain prints the why lines", p.stdout.count("why") >= 10)

p = run(["--template", "video-shot", "--scaffold"])
check("--scaffold exits 0", p.returncode == 0, p.stderr[:160])
check("--scaffold prints the camera-first note", "camera move goes FIRST" in p.stdout)

p = run(["--template", "video-sequence", "--scaffold", "--filled"])
check("--scaffold --filled exits 0", p.returncode == 0, p.stderr[:160])
check("--scaffold --filled names the three locks",
      "CHARACTER LOCK:" in p.stdout and "OUTFIT LOCK:" in p.stdout
      and "ENVIRONMENT LOCK:" in p.stdout)
check("--scaffold --filled does not double a heading",
      "CHARACTER LOCK: CHARACTER LOCK" not in p.stdout)

p = run(["--template", "nope"])
check("an unknown --template exits non-zero", p.returncode != 0)

p = run([])
check("no --template exits non-zero", p.returncode != 0)

p = run(["--template", "macro-insert", "--analyse", "-"],
        stdin="render an extreme macro of the eye, preserve the exact eye colour and gaze")
check("--analyse - reads stdin, exits 0", p.returncode == 0, p.stderr[:160])
check("analyse reports slots filled", "slots filled" in p.stdout, p.stdout[:80])
check("analyse finds the preserve slot", "[ok]" in p.stdout and "Preserve" in p.stdout)

p = run(["--template", "beauty-macro", "--analyse", "does-not-exist.txt"])
check("--analyse on a missing file exits non-zero", p.returncode != 0)

p = run(["--template", "beauty-macro", "--analyse", "-"], stdin="   ")
check("an empty prompt exits non-zero", p.returncode != 0)

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL ANATOMY CHECKS PASSED")

sys.exit(1 if fails else 0)
