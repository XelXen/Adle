# ADR-040: A picture is drawn happening, a step for each sentence, as long as the words said over it

- **Status:** Accepted
- **Date:** 2026-11-21
- **Changes:** the scene guide's section on motion and the request for a scene. ADR-035 (a
  lesson is watched) stands; this is what is drawn on that screen.

## Context

The owner, of the pictures: "they feel like a complement to the lesson; they should be a
bigger part … proper 3Blue1Brown vibes."

The scene guide asked for one idea per animation, a run of 0.5 to 1.5 seconds each, and a
whole scene under 15 seconds; the request asked for "between 6 and 14 seconds". A part's
narration runs for 20 to 60 seconds. So a picture drew itself in its first few seconds and
stood still while the rest was said: a slide, with things fading in. The model was never
told what makes a mathematical animation good to watch, and the brief a lesson gives the
animator asked for "a handful of shapes, one idea".

Wanim provides nearly all of manim's means of showing change (`TransformMatchingTex`,
`ValueTracker` with `always_redraw`, `Indicate`, `LaggedStart`, …). Tried in the player,
they work, but for one: `Circumscribe` given a colour takes the name for its shape and
stops the scene, and without one draws in a yellow outside the palette.

## Decisions

- **A picture lasts as long as the words said over it**: the request names a length worked
  out from the narration at two and a half words a second, between 8 and 40 seconds, and
  asks for a step on screen for each sentence, in its order, ending on a frame that holds
  the idea.
- **The guide says how to draw the idea happening** ("Motion: draw the idea happening"):
  show change as change (transform; rewrite an equation with `TransformMatchingTex`), let
  a value move and everything that depends on it with it, one colour for one meaning
  wherever a quantity appears, point at what the narration names, keep the stage clear,
  and little text, since the words are said. A new example, `sum_to_output.py`, does all of
  it and runs in the end-to-end suite in both themes, like every example.
- **The brief a lesson gives the animator** describes the picture step by step in the order
  of the beats: what appears, what changes into what, what is pointed at.
- **`Circumscribe` is refused by the static rules**, with what to use instead, and a
  fixture holds the failure.

## Consequences

- Pictures move while they are explained, which is where the learner's eyes are on the
  lesson's screen (ADR-035). Longer scenes are also more code: more for a model to get
  wrong. Every picture is tried before it is shown and written again once if it breaks
  (ADR-038).
- A picture is not yet in step with the voice beat by beat: it runs for about the length
  of its part, and the narrator is still the only clock (ADR-010). Holding a picture at
  each beat until the voice reaches it is a later step.
- The scene guide sent with every request for a scene is longer by one example (about a
  fifth more prompt for each).
