# ADR-061: A lesson is formed by rules, and each subject has its own

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** ADR-049 and ADR-050's "how to teach", which was one list written for
  mathematics with three lines for everything else; the lesson prompt's single example; the
  picture vocabulary of a slide; which ways of teaching are offered. A course gains a subject.
- **Keeps:** ADR-049 (a slide is data, and Adle draws it), ADR-050 (the case first, the rule
  made out of it), ADR-012 (the number of requests: none is added), ADR-047 (what can be
  mended is mended), ADR-055 and ADR-056 (a picture's words kept clear, said by every example
  the player runs).

## Context

The owner, on 2026-11-24: "currently the app is too focused on maths, we need to generalize it
to all subjects ... a generalized idea of first visual exemplification and then academic
theory, but if a subject requires specification which other subjects don't then it should
explicitly list specs for that, like maths requiring graphs and examples and then equations,
but english explaining everything within the examples and in what way, chemistry showing
experiments ... every lesson needs axiomatic rules as to how a lesson should be formed."

What made Adle read as an app for mathematics:

- **The rules of a lesson lived in a prompt**, as advice written while lessons of probability
  and calculus were looked at. Three of its lines spoke for every other subject.
- **The one example a writer was shown** was the area of a rectangle. A model follows the
  example it is shown more closely than any rule beside it.
- **What a slide could draw** was what mathematics draws: axes, curves, areas, tangents,
  vectors, coins and dice, with boxes and arrows for the rest. Chemistry had nothing to show
  an experiment in, history no timeline, programming no code.
- **The ways of teaching** offered for another explanation were the same for every course:
  a lesson on the French Revolution could be asked for as "Step-by-step math".

## Decisions

- **The rules are written down once**, in `lessons/axioms.py`, pure. Seven rules of every
  lesson, in the order a lesson obeys them: something to look at first; the idea worked out
  in it; the rule after, made from it; a name after what it names; one idea at a time, and
  a question; a picture for every part that teaches; nothing made up. Each is kept twice,
  side by side: one short line for the learner, and the brief a lesson's writer is given.
- **Thirteen kinds of subject, each with what it needs besides**: mathematics, physics,
  chemistry, biology, Earth and space, computer science, language, literature, history,
  economics and business, society and mind, arts and music, and a general one. Each says
  what its case is, how it is worked, how its theory is stated, what its questions ask, and
  what it must take care of (units; a balanced equation and a word about safety; dates
  that are right or left out; no invented quotation, study or figure). Mathematics: a
  picture or a count, one example in numbers, then the equation. A language: real
  sentences, the words that matter marked and changed, the rule in one line. Chemistry:
  an experiment, what the particles do, the equation.
- **A course has a subject** (`courses.subject`, revision 0014). Adle places it by its
  name, with no request (`axioms.guess`: words that say a subject, a word in the name
  counting twice a word elsewhere, and no guess when two subjects are as likely); the AI
  names it with the course's plan, in the plan's own request; the learner may choose it,
  and their choice stands. A course from before is placed as the core starts. A lesson of a
  course nobody has placed is formed by a guess from its concept.
- **A writer is given the rules, its subject's needs, and its subject's example**: one
  subject at a time, and one example (`generation/examples.py`), which obeys the rules it
  is an example of (a test) and is drawn by the player like any slide. A lesson's request
  is about as long as it was.
- **A slide draws what other subjects need** (`generation/slides.py`): a **timeline**; a
  **vessel** (a beaker, a test tube, a flask) in which something is seen to happen: a
  color, none at all, a level, bubbles, a solid, heat; a **molecule**, its atoms placed by
  the core; and **code**, a line at a time. Each is data, checked and drawn by the core,
  its words reaching the scene only as quoted literals, as ADR-049 has it.
- **The ways of teaching offered are those that suit the subject**, for another
  explanation Adle chooses and for the one the learner asks for.
- **The learner can read it.** A course says what it is taught as; one press opens "How
  lessons are formed": the rules, this subject's three steps, and the choice of subject.
  The words are the core's own (`lessons.rules`).
