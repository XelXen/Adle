# ADR-013: Narration is read by the computer's own voices

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

PLAN.md 11 asks for narration with a local text-to-speech engine as the preferred path (Piper or
Kokoro), the operating system's speech as a fallback, and an optional cloud voice. It also asks
that audio be the clock of a lesson, and that word highlighting never be invented.

A bundled engine means shipping a native binary per platform and a voice model of tens of
megabytes, checking each model's licence for redistribution, and a build and packaging path that
does not exist yet. The lesson player already keeps time by a `Narrator` (ADR-010), so the
engine is a detail behind an interface.

## Decisions

### The first engine is the browser's speech synthesis, with local voices only

- `lesson/speech.ts` reads narration through `speechSynthesis`, which on Windows, macOS, and
  most Linux desktops speaks with voices installed in the operating system. No download, no
  model, no licence question, and nothing to package.
- **Only voices with `localService` are listed or used.** A voice that would send the text to a
  service is ignored. Narration is lesson content; nothing leaves the computer to be read.
- The lesson's language decides the voice (English for now), not the system's default voice: a
  learner whose system speaks Japanese should not hear an English lesson read by a Japanese
  voice. The learner can choose any installed voice in Settings → Learning.

### The voice is the clock, and words are highlighted only when it says where it is

- `SpeechNarrator` implements `Narrator`: a line ends when the engine says it has ended; pausing
  pauses the engine. The controller is unchanged.
- The word being spoken is marked only on a word boundary event from the engine. Engines that
  report where a word starts but not its length get the length from the text. An engine that
  reports nothing gets no highlighting: the current sentence is marked, which is true.
- If a voice fails part-way through a line, that line is shown for its reading time instead, so
  a lesson never stalls on a broken voice.

### Silence is always available

- With no voice on the computer, the lesson says so and shows the narration as text at reading
  pace (`TimedNarrator`). The same narrator is used when the learner switches reading aloud off.
- "Read aloud" in the lesson is the same preference as Narration in Settings. Changing it
  mid-sentence starts that sentence again with the other narrator, because the two keep time
  differently.
- With narration spoken, the transcript can be hidden. With nothing spoken it cannot: the words
  are then the narration.
- Volume (0 to 100) and voice are stored with the other learning preferences in the core.

### Not built

- **A bundled engine (Piper, Kokoro).** Revisit if system voices prove too uneven across
  machines. It would be one more `Narrator`.
- **A cloud voice (ElevenLabs).** It would send every sentence of every lesson to a second
  service. Not worth a second disclosure and a second key for the first release.
- **Audio files and an audio cache.** Speech is produced as it is spoken; there is nothing to
  cache or to store beside a lesson.
- **Seeking inside a sentence.** A learner moves by sentence (replay) and by part.

## Consequences

- Narration works on a fresh install with no setup wherever the system has a voice, and says
  plainly when it does not.
- Voice quality is whatever the operating system provides, and differs between machines.
- Word highlighting depends on the engine. On the development machine (Windows 11, Microsoft
  voices) the engine speaks, pauses, and stops as asked; whether it reports word boundaries at
  every volume was not established, and nothing in the product depends on it.
- End-to-end tests of other features turn narration off so they keep the same time on every
  machine and play nothing aloud. `e2e/narration.spec.ts` exercises real speech at zero volume
  when the machine has a voice, and the no-voice path when it does not.

## Supersedes

The "local TTS first" order of PLAN.md 11.1, for the first release.
