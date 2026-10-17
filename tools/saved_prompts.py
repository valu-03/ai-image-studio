"""Your Prompt Bank - prompts saved exactly as you gave them, with their example images.

Usage:
    python tools/saved_prompts.py add --kind image --title "Active volcano infographic" \
        --file prompt.txt --image example1.png --image example2.jpg
    cat prompt.txt | python tools/saved_prompts.py add --kind video --title "Selfie monologue"
    python tools/saved_prompts.py attach "Active volcano infographic" --image another.png
    python tools/saved_prompts.py images "Active volcano infographic"
    python tools/saved_prompts.py reorder "Active volcano infographic" b.png a.png c.png
    python tools/saved_prompts.py rename-image "Active volcano infographic" a.png "cover shot"
    python tools/saved_prompts.py list
    python tools/saved_prompts.py show "Active volcano infographic"
    python tools/saved_prompts.py delete "Active volcano infographic" --kind image

THE ONE RULE: a prompt is stored byte for byte, and so is every example image.
Nothing is trimmed, reflowed, re-encoded, resized or "fixed" - line endings,
trailing spaces, [brackets], quotes and blank lines all come back exactly as
they went in, and an image is a straight file copy. This is a library of the
user's own prompts, not a composer, so the app has no opinion about any of it.

STORAGE. One folder per prompt, the folder name IS the title:

    temp/resources/prompt_bank/<kind>/<title>/prompt.txt     the exact text
    temp/resources/prompt_bank/<kind>/<title>/<image files>  its examples, original names
    temp/resources/prompt_bank/<kind>/<title>/order.txt      the images' order, one name
                                                             per line (only once reordered)

No index file to fall out of step, and any prompt can be opened, copied or
backed up by hand. temp/resources/ is user data: the same "never delete
without being asked" rule as the character library applies. The .exe built
into dist/ uses this same checkout folder (see _default_bank_dir), so a prompt
saved in either one shows up in both.
(Not to be confused with tools/prompt_bank.json, the realism vocabulary the
prompt builder draws from - unrelated, which is why this module is named
saved_prompts.)

AIVS_PROMPT_BANK_DIR redirects the folder, so a test can never touch the
user's real prompts - the same seam as AIVS_HISTORY_FILE.

Standard library only. No API keys, no network.
"""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("image", "video")
PROMPT_FILE = "prompt.txt"
ORDER_FILE = "order.txt"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".avif"}
# Characters Windows forbids in a file name, plus control characters.
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
MAX_TITLE = 80


class PromptBankError(ValueError):
    """An unknown kind, an empty prompt or title, a missing image, or a title that is not there."""


def _default_bank_dir(root):
    """root's own temp/resources/prompt_bank - unless root is a build in <checkout>/dist/.

    The frozen .exe ships tools/ as loose files, so its ROOT is dist/AI Video Studio/
    and it would otherwise keep a second, empty bank there - one PyInstaller wipes
    on every rebuild. A build that still sits inside its checkout shares the
    checkout's bank instead; an .exe copied anywhere else keeps its own.
    """
    root = Path(root)
    checkout = root.parent.parent
    if root.parent.name.lower() == "dist" and (checkout / "gui.py").is_file():
        root = checkout
    return root / "temp" / "resources" / "prompt_bank"


def bank_dir():
    """The Prompt Bank folder - read at call time, so the env seam always applies."""
    override = os.environ.get("AIVS_PROMPT_BANK_DIR")
    return Path(override) if override else _default_bank_dir(ROOT)


def kind_dir(kind):
    if kind not in KINDS:
        raise PromptBankError("Unknown kind '{}'. Use one of: {}".format(kind, ", ".join(KINDS)))
    return bank_dir() / kind


