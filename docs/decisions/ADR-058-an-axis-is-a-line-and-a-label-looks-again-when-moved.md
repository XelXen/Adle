# ADR-058: An axis is a line, and a moving label looks for room again only once it has moved

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** ADR-056 in what is found as a line: an axis, which the player draws itself
  and not as a `Line`, now counts. ADR-055 in when a label that moves looks for room: where
  it found none, only once what it names has moved.
- **Keeps:** ADR-055 and ADR-056 in everything else: what is held apart, the middle of a
  word, pins tidied before anything is shown, every step saying how it is laid out, the
  journeys failing on any finding, no request.

## Context

While 0.1.0-alpha.8 was checked, two slides stalled, once each and in different runs: a step
did not arrive in 30 seconds, and the same slide passed when tried again. Both have a label
that moves with a point. What the stalled run left on the screen showed "f' = 0" with the y
axis running down through its middle, which ADR-056 said could not happen.

There were two causes. The player draws an axis as a number line, its line made from the
number line's own points; only its ticks are `Line`s. So the search found the ticks and not
the axis, and nothing kept a label clear of it. And a label that moves, where no side of
what it names was clear, tried every side at both distances on every frame: eighteen checks
a frame against every word and line that stays put, each line's points read again for each
check. On a slow machine that is enough to hold a step back past its time.

## Decisions

- **An axis is a line.** A number line is looked at as one, and its ticks as lines of their
  own; its numbers are words, as before.
- **A line's path is read once**, when the slide is tidied, with the box round it: a word
  outside that box is passed over without looking at each piece. A step's end reads the
  paths afresh, once, for its own count.
- **A label that moves keeps the place it found**, its side and its distance. Where it found
  none, it looks again only once what it names has moved 0.2 from where it last looked;
  where it found one and that place is crowded again, it looks at once.

## Alternatives

- **Looking only every few frames.** Simpler, but a label would lag a point that moves
  quickly, and a frame's cost would still depend on how crowded the slide is.
- **Leaving axes out, as before.** A label above the origin is exactly where an axis runs:
  the case ADR-056 was written for.

## Consequences

- A label crossed by an axis goes where the axis does not run through it, and a step whose
  label stays crossed fails the journeys, as for any other line.
- Where no side is clear, a moving label may stay crowded until its point has moved 0.2;
  the step's end still says so (`layout`).
