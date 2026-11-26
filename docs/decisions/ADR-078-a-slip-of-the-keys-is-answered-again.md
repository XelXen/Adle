# ADR-078: A slip of the keys is answered again

- **Status:** Accepted
- **Date:** 2026-11-26
- **Changes:** ADR-010 and ADR-014 in how a typed answer is scored: one that misses an
  accepted answer by a slip of the keys is not marked wrong at once, and nothing of it is
  kept.
- **Keeps:** ADR-010 (the answer key stays in the core, and the core scores), ADR-014
  (evidence and what it means for the learner model), the rule that mastery is never
  marked from one answer and no answer is held against the learner as a score.

## Context

The owner, on 2026-11-26: "sometimes the user can make a mistake for filling answer — like i
did CH3CHWCH3 instead of CH3CH2CH3 — so for very minor or close mistakes, it allows for a
retry".

A short answer is right when, with case, accents, punctuation, spacing and a leading
article folded away, it is one of the accepted answers. Anything else was wrong, recorded
as evidence, and shown with the right answer: a W for a 2 cost the learner the question and
counted against what Adle believes they know.

## Decisions

1. **A near miss** (`scoring.near_miss`) is a typed answer within a slip of the keys of an
   accepted one, after the same folding: a character put in, left out, changed, or two
   swapped (optimal string alignment), one in an accepted answer of four characters or
   more, two in one of ten or more. Never in a shorter one, nor in one that is a number:
   there one character is the whole difference ("CH4" and "CH3" are two things). Only
   short answers: a number has its tolerance, and a choice has nothing to slip on.
2. **A near miss is told "Almost: check what you typed, and try again"** (`outcome:
   "near"`), with nothing of the answer, its explanation, or what it changed. Nothing is
   kept: no attempt, no evidence. The question stays open, the answer as typed, to be
   mended and checked again, and the answer that follows counts as a first answer.
3. **Once a sitting**: a second near miss of the same question within the time an
   explanation stays in mind (`FRESH_AGAIN_AFTER`) is scored as it is. That keeps a
   near miss from being a way to find the answer letter by letter. It is remembered by the
   core while it runs, and by nothing else.

## Consequences

- A typo no longer counts against the learner, and the right answer is not given away for
  one.
- A real mistake that is spelled close to the right answer ("propene" for "propane") is also
  given its second look, once; the answer after it is scored as it is.
- Practice and review, which answer through the same call, do the same.
