# ADR-076: Each chapter of a film at work says what it is doing

- **Status:** Accepted
- **Date:** 2026-11-26
- **Changes:** ADR-065 and ADR-068 in how a film being made says where it stands: the job's
  one line says how many chapters are written, and each chapter being made has a line of
  its own.
- **Keeps:** ADR-068 (up to three chapters written at once, where the provider takes several
  requests at once; the film maker checks one at a time), ADR-037 (what long work is doing
  is said in the learner's terms, never its words).

## Context

The owner, on 2026-11-26: "for the film if multiple tasks are being done at once — why just
one progress text? i want to see progress on all of them".

Since ADR-068 up to three chapters of a film are written at once at NVIDIA. Each told the
job what it was doing, and the job had one line: the Film tab showed whichever chapter had
spoken last ("Checking chapter 2 of 8", then "Writing chapter 3 of 8: Kimi K3.1 is
thinking"), and the chapters' list said only "Being written" for each of the others.

## Decisions

1. **Each chapter being made has a line of its own.** It works through its own view of the
   film's job (`_ChapterContext`): stopped when the job is, and what it says is kept as its
   line (`_AtWork`), in a few words, the chapter going without saying: "Writing: Nemotron 3
   Ultra is thinking", "Waiting for the film maker", "Checking it in the film maker",
   "Looking over its pictures", "Mending it (1 of 3)", or a wait for the provider's limit.
   Its line goes once it is written or told in words.
2. **The job's own line says how many chapters are written** ("Writing chapters: 2 of 8
   done") while chapters are made; what comes after them (the voice, the film put together,
   the video) is said as before.
3. **The lines travel in the job's progress** (`JobProgressDetail.chapters`: each chapter's
   number, what it is doing, and its stage), so nothing is written to the database for
   them and nothing is left of them once the job ends. The Film tab shows each in that
   chapter's row of the list (`chaptersAtWork` in `lib/films.ts`), in place of "Being
   written".
4. **Waiting for the film maker is said**: a chapter whose turn has not come, because the
   film maker checks one chapter at a time, says so, where before it went on saying what it
   did last.

## Consequences

- With chapters written one at a time (AIHubMix, or one endpoint), there is one line at a
  time, in the chapter's row, and the count above.
- Every step a chapter takes is still one report of the job's; the lines are said together
  each time, so the page never shows half of them.
