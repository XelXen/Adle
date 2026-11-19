# ADR-006: Sprout tokens, adjusted for contrast, with one theming mechanism

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

PLAN.md §4.2 gives starting colour tokens and asks that any intentional change be documented, that
the dark theme be designed rather than inverted, and that contrast be accessible.

## Decision

### Changes to the starting palette

Measured against WCAG 2.2 AA (4.5:1 for text, 3:1 for UI boundaries):

| Token | Plan value | Adopted | Reason |
|---|---|---|---|
| `muted` | `#69786F` | `#5F6E65` | 4.34:1 on the canvas; the adopted value is 5.0:1. |
| Filled action background | `primary` `#269B62` | new `action` `#1F8352` | White on `primary` is 3.5:1. `#1F8352` (the plan's hover value) is 4.7:1. Hover and pressed go darker (`#186B43`, `#135636`). |
| `primary` | `#269B62` | unchanged | Still the brand colour for progress, selection, and marks, where 3:1 applies. |
| Control borders | `border` `#DCE5DC` | new `border-strong` `#7F9084` | Input and switch boundaries need 3:1; hairlines keep `border`. |
| Text on tinted surfaces | accents | new `*-text` tokens | The accent hues themselves are too light for text. Each has a darker text companion and a `*-soft` background. |
| Focus | — | new `focus` `#1F6FD6` | Blue, so the ring is visible on green buttons and distinct from error red. |

All other plan values are used as given.

### Dark theme

Deep forest surfaces (`#101713`, `#18211C`, `#1F2A24`), near-white ink (`#E7EFE9`), brightened
accents. Filled actions invert their logic: a bright fill (`#4CC78C`) with dark text, because a
dark-green button on a dark surface would not read as primary. Shadows give way to borders.

### One mechanism

- Tokens are CSS custom properties in `packages/design-system/src/styles/tokens.css`: light in
  `:root`, dark in `@media (prefers-color-scheme: dark)`.
- The learner's choice (system / light / dark) is stored by the main process (`ui-state.json`) and
  applied with `nativeTheme.themeSource` **before the window is created**. Chromium then reports
  the matching `prefers-color-scheme` to the renderer and to player frames. No `data-theme`
  attribute, no flash of the wrong theme, nothing in web storage.
- Scenes cannot read CSS. `scene-palette.ts` mirrors eight tokens per theme for them; the player
  passes the theme and supplies the stage background.

### Guards

`packages/design-system/src/tokens.test.ts` fails the build if: a contrast pair drops below its
threshold in either theme; the dark theme omits a colour; the scene palette drifts from the tokens;
or any component stylesheet contains a raw colour.

## Consequences

- Two more colour families than the plan listed (`action`, `*-text`/`*-soft`), each with a stated
  job. DESIGN_SYSTEM.md documents when to use which.
- End-to-end tests set the theme through the app's saved preference rather than emulating the
  media query, so they exercise the real path.
