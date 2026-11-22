"""Spaced review: when a concept comes back, and why."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.review import (
    NOT_SCHEDULED,
    ReviewParameters,
    ReviewState,
    describe_gap,
    is_due,
    schedule,
)

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
PARAMETERS = ReviewParameters()
SOLID = 0.999


def after(state: ReviewState, *, days: float) -> datetime:
    """A moment ``days`` after the practice that produced ``state``."""
    assert state.due_at is not None
    assert state.interval_days is not None
    return state.due_at - timedelta(days=state.interval_days) + timedelta(days=days)


def first_review(probability: float = SOLID) -> ReviewState:
    return schedule(NOT_SCHEDULED, outcome=Outcome.CORRECT, probability=probability, now=NOW).state


# -- starting and growing --------------------------------------------------


def test_the_first_success_schedules_a_review_for_the_next_day() -> None:
    decision = schedule(NOT_SCHEDULED, outcome=Outcome.CORRECT, probability=0.9, now=NOW)
    assert decision.state == ReviewState(
        interval_days=1.0, due_at=NOW + timedelta(days=1), streak=1
    )
    assert decision.reason == "First review tomorrow."


def test_each_recall_on_time_pushes_the_next_review_further_away_up_to_a_limit() -> None:
    state = first_review()
    gaps = [state.interval_days]
    for _ in range(8):
        assert state.interval_days is not None
        decision = schedule(
            state,
            outcome=Outcome.CORRECT,
            probability=SOLID,
            now=after(state, days=state.interval_days),
        )
        state = decision.state
        gaps.append(state.interval_days)
    assert gaps == sorted(gaps)
    assert gaps[1] == pytest.approx(2.5, abs=0.01)
    assert gaps[-1] == PARAMETERS.max_interval_days
    assert state.streak == 9
    assert decision.reason == "Recalled without help. Next review in about 3 months."


def test_a_recall_that_needed_help_grows_the_gap_less() -> None:
    state = first_review()
    on_time = after(state, days=1)
    clean = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=on_time)
    hinted = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=on_time, hinted=True)
    unsure = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=on_time, unsure=True)
    assert clean.state.interval_days is not None
    assert hinted.state.interval_days is not None
    assert 1.0 < hinted.state.interval_days < clean.state.interval_days
    assert unsure.state.interval_days == hinted.state.interval_days
    assert hinted.reason is not None
    assert hinted.reason.startswith("Recalled with some help.")


def test_thinner_evidence_grows_the_gap_more_slowly() -> None:
    state = first_review(probability=0.7)
    on_time = after(state, days=1)
    thin = schedule(state, outcome=Outcome.CORRECT, probability=0.7, now=on_time)
    solid = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=on_time)
    assert thin.state.interval_days is not None
    assert solid.state.interval_days is not None
    assert 1.0 < thin.state.interval_days < solid.state.interval_days


# -- misses and pauses -----------------------------------------------------


@pytest.mark.parametrize("outcome", [Outcome.INCORRECT, Outcome.PARTIAL])
def test_a_miss_brings_the_concept_back_tomorrow(outcome: Outcome) -> None:
    state = ReviewState(interval_days=20.0, due_at=NOW, streak=4)
    decision = schedule(state, outcome=outcome, probability=0.8, now=NOW)
    assert decision.state == ReviewState(
        interval_days=1.0, due_at=NOW + timedelta(days=1), streak=0
    )
    assert decision.reason == "That one slipped, so it’ll come back tomorrow."


def test_reviews_pause_while_a_concept_is_being_relearned() -> None:
    scheduled = ReviewState(interval_days=5.0, due_at=NOW, streak=2)
    paused = schedule(scheduled, outcome=Outcome.INCORRECT, probability=0.3, now=NOW)
    assert paused.state == NOT_SCHEDULED
    assert paused.reason is not None
    assert "paused" in paused.reason
    # Nothing to pause, nothing to say.
    quiet = schedule(NOT_SCHEDULED, outcome=Outcome.CORRECT, probability=0.5, now=NOW)
    assert quiet.state == NOT_SCHEDULED
    assert quiet.reason is None


def test_skipping_changes_nothing() -> None:
    state = ReviewState(interval_days=5.0, due_at=NOW, streak=2)
    decision = schedule(state, outcome=Outcome.SKIPPED, probability=0.1, now=NOW)
    assert decision.state is state
    assert decision.reason is None


# -- elapsed time ----------------------------------------------------------


def test_repeating_something_straight_away_is_not_another_recall() -> None:
    state = first_review()
    decision = schedule(
        state, outcome=Outcome.CORRECT, probability=SOLID, now=NOW + timedelta(minutes=10)
    )
    assert decision.state == state
    assert decision.reason == "Practiced before the review was due. The schedule is unchanged."


def test_recalling_after_a_longer_gap_than_planned_earns_bounded_credit() -> None:
    state = ReviewState(interval_days=4.0, due_at=NOW, streak=2)
    on_time = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=after(state, days=4))
    late = schedule(state, outcome=Outcome.CORRECT, probability=SOLID, now=after(state, days=6))
    very_late = schedule(
        state, outcome=Outcome.CORRECT, probability=SOLID, now=after(state, days=40)
    )
    assert on_time.state.interval_days is not None
    assert late.state.interval_days is not None
    assert very_late.state.interval_days is not None
    assert on_time.state.interval_days < late.state.interval_days < very_late.state.interval_days
    # Credit stops at twice the planned gap.
    assert very_late.state.interval_days == pytest.approx(2 * on_time.state.interval_days)


def test_due_means_the_time_has_come() -> None:
    state = ReviewState(interval_days=1.0, due_at=NOW, streak=1)
    assert is_due(state, NOW)
    assert is_due(state, NOW + timedelta(seconds=1))
    assert not is_due(state, NOW - timedelta(seconds=1))
    assert not is_due(NOT_SCHEDULED, NOW)


# -- wording and validation ------------------------------------------------


@pytest.mark.parametrize(
    ("days", "words"),
    [
        (1.0, "tomorrow"),
        (1.4, "tomorrow"),
        (2.3, "in about 2 days"),
        (13.0, "in about 13 days"),
        (14.0, "in about 2 weeks"),
        (45.0, "in about 6 weeks"),
        (60.0, "in about 2 months"),
        (90.0, "in about 3 months"),
    ],
)
def test_gaps_are_described_in_everyday_words(days: float, words: str) -> None:
    assert describe_gap(days) == words


def test_times_must_be_unambiguous() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        schedule(
            NOT_SCHEDULED,
            outcome=Outcome.CORRECT,
            probability=0.9,
            now=NOW.replace(tzinfo=None),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"first_interval_days": 0.0},
        {"first_interval_days": 10.0, "max_interval_days": 5.0},
        {"clean_growth": 1.0, "assisted_growth": 1.0},
        {"assisted_growth": 3.0, "clean_growth": 2.0},
        {"min_probability": 1.0},
        {"min_elapsed_fraction": 1.5},
        {"late_credit_limit": 0.5},
    ],
)
def test_parameters_that_make_no_sense_are_refused(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"must|range"):
        ReviewParameters(**changes)


# -- properties ------------------------------------------------------------


@given(
    st.lists(
        st.tuples(
            st.sampled_from(list(Outcome)),
            st.floats(min_value=0.0, max_value=1.0),
            st.booleans(),
            st.booleans(),
            st.floats(min_value=0.0, max_value=24.0 * 200),
        ),
        max_size=40,
    )
)
def test_a_schedule_is_always_coherent(
    answers: list[tuple[Outcome, float, bool, bool, float]],
) -> None:
    state = NOT_SCHEDULED
    now = NOW
    for outcome, probability, hinted, unsure, hours_later in answers:
        now += timedelta(hours=hours_later)
        state = schedule(
            state,
            outcome=outcome,
            probability=probability,
            now=now,
            hinted=hinted,
            unsure=unsure,
        ).state
        assert (state.interval_days is None) == (state.due_at is None)
        assert state.streak >= 0
        if state.interval_days is not None and state.due_at is not None:
            assert (
                PARAMETERS.first_interval_days
                <= state.interval_days
                <= PARAMETERS.max_interval_days
            )
        else:
            assert state.streak == 0
