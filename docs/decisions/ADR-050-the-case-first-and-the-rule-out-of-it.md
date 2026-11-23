# ADR-050: The case first, and the rule made out of it

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-049 in what the lesson's prompt asks of a part and of a lesson, and in two
  things a slide can do: a formula's parts can come out of the picture (`show` with `from`),
  and a formula a first step would show beside its case waits for the next step.
- **Keeps:** ADR-049 (a slide is data the core lays out and draws, paced by the words it
  marks), ADR-045 (a picture the core draws is data, never code), ADR-012 (one request for a
  lesson's words).

## Context

The owner watched lessons made as slideshows (0.1.0-alpha.4) and asked for more: "The model
should first show example visually and then relate the theory to it", where it "still first
shows the theory like equations side by side with the animation".

Read again offline, the slides of the lessons real models wrote that day never put a formula
in a part's first step (16 slides of three lessons). What came first was the theory in
words: a part's narration opened on the definition ("The set of all possible outcomes is
called the sample space", "The probability of an event is the sum of...") and the picture
illustrated it; its steps mostly added things one after another (a set, then a table, then a
formula), rather than doing something to the case; and the formula arrived beside the
picture as a new thing, not as the case's own numbers written down.

## Decisions

- **The prompt asks for the arc of every part, and of the lesson**: the narration opens on
  the case itself, never on a definition; the visual begins with the case alone on the stage
  (objects, small numbers, a real sentence); the next steps act on that case as it is
  explained (color, move, highlight, count, flip, roll), most of them changing what is there
  rather than adding something; only then the formula, first in the case's own numbers,
  brought out of the picture, each number in the color of what it counts; and last, where
  the part states a rule, those numbers turned into the rule's symbols. A name or a
  definition comes after two or three instances of it. The lesson's first part is a
  concrete case with no definition in it; the general statement comes later, built from the
  cases before it. "Step-by-step math" begins with one small case worked in numbers too.
- **A formula can come out of the picture**: `{"show": "id", "from": [...]}` turns a copy of
  each thing named (a brace's or an arrow's words, a member of a set, a cell, a number, a
  whole element) into the formula's `{{ }}` parts, in order or by part name, while the rest
  of the formula is written around them; the sources stay where they are. Written as
  `TransformFromCopy`, after which the formula is one thing on the stage again (its parts
  removed and the whole added), so that a later step can point at it or turn it into
  another. Anything else that can be shown whole (text, a box, a number, a sentence) can
  come out of one source. A `from` that cannot be followed is left out and said, and the
  element is shown as it would have been. Each source is lit, in its own color, while its
  copy leaves it, until the next step.
- **A sentence or a formula made of one on the stage comes out of it**, whatever the
  script says: one of the same kind, on one line each, in plain letters, that shares two
  words that say something with it (not "the", "was", "by"), or one term (not "=", "+"),
  and two fifths of all its words or parts, is shown with `TransformMatchingTex` from a copy
  of the other. "The ball was chased by the dog." is seen to be "The dog chased the ball."
  rearranged; an equation's next line comes out of the line above, what they share moving
  into place. The one it came out of stays.
- **The case is alone on the stage first, whatever the script says** (`defer_theory`): a
  formula or a rule (a `math` or a `box`) that a slide's first step would show beside a case
  (any element that pictures one) is shown at the start of the next step instead, when the
  narration reaches its first marked words; a slide with one step gains a second. A slide
  that is only formulas keeps its first step.
- **What a model writes for a slide is read as it meant it** (ADR-049), from the lessons
  written with this prompt: a point written inline where an element names one (a tangent
  `"at": {"x": -2, "on": "curve"}`, or `"at": 0` on the one curve there is, a line
  `"to"` one) is made a point of its own; a point, a value or a number moved by
  `{"x": ...}` is moved to that number; a number that follows a point or the value through
  a formula (`"p.x"`, `"2*p.x"`) follows it, the formula written again as arithmetic as a
  curve's is; and a slider nothing follows, on a slide with one point that has a place of
  its own, moves that point.
- **The prompt's own example is that arc**: a grid of squares, its row and column counted
  with braces, `3 × 4 = 12` made of the braces' numbers, then turned into `h × w = A`. It is
  one of the slides the player suite runs, with a set whose members fly into a probability
  (`counted_out`), a die whose formula waits for its next step (`case_first`), and a
  sentence and an equation rewritten out of the ones before them (`rewritten`).
- **Verified in the pinned Wanim** (`slide-player.spec.ts`, both themes): `TransformFromCopy`
  into a part of a `MathTex`, removing the parts and adding the whole after it, and
  `TransformMatchingTex` from that formula afterwards, draw as written and leave no copy
  behind; so does `TransformMatchingTex(one.copy(), other)` of sentences and of formulas.

## Alternatives

- **Drawing the formula below the picture rather than beside it.** The owner's words were
  about the order, and the link: a formula beside its case is where the eye can go from one
  to the other, once it comes after the case and out of it.
- **Checking the narration for a definition in its first sentence and asking again.** A
  second request for a lesson is what ADR-047 and ADR-048 took away; what a model meant by a
  sentence is not something to judge by its words. The prompt asks, and the slide is made to
  keep the order it can keep.
- **A `{{ }}` part inside a fraction.** A part of a formula has to be TeX on its own, which
  the inside of `\frac{...}` is not; a fraction comes out of the picture whole, or is
  written with `/` where its numerator and denominator are to come out of it apart.

## Consequences

- A part's formula is seen to be made of its picture: the numbers fly out of the braces, the
  set, the cells, into the formula, and then become its symbols.
- How well a model follows the arc is still the model's; real lessons written with this
  prompt are recorded in `PERFORMANCE.md` and PROJECT_STATE, with how often each part opened
  on its case.
