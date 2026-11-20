"""Questions kept for practice, and lessons that teach the same thing a different way."""

from __future__ import annotations

import copy
from typing import Any

from fastapi.testclient import TestClient

from adle_core.application.generation import STRATEGY_ROTATION, next_strategy
from adle_core.application.services import Services
from adle_core.generation import prompts
from adle_core.generation.drafts import (
    LessonContext,
    compile_lesson,
    parse_lesson_draft,
)
from adle_core.learner_model.next_step import MAX_LESSONS_PER_CONCEPT
from adle_core.lessons.bundle import parse_bundle
from adle_core.lessons.ir import MAX_PRACTICE_ITEMS, STRATEGIES, Lesson
from adle_core.lessons.player import player_view
from tests.support.model import LESSON, FakeProvider
from tests.unit.test_drafts import CONTEXT
from tests.unit.test_generation_api import add_concept, finished, keyed, topic_course  # noqa: F401
from tests.unit.test_lesson_ir import bundle, choice, problems

# -- in the lesson format ----------------------------------------------------------------


def test_a_lesson_may_carry_questions_that_are_not_part_of_its_flow() -> None:
    extra = choice("q_kept_for_later")
    parsed = parse_bundle(bundle(practice=[extra]))
    assert [question.id for question in parsed.lesson.questions()] == ["q_which_input"]
    assert [question.id for question in parsed.lesson.practice] == ["q_kept_for_later"]
    assert [question.id for question in parsed.lesson.all_questions()] == [
        "q_which_input",
        "q_kept_for_later",
    ]
    # They survive being stored and read back.
    again = Lesson.model_validate(parsed.lesson.model_dump(mode="json"))
    assert again == parsed.lesson


def test_a_lesson_written_before_practice_questions_existed_still_reads() -> None:
    stored = parse_bundle(bundle()).lesson.model_dump(mode="json")
    del stored["practice"]
    assert Lesson.model_validate(stored).practice == []


def test_practice_questions_follow_the_same_rules_as_the_others() -> None:
    same_id = problems(bundle(practice=[choice("q_which_input")]))
    assert any("question ids must be different" in message for _, message in same_id)

    elsewhere = choice("q_other", concept_id="con_00000000000000000009")
    other_concept = problems(bundle(practice=[elsewhere]))
    assert any("a concept this lesson does not teach" in message for _, message in other_concept)

    too_many = [choice(f"q_extra_{n}") for n in range(MAX_PRACTICE_ITEMS + 1)]
    assert any("practice" in where for where, _ in problems(bundle(practice=too_many)))


def test_the_player_is_not_given_the_practice_questions() -> None:
    parsed = parse_bundle(bundle(practice=[choice("q_kept_for_later")]))
    view = player_view(parsed.lesson).model_dump(mode="json")
    assert "practice" not in view
    assert "q_kept_for_later" not in str(view)


# -- written by a model ----------------------------------------------------------------------


def draft(**changes: Any) -> dict[str, Any]:
    return {**copy.deepcopy(LESSON), **changes}


def extra_question(**changes: Any) -> dict[str, Any]:
    return {
        "form": "true_false",
        "stem": "A weight of zero means the input is ignored.",
        "correct": True,
        "explanation": "Anything times zero is zero.",
        "objective": 2,
        **changes,
    }


def test_extra_questions_in_a_draft_are_kept_for_practice_with_ids_of_their_own() -> None:
    compiled = compile_lesson(
        parse_lesson_draft(draft(practice=[extra_question(), extra_question(transfer=True)])),
        CONTEXT,
    )
    lesson = Lesson.model_validate(compiled.lesson)
    assert [question.id for question in lesson.practice] == ["q_practice_1", "q_practice_2"]
    assert lesson.practice[0].objective_id == CONTEXT.objectives[1].id
    assert [question.is_transfer for question in lesson.practice] == [False, True]
    assert {question.concept_id for question in lesson.practice} == {CONTEXT.concept_id}


def test_an_extra_question_that_cannot_be_used_is_left_out_not_fatal() -> None:
    unusable = [
        extra_question(form="true_false", correct=None),
        extra_question(form="riddle"),
        # Markup is refused by the lesson format; the question is dropped, the lesson kept.
        extra_question(stem="Click <a href=x>here</a>"),
        extra_question(),
    ]
    compiled = compile_lesson(parse_lesson_draft(draft(practice=unusable)), CONTEXT)
    lesson = Lesson.model_validate(compiled.lesson)
    assert [question.id for question in lesson.practice] == ["q_practice_4"]


def test_a_draft_without_extra_questions_is_still_a_lesson() -> None:
    compiled = compile_lesson(parse_lesson_draft(draft()), CONTEXT)
    assert Lesson.model_validate(compiled.lesson).practice == []


