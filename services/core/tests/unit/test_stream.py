"""A lesson's answer read while it is written: what it says before its parts, then each part
as soon as its closing brace has come (ADR-048). Pure: no model, no clock."""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from adle_core.generation.drafts import extract_json_object, mend_backslashes
from adle_core.generation.stream import PartStream
from tests.support.model import LESSON

ANSWER = json.dumps(LESSON, indent=2)


def read(text: str, sizes: list[int]) -> tuple[str | None, list[str], PartStream]:
    """The header and the parts handed over when ``text`` arrives in pieces of ``sizes``."""
    stream = PartStream()
    header: str | None = None
    parts: list[str] = []
    at = 0
    for size in sizes:
        found = stream.add(text[at : at + size])
        header = header or found.header
        parts += found.parts
        at += size
    found = stream.add(text[at:])
    header = header or found.header
    parts += found.parts
    return header, parts, stream


def test_each_part_is_handed_over_whole_and_the_header_before_them() -> None:
    header, parts, stream = read(ANSWER, [])
    assert header is not None
    assert json.loads(header) == {
        "title": LESSON["title"],
        "strategy": LESSON["strategy"],
        "sources": LESSON["sources"],
    }
    assert [json.loads(part) for part in parts] == LESSON["segments"]
    assert stream.finished_parts
    assert stream.count == len(LESSON["segments"])


@given(st.lists(st.integers(min_value=1, max_value=400), max_size=60))
def test_however_the_answer_arrives_the_same_parts_come_out(sizes: list[int]) -> None:
    header, parts, _ = read(ANSWER, sizes)
    assert header is not None
    assert [json.loads(part) for part in parts] == LESSON["segments"]


def test_a_part_is_handed_over_only_once_its_closing_brace_has_come() -> None:
    stream = PartStream()
    first_end = ANSWER.index('"segments"')
    stream.add(ANSWER[:first_end])
    found = stream.add(ANSWER[first_end : first_end + 40])
    assert found.parts == []
    rest = stream.add(ANSWER[first_end + 40 :])
    assert len(rest.parts) == len(LESSON["segments"])


def test_text_inside_a_string_is_never_taken_for_its_structure() -> None:
    tricky = {
        "title": 'A "quoted" title with } and ] and { in it',
        "strategy": "visual",
        "sources": [],
        "segments": [
            {"type": "explanation", "title": "Braces", "beats": [{"say": "a } b ] c { d [ e"}]},
            {"type": "explanation", "title": 'Escapes \\" and \\\\', "beats": [{"say": "x"}]},
        ],
    }
    header, parts, _ = read(json.dumps(tricky), [3] * 200)
    assert json.loads(header or "{}")["title"] == tricky["title"]
    assert [json.loads(part) for part in parts] == tricky["segments"]


def test_tex_written_with_one_backslash_is_read_as_the_whole_answer_would_be() -> None:
    # As a real model wrote it: TeX inside strings, the JSON escape of its backslash missed.
    text = (
        'Here is the lesson:\n```json\n{"title": "Densities", "strategy": "visual", '
        '"sources": [1], "segments": [{"type": "explanation", "title": "Area", "beats": '
        '[{"say": "x", "show": "$\\frac{1}{2}$ and $\\int_0^1 f$"}]}], "practice": []}\n```'
    )
    _, parts, _ = read(text, [5] * 100)
    whole = extract_json_object(text)
    assert [json.loads(mend_backslashes(part)) for part in parts] == whole["segments"]


def test_parts_written_before_the_title_give_no_header() -> None:
    first = {"segments": LESSON["segments"], "title": "Later", "strategy": "visual"}
    header, parts, _ = read(json.dumps(first), [])
    assert header is None
    assert len(parts) == len(LESSON["segments"])


def test_an_answer_cut_off_hands_over_only_the_parts_that_were_whole() -> None:
    cut = ANSWER[: ANSWER.index('"type": "checkpoint"')]
    _, parts, stream = read(cut, [])
    assert [json.loads(part) for part in parts] == LESSON["segments"][:2]
    assert not stream.finished_parts


def test_another_answer_from_its_first_word_starts_afresh() -> None:
    stream = PartStream()
    stream.add(ANSWER[: len(ANSWER) // 2])
    stream.start_again()
    found = stream.add(ANSWER)
    assert len(found.parts) == len(LESSON["segments"])
    assert found.header is not None


def test_whatever_follows_the_answer_is_not_read() -> None:
    _, parts, _ = read(ANSWER + '\n{"segments": [{"type": "x"}]}', [])
    assert len(parts) == len(LESSON["segments"])
