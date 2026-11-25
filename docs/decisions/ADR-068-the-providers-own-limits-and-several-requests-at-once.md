# ADR-068: The providers' own limits, and several requests at once

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-012 in how much Adle asks of a provider: the limits are now the
  providers' own, with no margin under them, and NVIDIA's are 40 requests a minute with no
  daily limit, where Adle had kept to 4 a minute, 200 a day and 3 million tokens of its own.
  ADR-021 and ADR-039 in "one request in flight at each provider": a provider says how
  many it takes at once (AIHubMix one, NVIDIA six), and a film's chapters and a file's
  pages are asked for side by side where it takes several.
- **Keeps:** ADR-012 (the number of requests a piece of work may send is fixed and said
  first: doing them side by side changes when, never how many), ADR-023 (where a request
  goes is the learner's choice), ADR-060 (a page is one request, at the learner's word),
  ADR-065 and ADR-066 (a chapter is asked for once, mended at most three times, looked over
  once).

## Context

The owner, on 2026-11-25: "nvidea nim has 40 requests per min limit, no cap for how many
requests tho so we can go for concurrent requests, no need for sequential and limiting...
and for aihubmix, 100, not 90".

Adle sent one request at a time to each provider and kept under limits of its own: for
AIHubMix just under the published ones (4 a minute, 90 a day, 900,000 tokens, against 5,
100 and a million), and for NVIDIA, which had published none to Adle, 4 a minute, 200 a day
and 3 million tokens, as a guard against a mistake running away with an account. A film of
a dozen chapters took two to four hours, nearly all of it chapters written one after
another (each five to eleven minutes); a notebook of twenty pages read from its pictures
took minutes at four a minute.

## Decisions

1. **The limits are the providers' own.** AIHubMix: 5 a minute, 100 a day, a million tokens
   a day. NVIDIA: 40 a minute and no daily limit; its day is still counted and shown in
   Settings, and nothing stops it.
2. **A provider says how many of its requests may be in flight at once** (`at_once` in
   `ProviderConfig`): AIHubMix one, whose day is small; NVIDIA six, room for a lesson, a
   question and a film's chapters together, far under its minute. A request is let in and
   counted as one step, so that several let in together cannot both take the last place in
   a minute; and work stopped while its request waited for its turn sends nothing.
3. **A film writes up to three chapters at once, and a file reads up to four pages at
   once**, where the provider asked first for them takes several requests at once; one at a
   time, in order, where it takes one. The film maker still checks one chapter at a time
   (the takes share the film's folder), and a page is still drawn on this computer one at a
   time. Each chapter being written says so; the first failure, or the learner's Stop, stops
   the rest, and a chapter being written then waits to be written again.
4. **Nothing else changes in how many requests a piece of work sends**, or where they go.

## Consequences

- A film whose chapters NVIDIA writes has up to three of them written at once. Its time
  should come down to about a third for the chapters themselves, and less where the film
  maker's checks of one chapter at a time are the longer part; this has not been measured
  with the real provider yet.
- A notebook's pages are read up to four at once, while the next is drawn here.
- On Windows, a file removed while a page of it is being drawn is held open a moment: its
  original is tried again for a few seconds as it is deleted, and one held longer is left
  for the next start, which now always deletes the originals no source refers to.
- A mistake that sends requests in a loop is no longer stopped by a daily cap at NVIDIA;
  each piece of work still has its own bound (ADR-012), and the count is shown in Settings.
