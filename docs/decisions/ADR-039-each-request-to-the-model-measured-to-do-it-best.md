# ADR-039: Each kind of request goes to the model measured to do it best

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** ADR-023 in how "automatic" orders the providers (quick first for what is
  waited for, long work moved once half the quick one's day is spent). Its rules about
  keys, choice, stand-ins and saying where a request goes stand. ADR-021's one order of
  NVIDIA's models for every request.

## Context

NVIDIA's models were asked in one order for everything: Kimi K3.1 Pro, then Mistral Large 4,
then GLM 5.3 Flash. Kimi thinks for a minute or more before its first word: a question in
the middle of a lesson took over a minute to answer, a lesson four to six. In "automatic",
AIHubMix was taken to be the quick provider and was asked first for what the learner waits
for. It has not yet answered a request on this computer (its account needs a top-up), and
its one model, Coding Kimi K3, is a model for code with a small daily allowance.

The owner: "arrange the speed of models (benchmark them all) for different tasks … keep
Kimi for coding only, so this way AIHubMix also stays less busy, and also since it's slow."

On 2026-11-21 every model NVIDIA lists for chat was asked, through Adle's own prompts, for
each kind of request, once each (`docs/engineering/PERFORMANCE.md`). What was usable, and
how long it took:

| Request | Nemotron 3 Ultra | Nemotron 3.5 Super | Kimi K3.1 Pro | Others |
|---|---|---|---|---|
| A question | 8 s | 7 s | 66 s | Laguna XS 2 s (a wrong statement in it); Mistral 144 s; GLM 151 s |
| Suggested concepts | 30 s | 39 s | 123 s | Laguna XS 14 s |
| A lesson's words | 113 s | not usable, twice | 254 s | Laguna XS not usable |
| A scene file | 20 s | empty | 134 s | Laguna XS 9 s |

## Decisions

- **Within a provider, each kind of request has its own order of models**
  (`ProviderConfig.orders`, `models_for(purpose)`). The first is the one measured to do it
  well and soonest; the rest stand in, as before, and that is said. NVIDIA:
  - questions and key checks: Nemotron 3.5 Super, then Nemotron 3 Ultra (then Kimi);
  - suggested concepts: Nemotron 3 Ultra, Nemotron 3.5 Super, Kimi, Mistral;
  - a lesson's words: Nemotron 3 Ultra, Kimi, Mistral;
  - a picture: Kimi K3.1 Pro, then Nemotron 3 Ultra. Pictures are drawn after the lesson
    can be started (ADR-031), so a slower model costs the learner no wait there, and each
    is tried before it is shown (ADR-038).
  GLM 5.3 Flash is no longer one of NVIDIA's models in Adle: it was the slowest to answer
  anything, when it answered at all.
- **Across providers, in "automatic", each provider says what it is asked first for**
  (`ProviderConfig.first_for`): AIHubMix the pictures, its model being made for code, so
  that its small allowance goes on them alone; NVIDIA everything else. The other provider
  stands in when the first cannot answer, as before. With one provider chosen, that one
  does everything, with its own orders.
- **Settings says which model writes each kind of request**, pictures included ("Current
  routing"), and what each provider is for with "Automatic". The new models are sent only
  the fields every request has, which is how they were measured.

## Consequences

- With NVIDIA alone or first, a question is answered in about ten seconds instead of over a
  minute, suggested concepts in about half a minute, a lesson's words in about two minutes
  instead of four to six. Kimi's richer writing is given up for lessons: the owner asked for
  speed, and Ultra's lessons were usable and complete.
- AIHubMix is asked for nothing but pictures while NVIDIA has a key. Its speed is still
  unmeasured; until it is, the times shown for pictures are what is usual elsewhere.
- One run of each is a small sample, on one day, of a shared service. The orders are data in
  `provider.py` and are meant to be measured again (`scripts/dev/` holds the tools to do it
  by hand) and changed by a later decision.
