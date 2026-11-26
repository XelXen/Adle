# ADR-072: A lesson takes the time a concept needs

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-061 (the rules of every lesson gain three: a child could follow it, it is
  summed up along the way, and it goes from the examples to the general idea), ADR-010 (a
  lesson has at most 20 parts, from 14).
- **Keeps:** ADR-048 (a lesson is written as one request and can be begun at its first
  part), ADR-049 and ADR-050 (a slideshow; the case before the rule).

## Context

The owner, on 2026-11-25: "the ai should in between give summaries of what's done up till
now, not hurry stuff, no one would mind if the lessons are longer, it should be good tho,
like it should explain the concept clearly to even a child: examples, intuition, animations,
summaries, generalisations, etc. we're not trying to hurry the syllabus, we are trying to
make the user understand the depth behind it and not miss a part."

A lesson was asked for in 6 to 9 parts, 2 to 4 beats each, with three questions. Written
that short, a concept with several ideas in it was hurried: a step left to be guessed, a
word used before it was explained, and nothing that said where the learner had got to.

## Decisions

1. **A lesson is asked for in 10 to 16 parts**, with 2 to 5 beats a part and 3 or 4
   questions along the way, and may have up to 20 (`MAX_SEGMENTS`). The writer is told
   that there is no hurry: a lesson is as long as the learner needs to understand the
   concept in depth, and nothing of it is skipped.
2. **Three rules of every lesson** (`lessons/axioms.py`), which the learner can read with
   the others:
   - *Explained so that a child could follow, and nothing skipped*: every step said, every
     new word explained the first time, an everyday example or comparison wherever it
     helps, the intuition before the formal statement.
   - *Along the way, a short summary*: a summary part after every three or four parts of
     new material, saying what has been learned so far and how it fits together, its
     picture bringing back what was shown; and one of the whole lesson at its end.
   - *From the examples to the general idea*: before the end, what holds beyond the
     examples and why, where it stops holding, and one new case that shows it.
3. **Nothing else changes in what a lesson costs**: it is still one request, read part by
   part as it arrives, and begun at its first part.

## Consequences

- A lesson takes longer to write and to hear. Its first part still comes as soon as it is
  written, so the wait to begin is no longer than before.
- Summaries give a learner who stops in the middle a place to come back to.
- A model that writes fewer parts is not refused: the shape is asked for, and the rules
  say why.
