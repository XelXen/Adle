# ADR-036: Say less: what a request sends is one press away, not beside every button

- **Status:** Accepted
- **Date:** 2026-11-21
- **Changes:** ADR-023 and ADR-028 in one respect each (below). Their rules about where a
  request may go, and about plain words, stand.

## Context

ADR-028 made every sentence short and plain. There were still too many of them. Beside
every button that asks an AI provider for something stood a paragraph: "Sends the course
name, this concept and its objectives, and your level, preferences, and goal, plus a few
passages from your materials to NVIDIA NIM, then AIHubMix if needed. Ready to start in
about 5 minutes. Its pictures follow." Under a lesson's title stood what it was made
from, how long it takes, its sources and who wrote it. Sections explained what the app
does with a file, what its background service is for, and how a setting is used inside.

The owner, after using it: "it's meant to be a study app, no need to show these things;
just show what the best user experience is meant to show."

The sentences were there for a reason that still holds. The operating contract says a
request must never go anywhere silently, and ADR-023 says where a request may go is said
before it is sent, and who wrote an answer afterwards. What was wrong was not that this
is said but where, and how often: a promise repeated beside every button is read once and
is in the way ever after.

## Decisions

- **What a request sends and where it goes is said in full where the choice is made**:
  Settings → AI provider, where a key is given and the provider chosen, shows the route
  each kind of request takes now; Settings → Privacy & data lists what each kind sends.
- **Beside every control that sends, the same words are one press away** (`WhatIsSent`,
  an `InfoPopover`): what is sent, where it goes as the core plans it at that moment,
  and how long it usually takes. Nothing is sent before that control is pressed, and the
  note is there before it is. This replaces the sentence beside the button (ADR-023:
  "said before it is sent" is now "there to be read before it is sent").
- **A request that only fetches something to review is not asked about twice.** Asking
  for suggested concepts began with a dialog whose only content was what would be sent.
  The button now asks at once; nothing is added until the suggestions have been reviewed,
  as before.
- **Who wrote a lesson, what it draws on and how long it takes** is one press away beside
  its title ("About this lesson"). An answer to a question still names who wrote it under
  the answer itself: there it is part of what is read.
- **A sentence stays where the learner has to act on it or decide by it**: why the next
  step was chosen, what a destructive action removes, what went wrong and what to do
  about it, that importing uploads nothing, that a notification never carries lesson
  content. A sentence about how Adle works inside goes.
- **Settings is where explanations live**, and they are kept short there too.

## Consequences

- A learner who wants to know what leaves the computer has to press once to read it. A
  learner who does not is no longer told on every screen.
- The promise in `lib/generation.ts` (`lessonDisclosure`, `askDisclosure`) and its test
  stay as they were: what is named there must match what the core sends.
- Journeys that read the sentence beside a button now open the note first. The ones that
  check that nothing is sent before the control is pressed are unchanged.

## Not done, and why

- **Removing the note altogether.** The owner asked for the text to go, not for the app
  to stop saying where a learner's words are sent. One small button keeps the second
  without the first.
