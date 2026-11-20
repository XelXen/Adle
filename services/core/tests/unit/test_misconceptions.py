"""Hypotheses about mistakes: opened, supported, rejected, resolved, by readable rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.misconceptions import (
    KIND_LABELS,
    SLIPS,
    Answer,
    Dismissal,
    Status,
    blocks_mastery,
    fold,
    needing_a_check,
)
from adle_core.lessons.ir import MISCONCEPTION_KINDS

START = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
KIND = "definition_confusion"


def wrong(minute: float, question: str = "q_1", kind: str | None = KIND, **extra: object) -> Answer:
    return Answer(
        occurred_at=START + timedelta(minutes=minute),
        question_id=question,
        outcome=Outcome.INCORRECT,
        suggests=kind,
        reveals=frozenset({kind} if kind else ()),
        **extra,  # type: ignore[arg-type]
    )


def right(
    minute: float, question: str = "q_2", reveals: tuple[str, ...] = (KIND,), **extra: object
) -> Answer:
    return Answer(
        occurred_at=START + timedelta(minutes=minute),
        question_id=question,
        outcome=Outcome.CORRECT,
        reveals=frozenset(reveals),
        **extra,  # type: ignore[arg-type]
    )


def test_every_kind_a_lesson_can_name_has_words_for_the_learner() -> None:
    assert set(KIND_LABELS) == set(MISCONCEPTION_KINDS)
    for label in KIND_LABELS.values():
        # Said as a possibility about the idea, never as a fault of the person.
        assert "you" not in label.lower().split()
        assert not label.endswith(".")


def test_nothing_is_suspected_without_a_wrong_answer_that_points_somewhere() -> None:
    assert fold([]) == {}
    assert fold([right(0), wrong(1, kind=None)]) == {}
    # A kind Adle has no rule for is not invented into a hypothesis.
    assert fold([wrong(0, kind="laziness")]) == {}


def test_one_answer_is_a_suspicion_not_a_diagnosis() -> None:
    (hypothesis,) = fold([wrong(0)]).values()
    assert hypothesis.status is Status.TENTATIVE
    assert hypothesis.suggested == 1
    assert hypothesis.is_open
    assert not hypothesis.blocks_mastery
    assert "One answer is not enough to say" in hypothesis.describe()


def test_an_independent_second_answer_makes_it_supported() -> None:
    hypothesis = fold([wrong(0, "q_1"), wrong(5, "q_3")])[KIND]
    assert hypothesis.status is Status.SUPPORTED
    assert hypothesis.suggested == 2
    assert hypothesis.blocks_mastery
    assert blocks_mastery([hypothesis])
    assert hypothesis.last_changed_at == START + timedelta(minutes=5)


def test_clicking_the_same_wrong_option_again_is_not_a_second_piece_of_evidence() -> None:
    hypothesis = fold([wrong(0, "q_1"), wrong(1, "q_1"), wrong(2, "q_1")])[KIND]
    assert hypothesis.status is Status.TENTATIVE
    assert hypothesis.suggested == 1


def test_the_same_question_on_another_day_is_independent() -> None:
    hypothesis = fold([wrong(0, "q_1"), wrong(60 * 13, "q_1")])[KIND]
    assert hypothesis.status is Status.SUPPORTED


def test_a_question_that_could_have_shown_it_and_did_not_rejects_a_suspicion() -> None:
    hypothesis = fold([wrong(0), right(5)])[KIND]
    assert hypothesis.status is Status.REJECTED
    assert not hypothesis.is_open
    assert "A later question did not show it" in hypothesis.describe()


def test_a_right_answer_to_an_unrelated_question_clears_nothing() -> None:
    assert (
        fold([wrong(0), right(5, reveals=("causal_confusion",))])[KIND].status is Status.TENTATIVE
    )
    assert fold([wrong(0), right(5, reveals=())])[KIND].status is Status.TENTATIVE


@pytest.mark.parametrize("extra", [{"hinted": True}, {"unsure": True}])
def test_a_right_answer_with_help_or_doubt_clears_nothing(extra: dict[str, bool]) -> None:
    assert fold([wrong(0), right(5, **extra)])[KIND].status is Status.TENTATIVE


def test_a_supported_hypothesis_takes_two_clean_answers_to_resolve() -> None:
    events = [wrong(0, "q_1"), wrong(5, "q_3"), right(10, "q_4")]
    once = fold(events)[KIND]
    assert (once.status, once.countered) == (Status.SUPPORTED, 1)
    assert once.blocks_mastery

    resolved = fold([*events, right(15, "q_5")])[KIND]
    assert resolved.status is Status.RESOLVED
    assert not resolved.blocks_mastery
    assert "show it is sorted" in resolved.describe()


def test_pointing_at_it_again_undoes_progress_towards_resolving_it() -> None:
    events = [
        wrong(0, "q_1"),
        wrong(5, "q_3"),
        right(10, "q_4"),
        wrong(15, "q_5"),
        right(20, "q_6"),
    ]
    hypothesis = fold(events)[KIND]
    assert (hypothesis.status, hypothesis.countered) == (Status.SUPPORTED, 1)


def test_a_settled_hypothesis_can_be_reopened_and_starts_from_one_answer_again() -> None:
    resolved = [wrong(0, "q_1"), wrong(5, "q_3"), right(10, "q_4"), right(15, "q_5")]
    again = fold([*resolved, wrong(60, "q_6")])[KIND]
    assert again.status is Status.TENTATIVE
    assert again.suggested == 1
    # It remembers when it was first seen.
    assert again.first_seen_at == START


def test_the_learner_can_say_it_was_a_slip() -> None:
    dismissed = fold([wrong(0), Dismissal(START + timedelta(minutes=2), KIND)])[KIND]
    assert dismissed.status is Status.REJECTED
    assert dismissed.dismissed_by_learner
    assert "You said it was a slip" in dismissed.describe()
    # Even a supported one: the learner has the last word, until the answers say otherwise.
    supported = [wrong(0, "q_1"), wrong(5, "q_3"), Dismissal(START + timedelta(minutes=6), KIND)]
    assert fold(supported)[KIND].status is Status.REJECTED
    assert fold([*supported, wrong(30, "q_4")])[KIND].status is Status.TENTATIVE


def test_dismissing_something_that_is_not_open_changes_nothing() -> None:
    assert fold([Dismissal(START, KIND)]) == {}
    settled = [wrong(0), right(5), Dismissal(START + timedelta(minutes=9), KIND)]
    hypothesis = fold(settled)[KIND]
    assert (hypothesis.status, hypothesis.dismissed_by_learner) == (Status.REJECTED, False)


@pytest.mark.parametrize("kind", sorted(SLIPS))
def test_a_slip_is_noted_and_never_held_against_understanding(kind: str) -> None:
    hypothesis = fold([wrong(0, "q_1", kind), wrong(5, "q_2", kind)])[kind]
    assert hypothesis.status is Status.SUPPORTED
    assert hypothesis.is_slip
    assert not hypothesis.blocks_mastery
    assert "treated as a slip, not as a gap" in hypothesis.describe()
    assert needing_a_check([hypothesis]) == []


def test_skips_say_nothing() -> None:
    skipped = Answer(START, "q_1", Outcome.SKIPPED, suggests=KIND, reveals=frozenset({KIND}))
    assert fold([skipped]) == {}
    assert (
        fold(
            [
                wrong(0),
                Answer(
                    START + timedelta(minutes=5), "q_2", Outcome.SKIPPED, reveals=frozenset({KIND})
                ),
            ]
        )[KIND].status
        is Status.TENTATIVE
    )


def test_a_partly_right_answer_can_point_at_a_mistake_too() -> None:
    partial = Answer(START, "q_1", Outcome.PARTIAL, suggests="procedure_order")
    assert fold([partial])["procedure_order"].status is Status.TENTATIVE


def test_events_are_applied_in_the_order_they_happened_however_they_are_given() -> None:
    events = [wrong(0, "q_1"), wrong(5, "q_3"), right(10, "q_4"), right(15, "q_5")]
    assert fold(reversed(events)) == fold(events)


def test_what_to_ask_about_next_puts_the_established_before_the_suspected() -> None:
    hypotheses = fold(
        [
            wrong(0, "q_1", "causal_confusion"),
            wrong(1, "q_2", "definition_confusion"),
            wrong(2, "q_3", "definition_confusion"),
            wrong(3, "q_4", "arithmetic_slip"),
            wrong(4, "q_5", "overgeneralization"),
            right(5, "q_6", reveals=("overgeneralization",)),
        ]
    )
    assert [hypothesis.kind for hypothesis in needing_a_check(hypotheses.values())] == [
        "definition_confusion",
        "causal_confusion",
    ]
    assert blocks_mastery(hypotheses.values())


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=5000),
            st.sampled_from(["q_1", "q_2", "q_3"]),
            st.sampled_from(["right", "wrong", "skip", "dismiss"]),
            st.sampled_from(sorted(KIND_LABELS)),
            st.booleans(),
        ),
        max_size=40,
    )
)
def test_any_record_folds_to_coherent_hypotheses(
    record: list[tuple[int, str, str, str, bool]],
) -> None:
    events: list[Answer | Dismissal] = []
    for minute, question, what, kind, flag in record:
        at = START + timedelta(minutes=minute)
        if what == "dismiss":
            events.append(Dismissal(at, kind))
        elif what == "skip":
            events.append(Answer(at, question, Outcome.SKIPPED))
        elif what == "wrong":
            events.append(
                Answer(at, question, Outcome.INCORRECT, suggests=kind, reveals=frozenset({kind}))
            )
        else:
            events.append(
                Answer(at, question, Outcome.CORRECT, hinted=flag, reveals=frozenset({kind}))
            )

    hypotheses = fold(events)
    suggested_kinds = {
        e.suggests for e in events if isinstance(e, Answer) and e.outcome is Outcome.INCORRECT
    }
    # A hypothesis exists only for something an answer pointed at.
    assert set(hypotheses) <= suggested_kinds
    for kind, hypothesis in hypotheses.items():
        assert hypothesis.kind == kind
        assert hypothesis.suggested >= 1
        assert hypothesis.countered >= 0
        assert hypothesis.first_seen_at <= hypothesis.last_changed_at
        assert hypothesis.describe()
        if hypothesis.status is Status.RESOLVED:
            assert hypothesis.countered >= 2
        if hypothesis.blocks_mastery:
            assert hypothesis.status is Status.SUPPORTED
            assert kind not in SLIPS
