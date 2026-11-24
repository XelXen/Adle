# ADR-062: The Expressive voice is put together from parts

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** ADR-057's presets, which were five descriptions written out whole ("Warm
  teacher", "Gentle storyteller"). How a learner says who reads their lessons.
- **Keeps:** ADR-057 (the voice is a description; a lesson adds only its delivery; a voice is
  heard before it is chosen; a new voice records the lessons opened last), ADR-042 (nothing
  is downloaded for this), ADR-051 and ADR-052 (a lesson made with its voice, timed where it
  runs).

## Context

The owner, on 2026-11-24: "expressive voice can be much more modular: firstly the user can
directly change the voice design, but that should be the most custom way; with that, presets
need not be just characters like teacher or storyteller, there can be so much more, like
gender, ethnic, speed, stability of tone, what kind of work", with a list beside it:
"Persona: male or female, young, middle-aged or elderly. Pace: fast, moderate or slow.
Timbre: clear, deep, sweet, magnetic or raspy. Emotion: calm, enthusiastic, gentle, serious
or lively. Scenario: news, storytelling, sales or classroom."

A voice was a sentence of up to 200 characters. A learner could write it, or start from one
of five written for them. To change one thing about a voice (the same narrator, slower) was
to rewrite a sentence, and nothing said what a sentence could ask for.

The makers of the voice (Qwen3-TTS, its voice design) say what a description is listened to
for: gender, age, pitch, speech rate, emotion, the character of the voice (magnetic, crisp,
raspy, mellow, sweet, deep, powerful) and what it is for (news, audio books, documentary
narration), several of them together, in plain and specific words. That is the owner's list.
An accent is not on theirs.

## Decisions

- **A voice has nine parts, each a choice from a short list** (`voice/design.py`, pure):
  who speaks (a woman, a man), age (young, middle-aged, older), pitch, pace, tone (clear,
  deep, warm, sweet, rich, raspy, strong), feeling (calm, cheerful, enthusiastic, gentle,
  serious, lively, soothing), delivery (steady, or expressive: the owner's "stability of
  tone"), accent, and style (a classroom teacher, a storyteller, a newsreader, a
  documentary narrator, a podcast host, a presenter, a coach). A part left alone is left
  to the voice.
- **The core writes the one sentence the parts make**, in the words the voice's makers use
  ("A calm middle-aged man with a low-pitched, deep voice and a steady, even tone, speaking
  natural English at a slow pace, like a documentary narrator."). Nothing else writes it:
  a recording is named by the description it was made from, so the same parts must always
  be the same sentence. The page asks the core what parts make (`voice.describe`) and
  never puts a sentence together itself.
- **No parts at all is Adle's own voice**, the description it always had. Nothing recorded
  in it is recorded again.
- **The description stays what a voice is; its parts are only how it was made.** They are
  kept beside it and offered again in Settings while they still make it. Once the learner
  writes over the sentence, or a later version words a part differently, the parts are let
  go and the sentence goes on being read as it is. A change of wording therefore never
  changes a voice a learner already has.
- **Voices to start from are choices of parts**, which the learner goes on changing: a calm
  narrator, a bright and lively one, a gentle storyteller, a British lecturer, a
  newsreader, an encouraging coach, and Adle's own.
- **The learner's own words are still there, and are the most exact way.** Typing in them
  lets the parts go.
- **"Ethnic" is an accent**, of English: American, British, Australian, Indian, Irish,
  Scottish. It is asked for in the sentence like any other part. The voice's makers do not
  say it listens for one, so the choices say, one press away, that an accent is followed
  least of all, and a voice is heard before it is saved, as before.
- **Every description the parts can make is one a learner could have written**: plain
  words, one sentence, no longer than 200 characters (a test goes through them).

## Tried by hand

The real voice (Qwen3-TTS 1.7B, on this machine's graphics card, 2026-11-24) said the same
sample in fifteen voices made of parts. Each clip's pitch was measured (the middle of what
an autocorrelation finds, which can be an octave out and is good for comparing), and how
fast it speaks:

| Asked for | Pitch | Words a second |
|---|---|---|
| a woman, high-pitched | 350 Hz | 3.3 |
| a woman | 211 Hz | 2.7 |
| a man | 181 Hz | 2.9 |
| a man, low-pitched | 118 Hz | 3.2 |
| a slow pace | 189 Hz | 2.7 |
| a fast pace | 255 Hz | 3.5 |
| calm, with a steady, even tone | 130 Hz, ranging over 98 | 3.3 |
| enthusiastic, with varied intonation | 276 Hz, ranging over 148 | 3.0 |

- **Who speaks and how high are followed**, in the order asked for: high above a woman
  above a man above low.
- **Pace is followed, modestly**: "fast" is about 29% quicker than "slow".
- **Feeling and delivery are followed**: the steady voice keeps to two thirds of the range
  of the expressive one.
- **A part left alone is not held still.** The two voices that differ only in pace are two
  different speakers, 189 Hz and 255 Hz. To change one thing and keep the rest, the rest
  has to be chosen too. The choices say so, one press away.
- **An accent could not be measured**, and nobody has listened: the three clips asked for
  as British, Indian and Australian English are kept for the owner to hear. Until someone
  has, Adle says an accent is followed least of all.
- A voice is designed and its sample said in about 25 seconds once the voice is loaded.

## Alternatives

- **Parts that the page puts into a sentence.** Two places would then decide what a voice
  is, and a difference between them would record every lesson twice.
- **Keeping the parts and making the sentence each time it is needed.** A later version
  that words a part better would silently change every learner's voice and record their
  lessons again. The sentence is kept, and the parts are let go when they stop making it.
- **A slider for pace or pitch.** The voice is told in words, and its makers name three or
  five steps of each. A slider would promise more than is listened for.
- **Leaving accents out because they are not on the makers' list.** The owner asked for
  them, a description that names one is no worse a description, and the sample is how a
  learner finds out what they get. Said where the choice is made.
- **A child's or a teenager's voice, and a neutral one.** The makers list them. Left out:
  a learner who wants one can write it.

## Consequences

- A learner changes one thing about a voice with one choice, and can see what a voice can
  be asked for.
- The five descriptions of ADR-057 are no longer offered by name. A learner who chose one
  keeps it, as their own words.
- Changing the words of a part changes every voice made with it from then on. A part or a
  choice is added; the words of one are not changed without thought (the agent notes say so).
- What a voice does with a description is the voice's. Adle says what was asked for and
  lets it be heard.
