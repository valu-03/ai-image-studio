---
name: AI Image Studio
description: A dark-first PyQt6 workspace for composing, scoring and generating photorealistic avatar prompts.
colors:
  bg: "#0B0E14"
  surface: "#151A24"
  surface-variant: "#1B2230"
  surface-variant-high: "#232C3D"
  outline-variant: "#1A2333"
  outline: "#2A3648"
  outline-strong: "#64748B"
  text: "#F8FAFC"
  text-muted: "#94A3B8"
  primary: "#38BDF8"
  primary-container: "#0EA5E9"
  primary-fixed: "#16344A"
  on-primary: "#061018"
  success: "#34D399"
  warning: "#FBBF24"
  error: "#F87171"
  accent2: "#8B5CF6"
  light-bg: "#F7F9FC"
  light-surface: "#FFFFFF"
  light-text-muted: "#5B6B80"
  light-primary: "#0369A1"
  light-success: "#047857"
typography:
  hero: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "32px", fontWeight: 750}
  display: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "26px", fontWeight: 700}
  headline: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "19px", fontWeight: 650}
  title: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "15px", fontWeight: 600}
  body: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "14px", fontWeight: 400}
  body-sm: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "13px", fontWeight: 400}
  label: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "12px", fontWeight: 600}
  tab: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "12px", fontWeight: 600}
  caption: {fontFamily: "Inter, Segoe UI Variable, Segoe UI, system-ui, sans-serif", fontSize: "11px", fontWeight: 500}
  mono: {fontFamily: "JetBrains Mono, Cascadia Mono, Consolas, monospace", fontSize: "13px", fontWeight: 400}
rounded:
  sm: "4px"
  md: "8px"
  card: "12px"
  xl: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "40px"
components:
  button: {backgroundColor: "{colors.surface-variant}", textColor: "{colors.text}", rounded: "{rounded.md}", padding: "8px 16px", typography: "{typography.body-sm}"}
  button-primary: {backgroundColor: "{colors.primary}", textColor: "{colors.on-primary}", rounded: "{rounded.md}", padding: "8px 16px"}
  button-danger: {backgroundColor: "transparent", textColor: "{colors.error}", rounded: "{rounded.md}"}
  card: {backgroundColor: "{colors.surface}", rounded: "{rounded.card}", padding: "20px"}
  input: {backgroundColor: "{colors.surface-variant}", textColor: "{colors.text}", rounded: "{rounded.md}", padding: "8px"}
  badge: {textColor: "{colors.on-primary}", rounded: "{rounded.pill}", padding: "4px 16px", typography: "{typography.label}"}
  tab: {textColor: "{colors.text-muted}", typography: "{typography.tab}", padding: "8px 12px"}
  nav-item-checked: {backgroundColor: "{colors.primary-fixed}", textColor: "{colors.primary}", rounded: "{rounded.md}"}
---

# AI Image Studio design system

**Source of truth:** `ui/tokens.py` (values) and `ui/theme.py` `build_qss()` (how they are applied).
This file describes them; when the two disagree, the code wins and this file is stale. The binding
contract above both is `pyqt6_system_prompt.md`.

## Overview

An Operate-mode desktop tool: people come to finish a task (compose a prompt, score it, generate,
rate), so clarity, consistency and density beat expression. The look is a dark, cool slate
workspace with one sky-blue accent. A sky-to-violet gradient is reserved for the one primary
action of a view, and soft card shadows carry the depth. Light mode is derived from the dark
palette and is a full equal, not an afterthought.

## Colors

- **Dark (the default) is mandated** by `pyqt6_system_prompt.md` §2:
  - bg `#0B0E14`, surface `#151A24`, accent `#38BDF8`, success `#34D399`, border `#1A2333`,
    text `#F8FAFC`, muted `#94A3B8`.
  - The rest are derived tokens.
- **Light** has its own tuned values (`LIGHT` in tokens.py):
  - accent `#0369A1`, success `#047857`, muted `#5B6B80`;
  - each clears WCAG AA on the ground it is drawn on.
- **Accent use:** primary actions, the current selection and state indicators only, never
  decoration.
- **Status colours:** success, warning and error mean pass, caution and fail. Each is paired
  with a word or a mark (OK, !, ✓, ✕), never colour alone.
