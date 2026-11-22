# ADR-044: Words are in American English

- **Status:** Accepted
- **Date:** 2026-11-22
- **Adds to:** ADR-028 (short, plain words about the learner's task), which said nothing of
  spelling.

## Context

Adle's words were written in British spelling: "Practise", "maths", "colour", "licence",
"Cancelled", and in the sample course "grey", "labelled" and "judgement". Nobody decided
that; it was how they happened to be written. The owner, looking at "Up next": "why does
it show 'Practise', it's Practice".

## Decisions

- **Everything a learner reads is in American English**: practice (the noun and the verb),
  math, color, gray, labeled, license, canceled, toward, judgment. That covers the
  interface, the main process's dialogs and notifications, the design system's components,
  every sentence the core can say, the sample course, and the labels of its pictures.
- **What the model writes is asked for in American spelling**: the writing rules every
  lesson, course plan and answer is asked with say so, and so does the request for a
  picture.
- **The API's own names keep their spelling**: a job that was stopped is `cancelled` and a
  step of practice is `practise`, as the contract and the database have them. They are
  identifiers, and a learner never reads them.
- **Two tests keep it so**: `renderer/src/wording.test.ts` reads every string and every
  piece of text in the interface, the main process and the design system, and
  `tests/unit/test_wording.py` every string of the core (by Python's own parser: comments
  and docstrings do not count) and every text of the sample course.

## Consequences

- A lesson written before this, or a sample course installed before it, keeps the words it
  was written with.
- The documentation for developers is not part of this and keeps its spelling.
- 0.1.0-alpha.2 was published with the British words; the next release has these.
