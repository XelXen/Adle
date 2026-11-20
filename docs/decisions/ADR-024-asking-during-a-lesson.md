# ADR-024: Asking Adle a question in the middle of a lesson

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The owner asked that a learner be able to ask questions in the middle of a lesson. PLAN.md 3.3
already asks that a learner can "request a simpler explanation, mathematical derivation,
example", and until now the only way was to say "This did not help" and have a whole new
lesson written.

PROMPT.md 20 sets the limit: Adle "must not feel like a chatbot placed beside an animation
canvas". And everything that applies to any model request applies here: the learner's text is
data, a model's answer is untrusted, answer keys stay in the core, what is sent is said first.

## Decisions

- **An "ask" is a note in the margin, not a conversation.** One question about one part of
  one lesson, one answer. Each stands alone: no earlier question or answer is sent with the
  next. It is kept beside the part it was about (`lesson_asks`), folded away until asked for,
  and can be removed. It is called an "ask" in code to keep it apart from the questions a
  lesson puts to the learner.
- **Asking is a button in the lesson's bar** that pauses the lesson and opens a dialog: a
  field for the learner's own words, and a few ready-made questions (say it more simply, give
  an example, show the mathematics, why is this true), which are PLAN 3.3's requests. What
  will be sent and where is said in the dialog, and nothing is sent until "Ask".
- **The learner does not have to wait in front of it.** The answer is a job in the quick
  lane (below). The dialog can be closed while it is written; the answer then appears beside
  the part, the app says so, and so does the operating system if Adle is in the background.
- **What is sent** (`prompts.ask_request`): the course's name, the concept, the lesson's
  title and the titles of its parts, what the part says and shows (its narration, its board,
  its picture in words), up to three passages of the learner's materials found with their
  question, and the question. Everything from the learner or a lesson is inside a quoted
  block; the question's block says it is something to answer, never an instruction.
- **A question the lesson is asking is never answered for the learner.** For a checkpoint,
  the stem and the choices are sent, never which is right, the accepted answers, the expected
  number, the rubric, the hint, or the per-choice feedback; an ordering question's items are
  sent sorted by their words, because their stored order is the answer. The prompt forbids
  giving the answer. The lesson's own explanation is included only once the learner has
  answered.
- **Asking about an open question counts as help.** An answer to a checkpoint given after an
  ask about that part is recorded as an aided answer, like one given after the hint, in the
  core (`AssessmentService.answer`). What was asked is not looked at. The dialog says this
  before the learner asks. Nothing else is learned from an ask: it is not evidence.
- **The answer is read strictly and shown as text.** One JSON object with one to four short
  paragraphs (plain sentences are accepted too); each is display text like a lesson's: no
  links, markup, or paths, mathematics between dollar signs. A source is a number the prompt
  offered, or it is dropped. One request, a second only if the first answer was unusable,
  then the learner is told. The learner's own words are shown as plain text, never typeset.
- **Bounds:** a question is 3 to 500 characters; a lesson keeps 30 asks; one ask per lesson
  is answered at a time.
- **Two lanes of jobs.** Long work (an import, a lesson, a list of concepts) still runs one
  job at a time. A second lane runs what the learner is waiting for (an ask, a check of a
  key), so a question never queues behind a lesson that takes minutes. With "automatic"
  (ADR-023) it goes to the quick provider.
- **Every answer says who wrote it and that a model wrote it and can be wrong.**

## Consequences

- An ask costs one of the day's requests. With one slow provider it takes as long as that
  provider takes; the dialog says how long that usually is.
- The learner's questions are their own text, kept in the local database. They are in a
  saved copy and are deleted with the lesson, the course, or everything.
- A model can still be wrong, or leak the idea behind an answer while "helping to think".
  The answer key itself is never in the request, and the aided flag means such an answer
  counts for less.
- It is not a tutor that remembers. A follow-up has to say what it is about. That is the
  price of it not being a chat, and of each request staying small.
