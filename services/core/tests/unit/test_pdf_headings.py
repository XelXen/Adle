"""A PDF is read by its headings, so that what it covers can be read off them.

Its own outline first (the bookmarks a word processor or LaTeX writes), else the lines
numbered as headings, else its pages. A heading begins at its own line, never at the line of
the table of contents that names it, and a heading that runs over several pages gives a
section for each, so that a passage still says which page it is on.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.curriculum.outline import HeadingSection, draft_outline
from adle_core.ingestion.parsers import parse_pdf, reflow_wrapped_lines
from adle_core.ingestion.types import ExtractedDocument, Limits, SectionKind, heading_leaf
from tests.support.model import CURRICULUM, FakeProvider

REPOSITORY = Path(__file__).resolve().parents[4]
DOCUMENTS = REPOSITORY / "fixtures" / "sample-documents"
KEY = "sk-test-0123456789abcdefghijklmnop"


def headed(document: ExtractedDocument) -> list[tuple[str, int | None]]:
    """Each heading's own name, and the page each piece of it is on."""
    return [
        (heading_leaf(section.title or ""), section.page_number)
        for section in document.sections
        if section.kind == SectionKind.HEADING
    ]


def candidates(document: ExtractedDocument) -> list[str]:
    sections = [
        HeadingSection(
            section_id=f"sec_{index:020d}",
            source_id="src_00000000000000000001",
            source_name="notes.pdf",
            # As the course has them: each by its own name, not the path above it.
            title=heading_leaf(section.title or ""),
            level=section.level or 1,
            ordinal=index,
        )
        for index, section in enumerate(document.sections)
        if section.kind == SectionKind.HEADING
    ]
    return [candidate.title for candidate in draft_outline(sections)]


def test_a_pdf_with_an_outline_is_cut_where_each_of_its_headings_begins() -> None:
    document = parse_pdf(DOCUMENTS / "chapter-with-outline.pdf", Limits())
    assert headed(document) == [
        ("Chapter 3: Rates of Change", 1),
        ("3.1 Overview", 1),
        ("3.2 Average Rate of Change", 2),
        ("3.3 The Derivative as a Limit", 2),
        ("3.3 The Derivative as a Limit", 3),
        ("3.4 Rules for Derivatives", 3),
        ("3.5 Summary", 4),
    ]
    by_name = {heading_leaf(section.title or ""): section for section in document.sections}
    # Each begins at its own line: the contents list names them all, and starts none.
    assert by_name["3.1 Overview"].text.startswith("3.1 Overview\nA rate of change")
    assert by_name["3.4 Rules for Derivatives"].text.startswith("3.4 Rules for Derivatives")
    assert "3.2 Average Rate of Change . . ." in by_name["Chapter 3: Rates of Change"].text
    # A section is under its chapter.
    assert by_name["3.2 Average Rate of Change"].title == (
        "Chapter 3: Rates of Change › 3.2 Average Rate of Change"
    )
    assert by_name["3.2 Average Rate of Change"].level == 2
    # "Overview" and "Summary" organise a document; they are not concepts to teach.
    assert candidates(document) == [
        "Average Rate of Change",
        "The Derivative as a Limit",
        "Rules for Derivatives",
    ]


def test_without_an_outline_the_lines_numbered_as_headings_are_its_headings() -> None:
    document = parse_pdf(DOCUMENTS / "chapter-numbered.pdf", Limits())
    assert headed(document) == [
        ("Overview", 1),
        ("Average Rate of Change", 2),
        ("The Derivative as a Limit", 2),
        ("The Derivative as a Limit", 3),
        ("Rules for Derivatives", 3),
        ("Summary", 4),
    ]
    # What comes before the first heading is the first page's, as before.
    first = document.sections[0]
    assert (first.kind, first.page_number) == (SectionKind.PAGE, 1)
    assert first.text.startswith("Chapter 3: Rates of Change")


def test_a_pdf_without_headings_is_read_by_its_pages_as_before() -> None:
    document = parse_pdf(DOCUMENTS / "lecture-notes.pdf", Limits())
    assert [(section.kind, section.page_number) for section in document.sections] == [
        (SectionKind.PAGE, 1),
        (SectionKind.PAGE, 2),
        (SectionKind.PAGE, 3),
    ]


def test_a_contents_line_is_not_a_wrapped_line_and_a_heading_starts_a_line() -> None:
    page = "\n".join(
        [
            "5.1 Overview . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1",
            "5.2 The Cumulative Distribution Function . . . . . . . . . . . . . . . . . . . . 1",
            "5.1 Overview",
            "The random variables of Chapter 4 take values in a countable set, so their dis-",
            "tributions are described by a probability mass function and sums.",
        ]
    )
    assert reflow_wrapped_lines(page).splitlines() == [
        "5.1 Overview . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1",
        "5.2 The Cumulative Distribution Function . . . . . . . . . . . . . . . . . . . . 1",
        "5.1 Overview",
        "The random variables of Chapter 4 take values in a countable set, so their dis- "
        "tributions are described by a probability mass function and sums.",
    ]


