"""Build the binary document fixtures in fixtures/sample-documents.

Run from the repository root, after the base PDF has been printed:

    npx electron scripts/fixtures/print-pdf.cjs scripts/fixtures/lecture-notes.html \
        fixtures/sample-documents/lecture-notes.pdf
    uv run --directory services/core python ../../scripts/fixtures/build_documents.py

Every file is small, original, and safe to commit. The broken ones are broken
on purpose; see fixtures/sample-documents/README.md.
"""

from __future__ import annotations

from pathlib import Path

import docx
from pypdf import PdfReader, PdfWriter

OUT = Path(__file__).resolve().parents[2] / "fixtures" / "sample-documents"
BASE_PDF = OUT / "lecture-notes.pdf"
#: Published in the README so the fixture is reproducible; it protects nothing.
FIXTURE_PASSWORD = "adle-fixture-password"  # noqa: S105


def build_docx() -> None:
    document = docx.Document()
    document.add_heading("Course outline: Neural networks", level=0)
    document.add_paragraph("Sample course outline written for Adle's tests.")

    document.add_heading("Week 1: Neurons", level=1)
    document.add_paragraph(
        "We begin with the perceptron: inputs, weights, a bias, and an activation function."
    )
    document.add_heading("Reading", level=2)
    document.add_paragraph("Chapter 1, sections 1.1 to 1.3. Bring questions about the bias term.")

    document.add_heading("Week 2: Learning", level=1)
    document.add_paragraph(
        "Loss functions tell us how wrong a prediction is. Gradient descent uses the slope of "
        "the loss to improve the weights step by step."
    )
    table = document.add_table(rows=3, cols=2)
    for row, (term, meaning) in zip(
        table.rows,
        [
            ("Term", "Meaning"),
            ("Learning rate", "The size of each update step"),
            ("Epoch", "One pass through all of the training examples"),
        ],
        strict=True,
    ):
        row.cells[0].text = term
        row.cells[1].text = meaning

    document.add_heading("Assessment", level=1)
    document.add_paragraph("Two short quizzes and one practical exercise on backpropagation.")
    document.save(str(OUT / "course-outline.docx"))


def build_pdf_variants() -> None:
    base = PdfReader(BASE_PDF)

    encrypted = PdfWriter()
    for page in base.pages:
        encrypted.add_page(page)
    encrypted.encrypt(FIXTURE_PASSWORD, algorithm="RC4-128")
    with (OUT / "lecture-notes-encrypted.pdf").open("wb") as handle:
        encrypted.write(handle)

    scanned = PdfWriter()
    for _ in range(2):
        scanned.add_blank_page(width=595, height=842)
    with (OUT / "scanned-handout.pdf").open("wb") as handle:
        scanned.write(handle)

    partly = PdfWriter()
    partly.add_page(base.pages[0])
    partly.add_blank_page(width=595, height=842)
    partly.add_page(base.pages[2])
    with (OUT / "partly-scanned.pdf").open("wb") as handle:
        partly.write(handle)

    # A real PDF cut off part-way: what an interrupted download looks like.
    data = BASE_PDF.read_bytes()
    (OUT / "damaged.pdf").write_bytes(data[: len(data) // 3])


def build_mislabelled() -> None:
    (OUT / "not-really-a.pdf").write_text("This is plain text with a .pdf name.\n", "utf-8")
    (OUT / "binary-named.txt").write_bytes(bytes(range(256)) * 8)
    (OUT / "empty.txt").write_bytes(b"")
    (OUT / "legacy-encoding.txt").write_bytes(
        "Notes in a legacy encoding: caf\xe9, na\xefve, 20\xb0C.\n".encode("latin-1")
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_docx()
    build_pdf_variants()
    build_mislabelled()
    for path in sorted(OUT.iterdir()):
        print(f"{path.stat().st_size:>8}  {path.name}")  # noqa: T201
