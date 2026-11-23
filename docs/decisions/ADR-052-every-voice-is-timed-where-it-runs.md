# ADR-052: Every voice is timed where it runs, and a slow one is given a head start

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** ADR-051 in when a lesson in a natural voice is ready, on a computer where the
  voice is slower than speech, and in where its usual wait comes from.
- **Keeps:** ADR-051 (a lesson is made with its voice; a line not recorded yet is waited
  for; the voice never changes by itself in a lesson), ADR-042.

## Context

ADR-051 timed the Expressive voice on the development machine and took the lighter voices
to be fast. The owner asked for every voice to be timed: "we dont know how weak the
hardware would be... worst case scenario- they'll be done instantaneously".

Measured on the development machine (2026-11-23), eight lines of a lesson each:

| Voice | First line, disk cold | First line, warm | Later lines, work per second of speech |
|---|---|---|---|
| Natural (Kokoro, the processor's 32 threads) | 29.7 s | 11.8 s | 0.24 |
| Natural on 2 threads | | 11.3 s | 0.39 |
| Natural on 1 thread | | 11.7 s | 0.68 |
| Rich (Qwen3-TTS 0.6B, the card) | 43.5 s | 18.7 s | 0.31 |
| Expressive (Qwen3-TTS 1.7B, the card) | 25.4 s, then 12.6 s | | 0.39 |

Even the lightest voice takes 12 to 30 s before it can say anything, and on one thread of a
fast processor it is only one and a half times faster than speech: on an older or weaker
one, Kokoro is slower than speech. ADR-051's lesson is ready once its first part can be
heard, which suits a voice faster than speech; with a slower one, a learner who starts then
catches up with the voice and waits, line after line.

## Decisions

- **Every voice is timed on the computer it runs on** (`voice/timing.py`, pure;
  `NarrationService` keeps the numbers in `voice/timing.json`), whichever it is:
  - **at setup**: the voice says as much as a lesson's first part (three lines) from an
    engine started cold; how long that took is its `start`, and the work for each second of
    its last line's speech its `rate`;
  - **with every line it records** once its models are loaded (after its first line, or
    the Expressive voice's second): its `rate`, as a running mean;
  - **with every lesson made in it**: how long after the lesson was asked it was ready,
    its `ready`, as a running mean.
- **A voice slower than speech gives a lesson a head start.** A lesson is ready when its
  first part can be heard and, where the voice's measured rate is above one, when the speech
  recorded from its start is at least `lesson × (1 − 1 / rate)`, with 15 percent more: the
  voice then reaches every line before the learner does. The lesson's length is its lines,
  each recorded one as long as its clip and any other as long as its words (14 characters a
  second), and at least 120 s while its later parts are not written yet. A voice not timed
  yet is taken to be as fast as where Adle was made. A lesson job whose words are written
  waits for that, saying "Recording the voice", for up to five minutes (it was two).
- **How long a lesson usually takes comes from this computer**: as lessons made here took;
  before any, from the setup's timing, with the head start a voice slower than speech needs;
  before that, as on the development machine (30 s for Natural, 45 for Rich, 50 for
  Expressive).
- **Settings says when a voice is slower than speech here** ("Slower than speech on this
  computer, so a lesson in it takes longer to be ready."), where it changes the choice; a
  voice faster than speech says nothing of it.

## Alternatives

- **A fixed speed for each voice.** It would be right only for computers like the one it
  was measured on, which is the guess the owner asked not to make.
- **Making a slow voice the learner's problem in the lesson.** The lesson would wait at
  line after line (ADR-051 keeps that as the safety net); waiting once, before it starts,
  and saying so is kinder.

## Consequences

- On a computer where the voice is slower than speech, a lesson is ready later, and is then
  heard through without waiting; how much later is said before it is asked for.
- Setting a voice up takes a few seconds longer: it says three lines rather than one word.
- The numbers belong to the computer and the voice: removing a voice leaves them, and they
  are the voice's folder's, never sent anywhere.
