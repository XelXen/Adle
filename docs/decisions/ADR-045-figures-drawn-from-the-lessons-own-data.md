# ADR-045: Figures, drawn by Adle from the lesson's own data

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-012 and ADR-038 for most pictures: a figure costs no request of its own.
  A picture a model writes (a scene) is asked for as before, one request and one complete
  file, with at most one retry told what was wrong.
- **Adds to:** ADR-031 (a lesson is not kept back for its pictures) and ADR-040 (a picture
  is drawn happening, paced to the words).

## Context

The owner: "Why does ai fail on a lot of animations. Most animations are easy to build...
Still it's a lot of times error prone, takes a lot of time to generate even though it's
meant to be super simple. Also why does it only draw like 1 or two animations in total? it
should be more visual."

What happened: every picture was a whole Wanim file written by a model, one request each.
On the fastest model that writes them well that took 134 to 151 seconds a picture
(measured 2026-11-21, ADR-039), a share of them failed the policy or the player and cost a
second request, and a lesson asked for at most two, to stay inside the providers' limits
and within a wait a learner would accept. Most of those pictures were of a few kinds: a
formula worked step by step, a curve with an area under it, bars, a number line, steps in
order, a table filling in. A model can say *which* picture and *what is in it* in a few
lines, reliably; writing the program that draws it is where the time and the failures were.

## Decisions

- **A part of a lesson may carry a figure**: a kind, the data of that kind, and a
  description for someone who cannot see it. The lesson is asked for one on every
  explanation, visualization and worked example that has something to see: four to seven
  in a lesson.
- **Ten kinds** (`generation/figures.py`): `equation` (a formula rewritten step by step),
  `graph` (up to three curves given as formulas, an area under one, named points, a point
  running along the first curve, or a slider the learner moves), `bars` (and the values
  they change to), `number_line` (marks, an interval, a moving point), `flow` (steps in
  order, or in a loop), `layers` (nodes in layers, joined, and a path through them),
  `table` (filled row by row, a row pointed at), `scatter` (points, a fitted line, its
  residuals), `vectors` (from the origin, and added tip to tail), `tree` (branches with
  words on them).
- **Adle writes the scene, not a model.** Each kind is a fixed template; the figure's data
  fills it in. The data is checked first: field by field (a field the format does not know
  is passed over; one it knows must be right), text as
  plain words or as TeX without the commands that could reach outside a formula, a formula
  as numbers, `x`, the slider's name, `+ - * / ^`, brackets and a short list of functions,
  parsed and written out again as Python over `math` (nothing of the model's text reaches
  the scene but as a quoted string), every curve tried at 161 points for a value and a
  jump. A figure that fails any of that is left out, and its part is told in words.
- **The format takes what a model means.** The first real lesson written this way lost all
  six of its figures to the format, not to the idea: a label left `""`, curves counted
  from 0, a density written in pieces (`(x >= 0) * exp(-x)`), an area that was to follow
  the slider (`"to": "a"`), a table cell with words and a formula together. So: a field
  left empty is no field; a curve numbered 0 means the model counts from 0 (and a curve
  not named is the first); a comparison in a formula is 1 where it holds and 0 where not;
  either end of a shaded area may be the slider's name; a cell may mix words and `$math$`
  (set as one formula with the words as text), and each column is as wide as what is in
  it; a slider named `x` is a point that runs along the curve; TeX whose every backslash
  was written twice is read as it was meant. A figure the model did not describe (a third
  answer left out all five descriptions) is described by Adle from its data ("A graph of
  $F_X(x)$ for $x$ from $-2$ to $12$, with a point that runs along the curve."), so that it
  is never a picture without words. Measured again on all five answers the three runs
  gave: twenty-seven figures of twenty-seven are drawn, and every answer is a lesson.
- **A figure is a picture like any other once it is written**: it passes the scene policy,
  it is tried in the app's player before it joins the lesson (ADR-038), and it joins the
  stored lesson only through `LessonService.settle_scene`. Its description is the text a
  learner reads when the picture is not seen. A lesson's figures are offered for their
  trials all at once, so that the app runs them one after another in a single look rather
  than each waiting a second for the next; they join the lesson in order.
- **Paced to the words** (ADR-040): a step of the figure for each sentence said over it,
  at two and a half words a second, so that it moves on as the narration does.
- **An interaction is a figure with a slider**: the learner moves it and the graph is
  drawn again. An interaction whose figure has nothing to move is shown as a
  visualization, as an interaction whose scene had nothing to move always was.
- **A scene written by a model is kept for what no figure can show**, and only for an
  interaction, at most `MAX_SCENES_PER_LESSON` (two) in a lesson, asked for after the
  figures are in place.
- **Laid out to be read**: names stand where nothing else is drawn (a point's name above
  its curve on the side the curve is not, a vector's on the side away from the others, a
  curve's in a legend over the graph, the shaded area's with them), axes in round steps
  that waste little of the stage and keep the range asked for where a round step fits it,
  numbers on the multiples of a step, one scale across and up for vectors, a formula in
  display style, a curve in pieces drawn in short straight steps (smoothed, it ripples
  where it jumps).
- **Each kind is run in the player in both themes** by the end-to-end suite
  (`e2e/fixtures/figures/`, written by `npm run figures` from the examples in
  `adle_core/tools/export_figures.py`); a unit test fails if those files are not what the
  module writes now.
- **The scene policy refuses `Indicate` given a color**: found in a figure, it makes a
  point that is not a number in the pinned runtime and the scene stops. Without a color it
  runs.

## Consequences

- A lesson has four to seven pictures where it had one or two, and they are there seconds
  after its words: drawing a figure is a template filled in and a trial in the player.
- A lesson costs one request where it cost three (usually), and a model's request for a
  picture is the exception.
- A figure can show only what its kind can. A picture outside the ten kinds is a scene a
  model writes, or words.
- The lesson's answer is longer by its figures' data, a few hundred characters each: the
  request for the words takes a little longer than before.
- The rule "one scene = one request" (AGENTS.md) is about a scene a model writes. A figure
  is no request at all.
