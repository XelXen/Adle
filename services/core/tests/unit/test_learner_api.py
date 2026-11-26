"""The learner model through the API and the service: preferences and recorded evidence."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from adle_core.api.auth import LaunchToken
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.infrastructure.orm import LearnerConceptState, LearnerObservation
from adle_core.ingestion.extract import extract_in_process
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.mastery import MasteryState
from adle_core.learner_model.tracing import Observation, ObservationKind

START = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)


def concept_in_new_course(client: TestClient, title: str = "Loss") -> dict[str, Any]:
    course = client.post(
        "/v1/courses", json={"title": "Neural networks", "origin": "topic", "topic": "Learning"}
    ).json()
    response = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={"title": title, "objectives": ["Define it."]},
    )
    assert response.status_code == 201, response.text
    return response.json()["concepts"][-1]


def answer(
    outcome: Outcome = Outcome.CORRECT,
    form: str = "multiple_choice",
    *,
    minutes: int = 0,
    transfer: bool = False,
    hinted: bool = False,
) -> Observation:
    return Observation(
        kind=ObservationKind.ANSWER,
        occurred_at=START + timedelta(minutes=minutes),
        outcome=outcome,
        question_form=form,
        is_transfer=transfer,
        hinted=hinted,
    )


# -- preferences -----------------------------------------------------------


def test_preferences_start_with_sensible_defaults(client: TestClient) -> None:
    assert client.get("/v1/learner/preferences").json() == {
        "pace": "standard",
        "explanation_density": "balanced",
        "narration": True,
        "captions": True,
        "goal": "",
        "voice": "",
        "volume": 100,
        "character": "",
        "character_parts": {},
        "character_follows_voice": True,
    }


def test_preferences_can_be_changed_one_at_a_time_and_are_kept(
    client: TestClient, settings: Settings, services: Services
) -> None:
    changed = client.patch(
        "/v1/learner/preferences",
        json={"pace": "relaxed", "goal": "  Understand   backpropagation.  "},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json() == {
        "pace": "relaxed",
        "explanation_density": "balanced",
        "narration": True,
        "captions": True,
        "goal": "Understand backpropagation.",
        "voice": "",
        "volume": 100,
        "character": "",
        "character_parts": {},
        "character_follows_voice": True,
    }
    client.patch("/v1/learner/preferences", json={"narration": False})
    voiced = client.patch(
        "/v1/learner/preferences",
        json={"voice": " Microsoft Zira - English (United States) ", "volume": 35},
    ).json()
    assert (voiced["voice"], voiced["volume"]) == (
        "Microsoft Zira - English (United States)",
        35,
    )
    # Silence is a volume like any other, and choosing no voice is allowed again.
    quiet = client.patch("/v1/learner/preferences", json={"voice": "", "volume": 0}).json()
    assert (quiet["voice"], quiet["volume"]) == ("", 0)
    assert client.get("/v1/learner/preferences").json()["pace"] == "relaxed"

    # A new start of the service reads the same choices from disk.
    services.close()
    restarted = build_services(settings, LaunchToken("x" * 40), extract=extract_in_process)
    try:
        kept = restarted.learner.get_preferences()
        assert (kept.pace.value, kept.narration, kept.goal) == (
            "relaxed",
            False,
            "Understand backpropagation.",
        )
    finally:
        restarted.close()


@pytest.mark.parametrize(
    "body",
    [
        {"pace": "ludicrous"},
        {"narration": "sometimes"},
        {"explanation_density": 3},
        {"goal": "x" * 601},
        {"voice": "v" * 121},
        {"volume": 101},
        {"volume": -1},
        {"volume": "loud"},
        {"goal": "word " * 80},
        {"favourite_colour": "green"},
    ],
)
def test_preferences_that_make_no_sense_are_refused(
    client: TestClient, body: dict[str, Any]
) -> None:
    before = client.get("/v1/learner/preferences").json()
    response = client.patch("/v1/learner/preferences", json=body)
    assert response.status_code == 422
    assert client.get("/v1/learner/preferences").json() == before


# -- self-rating -----------------------------------------------------------


def test_saying_you_know_a_concept_is_recorded_as_a_claim_to_check(client: TestClient) -> None:
    concept = concept_in_new_course(client)
    before = client.get(f"/v1/concepts/{concept['id']}/evidence").json()
    assert before["history"] == []
    assert before["knowledge"]["state"] == "not_assessed"

    response = client.post(f"/v1/concepts/{concept['id']}/self-rating", json={"level": "confident"})
    assert response.status_code == 200, response.text
    evidence = response.json()
    assert evidence["knowledge"] == {
        "state": "needs_evidence",
        "label": "Nearly there",
        "missing": ["a few questions to confirm what you know"],
        "answered": 0,
        "self_report": "confident",
        "review_due_at": None,
    }
    (entry,) = evidence["history"]
    assert entry["kind"] == "self_report"
    assert (entry["state_before"], entry["state_after"]) == ("not_assessed", "needs_evidence")
    assert entry["explanation"].startswith("You said you already know this well.")

    # The curriculum shows the same state.
    shown = client.get(f"/v1/courses/{concept['course_id']}/curriculum").json()["concepts"][0]
    assert shown["knowledge"]["label"] == "Nearly there"


def test_a_later_self_rating_is_added_to_the_record_not_written_over_it(client: TestClient) -> None:
    concept = concept_in_new_course(client)
    client.post(f"/v1/concepts/{concept['id']}/self-rating", json={"level": "confident"})
    evidence = client.post(
        f"/v1/concepts/{concept['id']}/self-rating", json={"level": "new"}
    ).json()
    assert [entry["state_after"] for entry in evidence["history"]] == [
        "not_assessed",
        "needs_evidence",
    ]
    assert evidence["knowledge"]["self_report"] == "new"
    assert evidence["knowledge"]["state"] == "not_assessed"


def test_self_ratings_are_validated(client: TestClient) -> None:
    concept = concept_in_new_course(client)
    assert (
        client.post(
            f"/v1/concepts/{concept['id']}/self-rating", json={"level": "expert"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/concepts/con_00000000000000000000/self-rating", json={"level": "some"}
        ).status_code
        == 404
    )


def test_no_score_ever_reaches_the_interface(client: TestClient, services: Services) -> None:
    concept = concept_in_new_course(client)
    services.learner.record(concept["id"], answer(minutes=0))
    services.learner.record(concept["id"], answer(Outcome.INCORRECT, "numeric", minutes=1))
    client.post(f"/v1/concepts/{concept['id']}/self-rating", json={"level": "some"})

    for path in (
        f"/v1/concepts/{concept['id']}/evidence",
        f"/v1/courses/{concept['course_id']}/curriculum",
    ):
        text = client.get(path).text
        assert "probability" not in text
        assert "%" not in text


# -- answers and the record ------------------------------------------------


def test_evidence_moves_a_concept_through_the_states_with_reasons(
    client: TestClient, services: Services
) -> None:
    concept = concept_in_new_course(client)
    observations = [
        answer(form="multiple_choice", minutes=0),
        answer(form="numeric", minutes=1),
        answer(form="prediction", transfer=True, minutes=2),
    ]
    states = [services.learner.record(concept["id"], item).state_after for item in observations]
    assert states == [
        MasteryState.BUILDING,
        MasteryState.NEEDS_EVIDENCE,
        MasteryState.DEMONSTRATED,
    ]

    evidence = client.get(f"/v1/concepts/{concept['id']}/evidence").json()
    assert evidence["knowledge"]["state"] == "demonstrated"
    assert evidence["knowledge"]["label"] == "Understood"
    assert evidence["knowledge"]["missing"] == []
    assert evidence["knowledge"]["answered"] == 3
    assert evidence["knowledge"]["review_due_at"] is not None
    # Newest first, and each entry starts where the previous one ended.
    history = list(reversed(evidence["history"]))
    assert [entry["state_after"] for entry in history] == [
        "building",
        "needs_evidence",
        "demonstrated",
    ]
    for earlier, later in itertools.pairwise(history):
        assert later["state_before"] == earlier["state_after"]
    assert "Now: Understood." in history[-1]["explanation"]


def test_one_answer_never_marks_a_concept_as_demonstrated(
    client: TestClient, services: Services
) -> None:
    concept = concept_in_new_course(client)
    transition = services.learner.record(
        concept["id"],
        Observation(
            kind=ObservationKind.ANSWER,
            occurred_at=START,
            outcome=Outcome.CORRECT,
            question_form="numeric",
            is_transfer=True,
            item_guess=0.01,
        ),
    )
    assert transition.state_after is MasteryState.NEEDS_EVIDENCE
    knowledge = client.get(f"/v1/concepts/{concept['id']}/evidence").json()["knowledge"]
    assert knowledge["state"] == "needs_evidence"
    assert "2 more correct answers without a hint" in knowledge["missing"]


def test_the_stored_state_can_be_rebuilt_from_the_record(
    client: TestClient, services: Services
) -> None:
    concept = concept_in_new_course(client)
    sequence = [
        answer(form="multiple_choice", minutes=0),
        answer(Outcome.INCORRECT, "numeric", minutes=5),
        answer(form="numeric", hinted=True, minutes=9),
        answer(form="prediction", transfer=True, minutes=12),
        answer(Outcome.SKIPPED, minutes=14),
        answer(form="ordering", minutes=20),
    ]
    for item in sequence:
        services.learner.record(concept["id"], item)
    before = client.get(f"/v1/concepts/{concept['id']}/evidence").json()["knowledge"]

    def stored() -> dict[str, Any]:
        with services.database.session() as session:
            row = session.get(LearnerConceptState, concept["id"])
            assert row is not None
            return {
                column.name: getattr(row, column.name)
                for column in LearnerConceptState.__table__.columns
                if column.name != "updated_at"
            }

    original = stored()
    # Damage the derived state, then rebuild it from the observations alone.
    with services.database.session() as session:
        row = session.get(LearnerConceptState, concept["id"])
        assert row is not None
        row.probability = 0.999
        row.state = "demonstrated"
        row.unaided_correct = 99
        row.missing = []
    assert stored() != original

    services.learner.rebuild(concept["id"])
    assert stored() == original
    assert client.get(f"/v1/concepts/{concept['id']}/evidence").json()["knowledge"] == before


def test_rebuilding_a_concept_with_no_record_leaves_it_not_assessed(
    client: TestClient, services: Services
) -> None:
    concept = concept_in_new_course(client)
    services.learner.rebuild(concept["id"])
    knowledge = client.get(f"/v1/concepts/{concept['id']}/evidence").json()["knowledge"]
    assert knowledge["state"] == "not_assessed"


def test_removing_a_concept_removes_what_was_recorded_about_it(
    client: TestClient, services: Services
) -> None:
    concept = concept_in_new_course(client)
    services.learner.record(concept["id"], answer())
    assert client.delete(f"/v1/concepts/{concept['id']}").status_code == 200
    with services.database.session() as session:
        assert session.scalar(select(func.count(LearnerObservation.id))) == 0
        assert session.scalar(select(func.count(LearnerConceptState.concept_id))) == 0
