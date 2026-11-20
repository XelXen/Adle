"""A sitting, read off the record, and what it showed."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.learner_model.mastery import MasteryState
from adle_core.learner_model.sitting import (
    SITTING_GAP,
    Activity,
    ConceptNow,
    PlannedReview,
    Shown,
    StillNeeded,
    latest_sitting,
)

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


def ago(**span: float) -> datetime:
    return NOW - timedelta(**span)


def right(concept: str, **span: float) -> Activity:
    return Activity(
        at=ago(**span), concept_id=concept, answered=True, right=True, right_unaided=True
    )


def lighter(concept: str, **span: float) -> Activity:
    """Right, but after a hint, or unsure, or marked by the learner, or a repeat."""
    return Activity(at=ago(**span), concept_id=concept, answered=True, right=True)


def wrong(concept: str, **span: float) -> Activity:
    return Activity(at=ago(**span), concept_id=concept, answered=True)


def skipped(concept: str, **span: float) -> Activity:
    return Activity(at=ago(**span), concept_id=concept)


def finished(concept: str, **span: float) -> Activity:
    return Activity(at=ago(**span), concept_id=concept, lesson_completed=True)


BUILDING = ConceptNow(
    id="weights",
    title="Weights and bias",
    state=MasteryState.BUILDING,
    missing=("2 more correct answers without a hint",),
    review_due_at=NOW + timedelta(days=2),
)
DEMONSTRATED = ConceptNow(
    id="activation",
    title="Activation functions",
    state=MasteryState.DEMONSTRATED,
    review_due_at=NOW + timedelta(days=5),
)
UNTOUCHED = ConceptNow(
    id="loss",
    title="Loss",
    state=MasteryState.NOT_ASSESSED,
    missing=("answered questions on this concept",),
)
COURSE = [BUILDING, DEMONSTRATED, UNTOUCHED]


# -- where a sitting begins and ends ---------------------------------------


def test_with_nothing_done_there_is_no_sitting() -> None:
    assert latest_sitting([], COURSE, NOW) is None


def test_a_sitting_is_the_latest_run_of_activity_without_a_long_pause() -> None:
    sitting = latest_sitting(
        [
            right("weights", days=3),
            wrong("weights", days=3, minutes=-10),
            # Today, with a break in the middle that is shorter than the gap.
            right("weights", minutes=70),
            right("weights", minutes=40),
            finished("weights", minutes=5),
        ],
        COURSE,
        NOW,
    )
    assert sitting is not None
    assert sitting.started_at == ago(minutes=70)
    assert sitting.ended_at == ago(minutes=5)
    assert sitting.current
    assert sitting.answered == 2
    assert sitting.lessons_completed == 1


def test_a_pause_longer_than_the_gap_starts_a_new_sitting() -> None:
    just_over = SITTING_GAP + timedelta(seconds=1)
    earlier = Activity(at=NOW - just_over - timedelta(minutes=1), concept_id="weights")
    later = Activity(at=NOW - timedelta(minutes=1), concept_id="activation", answered=True)
    sitting = latest_sitting([earlier, later], COURSE, NOW)
    assert sitting is not None
    assert sitting.started_at == later.at
    # Only what was worked on in this sitting has a line.
    assert [line.title for line in sitting.still_needed] == []
    assert sitting.answered == 1


def test_a_pause_of_exactly_the_gap_does_not() -> None:
    first = Activity(at=NOW - SITTING_GAP - timedelta(minutes=1), concept_id="weights")
    second = Activity(at=NOW - timedelta(minutes=1), concept_id="weights")
    sitting = latest_sitting([second, first], COURSE, NOW)
    assert sitting is not None
    assert sitting.started_at == first.at


def test_a_sitting_the_learner_has_left_is_last_time_not_this_session() -> None:
    sitting = latest_sitting([right("weights", days=2)], COURSE, NOW)
    assert sitting is not None
    assert not sitting.current
    assert sitting.ended_at == ago(days=2)

    still_there = latest_sitting([right("weights", minutes=44)], COURSE, NOW)
    assert still_there is not None
    assert still_there.current


def test_activity_dated_after_now_is_ignored() -> None:
    """The clock was changed. A sitting that ends in the future would never end."""
    sitting = latest_sitting(
        [right("weights", minutes=10), right("activation", days=-1)], COURSE, NOW
    )
    assert sitting is not None
    assert sitting.ended_at == ago(minutes=10)
    assert [line.concept_id for line in sitting.shown] == ["weights"]
    assert latest_sitting([right("weights", days=-1)], COURSE, NOW) is None


# -- what it showed ----------------------------------------------------------


def test_what_was_shown_is_counted_in_right_answers_and_how_many_count_in_full() -> None:
    sitting = latest_sitting(
        [
            right("weights", minutes=30),
            wrong("weights", minutes=25),
            right("weights", minutes=20),
            lighter("weights", minutes=18),
            skipped("weights", minutes=15),
            right("activation", minutes=10),
        ],
        COURSE,
        NOW,
    )
    assert sitting is not None
    assert sitting.answered == 5
    assert sitting.shown == (
        Shown(
            concept_id="weights",
            title="Weights and bias",
            right=3,
            right_unaided=2,
            demonstrated=False,
        ),
        Shown(
            concept_id="activation",
            title="Activation functions",
            right=1,
            right_unaided=1,
            demonstrated=True,
        ),
    )


def test_a_right_answer_that_is_lighter_evidence_still_shows_something() -> None:
    sitting = latest_sitting([lighter("weights", minutes=5)], COURSE, NOW)
    assert sitting is not None
    assert [(line.right, line.right_unaided) for line in sitting.shown] == [(1, 0)]


def test_one_sitting_never_makes_a_concept_demonstrated_by_itself() -> None:
    """ "Demonstrated" is the state the usual criteria give, whatever happened today."""
    many = [right("weights", minutes=minute) for minute in range(1, 12)]
    sitting = latest_sitting(many, COURSE, NOW)
    assert sitting is not None
    assert sitting.shown[0].right == 11
    assert sitting.shown[0].right_unaided == 11
    assert not sitting.shown[0].demonstrated
    assert [line.concept_id for line in sitting.still_needed] == ["weights"]


def test_what_still_needs_evidence_says_what_is_missing() -> None:
    sitting = latest_sitting(
        [wrong("weights", minutes=10), right("activation", minutes=5)], COURSE, NOW
    )
    assert sitting is not None
    # Worked on and not demonstrated: listed, with the words used everywhere else.
    assert sitting.still_needed == (
        StillNeeded(
            concept_id="weights",
            title="Weights and bias",
            state=MasteryState.BUILDING,
            missing=("2 more correct answers without a hint",),
        ),
    )
    # A wrong answer shows nothing, and is not held against the learner anywhere here.
    assert [line.concept_id for line in sitting.shown] == ["activation"]


def test_a_lesson_finished_with_every_question_skipped_shows_nothing_and_needs_answers() -> None:
    concept = ConceptNow(
        id="loss",
        title="Loss",
        state=MasteryState.NOT_ASSESSED,
        missing=("answered questions on this concept",),
    )
    sitting = latest_sitting(
        [skipped("loss", minutes=9), skipped("loss", minutes=8), finished("loss", minutes=7)],
        [concept],
        NOW,
    )
    assert sitting is not None
    assert (sitting.answered, sitting.lessons_completed) == (0, 1)
    assert sitting.shown == ()
    assert [line.missing for line in sitting.still_needed] == [
        ("answered questions on this concept",)
    ]
    assert sitting.reviews == ()


def test_reviews_planned_for_what_was_worked_on_are_listed_soonest_first() -> None:
    sitting = latest_sitting(
        [right("weights", minutes=10), right("activation", minutes=5)],
        [DEMONSTRATED, BUILDING, UNTOUCHED],
        NOW,
    )
    assert sitting is not None
    assert sitting.reviews == (
        PlannedReview(
            concept_id="weights", title="Weights and bias", due_at=NOW + timedelta(days=2)
        ),
        PlannedReview(
            concept_id="activation",
            title="Activation functions",
            due_at=NOW + timedelta(days=5),
        ),
    )


def test_lines_follow_the_learning_order_they_are_given_in() -> None:
    activities = [right("activation", minutes=10), right("weights", minutes=5)]
    forwards = latest_sitting(activities, [BUILDING, DEMONSTRATED], NOW)
    backwards = latest_sitting(activities, [DEMONSTRATED, BUILDING], NOW)
    assert forwards is not None
    assert backwards is not None
    assert [line.concept_id for line in forwards.shown] == ["weights", "activation"]
    assert [line.concept_id for line in backwards.shown] == ["activation", "weights"]


def test_work_on_a_concept_that_was_removed_counts_but_has_no_line() -> None:
    sitting = latest_sitting(
        [right("removed", minutes=10), right("weights", minutes=5)], COURSE, NOW
    )
    assert sitting is not None
    assert sitting.answered == 2
    assert [line.concept_id for line in sitting.shown] == ["weights"]


def test_only_an_answer_can_be_right_and_only_a_right_one_can_count_in_full() -> None:
    with pytest.raises(ValueError, match="Only an answer"):
        Activity(at=NOW, concept_id="weights", right=True)
    with pytest.raises(ValueError, match="An unaided right answer"):
        Activity(at=NOW, concept_id="weights", answered=True, right_unaided=True)


# -- whatever the record looks like -------------------------------------------

_CONCEPT_IDS = ["a", "b", "c", "d"]


@st.composite
def _activities(draw: st.DrawFn) -> list[Activity]:
    count = draw(st.integers(min_value=0, max_value=25))
    made: list[Activity] = []
    for _ in range(count):
        answered = draw(st.booleans())
        was_right = answered and draw(st.booleans())
        made.append(
            Activity(
                at=NOW - timedelta(minutes=draw(st.integers(min_value=-120, max_value=6000))),
                concept_id=draw(st.sampled_from([*_CONCEPT_IDS, "removed"])),
                answered=answered,
                right=was_right,
                right_unaided=was_right and draw(st.booleans()),
                lesson_completed=draw(st.booleans()),
            )
        )
    return made


@st.composite
def _concepts(draw: st.DrawFn) -> list[ConceptNow]:
    made: list[ConceptNow] = []
    for concept_id in draw(st.permutations(_CONCEPT_IDS)):
        state = draw(st.sampled_from(list(MasteryState)))
        due = draw(st.one_of(st.none(), st.integers(min_value=-3, max_value=30)))
        made.append(
            ConceptNow(
                id=concept_id,
                title=f"Concept {concept_id}",
                state=state,
                missing=() if state is MasteryState.DEMONSTRATED else ("something more",),
                review_due_at=None if due is None else NOW + timedelta(days=due),
            )
        )
    return made


@given(_activities(), _concepts())
def test_a_sitting_is_consistent_whatever_the_record(
    activities: list[Activity], concepts: list[ConceptNow]
) -> None:
    sitting = latest_sitting(activities, concepts, NOW)
    past = [item for item in activities if item.at <= NOW]
    if not past:
        assert sitting is None
        return
    assert sitting is not None

    # It ends with the last thing done, and never in the future.
    assert sitting.ended_at == max(item.at for item in past)
    assert sitting.started_at <= sitting.ended_at <= NOW
    assert sitting.current == (NOW - sitting.ended_at <= SITTING_GAP)

    during = [item for item in past if item.at >= sitting.started_at]
    before = [item for item in past if item.at < sitting.started_at]
    # No long pause inside it, and a long pause before it.
    times = sorted(item.at for item in during)
    assert all(later - earlier <= SITTING_GAP for earlier, later in itertools.pairwise(times))
    if before:
        assert sitting.started_at - max(item.at for item in before) > SITTING_GAP

    # Totals are counts of what was done in it, nothing else.
    assert sitting.answered == sum(1 for item in during if item.answered)
    assert sitting.lessons_completed == sum(1 for item in during if item.lesson_completed)

    known = {concept.id: concept for concept in concepts}
    touched = {item.concept_id for item in during} & set(known)
    order = [concept.id for concept in concepts]

    # Something shown is something answered right in this sitting, counted exactly.
    for line in sitting.shown:
        assert line.concept_id in touched
        mine = [item for item in during if item.concept_id == line.concept_id]
        assert line.right == sum(1 for item in mine if item.right)
        assert line.right_unaided == sum(1 for item in mine if item.right_unaided)
        assert line.right >= 1
        assert 0 <= line.right_unaided <= line.right
        assert line.demonstrated == (known[line.concept_id].state is MasteryState.DEMONSTRATED)

    # Every concept worked on is either demonstrated or says what is missing; never both.
    needing = {line.concept_id for line in sitting.still_needed}
    assert needing == {
        concept_id
        for concept_id in touched
        if known[concept_id].state is not MasteryState.DEMONSTRATED
    }
    assert all(line.missing for line in sitting.still_needed)

    # Reviews are those of the concepts worked on, soonest first.
    assert {line.concept_id for line in sitting.reviews} == {
        concept_id for concept_id in touched if known[concept_id].review_due_at is not None
    }
    dues = [line.due_at for line in sitting.reviews]
    assert dues == sorted(dues)

    # Lines keep the order the concepts were given in.
    for lines in (sitting.shown, sitting.still_needed):
        positions = [order.index(line.concept_id) for line in lines]
        assert positions == sorted(positions)
