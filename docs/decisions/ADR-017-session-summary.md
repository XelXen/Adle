# ADR-017: A session is a sitting, read off the record

- **Status:** Accepted
- **Date:** 2026-11-19
- **Builds on:** ADR-009 (knowledge as a record and four states), ADR-014 (adaptation).

## Context

The plan's journey ends with a session summary: "show demonstrated concepts, areas that need
more evidence, and planned review. Provide a clear Continue action."

Nothing in Adle is a session. The learner never starts one and never ends one, and asking
them to would be ceremony. What exists is a record: answers with the time of each, lessons
finished, the state of each concept and why, and the reviews that are planned.

Two risks came with the feature. A summary of "how the session went" slides easily into a
score, which Adle does not show. And "demonstrated" must never be something one sitting can
grant, since no single answer and no single day establishes anything.

## Decisions

- **A sitting is computed, never stored.** It is the latest run of activity on a course with
  no pause in it longer than 45 minutes (`learner_model/sitting.py`). Activity is answers,
  skipped questions, and lessons finished. Like a hypothesis about a mistake (ADR-014), it is
  worked out from the record each time, so it cannot disagree with it and needs no migration.
- **While the learner may still be in it, it is "This session"; afterwards it is "Last time",
  with the day.** The same account serves someone finishing and someone coming back, who
  wants to be reminded where they left off.
- **Answers are read from the observations**, which hold what was counted as evidence, not
  from the attempts. So an answer that counts in full in a summary is exactly one that counts
  in full for the state of a concept.
- **What a sitting showed is a count of right answers per concept.** Wrong answers are not
  listed and not counted: they showed nothing, and nothing is held against the learner. A
  right answer that did not count in full (after a hint, when unsure, marked by the learner
  themselves, or to a question just seen explained) is still a right answer; it is said to be
  "lighter evidence", the term already used when an answer is recorded, with one sentence
  underneath saying what that means.
- **"Demonstrated" is only ever reported as the state the concept is in now**, by the usual
  criteria over everything recorded. A sitting cannot grant it.
- **What still needs evidence is said in the words the concept's own row uses** (the
  `missing` list from `learner_model/mastery.py`), and a planned review is the concept's own
  review date. The summary adds no judgement of its own.
- **It is shown on the Learn tab, under the suggested next step.** That step is the "Continue"
  the plan asks for. There is no separate summary screen and no button to end a session; the
  end of a lesson and the end of practice keep their own, narrower accounts and lead here.
- **The look back is bounded** (the latest 600 answers and lessons finished), so opening a
  course does not read everything ever answered in it.

Fixed on the way: a right answer to an explain-in-your-own-words question was described as
"you said you were unsure", because self-marked answers are recorded as unsure. It now says
that the learner judged their own explanation, and that this counts as lighter evidence.

## Consequences

- A learner who works for five minutes, stops for an hour, and comes back has two sittings.
  The first is then no longer shown anywhere; the concepts' own rows still hold everything.
- Activity dated in the future (the clock was changed) is ignored, or a sitting would never end.
- Work on a concept that has since been removed counts in the totals and has no line.
- Tests: `test_sitting.py` (the rules, including a property test over arbitrary records),
  `test_session_summary_api.py` (what is gathered, the same words as the concept's row, no
  score), `learning.test.ts` (the sentences), and `e2e/learning.spec.ts` (this session, last
  time two days on, and a new sitting replacing it).
