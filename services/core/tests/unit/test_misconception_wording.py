"""What the learner is told when an answer changes a hypothesis: tentative, and never blaming."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from adle_core.evaluation.scoring import reveals
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.misconceptions import (
    KIND_LABELS,
    Answer,
    Hypothesis,
    describe_change,
    fold,
)
from tests.unit.test_scoring import CHOICE, NUMERIC, ORDERING, SHORT, item

START = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
KIND = "definition_confusion"


def wrong(minute: float, question: str, kind: str = KIND) -> Answer:
    return Answer(
        occurred_at=START + timedelta(minutes=minute),
        question_id=question,
        outcome=Outcome.INCORRECT,
        suggests=kind,
        reveals=frozenset({kind}),
    )


def right(minute: float, question: str, kind: str = KIND) -> Answer:
    return Answer(
        occurred_at=START + timedelta(minutes=minute),
        question_id=question,
        outcome=Outcome.CORRECT,
        reveals=frozenset({kind}),
    )


def test_what_one_answer_changed_is_said_no_more_strongly_than_the_evidence() -> None:
    nothing: dict[str, Hypothesis] = {}
    first = fold([wrong(0, "q_1")])
    assert describe_change(nothing, first) == (
        "That answer could mean that two terms may be getting mixed up. "
        "A follow-up question will check."
    )

    second = fold([wrong(0, "q_1"), wrong(5, "q_3")])
    assert describe_change(first, second).startswith(
        "This is the second answer suggesting that two terms may be getting mixed up"
    )

    countered = fold([wrong(0, "q_1"), wrong(5, "q_3"), right(10, "q_4")])
    assert "This one goes against that. One more like it settles it." in describe_change(
        second, countered
    )

    resolved = fold([wrong(0, "q_1"), wrong(5, "q_3"), right(10, "q_4"), right(15, "q_5")])
    assert describe_change(countered, resolved).endswith("Recent answers show it’s resolved.")

    rejected = fold([wrong(0, "q_1"), right(5, "q_2")])
    assert "This one shows otherwise, so it’s set aside." in describe_change(first, rejected)


def test_an_answer_that_changes_nothing_adds_no_sentence() -> None:
    first = fold([wrong(0, "q_1")])
    assert describe_change(first, first) == ""
    # The same wrong option again is not new evidence, so there is nothing new to say.
    again = fold([wrong(0, "q_1"), wrong(1, "q_1")])
    assert describe_change(first, again) == ""
    # A slip is described with the answer itself, not as a hypothesis about the idea.
    assert describe_change({}, fold([wrong(0, "q_1", "arithmetic_slip")])) == ""


def test_no_sentence_about_a_hypothesis_blames_the_learner() -> None:
    for kind in sorted(KIND_LABELS):
        opened = fold([wrong(0, "q_1", kind)])
        supported = fold([wrong(0, "q_1", kind), wrong(5, "q_2", kind)])
        sentences = [
            describe_change({}, opened),
            describe_change(opened, supported),
            *(hypothesis.describe() for hypothesis in supported.values()),
        ]
        for sentence in sentences:
            lowered = sentence.lower()
            for phrase in ("you got", "your mistake", "you are wrong", "you failed", "careless"):
                assert phrase not in lowered


# -- what a question is able to reveal ------------------------------------------------


def test_a_choice_can_reveal_what_its_wrong_options_are_tagged_with() -> None:
    assert reveals(CHOICE) == frozenset({"definition_confusion"})
    tagged_on_the_right_answer = item(
        "multiple_choice",
        options=[
            # A tag on the correct option means nothing: choosing it is not a mistake.
            {"id": "a", "text": "Right", "misconception": "causal_confusion"},
            {"id": "b", "text": "Wrong", "misconception": "overgeneralization"},
        ],
        correct_option="a",
    )
    assert reveals(tagged_on_the_right_answer) == frozenset({"overgeneralization"})


def test_a_number_can_reveal_a_slip_of_sign_unless_the_answer_is_zero() -> None:
    assert reveals(NUMERIC) == frozenset({"arithmetic_slip"})
    assert reveals(item("numeric", expected=0)) == frozenset()


def test_an_order_can_reveal_steps_out_of_order_and_words_reveal_nothing() -> None:
    assert reveals(ORDERING) == frozenset({"procedure_order"})
    assert reveals(SHORT) == frozenset()
    assert reveals(item("true_false", correct=True)) == frozenset()