- **What the core can check or mend, it does.** A rule that a slide shows before its case
  is moved after it (ADR-050, as before). A web address in anything an element says costs
  the picture that element and not the whole slide. And what real lessons asked of a slide
  and did not get is forgiven (below).

## Tried by hand

Six lessons through NVIDIA NIM (Nemotron 3 Ultra), one request each, 62 to 161 seconds, on
2026-11-24: neutralization, why the French Revolution began in 1789, bubble sort, ser and
estar, the cell membrane, Newton's second law. Each was formed as its subject asks: the
chemistry lesson opened on a beaker of indicator fading as acid was added, went on to the
ions, ended on the balanced equation, and said that it belongs in a laboratory; the history
lesson put six dated events of 1789 on a timeline (all of them right) and set two
historians' explanations side by side; the programming lesson ran one pass over five numbers
by hand before it showed code.

Their slides were then run in the player, and what they showed was mended in the slides
module, each with an example the player steps through and a test
(`test_slide_real_lessons.py`):

- characters written small ("H₂O", "Na⁺") have no glyph in the face the player sets words
  in: they are set as formulas, a formula of chemistry upright;
- a quantity ("10 N") was set as a number times a letter: its unit is upright;
- a liquid made "colorless" stayed as it was; an arrow "to the right of" a cart (a push),
  a list set to new rows (a pass of a sort), an arrow moved to what it compares next, and
  the words on an arrow changed were all left out: they are drawn;
- an edge between nodes that are not neighbors ran through the names between them: it goes
  round them;
- one molecule written as three elements, the first moved onto the second and then "the
  second" onto the third, was drawn twice: what is moved onto something never shown stands
  for it;
- two things put on one side of the same thing lay over each other, and one put under what
  stood at the foot of the stage was pushed back onto it: they stand one beyond the other,
  or across from it;
- a value shown as if it were drawn **stopped the scene**: it is passed over.

Of the 34 slides of those six lessons, as they were first drawn: 8 said that words lay over
words or under a line, 1 did not run, and 6 left out something the lesson had written to be
drawn. Drawn again after the mends: all 34 run, 4 say so, and none leaves out anything
written to be drawn. Those four are a model's own layout (a molecule drawn across the word
"membrane" to show it crossing): nothing in the app acts on what a slide says of its layout,
and Adle's own examples say nothing (42 of 42).

## Alternatives

- **Every subject's rules in every request.** Longer for each lesson, and the example a
  model is shown still decides what it draws. One subject at a time is what a teacher of
  that subject is told.
- **Asking a model for a subject in a request of its own.** A request more for what a name
  usually says, and nothing a learner could read or change before a lesson is written.
- **A subject for each lesson.** A field more for a model to get wrong on every lesson. A
  course's subject can be read and changed in one place, and a lesson of a course nobody
  has placed is still formed by what its concept says.
- **Pictures of real apparatus, or photographs.** Adle has no network and ships no
  pictures; a slide is drawn from data, and what is drawn can change as it is spoken of.
- **A fixed-width face for code.** The player sets words in one face. Setting code as TeX
  in a typewriter face would lose quotation marks, braces and backslashes; in the stage's
  own face a line keeps every character and its indentation.
- **Checking a whole lesson against the rules and asking again.** A lesson is stored at its
  first part and never written again (ADR-048). The rules are given to the writer, shown
  by an example, and enforced where the core puts a slide together.

## Consequences

- A lesson of chemistry, a language, history or programming is formed the way that subject
  is taught, and can draw what it needs. A course says what it is taught as.
- 25 more slide examples for the player to step through (42 in all): about four minutes
  more of journeys when everything runs.
- The guess is made from English words. A course named in another language is general until
  the AI plans it or the learner says.
- A subject is one of thirteen. A course between two of them is one of them, or general.
- Code is not set in a fixed-width face.
- A model can still lay a slide out so that words lie over a drawing it meant them to lie
  over. The audit says so; nothing acts on it outside the tests.
