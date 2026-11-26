# ADR-077: A film uses every request at once but one

- **Status:** Accepted
- **Date:** 2026-11-26
- **Changes:** ADR-068 in how many chapters of a film are written at once: from three at
  most to as many as the provider takes requests at once but one, and five at most.
- **Keeps:** ADR-068 (each provider's own limits; the film maker checks one chapter at a
  time), ADR-076 (each chapter at work says what it is doing).

## Context

The owner, on 2026-11-26: "if there are 6 concurrencies available, why just using 3 for
film mode? use 5 and retain one in case he wants to study lessons till then".

NVIDIA takes six requests at once (ADR-068), and a film wrote three chapters at once: half
of what the provider allows sat unused through an hour of work, while nothing kept a
request free for the learner, who may go on studying while the film is made.

## Decisions

1. **A film writes as many chapters at once as the provider takes requests, but one**
   (`chapters_at_once`): five at NVIDIA. The one left is the learner's, for a lesson, a
   question, or a check of a key while the film is made.
2. **Never more than five at once**, whatever a provider takes: each chapter is minutes of a
   model's work and waits its turn at the film maker, which checks one at a time.
3. Where the provider takes one request at a time (AIHubMix), chapters are written one at a
   time, as before.

## Consequences

- A film of many chapters is written sooner at NVIDIA; the film maker, which still checks
  one chapter at a time, is more often what chapters wait for, and each says so on its own
  line (ADR-076).
- What else is written while a film is made (a lesson, its pictures, the pages of a file)
  shares the request left, and waits its turn for it.
