# ADR-037: Watching a lesson being written: its stage, its parts by title, and a clock

- **Status:** Accepted
- **Date:** 2026-11-21
- **Changes:** ADR-026 in one respect (below). Its rules about breaks and notifications
  stand.

## Context

A lesson takes a model one to four minutes to write: NVIDIA's Nemotron 3 Ultra wrote one
in 113 seconds and Kimi K3.1 Pro in 254 (`docs/engineering/PERFORMANCE.md`). A model that
thinks before it writes says nothing for the first half of that. The card that followed
the work showed a sentence ("Writing the lesson: Kimi K3.1 Pro is thinking"), a bar at
"Step 1 of 3" that did not move until the whole lesson had arrived, and how long it
usually takes. For minutes on end nothing on the screen changed.

The owner: "how do we show the user that AI is making progress and not stuck, without
showing raw tokens and stuff".

The answer arrives piece by piece already (the core streams it, ADR-012), and a lesson's
draft names the lesson first and then each part as it begins it. The titles are a
truthful measure of how far the writing has come, and they are words a learner would
want to see: what the lesson is going to cover. The rest of the answer is not: half a
sentence, a question before its answer key has been written, JSON.

## Decisions

- **The core says what stage long work is at**, beside its sentence and its count:
  `waiting` (for a turn, the rate limit, or another model standing in), `thinking`
  (the model has begun and is not yet writing), `writing`, or `drawing` a picture
  (`Job.progress_detail.stage`).
- **While a lesson or a list of concepts is written, the core reads the titles off the
  answer as it arrives** (`generation.Outline`): the lesson's own title, then each part's;
  or each concept's. Nothing else of the answer is read or kept there, and only keys
  are read: a quotation mark inside a sentence is escaped in JSON and is not a key. A
  title is one line of at most 120 characters, and there are at most 40. When another
  model takes over, the titles start again with it.
- **The client hands each piece of the answer to whoever asked for it as it arrives**
  (`on_piece`), never any of the model's thinking, and nothing once the request has been
  given up.
- **The card says what is happening in the learner's terms** ("Planning the lesson",
  "Writing “How a neuron weighs its inputs”", "Choosing concepts"), not the model's. Where
  the core's own sentence is the news (a wait for the rate limit, a model that is away and
  the one asked instead), that sentence is shown as it is. Who wrote the lesson is said
  afterwards, as before.
- **The parts written so far are listed under the bar** by their titles, each ticked when
  the next has begun, the one being written marked as the present step. A screen reader
  hears each title once, as it arrives.
- **The bar counts parts, not minutes.** While nothing can be counted (waiting, thinking)
  it moves without a measure; it is never an empty bar standing still. While words are
  written it moves on a little with each part and never reaches the end by itself; a
  clock would be a guess, and a part that exists is a fact.
- **A clock moves beside the headline** (minutes and seconds since the work was asked
  for). It is not read out: the bar and the list say how far the work has come.

## Consequences

- A long wait looks like what it is: work going on. The learner sees what the lesson will
  cover before it can be started, and can still take a break, as ADR-026 offers.
- ADR-026 said the wait is said honestly beside a break. It still is, with "Step 1 of 3"
  gone: the step count was the job's own bookkeeping (one request for the words and one
  for each picture) and read as a measure it was not.
- A model that does not stream, or a provider that sends the answer in one piece, shows
  the stage and the clock and no titles until it is done. Nothing pretends otherwise.
- The fake provider used by the journeys can answer the way such a model does
  (`{ slowly }`: thinking first, then one title per piece); `e2e/generation.spec.ts`
  watches a lesson take shape with it.
