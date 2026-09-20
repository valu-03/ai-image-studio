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
check("five templates", len(pa.templates(bank)) == 5, str(sorted(pa.templates(bank))))
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
