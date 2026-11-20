# ADR-023: "Automatic": every provider the learner has a key for, each for what it is good at

- **Status:** Accepted
- **Date:** 2026-11-20
- **Supersedes:** one sentence of ADR-021, "the learner chooses the provider and nothing else
  does", in the one case described here. Everything else in ADR-021 stands: a key goes only
  to the provider and the address it was given for; a provider's next model may stand in for
  its first; every stand-in is said; each provider is counted alone.

## Context

The owner has keys for both providers and described them: AIHubMix answers quickly and allows
little in a day; NVIDIA NIM answers slowly and allows a great deal. They asked that, when both
are present, Adle use the best qualities of both.

PLAN.md 6.3 and PROMPT.md 6 say: "Never silently use another provider or send data to another
service. Any provider change requires explicit user configuration and disclosure." ADR-021
met that by having exactly one provider in use. Using two together has to meet it too, and
not by quietly dropping it.

## Decisions

- **The learner's choice is one provider, or "automatic".** It is a setting they can see and
  change (Settings → AI provider → "Which provider to use"), kept by the main process with the
  keys and handed to the core at every start. Nothing else changes it.
- **Automatic uses only providers the learner has given a key to.** Giving a provider a key
  is the consent to send it text; a provider without a key is never contacted, in any mode.
  With one key, automatic is simply that provider. A new installation starts on automatic.
  A learner who chose one provider under ADR-021 keeps that choice: if they have keys for
  both, the settings *offer* to use both, with a button, and do nothing by themselves.
- **Who gets what** is decided by pure rules (`generation/routing.py`), from two facts about
  each provider (`quick`, and whether it publishes a small daily limit) and from Adle's own
  count of the day:
  - what the learner sits and waits for (a question during a lesson, a list of suggested
    concepts, a check of a key) goes to the quick provider, as long as it has any allowance
    left;
  - long work (a lesson, a picture) goes to the quick provider too while less than half of
    its day is used, and to the roomy one after that, so that the quick one always has
    something left for what is waited for;
  - if the provider asked cannot answer (down, refusing, out of allowance, rejecting its
    key, answering with a notice, unreadable), the next in the plan is asked. A provider
    that failed is asked second for ten minutes, not dropped.
- **With one provider chosen, none of that happens.** Its failure is the answer, and its
  allowance running out stops the work, exactly as in ADR-021.
- **It is said before, during, and after.**
  - Before: every control that sends something names where it will go in the words the core
    plans at that moment, including the provider that would be asked second
    ("Sends to AIHubMix, or NVIDIA NIM if AIHubMix cannot answer: …"). The settings show the
    plan for each kind of request, with the reason.
  - During: the job's progress says when one provider is passed over for another, and why.
  - After: what was written records every provider and model that wrote part of it
    (`written_by.authors`), and carries a sentence when the one asked first did not write it.
- **One request at a time at each provider**, where it was one at a time overall. Two
  providers are two accounts with two allowances; a question to one does not wait for a
  lesson being written at the other. Each provider still sees at most one request from Adle
  at once and at most four a minute.
- **A key can be checked** (`provider.check`): one request of a few words to one named
  provider, with nothing of the learner's in it. It never goes to another provider, and it
  counts as one request there.
- **An account that refuses is left alone for hours.** A provider that stumbles (down, slow,
  unreadable) is asked second for ten minutes. One whose key is rejected, or which answers
  with a notice about the account, is asked second for six hours, or until its key is
  changed or a check of it succeeds: seen for real on 2026-11-20, each try at such an
  account can be one of a handful it allows. A check that fails counts as having asked.
- **"Stop" is immediate.** A request is made on a thread of its own; whoever asked is told
  the moment the learner stops it, however silent the provider is, and the connection is
  let go the next time anything arrives on it. ADR-021 had left this waiting for the
  provider's next line, which with a model that thinks first could be minutes.
- **What to expect of a wait** is told from what was measured on this computer (the middle
  of the last few answers of that kind at that provider, `model_usage.seconds`), and from
  what is usual for the provider before anything has been measured.

## Consequences

- A request may now go to either of two companies. That is only true after the learner has
  given both a key, and it is never unsaid. The welcome and the privacy settings say "a
  provider you have given a key to" where they said "the one provider you choose".
- The disclosure beside a control is a promise about a plan that can change before the
  request is sent (the quick provider passes half of its day). The sentence names every
  provider in the plan, so it stays true whichever is asked first.
- One lesson can be written by two providers (its text by one, a picture by the other).
  Both are recorded, and the note says so when it was not planned.
- `quick` is a fact written into the provider's definition, from what the owner reported for
  AIHubMix and what was measured for NVIDIA. AIHubMix's model has still never answered Adle
  (ADR-020); if it turns out slow, that one word changes.
- The API contract changed: `provider.select` takes `{selection}`; `provider.status` gains
  `selection`, `routes`, and per-provider `usage`, `quick`, `in_use`.
