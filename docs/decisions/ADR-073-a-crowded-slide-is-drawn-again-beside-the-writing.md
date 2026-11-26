# ADR-073: A crowded slide is drawn again, beside the writing

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-049 ("a slide is no request at all"): where the provider that writes
  lessons takes several requests at once, a slide whose words were in each other's way as
  it was tried is sent back, at most twice. ADR-069 in that such a word is not only shaded.
  ADR-038 in what a trial reports: the slide's layout as each step ended. The pictures a
  model writes for a lesson are drawn side by side.
- **Keeps:** ADR-069 (every such word still has its shadow, and keeps it where nothing
  better comes), ADR-031 and ADR-048 (a lesson is not kept back for its pictures, and a
  picture is never sprung on a learner in the middle of a part), ADR-068 (each provider's
  own limits), ADR-070 (the pictures stay Wanim scenes in the frame).

## Context

The owner, on 2026-11-25, after a film came out clean where slides did not: "about the
slides, if not 3 checks, now that concurrent stuff is allowed, ai can draw the next picture
and fix the last one parallelly; in fact a lot of things can be optimized this way". A film
is clean because each of its chapters is run and its overlaps told back to its writer
(ADR-065). A slide was laid out by Adle from a model's script, its labels moved apart, and
what could not be moved shaded (ADR-069); nothing told the model that wrote it.

## Decisions

1. **A slide says, as it is tried, what is in whose way** (`layout.audit`): after its
   counts, each word over another and each word under a line, by the names its script gave
   its elements ("note over water; water under heat"). The hidden trial (ADR-038) gathers
   what the slide said as each step ended, each once, eight at most, and reports it with
   its verdict.
2. **A slide that was crowded is sent back** to the model that writes lessons, told in
   sentences which of its own elements lay over which (`generation/slide_mends.py`; only
   names of its script are ever passed on, never what a scene said), with the part's
   words and where each step plays, and asked for the same slide in the same steps with
   them apart. One request each time, twice at most (`MAX_SLIDE_MENDS`). The new one must
   take the same steps at the same cues, passes the scene policy, and is tried in the
   hidden frame as the first was; it is kept only when fewer words are in each other's
   way, in the place of the one it mends and under its name, and the whole lesson goes
   through `parse_bundle` again (`LessonService.mend_scene`).
3. **Beside the writing, never in its way.** A mend runs while the lesson's later parts are
   written and its other pictures drawn, two at most at once, only where the provider that
   writes lessons takes several requests at once (NVIDIA; ADR-068). Where it takes one at a
   time (AIHubMix, a hundred a day), nothing is sent back: its day is not spent on mends,
   and the shadows stay. A lesson job waits a while at its end for mends still under way
   ("Checking the pictures"), and stopping or removing the lesson stops them.
4. **A lesson open meanwhile** looks again while a slide is mended (`mending`), and a mended
   slide takes its place in a part not begun yet; a part on the screen keeps the picture it
   began with until the learner comes to it again.
5. **The pictures a model writes for a lesson are drawn side by side**: up to three at once,
   as many as the provider that draws them takes at once (one at AIHubMix), each still one
   request and one deliberate retry at most.

## Consequences

- A lesson written at NVIDIA can cost up to two more requests a crowded slide, each with
  nothing in it but the lesson's own: its course and concept, the part's words, its slide.
  Settings → Privacy & data says so.
- What the learner sees is the slide with the fewest words in each other's way; a slide
  that could not be mended is no worse than before.
- Being drawn at once, a lesson's pictures are ready sooner where the provider allows it.
