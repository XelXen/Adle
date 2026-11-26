"""Answering a lesson's questions: scored by the core, kept, and recorded as evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from adle_core.application.services import Services
from adle_core.evaluation.scoring import Response
from adle_core.infrastructure.orm import Attempt, LearnerObservation


@pytest.fixture
def lesson(client: TestClient) -> dict[str, Any]:
    course = client.post("/v1/courses/sample").json()
    summary = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]
    return client.get(f"/v1/lessons/{summary['id']}").json()["lesson"]


def answer(client: TestClient, lesson: dict[str, Any], question: str, **body: Any) -> Any:
    return client.post(f"/v1/lessons/{lesson['lesson_id']}/questions/{question}/answer", json=body)


def state(client: TestClient, lesson: dict[str, Any]) -> dict[str, Any]:
    concept_id = lesson["concept_ids"][0]
    return client.get(f"/v1/concepts/{concept_id}/evidence").json()["knowledge"]


def test_a_right_answer_is_explained_and_recorded(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    response = answer(client, lesson, "q_influence", option_id="a")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["outcome"] == "correct"
    assert result["feedback"].startswith("Yes. Its weight is fifteen times larger")
    assert result["explanation"].startswith("Influence comes from the weight.")
    assert result["correct_answer"] == "The first input"
    assert result["correct_option"] == "a"
    assert result["attempt_number"] == 1
    assert result["change"].startswith("You answered a multiple-choice question correctly.")
    assert result["knowledge"]["state"] == "building"
    assert result["knowledge"]["answered"] == 1
    assert state(client, lesson) == result["knowledge"]


def test_a_wrong_answer_says_what_was_wrong_without_blame_and_notes_a_hypothesis(
    client: TestClient, lesson: dict[str, Any], services: Services
) -> None:
    result = answer(client, lesson, "q_influence", option_id="c").json()
    assert result["outcome"] == "incorrect"
    assert result["feedback"].startswith("The inputs are equal, but each is multiplied")
    assert result["correct_answer"] == "The first input"
    assert "wasn’t right" in result["change"]
    for word in ("wrong!", "fail", "mistake", "bad"):
        assert word not in (result["change"] + result["feedback"]).lower()
    with services.database.session() as session:
        attempt = session.scalars(select(Attempt)).one()
        assert (attempt.outcome, attempt.misconception) == ("incorrect", "causal_confusion")
        assert attempt.question_id == "q_influence"


def test_working_through_the_lesson_can_demonstrate_the_concept(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    states = [
        answer(client, lesson, "q_influence", option_id="a").json()["knowledge"]["state"],
        answer(client, lesson, "q_compute", number=3).json()["knowledge"]["state"],
    ]
    last = answer(client, lesson, "q_baseline", option_id="a").json()
    states.append(last["knowledge"]["state"])
    # Three unaided answers, two kinds of question, one of them a transfer question.
    assert states == ["building", "needs_evidence", "demonstrated"]
    assert last["knowledge"]["label"] == "Understood"
    assert last["knowledge"]["missing"] == []
    assert last["knowledge"]["review_due_at"] is not None
    assert "Now: Understood." in last["change"]

    curriculum = client.get(f"/v1/courses/{lesson['course_id']}/curriculum").json()
    shown = next(c for c in curriculum["concepts"] if c["id"] == lesson["concept_ids"][0])
    assert shown["knowledge"]["state"] == "demonstrated"


def test_numbers_are_scored_with_the_question_tolerance(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    assert answer(client, lesson, "q_compute", number=3.0004).json()["outcome"] == "correct"
    wrong = answer(client, lesson, "q_compute", number=5).json()
    assert (wrong["outcome"], wrong["correct_answer"]) == ("incorrect", "3")
    assert wrong["correct_option"] is None
    assert wrong["explanation"].endswith("gives $z = 3$.")


def test_a_hint_or_doubt_makes_a_right_answer_count_for_less(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    hinted = answer(client, lesson, "q_influence", option_id="a", hinted=True).json()
    assert "after a hint, which counts a little less" in hinted["change"]
    unsure = answer(client, lesson, "q_compute", number=3, unsure=True).json()
    assert "weren’t sure" in unsure["change"]
    # Two right answers, neither unaided: nothing counts towards the criteria yet.
    assert "3 more correct answers without a hint" in unsure["knowledge"]["missing"]


def test_answering_again_after_seeing_the_explanation_counts_as_aided(
    client: TestClient, lesson: dict[str, Any], services: Services
) -> None:
    first = answer(client, lesson, "q_influence", option_id="b").json()
    second = answer(client, lesson, "q_influence", option_id="a").json()
    assert (first["attempt_number"], second["attempt_number"]) == (1, 2)
    assert second["outcome"] == "correct"
    assert "just seen its explanation" in second["change"]
    assert "3 more correct answers without a hint" in second["knowledge"]["missing"]
    with services.database.session() as session:
        attempts = session.scalars(select(Attempt).order_by(Attempt.id)).all()
        assert [(item.outcome, item.hinted) for item in attempts] == [
            ("incorrect", False),
            ("correct", True),
        ]


def test_skipping_is_allowed_and_is_not_held_against_the_learner(
    client: TestClient, lesson: dict[str, Any], services: Services
) -> None:
    before = state(client, lesson)
    result = answer(client, lesson, "q_compute", skipped=True).json()
    assert result["outcome"] == "skipped"
    # Skipping does not hand over the answer.
    assert (result["correct_answer"], result["correct_option"]) == ("", None)
    assert result["feedback"] is None
    # The explanation is still offered: skipping should not cost the learner the answer.
    assert result["explanation"]
    assert result["change"].startswith("You skipped a question.")
    assert result["knowledge"]["state"] == before["state"] == "not_assessed"
    assert result["knowledge"]["answered"] == 0
    # A skip is not an attempt at the answer: the next answer is still a first try.
    assert answer(client, lesson, "q_compute", number=3).json()["attempt_number"] == 1
    with services.database.session() as session:
        outcomes = [row.outcome for row in session.scalars(select(LearnerObservation))]
        assert outcomes == ["skipped", "correct"]


@pytest.mark.parametrize(
    ("question", "body"),
    [
        ("q_influence", {"option_id": "z"}),
        ("q_influence", {}),
        ("q_influence", {"number": 3}),
        ("q_compute", {"text": "three"}),
        ("q_compute", {"option_id": "a"}),
        ("q_compute", {"number": "three"}),
        ("q_compute", {"number": 3, "certainty": 0.9}),
        ("q_compute", {"text": "x" * 500}),
    ],
)
def test_a_response_that_does_not_fit_is_refused_and_nothing_is_recorded(
    client: TestClient,
    lesson: dict[str, Any],
    services: Services,
    question: str,
    body: dict[str, Any],
) -> None:
    response = answer(client, lesson, question, **body)
    assert response.status_code == 422, response.text
    assert state(client, lesson)["answered"] == 0
    with services.database.session() as session:
        assert session.scalars(select(Attempt)).all() == []


def test_unknown_questions_and_lessons_are_not_found(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    assert answer(client, lesson, "q_not_there", option_id="a").status_code == 404
    other = {**lesson, "lesson_id": "les_00000000000000000000"}
    assert answer(client, other, "q_influence", option_id="a").status_code == 404


def test_no_answer_response_ever_contains_a_score(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    for body in ({"option_id": "a"}, {"option_id": "b"}, {"skipped": True}):
        text = answer(client, lesson, "q_influence", **body).text
        assert "probability" not in text
        assert "%" not in text


def test_a_skip_shows_the_explanation_so_the_answer_that_follows_is_an_aided_one(
    client: TestClient, lesson: dict[str, Any], services: Services
) -> None:
    """Skipping is free, but what it shows is help: the next answer is not a first unaided one."""
    skipped = answer(client, lesson, "q_compute", skipped=True).json()
    assert skipped["explanation"]
    after = answer(client, lesson, "q_compute", number=3).json()
    assert after["outcome"] == "correct"
    assert "You’d just seen its explanation, so it counts a little less." in after["change"]
    # After a real gap the same answer is recall, and counts in full.
    later = datetime.now(UTC) + timedelta(days=2)
    recalled = services.assessment.answer(
        lesson["lesson_id"], "q_compute", Response(number=3), now=later
    )
    assert "just seen its explanation" not in recalled.change


def test_a_slip_of_the_keys_is_said_and_answered_again_with_nothing_kept(
    client: TestClient, lesson: dict[str, Any], services: Services
) -> None:
    # "biaz" for "bias": almost, not wrong (ADR-078).
    near = answer(client, lesson, "q_only_the_bias", text="biaz")
    assert near.status_code == 200, near.text
    said = near.json()
    assert said["outcome"] == "near"
    assert said["feedback"] == "Check what you typed, and try again."
    # Nothing of the answer is shown, and nothing is kept: it is not evidence.
    assert (said["correct_answer"], said["explanation"], said["change"]) == ("", "", "")
    assert state(client, lesson)["answered"] == 0
    with services.database.session() as session:
        assert session.scalars(select(Attempt)).all() == []
    # Answered again, it counts as a first answer, in full.
    right = answer(client, lesson, "q_only_the_bias", text="bias").json()
    assert (right["outcome"], right["attempt_number"]) == ("correct", 1)
    assert state(client, lesson)["answered"] == 1


def test_a_second_slip_in_a_sitting_is_scored_as_it_is(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    assert answer(client, lesson, "q_only_the_bias", text="biaz").json()["outcome"] == "near"
    again = answer(client, lesson, "q_only_the_bias", text="bais").json()
    assert again["outcome"] == "incorrect"
    assert again["correct_answer"] == "bias"
    # An answer nothing like an accepted one is wrong at once.
    other = answer(client, lesson, "q_only_the_bias", text="the weight").json()
    assert other["outcome"] == "incorrect"
