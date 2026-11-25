# ADR-066: A film's pictures are looked over by a model that sees them

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-065 in what a chapter is checked by. The engine found what it can
  measure (words over words, a line through words, something past the edge, text too small
  to read); now a model that reads pictures also looks at the screen at the end of every
  animation of a chapter, once, and what it sees is told to the chapter's writer like what
  the engine found. A film may send one more request a chapter, and pictures of each
  chapter go to that model's provider. There is a seventh kind of request, `storyboard`.
- **Keeps:** ADR-065 (a chapter is asked for once and mended at most three times; the
  version that ran with the least wrong is kept), ADR-060 (only a model seen to read a
  picture is sent one; a provider without one is sent none, and nothing else is asked in
  its place), ADR-012 (the bound on requests is said before anything is sent), ADR-036
  (what is sent, and where, is one press away).

## Context

The owner, on 2026-11-25, said yes to "a picture-reading model looking at each chapter's
storyboard images, one more request per chapter, catching things the layout check can't,
like an arrow pointing at nothing".

ManimGX's `inspect` writes a storyboard beside the scene as it runs: the screen at the end
of every animation, captioned with the animation's number, time, and line of the file, six
to a sheet, with what its layout check found outlined. Adle read only the check. A chapter
can pass it and still show an arrow drawn toward a box that comes only later, a label far
from what it names, or a bar still full while the voice says it has collapsed.

Tried by hand on 2026-11-25, with a chapter of a history course from a film made by hand
the day before (31 animations, 205 s, no layout problems, four sheets of 1928 by 1720,
140 to 200 KB each): NVIDIA's endpoint took all four sheets in one request, about 3,300
tokens each. Nemotron 3.5 Super thinks before it answers: with 3,000 tokens it thought to
the end of them and wrote nothing; with 16,000 it answered in 114 s (14,000 tokens of
thought). Asked broadly (arrows, labels, colors, agreement with what is said), it found
two faults a viewer would see, one half right, and one that was a matter of taste, and
missed an arrow pointing at nothing. Asked to go through each picture in turn, every arrow
by what is at each end and every label by what is beside it, it answered in 95 s (25,000
tokens in all) with three faults, all real, among them that arrow, and nothing false. It
still missed arrows too short to be seen.

Then a film of one chapter was made through Adle (34.5 minutes, five requests: written,
mended three times, looked over once). Its look, of four sheets, thought past the 24,000
tokens it was given and wrote nothing (238 s); the chapter was kept as it ran, as decided
below. The same look sent again by hand with `reasoning_effort`, which the endpoint took:
at "medium", 11,000 tokens of thought and 95 s, two faults, one real (a box far from the
date it belongs to) and one not (a timeline it wanted cut short at its first date); at
"low", 19,500 and 170 s, four, one real; at "none", 7.5 s and eight, mostly wrong. About
half of what the look says is so, and thinking is what makes any of it so.

## Decisions

1. **A chapter's pictures are looked over once**, by a model seen to read pictures
   (`ModelSpec.images`; Nemotron 3.5 Super at NVIDIA today, at a "reasoning_effort" of
   "medium", the one tried that both answered and kept to what is so), as a kind of
   request of its own (`storyboard`): the storyboard's sheets, at most eight, in one
   request; with what is said while each animation plays, so that a picture can be held to
   what is said. It is
   asked to go through the pictures one at a time and to name, for each fault, the picture
   it is first seen in: an arrow or line with an end in empty space or too small to see,
   a label away from what it names, a change that is said before it is shown, one thing in
   two colors, a drawing squeezed into a corner, a shape over another; an axis or a
   timeline may run on past what is on it, and nothing is to be added that the words do
   not say. What the layout check finds is left to it. At most eight faults, a line each,
   or "NOTHING".
2. **When:** once a version has run with nothing wrong by the engine's measure, while a
   mend is left; or the version before the last mend, if it ran but not clean, so that
   what is seen is still acted on, with what the engine found, in that last mend. A
   version that stopped is not looked over. The look is within the three mends' bound,
   not a fourth mend: a chapter is asked for once, mended at most three times, and looked
   over at most once, so at most five requests.
3. **What it sees is told to the writer** like what the engine found: by the line of the
   chapter's own file that played the animation, and its time ("line 160, in the picture
   at 85.1 s: …"), with the whole file, to be written again, and told that what was seen
   in the pictures is one viewer's: it puts right what it agrees is wrong. (A file sent
   back had been cut at 12,000 characters, as a picture of a lesson is; every chapter
   written by hand
   was 12,400 to 15,700, and a model asked to write the whole file again from part of it
   writes the rest anew. A chapter is now shown back up to the 60,000 characters the
   policy allows.) A version written after the look is kept over the one looked at if
   the engine finds no more wrong with it: the look is not asked again, and the writer
   was asked to put right what it saw.
4. **Nothing waits on it.** A look that is refused, fails, or whose answer cannot be read
   is passed over, and the chapter is kept as it ran. Without a model that reads pictures
   by the learner's choice (only AIHubMix, or only AIHubMix with a key), nothing is looked
   over, nothing is sent in its place, and the film is made as before.
5. **It is said before anything is sent**: "Sends pictures of each chapter to NVIDIA NIM to
   be checked", and the bound, one press from "Make the film"; in Settings, where
   "Checking films" goes, listed only when a provider that reads pictures has a key (as
   pages that are pictures are, ADR-060).

## What this is not

- **A judge of the teaching.** It looks at what is on the screen, not whether the
  chapter teaches well or is right: that is the writer's, from the rules of every lesson
  (ADR-061).
- **A loop.** One look a chapter, and what the writer makes of it is checked by the engine,
  not looked at again.
- **Sure.** It misses things (short arrows, in the trial), about half of what it says is
  so, and it can think past its tokens and say nothing. Its findings go to the writer, who
  has the file and judges them; a version is never kept for the look alone if the engine
  finds more wrong with it.

## Alternatives

- **The writer looks at its own pictures.** Kimi K3.1 Pro has not been seen to read a
  picture at NVIDIA, and its request is already the longest Adle sends.
- **A request a sheet.** Four to eight requests a chapter, and a fault that spans two sheets
  (a color that changes) is not seen.
- **Each picture alone, larger.** Thirty pictures or more a chapter, and more tokens. It
  may be what would catch an arrow too short to see on a sheet; it was not tried.
- **Looking the film over whole, after it is put together.** By then nothing is left to
  mend it with.

## Consequences

- A chapter that passes the layout check is held to what a viewer sees.
- A film costs up to five requests a chapter, not four, and about two minutes more a
  chapter for the look, more when it is mended for it.
- Pictures of every chapter (words from the learner's materials among them) go to the
  provider of the model that reads them, as the chapters' words already go to the writer's.
