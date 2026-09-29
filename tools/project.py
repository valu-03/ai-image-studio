"""A project file: everything a session was, in one JSON manifest.

THE HOLE THIS FILLS. A nine-scene Cats story - scenes, storyboard, generated
clips, sound effects, voiceovers - lived only in `CatsView.scenes` / `.videos` /
`.sfx`, all plain Python attributes, and closing the window threw the lot away.
Characters could be saved and personas could be saved, but the body of work that
USES them could not. Nothing in the app grouped a spec, its scenes and its
outputs into a thing with a name.

WHAT IT DELIBERATELY DOES NOT DO. It stores no image bytes and copies no files.
A project records the spec and the PATHS of what was generated, because the
files already live in temp/outputs/ and duplicating them into a manifest would
make the manifest enormous and the copies stale. That means a project can
reference a file that has since been deleted, which is why `missing()` exists -
it is better to say "four of these nine clips are gone" than to silently load a
story with holes in it.

Standard library only. No Qt here: the GUI reads and writes these dicts, and
keeping the format in tools/ means the CLI can too, the same split every other
bank and builder in this project follows.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "temp" / "resources" / "projects"

#: Bumped when the shape changes incompatibly. `load()` refuses a version it
#: does not understand rather than guessing, for the same reason
#: history.usable() discards entries from a different bank_version: a
#: half-understood project is worse than a refused one.
VERSION = 1

SUFFIX = ".aivs.json"


def _slug(name):
    keep = [c.lower() if c.isalnum() else "-" for c in (name or "project")]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "project"


def new_project(name="Untitled", spec=None):
    """An empty project. `spec` is Compose's own dict, stored verbatim."""
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "version": VERSION,
        "name": name,
        "created": now,
        "modified": now,
        "spec": dict(spec or {}),
        # The Cats story, exactly as CatsView holds it.
        "scenes": [],
        "videos": {},          # scene index (as a string key) -> clip path
        "sfx": {},             # scene index -> {layer: audio path}
        "images": {},          # scene index -> still path
        "render": "",          # the finished cut, if one was made
        "notes": "",
    }


def from_views(name, spec=None, scenes=None, videos=None, sfx=None,
               images=None, render="", notes=""):
    """Build a project from what the views are holding right now.

    JSON object keys are always strings, so the integer scene indices the views
    use are stringified HERE rather than being left to json.dump - otherwise
    `videos[3]` would write as "3" and read back as "3" while every caller
    still looked for 3, which is the kind of asymmetry that only shows up once
    a file has been saved and reloaded.
    """
    project = new_project(name, spec)
    project["scenes"] = list(scenes or [])
    project["videos"] = {str(k): str(v) for k, v in (videos or {}).items()}
    project["images"] = {str(k): str(v) for k, v in (images or {}).items()}
    project["sfx"] = {
        str(k): {str(layer): str(path) for layer, path in (value or {}).items()}
        for k, value in (sfx or {}).items()
    }
    project["render"] = str(render or "")
    project["notes"] = notes or ""
    return project


def path_for(name, folder=None):
    folder = Path(folder) if folder else PROJECTS_DIR
    return folder / (_slug(name) + SUFFIX)


def save(project, path=None, folder=None):
    """Write the manifest. Returns the path written."""
    project = dict(project)
    project["modified"] = datetime.now().isoformat(timespec="seconds")
    target = Path(path) if path else path_for(project.get("name", "project"), folder)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(project, indent=2), encoding="utf-8")
    return target


def load(path):
    """Read a manifest. Raises ValueError on anything it cannot honour."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read {}: {}".format(path.name, exc))
    if not isinstance(data, dict):
        raise ValueError("{} is not a project file".format(path.name))
    version = data.get("version")
    if version != VERSION:
        raise ValueError(
            "{} was written by a different version of the project format "
            "(found {}, this app writes {}). Refusing to guess at it.".format(
                path.name, version, VERSION))
    # Fill anything a hand-edited file left out, so callers can index freely.
    base = new_project(data.get("name", path.stem))
    base.update(data)
    return base


def listing(folder=None):
    """Every project on disk, most recently modified first."""
    folder = Path(folder) if folder else PROJECTS_DIR
    if not folder.exists():
        return []
    out = []
    for path in folder.glob("*" + SUFFIX):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue            # a corrupt file is skipped, never fatal
        out.append({
            "path": path,
            "name": data.get("name") or path.stem,
            "modified": data.get("modified") or "",
            "scenes": len(data.get("scenes") or []),
        })
    out.sort(key=lambda row: row["modified"], reverse=True)
    return out


def referenced_files(project):
    """Every path a project points at, in one flat list."""
    paths = []
    for value in (project.get("videos") or {}).values():
        paths.append(value)
    for value in (project.get("images") or {}).values():
        paths.append(value)
    for group in (project.get("sfx") or {}).values():
        paths.extend((group or {}).values())
    if project.get("render"):
        paths.append(project["render"])
    reference = (project.get("spec") or {}).get("reference")
    if reference:
        paths.append(reference)
    return [p for p in paths if p]


def missing(project):
    """The referenced files that are no longer on disk.

    A project stores paths rather than bytes, so a file can vanish between
    saving and loading - temp/outputs/ is a folder this app's own Settings
    labels "disposable" to the user's face. Saying which are gone is the
    honest alternative to loading a story with silent holes in it.
    """
    out = []
    for raw in referenced_files(project):
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            out.append(raw)
    return out


def scene_videos(project):
    """`videos` with integer keys, the way the views want it back."""
    out = {}
    for key, value in (project.get("videos") or {}).items():
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def scene_sfx(project):
    """`sfx` with integer keys."""
    out = {}
    for key, value in (project.get("sfx") or {}).items():
        try:
            out[int(key)] = dict(value or {})
        except (TypeError, ValueError):
            continue
    return out


def scene_images(project):
    """`images` with integer keys."""
    out = {}
    for key, value in (project.get("images") or {}).items():
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def describe(project):
    """One line for a status bar or a recent-files menu."""
    bits = [project.get("name") or "Untitled"]
    scenes = len(project.get("scenes") or [])
    if scenes:
        bits.append("{} scene{}".format(scenes, "" if scenes == 1 else "s"))
    clips = len(project.get("videos") or {})
    if clips:
        bits.append("{} clip{}".format(clips, "" if clips == 1 else "s"))
    if project.get("render"):
        bits.append("rendered")
    return " · ".join(bits)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect the project manifests this app saves.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--list", action="store_true", help="every saved project")
    parser.add_argument("--show", help="print one project and what it references")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.list:
        rows = listing()
        if not rows:
            print("No projects in {}".format(PROJECTS_DIR))
            return 0
        for row in rows:
            print("  {:<28} {:>2} scene(s)  {}".format(
                row["name"][:28], row["scenes"], row["modified"]))
        return 0

    if args.show:
        project = load(args.show)
        print(describe(project))
        for raw in referenced_files(project):
            print("   " + raw)
        gone = missing(project)
        if gone:
            print("MISSING {} file(s):".format(len(gone)))
            for raw in gone:
                print("   " + raw)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
