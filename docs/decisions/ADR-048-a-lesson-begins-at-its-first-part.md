# ADR-048: A lesson begins at its first part while the rest is written; a lesson's model thinks less

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-031 in when a lesson can be started: at its first whole part, not when
  all of its words are written. ADR-039 in what Nemotron 3 Ultra is sent for a lesson.
- **Keeps:** ADR-012 (one request for a lesson's words, at most one more), ADR-010 (a
  lesson enters the database only through `parse_bundle`), ADR-024, ADR-038, ADR-045.

## Context

The owner asked for the lowest latency at the best accuracy across the whole workflow.
Measured on their chapter with the real provider (PERFORMANCE.md), the longest wait by far
is a lesson's words: 116 to 259 seconds before anything could be started, every second of
it in front of a bar. Two things made it long.

- **The learner waited for the last word of the answer.** A lesson is a list of parts, and
  the model writes them in order. The first is whole a small share of the way into the
  answer, and it is all a learner needs to begin: nobody reads eight parts at once.
- **The model thought for minutes first.** Nemotron 3 Ultra's reference lists a
  `reasoning_effort` of "none", "medium" or "high", "high" being the default. Asked for the
  chapter's first lesson at "high" it thought for 18,000 to 35,000 characters and took 116
  to 232 seconds; at "medium" it thought 1,500 to 3,300 characters and took 53 to 74
  seconds, and was as correct: three lessons of three usable at their first answer.

## Decisions

- **The answer is read as it arrives** (`generation/stream.py`, `PartStream`): what comes
  before its parts (title, strategy, sources), then each element of `segments` as soon as
  it closes. Only a whole part is ever taken. Strings and escapes are followed, so a brace
  in a sentence is not the end of a part; a bound on the whole keeps a runaway answer
  from being held.
- **A lesson is stored at its first whole part** (`writing` on the stored lesson, migration
  0010), through `parse_bundle` like any other, and the job says it has a lesson (ADR-031).
  Each later part, once whole, is added after the last with `LessonService.extend`, which
  passes the whole lesson through `parse_bundle` again. A part already stored never
  changes: the learner may be in it. Identifiers follow from the parts kept, so a lesson
  taken part by part and one taken whole are the same lesson.
- **Until the first part is whole, the whole answer decides**, as before: a first part
  that cannot be used means nothing is stored, and the one retry is told what was wrong.
  **Once a lesson has begun, it is never written again.** A later part that cannot be used
  is left out, and the lesson says so at its end. No other model is asked to write it
  again: where the gateway would stand another model in, the answer ends instead, since
  the whole of the other's answer would be thrown away. Whatever ends the answer once
  the lesson has begun (the learner's stop, a provider that fails, an answer that runs
  out of room before its list of parts closes, anything else) ends the lesson's writing
  there: it keeps the parts it has and says it ends early. A stop that comes while the
  first part is being stored waits for that part, and takes no more.
- **Each figure is tried and taken in as soon as its part is stored** (ADR-045, ADR-038):
  the learner may be about to begin that part. Its trial is waited for 15 seconds at most
  (`FIGURE_WAIT_WHILE_WRITING`), since the parts after it are not read meanwhile; one that
  does not come keeps the figure untried, as before trials. A scene a model writes is
  asked for once every word is written, as before: one request at a time at a provider.
- **Who writes it is kept from its first part**: the gateway says who is writing when a
  model begins to write (`on_writer`), as the answer will say at its end.
- **What the lesson is comes before its parts**: the prompt asks for its keys in order,
  title, strategy, sources and the narrator's voice first. The voice known when the lesson
  begins is its voice: one written only after the parts is not used, since what the lesson
  sounds like does not change while someone listens (and a natural voice would record
  every line again). Passages named only after the parts are added when the answer ends:
  they change no part.
- **The core says when the words are all written**: the job reports the `drawing` stage
  before it says anything more about the lesson, so nothing reads the lesson as still
  being written once only its pictures are left.
- **In the lesson** the parts grow at the end (`LessonController.extend`, found by
  `useLessonUpdates`): "Part 1 of 2 so far", and a bar in the list of parts for those still
  to come. A natural voice's recordings stay with the narrator as the lesson grows; only
  the new lines are fetched. At the end of what is written the learner waits there ("The next part is being
  written. It starts when it's ready."), and goes on into the next part by itself when it
  comes. The last part so far is not the last: it never says "Finish lesson" while more
  are coming, and "About N minutes" is not said for a lesson opened before its length was
  known.
- **In the course** the lesson's row says "Still being written", the job's card goes on
  showing the parts being written, by their titles, beside "You can start the lesson now.
  The rest of it is being written.", and "Stop" there ends the writing and keeps the
  lesson as far as it has come. "Lesson ready" is said once, at the first part.
- **Nemotron 3 Ultra is asked for a lesson with `reasoning_effort: "medium"`**
  (`ModelSpec.reasoning_for`), checked against the real endpoint by hand. Every other kind
  of request is sent nothing new: a course plan was no quicker at "medium" (62 seconds,
  against 18 to 52 at the default), and a question during a lesson is already quick.
  "none", the one setting below, was measured and not kept: a lesson could be begun at 5.5
  seconds, but one lesson of four had a question whose answer key contradicted its own
  explanation, which held the model's second thoughts (PERFORMANCE.md). Accuracy first.

## Consequences

- Measured on the owner's chapter (PERFORMANCE.md, run 7): the lesson could be begun at
  77 seconds, at its first part, with every part written by 122; the model thought for
  9,600 characters first, three times as long as at "medium" before. At "high" and taken
  whole the same wait was 116 to 259 seconds. Three lessons at "medium" were usable at
  their first answer, and with what ADR-045 now takes, every figure they asked for is
  drawn.
- A lesson begun early has one or two parts at first. A learner who reads faster than the
  model writes waits at the end of what is written, told so, and is never asked to press
  anything to go on.
- A part left out after the lesson has begun is not asked for again: the budget of
  requests is unchanged, and the learner may be past it. They are told at the end.
- The answer is parsed twice: piece by piece while it arrives and whole at its end, for
  practice and the voice. Both are milliseconds beside the request.
