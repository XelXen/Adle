# ADR-057: A voice that says what is meant, that the learner shapes, and that is ready first

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** ADR-042 in what is offered: two natural voices, not three ("Rich" is gone),
  and the Expressive voice designed from the learner's description rather than the lesson's
  alone. ADR-047 in what is said in words: mathematics typed with the keyboard's own
  characters too. ADR-051 in when a lesson is recorded: also as soon as the voice changes.
- **Keeps:** ADR-042 (what is downloaded and pinned, at the learner's word; the engine in a
  process of its own), ADR-051 (a lesson made with its voice; the voice never changes by
  itself in the middle of a lesson), ADR-052 (every voice timed where it runs).

## Context

The owner, listening to lessons: "the transcript uses things like ! which is factorial for
an equation but voice never pronounces it as that or ... which is pronounced as 'and so on'
or something else depending on context. In fact the expressive voice doesn't sound very nice.
The voice design could be better ... allow user to be able to customize voice design in
settings as addon characteristics he wants in addition to already expressions that ai will
generate ... presets provided if he doesn't want to write himself. Get rid of rich- it's of
no use. For natural aka kokoro- allow samples. ... if the voice is changed in settings ... it
should automatically show up on lesson page that voice is being recorded ... instead of first
going inside the lesson and then it gets generated. Keep the cache audio for all types so if
switched back- it doesn't regen."

What the code did: notation was said in words only in a line with TeX or a mathematical
symbol in it, so "5!" reached the voice as "5" said with surprise, and "1, 2, ..., n" as a
pause. The Expressive voice was designed from the lesson's own description of its narrator,
saying the lesson's first line (often a few words), and every later line was spoken as a copy
of that: a short, arbitrary clip is a poor thing to copy a voice from. A lesson was recorded
in a new voice only when it was opened. Clips were already named by the voice and the words,
and kept: a voice chosen again already played what it had recorded.

## Decisions

- **Mathematics typed with the keyboard is said** (`speech._typed`): "n!", "(n-k)!" and
  "5! = 120" are factorials; "!=", "<=", ">=", "->", "=>" are said as relations; "..." or
  "…" in a list or a sum is "and so on", and "and so on, up to" when the list goes on to its
  last item. An exclamation after a word, or after a number that ends a sentence ("That's
  120!"), stays one, and so does a pause in a sentence ("Wait... think").
- **Rich is gone.** Qwen3-TTS 0.6B is no longer offered; a computer that has it set up has
  it taken away as the core starts, with what it recorded (`catalog.RETIRED`,
  `NarrationService._retire`), keeping what the Expressive voice shares with it. A learner
  who chose it is read to by the richest voice set up, as for any voice that is not there.
- **The learner says who reads; the lesson says how it is delivered.** Settings has the
  voice in the learner's words (200 characters, plain), with descriptions to start from
  (`DESIGN_PRESETS`: a warm teacher, calm and low, bright and lively, a British narrator, a
  gentle storyteller); empty, it is Adle's own. The lesson's model now writes only the
  delivery (pace, energy, feeling), and the voice is designed from the learner's words
  followed by "Its delivery here: ...". A lesson written before keeps what it said.
- **A voice is designed saying a passage made for it** (`REFERENCE_TEXT`), long and varied
  enough to be copied cleanly, and every line, the first too, is spoken as a copy of it.
- **A voice can be heard before it is chosen** (`voice.sample`): each speaker of the Natural
  voice, and the Expressive voice of a description being written. A sample is made once in
  the voice's lane and kept (`samples/<size>/`); lessons recorded ahead of time step aside
  for it, and carry on after.
- **A new voice records at once.** When the voice changes (its size, speaker, description, or
  being turned on), the two lessons the learner opened last and has not finished are recorded
  in it straight away, before they are opened (`RECORD_AHEAD_LESSONS`); Settings says which
  lesson is being recorded and how far it has come. A lesson the learner opens, or a sample
  they ask for, goes first: lessons recorded ahead of time step aside. A recording under
  way goes on in the voice chosen now, from its next line, and ends if the natural voice is
  turned off.
- **Every voice's recordings are kept** (as they were): switching back plays them and says
  nothing again. Only removing a voice removes what it recorded, and its samples.

## Alternatives

- **Saying a lone "<" and ">" as relations.** Voices already read them so; a test keeps
  "For x < 0" as it was written.
- **Designing the voice anew for every line, with the line's own feeling.** The voice would
  change from line to line; a copy of one design keeps it one voice.
- **Recording every lesson in a new voice.** Hours of work on a weak computer for lessons
  that may never be opened; the two most likely are recorded, and any other when opened.
- **Deleting Rich's files only when the learner asks.** The owner asked for it to go; a
  voice that cannot be chosen is only space taken.

## Consequences

- "n!", "1, 2, ..., n" and "a != b" are said as a teacher says them, in captions too.
- The Expressive voice sounds like what the learner described, in every lesson, delivered as
  the lesson asks, and steadier from line to line.
- Changing the voice in Settings starts the recording of what is likely to be opened next,
  and says so; opening a lesson then finds it ready, or nearly.
- A computer that had Rich set up gets its space back when it updates.
- No migration: the description is kept with the voice's other choices. New operations:
  `voice.sample` and `voice.sample_clip`; `voice.status` also says `design`,
  `design_presets` and `recording`.
