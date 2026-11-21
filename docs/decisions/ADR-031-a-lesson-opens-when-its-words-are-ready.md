# ADR-031: A lesson opens when its words are ready

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

A lesson is written in one request for its text and one for each of its pictures, at most
two (ADR-012). Measured through NVIDIA NIM on 2026-11-20, the text takes about five to six
minutes and each picture two to four, so a learner waited about twelve minutes and was then
given everything at once. PROMPT.md 3 says never to make the learner wait for a whole
chapter if the first useful part is ready, and PLAN.md 12.1 asks for the first ready part to
be shown while later ones are prepared. ADR-026 made the wait easier (a break, a
notification) and said plainly that it did not shorten it.

The text of a lesson is complete by itself. Every part that has a picture also carries that
picture's description in words, because a picture may fail to run and a learner may not see
it (ADR-010). So a lesson without its pictures is already a lesson that can be taken.

## Decisions

- **A lesson is stored as soon as its text is written and has been checked**, with its
  pictures marked as still to come. From that moment it is listed, can be opened, and
  counts as the concept's lesson. The time said before asking ("Ready to start in about six
  minutes. Its pictures follow.") is the time until then.
- **A picture is added to the stored lesson when it is drawn.** One request each, one more
  only if the file is refused, exactly as before: the number of requests has not changed,
  only when the learner can begin.
- **A picture that could not be drawn is settled in words**, as it always was: that part
  becomes an explanation carrying the picture's description. So is one that was drawn and
  that the lesson then cannot take. Nothing stays "still to come" once the work has ended:
  if the learner stops it, if the provider gives out, or if the app is closed while a
  picture is being drawn (settled the next time the core starts).
- **Stopping the work once the lesson exists stops the pictures and keeps the lesson.**
  Before that, stopping means nothing was saved, as before.
- **Removing the lesson, or its course, stops the work at once.** The request under way is
  let go of and no other is made: nothing more is asked of a provider for something the
  learner has thrown away. (Removing a course did not stop its work before this; the
  request under way ran to its end.)
- **The lesson goes through the same gate** (`parse_bundle`), which now knows that a scene
  may be still to come: a part may refer to a picture that is included, or to one that is
  listed as coming, and to nothing else. Adding a picture, or settling one in words, passes
  the whole lesson through the gate again.
- **The player is told which pictures are still to come** (`pending_scene_ids`), and shows
  such a part with its description in words and a line saying the picture is being drawn.
  It looks again every few seconds while any are outstanding. The lesson's own text is not
  swapped under a learner who is in it.
- **A picture that arrives takes its place only in a part that has not begun.** In a part
  that is being read, or has been, it is offered ("The picture is ready. Show picture") and
  shown when the learner asks: nothing is sprung on someone in the middle of a sentence.
- **The learner is told once**, when the lesson can be started, not a second time when its
  pictures are done, whichever screen they are on then and whichever they were on before
  (`WritingProvider` keeps the one record). The end of the work is worth a second word only
  if a picture did not arrive.
- **Who wrote a lesson is kept with the lesson**, not only with the job that made it, and
  is said in the lesson in one line: the model and the provider, and that AI can make
  mistakes (ADR-028).

## Consequences

- One column on `lessons` for the pictures still to come and one for who wrote it
  (migration 0008). A copy of the data made while a picture was being drawn restores to a
  lesson whose remaining pictures are settled in words.
- A lesson job now has a result while it is still running (`JobContext.publish`): the
  lesson's id and how many pictures are outstanding. Everything that reads a lesson job's
  result reads it through `readLessonOutcome`.
- A learner who starts at once may reach a part before its picture exists. They read it in
  words and can come back to it; nothing waits for the picture.
- A lesson opened before a picture arrived keeps the words it was opened with. If the
  picture came out as an animation where something to operate was asked for, the lesson as
  stored calls that part a visualization and the open one still calls it an interaction, so
  the player asks the picture itself whether it has anything to operate before it says
  "Try it".
- While a lesson is getting its pictures no other lesson is offered for that concept, and
  no break: there is nothing left to wait for.
- Still not done from PLAN.md 12.1: writing a lesson part by part. The text is one request
  and arrives whole (ADR-012).

## What was tried and seen

- The two tests for "removing stops the work" first passed with the stopping taken out:
  the stand-in for a slow picture lets go by itself after twenty seconds, and the tests
  waited thirty. They now wait five and ten, and were seen to fail without the fix.
- A journey that had passed a hundred times missed once in the packaged run: it pressed
  "anything that says lesson" before the list of lessons had loaded, and so pressed "Create
  a lesson with AI". The button is no longer shown until the list is known (it would say "a
  lesson" where it means "another"), and the journey asks for the lesson's own button.
