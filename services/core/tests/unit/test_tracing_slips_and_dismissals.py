"""Knowledge tracing, continued: slips, repeats, and misunderstandings that stand or are set aside."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.mastery import MasteryState, assess
from adle_core.learner_model.tracing import (
    ConceptKnowledge,
    Observation,
    ObservationKind,
    apply,
    initial_knowledge,
    replay,
)

START = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)


def answer(
    outcome: Outcome = Outcome.CORRECT,
    form: str = "multiple_choice",
    *,
    minutes: int = 0,
    transfer: bool = False,
    unresolved: bool | None = None,
) -> Observation:
    return Observation(
        kind=ObservationKind.ANSWER,
        occurred_at=START + timedelta(minutes=minutes),
        outcome=outcome,
        question_form=form,
        is_transfer=transfer,
        unresolved_misconception=unresolved,
    )


def slip(form: str = "numeric", *, minutes: int = 0) -> Observation:
    return Observation(
        kind=ObservationKind.ANSWER,
        occurred_at=START + timedelta(minutes=minutes),
        outcome=Outcome.INCORRECT,
        question_form=form,
        slip=True,
    )


def strong_evidence() -> ConceptKnowledge:
    return replay(
        [
            answer(form="numeric", minutes=0),
            answer(form="multiple_choice", minutes=1),
            answer(form="numeric", minutes=2, transfer=True),
            answer(form="multiple_choice", minutes=3),
        ]
    )


def test_a_slip_counts_as_partly_right_and_says_so() -> None:
    knowledge = replay([answer(form="numeric"), answer(form="multiple_choice", minutes=1)])
    slipped = apply(knowledge, slip(minutes=2))
    missed = apply(knowledge, answer(Outcome.INCORRECT, form="numeric", minutes=2))
    partial = apply(knowledge, answer(Outcome.PARTIAL, form="numeric", minutes=2))

    # The same evidence as an answer that was partly right, and kinder than a plain miss.
    assert slipped.after.probability == pytest.approx(partial.after.probability)
    assert slipped.after.probability > missed.after.probability
    assert "looks like a slip, not a gap" in slipped.explanation
    assert "It counts as partly right." in slipped.explanation
    # It is still an answer that was not right: it earns no credit as a correct one.
    assert slipped.after.answered == knowledge.answered + 1
    assert slipped.after.correct == knowledge.correct
    assert slipped.after.unaided_correct == knowledge.unaided_correct


def test_only_a_wrong_answer_can_be_a_slip() -> None:
    with pytest.raises(ValueError, match="Only a wrong answer can be a slip"):
        Observation(
            kind=ObservationKind.ANSWER,
            occurred_at=START,
            outcome=Outcome.CORRECT,
            question_form="numeric",
            slip=True,
        )


def test_a_repeat_soon_after_is_described_as_one_and_not_as_a_hint() -> None:
    repeated = Observation(
        kind=ObservationKind.ANSWER,
        occurred_at=START,
        outcome=Outcome.CORRECT,
        question_form="numeric",
        hinted=True,
        repeated=True,
    )
    transition = apply(initial_knowledge(), repeated)
    assert "You’d just seen its explanation" in transition.explanation
    assert "after a hint" not in transition.explanation
    # It is recorded as an aided answer all the same.
    assert transition.after.unaided_correct == 0


def test_a_standing_misunderstanding_blocks_demonstrated_until_it_is_cleared() -> None:
    knowledge = strong_evidence()
    assert assess(knowledge.evidence()).state is MasteryState.DEMONSTRATED

    blocked = apply(knowledge, answer(form="numeric", minutes=5, unresolved=True))
    assert blocked.after.unresolved_misconception
    assert blocked.state_after is not MasteryState.DEMONSTRATED
    assert "a possible misunderstanding to clear up" in blocked.assessment.missing

    # An answer that says nothing about it leaves it standing.
    still = apply(blocked.after, answer(form="numeric", minutes=6))
    assert still.after.unresolved_misconception

    cleared = apply(still.after, answer(form="multiple_choice", minutes=7, unresolved=False))
    assert not cleared.after.unresolved_misconception
    assert cleared.state_after is MasteryState.DEMONSTRATED


def test_setting_a_suspicion_aside_is_an_observation_with_its_own_sentence() -> None:
    knowledge = apply(strong_evidence(), answer(form="numeric", minutes=5, unresolved=True)).after
    dismissal = Observation(
        kind=ObservationKind.DISMISSAL,
        occurred_at=START + timedelta(days=3),
        unresolved_misconception=False,
    )
    transition = apply(knowledge, dismissal)
    assert transition.explanation.startswith(
        "You marked a suspected mix-up as a slip, so it’s set aside."
    )
    assert transition.state_before is not MasteryState.DEMONSTRATED
    assert transition.state_after is MasteryState.DEMONSTRATED
    # Nothing was practised: the estimate, the counts, and "last practised" stay as they were.
    assert transition.after.probability == knowledge.probability
    assert transition.after.answered == knowledge.answered
    assert transition.after.last_observed_at == knowledge.last_observed_at
    assert transition.after.review == knowledge.review


def test_a_dismissal_must_say_what_still_stands() -> None:
    with pytest.raises(ValueError, match="must say what still stands"):
        Observation(kind=ObservationKind.DISMISSAL, occurred_at=START)
    with pytest.raises(ValueError, match="no outcome"):
        Observation(
            kind=ObservationKind.DISMISSAL,
            occurred_at=START,
            outcome=Outcome.CORRECT,
            unresolved_misconception=False,
        )


def test_what_only_the_caller_knows_is_said_between_what_happened_and_what_it_means() -> None:
    transition = apply(
        initial_knowledge(),
        answer(Outcome.INCORRECT, form="multiple_choice"),
        note="That answer could mean that two terms may be getting mixed up.",
    )
    happened = transition.explanation.index("wasn’t right")
    note = transition.explanation.index("That answer could mean")
    meaning = transition.explanation.index("Now: ")
    assert happened < note < meaning


def test_replaying_observations_reproduces_slips_and_misunderstandings() -> None:
    observations = [
        answer(form="numeric"),
        slip(minutes=1),
        answer(Outcome.INCORRECT, form="multiple_choice", minutes=2, unresolved=True),
        Observation(
            kind=ObservationKind.DISMISSAL,
            occurred_at=START + timedelta(minutes=3),
            unresolved_misconception=False,
        ),
    ]
    step_by_step = initial_knowledge()
    seen_blocked = False
    for observation in observations:
        step_by_step = apply(step_by_step, observation).after
        seen_blocked = seen_blocked or step_by_step.unresolved_misconception
    assert seen_blocked
    assert replay(observations) == step_by_step
    assert not step_by_step.unresolved_misconception
