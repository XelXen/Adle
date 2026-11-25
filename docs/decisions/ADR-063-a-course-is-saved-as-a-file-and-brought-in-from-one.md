# ADR-063: A course is saved as a file, and brought in from one

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** A course could leave a computer only inside a copy of everything (ADR-016),
  and could not be given to anyone. The bridge gains three functions, and the core three
  routes that only the desktop shell may call.
- **Keeps:** ADR-016 (the data as a whole: one file, restored only while the core starts),
  ADR-010 (a lesson is stored only through the gate), ADR-009 (the curriculum stays
  learnable), ADR-029 (the page names no file), ADR-061 (a course's subject).

## Context

The owner, on 2026-11-24: "the courses can now be exported and imported via zip files so
someone else can access them too the same way. They can be exported as either a template, so
someone can start from scratch with their own knowledge base (templates just include lessons
and curriculum, but not the personal knowledge acquired, like how much the user knows), or
exported as transferring course, which means transferring to another device. And imports are
also configurable as to what to import, but these configs are advanced so are hidden in a
dropdown."

A course is rows in a dozen tables that refer to each other by identifiers, some files, and
what the learner has shown they know. Two things about it decide the design:

- **A file that is brought in comes from anywhere.** Someone else made it, or it was
  changed on the way. It must not be able to name, change or replace anything that is here,
  write anywhere, run anything outside the player's frame, or say what a learner knows.
- **A file that is given away should carry no more of the giver than they meant.** A
  course made from a professor's notes has the notes in it, in passages and in every
  citation.

## Decisions

- **A course file is a zip of a few JSON documents**, and the documents the course was made
  from when the learner asks for them (`application/course_file.py`):
  `adle-course.json` (what it is and what it holds), `curriculum.json`, a file for each
  lesson (the Lesson IR and its scenes), a file for each imported document (its sections
  and passages) with the document itself beside it, `progress.json`, `notes.json`.
- **Two kinds, and what either holds can be changed** under "Advanced", which is closed
  until it is wanted (`Disclosure`, new in the design system):
  - a **template** holds the plan and its lessons, and nothing of the learner: no answers,
    no notes, and no materials. Its lessons cite nothing, and do not name the files they
    were written from. This is what is chosen until the learner says otherwise;
  - **everything** holds the materials, the progress and the notes too, to move a course to
    another computer.
  The course's plan is always saved. A lesson still being written or drawn is left out,
  and that is said.
- **Bringing a file in always makes a new course.** Nothing in a file is looked up here:
  every identifier in it is only a name for its own parts to refer to each other, and
  everything is given a new one. Two courses of one name can stand side by side; one that
  came in a file says "Imported" (`courses.brought_in`, revision 0015).
- **It goes in by the roads everything else goes in by** (`application/course_sharing.py`):
  - the curriculum through `CurriculumService`, a concept at a time, so that a loop or a
    need for something that is not there cannot be made (what a concept was said to need is
    then left out);
  - a lesson through `lessons.bundle.parse_bundle` and `LessonService.store`: its shape
    checked, its scenes put through the policy, every reference resolved. One that cannot be
    used is left out and counted, and the rest come in. A scene still runs only in the
    player's frame;
  - a document as its sections and passages, under new identifiers
    (`SourceService.add_copied`), with the document itself kept only if its size and its
    hash are what its entry says;
  - **what the learner showed is recorded again, answer by answer, in order**
    (`LearnerService.replay`): every state and every sentence about it is worked out here.
    A file has no place to say what a learner knows, and one with such a field is refused.
  Half a course is removed again.
- **Never as Adle's own.** A file that says its course is the sample, or that its lessons
  are, is not believed: what comes in is a course from a topic or from materials, with
  lessons that say they were written elsewhere. Who wrote a lesson is kept as names only.
- **Without its materials a lesson cites nothing**, and no longer says it is grounded in
  materials the reader does not have: a citation of a passage that is not there would be
  an invented one.
- **Reading a file extracts nothing.** A member is read by a name the core made (a name in
  a file is never used as a path), up to a bound on its size that does not trust what the
  file says its size is, and against a bound on the whole. A member of any other name, a
  folder, a member locked with a password, or two of one name refuse the file. Each part is
  checked against a closed description of it, unknown fields refused.
- **The page never names a place.** It says which course and what the file should hold, or
  what to bring in of a file the learner chose (`window.adle.courses`). The core writes a
  file in a folder of its own under a name it makes; the shell asks the learner where it
  should go, in a window of the operating system, and moves it there, so the core is never
  told a place to write. A file to bring in is chosen in such a window, and the page knows
  it by its name and by a token that is good for that file, for half an hour. The core's
  three routes are internal.
- **Recordings of a natural voice are not carried.** They are made again where the course
  arrives, in the voice chosen there.

## Alternatives

- **The course's rows, copied as they are.** Quick to write, and a file could then set a
  state, an answer key's score, or an identifier that is already in use. Everything is
  rebuilt through the services instead.
- **A copy of the data, cut down to one course.** A database file from anywhere is a much
  larger thing to trust than JSON read against a description, and it could not be merged
  into the data that is here.
- **Keeping what the file says a learner knows.** It is derived, and from a file it would
  be a claim. The answers are kept; what they add up to is worked out.
- **Materials in a template by default.** The owner asked for "lessons and curriculum".
  A course's materials are often not the learner's to give away. They go in when asked for.
- **The core writing the file where the learner chose.** One route already does that
  (`data.save_copy`), and it is meant to stay the only one. The shell moves a finished file
  instead.
- **Passing the chosen path to the page and back.** A page that can hold a path can send
  another. It holds a token.

## Consequences

- A course can be given to someone, and moved to another computer.
- A course brought in is a new course every time: bringing the same file in twice makes
  two.
- A template of a course made from materials loses its citations. Its lessons say they are
  from general knowledge, which for the reader they are.
- A lesson made by a later Adle that this one cannot read is left out, and the count says
  so. A file made by a later version of the format is refused whole, with a sentence that
  says to update.
- Progress brought in is as this version works it out. A version with other rules of
  tracing could arrive at another state from the same answers.
- Bringing in is one call that the learner waits for. A course with very many documents
  could take a while; it is not yet a job with a bar.
