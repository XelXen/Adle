# ADR-028: Plain words: what the interface says, and what it leaves unsaid

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The owner, looking at the app: "why is there so much non-sensical, development text that
makes it look like an unfinished app? ... everywhere stay compact, professional and easy with
wordings". The example was the line under an answer: "Written by Coding Kimi K3 (free) on
Custom endpoint (127.0.0.1). A model wrote this, and it can be wrong."

The words had been written to be exact, and had become long, literary, and full of the app's
own workings: "the local service", "today's requests", "lighter evidence", "Waiting for its
turn", "That could not be recorded". A rail light said "Local service ready" to someone who
only wanted to learn.

## Decisions

- **Short, and about the learner's task.** One sentence where one will do. The point first.
  No account of how the app works unless the learner has to act on it.
- **Ordinary speech.** Contractions ("couldn't", "you'll"). A failure is "Couldn't save your
  goal", a success "Key saved", something loading "Loading library…". A confirmation asks one
  question and offers "Cancel" and the action by its name.
- **Typographic quotation marks and apostrophes** everywhere a learner reads, in the core's
  sentences as in the interface's. Titles are quoted “like this”.
- **What a learner has no use for is not shown.** The rail says nothing about the app's own
  service while it runs; it speaks up when it is starting or has stopped. (The page writes
  the state on `<html data-core>`, which is where a test reads it.) Quota arithmetic is said
  in Settings, not beside every button.
- **What must be said stays, in fewer words** (PLAN 6.3, ADR-021, ADR-023, ADR-024):
  - before sending: one line beside the control, "Sends *what* to *where*. Takes about *n*
    minutes.";
  - afterwards: "Answered by *model* on *provider*. AI can make mistakes.", and a stand-in is
    still named;
  - why a step is suggested: always, in one sentence.
- **Progress in four words:** Not started, Learning, Nearly there, Understood. They replace
  "Not assessed", "Building understanding", "Needs more evidence", "Demonstrated for now".
  The rules behind them are unchanged: still no percentage, still never from one answer. A
  right answer that counts for less is "with help", not "lighter evidence".
- **Names in the interface:** "Teaching style" (not "How should it explain?"),
  "Prerequisites" (not "Needs first"), "History" (not "the record"), "Queued" (not "Waiting
  for its turn"), "Test key", "Usage today".

## Consequences

- About four hundred sentences changed across the renderer, the main process and the core,
  and with them the tests that quote them. The lists used for the change are not kept; the
  rule for a new sentence is this record.
- `ruff`'s list of allowed look-alike characters gained the typographic quotation marks.
- Privacy and provider settings say the same things as before in a third of the space. What
  is sent, and that nothing else is, is still said in full under Privacy & data.
