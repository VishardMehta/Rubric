---
version: 1.0
name: Rubric-design-system
description: >
  A calm, light, instrument-grade interface for high-stakes hiring decisions.
  Warm near-white canvas, near-black ink, hairline borders, and a single indigo
  accent reserved exclusively for interactive and brand use. Semantic color is
  a set of exactly three muted tones (positive, caution, negative) that appear
  only as low-saturation score tints, never as saturated badges. Typography is
  Inter with tabular figures on every number, carrying the hierarchy that
  decoration is not allowed to carry. Two shells: a dense sidebar application
  for HR, and a chrome-free centered flow for candidates.

colors:
  # Brand and interaction. Never used to mean good or bad.
  accent: "#4F46E5"
  accent-hover: "#4338CA"
  accent-pressed: "#3730A3"
  accent-tint: "#EEF0FE"
  accent-ring: "#A5B0F5"
  on-accent: "#FFFFFF"

  # Surfaces
  canvas: "#FAFAF9"
  surface: "#FFFFFF"
  surface-sunken: "#F5F5F4"
  surface-hover: "#F7F7F6"
  overlay-scrim: "rgba(26, 26, 25, 0.32)"

  # Ink
  ink: "#1A1A19"
  ink-secondary: "#6B6B68"
  ink-tertiary: "#9A9A96"
  ink-disabled: "#BDBDB9"
  on-dark: "#FFFFFF"

  # Borders
  hairline: "#E8E8E5"
  hairline-strong: "#D6D6D2"
  hairline-focus: "#4F46E5"

  # Semantic. Score meaning only. Never decoration, never brand.
  positive: "#1E7B4D"
  positive-tint: "#EDF7F1"
  caution: "#8A5A00"
  caution-tint: "#FBF5E8"
  negative: "#A93226"
  negative-tint: "#FBF0EE"

  # Live recording. Distinct from negative so a recording dot never reads as an error.
  live: "#D1453B"
  live-tint: "#FDF1F0"

typography:
  display:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 44px
    fontWeight: 600
    lineHeight: 1.10
    letterSpacing: -0.02em
  title-1:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.02em
  title-2:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.20
    letterSpacing: -0.015em
  title-3:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 19px
    fontWeight: 600
    lineHeight: 1.30
    letterSpacing: -0.01em
  body-lg:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: -0.005em
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  body-strong:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.55
    letterSpacing: 0
  caption:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.40
    letterSpacing: 0.06em
    textTransform: uppercase
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: 0

  # Numbers only. Always tabular so score columns never jitter.
  score-hero:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.0
    letterSpacing: -0.03em
    fontVariantNumeric: tabular-nums
  score-large:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.0
    letterSpacing: -0.02em
    fontVariantNumeric: tabular-nums
  score-inline:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
    fontVariantNumeric: tabular-nums

spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 20px
  6: 24px
  8: 32px
  10: 40px
  12: 48px
  16: 64px
  20: 80px
  24: 96px

rounded:
  sm: 6px
  md: 10px
  lg: 14px
  xl: 20px
  pill: 9999px

shadow:
  none: "none"
  sm: "0 1px 2px rgba(26,26,25,0.04), 0 1px 3px rgba(26,26,25,0.06)"
  md: "0 4px 12px rgba(26,26,25,0.08)"
  lg: "0 12px 32px rgba(26,26,25,0.12)"

motion:
  duration-fast: 120ms
  duration-base: 200ms
  duration-slow: 320ms
  ease-standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  ease-entrance: "cubic-bezier(0.2, 0, 0, 1)"
  ease-exit: "cubic-bezier(0.4, 0, 1, 1)"

layout:
  hr-sidebar-width: 240px
  hr-sidebar-compact: 64px
  hr-content-max: 1280px
  candidate-content-max: 640px
  landing-content-max: 1080px
  gutter-wide: 48px
  gutter-medium: 32px
  gutter-compact: 20px

breakpoints:
  compact: "max-width: 767px"
  medium: "768px to 1179px"
  wide: "min-width: 1180px"
---

# Rubric design tokens

This file is the token source of truth. `docs/design-system.md` explains how to
apply them. Where the two disagree, this file wins for values and the design
system wins for behavior.

## Non-negotiables

1. **Light only.** No dark mode. No `prefers-color-scheme` branch. Every value
   above is a light-mode value and there is no counterpart.

2. **`accent` never means good or bad.** It is brand and interaction only:
   primary buttons, links, focus rings, active nav, the logo. A score is never
   indigo. An indigo element is never a status.

3. **Semantic color is exactly three tones.** `positive`, `caution`, `negative`.
   There is deliberately no `info` color, because an info blue would compete
   with the accent. Informational content uses `ink-secondary` on
   `surface-sunken` instead.

4. **Semantic tints are backgrounds, semantic tones are text.** Never fill an
   element with `positive` at full saturation. `positive-tint` behind
   `positive` text is the only combination allowed for score chips.

5. **`live` is not `negative`.** The recording indicator uses `live` so that a
   candidate mid-answer never sees the same red the interface uses for failure.

6. **Every number renders with `font-variant-numeric: tabular-nums`.** Scores,
   counts, durations, dates. A column of scores that shifts horizontally as
   digits change looks broken.

7. **Default elevation is none.** Reach for `hairline` before `shadow-sm`.
   `shadow-md` is for popovers and dropdowns. `shadow-lg` is for modals only.

## Font loading

Inter, self-hosted, subset to latin. Weights 400, 500, 600 only. Do not load
700 or above; hierarchy comes from size and color, not from heavier weight.

```css
font-feature-settings: "cv11", "ss01";
font-variant-numeric: tabular-nums;
```

`cv11` gives Inter the single-storey lowercase g, which reads closer to a
system font. Apply `tabular-nums` globally and override to `normal` only in
long prose where proportional figures read better.

## Contrast floors

| Pair | Ratio | Use |
|---|---|---|
| `ink` on `surface` | 15.8:1 | Body and headings |
| `ink-secondary` on `surface` | 5.3:1 | Secondary text, labels |
| `ink-tertiary` on `surface` | 2.9:1 | Decorative only. Never for text that carries meaning. |
| `on-accent` on `accent` | 5.4:1 | Primary buttons |
| `positive` on `positive-tint` | 5.1:1 | Score chips |
| `caution` on `caution-tint` | 5.6:1 | Score chips |
| `negative` on `negative-tint` | 5.4:1 | Score chips |

`ink-tertiary` fails AA for body text. It exists for separators, disabled
glyphs and placeholder icons. If a string matters, it does not get
`ink-tertiary`.
