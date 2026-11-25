# ADR-067: A question can have its part's picture drawn again

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-024 in what an answer can be: still a note beside one part, which may
  now carry that part's picture drawn again. ADR-048 in "a part already there never
  changes": its words still never do, but its picture can, when the learner asks for it
  and then chooses to use what came back. ADR-049 in what a slide's scene holds: the
  script it was drawn from, encoded, in a comment no player reads.
- **Keeps:** ADR-049 (a slide is data Adle draws: no model writes its scene), ADR-031 (a
  picture is never sprung on someone in the middle of a part: this one goes in at the
  learner's own press, and the part starts again), ADR-012 (an ask is one request, two at
  most), ADR-036 (what is sent and where is one press away), ADR-010 (a lesson enters the
  database only through `parse_bundle`), ADR-063 (a note brought in from a file carries
  words only).

## Context

The owner, on 2026-11-25: "allow answer a question to change the lecture slides if user
wants something specific... like for example in my case it forgot to draw hydrogen bonds".

A part's picture is a slide its lesson's writer scripted and Adle drew (ADR-049). Asking
about a part gave words, never a better picture, and a lesson is never written again once
begun, so a picture that left out what mattered stayed so. The slide's vocabulary could
already draw what was missing: a dashed line from an atom of one molecule to an atom of
another is a hydrogen bond. But only the scene file of a slide was kept, not its script,
so a picture could not be changed by what it was made of, only made anew.

## Decisions

1. **The learner says they want the picture changed.** The Ask dialog of a part that
   teaches with a picture (an explanation, a picture, a worked example, a summary) offers
   "Ask a question" or "Change the picture", and with the second, "What should the
   picture show?", in their own words. Without it, an ask is as it was. A part whose
   picture is still being drawn cannot be given another until it has arrived.
2. **Every slide keeps its script**, as the last line of its scene: a comment that holds
   the script's JSON in base64, so that none of a model's words is in a scene but as a
   quoted literal, at most 10,000 characters of it, and none that names a link. The
   script goes wherever the scene goes (a stored lesson, a copy of the data, a course
   file); the player never reads it.
3. **One request, as any ask, two at most** (`prompts.redraw_request`): the part's words
   with where each step of its picture plays (⟨2⟩, ⟨3⟩ …), its board, the script of its
   picture or, for a picture without one (a lesson made before this, a figure, a scene a
   model wrote), what it shows in words, the slide's vocabulary, and the learner's words.
   It goes where a lesson would go (purpose `lesson`): the model that writes slides. The
   answer is a sentence or two on what the picture now shows, and the whole slide.
4. **Adle draws it**, as any slide: checked element by element, its scene written from
   templates, and its steps placed on the part's words where they are (`_paced`): the
   words do not change. A slide with a slider is refused (it would be something to try,
   not a picture). A slide that cannot be drawn is asked for once more, told why; then
   nothing is kept, and the learner is told.
5. **It joins the lesson only at the learner's press**: "Use this picture", in the answer
   and in the note beside the part. The whole lesson goes through `parse_bundle` again with
   the new scene in the part's place and where its steps fall; the part's own picture and
   cues are kept with the note. "Put the original back" restores them; so does removing
   the note, so that nothing of a removed note stays in the lesson. Using a second note's
   picture in a part puts the first's back first, so that what is put back is always the
   part's own. A learner in that part starts it again.
6. **Said before it is sent**: with "Change the picture", "What is sent" names the part's
   picture, and where it goes is where a lesson would go.
7. **A course saved as a file carries the lesson as it is** (with a picture in use, as the
   part's), and its notes' words only.

## Alternatives

- **The model decides from the question whether to redraw.** Every ask would carry the
  slide's vocabulary (about 2,500 tokens), and a picture could change when nobody asked.
- **The picture changes as soon as the answer comes.** The learner may be in that part,
  and the drawing may be wrong; a press costs nothing and keeps the lesson theirs.
- **The lesson written again.** Minutes, a request of a lesson's size, and every part
  changed for one picture.
- **The script kept in a column of its own.** Every road a scene takes (written, extended,
  settled, copied, saved in a file, brought in) would have to carry it; in the scene it
  goes with it.

## Consequences

- A picture that missed what mattered can be mended by the learner who noticed.
- An ask that changes a picture is a request of a lesson's kind, larger than an answer's.
- A lesson made before this keeps no scripts: its pictures are drawn again from what they
  show in words, and may differ more from what they were.
- A picture drawn again is the writer's: it can be wrong, and the learner sees it before
  it is used. Drawing the example by hand showed a dashed line laid through another atom
  on its way to the oxygen, which the layout check did not find; the example was laid out
  again, and the check's blind spot is in "Known gaps".
