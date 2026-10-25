"""Talk to Skit Studio - the talking-pet skit factory - over its REST API.

Usage:
    python tools/skit_client.py --health
    python tools/skit_client.py --idea "a cat jealous of the robot vacuum" --seconds 30
    python tools/skit_client.py --status <task_id>
    python tools/skit_client.py --approve <task_id>        # spends Kie credits
    python tools/skit_client.py --download <task_id>
    python tools/skit_client.py --list

Skit Studio is a separate app (..\\Skit Studio, `python -m server`). It
writes a skit with a text model, lints and prices it, then - only after approval -
films it: Nano Banana stills, Kling 3.0 clips, VoiceStudio/ElevenLabs voices, captions,
one mp4. This file is the only place AI Video Studio knows how to speak to it; the
Videos section's Skit Studio tab calls these functions and nothing else.

The contract (Skit Studio's CLAUDE.md) mirrors MoneyPrinterTurbo:
POST /api/v1/skits -> task_id, GET /api/v1/tasks/{id}, POST .../approve, download a file.

Settings, read from this project's .env:
    SKIT_API_BASE    default http://127.0.0.1:8780
    SKIT_API_TOKEN   sent as a bearer token when Skit Studio requires one

Every function returns (result, error) - exactly one is None - like the rest of tools/.
Standard library only.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_image as gi  # noqa: E402  (.env reader)

DEFAULT_BASE = "http://127.0.0.1:8780"
OUT_DIR = ROOT / "temp" / "outputs" / "skit_studio"
RESTING = ("awaiting_approval", "done", "failed", "cancelled")
TIMEOUT = 30


def base_url():
    return (gi.env_value("SKIT_API_BASE") or DEFAULT_BASE).rstrip("/")


def web_url(task_id=None):
    """The job's page in Skit Studio's own web UI."""
    return base_url() + "/" + ("#/job/" + urllib.parse.quote(task_id) if task_id else "")


def _request(method, path, body=None, timeout=TIMEOUT, raw=False):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    token = gi.env_value("SKIT_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    url = base_url() + path
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method),
                                    timeout=timeout) as resp:
            payload = resp.read()
            return (payload if raw else json.loads(payload.decode("utf-8"))), None
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail")
        except ValueError:
            detail = exc.reason
        return None, "Skit Studio said {}: {}".format(exc.code, detail)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        return None, ("Skit Studio is not running at {} ({}). Start it with "
                      "`python -m server` in its folder.".format(base_url(), getattr(exc, "reason", exc)))


def health():
    return _request("GET", "/api/v1/health", timeout=5)


VIDEO_MODELS = (("kling-3.0", "Kling 3.0 - Higgsfield"), ("seedance-2.0", "Seedance 2.0 - Higgsfield"),
                ("seedance-2.5", "Seedance 2.5 - Higgsfield"), ("wan-3.0", "Wan 3.0 - Higgsfield"),
                ("kie-kling", "Kling 3.0 - Kie"))


def create(idea, seconds=30, style=None, mode="std", voice_provider=None, sound=False, sfx=True,
           video_model=None):
    """Start a skit. It is written and priced, then waits for approve() - nothing is spent yet.

    video_model None lets Skit Studio pick its default (Kling 3.0 on Higgsfield).
    The stills come from this app's Local API and its current Look while it is open.
    """
    body = {"idea": idea, "seconds": int(seconds), "style": style, "mode": mode,
            "voice_provider": voice_provider, "sound": bool(sound), "sfx": bool(sfx),
            "video_model": video_model}
    return _request("POST", "/api/v1/skits", body)


def ideas(count=1, hint="", avoid=()):
    """Auto-generate skit ideas - Skit Studio's writer, a small text-model call (no cost gate)."""
    return _request("POST", "/api/v1/ideas", {"count": int(count), "hint": hint or "",
                                              "avoid": list(avoid)[-10:]}, timeout=90)


def get(task_id):
    return _request("GET", "/api/v1/tasks/" + urllib.parse.quote(task_id))


def approve(task_id, force=False):
    """Pass the cost gate. This is the call that spends Kie credits."""
    return _request("POST", "/api/v1/tasks/{}/approve".format(urllib.parse.quote(task_id)), {"force": force})


def cancel(task_id):
    return _request("POST", "/api/v1/tasks/{}/cancel".format(urllib.parse.quote(task_id)))


def list_tasks(limit=30):
    result, error = _request("GET", "/api/v1/tasks?limit={}".format(int(limit)))
    return (result["tasks"] if result else None), error


def download(task_id, out_dir=None):
    """Save the finished mp4 into temp/outputs/skit_studio/ (or out_dir). Returns the path."""
    job, error = get(task_id)
    if error:
        return None, error
    url = (job.get("urls") or {}).get("final")
    if not url:
        return None, "That skit has no finished video yet (state: {}).".format(job.get("state"))
    data, error = _request("GET", url, raw=True, timeout=120)  # url is server-relative
    if error:
        return None, error
    out_dir = Path(out_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "skit-{}.mp4".format(task_id)
    path.write_bytes(data)
    return path, None


def summary(job):
    """One readable block for a job: the script lines, lint score and estimate."""
    skit = job.get("skit") or {}
    lines = ["{}  [{}]  {}%".format(skit.get("title") or "(writing...)", job.get("state"), job.get("progress", 0)),
             job.get("message") or ""]
    names = {c["id"]: c["name"] for c in skit.get("cast", [])}
    for s in skit.get("scenes", []):
        who = names.get(s.get("speaker"), "")
        lines.append("{:>2}. {:<10} {:>2}s  {}{}".format(
            s["n"], s["beat"], s["seconds"], (who + ": ") if who else "", s.get("line") or s.get("action", "")))
    if job.get("lint"):
        lines.append("lint {}/{}{}".format(job["lint"]["score"], job["lint"]["total"],
                                           "" if job["lint"]["passed"] else "  - blocked: " + ", ".join(job["lint"]["errors"])))
    if job.get("estimate"):
        lines.append("cost: " + job["estimate"].get("summary", ""))
    if job.get("error"):
        lines.append("error: " + job["error"])
    return "\n".join(l for l in lines if l is not None)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--health", action="store_true")
    p.add_argument("--idea")
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--style", choices=("photoreal", "pixar", "claymation"))
    p.add_argument("--status", metavar="TASK")
    p.add_argument("--approve", metavar="TASK", help="pass the cost gate (spends credits)")
    p.add_argument("--cancel", metavar="TASK")
    p.add_argument("--download", metavar="TASK")
    p.add_argument("--list", action="store_true")
    args = p.parse_args(argv)

    if args.health:
        result, error = health()
    elif args.idea:
        result, error = create(args.idea, args.seconds, args.style)
    elif args.status:
        result, error = get(args.status)
        if result:
            print(summary(result))
            return 0
    elif args.approve:
        result, error = approve(args.approve)
    elif args.cancel:
        result, error = cancel(args.cancel)
    elif args.download:
        result, error = download(args.download)
        if result:
            print("[video] {}".format(result))
            return 0
    elif args.list:
        result, error = list_tasks()
        if result is not None:
            for t in result:
                print("{:46} {:18} {:>3}%  {}".format(t["id"], t["state"], t["progress"], t["title"]))
            return 0
    else:
        p.print_help()
        return 1
    if error:
        print(error, file=sys.stderr)
        return 2
    if isinstance(result, dict) and "state" in result and "id" in result:
        print(summary(result))
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
