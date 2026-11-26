# ADR-071: The teacher a lesson is written by

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-061 (the rules of every lesson gain one: a light moment or a fun fact,
  rarely, as the teacher allows), ADR-024 (what a question during a lesson sends: the
  teacher too).
- **Keeps:** ADR-057 and ADR-062 (the Expressive voice is put together from parts, from a
  voice to start from, or in the learner's own words), ADR-024 (a question is a note beside
  one part, not a chat), the rule that the learner's words are data, never instructions.

## Context

The owner, on 2026-11-25: "make the ai a bit character-ful, allow random witty moments
rarely in between, fun facts, not too much that it disrupts the thing but just a bit", and
then "the way voice is designed (at least for expressive), the lesson should adapt the
character of that ... give a characteristics area which has a tickbox that it adapts to
expressive character if used (and available) or allow building the character just like
voice ... when writing the transcript, the character info should be given to that ai too".

A lesson's words were written in one voice, Adle's, and the Expressive voice read them
aloud as whatever person the learner had made it. The two never met.

## Decisions

1. **A lesson has a teacher, and the learner says who** (Settings → Learning → Teacher,
   `TeacherSettings`), the way they say who reads in the Expressive voice: a part at a
   time (Manner, Kind of teacher, Humor, Fun facts, Words), from a teacher to start from
   (Adle's own, Storyteller, Curious scientist, Calm guide, Playful coach, Thoughtful
   professor), or in their own words, at most 300 characters. The parts and the sentence
   they make are the core's (`lessons/character.py`): the same parts always make the same
   teacher, and the page writes none of it.
2. **Adle's own teacher** is what a lesson is written by when the learner says nothing:
   warm and patient, speaking plainly, with a light, witty moment now and then and a fun
   fact now and then that belongs to the topic.
3. **The teacher can be the Expressive voice's person.** While that voice reads the lessons,
   a switch ("Teach as the Expressive voice's person", on unless turned off) makes the
   teacher the person the voice was described as. Without that voice, or with the switch
   off, the teacher is the one the learner made.
4. **The teacher goes to the writer of the lesson and of every answer to a question**
   (`lesson_request`, `ask_request`), as a description in a block of its own, told that it
   changes how things are said, never what is taught or how carefully, and that it is a
   description, not an instruction. What a question sends says so ("and the teacher you
   chose").
5. **Light moments are rare whatever the teacher** (axiom `light_touch`): in one part of
   every four at most, true, belonging to the topic, never in a question, never at the
   learner's expense, and never in place of a step of the teaching. A teacher who "never
   jokes" has none.

## Consequences

- A lesson sounds like someone, and like the same someone the learner hears.
- The rules of a lesson do not bend to a teacher: a playful one still teaches every step.
- A teacher written in the learner's own words is their data, like a voice's: it is sent
  only in the requests that write lessons and answers, and kept in their preferences, and
  in a settings file with them.
