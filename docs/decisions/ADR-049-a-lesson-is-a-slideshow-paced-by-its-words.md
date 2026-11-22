# ADR-049: A lesson is a slideshow, each part's picture a slide paced by the words it marks

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-045 in what a lesson's prompt asks for: a slide script on every part that
  teaches, not a figure on some of them. ADR-031 and ADR-038 in nothing but what a picture
  is: a slide is stored, tried and taken in as a figure is. The board (`show`) is no longer
  asked for, and is not kept on a part that has a slide. ADR-048 in how long Nemotron 3
  Ultra thinks for a lesson: not at all ("none"), where it was "medium".
- **Keeps:** ADR-010 (a lesson enters the database only through `parse_bundle`), ADR-012 (one
  request for a lesson's words), ADR-035 (a lesson is watched on one dark screen), ADR-038,
  ADR-045 (a picture the core draws is data, never code), ADR-048.

## Context

The owner watched real lessons and asked for something else (2026-11-22): lessons took six
minutes to be ready, most parts had no animation, and the pictures there were showed
equations or a board of formulas, the same line three times over, a table with its TeX
printed raw. They asked for "3b1b level of visual teaching": the visual intuition first,
and its relation to the equation; for English and other subjects, examples; one slideshow
the lesson controls, the picture changing at the words being said, and the words and the
pictures made separately rather than synchronized by a model.

Measured: a lesson's words took 53 to 245 seconds, and a scene a model wrote took about
228 seconds more, failed its trial often enough to be written twice, and only two parts of
a lesson could have one. A figure (ADR-045) cost nothing, but there were ten fixed kinds,
each a whole animation timed by the beats, and a lesson had four to seven of them.

## Decisions

- **Every part that teaches has a slide**: what is on the stage (`elements`) and how it
  changes (`steps`), written by the model beside the part's words, as data
  (`generation/slides.py`). Twenty-seven kinds of element, from which a picture is built
  rather than chosen: text, a formula whose parts can be pointed at and colored, a sentence
  whose words can be, a set of outcomes, a grid, a table, nodes and edges, bars, a number
  line, axes with curves, areas, points, tangents and vectors, a number, a coin, a die,
  shapes, arrows, braces, outlines, labels, and one value (`param`) that curves, points and
  numbers follow, which the learner moves at the end with a slider. Seven verbs for a step:
  show, hide, highlight, color, move, transform, set.
- **The words cue the pictures.** The model puts [brackets] around the words at which the
  picture should change; the core takes the brackets out of what is said and keeps where
  each phrase begins (`Beat.cues`, the index of a character). The first step plays as the
  part begins; each cue plays the next. Marks that do not fit are fitted: a mark on the
  first words, or past the last step, is dropped; a step without one is cued where a
  sentence begins (`drafts._paced`). Brackets inside `$...$`, and ones that hold a number
  or an interval, are mathematics, not cues.
- **The core lays the slide out and writes the scene**, from templates, as it writes a
  figure: by named places (left, right, top, beside another element) given room as what is
  in them needs, each fitted at run time when sizes are known; one storyboard phase for
  each step, run in Wanim's slides mode (`pacing: 'cued'` on load), which holds after each
  phase until `next`. Each phase ends with `post_message("step", n)`. A slide with a slider
  ends on a live page. Nothing of the model's text reaches the scene but as a quoted
  literal; a formula of a curve is Python written again from arithmetic (ADR-045).
- **A slide is never lost for one of its parts.** An element that cannot be drawn, an action
  that names nothing on the stage, a step past the ninth: each is left out and said
  (`left_out`, logged by count only); the rest is drawn. A slide with nothing that can be
  drawn leaves its part in words, as a figure that cannot be drawn did.
- **The scene says how many steps it has**, and that is computed, never taken on trust: the
  policy counts the `step` events numbered from 0 (`SceneReport.steps`, `SceneArtifact.steps`).
  `step` joins the closed event vocabulary.
- **The narrators deliver cues** (`NarrationHandlers.cues`, `onCue`): a recorded voice at the
  words the core measured, the computer's voice at its word boundaries (or, for a voice that
  says nothing of where it is, at the time it would reach them at its pace), silent reading
  at the time the line would reach them; every cue before the line ends. A cue is not a
  highlighted word: nothing claims a position it does not know. The lesson passes each to
  the scene on screen (`advanceScene`), and `SceneCues` counts them: a slide takes one each
  time it holds after a step, so a cue said while a step is still drawn waits for it.
- **A slide is tried like any picture** (ADR-038): `runTrial` loads it cued, says `next` at
  each step's end, and passes it held at its last; a live page at its end is operated.
- **The prompt teaches by intuition and example**: begin with something the learner can see,
  name the idea once it has been seen, the picture carrying it; a formula after the picture
  it describes, each symbol in the color of what it stands for; for language, real
  sentences with the words that carry the idea colored and labeled; for other subjects a
  concrete case first. 6 to 9 parts, no board, no scene for a model to write. The prompt's
  own example is one of the slides the player suite runs.
- **A lesson's model does not think first** (`reasoning_effort` "none" for Nemotron 3
  Ultra's lessons). Measured by hand through NVIDIA: asked for a slideshow at "medium" the
  model thought 19,000 to 59,000 characters and a lesson could be begun only after 118 to
  313 s; at "none", after 13.5 s, every part written at 63 s. ADR-048 kept "medium" because
  an answer written without thinking once had an answer key its own explanation did not
  reach; that, and the slip seen this time (a wrong option that is the right one written
  another way, 12/52 beside 3/13), are now caught in drafts, deterministically: a wrong
  option equal in value to the right one is left out, and a numeric question whose
  explanation writes numbers none of which is its key is not used. The prompt asks for
  each question's working before its answer, and the answer the working finds.
- **What a model writes for a slide is read as it meant it**, as for figures (ADR-047):
  a part named after the prompt's example ("sentence.s.1-2", "omega.2" in a set called
  "omega_die"), items written as parts ("omega.HH"), a cell counted from 0, a sentence left
  empty for a later step to fill, "below" as a place, set symbols written as themselves
  (set as a formula, and said in words); a stage given no places is laid out with its
  pictures on the left and its words on the right, and many things in one place stand in
  rows. A worked example or a summary may show its point in its slide rather than on a
  board; a worked example without a problem is an explanation.
- **What the probe found in the pinned Wanim** is relied on and tested (`slide-player.spec.ts`
  runs every example in both themes, step by step): a storyboard keeps what each phase drew;
  slides mode holds after every phase, and `next` during a phase cuts it short, so a host
  says `next` only after a step's event; TeX takes `\color{#hex}`; TeX is drawn about two
  thirds the size of text at one size (`_TEX_SCALE`). `Ellipse` and `Flash` stop a scene,
  and the policy now refuses them.

## Consequences

- A lesson costs one request, as before, and asks no scene of a model in the ordinary case:
  the minutes a scene took are gone, and every part that teaches has a picture that is
  drawn at once.
- A lesson can be begun about twelve seconds after it is asked for through NVIDIA (11.5 to
  13.5 s in three lessons), and is whole within about a minute and a half, where it was
  two to five minutes before it could be begun (PERFORMANCE.md).
- What thinking would have caught and drafts do not is not caught: a wrong idea stated
  rightly, an option that is wrong in a way no number shows. The checkpoints of three
  lessons written so were checked by hand and found right.
- What a slide can show is what the elements can draw. A picture they cannot build is said
  in words, not drawn wrongly.
- Figures and model-written scenes stay: an old lesson keeps them, and an answer that gives
  one is still read.
