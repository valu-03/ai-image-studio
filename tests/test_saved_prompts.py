"""tools/saved_prompts.py + the Assistant > Prompt Bank tab.

The Prompt Bank's whole promise is "exactly as you gave it", so the core of
this suite is byte-for-byte round trips - CRLF, trailing spaces, [brackets],
quotes, unicode, leading and trailing blank lines - for the text AND for the
example images. Then: nothing is ever overwritten, kinds stay apart, delete
only removes what it is pointed at, and the GUI shows and copies the exact
text. Everything runs in a temporary AIVS_PROMPT_BANK_DIR - the user's real
prompts are never touched.

Offscreen, no network.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

TMP = Path(tempfile.mkdtemp(prefix="aivs-prompt-bank-"))
os.environ["AIVS_PROMPT_BANK_DIR"] = str(TMP / "bank")
_EMPTY = TMP / "empty.env"
_EMPTY.write_text("# intentionally empty\n", encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY)
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")
os.environ["AIVS_HISTORY_FILE"] = str(TMP / "history.jsonl")

import saved_prompts as sp  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def raw(path):
    return Path(path).read_bytes()


def _png(width=4, height=4):
    """A tiny valid PNG, built by hand, so image copies can be compared exactly."""
    import struct
    import zlib

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    rows = b"".join(b"\x00" + b"\xff\x55\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


PNG = _png()
img_a = TMP / "example one.png"
img_a.write_bytes(PNG)
img_b = TMP / "second.JPG"
img_b.write_bytes(b"\xff\xd8\xff\xe0not-really-a-jpeg-but-bytes-are-bytes\xff\xd9")
not_image = TMP / "notes.txt"
not_image.write_text("hello", encoding="utf-8")

print("=== VERBATIM: the text comes back exactly ===")
TRICKY = ("\n\n  Create a premium [Active Volcano] poster.  \r\n"
          "Use \"quotes\", 'apostrophes' and — dashes, café, 漢字, \U0001F30B\r\n"
          "\ttab-indented line with trailing spaces   \n\n\n")
entry = sp.add("image", "Tricky one", TRICKY)
check("read() returns the identical string", sp.read(entry) == TRICKY)
check("the file on disk holds the identical bytes",
      raw(entry / sp.PROMPT_FILE) == TRICKY.encode("utf-8"))
check("CRLF line endings survive (not translated)", b"\r\n" in raw(entry / sp.PROMPT_FILE))
check("leading and trailing blank lines survive", sp.read(entry).startswith("\n\n")
      and sp.read(entry).endswith("\n\n\n"))

print()
print("=== EXAMPLE IMAGES: straight copies, original names ===")
entry2 = sp.add("image", "With images", "a prompt", [img_a, img_b])
pics = sp.images(entry2)
check("both images were saved with the prompt", [p.name for p in pics] == ["example one.png", "second.JPG"],
      str([p.name for p in pics]))
check("each image is a byte-for-byte copy",
      raw(entry2 / "example one.png") == PNG and raw(entry2 / "second.JPG") == raw(img_b))
check("the source images are left where they were", img_a.exists() and img_b.exists())
more = sp.attach(entry2, [img_a])
check("attaching a same-named image never overwrites - it gets -2",
      more[0].name == "example one-2.png" and raw(entry2 / "example one.png") == PNG, str(more))
check("prompt.txt is not listed as an image", all(p.suffix != ".txt" for p in sp.images(entry2)))
for label, call in (("a missing image", lambda: sp.attach(entry2, [TMP / "nope.png"])),
                    ("a non-image file", lambda: sp.attach(entry2, [not_image])),
                    ("a bad image on add", lambda: sp.add("image", "Bad", "text", [not_image]))):
    try:
        call()
        check("refuses " + label, False)
    except sp.PromptBankError:
        check("refuses " + label, True)
check("a refused add leaves no half-made folder", not (sp.kind_dir("image") / "Bad").exists())

print()
print("=== IMAGE ORDER AND IMAGE NAMES ===")
oe = sp.add("image", "Ordering", "text", [img_a, img_b])
img_c = TMP / "third.webp"
img_c.write_bytes(b"RIFF....WEBPfake")
sp.attach(oe, [img_c])
names = [x.name for x in sp.images(oe)]
check("never reordered: images are in name order", names == ["example one.png", "second.JPG", "third.webp"],
      str(names))
check("...and no order file exists yet", not (oe / sp.ORDER_FILE).exists())
sp.set_order(oe, ["third.webp", "example one.png", "second.JPG"])
check("set_order is what images() returns",
      [x.name for x in sp.images(oe)] == ["third.webp", "example one.png", "second.JPG"])
check("the order file is plain text, one name per line",
      (oe / sp.ORDER_FILE).read_text(encoding="utf-8") == "third.webp\nexample one.png\nsecond.JPG\n")
check("order.txt is never listed as an image", all(x.suffix != ".txt" for x in sp.images(oe)))
for label, bad in (("a missing image", ["third.webp", "example one.png"]),
                   ("an image twice", ["third.webp", "third.webp", "second.JPG"]),
                   ("an unknown name", ["third.webp", "example one.png", "nope.png"])):
    try:
        sp.set_order(oe, bad)
        check("a reorder refuses " + label, False)
    except sp.PromptBankError:
        check("a reorder refuses " + label, True)
new = sp.attach(oe, [img_a])[0]
check("a newly attached image joins at the END of a custom order",
      [x.name for x in sp.images(oe)][-1] == new.name, str([x.name for x in sp.images(oe)]))
(oe / "dropped in by hand.png").write_bytes(PNG)
check("an image added by hand (not in order.txt) still shows, at the end",
      [x.name for x in sp.images(oe)][-1] == "dropped in by hand.png")
renamed_img = sp.rename_image(oe / "example one.png", "Cover shot")
check("rename_image keeps the extension", renamed_img.name == "Cover shot.png", renamed_img.name)
check("...keeps the image's place in the order",
      [x.name for x in sp.images(oe)][1] == "Cover shot.png", str([x.name for x in sp.images(oe)]))
check("...and keeps its bytes", renamed_img.read_bytes() == PNG)
check("a typed extension is not applied (no fake .jpg)",
      sp.rename_image(renamed_img, "cover.jpg").name == "cover.png")
check("renaming onto a taken name never overwrites",
      sp.rename_image(oe / "dropped in by hand.png", "cover").name == "cover-2.png"
      and (oe / "cover.png").read_bytes() == PNG)
for label, call in (("an empty name", lambda: sp.rename_image(oe / "cover.png", " / ")),
                    ("a file that is not an image", lambda: sp.rename_image(oe / sp.PROMPT_FILE, "x"))):
    try:
        call()
        check("rename_image refuses " + label, False)
    except sp.PromptBankError:
        check("rename_image refuses " + label, True)
before = [x.name for x in sp.images(oe)]
sp.remove_image(oe / "third.webp")
check("removing an image keeps the rest of the order",
      [x.name for x in sp.images(oe)] == [n for n in before if n != "third.webp"])
check("the prompt text is untouched by all of it", sp.read(oe) == "text")

print()
print("=== NOTHING IS EVER OVERWRITTEN; KINDS STAY APART ===")
dup = sp.add("image", "Tricky one", "different text")
check("a taken title gets -2", dup.name == "Tricky one-2", dup.name)
check("...and the original is untouched", sp.read(entry) == TRICKY)
video = sp.add("video", "Tricky one", "a video prompt")
check("the same title in the other kind is its own prompt", video.parent.name == "video")
check("image list holds only image prompts",
      {r["title"] for r in sp.entries("image")} == {"Tricky one", "Tricky one-2", "With images", "Ordering"})
check("video list holds only video prompts", [r["title"] for r in sp.entries("video")] == ["Tricky one"])
check("entries report the image count",
      next(r for r in sp.entries("image") if r["title"] == "With images")["images"] == 3)

print()
print("=== TITLES, RENAME, DELETE ===")
check("a title is made file-safe but stays readable",
      sp.clean_title('Volcano: "cutaway" / poster?') == "Volcano cutaway poster", sp.clean_title('Volcano: "cutaway" / poster?'))
renamed = sp.rename(entry2, "Renamed with images")
check("rename keeps the text and every image",
      sp.read(renamed) == "a prompt" and len(sp.images(renamed)) == 3 and not entry2.exists())
check("renaming onto a taken title never overwrites",
      sp.rename(renamed, "Tricky one").name == "Tricky one-3")
for label, call in (("an empty prompt", lambda: sp.add("image", "x", "   \n\t ")),
                    ("an empty title", lambda: sp.add("image", " / ", "text")),
                    ("an unknown kind", lambda: sp.add("audio", "x", "text"))):
    try:
        call()
        check("refuses " + label, False)
    except sp.PromptBankError:
        check("refuses " + label, True)
try:
    sp.delete(TMP)
    check("delete refuses anything that is not a prompt folder", False)
except sp.PromptBankError:
    check("delete refuses anything that is not a prompt folder", True)
gone = sp.find("Tricky one-2", "image")
sp.delete(gone)
check("delete removes exactly that prompt", not gone.exists() and entry.exists())
check("find() searches both kinds", sp.find("Tricky one").parent.name in sp.KINDS)

print()
print("=== THE CLI SAVES EXACTLY TOO ===")
import io  # noqa: E402
src = TMP / "cli.txt"
src.write_bytes("line one  \r\nline two [x]\r\n".encode("utf-8"))
sp.main(["add", "--kind", "video", "--title", "From CLI", "--file", str(src), "--image", str(img_a)])
cli_entry = sp.find("From CLI", "video")
check("--file is stored byte for byte", raw(cli_entry / sp.PROMPT_FILE) == raw(src))
check("--image is stored with it", [p.name for p in sp.images(cli_entry)] == ["example one.png"])

print()
print("=== THE .EXE IN dist/ SHARES THE CHECKOUT'S BANK ===")
fake = TMP / "checkout"
build = fake / "dist" / "AI Video Studio"
build.mkdir(parents=True)
check("a build with no gui.py above it keeps its own bank",
      sp._default_bank_dir(build) == build / "temp" / "resources" / "prompt_bank")
(fake / "gui.py").write_text("", encoding="utf-8")
check("a build inside its checkout uses the checkout's bank",
      sp._default_bank_dir(build) == fake / "temp" / "resources" / "prompt_bank")
check("running from source uses the root's own bank",
      sp._default_bank_dir(fake) == fake / "temp" / "resources" / "prompt_bank")

print()
print("=== THE PROMPT BANK TAB ===")
from PyQt6.QtGui import QGuiApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication(sys.argv)
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import ThemeManager  # noqa: E402

win = MainWindow(ThemeManager(app))
win.show()
app.processEvents()
assistant = win.assistant_view if hasattr(win, "assistant_view") else None
if assistant is None:
    assistant = next(w for w in win.findChildren(type(win.brief_view.parent().parent()))
                     if hasattr(w, "prompt_bank"))
tab_names = [assistant.tabs.tabText(i) for i in range(assistant.tabs.count())]
check("Assistant has a Prompt Bank tab", "Prompt Bank" in tab_names, str(tab_names))
check("...and no Anatomy tab any more", "Anatomy" not in tab_names, str(tab_names))
bank = assistant.prompt_bank
check("Prompt Bank splits into Image and Video",
      [bank.tabs.tabText(i) for i in range(bank.tabs.count())] == ["Image prompts", "Video prompts"])

view = bank.image
view.reload()
check("the Image list shows the saved image prompts", view.list.count() == len(sp.entries("image")))
path = view.add_prompt("Added in the app", TRICKY, [str(img_a)])
app.processEvents()
check("Add saves verbatim and selects it", path is not None and view.selected_path() == str(path)
      and sp.read(path) == TRICKY)
check("the viewer shows the text", view.viewer.toPlainText().strip().startswith("Create a premium"))
check("the example image is shown as a thumbnail", view.thumbs.count() == 1)
view.copy_selected()
check("Copy puts the exact saved text on the clipboard",
      QGuiApplication.clipboard().text().replace("\r\n", "\n") == TRICKY.replace("\r\n", "\n"))
view.attach_images([str(img_b)])
app.processEvents()
check("Add images attaches to the selected prompt", view.thumbs.count() == 2
      and len(sp.images(path)) == 2)
check("the thumbnails can be dragged (internal move)",
      view.thumbs.dragDropMode() == view.thumbs.DragDropMode.InternalMove)
order_before = view.thumbs.names()
view.thumbs.setCurrentRow(0)
view.thumbs.move_item(0, 1)
app.processEvents()
check("a drag-reorder is saved to disk straight away",
      [x.name for x in sp.images(path)] == list(reversed(order_before)), str(sp.images(path)))
view.reload(select_path=path)
check("...and survives a reload", view.thumbs.names() == list(reversed(order_before)))
print()
print("=== DRAG-AND-DROP: a dropped thumbnail never disappears ===")
# The reported bug: drop a thumbnail in some spots and it vanished. The drop
# handler reported MoveAction back to Qt, and Qt's drag code then "finished
# the move" by deleting the selected item - the one just dropped. A real OS
# drag cannot be driven offscreen, so the drop is delivered directly, and the
# thing that caused the bug is what gets checked: the action handed back.
from PyQt6.QtCore import QPointF, Qt as _Qt  # noqa: E402

view.attach_images([str(img_c)])          # three thumbnails now
app.processEvents()
thumbs = view.thumbs


class FakeDrop:
    def __init__(self, x):
        self._pos = QPointF(x, 20)
        self.action = None
        self.accepted = False

    def source(self):
        return thumbs

    def position(self):
        return self._pos

    def setDropAction(self, action):
        self.action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def drop(source_row, x):
    thumbs.setCurrentRow(source_row)
    event = FakeDrop(x)
    thumbs.dropEvent(event)
    app.processEvents()
    return event


def rect(row):
    return thumbs.visualItemRect(thumbs.item(row))


names0 = thumbs.names()
far_right = rect(thumbs.count() - 1).right() + 200   # empty space after the last thumbnail
ev = drop(0, far_right)
check("the drop is never handed back to Qt as a move (the vanishing bug)",
      ev.accepted and ev.action == _Qt.DropAction.IgnoreAction, str(ev.action))
check("dropping in the empty space on the right moves it to the END, and keeps all of them",
      thumbs.names() == names0[1:] + names0[:1], str(thumbs.names()))
check("...and the order on disk matches", [x.name for x in sp.images(path)] == thumbs.names())
names1 = thumbs.names()
drop(2, rect(0).left() - 2)
check("dropping before the first thumbnail moves it to the START",
      thumbs.names() == names1[2:] + names1[:2], str(thumbs.names()))
names2 = thumbs.names()
gap = (rect(0).right() + rect(1).left()) // 2
drop(2, gap)
check("dropping in the GAP between two thumbnails lands it in that gap",
      thumbs.names() == [names2[0], names2[2], names2[1]], str(thumbs.names()))
names3 = thumbs.names()
drop(0, rect(2).center().x())
check("dropping ONTO another thumbnail SWAPS the two (moving right); the middle one stays",
      thumbs.names() == [names3[2], names3[1], names3[0]], str(thumbs.names()))
check("...and the swap is saved to disk", [x.name for x in sp.images(path)] == thumbs.names())
names4 = thumbs.names()
drop(2, rect(1).center().x())
check("dropping ONTO another thumbnail SWAPS the two (moving left)",
      thumbs.names() == [names4[0], names4[2], names4[1]], str(thumbs.names()))
names5 = thumbs.names()
drop(1, rect(0).left() + 4)
check("...even when dropped near that thumbnail's left edge, not only its centre",
      thumbs.names() == [names5[1], names5[0], names5[2]], str(thumbs.names()))
check("the swapped-in thumbnail is the selected one", thumbs.currentRow() == 0)
names3 = thumbs.names()
drop(1, rect(1).center().x())
check("dropping a thumbnail onto itself changes nothing and loses nothing",
      thumbs.names() == names3 and thumbs.count() == 3)
check("every image file is still there after all the drags", len(sp.images(path)) == 3)

first = view.thumbs.names()[0]
renamed_thumb = view.rename_image(first, "Hero example")
app.processEvents()
check("rename from the tab renames the file and keeps its place",
      renamed_thumb is not None and view.thumbs.names()[0] == renamed_thumb.name
      and renamed_thumb.name.startswith("Hero example"), str(view.thumbs.names()))
check("...and the label under the thumbnail shows the new name",
      view.thumbs.item(0).text() == "Hero example")
check("an empty prompt is refused in the app too", view.add_prompt("Empty", "  ") is None)

original_question = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
view.delete_selected()
check("Delete does nothing when you say No", path.exists())
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
view.delete_selected()
QMessageBox.question = original_question
check("Delete removes it when you confirm", not path.exists())

sp.add("video", "Saved from outside", "added by Claude while the app is open")
bank.tabs.setCurrentIndex(1)
app.processEvents()
check("switching tab picks up prompts saved from outside the app",
      any(bank.video.list.item(i).data(0x0100).endswith("Saved from outside")
          for i in range(bank.video.list.count())))

win.close()
shutil.rmtree(TMP, ignore_errors=True)

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL PROMPT BANK CHECKS PASSED")
