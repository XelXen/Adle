# ADR-020: An answer the provider wrote itself is recognised, shown in its own words, and not asked for again

- **Status:** Accepted
- **Date:** 2026-11-20
- **Builds on:** ADR-012 (the provider client, the quota, and generation as jobs).

## Context

The real provider was tried with a second key on 2026-11-20. The request on the model's own
documentation page came back with HTTP 200 and an ordinary, successful completion. Its text
was not the model's:

> Sorry, to prevent abuse of free resources, accounts that have not been recharged can only
> try 10 times. You can increase the free quota after recharging; https://console.aihubmix.com/topup

The response's identifier began `chatcmpl-fake`, it reported no tokens used, and asked for as
a stream it was a single chunk with no usage report at all.

Nothing in Adle recognised this. The text would have been taken for the model's answer,
found not to be a lesson, and asked for once more (ADR-012 allows one deliberate retry of an
unusable draft). The learner would then have been told that the lesson could not be used:
two of an account's ten tries spent, and the one sentence that says what to do thrown away.

## Decisions

- **Such an answer is a kind of failure of its own**, `provider_notice`, raised by the client
  before anything looks at the text as a draft. A job that meets it ends at once. It is never
  retried: asking again cannot change what the provider thinks of the account.
- **It is recognised by two signs, either of which is enough.** The identifier begins
  `chatcmpl-fake`, which is what the documented provider was seen to send. Or the answer has
  text and reports that no tokens were read and none written, which no model can do. An
  answer that simply does not report its usage is not a notice: silence is not zero.
- **The provider's words are shown to the learner, quoted, as text.** They are the only thing
  that says what the learner can do, so a summary of Adle's own would be worse. Around them
  Adle says whose words they are, that they concern the learner's account with the provider
  and not Adle, and that nothing was changed.
- **They are somebody else's text and are treated as such.** Before being shown they are
  made one line, cut at 300 characters, and cleared of control characters and of the
  characters that hide or reorder text; quotation marks inside them are changed so they
  cannot close the quotation. An address in them stays text: nothing in a provider's words
  becomes something to press. They are never logged, never stored apart from the job's
  message, and never read as an instruction.
- **What is offered is the settings**, where the key and the links to the provider's account
  are, and not "Try again".

## Consequences

- An account that has run out of whatever the provider allows now costs one request to find
  out, and the learner reads the provider's own explanation.
- The first sign depends on a detail of one provider's behaviour that is not documented and
  may change. The second does not. If both stop matching, the behaviour falls back to what
  it was: an unusable draft, asked for once more.
- A provider could write anything in such a notice. It is shown inside quotation marks,
  under a heading that says the lesson could not be made, with Adle's own sentence before
  and after it. That is the same standing as an error message from any service the learner
  chose to use.
- The real model has still not answered. With the first key the provider's relay returns
  HTTP 500; with the second, the account has to be topped up before the provider passes
  anything on. See `docs/engineering/PROJECT_STATE.md`.
- Tests: `test_provider_notice.py` (both shapes as they arrived; an ordinary answer is not
  mistaken for one; the words reach the learner and not the log; cleaning; a lesson job and
  a curriculum job each end after one request), `generation.test.ts`, and
  `e2e/generation.spec.ts`.
