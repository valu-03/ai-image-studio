"""ElevenLabs sound-effect prompts: the bank, the linter and the three layers.

The load-bearing assertion is the first one. The course's 100 example prompts
ARE the fixture - a linter that rejects one of them is wrong about it, not the
other way round. The first version of sound_lint.py guessed at the pattern and
rejected 31 of them, which is exactly the failure this test exists to catch.

Standard library only; no PyQt, no network.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_sound as bsd  # noqa: E402
import sound_lint as sl  # noqa: E402

bank = sl.load_bank()
fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


print("=== THE FIXTURE: the course's own 100 prompts ===")
rows = sl.examples(bank)
check("all 100 are present", len(rows) == 100, str(len(rows)))
check("numbered 1..100", [e["n"] for e in rows] == list(range(1, 101)))
check("every one is tagged", all(e.get("theme") for e in rows))
check("nine themes", len(sl.themes(bank)) == 9, str(len(sl.themes(bank))))

rejected = [e for e in rows if not sl.passes(bank, e["text"])]
check("the linter accepts every one of them", not rejected,
      "; ".join("{}. {}".format(e["n"], e["text"]) for e in rejected[:3]))

# The pattern claims in the bank's own note, verified rather than asserted.
counts = [len(e["text"].split()) for e in rows]
check("they run 4 to 9 words", min(counts) >= 4 and max(counts) <= 9,
      "{}..{}".format(min(counts), max(counts)))
# 81, not 82: the remaining -ing word is "being", in example 9 "Greek lyre being
# plucked" - a copula rather than an action, excluded by the linter's regex on
# purpose. The bank's note says 81 for the same reason.
ing = sum(1 for e in rows if re.search(r"\b[a-z]{3,}ing\b", e["text"], re.I))
check("81 carry an -ing action verb", ing == 81, str(ing))
check("the bank's note agrees", "81 carry" in bank["pattern"]["why"])

print()
print("=== THE GATE: what it must reject ===")
for text, why in [
    ("", "nothing at all"),
    ("a sword", "an object, not an event"),
    ("cat", "one bare noun"),
]:
    check("rejects {!r} - {}".format(text, why), not sl.passes(bank, text))

for text in ["sad piano melody playing softly in a room",
             "an upbeat song with drums building",
             "a narrator reading the opening line"]:
    results = sl.lint(bank, text)
    effect_row = next(r for r in results if r[0] == "effect")
    check("rejects music/speech: {!r}".format(text[:34]), not effect_row[2], effect_row[3][:60])

# The music gate is exactly bank["not_effects"] - no more, no less. This pin
# exists because prose elsewhere in the project twice claimed the list contains
# "beat", and it does not: "chic upbeat lounge hip-hop beat" sails through
# check_is_an_effect and fails check_event instead, for naming an object rather
# than a sound. A doc that names the gate's contents from memory is a doc that
# drifts; this makes the next wrong claim fail a test.
for word in ("beat", "hip-hop", "bass", "rhythm", "tempo", "drums"):
    check("'{}' is NOT a not_effects word".format(word),
          word not in bank["not_effects"], str(bank["not_effects"]))
for word in ("music", "soundtrack", "lyrics", "narration", "instrumental"):
    check("'{}' IS a not_effects word".format(word), word in bank["not_effects"])

hiphop = "chic upbeat lounge hip-hop beat, subtle bass"
bed = {r[0]: r for r in sl.lint(bank, hiphop)}
check("a music bed fails, but on the EVENT check", not bed["event"][2], bed["event"][3][:40])
check("and passes the music gate untouched", bed["effect"][2], bed["effect"][3][:40])

long_text = "a very long description of an entire scene in which many things happen at once"
results = sl.lint(bank, long_text)
length_row = next(r for r in results if r[0] == "length")
check("rejects a scene description", not length_row[2], length_row[3][:50])

print()
print("=== 'dialogue' as context is not a request for speech ===")
# Example 72 is the course's own: "Heartbeat slowing down before emotional
# dialogue". A gate that fails it is wrong about the example.
seventy_two = next(e for e in rows if e["n"] == 72)
check("example 72 mentions dialogue", "dialogue" in seventy_two["text"])
check("and still passes", sl.passes(bank, seventy_two["text"]), seventy_two["text"])

print()
print("=== ADVICE is separate from failure ===")
plain = "Sandbags rustling and barbed wire creaking"
check("a prompt with no stated space still passes", sl.passes(bank, plain))
check("but it is advised about it", any("space" in n for n in sl.advice(bank, plain)),
      str(sl.advice(bank, plain)))
rich = "Torch flame crackling in a temple hallway"
check("a fully-formed prompt gets no advice", not sl.advice(bank, rich), str(sl.advice(bank, rich)))

print()
print("=== COMPOSING ===")
text = bsd.compose(bank, "torch flame", "crackling", "a temple hallway")
check("assembles in the pattern", text == "torch flame crackling in a temple hallway", text)
check("and it passes", sl.passes(bank, text))

text2 = bsd.compose(bank, "cat paws", "landing", "on a wooden table")
check("does not double the preposition", text2.count(" in ") == 0, text2)

text3, passed, _ = bsd.compose_checked(bank, "tiny mouse", "squeaking",
                                       treatment="comedic echo")
check("treatment reads as 'with ...'", "with comedic echo" in text3, text3)
check("composed prompts are pre-scored", passed)

long_source = bsd.compose(bank, "a b c d e f g h i j k", "running", "somewhere far away")
check("never emits more than 12 words", len(long_source.split()) <= 12, long_source)

print()
print("=== THE THREE LAYERS ===")
layers = bsd.scene_sound(bank, "a suburban kitchen at night", "the cat",
                         "hauling the fridge door open", theme="comedy")
check("three of them", len(layers) == 3, str(len(layers)))
check("named ambience, key, accent",
      [l["layer"] for l in layers] == ["ambience", "key", "accent"])
check("every layer passes its own gate", all(l["passed"] for l in layers),
      str([(l["layer"], l["failures"]) for l in layers if not l["passed"]]))
check("the accent comes from the course's examples",
      layers[2]["text"] in [e["text"] for e in rows], layers[2]["text"])
check("the ambience names the setting", "kitchen" in layers[0]["text"], layers[0]["text"])
check("the key names what happens", "fridge" in layers[1]["text"], layers[1]["text"])

print()
print("=== ACROSS A STORY ===")
ACTIONS = [
    "staring at the fridge handle",
    "padding across the tiles",
    "hauling the door open with both paws",
    "freezing mid-reach with his ears back",
    "dragging a slice of ham along the floor",
    "sitting beside a dog sharing the ham",
]
scenes = [
    {"n": i + 1, "label": "Scene {}".format(i + 1),
     "spec": {"setting": "a kitchen at night", "action": action}}
    for i, action in enumerate(ACTIONS)
]
sheets = bsd.story_sound(bank, scenes, subject="the cat", theme="comedy")
check("a sheet per scene", len(sheets) == 6, str(len(sheets)))

accents = [s["layers"][2]["text"] for s in sheets]
# Random sampling collided here: scenes 4 and 5 of a five-scene story drew the
# same accent. The same joke twice in a row is worse than a duller one.
check("no accent repeats back to back",
      all(a != b for a, b in zip(accents, accents[1:])), str(accents))
keys = [s["layers"][1]["text"] for s in sheets]
check("each scene's key effect is its own", len(set(keys)) == len(keys))
check("every prompt in the sheet passes",
      all(l["passed"] for s in sheets for l in s["layers"]))

text = bsd.sheet_text(sheets)
check("the sheet mentions every scene", all("Scene {}".format(i + 1) in text
                                            for i in range(6)))

# A weak action must be REPORTED, not silently emitted as a good prompt. Found
# by a test fixture that used "doing thing 0" as an action.
weak = bsd.story_sound(bank, [{"n": 1, "label": "S", "spec": {
    "setting": "a kitchen", "action": "doing thing"}}])
key_layer = weak[0]["layers"][1]
check("a weak action is reported, not silently passed",
      not key_layer["passed"] and key_layer["failures"], key_layer["text"])

print()
print("=== KEY OVERRIDE (Cats' Audio Cues field) ===")
default_layers = bsd.scene_sound(bank, "a kitchen at night", "the cat",
                                 "hauling the fridge door open", seed=0)
overridden = bsd.scene_sound(bank, "a kitchen at night", "the cat",
                             "hauling the fridge door open", seed=0,
                             key_override="claws scraping on the fridge door, ice cubes rattling")
check("the key layer becomes the override",
      overridden[1]["text"] == "claws scraping on the fridge door, ice cubes rattling",
      overridden[1]["text"])
check("ambience is untouched", overridden[0]["text"] == default_layers[0]["text"])
check("accent is untouched", overridden[2]["text"] == default_layers[2]["text"])
check("an override is still scored, not exempt from the gate",
      "score" in overridden[1] and "passed" in overridden[1])

blank_override = bsd.scene_sound(bank, "a kitchen at night", "the cat",
                                 "hauling the fridge door open", seed=0, key_override="")
check("a blank override falls back to key_for(), same as no override at all",
      blank_override[1]["text"] == default_layers[1]["text"], blank_override[1]["text"])

sheets_no_override = bsd.story_sound(bank, scenes, subject="the cat", theme="comedy")
sheets_with_override = bsd.story_sound(bank, scenes, subject="the cat", theme="comedy",
                                       key_overrides={2: "a loud crash of pans hitting the floor"})
check("story_sound with no key_overrides reproduces today's output exactly",
      [s["layers"][1]["text"] for s in sheets_no_override]
      == [s["layers"][1]["text"] for s in sheets],
      str([s["layers"][1]["text"] for s in sheets_no_override]))
check("only the overridden scene's key layer changes",
      sheets_with_override[2]["layers"][1]["text"] == "a loud crash of pans hitting the floor")
check("every other scene keeps its own auto-composed key effect",
      all(sheets_with_override[i]["layers"][1]["text"]
          == sheets_no_override[i]["layers"][1]["text"]
          for i in range(len(scenes)) if i != 2))

print()
print("=== THEMES ===")
comedy = sl.by_theme(bank, "comedy")
check("comedy has ten", len(comedy) == 10, str(len(comedy)))
check("it is the animal-video set",
      any("mouse squeak" in e["text"] for e in comedy))
check("an unknown theme is empty, not a crash", sl.by_theme(bank, "nope") == [])

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL SOUND CHECKS PASSED")
