# ADR-054: One compact row of lesson controls, and "This didn't help" can be taken back

- **Status:** Accepted
- **Date:** 2026-11-23
- **Changes:** how the lesson's bar of controls is laid out and named on screen. What a
  "this did not help" report means to what is suggested next: it counts until the learner
  takes it back.
- **Keeps:** ADR-012 and the core's rule that `learner_events` is append-only (taking a
  report back is a row of its own; nothing is deleted or changed), "this did not help" is
  recorded first and never argued with, ADR-035 (the lesson is watched on its screen, the
  bar under it), ADR-036 (few words).

## Context

The owner looked at the bar of controls under a lesson and asked why it took two rows when
there was room, and for less of it: "make it compact- too much text- for much used buttons-
keep em big and all but otherwise- i think speaker icon without text is sufficient and same
goes for captions", and "allow to revert back if mistakenly clicked on this didn't help".

The bar was two groups of buttons that wrapped as wholes: whenever the two together were
even a little wider than the bar, the whole second group went to a second row, leaving the
room the owner saw beside both. A note ("Answer or skip to continue.", "The next part is
being written.") made the second group wider still. And "This didn't help" could not be
undone: a press by mistake changed what the course suggested next, and nothing in the
lesson said so.

## Decisions

- **The bar is one row**: the lesson's own controls on the left (Previous, Start / Pause /
  Resume, Read aloud, Transcript), what the learner may need to know just now in the
  middle, and what they can do about the part on the right (Ask a question, This didn't
  help, Continue / Finish lesson, Full screen). The note wraps in its own room in the
  middle, and takes no room when there is nothing to say, so the buttons keep one row
  whenever the two groups fit side by side; only a window too narrow for them moves the
  right group down. Seen at 1280, 1100, 960 and 820 points wide: one row, with a note and
  without.
- **The controls pressed most keep their words**: Previous, the play button, Ask a
  question, Continue and Finish lesson. **Read aloud, Transcript and This didn't help are
  icons**: a speaker (on, or struck through), captions (on, or struck through) and a thumb
  down. Each is a toggle (`aria-pressed`), named for assistive technology and on hover by
  the words it had, and shows when it is on.
- **"This didn't help" is pressed while it stands.** Pressing it records the report and
  opens the dialog of ways forward, as before; that dialog now has **Undo** once the
  report is saved. Pressed again in the bar, the report is taken back, with nothing to
  choose. Either way the learner is told "Feedback removed", and what the course suggests
  is what it was before.
- **Taking back is a row of its own** (`explanation_unhelpful_withdrawn`, revision 0012,
  `DELETE /lessons/{lesson_id}/unhelpful/{segment_id}`): it withdraws every report about
  that part of that lesson made before it, and a report made after it stands again.
  Which reports stand is decided in one place (`evidence.standing_reports`), by the order
  the rows were written. A lesson says which of its parts stand reported
  (`LessonForPlayer.unhelpful_parts`), so the toggle tells the truth when the lesson is
  opened again. With nothing to take back, nothing is written.

## Alternatives

- **Deleting the report.** `learner_events` is append-only, and the evidence a learner
  gave is never rewritten; a second row says what happened.
- **A toast with "Undo" after every report.** The dialog opens on the press and is where
  the learner is looking; a toast under it would be read after the dialog is closed, if at
  all. The bar's pressed toggle stays where the report was made.
- **Making every button an icon.** The owner asked to keep the much-used ones as they are,
  and a word is quicker to read than a picture to learn.

## Consequences

- The buttons keep one row on any window at least 820 points wide, the narrowest tried,
  and a note no longer pushes them to a second row.
- A report said by mistake costs the learner nothing: the next suggestion is as it was.
- The two "didn't help" kinds of row are read together wherever reports are counted; a new
  reader of reports uses `standing_reports`.
