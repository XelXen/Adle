# ADR-051: A lesson in a natural voice is made with its voice, and waits for it

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-042 in "a lesson is recorded once, in the background, and nothing waits
  for it": a line not recorded yet is now waited for, and the voice does not change by
  itself in the middle of a lesson. ADR-048 in when a lesson is ready: in a natural voice,
  once its first part can be heard.
- **Keeps:** ADR-042 (what a natural voice is, where it runs, how it is set up, and that
  where each word is said is known, never guessed), ADR-013 (the computer's own voice and
  reading at reading pace remain), ADR-048 (a lesson is begun at its first part, and a part
  already there never changes).

## Context

The owner chose the richer voices and found that "it takes a long time to process text so
app defaults back to computer default", and asked for the voice to be made while the lesson
is built, its time counted in the lesson's, or for the lesson to be shown as still being
made, with a way to start anyway.

Measured on the development machine (an RTX 4080 Laptop GPU, Expressive, Qwen3-TTS 1.7B,
eight lines of a lesson): the first line took 25 s (the engine started, the voice-design
model loaded and warmed, the voice designed); the second 13 s (that model put away and the
one that speaks in the designed voice loaded); every line after it was recorded 2.5 times
faster than it is said (0.39 s of work a second of speech). The voice is fast; loading it is
not. And a lesson was recorded by a job that read its lines once and ended: a lesson
written part by part (ADR-048) started a job, the job ended when it had caught up, and the
next part started another, which loaded the models again. A part stored while a job ran was
not recorded until another began, if one did. A line without its clip was read by the
computer's voice, so a lesson went from one voice to the other and back.

## Decisions

- **The voice is loaded as the lesson is asked for** (`NarrationService.warm`, called by
  `GenerationService.generate_lesson`): a job in the voice lane starts the engine and loads
  what the lesson's first line is said with, and the aligner, while the model writes the
  lesson's first words. The engine has a request for it (`load`).
- **One recording follows a lesson from its first part to its last, on one engine.** It
  records the lines there are, in the order they are said; while the lesson is still being
  written it waits for the next part (woken when one is stored) and records that; it ends
  when the lesson is whole and every line is recorded (or after ten quiet minutes). The
  engine is kept loaded between recordings for three minutes, then closed; it is closed at
  once when a voice is set up or removed, and when the core stops. Removing a lesson stops
  its recording.
- **A lesson in a natural voice is ready once its first part can be heard.** The lesson
  job says `voicing` while its first part (the first that says anything) is still being
  recorded; the interface announces the lesson, offers it as ready and starts it from
  "Lesson ready" only after. The job is told each time more of its lesson can be heard
  (`on_voiced`) and says so at once. When its words are all written before that, the job
  says so (`stage: voicing`, "Recording the voice") and waits for it, for two minutes at
  most. A recording that ends without the line, or a voice that cannot record, holds the
  lesson back no longer.
- **How long a lesson usually takes counts its voice**: the larger of what its words take
  and how long after a lesson is asked its first part could be heard here, kept as a
  running mean for each voice (`voice/timing.json`), or as measured on the development
  machine until it has been (15 s for Natural, 45 for Rich, 55 for Expressive).
- **A line not recorded yet is waited for** (`RecordedNarrator`): the lesson holds at it,
  playing, and the bar says "Recording the voice for this part." with a way to read on in
  the computer's voice (or in words, where the computer has none). Chosen, that voice reads
  the rest of the lesson, so that the voice does not change back and forth. A line is read
  in the other voice by itself only when no recording will come for it (the recording ended
  without it, or cannot be made). The narrator is still the clock: a line waited for has
  not begun, and nothing measures the wait. A line paused while it waits begins when the
  lesson goes on; one left is not played when its clip comes.

## Alternatives

- **The lesson job records the voice itself.** The words are written in the main lane, the
  voice in its own, and the main lane would be held for the whole of a recording. The lesson
  job only waits, and only when its words are all written before its first part is heard.
- **Streaming each line's sound as it is made.** Qwen3-TTS can stream, but where each word
  is said is found from the whole line, and the voice is already faster than speech once
  loaded: what was slow was loading it, again and again.
- **Keeping both of the Expressive voice's models on the card.** It would save the swap
  after a lesson's first line, on cards with room for both; the voice runs on 8 GB cards,
  which do not have it. Not done.

## Consequences

- Through NVIDIA with the Expressive voice on the development machine, a lesson's first part
  could be heard 40 to 49 s after it was asked for (three lessons), and the whole of its
  voice was there within 41 s of its last word, well ahead of a learner who started at
  "ready" (PERFORMANCE.md). Natural (Kokoro) is not timed so yet; it is ready 2.3 s after
  it starts and four times faster than speech.
- A learner who opens a lesson before it is ready, or one from before the voice was chosen,
  waits at its first line rather than hearing another voice, and is told so.
- The engine holds the card's memory for three minutes after a recording.
