# ADR-022: Sprout, second edition: a serif for what is read, three grounds, and a lesson that has the window

- **Status:** Accepted
- **Date:** 2026-11-20
- **Supersedes:** the values of ADR-006 (the tokens' structure, the contrast rules, and the one
  theming mechanism stand). ADR-011 (the mark and its teal) stands.

## Context

The owner looked at the app and said that the design system "looks super AI-generated, basic,
unpolished, not at all professional-grade", and asked for one that is.

They were right, and the reasons can be named. Every text was one sans at two weights, so a
lesson's title and a button's label had the same voice. Radii of 12 and 18 made everything a
soft box. The ground was a mint tint with white cards on it, the default of a hundred
templates. The one suggestion that mattered was marked with a coloured bar down its side.
Badges were pills. A rail 240 pixels wide held two links. A lesson was read inside the same
chrome as the settings.

PLAN.md section 4.2 gives the first edition's values as "starting values" to be centralised
and changed on purpose. This is that change, on purpose.

## Decisions

- **Two voices.** A serif, Newsreader, sets what is *read*: page titles, a lesson's own words,
  questions, a dialog's title. Inter sets what is *operated*. JetBrains Mono sets what is typed
  or copied exactly. All three are variable fonts under the SIL Open Font Licence, bundled.
  Mathematics (KaTeX) sits beside the serif at the same size, which it never did beside the
  sans.
- **Three grounds.** `canvas` is the frame of the app; the rail lies directly on it. `page` is
  the main region, a panel set into the frame with its own edge. `surface` is a thing on the
  page. The first edition had two, and so every screen was "boxes on a tint".
- **Neutrals that are neutral.** The grounds and text lose most of their green. Ink is close to
  black; there is a third text colour, `faint`, for the quietest things that are still text.
- **Teal is spent sparingly.** It is the filled action and the mark of selection. Tabs, the
  rail, and a lesson's present part are marked in ink, not teal. The filled action is a shade
  deeper than the mark, so white on it clears 4.5:1 with room.
- **Finer shape.** Radii 6, 8, 12, 16 where they were 8, 12, 18. A badge is a small label with
  square shoulders, not a pill. Controls are 36 px tall where they were 40. Three named
  shadows; most things have none. This departs from PLAN 4.2's "card radius 16–20, controls
  10–14, pills fully rounded", which is what made it look as it did.
- **The rail earns its width.** It lists the learner's most recent courses under the two
  destinations, so any course is one click from anywhere.
- **A lesson has the whole window.** In a lesson, and in a round of questions, the rail is left
  out. Where the learner is, is a strip cut into the lesson's parts, not a row of numbered
  discs. The controls are one bar that floats at the bottom edge.
- **The main suggestion is marked by what it is, not by a stripe:** an eyebrow, a title in the
  serif, the only filled button on the page, and a wash of `primary-soft` from its top edge.
- **The welcome shows the thing.** Beside the words, a lesson in miniature, drawn from the
  same tokens: a picture with something to move, the words beside it, where the learner is.
- **The stage keeps its colours.** Scenes are Python files with colours written into them. The
  stage, its ink, and its muted text get tokens of their own (`scene-*`) with the old values,
  so the interface can change without a single scene changing.
- **Motion says what happened:** a page settles, a dialog arrives, a line of the board is
  written, a card lifts under the pointer. Nothing moves to be looked at.

## Consequences

- Two more font files ship (about 400 kB together). Nothing is fetched.
- Every screen changed appearance and none changed what it says. The end-to-end journeys ask
  for things by role and name, so they needed four kinds of change: a course is now also in
  the rail (ask for its card in the main region); a lesson has no rail (go back to the course
  first); the canvas has new colours; and a check for contrast must wait for motion to finish,
  because a panel that is fading in has, for 300 ms, a colour nobody is meant to read.
- The first edition's "playful" is now carried by the content (the scenes, the questions) and
  not by the chrome. That is the trade the owner asked for.
- The serif is used for reading text at 18 px and up. Below that, and for anything pressed, the
  sans stays: a serif at 13 px in a button would be the mistake in the other direction.
- `DESIGN_SYSTEM.md` is rewritten for the tokens and the patterns above. A gallery of every
  component in every state (PLAN 4.3) still does not exist; the set of screenshots the
  end-to-end suite saves remains the visual reference.
