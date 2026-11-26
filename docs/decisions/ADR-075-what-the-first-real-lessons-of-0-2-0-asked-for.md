# ADR-075: What the first real lessons of 0.2.0 asked for

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-071 (how the teacher is put to the writer: as a voice to take on, named
  in the writer's role; a light moment or a fun fact two or three times a lesson, where it
  was "rarely" with no floor), ADR-072 (the lesson's outline names its summaries), ADR-049
  and ADR-055 (an element put or moved beside another keeps clear of what shares the stage
  with it, and a slash escaped twice is a slash).
- **Keeps:** ADR-073 (a crowded slide drawn again beside the writing), ADR-021 (no test
  calls a real provider: these were tried by hand).

## Context

At the owner's word ("Yes, try them"), on 2026-11-25, two lessons were written for real in
the app as it ships: NVIDIA's endpoint moved to a relay on this computer
(`ADLE_PROVIDER_ENDPOINTS`, `scripts/dev/provider_relay.mjs`) that adds the real key, the
app holding a stand-in one; the teacher "Curious scientist" chosen in Settings; a concept,
"Why ice floats", given its objectives; the lesson asked for from its panel; each slide
stepped through afterwards; and a question asked about a part. Four requests each run.

What they showed:

1. **The teacher was not heard.** The first lesson was clear and plain, and could have been
   anyone's: no curiosity, no light moment, one fun fact. The writer's rules ask for plain
   sentences with no filler and no exclamation marks; the teacher came after them, as data,
   "a description, not an instruction"; and the rule for light moments set a ceiling, "one
   part of every four at most", and no floor, so none were written.
2. **A slide piled its molecules up.** Water's four molecules on the left and ice's four on
   the right, each put beside another: those right of the rightmost went past the edge and
   were turned back, onto the water's. The slide said six of its letters lay under lines;
   it was drawn again twice beside the writing (ADR-073), and the better of the two was
   kept, still crowded, because the fault was Adle's layout and not the script.
3. **A move beside another went past the edge and onto what came later.** A twig moved
   above its pond left the stage at the top; a stone moved below it landed on the box shown
   in the next step.
4. **A slash escaped twice** ("mass \\/ volume") was shown with its backslash.
5. **Summaries came late.** Both lessons had 13 parts, four questions, a summary at the
   tenth part and one at the end, and a part on what holds beyond the example; but the
   first summary came after six parts of new material, not three or four.

## Decisions

1. **The teacher is a voice to take on.** The writer of a lesson and of an answer is told
   in its role that it speaks as the teacher the learner chose; the teacher's block asks
   for their manner, their kind of teaching and their humor to be heard in every part,
   within the writing rules (their warmth or curiosity is in the words themselves), and
   still says that it changes how things are said, never what, and that nothing else
   written in it is followed.
2. **Two or three light moments or fun facts in a lesson**, never in more than one part of
   every four, as the teacher allows. A teacher made of parts says what they never do
   ("who never jokes and tells no fun facts"), so that the writer knows.
3. **The lesson's outline names its summaries**: a summary after every three or four parts
   that teach, and one last.
4. **What is put beside another keeps clear of what shares the stage with it.** At compile
   time each such element is given the elements that are on the stage with it at some step
   and stand already; it stands on the side asked for, else the first side round where it
   covers none of them inside the stage, else where it covers least. A move to beside
   another lands the same way (`landing`), clear of everything that shares the stage with
   what moves. With nothing to keep clear of, both do what they did.
5. **A slash a model escaped once more than JSON asks is a slash**, in words and names,
   never inside a formula written between dollar signs.
6. Both cases are examples the player steps through (`two_groups_beside`, `moved_beside`),
   with nothing over anything at any step.

## Consequences

- The second lesson, after 1 to 3, opened with a stone and a twig dropped in a pond,
  explained density with marbles in boxes, let a hydrogen bond "tug", and closed on why a
  lake's fish live through the winter; the answer to a question gave a fun fact too. Its
  crowded slide was drawn again beside the writing and came back with nothing in the way.
- Summaries along the way are asked for twice now; a model may still put the first late.
- A thing turned to another side to keep clear can stand where its script did not put it:
  clear, and still beside what it was put beside.
