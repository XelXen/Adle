# ADR-079: A film opens on an index, and its voice breathes between lines

- **Status:** Accepted
- **Date:** 2026-11-26
- **Changes:** ADR-065 in what a film opens with, and in how one line of its voice follows
  another.
- **Keeps:** ADR-065 (the files around a chapter are Adle's, and Adle's own chapters pass
  the same policy as a model's), ADR-042 and ADR-051 (a natural voice records each line,
  and what is said never changes once it is written).

## Context

The owner, on 2026-11-26: "introduction of the film could be better — if there are too
many chapters, it sometimes overflows or the voice looks like a psychotic being that keeps
saying them out, just show the index properly and that should be fine", and "sometimes the
voice looks like it was poorly stitched — like normal voice and suddenly no gap to another
clause … like when stitching audios — give em some space … make it natural".

The opening was a chapter in words (`plain_chapter`) whose points were the film's
chapters, up to five to a line: each line said and shown. A long course's titles were run
together a dozen to a line, read out in full, and wrapped to as many rows as they took,
past the foot of the stage.

Each line of a film is recorded alone, and the engine plays a chapter's lines one after
another, each as long as its recording. A voice ends a recording with its last word, so
each line began the instant the one before it ended.

## Decisions

1. **The opening shows the chapters as an index** (`script.opening_chapter`): the
   course's name, then the chapters numbered, up to ten to a column (`INDEX_ROWS`) and two
   columns to a screen (`INDEX_COLUMNS`), each column one `Paragraph`, so that its entries
   stand on one grid of lines whatever letters they hold. Past twenty, the index turns to
   its next screen, each held long enough to read (0.4 s an entry, two to eight seconds).
   Every screen is set at one size, the largest at which each fits the room under the
   name (`_INDEX_ROOM`). A title too long for its column is cut at a word, with an
   ellipsis.
2. **It is said in two lines, never chapter by chapter**: "This film goes through
   <course>, in <n> chapters." and "Here they are, in order." The course's name is made
   something a voice can say before it goes into the line, so that what is taken out of it
   takes nothing of the line with it; a name with nothing left to say is "this course".
3. **Every line of a film's voice is followed by a breath**, in the voice module Adle
   writes (`script.voice_source`): 0.45 s after a line that ends a sentence (in `.`, `!`,
   `?`, `:` or an ellipsis, before any closing quote or bracket), 0.25 s after one that
   does not (`SENTENCE_REST`, `CLAUSE_REST`). A recorded line has that much quiet put
   after its sound; a line never recorded is quiet for as long as it would take to say,
   and the breath. When each word is said does not change: the breath comes after the
   last one.

## Consequences

- An opening fits whatever the number of chapters, up to `MAX_CHAPTERS` (60). Tried in
  the pinned film maker with seven and sixty: no layout problem in either; three screens
  for sixty, every one at one size.
- A long course's opening is two lines to hear, and a little longer to watch: up to eight
  seconds a screen of twenty.
- A film is longer by a breath a line: about five to nine seconds a chapter of a dozen to
  twenty lines.
- A lesson's narration is unchanged: each part is recorded whole, and a slide turns
  between parts.
