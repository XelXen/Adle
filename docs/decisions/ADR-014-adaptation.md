# ADR-014: Mistakes are hypotheses, and the next step is a suggestion with a reason

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

PLAN.md 8.3 to 8.5 ask for a misconception engine whose hypotheses are tentative, supported,
rejected, or resolved; a deterministic policy that chooses the next step and says why; and
spaced review that depends on evidence. M6 also asks for rubric-bounded evaluation of open
answers and for distinct evidence paths for correct, incorrect, guessed, hinted, and slipped
answers.

Three things shaped the decisions below. The learner must never be told something the evidence
does not support, and must never be trapped. The model provider is scarce (a lesson costs three
of roughly eighty requests a day) and, at the time of writing, unavailable. And everything that
decides what a learner sees should be readable as rules and testable without a database.

## Decisions

### Hypotheses are computed, never stored

- `learner_model/misconceptions.py` folds a concept's answers and the learner's dismissals into
  one hypothesis per kind of mistake. Nothing is written back: a hypothesis cannot drift from
  the record it comes from, and changing a rule changes every hypothesis consistently.
- One wrong answer that points at a kind of mistake opens a **tentative** hypothesis. A second,
  independent one (another question, or the same question after twelve hours) makes it
  **supported**. A right, unaided answer to a question that _could have shown_ the mistake
  **rejects** a tentative hypothesis; two of them **resolve** a supported one. Pointing at it
  again undoes progress towards resolving it.
- To know what a question could have shown, every attempt stores `reveals`: the kinds of mistake
  the question's wrong options are tagged with (plus a slip of sign for a number, and steps out
  of order for an ordering).
- Only a supported hypothesis about the idea itself stands in the way of "Demonstrated for now".
  It reaches the knowledge state as a flag on the observation (`unresolved_misconception`), so
  the state is still a pure fold of observations and can be rebuilt.
- **The learner has the last word.** "That was a slip" rejects an open hypothesis. It is stored
  as a learner event and as an observation of its own kind (`dismissal`), so the change of state
  has a row that caused it and a sentence that explains it. The hypothesis comes back only if
  later answers point the same way, and then it starts again from one answer.
- Wording is fixed in one place and never stronger than the evidence: one answer "could mean",
  two "suggest". No sentence names a fault of the person.

### A slip is not a gap

- A wrong answer that shows the method (the right number with the wrong sign, or an option the
  lesson's author tagged as a slip or a misreading) is recorded as incorrect and **counted as
  partly right** by the tracing model. It never blocks mastery and is never a reason to
  re-teach.
- Consequence, checked by a test: on a question that is hard to guess, a slip moves the estimate
  more than a right answer given after a hint that gave the method away.

### A repeat counts in full only after a real gap

- Answering a question again within twelve hours is recorded as an aided answer and described as
  such ("you had seen its explanation a short while ago"). After that it is recall, and counts in
  full. Before M6 any repeat counted as aided for ever, which made review of a small set of
  questions impossible.
- The same twelve hours decide which questions practice may ask. If every question was answered
  recently, practice says so and says when there will be something to ask, rather than asking
  for an echo.

### Lessons carry questions that are kept for later

- `Lesson.practice` (Lesson IR 1.0, additive) holds up to eight questions that are not part of
  the lesson's flow. They are asked in practice and review, so a review is more than the
  lesson's own questions again. The player view does not include them.
- A generated lesson is asked for three. One that cannot be used is dropped; it is never a
  reason to write the lesson again.

### Practice asks for what the evidence lacks

`learner_model/practice.py` chooses, in order: a question that would show a suspected mistake; a
question in a new situation, if none has been answered correctly; a kind of question not yet
answered correctly; then whatever has gone unseen longest. Variety counts when all else is
equal. Answers go through the same `lessons.answer` as in a lesson: there is one scoring path.

### The next step is decided by rules a learner could argue with

`learner_model/next_step.py` returns one recommended step, up to three alternatives, and
sometimes a note. In order of concern: an explanation the learner asked for and has not opened;
finishing what was started; something going wrong; a review that is due; a suspicion worth one
question; the next concept, with practice beside it; and, when nothing is worth doing, saying so
and when there will be something.

- Every step has a reason in one or two sentences. No rule reads the estimate; the inputs are
  states, counts, and dates. No reason contains a score (a test checks every reason).
- **Never the same lesson again after it did not work.** After three misses in the last four
  answers, or when the learner says an explanation did not help, the policy looks at what the
  concept builds on, then at another explanation (one already there, else a new one in a way of
  teaching not used yet), and says that stopping for today is fine. Going through a finished
  lesson again is offered last, and not at all in those cases.
- **Bounded.** A concept has at most four lessons; the fifth is refused with a reason. A
  suggestion that needs a key the learner has not set up is never placed before one that can be
  done, and says what it needs.
- Practice is suggested only for what practice can supply right now. If all that is missing is a
  check that no fresh question can make, the policy says the concept needs time.

### "This did not help" is an event, and it is believed

- It is stored with the part it was said about. It demotes the lesson it was said in, and puts
  another explanation first, until there is one, or until a question on the concept goes well
  without help.
- In the lesson it opens ways forward: skip to the next question (what is skipped stays open),
  another explanation in a chosen way of teaching, or something else. None of them is the same
  content again.

### Learner events

`learner_events` is append-only and holds what the learner did that is not an answer: a
hypothesis set aside, an explanation reported as unhelpful, a lesson finished (the progress row
moves on when a lesson is reopened, so "when was it finished" would otherwise be lost). Only
events with a reader are stored.

## Deviations from PLAN.md

- **No model-proposed hypotheses.** PLAN.md 8.3 allows a model to propose a hypothesis with
  evidence and confidence. Here a hypothesis comes only from how a question was written (which
  mistake each wrong option points at) and from deterministic scoring. It costs no requests,
  sends no answers anywhere, and can be replayed. A model's proposal could be added later as one
  more source of "suggests" on an attempt.
- **No model grading of open answers.** An "explain in your own words" answer is compared by the
  learner against a sample answer and a rubric, and recorded as lighter evidence. Grading by the
  model would send the learner's own words to the provider and cost a request per answer.
  Self-assessment against a rubric is bounded by that rubric, which is what M6 asks for.
- **"Likely guess" is not a kind of mistake.** It is what "I am not sure" and the question's
  guessing odds already measure, and it says nothing about the idea.

## Consequences

- Hypotheses, practice, and the next step are recomputed on every request from attempts and
  events. For a course of ordinary size that is a few queries and a fold; if it ever shows up in
  a profile, the place to cache is `LearningService._pictures`.
- A schema change: revision `0005` adds columns and rebuilds `learner_observations` (SQLite
  cannot widen a CHECK constraint in place). A test upgrades a database with data across it.
- The quality of adaptation depends on how well wrong options are tagged. The sample course is
  tagged by hand; generated lessons are asked to tag, and an unknown tag is dropped.
