"""Real ElevenLabs generation - sound effects, text-to-speech, voice cloning.

Verifies the three new tools (generate_sound.py, generate_speech.py,
elevenlabs_voices.py) against a mock ElevenLabs server: the sound_lint gate
actually blocks an unscored effect and can be forced past it, TTS produces a
real file and reports a character count, cloning refuses without explicit
consent even with otherwise-valid input, and no key value ever reaches stdout.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
SOUND_TOOL = ROOT / "tools" / "generate_sound.py"
SPEECH_TOOL = ROOT / "tools" / "generate_speech.py"
VOICES_TOOL = ROOT / "tools" / "elevenlabs_voices.py"
SOUND_DIR = ROOT / "temp" / "outputs" / "sound"
VOICE_DIR = ROOT / "temp" / "outputs" / "voice"

import mock_elevenlabs  # noqa: E402

PORT = 8796
mock_elevenlabs.serve(PORT)
BASE = "http://127.0.0.1:{}".format(PORT)

EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-elevenlabs-empty.env"
EMPTY_ENV.write_text("# intentionally empty\n", encoding="utf-8")

SAMPLE_1 = Path(tempfile.gettempdir()) / "aivs-voice-sample-1.wav"
SAMPLE_1.write_bytes(b"RIFF....WAVEfmt fake sample bytes for a test")
SAMPLE_2 = Path(tempfile.gettempdir()) / "aivs-voice-sample-2.wav"
SAMPLE_2.write_bytes(b"RIFF....WAVEfmt another fake sample")

KEY = {"ELEVENLABS_API_KEY": "el-test-key"}

fails = []
written = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def run(tool, args, env_extra=None):
    env = dict(os.environ)
    env["AIVS_ENV_FILE"] = str(EMPTY_ENV)
    env.pop("ELEVENLABS_API_KEY", None)
    env.update(env_extra or {})
    mock_elevenlabs.reset()
    proc = subprocess.run(
        [sys.executable, str(tool)] + args,
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    return proc


def saved(directory, name):
    path = directory / name
    written.append(path)
    return path


print("=== --help documents the key each tool needs ===")
# --text is required on generate_sound.py/generate_speech.py, but argparse's
# --help exits before required-argument validation runs, so this is safe.
for tool in (SOUND_TOOL, SPEECH_TOOL, VOICES_TOOL):
    p = run(tool, ["--help"])
    check("{} --help exits 0".format(tool.name), p.returncode == 0)
    check("{} --help names ELEVENLABS_API_KEY".format(tool.name),
          "ELEVENLABS_API_KEY" in p.stdout)

print()
print("=== sound_lint gates generate_sound.py before a generation is spent ===")
p = run(SOUND_TOOL, ["--text", "a sword", "--dry-run"])
check("a bare object fails the gate", p.returncode == 3, str(p.returncode) + p.stderr[:200])
check("reports the score", "sound_lint: " in p.stderr, p.stderr[:200])
p = run(SOUND_TOOL, ["--text", "a sword", "--force", "--dry-run"])
check("--force overrides the gate on a dry run", p.returncode == 0, p.stderr[:200])

print()
print("=== dry run needs no key and leaks none ===")
p = run(SOUND_TOOL, ["--text", "torch flame crackling in a temple hallway", "--dry-run"])
check("exits 0", p.returncode == 0, p.stderr[:200])
check("shows the endpoint", "sound-generation" in p.stdout, p.stdout[:200])
check("no key in output", "el-test-key" not in p.stdout and "el-test-key" not in p.stderr)

p = run(SPEECH_TOOL, ["--text", "Your hair gets greasy 5 hours after washing it.", "--dry-run"])
check("speech dry run exits 0", p.returncode == 0, p.stderr[:200])
check("reports character count", "characters: " in p.stderr, p.stderr[:200])
check("shows the endpoint", "text-to-speech" in p.stdout, p.stdout[:200])

p = run(VOICES_TOOL, ["--list", "--dry-run"])
check("voices --list dry run exits 0", p.returncode == 0, p.stderr[:200])
check("shows the endpoint", "/v1/voices" in p.stdout, p.stdout[:200])

print()
print("=== a missing key is refused before any request is sent ===")
p = run(SOUND_TOOL, ["--text", "torch flame crackling in a temple hallway"])
check("exits 1", p.returncode == 1, str(p.returncode) + p.stderr[:200])
check("names the env var", "ELEVENLABS_API_KEY" in p.stderr, p.stderr[:200])
check("names where to get one", "elevenlabs.io" in p.stderr, p.stderr[:200])

print()
print("=== a real call generates a real sound-effect file ===")
p = run(SOUND_TOOL, ["--text", "torch flame crackling in a temple hallway",
                     "--base-url", BASE, "--out", "test-effect.mp3"], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("prints the marker", p.stdout.startswith("[sound] "), p.stdout[:80])
effect = saved(SOUND_DIR, "test-effect.mp3")
check("file written", effect.exists())
check("real audio bytes", effect.exists() and len(effect.read_bytes()) > 0)
sent = mock_elevenlabs.STATE["last"]
check("hit sound-generation", "sound-generation" in (sent or {}).get("path", ""))
check("the actual text went out",
      (sent or {}).get("body", {}).get("text") == "torch flame crackling in a temple hallway")
check("no key in output", "el-test-key" not in p.stdout)

print()
print("=== force sends a prompt that fails sound_lint anyway ===")
p = run(SOUND_TOOL, ["--text", "a sword", "--force", "--base-url", BASE,
                     "--out", "test-forced.mp3"], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
saved(SOUND_DIR, "test-forced.mp3")

print()
print("=== a real call generates a real speech file, character count reported ===")
line = "Your hair gets greasy 5 hours after washing it."
p = run(SPEECH_TOOL, ["--text", line, "--voice", "voice_premade_1",
                      "--base-url", BASE, "--out", "test-speech.mp3"], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("prints the marker", p.stdout.startswith("[voice] "), p.stdout[:80])
check("reports the right character count", "characters: {}".format(len(line)) in p.stderr,
      p.stderr[:200])
speech = saved(VOICE_DIR, "test-speech.mp3")
check("file written", speech.exists())
sent = mock_elevenlabs.STATE["last"]
check("hit the chosen voice", "voice_premade_1" in (sent or {}).get("path", ""))
check("the actual line went out", (sent or {}).get("body", {}).get("text") == line)

print()
print("=== listing voices returns the mock account's real voices ===")
p = run(VOICES_TOOL, ["--list", "--base-url", BASE], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("shows the premade voice", "Rachel" in p.stdout, p.stdout[:200])

print()
print("=== cloning refuses without consent, even with valid input ===")
p = run(VOICES_TOOL, ["--clone", "--name", "Narrator", "--sample", str(SAMPLE_1),
                      "--base-url", BASE], KEY)
check("exits 3", p.returncode == 3, str(p.returncode) + p.stderr[:200])
check("says why", "consent" in p.stderr.lower(), p.stderr[:200])
check("nothing was cloned", len(mock_elevenlabs.STATE["voices"]) == 1)

print()
print("=== cloning with consent actually sends the samples ===")
p = run(VOICES_TOOL, ["--clone", "--name", "Narrator", "--sample", str(SAMPLE_1),
                      "--sample", str(SAMPLE_2), "--consent", "--base-url", BASE], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("prints the new voice id", p.stdout.startswith("[voice] voice_cloned_"), p.stdout[:80])
sent = mock_elevenlabs.STATE["last"] or {}
recorded = sent.get("body", {})
check("hit voices/add", "voices/add" in sent.get("path", ""))
check("sent as multipart", "multipart" in recorded.get("content_type", ""),
      recorded.get("content_type", ""))
check("both sample files' bytes went out",
      b"another fake sample" in recorded.get("raw", b"")
      and b"fake sample bytes" in recorded.get("raw", b""))

print()
print("=== deleting a voice removes it ===")
voice_id = "voice_cloned_2"
p = run(VOICES_TOOL, ["--delete", voice_id, "--base-url", BASE], KEY)
check("exits 0", p.returncode == 0, p.stderr[:200])
check("removed from the mock account",
      voice_id not in [v["voice_id"] for v in mock_elevenlabs.STATE["voices"]])

print()
if fails:
    print("FAILED: {}".format(", ".join(fails)))
else:
    print("ALL ELEVENLABS CHECKS PASSED")

for path in written:
    try:
        path.unlink()
    except OSError:
        pass
for path in (SAMPLE_1, SAMPLE_2):
    try:
        path.unlink()
    except OSError:
        pass

sys.exit(1 if fails else 0)
