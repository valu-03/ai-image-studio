"""Design-token gate: colour comes from tokens.py only, and the palettes stay legible.

Two things that used to be judged by eye:
  1. No widget code names a colour. A literal "#34D399" beside a palette lookup
     is a dark-theme colour waiting to show up in light mode; ui/ reads every
     colour from ui/tokens.py through the palette or theme.color().
  2. Every text-on-ground pair the stylesheet draws clears WCAG AA (4.5:1 for
     text, 3:1 for a control's edge) in BOTH palettes - computed, not guessed.
Plus: the bundled fonts load, and the text-size setting really scales the sheet.
"""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import tokens as T  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


print("--- no colour literal outside tokens.py ---")
literal = re.compile(r"#[0-9A-Fa-f]{6}\b|QColor\(\s*\d+\s*,\s*\d+\s*,\s*\d+")
found = []
for path in sorted((ROOT / "ui").rglob("*.py")):
    if path.name == "tokens.py":
        continue
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # A neutral black shadow (QColor(0, 0, 0, a)) is not a palette colour.
        if literal.search(line) and "QColor(0, 0, 0" not in line:
            found.append("{}:{}".format(path.relative_to(ROOT), number))
check("ui/ names no colour of its own", not found, ", ".join(found[:8]))

print("--- contrast, both palettes ---")
TEXT = [("text", "bg"), ("text", "surface"), ("text", "surface_variant"),
        ("text_muted", "bg"), ("text_muted", "surface"), ("text_muted", "surface_variant"),
        ("primary", "surface"), ("primary", "primary_fixed"), ("on_primary", "primary"),
        ("on_primary", "text_muted"), ("on_primary", "success"), ("on_primary", "warning"),
        ("on_primary", "error"), ("error", "surface"), ("success", "surface"), ("warning", "surface")]
EDGES = [("outline_strong", "surface"), ("primary", "surface_variant")]
for name, palette in T.PALETTES.items():
    weak = ["{} on {} {:.2f}".format(fg, bg, contrast(palette[fg], palette[bg]))
            for fg, bg in TEXT if contrast(palette[fg], palette[bg]) < 4.5]
    check("{}: every text pair is at least 4.5:1".format(name), not weak, "; ".join(weak))
    faint = ["{} on {} {:.2f}".format(fg, bg, contrast(palette[fg], palette[bg]))
             for fg, bg in EDGES if contrast(palette[fg], palette[bg]) < 3.0]
    check("{}: control edges are at least 3:1".format(name), not faint, "; ".join(faint))
    check("{}: both palettes name the same tokens".format(name), set(palette) == set(T.DARK),
          str(sorted(set(T.DARK) ^ set(palette))))

print("--- the mandated dark palette is untouched ---")
MANDATED = {"bg": "#0B0E14", "surface": "#151A24", "primary": "#38BDF8", "success": "#34D399",
            "outline_variant": "#1A2333", "text": "#F8FAFC", "text_muted": "#94A3B8"}
check("pyqt6_system_prompt.md section 2 colours", all(T.DARK[k] == v for k, v in MANDATED.items()))

print("--- fonts and text size ---")
from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from ui.theme import ThemeManager, build_qss  # noqa: E402

theme = ThemeManager(app)
families = set(QFontDatabase.families())
check("Inter is bundled and loaded", "Inter" in families)
check("JetBrains Mono is bundled and loaded", "JetBrains Mono" in families)
check("every bundled font file exists", all((ROOT / "assets" / "fonts" / f).is_file() for f in T.FONT_FILES))
base, big = build_qss(T.DARK), build_qss(T.DARK, 1.3)
size = lambda sheet, px: "font-size: {}px".format(px) in sheet  # noqa: E731
check("the sheet uses the body size at 100%", size(base, T.TYPO["body"][0]))
check("the sheet scales the body size at 130%", size(big, round(T.TYPO["body"][0] * 1.3)))
theme.set_text_scale(1.15)
check("set_text_scale snaps and remembers", theme.text_scale == 1.15)
theme.set_text_scale(9)
check("an out-of-range scale snaps to the largest step", theme.text_scale == max(T.TEXT_SCALES))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL DESIGN TOKEN CHECKS PASSED")
