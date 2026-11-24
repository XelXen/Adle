"""Document parsing, type detection, and chunking, against real fixture files."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from adle_core.ingestion import worker
from adle_core.ingestion.chunking import (
    MAX_CHARACTERS,
    TARGET_CHARACTERS,
    chunk_document,
    chunk_section,
)
from adle_core.ingestion.detect import detect_kind
from adle_core.ingestion.extract import extract_in_process
from adle_core.ingestion.parsers import clean_text, reflow_wrapped_lines
from adle_core.ingestion.types import (
    DEFAULT_LIMITS,
    DocumentKind,
    ExtractedSection,
    IngestionError,
    SectionKind,
)
from adle_core.ingestion.worker import document_from_json, request_for

DOCUMENTS = Path(__file__).resolve().parents[4] / "fixtures" / "sample-documents"

# Characters that are invisible in an editor are spelled out by code point.
ZERO_WIDTH_SPACE = chr(0x200B)
PRIVATE_OPEN = chr(0xE000)
PRIVATE_CLOSE = chr(0xE001)
COMBINING_ACUTE = chr(0x0301)


def extract(name: str, **limit_overrides: float) -> object:
    limits = replace(DEFAULT_LIMITS, **limit_overrides) if limit_overrides else DEFAULT_LIMITS
    return extract_in_process(DOCUMENTS / name, name, limits)


# -- supported formats -----------------------------------------------------


def test_markdown_is_split_at_headings_with_the_full_heading_path() -> None:
    document = extract_in_process(DOCUMENTS / "neural-networks-syllabus.md", "syllabus.md")
    assert document.kind is DocumentKind.MARKDOWN
    assert document.warnings == ()
    titles = [section.title for section in document.sections]
    assert titles[0] == "Introduction to Neural Networks"
    assert "Introduction to Neural Networks › Unit 1: The perceptron › Weights and bias" in titles
    assert "Introduction to Neural Networks › Unit 7: Gradient descent" in titles

    weights = next(s for s in document.sections if (s.title or "").endswith("Weights and bias"))
    assert weights.kind is SectionKind.HEADING
    assert weights.level == 3
    assert "The bias is a number added to the weighted sum." in weights.text
    # Markup is gone; the words remain.
    assert "*" not in document.sections[0].text
    assert "Sample syllabus written for Adle" in document.sections[0].text
    # Text from one section never leaks into another.
    assert "ReLU" not in weights.text


def test_markdown_heading_levels_that_skip_do_not_corrupt_the_path(tmp_path: Path) -> None:
    file = tmp_path / "skips.md"
    file.write_text(
        "### Deep start\n\nfirst\n\n## Shallower\n\nsecond\n\n### Deep again\n\nthird\n"
    )
    document = extract_in_process(file, file.name)
    assert [(s.title, s.level) for s in document.sections] == [
        ("Deep start", 3),
        ("Shallower", 2),
        ("Shallower › Deep again", 3),
    ]


def test_pdf_keeps_one_section_per_page_with_its_page_number() -> None:
    document = extract_in_process(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    assert document.kind is DocumentKind.PDF
    assert document.warnings == ()
    assert [section.page_number for section in document.sections] == [1, 2, 3]
    assert all(section.kind is SectionKind.PAGE for section in document.sections)
    assert all(section.confidence == 1.0 for section in document.sections)
    # Sentences wrapped at the page margin are rejoined; headings keep their own line.
    first = document.sections[0].text
    assert "For a regression problem the usual choice is the mean squared error" in first
    lines = first.splitlines()
    assert lines[0] == "Lecture notes: loss and gradient descent"
    assert "Measuring error with a loss function" in lines
    assert "The gradient points uphill" in document.sections[1].text
    assert "equals 1.95" in document.sections[2].text
    assert document.parser == "pypdf"


def test_docx_uses_heading_styles_and_keeps_table_rows() -> None:
    document = extract_in_process(DOCUMENTS / "course-outline.docx", "course-outline.docx")
    assert document.kind is DocumentKind.DOCX
    titles = [section.title for section in document.sections]
    assert "Course outline: Neural networks › Week 1: Neurons › Reading" in titles
    learning = next(s for s in document.sections if (s.title or "").endswith("Week 2: Learning"))
    assert "Gradient descent uses the slope" in learning.text
    assert "Learning rate | The size of each update step" in learning.text


def test_plain_text_is_one_document_section() -> None:
    document = extract_in_process(DOCUMENTS / "study-notes.txt", "study-notes.txt")
    assert document.kind is DocumentKind.TEXT
    assert len(document.sections) == 1
    assert document.sections[0].kind is SectionKind.DOCUMENT
    assert "new weight = old weight - learning rate x gradient" in document.sections[0].text


def test_legacy_encoding_is_imported_with_a_warning_and_lower_confidence() -> None:
    document = extract_in_process(DOCUMENTS / "legacy-encoding.txt", "legacy-encoding.txt")
    assert "café" in document.sections[0].text
    assert len(document.warnings) == 1
    assert "Windows-1252" in document.warnings[0]
    assert document.sections[0].confidence < 1.0


def test_utf16_text_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    file = tmp_path / "wide.txt"
    file.write_bytes("Größe und Übung".encode("utf-16"))
    assert extract_in_process(file, file.name).sections[0].text == "Größe und Übung"


def test_partly_scanned_pdf_imports_what_it_can_and_says_what_it_skipped() -> None:
    document = extract_in_process(DOCUMENTS / "partly-scanned.pdf", "partly-scanned.pdf")
    assert [section.page_number for section in document.sections] == [1, 3]
    assert len(document.warnings) == 1
    assert document.warnings[0] == (
        "1 of 3 pages had no selectable text (page 2). "
        "It may be an image or a scan and was skipped."
    )


def test_a_page_drawn_past_the_readers_budget_is_read_with_a_larger_one() -> None:
    # A detailed diagram (a molecule drawn atom by atom) is more work than pypdf reads by
    # default, and the whole page's words were lost (2026-11-24). Under a budget this
    # small every page of these notes is such a page: each is read on its second try,
    # exactly as it reads with none, and nothing is said.
    from pypdf import apply_configuration

    plain = extract_in_process(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    with apply_configuration(stream_parsing_work_maximum_count=50):
        heavy = extract_in_process(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    assert heavy.sections == plain.sections
    assert heavy.warnings == ()


def test_second_tries_stop_when_their_time_is_spent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Each second try takes a second of this clock, and two are allowed: the third heavy
    # page is skipped and said, in the singular.
    from pypdf import apply_configuration

    from adle_core.ingestion import parsers

    ticks = iter(range(100))
    monkeypatch.setattr(parsers, "monotonic", lambda: float(next(ticks)))
    monkeypatch.setattr(parsers, "_LARGE_PAGES_SECONDS", 2.0)
    with apply_configuration(stream_parsing_work_maximum_count=50):
        document = extract_in_process(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    assert document.warnings == ("1 page (page 3) could not be read and was skipped.",)
    assert 3 not in {section.page_number for section in document.sections}


def test_a_pdf_no_page_of_which_can_be_read_is_not_called_a_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdf import apply_configuration

    from adle_core.ingestion import parsers

    monkeypatch.setattr(parsers, "_LARGE_PAGES_SECONDS", 0.0)
    with (
        apply_configuration(stream_parsing_work_maximum_count=50),
        pytest.raises(IngestionError) as raised,
    ):
        extract_in_process(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    assert raised.value.code == "malformed_document"
    assert "could not read any page" in raised.value.message


# -- rejections ------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "code", "hint"),
    [
        ("lecture-notes-encrypted.pdf", "encrypted_document", "password-protected"),
        ("scanned-handout.pdf", "scanned_document", "never uploads"),
        ("damaged.pdf", "malformed_document", "damaged"),
        ("not-really-a.pdf", "unsupported_type", "not a PDF"),
        ("binary-named.txt", "unsupported_type", "readable text"),
        ("empty.txt", "empty_document", "empty"),
    ],
)
def test_unusable_files_are_rejected_with_an_actionable_message(
    name: str, code: str, hint: str
) -> None:
    with pytest.raises(IngestionError) as raised:
        extract_in_process(DOCUMENTS / name, name)
    assert raised.value.code == code
    assert hint in raised.value.message
    # The message is for a learner: no paths, tracebacks, or library names.
    assert "Traceback" not in raised.value.message
    assert str(DOCUMENTS) not in raised.value.message


@pytest.mark.parametrize(
    ("name", "hint"),
    [
        ("slides.pptx", "export the slides as a PDF"),
        ("old.doc", "save it as .docx"),
        ("photo.JPG", "OCR"),
        ("archive.zip", "'.zip' files are not supported"),
        ("README", "without an extension"),
    ],
)
def test_unsupported_extensions_explain_what_to_do_instead(
    tmp_path: Path, name: str, hint: str
) -> None:
    file = tmp_path / name
    file.write_bytes(b"irrelevant")
    with pytest.raises(IngestionError) as raised:
        detect_kind(file, name, DEFAULT_LIMITS)
    assert raised.value.code == "unsupported_type"
    assert hint in raised.value.message
    assert "PDF, Word (.docx), Markdown (.md), and plain text (.txt)" in raised.value.message


def test_a_zip_that_is_not_a_word_document_is_rejected(tmp_path: Path) -> None:
    import zipfile

    file = tmp_path / "fake.docx"
    with zipfile.ZipFile(file, "w") as archive:
        archive.writestr("payload.txt", "not a document")
    with pytest.raises(IngestionError) as raised:
        detect_kind(file, file.name, DEFAULT_LIMITS)
    assert raised.value.code == "unsupported_type"


def test_missing_file_is_reported_not_raised_as_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(IngestionError) as raised:
        detect_kind(tmp_path / "gone.txt", "gone.txt", DEFAULT_LIMITS)
    assert raised.value.code == "file_unreadable"


@pytest.mark.parametrize(
    ("name", "limits", "code"),
    [
        ("lecture-notes.pdf", {"max_file_bytes": 1000}, "file_too_large"),
        ("study-notes.txt", {"max_text_file_bytes": 100}, "file_too_large"),
        ("lecture-notes.pdf", {"max_pages": 2}, "file_too_large"),
        ("neural-networks-syllabus.md", {"max_characters": 500}, "file_too_large"),
    ],
)
def test_limits_are_enforced(name: str, limits: dict[str, int], code: str) -> None:
    with pytest.raises(IngestionError) as raised:
        extract(name, **limits)
    assert raised.value.code == code


def test_worker_reports_parser_failures_without_quoting_the_document() -> None:
    damaged = request_for(DOCUMENTS / "damaged.pdf", DocumentKind.PDF, DEFAULT_LIMITS)
    assert worker.handle(damaged) == {
        "ok": False,
        "code": "malformed_document",
        "message": "The PDF is damaged and could not be read.",
    }

    missing = request_for(DOCUMENTS / "does-not-exist.txt", DocumentKind.TEXT, DEFAULT_LIMITS)
    response = worker.handle(missing)
    assert (response["ok"], response["code"]) == (False, "malformed_document")
    assert "does-not-exist" not in response["message"]

    for garbage in (None, [], {}, {"path": 1, "kind": "pdf", "limits": {}}, {"kind": "exe"}):
        assert worker.handle(garbage)["code"] == "malformed_document"


def test_a_document_survives_the_trip_through_the_worker_protocol() -> None:
    original = extract_in_process(DOCUMENTS / "neural-networks-syllabus.md", "syllabus.md")
    response = worker.handle(
        request_for(
            DOCUMENTS / "neural-networks-syllabus.md", DocumentKind.MARKDOWN, DEFAULT_LIMITS
        )
    )
    assert response["ok"] is True
    # The reply is plain JSON: nothing in it can execute when it is read back.
    restored = document_from_json(json.loads(json.dumps(response["document"])), DEFAULT_LIMITS)
    assert restored == original


@pytest.mark.parametrize(
    "reply",
    [
        None,
        [],
        {"sections": "not a list"},
        {"sections": [{"kind": "page"}]},
        {"sections": [{"kind": "page", "text": 5}]},
        {
            "sections": [{"kind": "spreadsheet", "text": "x"}],
            "kind": "pdf",
            "parser": "p",
            "parser_version": "1",
        },
        {"sections": [{"kind": "page", "text": "x", "page_number": "one"}]},
        {"sections": [{"kind": "page", "text": "x", "confidence": "high"}]},
        {"sections": [], "kind": "executable", "parser": "p", "parser_version": "1"},
        {"sections": [], "kind": "pdf", "parser": "p", "parser_version": "1", "warnings": [1]},
        {"sections": [], "kind": "pdf", "parser": 7, "parser_version": "1"},
    ],
)
def test_a_malformed_worker_reply_is_refused(reply: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        document_from_json(reply, DEFAULT_LIMITS)


def test_a_worker_reply_cannot_exceed_the_text_limit_or_push_values_out_of_range() -> None:
    oversized = {
        "kind": "text",
        "parser": "text",
        "parser_version": "1",
        "sections": [
            {"kind": "document", "text": "x" * 600},
            {"kind": "document", "text": "y" * 600},
        ],
    }
    with pytest.raises(IngestionError) as raised:
        document_from_json(oversized, replace(DEFAULT_LIMITS, max_characters=1000))
    assert raised.value.code == "file_too_large"

    odd = {
        "kind": "pdf",
        "parser": "p" * 100,
        "parser_version": "1",
        "warnings": ["w" * 2000] * 50,
        "sections": [{"kind": "page", "text": "x", "confidence": 9.5, "title": "t" * 1000}],
    }
    document = document_from_json(odd, DEFAULT_LIMITS)
    assert document.sections[0].confidence == 1.0
    assert len(document.sections[0].title or "") == 300
    assert len(document.parser) == 40
    assert len(document.warnings) == 20
    assert len(document.warnings[0]) == 500


# -- text cleaning ---------------------------------------------------------


def test_clean_text_normalises_without_losing_words() -> None:
    raw = f"Line one\r\nLine  two\t\ttabbed \x00\x07\n\n\n\n  Line three  {ZERO_WIDTH_SPACE}"
    assert clean_text(raw) == "Line one\nLine two tabbed\n\nLine three"


def test_clean_text_removes_private_use_characters() -> None:
    # Search highlighting relies on these never appearing in stored text.
    assert clean_text(f"a{PRIVATE_OPEN}b{PRIVATE_CLOSE}c") == "abc"


def test_clean_text_composes_accents() -> None:
    assert clean_text(f"cafe{COMBINING_ACUTE}") == "café"


def test_reflow_joins_wrapped_lines_but_keeps_short_ones() -> None:
    printed = [
        "A short heading",
        "This line runs all the way to the right-hand margin of the page and",
        "continues here, ending the paragraph.",
        "- a list item",
        "- another item",
    ]
    assert reflow_wrapped_lines("\n".join(printed)).splitlines() == [
        "A short heading",
        "This line runs all the way to the right-hand margin of the page and "
        "continues here, ending the paragraph.",
        "- a list item",
        "- another item",
    ]
    assert reflow_wrapped_lines("") == ""
    assert reflow_wrapped_lines("one line") == "one line"


# -- chunking --------------------------------------------------------------


def test_short_sections_become_one_chunk_each() -> None:
    sections = (
        ExtractedSection(SectionKind.PAGE, "Page one text.", page_number=1),
        ExtractedSection(SectionKind.PAGE, "Page two text.", page_number=2),
    )
    chunks = chunk_document(sections)
    assert [(chunk.section_index, chunk.text) for chunk in chunks] == [
        (0, "Page one text."),
        (1, "Page two text."),
    ]


def test_long_text_breaks_at_paragraphs_then_sentences() -> None:
    paragraph = "This is a sentence about gradients. " * 20  # ~720 characters
    text = "\n\n".join([paragraph.strip()] * 5)
    chunks = chunk_section(0, text)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= MAX_CHARACTERS for chunk in chunks)
    # Paragraph-sized pieces are kept whole: every chunk ends at a sentence end.
    assert all(chunk.text.endswith(".") for chunk in chunks)


def test_a_single_enormous_unbroken_run_is_still_bounded() -> None:
    chunks = chunk_section(0, "x" * (MAX_CHARACTERS * 3 + 17))
    assert all(len(chunk.text) <= MAX_CHARACTERS for chunk in chunks)
    assert sum(len(chunk.text) for chunk in chunks) == MAX_CHARACTERS * 3 + 17


def test_chunk_hash_identifies_content() -> None:
    first, second = chunk_section(0, "Same text."), chunk_section(3, "Same text.")
    assert first[0].content_hash == second[0].content_hash
    assert first[0].content_hash != chunk_section(0, "Other text.")[0].content_hash


_paragraphs = st.lists(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=" .!?,"
        ),
        min_size=1,
        max_size=3000,
    ),
    min_size=1,
    max_size=8,
)


@settings(max_examples=120, deadline=None)
@given(_paragraphs)
def test_chunks_are_ordered_bounded_and_lossless(paragraphs: list[str]) -> None:
    text = clean_text("\n\n".join(paragraphs))
    chunks = chunk_section(0, text)

    previous_end = 0
    for chunk in chunks:
        # Each chunk is exactly a slice of the section, in order, without overlap.
        assert chunk.char_start >= previous_end
        assert chunk.char_end <= len(text)
        assert text[chunk.char_start : chunk.char_end].strip() == chunk.text
        assert len(chunk.text) <= MAX_CHARACTERS
        previous_end = chunk.char_end

    # Nothing but whitespace is ever dropped between or around chunks.
    kept = "".join(chunk.text for chunk in chunks)
    assert "".join(kept.split()) == "".join(text.split())
    # Chunking does not fragment needlessly.
    if len(text) <= TARGET_CHARACTERS and text:
        assert len(chunks) == 1


def test_what_a_worker_says_about_a_file_is_shown_only_if_a_parser_could_have_said_it() -> None:
    """The worker read a file from elsewhere; its words are shown to the learner."""
    from adle_core.ingestion.extract import _refusal
    from adle_core.ingestion.worker import CRASH_MESSAGE

    # A reason a parser has, said in a sentence: passed on as it is.
    plain = _refusal("scanned_document", "2 of 3 pages had no selectable text.")
    assert (plain.code, plain.message) == (
        "scanned_document",
        "2 of 3 pages had no selectable text.",
    )

    # A reason no parser has is a worker that broke, whatever it says.
    for code in ("please_call", "", "MALFORMED_DOCUMENT", "provider_notice", "x" * 500):
        made_up = _refusal(code, "Your licence has expired. Call 555 0100 to renew it.")
        assert (made_up.code, made_up.message) == ("malformed_document", CRASH_MESSAGE)

    # A sentence is one plain line of limited length, with nothing hidden in it.
    hostile = (
        "Line one\n\n\tline two " + chr(0x202E) + "desrever" + chr(0x202C) + chr(0) + "!" * 5000
    )
    shown = _refusal("malformed_document", hostile)
    assert shown.code == "malformed_document"
    assert shown.message.startswith("Line one line two desrever")
    assert len(shown.message) == 600
    assert "\n" not in shown.message
    assert chr(0x202E) not in shown.message

    # No sentence at all is no reason at all.
    assert _refusal("encrypted_document", " \n\t ").message == CRASH_MESSAGE
