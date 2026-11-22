# ADR-046: A PDF's whole syllabus, from its outline, its numbered headings, or its pages

- **Status:** Accepted
- **Date:** 2026-11-22
- **Changes:** ADR-007 in how a PDF is cut into sections, and ADR-009 in what a course plan
  is asked with when a document has no headings. Nothing about how a file is read (a
  worker process, paths only from the main process, bounds) changes.

## Context

The owner: "when a pdf is uploaded- it doesnt cover the full syllabus for some reason?",
with a chapter of their lecture notes (26 pages, ten sections) to try it on.

What happened: a PDF was read page by page and every page was a section with no title, so
there were no headings to make a plan from. The course plan was then asked with the
excerpts that fit, which were the first pages, and it planned the first pages. The notes
had their structure all along: an outline (the bookmarks a PDF carries), and numbered
headings in the text ("5.3 Expected Value and Variance"). The text's reflow also joined a
line of the table of contents ("5.1 The Cumulative Distribution Function . . . . 2") and a
numbered heading into the paragraph around it, so a heading could not be found even by
eye.

## Decisions

- **A PDF's sections come from its outline** when it has one with at least two entries:
  each entry's title, level (from how deep it is nested) and page.
- **Else from its numbered headings**: a line on its own that starts with a number such as
  `3`, `3.2` or `3.2.1` and a capitalized title of at most 80 characters, when there are at
  least three of them and their numbers go up.
- **A heading's section is the text from where it stands to the next heading**, across
  pages, cut where each page begins so that a passage still has its page. Text before the
  first heading is kept, a section for each page it is on, as every page was before. A
  bookmark to a page without text points at the next page that has some.
- **Else, as before, a section for each page.**
- **The reflow does not join** a line with dot leaders (a table of contents) or a numbered
  heading to the lines around it.
- The parsers' revision is 3: a document imported before says so in its parser version,
  and is read the new way when it is imported again.
- **A plan is asked with every heading** the materials have (up to 60), as before. **A
  document with no headings at all** is shown to the planner as how each of its pages
  begins (220 characters, evenly chosen across the document, up to 60 pages), from the
  first to the last, inside the same quoting as anything else from a learner's document.
- **The owner's own chapter is a test where it is** (`testchap.pdf` at the root of the
  repository, ignored by git): read section by section, and a plan asked with all of it.
  It is theirs and is never committed. Two documents of Adle's own stand for it everywhere
  else: `fixtures/sample-documents/chapter-with-outline.pdf` and `chapter-numbered.pdf`,
  printed from `scripts/fixtures/chapter-notes.html`.

## Consequences

- Measured on the owner's chapter: ten sections where there were twenty-six untitled
  pages; nine headings offered to the planner (the overview left out, as before); a plan of
  nine concepts in 32 seconds, one for each heading, none missed.
- A PDF whose outline is wrong (some are made by tools that guess) is cut where its outline
  says. The text is all there either way: only where one section ends changes.
- A scanned PDF is still refused (ADR-041): it has no text to find headings in.
