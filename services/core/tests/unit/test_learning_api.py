"""What to do next, progress, practice, and hypotheses about mistakes, through the core's API.

Time matters here (a repeat too soon, a review coming due), so some tests call
the services directly with a clock of their own; the HTTP layer has no way to
pass one, on purpose.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from adle_core.application.services import Services
from adle_core.evaluation.scoring import Response
from adle_core.infrastructure.orm import (
    Attempt,
    LearnerConceptState,
    LearnerEvent,
    LearnerObservation,
)
from adle_core.learner_model.next_step import PAUSE_NOTE

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
CONCEPT_TITLE = "Weights and bias"
#: The right answers to the first sample lesson's questions.
RIGHT: dict[str, dict[str, Any]] = {
    "q_influence": {"option_id": "a"},
    "q_compute": {"number": 3},
    "q_baseline": {"option_id": "a"},
    "q_zero_weight": {"truth": True},
    "q_negative_weight": {"option_id": "a"},
    "q_three_inputs": {"number": 1.5},
    "q_only_the_bias": {"text": "bias"},
    "q_why_a_bias": {"covered": ["shift"]},
}


@pytest.fixture
def course(client: TestClient) -> dict[str, Any]:
    created: dict[str, Any] = client.post("/v1/courses/sample").json()
    return created


@pytest.fixture
def lesson(client: TestClient, course: dict[str, Any]) -> dict[str, Any]:
    summary = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]
    loaded: dict[str, Any] = client.get(f"/v1/lessons/{summary['id']}").json()["lesson"]
    return loaded


def overview(client: TestClient, course: dict[str, Any]) -> dict[str, Any]:
    response = client.get(f"/v1/courses/{course['id']}/learning")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def progress_of(view: dict[str, Any], concept_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(
        item for item in view["concepts"] if item["concept_id"] == concept_id
    )
    return found


def answer(client: TestClient, lesson: dict[str, Any], question: str, **body: Any) -> Any:
    response = client.post(
        f"/v1/lessons/{lesson['lesson_id']}/questions/{question}/answer", json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def answer_at(
    services: Services,
    lesson: dict[str, Any],
    question: str,
    when: datetime,
    *,
    hinted: bool = False,
    unsure: bool = False,
    **response: Any,
) -> Any:
    fields = dict(response or RIGHT[question])
    for key in ("order", "covered"):
        if key in fields:
            fields[key] = tuple(fields[key])
    return services.assessment.answer(
        lesson["lesson_id"],
        question,
        Response(**fields),
        hinted=hinted,
        unsure=unsure,
        now=when,
    )


def strings_in(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings_in(item)]
    if isinstance(value, list):
        return [text for item in value for text in strings_in(item)]
    return []


def keys_in(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in keys_in(item)}
    if isinstance(value, list):
        return {key for item in value for key in keys_in(item)}
    return set()


# -- the next step ---------------------------------------------------------------------


def test_a_new_course_suggests_its_first_lesson_and_says_why(
    client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    view = overview(client, course)
    step = view["plan"]["recommended"]
    assert step["kind"] == "start_lesson"
    assert step["lesson_id"] == lesson["lesson_id"]
    assert step["title"] == f'Start "{lesson["title"]}"'
    assert step["reason"] == f'"{CONCEPT_TITLE}" is next in your course. It needs nothing first.'
    assert not step["needs_key"]
    assert view["plan"]["note"] is None

    assert view["summary"] == {
        "concepts": 8,
        "demonstrated": 0,
        "in_progress": 0,
        "not_assessed": 8,
        "reviews_due": 0,
        "next_review_at": None,
    }
    first = view["concepts"][0]
    assert first["title"] == CONCEPT_TITLE
    assert (first["lessons_total"], first["lessons_completed"]) == (1, 0)
    # Three questions in the lesson and five kept for practice.
    assert first["fresh_questions"] == 8
    assert first["hypotheses"] == []
    assert not first["review_due"]


def test_concepts_come_in_an_order_that_respects_what_each_needs(
    client: TestClient, course: dict[str, Any]
) -> None:
    view = overview(client, course)
    curriculum = client.get(f"/v1/courses/{course['id']}/curriculum").json()
    assert [item["concept_id"] for item in view["concepts"]] == curriculum["learning_order"]
    place = {item["concept_id"]: index for index, item in enumerate(view["concepts"])}
    for concept in curriculum["concepts"]:
        for needed in concept["prerequisites"]:
            assert place[needed["concept_id"]] < place[concept["id"]]


def test_a_lesson_left_part_way_is_what_to_continue(
    client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    client.put(f"/v1/lessons/{lesson['lesson_id']}/progress", json={"position": 2})
    step = overview(client, course)["plan"]["recommended"]
    assert (step["kind"], step["lesson_id"]) == ("resume_lesson", lesson["lesson_id"])
    assert step["reason"] == "You stopped part-way through this lesson."


def test_an_empty_course_asks_for_concepts(client: TestClient) -> None:
    created = client.post(
        "/v1/courses", json={"title": "Empty", "origin": "topic", "topic": "Anything"}
    ).json()
    view = overview(client, created)
    assert view["plan"]["recommended"]["kind"] == "add_concepts"
    assert view["concepts"] == []
    assert view["summary"]["concepts"] == 0


def test_a_course_that_does_not_exist_is_not_found(client: TestClient) -> None:
    assert client.get("/v1/courses/crs_00000000000000000000/learning").status_code == 404


def test_no_score_ever_reaches_the_interface(
    client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    answer(client, lesson, "q_influence", option_id="c")
    answer(client, lesson, "q_compute", number=3)
    answer(client, lesson, "q_baseline", option_id="b")
    concept_id = lesson["concept_ids"][0]
    payloads = [
        overview(client, course),
        client.post(f"/v1/concepts/{concept_id}/practice", json={}).json(),
        client.get(f"/v1/concepts/{concept_id}/evidence").json(),
    ]
    for payload in payloads:
        assert not {"probability", "score", "mastery", "percent"} & keys_in(payload)
        for text in strings_in(payload):
            assert "%" not in text
            assert "probab" not in text.lower()


# -- hypotheses about mistakes ------------------------------------------------------------


def test_one_answer_is_a_suspicion_and_a_second_makes_it_something_to_come_back_to(
    client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    first = answer(client, lesson, "q_influence", option_id="c")
    assert (
        "That answer could mean that what causes what may be the other way round. "
        "One answer is not enough to say" in first["change"]
    )
    assert "a possible misunderstanding to clear up" not in first["knowledge"]["missing"]
    (suspected,) = progress_of(overview(client, course), concept_id)["hypotheses"]
    assert suspected == {
        "kind": "causal_confusion",
        "status": "tentative",
        "description": (
            "One answer suggested that what causes what may be the other way round. "
            "One answer is not enough to say: Adle will ask a question that would show it."
        ),
        "is_slip": False,
        "can_dismiss": True,
    }

    second = answer(client, lesson, "q_baseline", option_id="b")
    assert (
        "This is the second answer suggesting that what causes what may be the other way "
        "round, so the next steps come back to it." in second["change"]
    )
    assert "a possible misunderstanding to clear up" in second["knowledge"]["missing"]
    view = overview(client, course)
    (supported,) = progress_of(view, concept_id)["hypotheses"]
    assert supported["status"] == "supported"

    # The next step is a check on exactly that, and it says that stopping is fine too.
    step = view["plan"]["recommended"]
    assert (step["kind"], step["concept_id"], step["about"]) == (
        "check",
        concept_id,
        "causal_confusion",
    )
    assert step["reason"].startswith(
        f'More than one answer on "{CONCEPT_TITLE}" suggests that what causes what'
    )
    assert view["plan"]["note"] == PAUSE_NOTE


def test_a_check_asks_the_question_that_would_show_it_and_right_answers_settle_it(
    client: TestClient, services: Services, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer_at(services, lesson, "q_influence", T0, option_id="c")
    answer_at(services, lesson, "q_baseline", T0, option_id="b")

    later = T0 + timedelta(minutes=5)
    practice = services.learning.start_practice(concept_id, about="causal_confusion", now=later)
    assert practice.purpose == "check"
    assert practice.reason.startswith(f'More than one answer on "{CONCEPT_TITLE}" suggests that')
    asked = [item.question.id for item in practice.questions]
    assert asked[0] == "q_negative_weight"
    # The two questions answered a moment ago are not asked again so soon.
    assert not {"q_influence", "q_baseline"} & set(asked)

    once = answer_at(services, lesson, "q_negative_weight", later)
    assert "This one goes against that; one more like it settles it." in once.change
    assert "a possible misunderstanding to clear up" in once.knowledge.missing

    # A day later the first question is worth asking again, and a right answer settles it.
    next_day = T0 + timedelta(days=1)
    twice = answer_at(services, lesson, "q_influence", next_day)
    assert "Your recent answers show it is sorted." in twice.change
    assert "a possible misunderstanding to clear up" not in twice.knowledge.missing
    view = services.learning.overview(course["id"], now=next_day)
    (settled,) = next(item.hypotheses for item in view.concepts if item.concept_id == concept_id)
    assert (settled.status, settled.can_dismiss) == ("resolved", False)
    assert settled.description.endswith("Your later answers show it is sorted.")


def test_a_right_answer_soon_after_seeing_the_explanation_settles_nothing(
    services: Services, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer_at(services, lesson, "q_influence", T0, option_id="c")
    # The same question, answered right a minute later: recall of the explanation.
    again = answer_at(services, lesson, "q_influence", T0 + timedelta(minutes=1))
    assert "You had seen its explanation a short while ago" in again.change
    view = services.learning.overview(course["id"], now=T0 + timedelta(minutes=2))
    (suspected,) = next(item.hypotheses for item in view.concepts if item.concept_id == concept_id)
    assert suspected.status == "tentative"


def test_the_learner_can_set_a_suspicion_aside(
    client: TestClient, course: dict[str, Any], lesson: dict[str, Any], services: Services
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer(client, lesson, "q_influence", option_id="c")
    answer(client, lesson, "q_baseline", option_id="b")
    before = progress_of(overview(client, course), concept_id)
    assert "a possible misunderstanding to clear up" in before["knowledge"]["missing"]

    response = client.post(f"/v1/concepts/{concept_id}/hypotheses/causal_confusion/dismiss")
    assert response.status_code == 200, response.text
    after = progress_of(response.json(), concept_id)
    (hypothesis,) = after["hypotheses"]
    assert hypothesis["status"] == "rejected"
    assert not hypothesis["can_dismiss"]
    assert "You said it was a slip, so it is set aside." in hypothesis["description"]
    # The learner has the last word: it no longer stands in the way.
    assert "a possible misunderstanding to clear up" not in after["knowledge"]["missing"]

    history = client.get(f"/v1/concepts/{concept_id}/evidence").json()["history"]
    assert history[0]["kind"] == "dismissal"
    assert history[0]["explanation"].startswith(
        "You said a suspected mix-up was only a slip, so it has been set aside."
    )
    with services.database.session() as session:
        (event,) = session.scalars(select(LearnerEvent)).all()
        assert (event.kind, event.concept_id, event.detail) == (
            "misconception_dismissed",
            concept_id,
            {"kind": "causal_confusion"},
        )

    # There is nothing left to set aside, and Adle says so rather than pretending.
    again = client.post(f"/v1/concepts/{concept_id}/hypotheses/causal_confusion/dismiss")
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "There is nothing like that to set aside any more."


def test_what_was_set_aside_comes_back_only_if_the_answers_say_so(
    services: Services, client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer_at(services, lesson, "q_influence", T0, option_id="c")
    services.learning.dismiss_hypothesis(concept_id, "causal_confusion", now=T0)
    reopened = answer_at(
        services, lesson, "q_negative_weight", T0 + timedelta(hours=1), option_id="b"
    )
    assert "That answer could mean that what causes what may be the other way round." in (
        reopened.change
    )
    view = services.learning.overview(course["id"], now=T0 + timedelta(hours=2))
    (hypothesis,) = next(item.hypotheses for item in view.concepts if item.concept_id == concept_id)
    # It starts again from one answer; the dismissal is not held against the learner.
    assert hypothesis.status == "tentative"


def test_only_a_known_kind_of_mistake_on_a_real_concept_can_be_dismissed(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    assert client.post(f"/v1/concepts/{concept_id}/hypotheses/laziness/dismiss").status_code == 422
    assert (
        client.post(
            "/v1/concepts/con_00000000000000000000/hypotheses/causal_confusion/dismiss"
        ).status_code
        == 404
    )
    # Nothing has suggested it, so there is nothing to dismiss.
    assert (
        client.post(f"/v1/concepts/{concept_id}/hypotheses/causal_confusion/dismiss").status_code
        == 409
    )


# -- distinct paths for distinct kinds of answer -------------------------------------------


def estimate(services: Services, concept_id: str) -> float:
    with services.database.session() as session:
        state = session.get(LearnerConceptState, concept_id)
        assert state is not None
        return state.probability


@pytest.mark.parametrize(
    ("how", "wording"),
    [
        ("right", "You answered a numeric question correctly."),
        ("hinted", "correctly after a hint, which counts as lighter evidence"),
        ("unsure", "correctly but said you were unsure, which counts as lighter evidence"),
        ("slip", "it looks like a slip rather than a gap in understanding"),
        ("wrong", "Your answer to a numeric question was not right yet."),
        ("skipped", "You skipped a question. Skipping is not counted either way."),
    ],
)
def test_each_kind_of_answer_is_recorded_as_what_it_is(
    services: Services, lesson: dict[str, Any], how: str, wording: str
) -> None:
    concept_id = lesson["concept_ids"][0]
    if how == "skipped":
        result = services.assessment.answer(lesson["lesson_id"], "q_compute", None, now=T0)
    else:
        result = answer_at(
            services,
            lesson,
            "q_compute",
            T0,
            hinted=how == "hinted",
            unsure=how == "unsure",
            number={"slip": -3, "wrong": 7}.get(how, 3),
        )
    assert wording in result.change

    with services.database.session() as session:
        attempt = session.scalars(select(Attempt)).one()
        observation = session.scalars(select(LearnerObservation)).one()
        state = session.get(LearnerConceptState, concept_id)
        assert state is not None
        assert attempt.reveals == ["arithmetic_slip"]
        assert attempt.misconception == ("arithmetic_slip" if how == "slip" else None)
        assert observation.slip is (how == "slip")
        assert (attempt.hinted, attempt.unsure) == (how == "hinted", how == "unsure")
        # Only a right answer given without help counts towards "demonstrated".
        assert state.unaided_correct == (1 if how == "right" else 0)
        assert state.answered == (0 if how == "skipped" else 1)
        # A slip is never something to "clear up".
        assert not state.unresolved_misconception


def test_the_kinds_of_answer_move_the_estimate_by_different_amounts(
    services: Services, client: TestClient, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    """Right, right with help, a slip, and a miss are four different pieces of evidence."""
    concepts = client.get(f"/v1/courses/{course['id']}/curriculum").json()["concepts"]
    lesson_concept = lesson["concept_ids"][0]
    # The same question cannot be asked of other concepts, so compare on one concept by
    # rebuilding from nothing each time.
    seen: dict[str, float] = {}
    for how, fields in {
        "right": {"number": 3},
        "hinted": {"number": 3, "hinted": True},
        "slip": {"number": -3},
        "wrong": {"number": 7},
    }.items():
        with services.database.session() as session:
            for table in (Attempt, LearnerObservation, LearnerConceptState):
                for row in session.scalars(select(table)).all():
                    session.delete(row)
        answer_at(services, lesson, "q_compute", T0, **fields)
        seen[how] = estimate(services, lesson_concept)
    # A right answer counts for most and a miss for least. A slip on a question that is
    # hard to guess shows the method, so it counts for more than a right answer that
    # followed a hint which gave the method away.
    assert seen["right"] > seen["slip"] > seen["hinted"] > seen["wrong"]
    assert len(concepts) == 8


# -- practice and review ----------------------------------------------------------------


def finish_lesson(services: Services, lesson: dict[str, Any], when: datetime) -> None:
    for question in ("q_influence", "q_compute", "q_baseline"):
        answer_at(services, lesson, question, when)
    services.lessons.save_progress(lesson["lesson_id"], len(lesson["segments"]) - 1, completed=True)


def test_practice_asks_what_the_evidence_still_lacks_and_never_sends_an_answer(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    answer(client, lesson, "q_influence", option_id="a")
    response = client.post(f"/v1/concepts/{concept_id}/practice", json={})
    assert response.status_code == 200, response.text
    practice = response.json()
    assert practice["purpose"] == "practise"
    assert practice["concept_title"] == CONCEPT_TITLE
    assert practice["reason"].startswith(f'"{CONCEPT_TITLE}" is at "Building understanding".')
    assert practice["next_fresh_at"] is None
    questions = practice["questions"]
    assert len(questions) == 3
    assert all(item["lesson_id"] == lesson["lesson_id"] for item in questions)
    # The one just answered is kept back; a new situation is asked about first, and the
    # three are of three different kinds.
    assert "q_influence" not in [item["question"]["id"] for item in questions]
    assert questions[0]["question"]["is_transfer"]
    assert len({item["question"]["form"] for item in questions}) == 3
    leaked = {
        "correct_option",
        "correct",
        "expected",
        "tolerance",
        "accepted",
        "feedback",
        "misconception",
        "explanation",
    }
    assert not leaked & keys_in(practice)


def test_a_practice_question_is_answered_like_any_other(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    result = answer(client, lesson, "q_zero_weight", truth=True)
    assert result["outcome"] == "correct"
    assert result["change"].startswith("You answered a true-or-false question correctly.")
    # It is not part of the lesson the player is given.
    shown = [
        segment["question"]["id"]
        for segment in lesson["segments"]
        if segment["type"] == "checkpoint"
    ]
    assert shown == ["q_influence", "q_compute", "q_baseline"]
    assert "practice" not in lesson


def test_how_many_questions_can_be_chosen_within_limits(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    five = client.post(f"/v1/concepts/{concept_id}/practice", json={"count": 5}).json()
    assert len(five["questions"]) == 5
    assert client.post(f"/v1/concepts/{concept_id}/practice", json={"count": 9}).status_code == 422
    assert (
        client.post(f"/v1/concepts/{concept_id}/practice", json={"about": "boredom"}).status_code
        == 422
    )
    assert client.post("/v1/concepts/con_00000000000000000000/practice", json={}).status_code == 404


def test_a_concept_without_questions_says_so(client: TestClient, course: dict[str, Any]) -> None:
    added = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={"title": "Regularisation", "objectives": ["Say what weight decay does."]},
    ).json()
    without_lesson = next(item for item in added["concepts"] if item["title"] == "Regularisation")
    practice = client.post(f"/v1/concepts/{without_lesson['id']}/practice", json={}).json()
    assert practice["questions"] == []
    assert practice["reason"] == (
        f'There are no questions on "{without_lesson["title"]}" yet. '
        "A lesson on it brings some with it."
    )


def test_what_was_answered_today_is_not_asked_again_today(
    services: Services, lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    for question in RIGHT:
        answer_at(services, lesson, question, T0)
    soon = services.learning.start_practice(concept_id, now=T0 + timedelta(hours=1))
    assert soon.questions == []
    assert soon.reason.startswith(f'Every question on "{CONCEPT_TITLE}" was answered in the last')
    assert soon.next_fresh_at == T0 + timedelta(hours=12)
    later = services.learning.start_practice(concept_id, now=T0 + timedelta(hours=13))
    assert len(later.questions) == 3
    assert later.next_fresh_at is None


def test_a_repeat_counts_in_full_only_after_a_real_gap(
    services: Services, lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]

    def unaided() -> int:
        with services.database.session() as session:
            state = session.get(LearnerConceptState, concept_id)
            assert state is not None
            return state.unaided_correct

    first = answer_at(services, lesson, "q_compute", T0)
    assert (first.attempt_number, unaided()) == (1, 1)
    soon = answer_at(services, lesson, "q_compute", T0 + timedelta(hours=1))
    assert "You had seen its explanation a short while ago" in soon.change
    assert (soon.attempt_number, unaided()) == (2, 1)
    next_day = answer_at(services, lesson, "q_compute", T0 + timedelta(hours=14))
    assert next_day.change.startswith("You answered a numeric question correctly.")
    assert "short while ago" not in next_day.change
    assert (next_day.attempt_number, unaided()) == (3, 2)


def test_a_review_comes_due_is_suggested_and_moves_on_when_it_is_done(
    services: Services, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    finish_lesson(services, lesson, T0)

    same_day = services.learning.overview(course["id"], now=T0 + timedelta(hours=1))
    assert same_day.summary.reviews_due == 0
    assert same_day.summary.next_review_at == T0 + timedelta(days=1)
    assert same_day.plan.recommended.kind != "review"

    two_days_on = T0 + timedelta(days=2)
    due = services.learning.overview(course["id"], now=two_days_on)
    step = due.plan.recommended
    assert (step.kind, step.concept_id) == ("review", concept_id)
    assert step.title == f'Review "{CONCEPT_TITLE}"'
    assert step.reason == (
        f'A review of "{CONCEPT_TITLE}" was due a day ago. '
        "Answering from memory after a gap is what makes it last."
    )
    assert due.summary.reviews_due == 1
    assert next(item for item in due.concepts if item.concept_id == concept_id).review_due

    practice = services.learning.start_practice(concept_id, now=two_days_on)
    assert practice.purpose == "review"
    assert practice.reason == step.reason
    asked = [item.question.id for item in practice.questions]
    # Three questions the lesson did not ask, of three kinds it has not seen answered.
    assert asked == ["q_only_the_bias", "q_zero_weight", "q_why_a_bias"]

    results = [answer_at(services, lesson, question, two_days_on) for question in asked]
    assert "Recalled without help. Next review in about" in results[0].change

    done = services.learning.overview(course["id"], now=two_days_on + timedelta(minutes=5))
    assert done.summary.reviews_due == 0
    assert done.plan.recommended.kind != "review"
    assert done.summary.next_review_at is not None
    assert done.summary.next_review_at > two_days_on + timedelta(days=1)


def test_finishing_a_lesson_is_remembered_once_with_when(
    client: TestClient, services: Services, lesson: dict[str, Any]
) -> None:
    last = len(lesson["segments"]) - 1
    for _ in range(2):
        client.put(
            f"/v1/lessons/{lesson['lesson_id']}/progress",
            json={"position": last, "completed": True},
        )
    client.put(f"/v1/lessons/{lesson['lesson_id']}/progress", json={"position": 0})
    with services.database.session() as session:
        (event,) = session.scalars(select(LearnerEvent)).all()
        assert (event.kind, event.lesson_id) == ("lesson_completed", lesson["lesson_id"])
        assert event.occurred_at.tzinfo is not None


# -- "this did not help" ------------------------------------------------------------------


def test_saying_an_explanation_did_not_help_changes_what_is_suggested(
    client: TestClient, services: Services, course: dict[str, Any], lesson: dict[str, Any]
) -> None:
    concept_id = lesson["concept_ids"][0]
    client.put(f"/v1/lessons/{lesson['lesson_id']}/progress", json={"position": 1})
    response = client.post(
        f"/v1/lessons/{lesson['lesson_id']}/unhelpful", json={"segment_id": "seg_sum"}
    )
    assert response.status_code == 204

    plan = overview(client, course)["plan"]
    offered = [plan["recommended"], *plan["alternatives"]]
    another = next(step for step in offered if step["kind"] == "another_explanation")
    assert another["concept_id"] == concept_id
    assert another["reason"].startswith(
        f'You said an explanation of "{CONCEPT_TITLE}" did not help.'
    )
    # No key is set up in this test. The offer says so instead of hiding, and something
    # that can be done without one is suggested first.
    assert another["needs_key"]
    assert not plan["recommended"]["needs_key"]
    # The lesson that did not help is still there to continue, but only as a last resort.
    assert plan["recommended"]["lesson_id"] != lesson["lesson_id"]
    assert (plan["alternatives"][-1]["kind"], plan["alternatives"][-1]["lesson_id"]) == (
        "resume_lesson",
        lesson["lesson_id"],
    )

    # With a key, what the learner asked for comes first, and stopping is said to be fine.
    services.credentials.set_api_key("sk-test-not-a-real-key")
    with_key = overview(client, course)["plan"]
    assert (with_key["recommended"]["kind"], with_key["recommended"]["concept_id"]) == (
        "another_explanation",
        concept_id,
    )
    assert not with_key["recommended"]["needs_key"]
    assert with_key["note"] == PAUSE_NOTE

    # Once a question on it goes well without help, the request has been answered.
    answer(client, lesson, "q_influence", option_id="a")
    assert overview(client, course)["plan"]["recommended"]["kind"] == "resume_lesson"


def test_only_a_real_part_of_a_real_lesson_can_be_reported(
    client: TestClient, lesson: dict[str, Any]
) -> None:
    lesson_id = lesson["lesson_id"]
    assert (
        client.post(
            f"/v1/lessons/{lesson_id}/unhelpful", json={"segment_id": "seg_nowhere"}
        ).json()["error"]["message"]
        == "That is not a part of this lesson."
    )
    assert (
        client.post(
            f"/v1/lessons/{lesson_id}/unhelpful", json={"segment_id": "../../etc"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/lessons/les_00000000000000000000/unhelpful", json={"segment_id": "seg_why"}
        ).status_code
        == 404
    )