def test_the_way_of_teaching_that_was_asked_for_is_what_the_lesson_records() -> None:
    asked = LessonContext(
        lesson_id=CONTEXT.lesson_id,
        course_id=CONTEXT.course_id,
        concept_id=CONTEXT.concept_id,
        objectives=CONTEXT.objectives,
        passages=CONTEXT.passages,
        strategy="analogy",
    )
    # Whatever the model says about itself.
    compiled = compile_lesson(parse_lesson_draft(draft(strategy="visual")), asked)
    assert compiled.lesson["strategy"] == "analogy"


def test_another_explanation_uses_a_way_not_tried_yet() -> None:
    assert next_strategy([]) is None
    assert next_strategy(["visual"]) == "worked_example"
    assert next_strategy(["visual", "worked_example", "analogy"]) == "mathematical"
    assert next_strategy(list(STRATEGY_ROTATION)) is None
    assert set(STRATEGY_ROTATION) == set(STRATEGIES) == set(prompts.STRATEGY_BRIEFS)


def test_the_prompt_asks_for_practice_questions_and_names_the_way_to_teach() -> None:
    concept = prompts.ConceptBrief(
        title="Weights", summary="", objectives=["Compute a weighted sum."], prerequisites=[]
    )
    learner = prompts.LearnerBrief(
        knowledge="Not assessed.", pace="moderate", explanation_density="moderate", goal=""
    )
    plain = prompts.lesson_request(
        course_title="Networks", concept=concept, learner=learner, passages=[]
    )
    assert '"practice": [ 3 more questions' in plain.user
    assert "Teach it the" not in plain.user

    another = prompts.lesson_request(
        course_title="Networks",
        concept=concept,
        learner=learner,
        passages=[],
        approach="worked_example",
        earlier=["visual"],
    )
    assert 'Teach it the "worked_example" way: lead with one concrete problem' in another.user
    assert 'Set "strategy" to "worked_example".' in another.user
    assert 'already had a lesson on this concept ("visual")' in another.user
    assert "Do not write that lesson again" in another.user


# -- through the service -----------------------------------------------------------------------


def lessons_of(client: TestClient, course_id: str) -> list[dict[str, Any]]:
    summaries = client.get(f"/v1/courses/{course_id}/lessons").json()["lessons"]
    return [client.get(f"/v1/lessons/{item['id']}").json()["lesson"] for item in summaries]


def test_a_second_lesson_on_a_concept_is_taught_another_way(
    keyed: TestClient,  # noqa: F811
    services: Services,
    provider: FakeProvider,
) -> None:
    course = topic_course(keyed, "Neural networks")
    concept = add_concept(keyed, course["id"])

    first = finished(services, keyed.post(f"/v1/concepts/{concept}/lessons"))
    assert first["status"] == "succeeded", first
    assert "Teach it the" not in provider.prompt(0)

    second = finished(services, keyed.post(f"/v1/concepts/{concept}/lessons"))
    assert second["status"] == "succeeded", second
    prompt = provider.prompt(3)
    assert 'Teach it the "worked_example" way' in prompt
    assert 'already had a lesson on this concept ("visual")' in prompt

    chosen = finished(
        services, keyed.post(f"/v1/concepts/{concept}/lessons", json={"strategy": "socratic"})
    )
    assert chosen["status"] == "succeeded", chosen
    assert 'Teach it the "socratic" way' in provider.prompt(6)

    # The stand-in model always says "visual". What was asked for is what is recorded.
    assert [lesson["strategy"] for lesson in lessons_of(keyed, course["id"])] == [
        "visual",
        "worked_example",
        "socratic",
    ]


def test_a_way_of_teaching_adle_does_not_know_is_refused(
    keyed: TestClient,  # noqa: F811
    provider: FakeProvider,
) -> None:
    course = topic_course(keyed)
    concept = add_concept(keyed, course["id"])
    response = keyed.post(f"/v1/concepts/{concept}/lessons", json={"strategy": "hypnosis"})
    assert response.status_code == 422
    assert provider.requests == []


def test_explanations_of_one_concept_are_bounded(
    keyed: TestClient,  # noqa: F811
    services: Services,
    provider: FakeProvider,
) -> None:
    course = topic_course(keyed)
    concept = add_concept(keyed, course["id"])
    for _ in range(MAX_LESSONS_PER_CONCEPT):
        job = finished(services, keyed.post(f"/v1/concepts/{concept}/lessons"))
        assert job["status"] == "succeeded", job
    sent = len(provider.requests)

    refused = keyed.post(f"/v1/concepts/{concept}/lessons")
    assert refused.status_code == 409
    assert refused.json()["error"]["message"] == (
        f"This concept already has {MAX_LESSONS_PER_CONCEPT} lessons. "
        "Remove one you no longer want before creating another."
    )
    assert len(provider.requests) == sent

    # The next step no longer offers yet another explanation of it either.
    view = keyed.get(f"/v1/courses/{course['id']}/learning").json()
    kinds = [
        view["plan"]["recommended"]["kind"],
        *(s["kind"] for s in view["plan"]["alternatives"]),
    ]
    assert "another_explanation" not in kinds
