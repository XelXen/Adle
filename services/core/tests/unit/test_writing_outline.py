"""What can be said about an answer while it is still being written: its titles (ADR-038)."""

from __future__ import annotations

import json

from adle_core.application.generation import Outline
from tests.support.model import CURRICULUM, LESSON


def fed(outline: Outline, text: str, size: int) -> list[int]:
    """Feed ``text`` in pieces of ``size`` characters; how many parts were known after each
    piece that completed a title."""
    counts: list[int] = []
    for index in range(0, len(text), size):
        if outline.add(text[index : index + size]):
            counts.append(len(outline.parts))
    return counts


def test_a_lesson_is_named_first_and_its_parts_follow_one_by_one() -> None:
    outline = Outline(named=True)
    counts = fed(outline, json.dumps(LESSON, indent=2), 7)
    assert outline.title == LESSON["title"]
    assert outline.parts == [segment["title"] for segment in LESSON["segments"]]
    # Each title was said as it was completed: one more part at a time, never two at once.
    assert counts == list(range(len(LESSON["segments"]) + 1))


def test_whatever_the_size_of_the_pieces_the_titles_are_the_same() -> None:
    text = json.dumps(LESSON)
    expected = [segment["title"] for segment in LESSON["segments"]]
    for size in (1, 2, 3, 50, 4096, len(text)):
        outline = Outline(named=True)
        fed(outline, text, size)
        assert (outline.title, outline.parts) == (LESSON["title"], expected), size


def test_a_list_of_concepts_has_no_name_of_its_own() -> None:
    outline = Outline()
    fed(outline, json.dumps(CURRICULUM), 11)
    assert outline.title == ""
    assert outline.parts == [concept["title"] for concept in CURRICULUM["concepts"]]


def test_a_lesson_that_lists_its_parts_before_its_name_is_not_named_after_a_part() -> None:
    draft = {
        "segments": [{"type": "explanation", "title": "Why a slope", "beats": []}],
        "title": "Slopes",
    }
    outline = Outline(named=True)
    fed(outline, json.dumps(draft), 5)
    assert outline.title == ""
    assert outline.parts[0] == "Why a slope"


def test_only_keys_are_read_never_the_words_of_the_answer() -> None:
    # A sentence that quotes what looks like a title is escaped in JSON and is not one.
    draft = {
        "title": "Quotation",
        "segments": [
            {
                "type": "explanation",
                "title": 'A “quoted” "word" and a \\ backslash',
                "beats": [{"say": 'He wrote "title": "Not a part" on the board.'}],
            }
        ],
    }
    outline = Outline(named=True)
    fed(outline, json.dumps(draft), 3)
    assert outline.title == "Quotation"
    assert outline.parts == ['A “quoted” "word" and a \\ backslash']


def test_a_title_is_one_short_line() -> None:
    outline = Outline()
    outline.add(json.dumps({"concepts": [{"title": "  two\nlines\tand " + "x" * 300}]}))
    (title,) = outline.parts
    assert "\n" not in title
    assert "\t" not in title
    assert title.startswith("two lines and x")
    assert len(title) <= 120


def test_empty_titles_are_skipped_and_the_list_has_an_end() -> None:
    concepts = [{"title": ""}] + [{"title": f"Concept {n}"} for n in range(60)]
    outline = Outline()
    outline.add(json.dumps({"concepts": concepts}))
    assert outline.parts[0] == "Concept 0"
    assert len(outline.parts) == 40


def test_another_model_starts_from_its_first_word() -> None:
    outline = Outline(named=True)
    fed(outline, json.dumps(LESSON)[:400], 9)
    assert outline.title
    outline.start_again()
    assert (outline.title, outline.parts) == ("", [])
    fed(outline, json.dumps(LESSON), 9)
    assert outline.title == LESSON["title"]
    assert len(outline.parts) == len(LESSON["segments"])
