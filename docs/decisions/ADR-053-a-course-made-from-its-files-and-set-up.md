# ADR-053: A course is made from its files, named by Adle, and set up if asked

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** ADR-012 in "a proposal adds nothing until the learner picks": when the
  learner asks Adle to set the course up, what the AI suggests is added without a review.
  ADR-009 and ADR-046 in what the interface offers: a course's concepts are no longer
  drafted from the headings of its files by a button of their own.
- **Keeps:** ADR-012 for suggestions asked for on the curriculum (the learner picks),
  ADR-046 (a file's headings, or how its pages begin, ground the suggestions), ADR-048 (a
  lesson begun at its first part), ADR-036 (what is sent, one press away).

## Context

The owner looked at a concept and at how a course is made and asked:

- "shouldn't edit and remove button be at the end? shouldn't the description, learning
  objectives and prerequisites be together, then how much i know and lessons together";
- "no need to show start from materials button- relying on just RAG model would be weird
  + it wont add descriptions, prerequisites etc... rather auto-link the stuff that the
  model already does";
- "while making a course- allow to choose files immediately because it can auto decide the
  name from AI as well and also generate the first lesson (optionally)".

A course from files was made empty, named by hand, and filled on its Materials tab; its
concepts came either from its headings (titles alone: no summary, objectives or
prerequisites) or from the AI's suggestions, which carry all of those and are already
linked to the pages they come from.

## Decisions

- **A course from files is made with its files.** The new-course dialog starts on "From my
  files"; its button opens the system's file dialog and the course is made with what is
  chosen. Choosing nothing makes nothing. "From a topic" is the other way.
- **Its name may be left to Adle.** A course made without a name is "New course" at first,
  then is named after the first file imported into it, then takes the name the AI gives it
  with its concepts (`course_title`, asked for only then, one plain line of at most 80
  characters). The learner naming it ends that: Adle never renames a course the learner
  named (`courses.named_by_adle`, revision 0011).
- **"Set it up for me"** (on by default where there is an AI key, off and said otherwise):
  the suggestions are asked for as the course is made, after its files are imported, and
  everything suggested is added, as the learner would have added it all; then the first
  concept that can be taught has its lesson begun. It is the suggestion job with `setup`,
  then the ordinary lesson job: the same requests as asking for each by hand. What is
  sent is one press away from the button (ADR-036). Without it the suggestions wait for the
  learner's review, as ever.
- **"Start from your materials" is gone from the interface.** The headings of a course's
  files ground the AI's suggestions (ADR-046) and are linked from the concepts suggested;
  the operations that listed them and added them stay in the core, where the suggestions
  and one journey use them.
- **A concept is shown in the order the owner gave**: "About this concept" (what it
  covers, its learning objectives, its prerequisites and what needs it), then "Your
  learning" (how well it is known and the self-rating, then its lessons and the way to ask
  for one), then where it is in the learner's files, which can run long; "Edit concept"
  and "Remove concept" come last.

## Alternatives

- **Naming the course from its files alone.** It is what happens without an AI key; a
  file's name is rarely a course's ("chapter1.pdf").
- **Asking before adding what a setup suggests.** That is the curriculum's own "Suggest
  concepts with AI", kept as it was; the learner who asks Adle to set the course up has
  answered that question in advance, and can remove any concept afterwards.

## Consequences

- From the library to a lesson being written is one dialog: choose the files, and Adle
  imports them, names the course, adds its concepts and begins its first lesson.
- A course can no longer be made empty from files; a topic course can still be given files
  on its Materials tab.
