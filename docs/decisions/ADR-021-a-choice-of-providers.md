# ADR-021: A second provider, chosen by the learner; a provider's next model when its first is not available

- **Status:** Accepted
- **Date:** 2026-11-20
- **Builds on:** ADR-012 (the provider client, the quota, and generation as jobs), ADR-020
  (a provider's own notice).
- **Changes:** ADR-012's "one provider, one model". Everything else in it stands.

## Context

Until now Adle could send requests to one place: AIHubMix's `coding-kimi-k3-free`. By
2026-11-20 two keys had been tried there and the model had not answered once (a relay error
for one account, a notice that the account must be topped up for the other; ADR-020).

The owner asked for NVIDIA NIM to be supported **alongside** AIHubMix, with a key of its
own, using Kimi K3.1 Pro, "and fall back to Mistral Large 4 if Kimi is not available, and
after that to GLM 5.3 Flash".

Two things in the operating contract bear on this and are not relaxed:

- *Never silently switch provider or send user data elsewhere.*
- *No new external service without an ADR and a disclosure in the interface.*

This is that ADR.

## What was measured

Against `https://integrate.api.nvidia.com/v1/chat/completions` on 2026-11-20, with the
owner's key, identifying as `Adle`. Nothing here is from a test: no test may call a real
provider.

| | Kimi K3.1 Pro | Mistral Large 4 | GLM 5.3 Flash |
|---|---|---|---|
| Name in a request | `moonshotai/kimi-k3.1-pro` | `mistralai/mistral-large-4-1t-a52b` | `z-ai/glm-5.3-flash` |
| A one-line question | answered in 36–42 s | answered in 11–24 s | no line in 180 s, streamed or not |
| Reports tokens used | yes, when `stream_options` asks | not documented | not documented |
| A way to ask for JSON | not documented | not documented | not documented |
| Thinks before it answers | yes (`reasoning_content`) | yes | not seen |
| `reasoning_effort` in its reference | `low` (default), `high`, `max` | `none` (default), `high` | not listed |
| `reasoning_effort` in fact | left out: thinks for minutes. `low`: works | `none`: HTTP 400. Left out: thinks for minutes. `low`: works | not tried |
| One lesson's text (about 12,000 characters) | 5.5–6 minutes with `low` | 7.5 minutes with `low` | not tried |

- A model the endpoint does not have: HTTP 404 with the plain text `404 page not found`,
  in a quarter of a second.
- No rate-limit headers, and no published daily limit for these models.
- **A reference is not the endpoint.** Kimi's lists `low` as the default effort. Asked for
  a lesson without the field, it thought for more than eight minutes (39,000 characters)
  without writing a word, and in the first whole attempt it was still going at the
  fifteen-minute limit. With `"reasoning_effort": "low"` sent, as the request printed in
  the reference itself does, it thought for a minute and a half and then wrote. Mistral's
  lists `none` and `high`: `none` is refused, leaving the field out behaves like Kimi
  without it, and `low`, which the reference does not list, is accepted and works.

## Decisions

### Which provider

- **There are two providers, and the learner chooses one** in Settings → AI provider.
  AIHubMix is the one in use until they choose otherwise. Nothing else changes it: not a
  failure, not a missing key, not a quota that has run out. A provider that cannot be used
  says so and the learner decides.
- **The choice is not changed while something is being written.** A job was started with a
  provider named beside the button; it must not finish at another. The core refuses
  (`409`), saying who is writing and what to do.
- **The choice is kept by the main process**, beside the keys and encrypted with them, and
  handed to the core after each start, as the keys are. It is not in the database: a copy
  of the data carries neither a key nor a preference that only makes sense with one.

### Whose key goes where

- **A key belongs to one provider.** The core holds one per provider
  (`CredentialVault`), and each provider's client asks for its own and no other. With an
  AIHubMix key and no NVIDIA key, a request to NVIDIA is refused before anything is sent.
- **A key is kept with the address it was given for** (`ProviderKeyStore`). The main
  process learns each provider's address from the core, never from the page, stores the
  key under provider and address, and hands it back only for that pair. A developer who
  points "NVIDIA" at another address (below) is not handed the real NVIDIA key for it.
- **The page names a provider and nothing more.** `window.adle.provider.setApiKey`,
  `clearApiKey` and `select` take a provider's name, checked against a fixed list in the
  main process. There is no argument through which a page could say where a key is sent.
- The earlier single key is read as AIHubMix's key for AIHubMix's address, which is what
  it was.

### Which model

- **A provider lists its models in order.** NVIDIA's are Kimi K3.1 Pro, Mistral Large 4,
  GLM 5.3 Flash, as the owner asked. The first is the one asked.
- **The next is asked only when the one before is not available.** That means one of:
  - *gone*: the provider says there is no such model (HTTP 404 or 410);
  - *failing*: the provider reports an error of its own (HTTP 5xx, or an error in the
    middle of an answer);
  - *silent*: no line for three minutes, or no finished answer in fifteen;
  - *refused*: the model will not take the request (HTTP 400 or 422). Each model is sent a
    request made for it alone, so one model's refusal says nothing about the next. This is
    not hypothetical: Mistral Large 4 refuses a value its own reference lists.
- **These do not move on, and nothing else is asked:** a key that is refused (401, 403),
  being told to slow down (429: waited out and asked once more of the same model, as
  before), a provider's own notice (ADR-020), and not reaching the provider at all. The
  next model is behind the same key, the same account and the same connection; it would
  fail the same way, and a request would be spent finding that out.
- A provider with one model has nothing to move on to, and fails exactly as it did before.
- **This is not a change of provider.** The request goes to the same service, at the same
  address, under the same key and the same terms. The models and their order are shown
  where the learner chooses the provider, before anything is sent, with what the order
  means. That is why it does not ask each time.
- **A stand-in is never left unsaid.** It is said while it happens, in words that fit the
  reason ("Kimi K3.1 Pro is not available at the moment. Asking Mistral Large 4 instead"),
  and afterwards with the thing that was written: the job's record says which provider and
  which models wrote it (`written_by`), a lesson's notes carry a sentence about it, and
  the review of suggested concepts names its author.
- **A model that was passed over is left alone for ten minutes**, then asked first again.
  The rest of one lesson does not find out the same thing three more times; the model the
  learner was promised comes back the same evening. It is kept in memory only.
- **When every model is resting, one is asked: the one that has rested longest.** A
  request then costs one attempt and not three, and trying again asks a different one, so
  the first to come back is found.
- Every attempt is a request: counted, written down with its provider and model, and held
  to the same limits. The number of requests a job may make is otherwise unchanged
  (ADR-012).

### What is sent

- **Each model is sent only the fields its own reference lists.** Kimi: `stream_options`
  (so that it reports tokens) and `reasoning_effort`. Mistral: `reasoning_effort`. GLM:
  neither. None lists a way to ask for JSON, so none is sent `response_format`; the prompt
  asks, and the answer is read leniently. No sampling parameters, as before.
- **Both thinking models are sent `"reasoning_effort": "low"`.** For Kimi that is its
  documented default, which is not what it does when the field is left out. For Mistral it
  is the one value Adle sends that a reference does not list: the listed way to say the
  same thing is refused, and without the field the model does not reach its answer in the
  time a learner will wait. It is written down beside the model in `provider.py`. If the
  endpoint stops accepting it, that model refuses its request and the next is asked.
- **`max_tokens` has a floor of 16,384 for the models that think**, the figure in their
  references. Their thinking counts in it, and a small bound ends before the answer begins.
- A model's thinking is counted and never kept, read, shown or logged. Where the provider
  does not report tokens, the estimate includes it.

### Limits

- **Each provider is counted alone**, against its own limits (`model_usage.provider`,
  revision 0006). What was sent to one is not held against the other.
- **NVIDIA publishes no daily limit for these models, so Adle's are its own**: 4 requests
  a minute, 200 a day, 3,000,000 tokens a day. They exist so that a mistake cannot run
  away with an account. The interface says they are Adle's and not NVIDIA's.

### Long answers

- **What a model is doing is said while it does it**: "Writing the lesson: Kimi K3.1 Pro
  is thinking it through", then "is writing". A model that thinks for a minute and a half
  must not look like a job that has stalled.
- **"Stop" and the time limit are checked on every line that arrives**, including a
  model's thinking and a provider's keep-alive lines. Before, they were only checked when
  a piece of the answer arrived, which for these models is minutes into the request.

### For development and tests

- `ADLE_PROVIDER_ENDPOINTS` (a JSON object from provider name to address) moves known
  providers to other addresses before launch. Each then carries the address in its name
  ("NVIDIA NIM (custom endpoint 127.0.0.1)") wherever it is shown. The end-to-end suite
  uses it to stand two servers on this computer in for the two providers.
  `ADLE_PROVIDER_BASE_URL` still replaces the whole choice with one endpoint, as before.

## What the first lessons from a real model showed

On 2026-11-20 Kimi K3.1 Pro, through Adle's own generation service, wrote a lesson on
activation functions (nine segments, three checkpoints, two scenes) and a twelve-concept
curriculum for a course on conditional probability. It was the first time any real model
answered Adle. Two things were wrong, and neither was the model's understanding:

- **The first draft of the lesson was refused as "not valid JSON".** It wrote
  `$\operatorname{step}(z)$` where JSON needs `\\operatorname`. The same draft held
  `\frac`, which *is* valid JSON: a form feed followed by "rac". Read strictly, a good
  lesson is refused; read naively, its mathematics is silently destroyed. The reader now
  mends the backslashes of TeX before it parses (`mend_backslashes` in `drafts.py`), and
  the prompt says how to write them. The draft that was refused is now read whole.
- **One scene painted a curve as a solid shape.** It showed and hid a plotted curve with
  `set_opacity`, which also sets the fill. The scene guide now says to use the stroke, and
  the end-to-end suite checks both the mistake and the remedy pixel by pixel.

Both scenes passed the static policy on the first try and ran in the isolated player in
both themes. The curriculum was one request and two minutes.

A second lesson, on gradient descent, was then asked for with the reader mended and the
guide corrected: two requests and under nine minutes, the draft and its one scene each
accepted as first written, and the scene ran in the player in both themes.

## Consequences

- A request leaves the computer for one of two companies, and which one is the learner's
  decision, shown in Settings and named beside every control that sends something.
- A lesson may be written by a different model than the one named first. The learner was
  told that could happen, is told while it happens, and can read afterwards that it did.
- These models are slow: minutes for a lesson, not seconds. Adle says what the model is
  doing and leaves the rest of the app usable; it cannot make them faster.
- With a silent first model, falling back costs the wait: up to three minutes of silence or
  fifteen minutes in all before the next is asked. Ten minutes of rest keeps that to once
  per sitting in practice. If Kimi proves to be away more often than not, the order is one
  line in `provider.py`, and it is the owner's to change.
- "Stop" still waits for the provider's next line, at most three minutes. Closing a
  connection from another thread is not dependable across platforms, and it was not worth
  a second thread per request.
- What a provider's reference says and what its endpoint does can differ in both
  directions, and may change without notice. A change shows up as a refused request or as
  a model that no longer finishes; both move on to the next model and are said. The notes
  beside each model in `provider.py` record what was seen and when.
- Two providers' terms now apply instead of one. Adle links to each provider's own page
  and summarises neither.
- Tests: `test_provider_choice.py` (the catalogue; the exact body each model is sent; a
  key only at its own address; what counts as not available and what does not; the next
  model, the rest, all resting; each provider counted alone; "stop" and the time limit
  while a model only thinks; what a model is doing; the API; a lesson through NVIDIA with
  the first model away), `test_drafts.py` (TeX with one backslash or two; the draft a real
  model sent), `test_database.py` (revision 0006), `local-state.test.ts` (keys by provider
  and address; the earlier single key), `providers.test.ts` (what a freshly started core
  is handed), `provider-model.test.ts`, `generation.test.ts`, `e2e/providers.spec.ts` (two
  servers: nothing reaches the provider that was not chosen; the stand-in is said; the
  choice and both keys survive a restart; a key is not handed over for another address;
  the page cannot name an address), and `e2e/scene-player.spec.ts` (a curve by its
  stroke). Nineteen rules were each removed in turn and a test was seen to fail.
