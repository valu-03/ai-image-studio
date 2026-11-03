# AI Image Studio — Brand & Logo Guidelines

## 1. The Logo & Visual Concept

**Concept: Off-Centre Frame**

The identity directly embodies AI Image Studio's core aesthetic philosophy: overcoming the artificial, dead-centre, staged tell of generative AI through **candid asymmetry, rule-of-thirds composition, and authentic photographic realism**.

Four precise viewfinder corner brackets frame an intentionally off-centre subject focal dot placed at the upper-right rule-of-thirds intersection (148, 108). All corners are exact circular arcs and right angles.

| Master File | Format | Optimal Use |
|---|---|---|
| `ai-image-studio-symbol.svg` | Vector | App icon, avatar, compact UI badge (regular cut) |
| `ai-image-studio-symbol-small.svg` | Vector | 16–32 px display sizes (favicons, browser tabs, OS taskbars) |
| `ai-image-studio-symbol-reversed.svg` | Vector | Dark UI surfaces & darkroom mode (thinned ~4% for irradiation balance) |
| `ai-image-studio-horizontal.svg` | Vector | Default header lockup on light backgrounds |
| `ai-image-studio-horizontal-reversed.svg` | Vector | Default header lockup on darkroom / dark surfaces |
| `ai-image-studio-stacked.svg` | Vector | Centred editorial, splash screens, documentation covers |
| `ai-image-studio-stacked-reversed.svg` | Vector | Centred lockup on dark ground |
| `ai-image-studio-wordmark.svg` | Vector | Text-only brand placement |
| `export/` | Vector & Raster | Favicon pack (`.ico`, `.svg`), PWA manifest, iOS touch icons, 1-color variants |

All master assets are generated deterministically by `python assets/logo/build_logo.py`. Always edit the parametric construction script rather than hand-modifying SVG outputs.

---

## 2. Clear Space & Minimum Sizes

- **Clear Space**: Maintain a minimum clear space equal to the stroke thickness of the viewfinder brackets (**28 units on the 256 grid**, ≈ 11% of the mark's height). No text, borders, or interface elements may encroach within this perimeter.
- **Minimum Digital Sizes**:
  - Regular symbol: 32 × 32 px.
  - Small cut (`ai-image-studio-symbol-small.svg`): 16 × 16 px to 32 × 32 px.
  - Horizontal lockup: Minimum width of 140 px. Below 140 px, display the symbol alone.
- **Minimum Print Sizes**:
  - Symbol: 6 mm (0.25 in).
  - Horizontal lockup: 25 mm (1.0 in).

---

## 3. Brand Color Palette

| Color | Hex | RGB | Purpose & Role |
|---|---|---|---|
| **Darkroom Charcoal** | `#141413` | `20, 20, 19` | Primary ground, darkroom surface, light-mode mark paint |
| **Safelight Gold / Amber** | `#F5C451` | `245, 196, 81` | Accent color, focal point, dark-mode reversed mark paint |
| **Ground Hairline** | `#262624` | `38, 38, 36` | Subtle dividers, border containers, framing elements |
| **Pure White** | `#FFFFFF` | `255, 255, 255` | High-contrast single-color print, laser engraving, inverted masks |

### Contrast & Accessibility
- Safelight Gold (`#F5C451`) against Charcoal (`#141413`) yields a contrast ratio of **12.8:1**, easily exceeding WCAG AAA compliance (7.0:1) for both text and icons.

---

## 4. Typography

- **Wordmark Font**: **Inter-SemiBold** (OFL). Outlined to pure bezier vectors via `fontTools` so no font files or runtime type rendering are required.
- **Tracking & Proportion**: Standardized x-height matched to the viewfinder baseline; uppercase "AI" balances the title-cased "Image Studio".
- **Interface UI Pairing**: **Inter** (regular, medium, semibold) for UI labels, combined with **JetBrains Mono** or system monospace for prompt tokens and realism cues.

---

## 5. Usage Rules & Don'ts

- **Do Not** center the focal dot inside the brackets. The intentional off-centre placement is the signature of photographic realism.
- **Do Not** distort, stretch, skew, or flip the mark (flipping inverts the rule-of-thirds composition).
- **Do Not** apply drop shadows, 3D skeuomorphism, neon outer glows, or arbitrary gradients.
- **Do Not** retype the wordmark using a non-approved font; always use the vector outlines generated in `build_logo.py`.
- **Do Not** place the dark charcoal logo directly on a dark background; use the reversed Safelight Gold (`#F5C451`) or pure white variant.
