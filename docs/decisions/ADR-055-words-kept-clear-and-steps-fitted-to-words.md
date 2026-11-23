# ADR-055: Words are kept clear of words and of the edge, and a step is no longer than its words

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** ADR-049 in how long a slide's step takes: no longer than the words it goes
  with. The closed vocabulary of scene events (ADR-004) gains one name, `layout`.
- **Keeps:** ADR-012 (no request is made for any of this), ADR-038 (a picture's trial),
  ADR-045 and ADR-049 (Adle writes slides and figures from the lesson's data; a step
  begins when its words are said).

## Context

The owner asked: "is there a way to detect overlaps and out of bounds in animations? if so
we can ask the ai to redraw those.... also the animation shouldn't last too long or too
short after the transcript is over otherwise that means the thing is out of sync", and,
asked which overlaps count: "sometimes they are necessary and sometimes not- idk how
you'll check".

A label beside a line had been seen lying over an axis's number (2026-11-22). A slide or a
figure is written by Adle from the lesson's data: the AI never chose where anything goes,
so asking it to draw again would cost a request against the quota and could do no better.
How wide a word is drawn (TeX, the font) only the player knows.

A step of a slide begins when its words are said, and the next waits for it to end (the
cues are counted, ADR-049): a step whose animations last longer than the words before the
next cue makes the picture fall behind, and over a part the lag adds up.

## Decisions

- **Only words are held apart, and only from words; and nothing may lie past the edge of
  the screen.** A drawing over a drawing is usually meant (a point on its curve, a ring
  round a term, a shaded area under a curve), and so is a label touching what it names.
  Two pieces of text over each other never are: neither can be read. A word is what the
  player draws as text, a formula or a number (`Text`, `MathTex` and its kind,
  `DecimalNumber`), each taken whole. Two words overlap when they share more than 0.06
  of a unit both across and up.
- **A label is pinned beside what it names** (`pin`). Once everything of a slide is in
  place, and before anything is shown, a label that lies over another word or past the
  margin goes to the first side of what it names where it does neither, then a little
  further out; with no such side it stays where it was asked to go (`tidy`). A point's
  name moves with the point: it keeps its side while that is clear of the words that stay
  put, and steps to the first clear side when it is not, and stays there.
- **Every slide and figure says, as each step or page ends, how many of its words lie over
  others and how many things lie past the edge** (`audit`, the scene event `layout`). The
  app does nothing with it. The end-to-end suite steps through every slide and figure
  example in both themes and fails on any: what the templates draw is checked at every
  step, measured where it is drawn.
- **A step of a slide takes no longer than its words.** From its cue to the next (the
  first from the start, the last to the end of what is said and 0.6 s more), at a brisk
  3 words a second with 0.3 s between lines, a step whose animations would take longer
  has them made quicker in proportion, down to 0.45 of how long they were written to take,
  never slower. A step with time to spare is left as it is: the picture holds while the
  words go on.
- **No request is made for any of it.** A scene a model writes is not checked this way:
  its own code places its words. It still has its trial (ADR-038).

## Alternatives

- **Asking the AI to draw it again.** A request for each picture, against a quota, for a
  picture whose places Adle chose. The AI cannot see the drawing either.
- **Checking in the core before the scene runs.** The core does not know how large a word
  is drawn; the estimates it lays out by are why a label could land on a number.
- **Measuring from the player frame's own code, for every scene, a model's too.** It would
  read Wanim's internal arrays from outside the scene; the scene's own Python uses the
  documented calls the slides already use (`get_left()`, `next_to`).
- **Stretching a step whose words are long.** A picture that holds while its words go on
  is what a slide is; a slower animation is not a better one.

## Consequences

- A label that would cover a word or run off the screen is drawn on another side of what
  it names, before the learner sees it; nothing is seen to move.
- A part whose words come quickly has quicker animations; its picture cannot fall behind
  by more than the shortest a step can be made.
- The examples the player runs are written again (`npm run slides`, `npm run figures`):
  each has the layout methods and says how it is laid out as each step ends.
- `layout` is a fifth name in the scene policy, the event protocol and the lesson format's
  `events`; a lesson stored before keeps its scenes, which never say it.
