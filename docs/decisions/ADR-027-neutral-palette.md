# ADR-027: Sprout's third palette: neutral grounds, a darker dark, one deep action

- **Status:** Accepted
- **Date:** 2026-11-20
- **Supersedes:** the colour values of ADR-022 (its structure stands: three grounds, two
  voices, the radii, the rail)

## Context

The owner looked at the second edition (ADR-022) with Geist (ADR-025) and said the palette
could be better, "especially for dark mode which should be even darker and should have a more
neutralish dark primary bg color".

Three things in it worked against a calm, professional look:

- Every grey carried a green tint (`#0C100E`, `#111614`, `#171D1A` in the dark theme), so the
  dark theme read as dark green rather than dark.
- The filled action was a bright cyan block with dark text in the dark theme: the loudest
  thing on every screen.
- Tinted chips and callouts (violet for "Sample course", blue for information) added colours
  that meant nothing.

## Decisions

- **The grounds and the text are neutral.** No tint in any grey, in either theme. Dark:
  canvas `#0A0A0A`, page `#0E0E0E`, surface `#141414`, subtle `#1A1A1A`, sunken `#070707`,
  ink `#EDEDED`. Light: canvas `#F3F3F3`, page `#FCFCFC`, surface `#FFFFFF`, ink `#171717`.
  The steps between grounds stay small; borders carry the separation.
- **The dark theme is darker**, as asked: its canvas is near black.
- **One filled action, the same kind in both themes:** a deep teal with a white label
  (`#12707E` light, `#147989` dark). The bright fill with dark text is gone. Hover in the dark
  theme lightens only as far as the label keeps 4.5:1. The destructive button follows the
  same rule (a deep red, a white label).
- **Teal stays the one colour**, the teal of the mark: the action, selection, progress,
  links. Success keeps its green, so "this is the product" and "this went well" still never
  look the same (ADR-011).
- **The stage of a scene follows the surface it lies on.** Its dark background becomes
  `#141414`. That value is supplied by the player, not written into scene files, so lessons
  already generated on people's computers are unaffected; the ink, the muted text and the
  accents that *are* written into scene files stay exactly as they were.
- **The player frame declares both colour schemes.** A frame whose scheme differs from its
  parent's is given an opaque backdrop by the browser (white, in a dark app), which showed as
  a white line wherever the picture did not reach the frame's edge.

## Consequences

- Every pairing in `tokens.test.ts` still passes in both themes; two pairs were added for
  what the new rules depend on.
- The window's first-paint colour (`window.ts`), the stage background (`scene-run.ts`,
  `scene-palette.ts`, the scene-authoring skill and the packaged guide) and the end-to-end
  check of the canvas colour changed with the tokens. They must keep changing together.
- Chips and callouts that used a decorative tint may be moved to neutral ones over time; the
  tokens for those tints remain, because scenes share the accents.
