"""The latest sitting on a course and what it showed, through the service and the API.

The rules are in ``learner_model/sitting.py`` and tested in ``test_sitting.py``. Here:
that the right things are gathered from the record, that the words match the ones the
rest of the overview uses, and that nothing like a score is sent to the interface.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.infrastructure.database import utc_now
from adle_core.learner_model.sitting import SITTING_GAP
from tests.unit.test_learning_api import (
    CONCEPT_TITLE,
    answer_at,
    keys_in,
    overview,
    progress_of,
    strings_in,
)


@pytest.fixture
def course(client: TestClient) -> dict[str, Any]:
    created: dict[str, Any] = client.post("/v1/courses/sample").json()
    return created


@pytest.fixture
def lesson(client: TestClient, course: dict[str, Any]) -> dict[str, Any]:
    summary = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]
    loaded: dict[str, Any] = client.get(f"/v1/lessons/{summary['id']}").json()["lesson"]
    return loaded


@pytest.fixture
def now() -> datetime:
    """The real clock: finishing a lesson is stamped with it, so the answers are too."""
    return utc_now()


def finish(client: TestClient, lesson: dict[str, Any]) -> None:
    last = len(lesson["segments"]) - 1
    response = client.put(
        f"/v1/lessons/{lesson['lesson_id']}/progress", json={"position": last, "completed": True}
    )
    assert response.status_code == 200, response.text


def session_at(services: Services, course: dict[str, Any], when: datetime) -> Any:
    return services.learning.overview(course["id"], now=when).session


def test_before_anything_is_done_there_is_no_session(
    client: TestClient, course: dict[str, Any]
) -> None:
    assert overview(client, course)["session"] is None


def test_a_session_says_what_was_shown_and_what_is_still_missing(
    client: TestClient,
    services: Services,
    course: dict[str, Any],
    lesson: dict[str, Any],
    now: datetime,
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer_at(services, lesson, "q_influence", now - timedelta(minutes=12))
    answer_at(services, lesson, "q_compute", now - timedelta(minutes=9), number=99)
    answer_at(services, lesson, "q_baseline", now - timedelta(minutes=6))
    finish(client, lesson)

    view = overview(client, course)
    session = view["session"]
    knowledge = progress_of(view, concept_id)["knowledge"]

    assert session["current"] is True
    assert session["answered"] == 3
    assert session["lessons_completed"] == 1
    assert session["started_at"] < session["ended_at"]
    # Two of the three answers were right without help. A count, and the wrong one is
    # simply not in it.
    assert session["shown"] == [
        {
            "concept_id": concept_id,
            "title": CONCEPT_TITLE,
            "right": 2,
            "right_unaided": 2,
            "demonstrated": False,
        }
    ]
    # What is still needed is said in the very words the concept's own row uses.
    assert knowledge["state"] != "demonstrated"
    assert knowledge["missing"]
    assert session["still_needed"] == [
        {
            "concept_id": concept_id,
            "title": CONCEPT_TITLE,
            "label": knowledge["label"],
            "missing": knowledge["missing"],
        }
    ]
    # Nothing is planned for review while the concept is still being learned.
    assert knowledge["review_due_at"] is None
    assert session["reviews"] == []


def test_a_session_in_which_a_concept_was_demonstrated_says_when_it_comes_back(
    client: TestClient,
    services: Services,
    course: dict[str, Any],
    lesson: dict[str, Any],
    now: datetime,
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer_at(services, lesson, "q_compute", now - timedelta(minutes=12), number=99)
    answer_at(services, lesson, "q_influence", now - timedelta(minutes=9))
    answer_at(services, lesson, "q_baseline", now - timedelta(minutes=6))
    answer_at(services, lesson, "q_zero_weight", now - timedelta(minutes=3))

    view = overview(client, course)
    session = view["session"]
    knowledge = progress_of(view, concept_id)["knowledge"]

    # The usual criteria decide this, from everything recorded, not this summary.
    assert knowledge["state"] == "demonstrated"
    assert session["shown"] == [
        {
            "concept_id": concept_id,
            "title": CONCEPT_TITLE,
            "right": 3,
            "right_unaided": 3,
            "demonstrated": True,
        }
    ]
    assert session["still_needed"] == []
    # The review these answers scheduled is the one the concept's own row shows.
    assert knowledge["review_due_at"] is not None
    assert session["reviews"] == [
        {"concept_id": concept_id, "title": CONCEPT_TITLE, "due_at": knowledge["review_due_at"]}
    ]


def test_only_answers_that_counted_as_unaided_evidence_are_counted_as_shown(
    services: Services, course: dict[str, Any], lesson: dict[str, Any], now: datetime
) -> None:
    answer_at(services, lesson, "q_influence", now - timedelta(minutes=10))
    # The same question again a minute later: the explanation is still in mind.
    answer_at(services, lesson, "q_influence", now - timedelta(minutes=9))
    answer_at(services, lesson, "q_compute", now - timedelta(minutes=8), hinted=True)
    answer_at(services, lesson, "q_baseline", now - timedelta(minutes=7), unsure=True)

    session = session_at(services, course, now)

    assert session.answered == 4
    # All four were right; only the first counts in full. The rest are lighter evidence.
    assert [(line.right, line.right_unaided) for line in session.shown] == [(4, 1)]


def test_skipped_questions_are_activity_but_not_answers(
    client: TestClient,
    services: Services,
    course: dict[str, Any],
    lesson: dict[str, Any],
    now: datetime,
) -> None:
    for question in ("q_influence", "q_compute"):
        skipped = client.post(
            f"/v1/lessons/{lesson['lesson_id']}/questions/{question}/answer",
            json={"skipped": True},
        )
        assert skipped.status_code == 200, skipped.text

    session = session_at(services, course, now + timedelta(minutes=1))

    assert session is not None
    assert session.answered == 0
    assert session.shown == []
    # Nothing was shown either way, and what is needed is simply answers.
    assert [line.label for line in session.still_needed] == ["Not assessed"]


def test_coming_back_later_it_is_last_time_with_the_same_account(
    services: Services, course: dict[str, Any], lesson: dict[str, Any], now: datetime
) -> None:
    answer_at(services, lesson, "q_influence", now - timedelta(minutes=10))
    answer_at(services, lesson, "q_compute", now - timedelta(minutes=5))

    during = session_at(services, course, now)
    just_after = session_at(services, course, now - timedelta(minutes=5) + SITTING_GAP)
    two_days_on = session_at(services, course, now + timedelta(days=2))

    assert during.current
    assert just_after.current
    assert not two_days_on.current
    assert two_days_on.ended_at == during.ended_at
    assert two_days_on.shown == during.shown
    assert two_days_on.answered == 2


def test_a_new_sitting_takes_the_place_of_the_old_one(
    services: Services, course: dict[str, Any], lesson: dict[str, Any], now: datetime
) -> None:
    answer_at(services, lesson, "q_influence", now - timedelta(days=3, minutes=10))
    answer_at(services, lesson, "q_compute", now - timedelta(days=3, minutes=5))
    answer_at(services, lesson, "q_baseline", now - timedelta(days=3))

    answer_at(services, lesson, "q_zero_weight", now - timedelta(minutes=2))
    session = session_at(services, course, now)

    assert session.current
    assert session.started_at == now - timedelta(minutes=2)
    # Only today's answer is in it, though the concept's state rests on all four.
    assert session.answered == 1
    assert [(line.right, line.right_unaided) for line in session.shown] == [(1, 1)]


def test_a_session_carries_no_score(
    client: TestClient,
    services: Services,
    course: dict[str, Any],
    lesson: dict[str, Any],
    now: datetime,
) -> None:
    for minutes, question in enumerate(("q_influence", "q_compute", "q_baseline"), start=1):
        answer_at(services, lesson, question, now - timedelta(minutes=10 - minutes))

    session = overview(client, course)["session"]

    assert set(session) == {
        "started_at",
        "ended_at",
        "current",
        "lessons_completed",
        "answered",
        "shown",
        "still_needed",
        "reviews",
    }
    assert not {"probability", "score", "mastery", "percent", "rate"} & keys_in(session)
    assert not any("%" in text for text in strings_in(session))
    # Every number in it is a whole count of things that happened.
    numbers = [
        session["answered"],
        session["lessons_completed"],
        *(line["right"] for line in session["shown"]),
        *(line["right_unaided"] for line in session["shown"]),
    ]
    assert all(isinstance(number, int) and number >= 0 for number in numbers)