- **Contrast is tested:** `tests/test_design_tokens.py` requires ≥4.5:1 for every text pair and
  ≥3:1 for control edges (`outline-strong`), in both palettes.
- **No colour literals in widget code.** Use the palette dict, `theme.color(name)`,
  `theme.token_color(palette, name)` or `theme.hex_of(name)`. The token test fails on any
  `#RRGGBB` in `ui/` outside tokens.py.

## Typography

- **Inter** for all UI text and **JetBrains Mono** for prompts and code-like fields. Both are
  bundled in `assets/fonts` (SIL OFL) and loaded by `theme.load_fonts()`, so every machine
  renders the same face.
- **One family carries everything,** at a tight product scale:
  - hero 32, display 26, headline 19 and title 15;
  - body 14, body-sm 13 and label/tab 12;
  - caption 11, for fine print only, never for navigation.
- **Text size:** Settings > Appearance > Text size (100 / 115 / 130%) multiplies every size
  through `build_qss(c, scale)`. Never hard-code a font size in a view.

## Layout

- **Structure:** a 212px left rail, a 60px top bar and a `QStackedWidget` canvas with 24px padding.
- **Spacing:** a strict 4px grid (`SPACE`); card padding 20; column gap 16.
- **Window size:** minimum 1100×700 (it must fit a 1366×768 laptop); default 1440×900.
- **Splitters:** multi-column views use a `QSplitter` with an `objectName`, so the user's sizes are
  saved. Rename a splitter (`…_v2`) when its limits change, or the old saved state comes back.
- **Compose:**
  - form ≤380, prompt flexible, result ≤380;
  - spare width is shared 1:3:1;
  - at the default size the spec form must not scroll sideways.
- **Scroll areas:** never `ScrollBarAlwaysOff` on a resizable one, because it clips silently.
  `tests/test_layout.py` checks overlap, clipping, crushing and spill at the minimum and default
  sizes in both themes.

## Elevation & Depth

Depth comes from soft, offset shadows (`elevate`) on cards and an animated shadow lift on
hoverable result cards (`hover_elevate`). The checked rail item carries an accent glow
(`glow_primary`). With "Reduce motion" on, hover lifts and the pulse stop moving; the end state
still shows.

## Shapes

- **Radii:** cards 12; buttons and inputs 8; small controls 4; badges and chips are pills.
- **Borders:** 1px, `outline-variant` for structure, `outline-strong` where a control's edge must
  be findable (checkboxes, the credits button).

## Components

- **Buttons:** default (surface-variant), `primary` (gradient, one per view), `ghost` (quiet
  secondary), `danger` (error outline, fills on hover with on-primary text) and `chip` (pill toggle).
  - Every button has hover, pressed, focus (accent edge) and disabled states.
- **Badges** (`Badge`, read-only) and **BadgeButton** (pressable, focusable, e.g. the credits
  balance):
  - statuses neutral, quiet, success, warning, danger and accent;
  - "quiet" (outlined) is for states that are not news, like idle.
- **Tabs:** 12px labels, never elided; a bar too narrow scrolls (`widgets.readable_tabs`).
- **Empty lists** say what goes there and how to fill it (`widgets.set_empty_hint`): an icon plus
  one line, centred, with the icon dropped when the list is short.
- **Status bar:** one line via `widgets.status_line`, which turns paths into file names and links
  into site names. The full message goes on the bar's tooltip.
  - Multi-line failures go through `MainWindow.report_failure`, which opens a box.
- **Accessibility:** `widgets.name_controls` gives every unnamed control an accessible name, from
  its label, then its tooltip, then its card title, then its placeholder.
  - Name a control explicitly with `setAccessibleName` when none of those describe it well.

## Do's and Don'ts

- **Do** read colours from tokens and sizes from `TYPO` and `SPACE`.
- **Do** give every new list an empty hint, every icon-only button a tooltip or accessible name,
  and every long action a busy state and a Cancel.
- **Do** run `python tests/screenshot_all.py <dir>` before and after a UI change, and look at both
  themes at the minimum size.
- **Don't** elide tab labels, hide a horizontal overflow behind `ScrollBarAlwaysOff`, or put more
  than one gradient (primary) button in a view.
- **Don't** use colour as the only signal, or the 11px caption for anything a user must read to
  act.
- **Don't** move domain logic into `ui/`; the GUI calls `tools/`.