def test_a_numbered_line_is_a_heading_only_when_it_reads_like_one() -> None:
    from adle_core.ingestion.parsers import _is_numbered_heading, _numbered_headings

    assert _is_numbered_heading("5.2 The Cumulative Distribution Function")
    assert _is_numbered_heading("3 Results")
    assert not _is_numbered_heading("2 times the mean is the answer.")
    assert not _is_numbered_heading("1 The first item ends here.")
    assert not _is_numbered_heading("5.1 Overview . . . . . . . . . 1")
    assert not _is_numbered_heading("12 + 7 = 19")
    # Fewer than three, or out of order, is not an outline to trust.
    two = [(1, "1 Introduction\n2 Methods", 1.0)]
    assert _numbered_headings(two) == []
    three = [(1, "1 Introduction\nText.\n2 Methods\nText.\n1 Aside\n3 Results", 1.0)]
    assert [title for _, _, title in _numbered_headings(three)] == [
        "Introduction",
        "Methods",
        "Results",
    ]


# -- what a course plan is shown ----------------------------------------------------------


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def proposed_from(
    client: TestClient, services: Services, provider: FakeProvider, *names: str
) -> str:
    """The prompt a course plan is asked for with, for a course made from these files."""
    course = client.post("/v1/courses", json={"title": "Calculus", "origin": "materials"}).json()
    imported = services.sources.start_import(course["id"], [DOCUMENTS / name for name in names])
    services.jobs.wait(imported.id, timeout=60)
    provider.queue(copy.deepcopy(CURRICULUM))
    started = client.post(f"/v1/courses/{course['id']}/curriculum/proposal").json()
    services.jobs.wait(started["id"], timeout=60)
    return provider.prompt()


def test_a_course_plan_is_shown_every_heading_of_a_pdf(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    prompt = proposed_from(keyed, services, provider, "chapter-with-outline.pdf")
    for heading in (
        "Average Rate of Change",
        "The Derivative as a Limit",
        "Rules for Derivatives",
    ):
        assert heading in prompt
    assert "has not imported materials" not in prompt


def test_materials_without_headings_are_shown_page_by_page_and_never_as_none(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    prompt = proposed_from(keyed, services, provider, "lecture-notes.pdf")
    assert "has not imported materials" not in prompt
    assert "have no headings" in prompt
    for page in (1, 2, 3):
        assert f"page {page} of lecture-notes.pdf: " in prompt
    # The words of the pages are quoted, as everything from a learner's document is.
    assert '<learner_material kind="pages">' in prompt


# -- the owner's own document, where it is ---------------------------------------------------

OWNERS = REPOSITORY / "testchap.pdf"


@pytest.mark.skipif(not OWNERS.is_file(), reason="The owner's testchap.pdf is not here.")
def test_the_owners_chapter_is_read_section_by_section() -> None:
    """A chapter of lecture notes on continuous random variables (26 pages, an outline of
    ten sections). It is the owner's and is not in the repository: this runs where the file
    is."""
    document = parse_pdf(OWNERS, Limits())
    pages: dict[str, list[int]] = {}
    for name, page in headed(document):
        assert page is not None
        pages.setdefault(name, []).append(page)
    assert {name: (found[0], found[-1]) for name, found in pages.items()} == {
        "Overview": (1, 1),
        "The Cumulative Distribution Function": (2, 4),
        "Probability Density Functions": (4, 8),
        "Expected Value and Variance": (9, 11),
        "Functions of a Random Variable": (11, 12),
        "The Exponential Distribution": (13, 16),
        "The Normal Distribution": (16, 19),
        "The Gamma Distribution": (20, 23),
        "The Beta Distribution": (23, 25),
        "Summary of Key Formulas": (25, 26),
    }
    assert len(candidates(document)) == 9


@pytest.mark.skipif(not OWNERS.is_file(), reason="The owner's testchap.pdf is not here.")
def test_a_course_plan_for_the_owners_chapter_is_shown_all_of_it(
    keyed: TestClient, services: Services, provider: FakeProvider, tmp_path: Path
) -> None:
    course = keyed.post(
        "/v1/courses", json={"title": "Lecture notes", "origin": "materials"}
    ).json()
    imported = services.sources.start_import(course["id"], [OWNERS])
    services.jobs.wait(imported.id, timeout=120)
    provider.queue(copy.deepcopy(CURRICULUM))
    started = keyed.post(f"/v1/courses/{course['id']}/curriculum/proposal").json()
    services.jobs.wait(started["id"], timeout=60)
    prompt = provider.prompt()
    shown: dict[str, Any] = {
        heading: heading in prompt
        for heading in (
            "The Cumulative Distribution Function",
            "Probability Density Functions",
            "Expected Value and Variance",
            "Functions of a Random Variable",
            "The Exponential Distribution",
            "The Normal Distribution",
            "The Gamma Distribution",
            "The Beta Distribution",
        )
    }
    assert all(shown.values()), shown
