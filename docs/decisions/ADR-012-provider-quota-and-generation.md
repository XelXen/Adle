# ADR-012: The model provider, the quota, and how lessons are generated

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

M5 lets a learner ask an AI model for two things: a list of concepts for a course, and a lesson
for one concept. The provider is AIHubMix (`coding-kimi-k3-free`: 5 requests a minute, 100 a
day, 1,000,000 tokens a day per account, shared with anything else that uses the key). Model
output is the least trustworthy input the app handles, and every request spends an allowance the
learner cannot buy back.

## Decisions

### One module sends, one decides, one remembers

- `generation/provider.py` sends one OpenAI-compatible chat completion and reads the streamed
  answer. The key is read from the vault per request and placed in one header. Redirects are
  not followed; proxy and credential settings from the environment are not used; nothing from a
  request or a response is logged; an answer is bounded in size and time and can be abandoned
  between chunks.
- `generation/quota.py` is pure: given the requests already made and the time, it says
  *allowed*, *wait this long*, or *used up for today*. Defaults stay under the documented
  limits (4 a minute, 90 a day, 900,000 tokens a day). The day is counted in UTC because the
  provider does not say when its window resets.
- `application/model_gateway.py` joins them: one request in flight; a full minute is waited
  out (cancellably), not failed; a used-up day refuses before anything is sent; every request
  is written to `model_usage` **before** it is sent, so one that never returns still counts;
  a 429 is waited out and tried once more, and nothing else is retried.
- The interface shows the count as Adle's own estimate (`provider.usage`), never as the
  provider's balance.

### No sampling parameters

The provider's guide for this model family says sampling is fixed and should be left out of
requests. The client sends `model`, `messages`, `max_tokens`, `stream`, and (for JSON)
`response_format`. The model always thinks before it answers and that thinking counts as
output, so `max_tokens` is several times the size of the answer: 32,000 for a lesson, 16,000
for a scene or a curriculum.

### Where requests may go

`ADLE_PROVIDER_BASE_URL` and `ADLE_PROVIDER_MODEL` are developer configuration read at
start-up. Only `https` is accepted, or `http` on this computer (a local model, or the fake
provider in tests). Any endpoint other than the default is named as "Custom endpoint (host)"
wherever the provider is shown, so data never goes somewhere the learner was not told.

### The model writes a draft, not the Lesson IR

- A model is asked for a smaller, forgiving shape (`generation/drafts.py`): no identifiers, no
  bookkeeping, no references it could get wrong.
- A deterministic compiler turns the draft into the IR: it assigns every identifier, takes
  objectives from the curriculum, computes durations from the words, and resolves citations by
  the numbers the model was given. **A number that was not offered is dropped, so a citation
  cannot be invented.**
- Harmless formatting habits (Markdown emphasis, `\( \)` mathematics) are normalised. Everything
  else is judged by the IR's own validation, and the result is stored only through
  `parse_bundle` like any other lesson (ADR-010).

### A fixed, small number of requests

| Job | Requests |
|---|---|
| Curriculum proposal | 1, or 2 if the first answer was unusable |
| Lesson | 1 for the lesson (2 at most), then 1 per scene (2 at most each); at most 2 scenes |

- "Unusable" means it did not parse, compile, or validate. The second request says what was
  wrong, by place, **without quoting what the model wrote**. There is never a third.
- One scene is one request for one complete Python file. If the static policy refuses it, there
  is one more request with the policy's reasons. After that the segment loses its scene: a
  visualization or interaction becomes an explanation carrying the scene's description, and
  the job's result says so in a sentence. A scene asked to be interactive that came out as a
  plain animation is kept as a visualization.
- If the provider fails or the allowance runs out after the lesson is written, the lesson is
  kept without its pictures rather than thrown away.
- A lesson is validated before any scene is requested, so a lesson that would be refused never
  costs two more requests.

### A proposal is only a proposal

`generation.propose_curriculum` stores its result on the job. Nothing enters the course until
the learner picks (`generation.accept_proposal`), which adds the chosen concepts, their links to
each other, and their links to the materials in one transaction, through `CurriculumService`.
A concept may only need one listed before it, so a proposal cannot contain a loop. A proposal
can be found again after leaving the screen (`generation.latest_proposal`) or set aside
(`generation.dismiss_proposal`).

### Jobs know what they are about

`jobs.subject_id` (migration `0004`) records the concept or course a job concerns. Starting the
same work twice returns the job already doing it, and a screen can pick up work in progress
after navigation (`jobs.list_active`).

### Untrusted text stays quoted

Everything from the learner or their documents goes inside `<learner_material>` blocks, with a
standing rule in the system prompt that such text is information, never instructions. The tag's
name is broken inside quoted text so a document cannot close its own block. The model has no
tools: it can only answer.

### The scene guide ships inside the package

The scene writer is given the authoring skill and its examples. The core cannot read
`skills/` in a packaged build, so `npm run scene-guide` copies the relevant part into
`adle_core/generation/data/scene_guide.md`, and the gate fails if the copy drifts.

### Tests never reach the provider

Unit tests use an in-process transport (`tests/support/model.py`). End-to-end tests point the
app at a local HTTP server (`e2e/support/fake-provider.ts`). Both answer from the same fixtures
(`fixtures/model-answers/`).

## What the real provider did (2026-11-19)

Nine small requests were sent with the owner's key, from a script outside the repository. The
key works (`GET /v1/models` lists exactly `coding-kimi-k3-free`), but **every completion failed
at the provider** with HTTP 500 and
`do request failed: Post "https://***/coding/v1/messages": Bad Request` (`do_request_failed`):
on the OpenAI-compatible and the Anthropic-compatible endpoint, streamed or not, with and
without `temperature`, with the smallest possible body. The failure is in AIHubMix's own call
to its upstream, not in anything the request contains.

So the prompts have **not** been checked against the real model. The app reports this case as
"The AI provider reported a problem on its side", distinct from a network failure.

## Consequences

- A lesson costs three requests in the usual case and never more than six.
- A learner cannot be left with a half-made course or lesson: every job ends with something
  valid stored, or with nothing stored and a sentence saying why.
- The draft format is a second shape to maintain next to the IR. It is small, and its compiler
  is where every "the model got an id wrong" bug would otherwise have lived.
- Progressive playback (starting a lesson while its later parts are still being written, PLAN
  12.1) is not done: a lesson is one request, so there is nothing to stream in parts. The
  learner sees progress and can cancel.

## Not decided here

Model-assisted grading of open answers and misconception classification (M6); a user-facing
choice of provider or model; caching of generated lessons by input hash (PLAN 12.2), which
matters only once lessons are regenerated.
