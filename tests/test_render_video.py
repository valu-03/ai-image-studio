"""tools/render_video.py: normalize, mix, concat - end to end, with real ffmpeg.

No network, no real provider API - every input clip here is synthesized
locally with ffmpeg's own `lavfi` test sources (testsrc/anullsrc), the same
binary render_video.py itself calls through imageio_ffmpeg. This exercises the
real pipeline (four real ffmpeg subprocess calls), not a mock of it - a mock
would prove the Python glue is correct while missing exactly the kind of
filter-syntax mistake that only a real ffmpeg run catches.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import render_video as rv  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


WORKDIR = Path(tempfile.mkdtemp(prefix="aivs-render-test-"))


def _ffmpeg(args):
    exe = rv._ffmpeg_exe()
    proc = subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr


def make_clip(path, seconds, color="red", with_audio=True):
    """A tiny synthetic clip - a solid colour field plus (optionally) silence."""
    args = ["-f", "lavfi", "-i",
            "color=c={}:s=320x240:d={}".format(color, seconds)]
    if with_audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d={}".format(seconds)]
        args += ["-map", "0:v", "-map", "1:a"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds)]
    if with_audio:
        args += ["-c:a", "aac"]
    args += [str(path)]
    ok, err = _ffmpeg(args)
    if not ok:
        raise RuntimeError("failed to build test fixture clip: " + err)


def make_audio(path, seconds):
    ok, err = _ffmpeg([
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d={}".format(seconds),
        "-c:a", "libmp3lame", str(path),
    ])
    if not ok:
        raise RuntimeError("failed to build test fixture audio: " + err)


def probed_duration(path):
    """Seconds, parsed off ffmpeg's own stderr banner - no ffprobe bundled."""
    exe = rv._ffmpeg_exe()
    proc = subprocess.run([exe, "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr)
    if not match:
        return None
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


print("=== FIXTURES ===")
clip_a = WORKDIR / "a.mp4"
clip_b = WORKDIR / "b.mp4"
clip_silent = WORKDIR / "silent.mp4"
voice_a = WORKDIR / "voice-a.mp3"
try:
    make_clip(clip_a, 1, color="red")
    make_clip(clip_b, 1, color="blue")
    make_clip(clip_silent, 1, color="green", with_audio=False)
    make_audio(voice_a, 1)
    check("built two 1s clips and a silent one", True)
except RuntimeError as exc:
    check("built test fixtures", False, str(exc))

print()
print("=== HAPPY PATH: two clips, no voice ===")
out1 = WORKDIR / "out1.mp4"
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": None, "duration": 1},
     {"clip_path": str(clip_b), "voice_path": None, "duration": 1}],
    out1, aspect_ratio="9:16")
check("no error", error is None, str(error))
check("returns the output path", path == out1, str(path))
check("the file exists", out1.exists())
duration = probed_duration(out1) if out1.exists() else None
check("roughly 2 seconds long", duration is not None and 1.5 <= duration <= 2.5,
      str(duration))

print()
print("=== A SILENT CLIP STILL CONCATENATES (audio stream guaranteed by apad) ===")
out2 = WORKDIR / "out2.mp4"
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": None, "duration": 1},
     {"clip_path": str(clip_silent), "voice_path": None, "duration": 1}],
    out2, aspect_ratio="9:16")
check("no error mixing a clip with audio and one without", error is None, str(error))
check("the file exists", out2.exists())

print()
print("=== VOICEOVER: mixed into its own scene, not others ===")
out3 = WORKDIR / "out3.mp4"
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": str(voice_a), "duration": 1},
     {"clip_path": str(clip_b), "voice_path": None, "duration": 1}],
    out3, aspect_ratio="9:16")
check("no error with one scene voiced and one not", error is None, str(error))
check("the file exists", out3.exists())
duration = probed_duration(out3) if out3.exists() else None
check("a voiceover does not extend the scene past its clip", duration is not None
      and 1.5 <= duration <= 2.5, str(duration))

print()
print("=== MULTIPLE LAYERS: voiceover AND sfx_paths mixed together ===")
voice_b = WORKDIR / "voice-b.mp3"
sfx_1 = WORKDIR / "sfx-1.mp3"
sfx_2 = WORKDIR / "sfx-2.mp3"
try:
    make_audio(voice_b, 1)
    make_audio(sfx_1, 1)
    make_audio(sfx_2, 1)
    check("built the extra audio layers", True)
except RuntimeError as exc:
    check("built the extra audio layers", False, str(exc))

out4 = WORKDIR / "out4.mp4"
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": str(voice_b),
      "sfx_paths": [str(sfx_1), str(sfx_2)], "duration": 1}],
    out4, aspect_ratio="9:16")
check("no error mixing a voiceover and two SFX layers at once", error is None, str(error))
check("the file exists", out4.exists())
duration = probed_duration(out4) if out4.exists() else None
check("still pinned to the scene's own duration, not any layer's",
      duration is not None and 0.5 <= duration <= 1.5, str(duration))

out5 = WORKDIR / "out5.mp4"
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": None,
      "sfx_paths": [str(sfx_1)], "duration": 1}],
    out5, aspect_ratio="9:16")
check("sfx_paths alone (no voiceover) mixes cleanly too", error is None and out5.exists(),
      str(error))

print()
print("=== 16:9 AND 1:1 TARGETS ARE ACCEPTED TOO ===")
for aspect in ("16:9", "1:1"):
    out = WORKDIR / "out-{}.mp4".format(aspect.replace(":", "x"))
    path, error = rv.render(
        [{"clip_path": str(clip_a), "voice_path": None, "duration": 1}], out,
        aspect_ratio=aspect)
    check("{} renders cleanly".format(aspect), error is None and out.exists(), str(error))

print()
print("=== REFUSES RATHER THAN GUESSING ===")
path, error = rv.render([], WORKDIR / "empty.mp4")
check("no scenes is a clean error, not a crash", path is None and error is not None)

path, error = rv.render(
    [{"clip_path": str(WORKDIR / "does-not-exist.mp4"), "voice_path": None, "duration": 1}],
    WORKDIR / "missing.mp4")
check("a missing clip file is a clean error, not an ffmpeg stack trace",
      path is None and error is not None and "does-not-exist" in str(error), str(error))

print()
print("=== CANCELLATION IS CHECKED BEFORE ANY WORK STARTS ===")
path, error = rv.render(
    [{"clip_path": str(clip_a), "voice_path": None, "duration": 1},
     {"clip_path": str(clip_b), "voice_path": None, "duration": 1}],
    WORKDIR / "cancelled.mp4", should_cancel=lambda: True)
check("cancelled before the first ffmpeg call", path is None and error is not None
      and "cancel" in str(error).lower(), str(error))

print()
print("=== CLI ===")
scenes_file = WORKDIR / "scenes.json"
scenes_file.write_text(json.dumps(
    [{"clip_path": str(clip_a), "voice_path": None, "duration": 1}]), encoding="utf-8")
proc = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "render_video.py"),
     "--scenes-file", str(scenes_file), "--dry-run"],
    capture_output=True, text=True, cwd=str(ROOT))
check("--dry-run prints the scene plan and exits clean", proc.returncode == 0
      and "clip_path" in proc.stdout, proc.stdout + proc.stderr)

shutil.rmtree(WORKDIR, ignore_errors=True)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL RENDER_VIDEO CHECKS PASSED")
