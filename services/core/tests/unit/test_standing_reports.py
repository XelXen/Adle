"""Which "this did not help" reports still count (ADR-054)."""

from __future__ import annotations

from datetime import UTC, datetime

from adle_core.application.evidence import (
    EVENT_DISMISSED,
    EVENT_UNHELPFUL,
    EVENT_UNHELPFUL_WITHDRAWN,
    standing_reports,
)
from adle_core.infrastructure.orm import LearnerEvent

#: Every row in the same moment: the order they were written in is what counts.
AT = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def event(row: int, kind: str, segment: str = "seg_a", lesson: str = "les_1") -> LearnerEvent:
    return LearnerEvent(
        id=row,
        course_id="crs_1",
        concept_id="con_1",
        lesson_id=lesson,
        occurred_at=AT,
        kind=kind,
        detail={"segment_id": segment},
    )


def rows(events: list[LearnerEvent]) -> list[int]:
    return [item.id for item in standing_reports(events)]


def test_a_report_stands_until_it_is_taken_back() -> None:
    assert rows([event(1, EVENT_UNHELPFUL)]) == [1]
    assert rows([event(1, EVENT_UNHELPFUL), event(2, EVENT_UNHELPFUL_WITHDRAWN)]) == []


def test_taking_back_withdraws_every_report_about_that_part_made_before() -> None:
    events = [
        event(1, EVENT_UNHELPFUL),
        event(2, EVENT_UNHELPFUL),
        event(3, EVENT_UNHELPFUL_WITHDRAWN),
    ]
    assert rows(events) == []


def test_a_report_made_after_it_was_taken_back_stands() -> None:
    events = [
        event(1, EVENT_UNHELPFUL),
        event(2, EVENT_UNHELPFUL_WITHDRAWN),
        event(3, EVENT_UNHELPFUL),
    ]
    assert rows(events) == [3]


def test_only_the_same_part_of_the_same_lesson_is_taken_back() -> None:
    events = [
        event(1, EVENT_UNHELPFUL, segment="seg_a"),
        event(2, EVENT_UNHELPFUL, segment="seg_b"),
        event(3, EVENT_UNHELPFUL, segment="seg_a", lesson="les_2"),
        event(4, EVENT_UNHELPFUL_WITHDRAWN, segment="seg_a"),
    ]
    assert rows(events) == [2, 3]


def test_the_order_written_counts_not_the_order_given() -> None:
    # A withdrawal written before the report does not take back what came after it.
    assert rows([event(2, EVENT_UNHELPFUL), event(1, EVENT_UNHELPFUL_WITHDRAWN)]) == [2]


def test_other_kinds_are_not_reports() -> None:
    assert rows([event(1, EVENT_DISMISSED), event(2, "lesson_completed")]) == []
