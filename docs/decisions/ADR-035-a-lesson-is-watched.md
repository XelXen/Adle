# ADR-035: A lesson is watched: one dark screen, the words as captions, and the whole screen if wanted

- **Status:** Accepted
- **Date:** 2026-11-21
- **Builds on:** ADR-013 (narration), ADR-022 and ADR-027 (the look), ADR-032 (the size a
  picture is drawn at).

## Context

A lesson showed its picture in a card about 565 pixels wide, with the transcript in a
column beside it taking two fifths of the page. The owner, having sat through lessons:
the animations "feel like a complement to the lesson" and "should be a bigger part", with
a way to fill the screen, the transcript kept as captions ("don't get rid of the word by
word thing"), and the feel of a well-made mathematics film.

Three things stood in the way. The transcript competed with the picture for width. The
picture followed the theme, so in the light theme it was a white card among white cards,
and a scene looked different from one learner to the next. And nothing could fill the
screen: the app grants no permission to anyone, which included its own page asking for
the whole screen.

## Decisions

- **A lesson has a screen** (`StageFrame`): one dark surface in either theme, as wide as
  the page allows and no taller than leaves the lesson's title above it and its controls
  below it in view. Along its top, one quiet line says what the part is, where in the
  lesson it comes, and offers the picture in words. A picture is on it at 16 to 9; a part
  without a picture puts its board on it, and a board with nothing on it yet shows the
  part's title, as the first slide of a talk does. A question is not on it: a question is
  a card of the page.
- **A lesson's pictures are always drawn with the dark scene palette.** Every scene file
  already carries both palettes, and every scene of the sample course and of the skill is
  run in both by the end-to-end suite, so nothing had to be redrawn. The screen's colours
  are tokens of their own (`--ad-color-stage*`), the same in both themes and tested to be
  the dark palette's. Elsewhere (the check in Settings) a scene still follows the theme.
- **The words being said run along the foot of the screen**, one line at a time with the
  word the voice has reached marked, as under a film. They are the transcript and nothing
  less: every line is in the page for whoever reads it another way, and one press unfolds
  them into a list to read at leisure, which scrolls by itself to the line being said and
  can be reached and scrolled from the keyboard. With nothing spoken the words are what
  the lesson says, so the list starts unfolded. The "Transcript" button still puts the
  words away or brings them back.
- **The lesson can fill the screen.** The player itself is what fills it, by the browser's
  own means: Escape always gives the screen back, and so does the button that took it.
  The bar of controls keeps its place under the screen and fades while the lesson plays
  and nothing is being done; its place is kept, because a picture that changed size
  whenever the pointer moved would be worse than a dark strip. What is not on the lesson's
  screen (a question, the mirrored controls of a picture) keeps the page's colours on a
  card of the page's.
- **One permission is granted, to one asker** (`mayFillTheScreen`): the app's own page,
  as the window's own document, may fill the screen. Every other permission is refused to
  everyone as before, and this one is refused to a scene's frame, to a frame of the app
  inside the window, and to a page from anywhere else. Nothing is read, recorded or sent
  by it.
- **What the lesson is and who wrote it moved out of the way** (see ADR-036): one press on
  "About this lesson" beside its title, not three lines under it.

## Consequences

- At the usual window size the picture is about 750 pixels wide where it was 565, and as
  large as the screen when asked.
- A learner in the light theme has a dark screen in a light page, as a film has.
- A picture keeps the size it was drawn at when the screen is filled while it is showing
  (ADR-032): it is stretched until the next one loads, which is drawn to suit. On a dense
  display that is visible as softness.
- While the lesson fills the screen, a toast cannot be seen and the learner's own notes on
  a part are not shown. Both are there again when the screen is given back.
- A display with nothing on it that manages windows (a build machine's) may not grant the
  whole screen. The journey that asks for it follows what the display does.

## Not done, and why

- **Keys for the player** (space to pause, arrows to move). A press of space on a focused
  button already presses it; a second meaning for the same key on the same screen needs
  more care than a line of code.
- **Loading the picture again, larger, when the screen is filled.** It would start again.
  Bringing a newly loaded picture to the same moment needs the frame to be able to run
  ahead to a given frame, which belongs with the trial of a scene before it is shown
  (ADR-037).
