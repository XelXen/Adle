# ADR-029: Boundaries tightened after a review of the whole app

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

Two independent reviews of the code (one for security, one for correctness) were made after
the features of ADR-023, ADR-024 and ADR-026 landed. Neither found a way to a provider key
or to running code outside the sandbox. They did find places where the code did less than
`SECURITY.md` said. Each was confirmed before it was changed; the one about the network was
confirmed by running it (a page could send UDP and TCP to listeners on this computer through
a peer connection).

## Decisions

**The page cannot name a file, even by handing over something that only looks like a list.**
The preload used to call `.map` on what the page passed as "the dropped files". A value from
the page can carry functions of its own, so that was a way to name any path. The preload now
calls no method of it (`electron/preload/dropped.ts`): a real array, each entry a real
`File`, the path asked of the browser.

**"No network" covers what is not a request.** Refusing requests and `connect-src` do not
govern a peer connection or a connection opened ahead of time. Two things now do:

- no name is ever looked up by the browser (`host-resolver-rules`): nothing here needs one;
- whatever is left goes to a proxy that is nowhere, loopback included, and a peer connection
  may not use UDP outside a proxy.

A third was tried and taken out: `webrtc 'block'` in the content security policy. The
Chromium in this Electron does not know the directive; it stopped nothing and wrote an error
to the console of every page. With the two above, a peer connection gathers no address at
all and nothing arrives at a listener on this computer, by UDP or TCP, from the page or from
a player frame.

**A request is not read before it is known to be ours.** The core checked its token in a
step that ran after the body had been read, and the server set no limit on a body. A gate in
front of the routes (`api/gate.py`) now refuses a request without the token before reading
any of it, and any body over two megabytes.

**The learner's choice of provider arrives before their keys, and before anyone is told the
core is ready.** A core starts on "automatic". It was handed the keys first and the choice
second, and the page heard "ready" before either. The hand-over is now part of starting the
core: choice, then keys, then "ready". If the choice cannot be applied, no key is handed
over and the start fails.

**What a document says stays quoted, including what it is called.** A file's name and a
heading's text were put in front of each excerpt outside the quoted block. They are inside it
now, and nothing in quoted text that could pass for the block's tag, in any spelling,
survives.

**An ordering question no longer carries its answer.** Its items' ids are given in the right
order, and the shuffle could be worked out again from what the page knew. The page is now
shown names made with a secret of the installation (`ItemMask`), in the order of those
names; the core turns them back.

**A provider's answer is read with a bound on every side.** A line, the whole stream, the
time a document may drip, and what a pattern may be made to do with it. The answer is asked
for uncompressed. "Stop" closes it.

**The log says what kind of thing failed and where, never the text of the error**, and the
database never puts a statement's values into an error.

**Help counts as help.** Skipping a question shows its explanation, so the answer that
follows is an aided one. A question the learner asked and then removed leaves a mark with no
words in it, so the answer that follows is still an aided one.

**Smaller things, each with a test.**

- A scene frame that sends more than a few hundred messages in a second is ended like one
  that hangs (`WanimPlayerAdapter`).
- Looking for work that is under way and starting it are one step (`GenerationService`), so
  two requests arriving together cannot write the same lesson twice, and the provider cannot
  be changed in the moment a job begins.
- What a draft called a kind of part or of question is quoted back, in the request for a
  second draft, as a few plain characters.
- A file past the largest limit is refused before it is read; what a parser's process says
  about a file is shown only if it is a reason a parser has, as one plain line.
- A dialog is cut out of the strip the window is moved by (ADR-030).

## Not done, and why

- **Changing the provider choice needs no confirmation outside the page.** A page that has
  been taken over could switch from one provider to "automatic". It could also read every
  course through the core, so this is not where that is stopped; the keys it would use are
  ones the learner gave.
- **A release build can still be started with Chromium's remote debugging switch** by
  someone who can already run programs as the learner.
- **Ids of multiple-choice options still follow the order the model wrote them in.** They
  carry no key, only whatever habit a model has.
- **After "Stop", a provider's turn is given back without waiting for the stopped request
  to have ended.** The answer is hung up at once, as well as that can be done from another
  thread; where it cannot, the request ends at the next thing it reads or at its time limit,
  and until then two may be open at one provider (ADR-023).
- **The page can open the data dialogs again and again.** Each is the operating system's
  own window with "Cancel" as its default, and one is open at a time.
- **A key saved by a version before there were two providers is taken to be AIHubMix's**, at
  its usual address. No such version was ever given to anyone.

## Consequences

- Starting the core is slower by the hand-over (a few milliseconds), and a refused choice is
  a failed start with a message, which it was not before.
- Tests: the gate, the quoting, the mask, the bounds, the hand-over and the drop list each
  have unit tests; the network and the drop list are also tried inside the running app
  (`e2e/security.spec.ts`).
- Asking for an uncompressed answer, and reading it within bounds, was tried by hand against
  the real NVIDIA endpoint on 2026-11-20 (`scripts/dev/real_provider_check.py`, two requests):
  a key check came back in 26 seconds and an answer to a question in 88, as before.
- One file was added to the data folder: `items.key`, the installation's secret. It is not
  part of a saved copy and is made again after "delete everything".
