# ADR-047: Mend a lesson's answer rather than ask for it again; a voice begins when the words are stored

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-012 in what makes a lesson's answer "unusable": some of it the core now
  mends. The budget is unchanged: one request for the lesson, at most one more, told what
  was wrong.
- **Adds to:** ADR-042 (a natural voice): when a lesson is recorded.

## Context

The owner asked for "all slowdowns in a proper workflow", optimized "for lowest latency but
best accuracy". So the whole of it was run on their own chapter of lecture notes with the
real provider (NVIDIA, Nemotron 3 Ultra for each kind of request, ADR-039), by hand
(`scripts/dev/real_provider_check.py document:<file>`), each step timed.

The first run: the import took a second; the course plan 32 seconds, every section in it
(ADR-046). The lesson's answer came in 56 seconds and was refused: twelve of its
twenty-five spoken lines had TeX in them (`F_X(x) = P(X \le x)`), which the rules refuse
because they are read aloud. Written again, told why, it came in 149 seconds and was
refused again, for something it had not done the first time: one practice question
without its explanation. After 205 seconds and two requests there was no lesson. A second
run: the answer came in 116 seconds and was refused because its three checkpoints had no
title.

None of these needed a model to put right, and a whole second answer is the slowest thing
in the workflow: two to two and a half minutes, which can fail somewhere else.

## Decisions

- **Notation in what is read aloud is said in words by the core** (`generation/speech.py`),
  the way a teacher reads it: `F_X(x) = P(X \le x)` is "F sub X of x equals P of (X is less
  than or equal to x)", `e^{-\lambda x}` "e to the minus lambda x", `\int_0^x` "the integral
  from 0 to x of", `\frac{a}{b}` "a over b", a `cases` block "0 when x less than 0, 1 when x
  greater than or equal to 0". Only a line with notation in it is touched (a dollar sign, a
  backslash, `_`, `^`, a brace); a line with a link or markup is left as it is, to be
  refused as before; what comes out has no notation left in it and is checked by the same
  rules. The board (`show`) keeps the formula.
- **A practice question that is not whole is left out** when the answer is read, as one
  that could not be used already was when it was compiled. Practice is extra.
- **A checkpoint, a summary or a reflection without a title is named by what it is**
  ("Checkpoint 2", "Summary", "Think it over"). Any other part without one is still a
  problem for the rewrite.
- **TeX whose every backslash was written twice is read as it was meant.** Two of the three
  answers wrote the board's formulas so (`\\le` for `\le`, 26 and 31 times), which TeX
  reads as a line break and some letters: the formulas on the board came out broken. Where
  a command stands behind exactly two backslashes, every run of backslashes in that text is
  halved. TeX written once is left as it is.
- **Everything else that does not hold together is still the one retry**, told what was
  wrong: a missing question, a link, too few parts, a question that checks no objective.
- **A natural voice begins on a lesson as soon as its words are stored**, in the voice lane,
  when a natural voice reads the lessons (`NarrationService.record_ahead`). It used to begin
  when the lesson was opened, so its first lines were read in the computer's voice while
  the rest were recorded. Nothing a picture changes is said: a picture that does not come
  changes what is shown, not the words.

## Consequences

- Both refused answers of the first run, and the refused answer of the second, are usable
  lessons as they came: the lesson can be started after one request, about two minutes in,
  where it took two or failed. The third run was usable at its first answer (232 seconds:
  the model thought longer that time); its five figures, left out then for want of a
  description, and its board's formulas, written twice over, are drawn and shown whole by
  what was changed after it (checked on that same answer).
- The narration of a mathematical lesson can sound literal ("F sub X of x") where a model
  that followed the rule would have written "F of x". The rule stays in the prompt; this is
  for when it is not followed.
- A natural voice works on a lesson the learner may not open soon. It is this computer's
  time, in a lane of its own, and only when the learner chose such a voice.
