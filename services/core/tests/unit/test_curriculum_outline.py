"""Drafting concept candidates from the headings of imported materials."""

from __future__ import annotations

import pytest

from adle_core.curriculum.outline import (
    MAX_CANDIDATES,
    HeadingSection,
    clean_title,
    draft_outline,
)

EN_DASH = chr(0x2013)
EM_DASH = chr(0x2014)


def heading(
    title: str, level: int, ordinal: int, *, source: str = "src_1", name: str = "syllabus.md"
) -> HeadingSection:
    return HeadingSection(
        section_id=f"{source}-sec-{ordinal}",
        source_id=source,
        source_name=name,
        title=title,
        level=level,
        ordinal=ordinal,
    )


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("3. Loss functions", "Loss functions"),
        ("3.2 Mean squared error", "Mean squared error"),
        ("3.2.1) Worked example", "Worked example"),
        ("Week 4: Gradient descent", "Gradient descent"),
        ("Unit 2 - Activation functions", "Activation functions"),
        (f"Lecture 10 {EM_DASH} Backpropagation", "Backpropagation"),
        (f"Chapter 5 {EN_DASH} The chain rule", "The chain rule"),
        ("Part II: Calculus you need", "Calculus you need"),
        ("Module 3 Perceptrons", "Perceptrons"),
        ("  Weights   and\tbiases  ", "Weights and biases"),
        ("Forward propagation:", "Forward propagation"),
    ],
)
def test_numbering_is_removed_from_headings(raw: str, cleaned: str) -> None:
    assert clean_title(raw) == cleaned


@pytest.mark.parametrize(
    "title",
    [
        "Unit vectors",
        "Topic identification",
        "Section cuts and views",
        "Part of speech tagging",
        "3D graphics",
        "2.5D rendering",
        "1990s music",
        "Week 4",
        "Part II",
        "7.",
    ],
)
def test_headings_that_only_look_numbered_are_left_alone(title: str) -> None:
    assert clean_title(title) == title


def test_topics_are_the_headings_below_a_single_document_title() -> None:
    sections = [
        heading("Introduction to neural networks", 1, 0),
        heading("1. Perceptrons", 2, 1),
        heading("Weights and biases", 3, 2),
        heading("2. Activation functions", 2, 3),
        heading("3. Forward propagation", 2, 4),
    ]
    candidates = draft_outline(sections)
    assert [candidate.title for candidate in candidates] == [
        "Perceptrons",
        "Activation functions",
        "Forward propagation",
    ]
    assert candidates[0].section_id == "src_1-sec-1"
    assert candidates[0].source_name == "syllabus.md"


def test_several_top_level_headings_are_the_topics_themselves() -> None:
    sections = [
        heading("Loss", 1, 0),
        heading("Mean squared error", 2, 1),
        heading("Gradient descent", 1, 2),
    ]
    assert [candidate.title for candidate in draft_outline(sections)] == [
        "Loss",
        "Gradient descent",
    ]


def test_a_document_with_only_a_title_offers_that_title() -> None:
    assert [candidate.title for candidate in draft_outline([heading("Backpropagation", 1, 0)])] == [
        "Backpropagation"
    ]


def test_headings_that_only_organise_the_document_are_skipped() -> None:
    sections = [
        heading("Course information", 1, 0),
        heading("Schedule", 1, 1),
        heading("Week 1: Perceptrons", 1, 2),
        heading("Grading", 1, 3),
        heading("References", 1, 4),
        heading("x", 1, 5),
        heading("y" * 200, 1, 6),
    ]
    assert [candidate.title for candidate in draft_outline(sections)] == ["Perceptrons"]


def test_repeats_and_existing_concepts_are_not_offered_again() -> None:
    sections = [
        heading("Loss", 1, 0),
        heading("1. LOSS", 1, 1),
        heading("Chain rule", 1, 2),
        heading("Gradient descent", 1, 3),
    ]
    candidates = draft_outline(sections, existing_titles=["chain  rule"])
    assert [candidate.title for candidate in candidates] == ["Loss", "Gradient descent"]


def test_each_source_is_read_separately_and_in_its_own_order() -> None:
    sections = [
        heading("Notes on learning", 1, 0, source="src_b", name="notes.docx"),
        heading("Learning rate", 2, 2, source="src_b", name="notes.docx"),
        heading("Overfitting", 2, 1, source="src_b", name="notes.docx"),
        heading("Perceptrons", 1, 0, source="src_a", name="syllabus.md"),
        heading("Loss", 1, 1, source="src_a", name="syllabus.md"),
    ]
    candidates = draft_outline(sections)
    assert [(candidate.source_name, candidate.title) for candidate in candidates] == [
        ("notes.docx", "Overfitting"),
        ("notes.docx", "Learning rate"),
        ("syllabus.md", "Perceptrons"),
        ("syllabus.md", "Loss"),
    ]


def test_the_number_of_candidates_is_bounded() -> None:
    sections = [heading(f"Topic number {index:03d}", 1, index) for index in range(200)]
    assert len(draft_outline(sections)) == MAX_CANDIDATES
    assert len(draft_outline(sections, limit=5)) == 5


def test_no_headings_means_no_candidates() -> None:
    assert draft_outline([]) == []
