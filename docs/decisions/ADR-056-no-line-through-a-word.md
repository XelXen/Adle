# ADR-056: No line runs through a word

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** ADR-055 in what is held apart: words from words, and now also from the lines
  drawn through them.
- **Keeps:** ADR-055 in everything else: a label pinned and tidied before anything is shown,
  one that moves stepping aside, every step saying how it is laid out, no request.

## Context

ADR-055 kept words clear of words and of the edge of the screen, and said what it left: a
line or a curve that runs through a label was not looked for. The example it was checked on
showed one at once: "f' = 0", set above a flat tangent at the origin, with the y axis
running down through its middle. The owner asked for whatever was left to be done before
the release.

## Decisions

- **A line, an arrow, an axis or a curve may not run through the middle of a word.** What
  is drawn as a line is whatever the player draws as one (`Line` and its kinds, an axis's
  line among them, and `ParametricFunction`, a plotted curve); its path is taken from its
  anchors, piece by piece. The middle of a word is its box less a fifth of its width at
  each side and a quarter of its height at the top and bottom: a line beside a word, under
  it, or grazing the tops of its letters does not count.
- **The lines that stay put are kept with the words that do** (`self.lines`, set by
  `tidy`): a pinned label and a label that moves with something keep clear of both, by the
  same search for a side.
- **A step says how many words a line runs through**, with how many overlap and how many
  things lie past the edge (`layout`). The journeys fail on any, as before.
- **A tangent is drawn only over its axes' own area** (`clipped`): it moves with its point
  and cannot step aside, and drawn its full length near the bottom of the axes it ran down
  among their numbers (the x axis's 0, in the examples).
- A filled shape is not a line: a word on its own box, chip or bar is where it is meant to
  be. A dashed line is not looked at piece by piece.

## Alternatives

- **Any line through any part of a word's box.** Axis numbers sit just below their ticks,
  and a tangent passes just under its own label: both would count, though nothing is hard
  to read.
- **Leaving it to the learner's eye.** A line struck through a word is as unreadable as a
  word over a word, and the check that finds one is the same check.

## Consequences

- "f' = 0" in the examples is set where the y axis does not cross it.
- A template whose label a line runs through fails the journeys, for every example, in
  both themes, at every step.
