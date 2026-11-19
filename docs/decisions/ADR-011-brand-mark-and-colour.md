# ADR-011: The Adle mark and the brand colour

- **Status:** Accepted. Supersedes the brand rows of ADR-006 (the rest of ADR-006 stands).
- **Date:** 2026-11-19

## Context

The owner supplied a logo: the letters "a" and "d" as two interlocking rings, navy and teal, on a
light backdrop (`apps/desktop/assets/brand/adle-logo.png`). Until then the app carried a
placeholder mark (a sprout on a green tile) and a green brand colour chosen with it.

A teal and navy mark beside green buttons and green selection would look like two products.

## Decisions

### The mark is drawn as vectors, from the artwork's own geometry

- `mark.svg` redraws the artwork on its 1280 grid: two rings of outer radius 240 and stroke 90
  whose centres are one radius apart, and a stem with a round cap. The "a" is its ring minus the
  whole disc of the "d", which is what makes the rings read as linked.
- `npm run icons:verify` renders the vectors over the artwork's backdrop and compares the two
  pixel by pixel. They differ on 0.014% of pixels, all on anti-aliased edges.
- The `Logo` component draws the same shapes at one tenth scale, in tokens rather than fixed
  colours, so the mark follows the theme.

### The brand colour is the teal of the mark

| Token | Was (light / dark) | Is (light / dark) |
|---|---|---|
| `primary` | `#269B62` / `#3DBE7F` | `#167D8D` / `#3FB4C5` |
| `primary-soft` | `#E2F4E9` / `#1C3327` | `#DFF1F3` / `#16323A` |
| `primary-text` | `#1B7549` / `#6AD3A0` | `#0F6672` / `#6FD1DD` |
| `action` | `#1F8352` / `#4CC78C` | `#167D8D` / `#4CC0D0` |
| `action-hover` | `#186B43` / `#63D39D` | `#116876` / `#66CDDB` |
| `action-pressed` | `#135636` / `#7BDCAE` | `#0D545F` / `#80D9E5` |
| `on-action` | `#FFFFFF` / `#0C1410` | `#FFFFFF` / `#06161A` |

- The light `primary` and `action` are the artwork's teal exactly (`#167D8D`): white on it is
  4.83:1, so no darker variant is needed for filled buttons.
- `primary-text` is a deeper teal so that it also reads on `primary-soft` (5.7:1).
- The dark theme uses a lighter teal with dark labels, as it did with green.
- Every pair is checked by `tokens.test.ts` in both themes.

### Success keeps its green

Green used to mean both "this is Adle" and "this went well". They are now separate:
`success`, `success-soft`, and `success-text` carry the old green values and are used by the
success `Badge`, `Callout`, and toast, and by the "local service ready" dot. A learner's
"Demonstrated for now" badge is therefore green, and the button beside it is teal.

### The mark's dark letter has its own token

`brand-ink` is the artwork's navy (`#071B2B`) on light surfaces and the dark theme's ink on dark
ones. Only the logo uses it. Body text keeps `ink`; the two are both near-black and are not
meant to be compared.

### Scenes are not repainted

The scene palette's `green` now mirrors `success` instead of `primary`, with the same values, so
no scene file, example, or prompt changed. Scenes have their own small palette for telling
things apart inside a picture; they do not need to carry the brand.

### Icons are rendered from the vectors, by Electron

`npm run icons` draws the mark on a rounded tile of the artwork's backdrop colour (`#EEEEEE`) and
writes `apps/desktop/assets/icons/icon.ico` (16 to 256 px), `icon.png` (512), and `icon-1024.png`.
The outputs are committed. No image library was added: Electron, already a dependency, does the
drawing in an offscreen window, and an `.ico` is a short directory in front of PNG files.

The window takes its icon from these files on Windows and Linux. Packaging (M8) will use the same
files for the installer and the macOS bundle.

## Consequences

- One visual identity: the mark, primary buttons, selection, focusable brand accents, and
  progress share a colour.
- The neutral colours (canvas, surfaces, borders, text) are unchanged. They are very slightly
  green-grey; next to teal this reads as neutral. Re-tinting them would change every scene file
  for a difference few would notice.
- The design system keeps its name, Sprout. It is an internal name and nothing a learner sees.
- To go back to green, restore the seven values in the table: nothing else depends on the hue.

## Not decided here

A wordmark typeface (the app sets "Adle" in Inter beside the mark), installer artwork, and the
macOS `.icns` (generated at packaging time, M8).