def clean_title(title):
    """A title made safe to be a folder name - readable, not slugified.

    Only what Windows forbids is removed; case and spaces stay, because the
    folder name is what the user sees in the list.
    """
    text = _UNSAFE.sub(" ", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip().strip(".")
    return text[:MAX_TITLE].rstrip()


def _free(folder, name, suffix=""):
    """folder/name+suffix, or name-2, name-3... - never an existing path."""
    path = folder / (name + suffix)
    n = 2
    while path.exists():
        path = folder / "{}-{}{}".format(name, n, suffix)
        n += 1
    return path


def is_image(path):
    return Path(path).suffix.lower() in IMAGE_EXTS


def attach(entry, new_images):
    """Copy example images into a prompt's folder, byte for byte, keeping their
    names (a clash gets -2, -3 - nothing is overwritten). Returns the new paths.
    Every source is checked before anything is copied, so a bad path never
    leaves a half-attached set behind."""
    entry = Path(entry)
    sources = [Path(p) for p in new_images or ()]
    for src in sources:
        if not src.is_file():
            raise PromptBankError("Image not found: {}".format(src))
        if not is_image(src):
            raise PromptBankError("Not an image file: {}".format(src.name))
    current = [p.name for p in images(entry)]
    copied = []
    for src in sources:
        target = _free(entry, src.stem, src.suffix)
        shutil.copyfile(src, target)
        copied.append(target)
    # New images join at the END of whatever order the user has set, rather
    # than being sorted into the middle of it by name.
    if (entry / ORDER_FILE).exists() and copied:
        _write_order(entry, current + [p.name for p in copied])
    return copied


def add(kind, title, text, images=()):
    """Save `text` verbatim (plus any example images) as a new prompt; return its folder.

    Refuses an empty prompt (all whitespace counts as empty - there would be
    nothing to bank) but otherwise never alters a character. newline="" is
    what stops Python translating line endings on the way to disk.
    """
    if not isinstance(text, str) or not text.strip():
        raise PromptBankError("The prompt is empty - nothing to save.")
    title = clean_title(title)
    if not title:
        raise PromptBankError("Give the prompt a title.")
    for src in images or ():
        if not Path(src).is_file():
            raise PromptBankError("Image not found: {}".format(src))
        if not is_image(src):
            raise PromptBankError("Not an image file: {}".format(Path(src).name))
    folder = kind_dir(kind)
    folder.mkdir(parents=True, exist_ok=True)
    entry = _free(folder, title)
    entry.mkdir()
    with (entry / PROMPT_FILE).open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    attach(entry, images)
    return entry


def read(entry):
    """The prompt's text, exactly as saved."""
    with (Path(entry) / PROMPT_FILE).open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _read_order(entry):
    path = Path(entry) / ORDER_FILE
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_order(entry, names):
    with (Path(entry) / ORDER_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(name + "\n" for name in names))


def images(entry):
    """The prompt's example images, in the user's order.

    order.txt (written the first time they are reordered) lists names one per
    line. Anything listed that no longer exists is skipped; any image not
    listed - added by hand into the folder, say - follows at the end in name
    order. So the order file can never hide an image or break the list, and
    a folder that was never reordered is simply in name order.
    """
    entry = Path(entry)
    found = {p.name: p for p in entry.iterdir() if p.is_file() and is_image(p)}
    ordered = [found.pop(name) for name in _read_order(entry) if name in found]
    return ordered + sorted(found.values(), key=lambda p: p.name.lower())


def set_order(entry, names):
    """Save the images' order. `names` must be exactly the current images, each
    once - a reorder never adds, drops or renames anything."""
    entry = Path(entry)
    current = [p.name for p in images(entry)]
    if sorted(names) != sorted(current) or len(set(names)) != len(names):
        raise PromptBankError("A new order must list each of this prompt's images exactly once.")
    _write_order(entry, list(names))
    return images(entry)


def rename_image(path, new_name):
    """Rename one example image, keeping its extension and its place in the
    order. A taken name gets -2, -3 rather than overwriting. Returns the new path."""
    path = Path(path)
    if not path.is_file() or not is_image(path):
        raise PromptBankError("Not an example image: {}".format(path.name))
    stem = clean_title(new_name)
    # A typed extension is dropped, never applied: renaming .png to .jpg
    # does not convert anything, it just makes the file unreadable.
    if Path(stem).suffix.lower() in IMAGE_EXTS:
        stem = clean_title(Path(stem).stem)
    if not stem:
        raise PromptBankError("Give the image a name.")
    if stem == path.stem:
        return path
    entry = path.parent
    order = [p.name for p in images(entry)]
    target = _free(entry, stem, path.suffix)
    path.rename(target)
    _write_order(entry, [target.name if n == path.name else n for n in order])
    return target


def entries(kind):
    """[{title, path, saved, images}] for one kind, newest first."""
    folder = kind_dir(kind)
    if not folder.exists():
        return []
    rows = []
    for entry in folder.iterdir():
        prompt = entry / PROMPT_FILE
        if entry.is_dir() and prompt.is_file():
            rows.append({"title": entry.name, "path": entry,
                         "saved": datetime.fromtimestamp(prompt.stat().st_mtime),
                         "images": len(images(entry))})
    rows.sort(key=lambda r: (r["saved"], r["title"]), reverse=True)
    return rows


def find(title, kind=None):
    """The folder of the prompt with this exact title, searching one kind or both."""
    for k in ([kind] if kind else KINDS):
        entry = kind_dir(k) / str(title)
        if (entry / PROMPT_FILE).is_file():
            return entry
    raise PromptBankError("No saved prompt titled '{}'.".format(title))


def rename(entry, new_title):
    """Give a saved prompt a new title; text and images are untouched. Returns
    the new folder. A taken title gets -2, -3 rather than overwriting."""
    entry = Path(entry)
    title = clean_title(new_title)
    if not title:
        raise PromptBankError("Give the prompt a title.")
    if title == entry.name:
        return entry
    target = _free(entry.parent, title)
    entry.rename(target)
    return target


def remove_image(path):
    """Remove one example image. Only ever called on an explicit user request."""
    path = Path(path)
    if not is_image(path):
        raise PromptBankError("Not an image file: {}".format(path.name))
    entry = path.parent
    order = [p.name for p in images(entry)]
    path.unlink()
    if (entry / ORDER_FILE).exists():
        _write_order(entry, [n for n in order if n != path.name])


def delete(entry):
    """Remove one saved prompt and its images. Only ever on an explicit user request.
    Refuses anything that is not a prompt folder inside the bank."""
    entry = Path(entry).resolve()
    if not (entry / PROMPT_FILE).is_file() or bank_dir().resolve() not in entry.parents:
        raise PromptBankError("Not a saved prompt: {}".format(entry))
    shutil.rmtree(entry)


def _read_input(file_arg):
    if file_arg and file_arg != "-":
        with Path(file_arg).open("r", encoding="utf-8", newline="") as fh:
            return fh.read()
    return sys.stdin.buffer.read().decode("utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Your Prompt Bank - prompts saved exactly as given, with example images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="save a prompt verbatim, with optional example images")
    a.add_argument("--kind", choices=KINDS, required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--file", help="a text file holding the prompt; omit or - for stdin")
    a.add_argument("--image", action="append", default=[], help="an example image, repeatable")
    at = sub.add_parser("attach", help="add example images to a saved prompt")
    at.add_argument("title")
    at.add_argument("--kind", choices=KINDS)
    at.add_argument("--image", action="append", required=True, help="repeatable")
    im = sub.add_parser("images", help="list a prompt's example images, in order")
    im.add_argument("title")
    im.add_argument("--kind", choices=KINDS)
    ro = sub.add_parser("reorder", help="set the images' order (every image, once)")
    ro.add_argument("title")
    ro.add_argument("names", nargs="+")
    ro.add_argument("--kind", choices=KINDS)
    rn = sub.add_parser("rename-image", help="rename one example image (extension kept)")
    rn.add_argument("title")
    rn.add_argument("old")
    rn.add_argument("new")
    rn.add_argument("--kind", choices=KINDS)
    ls = sub.add_parser("list", help="list saved prompts")
    ls.add_argument("--kind", choices=KINDS)
    sh = sub.add_parser("show", help="print one prompt exactly")
    sh.add_argument("title")
    sh.add_argument("--kind", choices=KINDS)
    dl = sub.add_parser("delete", help="delete one prompt and its images (only when asked)")
    dl.add_argument("title")
    dl.add_argument("--kind", choices=KINDS)
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        if args.command == "add":
            entry = add(args.kind, args.title, _read_input(args.file), args.image)
            print("[saved] {}  ({} example image(s))".format(entry, len(images(entry))))
        elif args.command == "attach":
            entry = find(args.title, args.kind)
            for path in attach(entry, args.image):
                print("[attached] {}".format(path))
        elif args.command == "images":
            for i, path in enumerate(images(find(args.title, args.kind)), 1):
                print("{:>3}. {}".format(i, path.name))
        elif args.command == "reorder":
            for i, path in enumerate(set_order(find(args.title, args.kind), args.names), 1):
                print("{:>3}. {}".format(i, path.name))
        elif args.command == "rename-image":
            entry = find(args.title, args.kind)
            print("[renamed] {}".format(rename_image(entry / args.old, args.new).name))
        elif args.command == "list":
            for kind in ([args.kind] if args.kind else KINDS):
                rows = entries(kind)
                print("{} PROMPTS ({})".format(kind.upper(), len(rows)))
                for row in rows:
                    print("  {:%Y-%m-%d %H:%M}  {}  [{} image(s)]".format(
                        row["saved"], row["title"], row["images"]))
                print()
        elif args.command == "show":
            sys.stdout.buffer.write(read(find(args.title, args.kind)).encode("utf-8"))
        elif args.command == "delete":
            entry = find(args.title, args.kind)
            delete(entry)
            print("[deleted] {}".format(entry))
    except PromptBankError as exc:
        sys.exit(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
