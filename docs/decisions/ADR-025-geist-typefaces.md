# ADR-025: Geist for all three voices

- **Status:** Accepted
- **Date:** 2026-11-20
- **Supersedes:** the choice of typefaces in ADR-022 (Newsreader, Inter, JetBrains Mono).
  Everything else in ADR-022 stands, including "two voices": a serif for what is read and a
  sans for what is operated.

## Context

The owner asked for Geist: "use geist mono, sans and serif". Geist is one family drawn to
work together (Vercel, with Basement Studio; the serif with Andrés Briganti and Mark
Davis), under the SIL Open Font Licence.

## Decisions

- **Geist Sans** sets what is operated, **Geist Mono** what is typed or copied exactly, and
  **Geist Serif** what is read. The roles of ADR-022 are unchanged; only the faces are.
- Sans and Mono come from `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`
  (variable, with the italic of the sans).
- **Geist Serif is kept as a file in the repository**, with its licence beside it
  (`packages/design-system/src/fonts/geist-serif`). The only package that carries it is
  Vercel's `geist` (1.9.2), which requires the Next.js framework as a peer; installing it
  would bring a web framework into a desktop app for the sake of one 47 kB file. The file
  was taken unchanged from that package. `scripts/licenses.mjs` lists it by hand and fails
  if the file or its licence is missing.
- Of its four variants (Regular, Square, Triangle, Heart) Adle uses **Regular**: its own
  documentation gives Regular and Square as the ones for primary text.
- Geist Serif has **one weight and no italic**. Serif text styles are therefore all weight
  400 and a little larger than they were (a title is 32 px where it was 30), and
  `font-synthesis: none` is set app-wide so that nothing fakes a bold or an italic.
- **Scenes keep Inter.** A scene is a file with positions worked out for the widths of its
  letters; a different face would move every label in every scene there is. The stage has
  its own colours for the same reason (ADR-022).

## Consequences

- Geist Serif calls itself a display face: high contrast, fine hairlines. At 19 px for a
  lesson's narration it was looked at in both themes and reads well; it is not used smaller
  than that. If a smaller reading size is ever needed, it is set in the sans.
- Emphasis inside serif text cannot be bold. Where a word must stand out there, it is set
  in the sans (`text-body-strong`) or said in words.
- Geist Serif covers Latin. A character it lacks (a Greek letter outside a formula) falls
  back to the next serif in the stack. Mathematics is set by KaTeX as before.
- Updating Geist Serif is a manual step: take the file from a newer `geist` package,
  replace it and its licence, and change the version in `scripts/licenses.mjs`.
