# ADR-041: Reading more of a document, and finding a passage by any form of a word

- **Status:** Accepted
- **Date:** 2026-11-21
- **Changes:** ADR-007 in what the Word parser keeps and in one more index. Nothing about
  how files are read (a worker process, paths only from the main process, bounds) changes.

## Context

The owner asked whether Adle reads a learner's materials well: images, equations, tables,
and other files than PDF and Word.

What it did: a PDF's text layer, page by page (pypdf); a Word document's paragraphs under
its headings, its tables flattened into rows of cells joined by bars, and nothing of its
equations or pictures (python-docx's text leaves Office Math out); Markdown and plain text.
A scanned page is refused, since Adle does not recognise text in images. Passages are found
by SQLite's full-text search, word for word: a concept that says "weighted" finds nothing
in notes that say "weight".

## Decisions

- **A Word document keeps its equations, written out in a line** (`omml_text`): a fraction
  as `(a+b)/c`, a power as `x^2`, a subscript as `w_1`, a root, a sum with its limits, a
  bracket, a function. Not typesetting: enough of the structure survives to be searched
  for, quoted, and told apart (a fraction from a product).
- **A picture in a Word document is kept as what its description says it is**
  (`[Picture: …]`), where its author wrote one. A picture without one is not guessed at.
- **A Word table is a Markdown table**, its first row the header, a merged cell said once,
  a bar inside a cell escaped. A model reads a table as a table.
- **The passages that ground a lesson or an answer are found by any form of a word**: a
  second full-text index, with the Porter stemmer, over the same passages (migration 0009,
  `source_chunks_stems`). Searching the materials keeps the index it had, because there the
  last word is matched as a prefix while it is typed, which a stemmed index cannot do.
- The Word parser's revision is now 2: a document imported before says so in its parser
  version, and is read the new way if it is imported again.

## Not done, and why

- **PowerPoint and web pages.** Both would be a new kind of source, and the kinds a source
  and a section may be are held by check constraints on tables other tables refer to.
  Changing them in SQLite means rebuilding those tables, which with foreign keys enforced
  deletes what refers to them unless it is done in a particular order with the keys off,
  something the migrations cannot do inside their transaction today. That deserves its own
  change, with its own test of a copy of real data.
- **Text in images and scanned pages (OCR), and descriptions of figures.** Both need a model
  that runs on this computer and does not ship with it (tens to hundreds of megabytes). They
  belong with the other optional download, the natural voice (ADR-042): one way to fetch,
  check and remove what Adle downloads at the learner's word.
- **Tables in PDFs.** A PDF has no tables, only text placed on a page; recovering them is
  guesswork that would read some documents worse. Not attempted.

## Consequences

- An equation, a picture's description and a table in a Word document can be searched for,
  quoted in a lesson, and cited.
- A lesson about "weighted sums" finds notes about "weights".
- Each passage is indexed twice; the index is a small part of what a passage costs to keep.
