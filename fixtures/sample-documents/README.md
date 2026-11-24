# Sample documents

Small, original documents for testing import. **All content was written for Adle**; none of it is
copied from a real course. Safe to commit and to redistribute with the project.

| File | Purpose |
|---|---|
| `neural-networks-syllabus.md` | A well-formed syllabus with nested headings. Also the source text of the bundled sample course. |
| `study-notes.txt` | Plain UTF-8 text. |
| `lecture-notes.pdf` | A three-page PDF with a real text layer, printed by Chromium. |
| `chapter-with-outline.pdf` | A four-page chapter with a contents list, numbered sections (one beginning mid-page) and an outline (bookmarks), printed by Chromium: read by its headings. |
| `chapter-numbered.pdf` | The same chapter printed without an outline: read by its numbered headings. |
| `course-outline.docx` | A Word document with heading styles and a table. |
| `legacy-encoding.txt` | Latin-1 bytes: import succeeds with a warning. |
| `partly-scanned.pdf` | Pages 1 and 3 have text, page 2 is blank: import succeeds with a warning. |
| `lecture-notes-encrypted.pdf` | Password-protected: rejected as `encrypted_document`. Password: `adle-fixture-password`. |
| `scanned-handout.pdf` | No text layer at all: imported, both pages kept as pictures to be read (ADR-060). |
| `scanned-notes.pdf` | Typed notes photographed, handwritten notes with a drawing (pictures, no text layer), and a page of text: the first two are read from their pictures at the learner's word (ADR-060). |
| `damaged.pdf` | The first third of a real PDF: rejected as `malformed_document`. |
| `not-really-a.pdf` | Plain text with a `.pdf` name: rejected as `unsupported_type`. |
| `binary-named.txt` | Binary bytes with a `.txt` name: rejected as `unsupported_type`. |
| `empty.txt` | Zero bytes: rejected as `empty_document`. |

## Regenerating

The Markdown and text files are edited by hand. The rest are built:

```bash
npx electron scripts/fixtures/print-pdf.cjs scripts/fixtures/lecture-notes.html fixtures/sample-documents/lecture-notes.pdf
```

```bash
npx electron scripts/fixtures/print-pdf.cjs scripts/fixtures/chapter-notes.html fixtures/sample-documents/chapter-with-outline.pdf --outline
npx electron scripts/fixtures/print-pdf.cjs scripts/fixtures/chapter-notes.html fixtures/sample-documents/chapter-numbered.pdf
```

```bash
uv run --directory services/core python ../../scripts/fixtures/build_documents.py
```

On Windows, whose "Ink Free" font draws the handwriting:

```bash
npx electron scripts/fixtures/print-scans.cjs scripts/fixtures/scanned-notes.html fixtures/sample-documents/scanned-notes.pdf
```

Rebuilding changes the bytes of the PDF and Word files (timestamps, object ids). Tests assert on
extracted text and structure, not on file hashes.
