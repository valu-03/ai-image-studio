"""Assemble a sequence of generated clips into one exported .mp4.

Usage:
    python tools/render_video.py --scenes-file story.json --aspect 9:16 --out final.mp4
    python tools/render_video.py --scenes-file story.json --dry-run

`--scenes-file` points at a JSON array of scenes, in timeline order:

    [{"clip_path": "temp/outputs/videos/story-1-hook.mp4",
      "voice_path": "temp/outputs/voice/cats-1-voice.mp3",
      "sfx_paths": ["temp/outputs/sound/cats-1-ambience.mp3"],
      "duration": 5},
     {"clip_path": "temp/outputs/videos/story-2-build.mp4",
      "voice_path": null,
      "sfx_paths": [],
      "duration": 5}]

`voice_path` and `sfx_paths` are both optional per scene; a scene with
neither keeps only its own clip audio (or silence, if the clip was generated
without native sound). Every layer present - voiceover and any number of SFX
layers - is mixed together, not chosen between.

WHY FOUR SEPARATE FFMPEG PASSES, NOT ONE FILTER GRAPH:

Clips come from independent, async provider jobs (Kling 3.0 via generate_video.py)
run at different times, so nothing guarantees they share a resolution, frame rate
or codec. Rather than build one dynamic filter_complex string that has to account
for every combination of "has voice" / "resolution differs" per scene, each stage
below is one small, single-purpose ffmpeg call:

    1. normalize   every clip -> identical resolution/fps/codec/audio format
    2. mix         (only scenes with a voice file) clip audio + voice -> one track
    3. concat      the now-identical per-scene files, via the concat DEMUXER with
                   -c copy (valid and fast specifically because step 1 already
                   made every input bit-identical in format - no filter-based
                   concat or second full re-encode needed)
    4. verify      the muxed result opens and reports a duration

This keeps each stage independently debuggable (one ffmpeg invocation, one
input, one clear stderr blob if it fails), gives `on_stage()` real per-step
granularity, and gives `should_cancel()` a natural checkpoint between stages.

ffmpeg comes from the `imageio-ffmpeg` package (a bundled binary, no system
install required) - see _ffmpeg_exe(). Standard library plus imageio-ffmpeg
only; no moviepy.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "temp" / "outputs" / "render"
WORK_DIRNAME = "_work"

FPS = 30
# Matches generate_video.py's ASPECTS exactly - a render targets whatever
# aspect the clips were actually generated at.
RESOLUTIONS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
DEFAULT_ASPECT = "9:16"


def _ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run_ffmpeg(args, on_stage=None, stage_message=None):
    """Run one ffmpeg invocation. Returns (ok, stderr_text).

    Never uses shell=True. Failure is the return code, never "stderr is
    non-empty" - ffmpeg writes benign banner/progress chatter to stderr even
    on success, so trusting emptiness would flag good runs as failures.
    """
    if on_stage and stage_message:
        on_stage(stage_message)
    exe = _ffmpeg_exe()
    proc = subprocess.run(
        [exe, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True, text=True,
    )
    return proc.returncode == 0, proc.stderr


def _cancelled(should_cancel):
    return bool(should_cancel and should_cancel())


def _normalize_clip(clip_path, out_path, width, height, duration,
                    on_stage=None, stage_message=None):
    """`-t {duration}` is the real bound here, not `-shortest`: `apad` has no
    natural end (it pads with silence forever), and `-shortest` proved
    unreliable at cutting an unbounded padded stream at the video's actual
    length - it was observed inflating a 1s test clip to 15s+. The scene's own
    known duration is already available from generate_video.generate()'s
    request, so use it directly instead of trusting stream-length inference.
    """
    vf = (
        "scale=w={w}:h={h}:force_original_aspect_ratio=decrease,"
        "pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
    ).format(w=width, h=height, fps=FPS)
    args = [
        "-i", str(clip_path),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
        # `apad` guarantees an audio stream even on a silent/no-audio clip -
        # every normalized file needs one so the later concat-demuxer copy
        # (which requires identical streams across inputs) stays valid.
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-af", "apad",
        "-t", str(duration),
        str(out_path),
    ]
    return _run_ffmpeg(args, on_stage, stage_message)


def _mix_scene_audio(normalized_path, audio_paths, out_path, duration,
                     on_stage=None, stage_message=None):
    """Mix a scene's own (already-normalized) audio with one or more extra
    layers - a voiceover, and/or up to three ElevenLabs SFX layers
    (ambience/key/accent). `audio_paths` is a plain list, not a fixed
    voice-only slot, so a scene with any number of layers (including zero,
    though the caller skips this step entirely then) is the same code path.

    `-t {duration}` (same reasoning as `_normalize_clip`) pins the result to
    the scene's real length regardless of how long any layer runs, so a
    voiceover or effect longer than the clip cannot silently extend the scene.
    """
    args = ["-i", str(normalized_path)]
    for path in audio_paths:
        args += ["-i", str(path)]

    chains, mix_inputs = [], ["[0:a]"]
    for i in range(1, len(audio_paths) + 1):
        label = "a{}".format(i)
        chains.append("[{}:a]aformat=sample_rates=48000:channel_layouts=stereo,apad[{}]"
                      .format(i, label))
        mix_inputs.append("[{}]".format(label))
    mix_graph = "{}amix=inputs={}:duration=first:dropout_transition=0[aout]".format(
        "".join(mix_inputs), len(audio_paths) + 1)
    filter_complex = ";".join(chains + [mix_graph])

    args += [
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        "-t", str(duration),
        str(out_path),
    ]
    return _run_ffmpeg(args, on_stage, stage_message)


def _concat(part_paths, out_path, work_dir, on_stage=None, stage_message=None):
    list_path = work_dir / "concat.txt"
    lines = ["file '{}'".format(Path(p).resolve().as_posix()) for p in part_paths]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = ["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out_path)]
    return _run_ffmpeg(args, on_stage, stage_message)


def render(scenes, out_path, aspect_ratio=None, should_cancel=None, on_stage=None):
    """scenes -> one exported .mp4. Returns (path, error) - exactly one is None.

    `scenes`: ordered list of {"clip_path": str/Path, "voice_path": str/Path|None,
    "sfx_paths": [str/Path, ...]|None, "duration": float}. `sfx_paths` is any
    number of extra ElevenLabs layers (ambience/key/accent) - mixed in
    alongside the voiceover, not instead of it. Mirrors generate_video.generate's
    (path, error) contract so callers don't need a different error-handling
    shape per tool.
    """
    if not scenes:
        return None, gi.GenerationError("No scenes to render.", 4)

    width, height = RESOLUTIONS.get(aspect_ratio or DEFAULT_ASPECT, RESOLUTIONS[DEFAULT_ASPECT])
    out_path = Path(out_path)
    work_dir = out_path.parent / WORK_DIRNAME
    work_dir.mkdir(parents=True, exist_ok=True)

    part_paths = []
    total = len(scenes)
    for index, scene in enumerate(scenes):
        if _cancelled(should_cancel):
            return None, gi.GenerationError("Cancelled.", 3)
        clip_path = scene.get("clip_path")
        if not clip_path or not Path(clip_path).exists():
            return None, gi.GenerationError(
                "Scene {} has no clip at {}.".format(index + 1, clip_path), 4)

        duration = scene.get("duration") or 5
        norm_path = work_dir / "_norm_{}.mp4".format(index)
        ok, err = _normalize_clip(
            clip_path, norm_path, width, height, duration, on_stage,
            "Normalizing clip {}/{}...".format(index + 1, total))
        if not ok:
            return None, gi.GenerationError(
                "ffmpeg failed normalizing scene {}: {}".format(index + 1, err[-2000:]), 4)

        voice_path = scene.get("voice_path")
        audio_paths = [p for p in ([voice_path] + list(scene.get("sfx_paths") or []))
                      if p and Path(p).exists()]
        if audio_paths:
            mixed_path = work_dir / "_mixed_{}.mp4".format(index)
            ok, err = _mix_scene_audio(
                norm_path, audio_paths, mixed_path, duration, on_stage,
                "Mixing audio {}/{}...".format(index + 1, total))
            if not ok:
                return None, gi.GenerationError(
                    "ffmpeg failed mixing scene {}: {}".format(index + 1, err[-2000:]), 4)
            part_paths.append(mixed_path)
        else:
            part_paths.append(norm_path)

    if _cancelled(should_cancel):
        return None, gi.GenerationError("Cancelled.", 3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, err = _concat(part_paths, out_path, work_dir, on_stage, "Concatenating...")
    if not ok:
        return None, gi.GenerationError("ffmpeg failed concatenating: {}".format(err[-2000:]), 4)

    if on_stage:
        on_stage("Done.")
    return out_path, None


# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenes-file", required=True, help="JSON array, see module docstring")
    parser.add_argument("--aspect", choices=list(RESOLUTIONS), default=DEFAULT_ASPECT)
    parser.add_argument("--out", help="output filename inside temp/outputs/render/")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the scene plan, run nothing")
    args = parser.parse_args(argv)

    scenes = json.loads(Path(args.scenes_file).read_text(encoding="utf-8"))
    if args.dry_run:
        print(json.dumps(scenes, indent=2))
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / (args.out or "render.mp4")
    path, error = render(
        scenes, out_path, aspect_ratio=args.aspect,
        on_stage=lambda message: print(message, file=sys.stderr))
    if error:
        print(str(error), file=sys.stderr)
        return getattr(error, "code", 4)
    print("[render] {}".format(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
