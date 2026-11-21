"""Which questions to ask, and what to suggest next, with the reason for each."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.mastery import MasteryState
from adle_core.learner_model.misconceptions import Answer, fold
from adle_core.learner_model.next_step import (
    MAX_ALTERNATIVES,
    MAX_LESSONS_PER_CONCEPT,
    PAUSE_NOTE,
    ConceptStatus,
    LessonStatus,
    PracticePurpose,
    StepKind,
    plan,
    practice_purpose,
)
from adle_core.learner_model.practice import (
    FRESH_AGAIN_AFTER,
    Need,
    PoolItem,
    choose,
    next_fresh_at,
)

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
AGO = lambda **span: NOW - timedelta(**span)  # noqa: E731

# -- choosing questions -------------------------------------------------------------


def item(question: str, form: str = "multiple_choice", **extra: object) -> PoolItem:
    return PoolItem(lesson_id="les_1", question_id=question, form=form, **extra)  # type: ignore[arg-type]


def ids(items: list[PoolItem]) -> list[str]:
    return [chosen.question_id for chosen in items]


def test_with_no_questions_there_is_nothing_to_ask() -> None:
    assert choose([], Need(), NOW) == []


def test_a_question_that_would_show_a_suspected_mistake_comes_first() -> None:
    pool = [
        item("q_plain"),
        item("q_reveals", reveals=frozenset({"causal_confusion"})),
        item("q_transfer", is_transfer=True),
    ]
    chosen = choose(pool, Need(to_check=("causal_confusion",)), NOW)
    assert ids(chosen)[0] == "q_reveals"


def test_the_first_thing_to_check_outweighs_the_second() -> None:
    pool = [
        item("q_second", reveals=frozenset({"definition_confusion"})),
        item("q_first", reveals=frozenset({"causal_confusion"})),
    ]
    need = Need(to_check=("causal_confusion", "definition_confusion"))
    assert ids(choose(pool, need, NOW)) == ["q_first", "q_second"]


def test_a_new_situation_is_asked_about_until_one_has_been_answered() -> None:
    pool = [item("q_plain"), item("q_transfer", is_transfer=True)]
    assert ids(choose(pool, Need(), NOW))[0] == "q_transfer"
    # Once one has been answered correctly, it no longer jumps the queue.
    seen = [item("q_plain"), item("q_transfer", is_transfer=True, last_answered_at=AGO(days=1))]
    assert ids(choose(seen, Need(transfer_correct=1), NOW))[0] == "q_plain"


def test_a_kind_of_question_not_yet_answered_correctly_is_preferred() -> None:
    pool = [item("q_choice"), item("q_number", form="numeric")]
    need = Need(forms_correct=frozenset({"multiple_choice"}))
    assert ids(choose(pool, need, NOW))[0] == "q_number"


def test_variety_counts_when_all_else_is_equal() -> None:
    pool = [item("q_a"), item("q_b"), item("q_c", form="numeric"), item("q_d", form="true_false")]
    forms = [chosen.form for chosen in choose(pool, Need(), NOW, count=3)]
    assert len(set(forms)) == 3


def test_a_question_answered_in_the_last_hours_is_kept_back() -> None:
    pool = [
        item("q_recent", last_answered_at=AGO(hours=2), last_outcome=Outcome.INCORRECT),
        item("q_old", last_answered_at=AGO(days=3), last_outcome=Outcome.CORRECT),
    ]
    assert ids(choose(pool, Need(), NOW)) == ["q_old"]
    assert next_fresh_at(pool, NOW) == AGO(hours=2) + FRESH_AGAIN_AFTER
    # Everything recent: nothing is asked rather than asking for an echo.
    assert choose(pool[:1], Need(), NOW) == []
    assert next_fresh_at([item("q_never")], NOW) is None


def test_the_longest_unseen_and_the_once_missed_come_before_the_recently_right() -> None:
    pool = [
        item("q_right_yesterday", last_answered_at=AGO(days=1), last_outcome=Outcome.CORRECT),
        item("q_right_last_month", last_answered_at=AGO(days=30), last_outcome=Outcome.CORRECT),
        item("q_missed_yesterday", last_answered_at=AGO(days=1), last_outcome=Outcome.INCORRECT),
    ]
    need = Need(forms_correct=frozenset({"multiple_choice"}), transfer_correct=1)
    assert ids(choose(pool, need, NOW)) == [
        "q_right_last_month",
        "q_missed_yesterday",
        "q_right_yesterday",
    ]


def test_the_choice_does_not_depend_on_the_order_the_pool_is_given_in() -> None:
    pool = [item(f"q_{n}", form=form) for n, form in enumerate(["numeric", "true_false"] * 3)]
    assert ids(choose(pool, Need(), NOW)) == ids(choose(list(reversed(pool)), Need(), NOW))


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["multiple_choice", "numeric", "true_false", "ordering"]),
            st.booleans(),
            st.one_of(st.none(), st.integers(min_value=0, max_value=24 * 40)),
        ),
        max_size=12,
    ),
    st.integers(min_value=1, max_value=5),
)
def test_a_choice_is_always_fresh_distinct_and_within_the_count(
    pool_spec: list[tuple[str, bool, int | None]], count: int
) -> None:
    pool = [
        item(
            f"q_{index}",
            form=form,
            is_transfer=transfer,
            last_answered_at=None if hours is None else AGO(hours=hours),
        )
        for index, (form, transfer, hours) in enumerate(pool_spec)
    ]
    chosen = choose(pool, Need(), NOW, count=count)
    assert len(chosen) <= count
    assert len(set(ids(chosen))) == len(chosen)
    assert all(picked.is_fresh(NOW) for picked in chosen)
    fresh = [candidate for candidate in pool if candidate.is_fresh(NOW)]
    assert len(chosen) == min(count, len(fresh))


# -- the next step ----------------------------------------------------------------------


def lesson(
    key: str, *, started: bool = False, completed: bool = False, **extra: object
) -> LessonStatus:
    return LessonStatus(
        id=f"les_{key}",
        title=f"Lesson on {key}",
        started=started or completed,
        completed=completed,
        **extra,  # type: ignore[arg-type]
    )


def concept(key: str, *needs: str, **extra: object) -> ConceptStatus:
    return ConceptStatus(id=key, title=key.capitalize(), prerequisites=needs, **extra)  # type: ignore[arg-type]


WRONG = Outcome.INCORRECT
RIGHT = Outcome.CORRECT


def test_an_empty_course_asks_for_concepts() -> None:
    step = plan([], NOW, can_generate=True).recommended
    assert step.kind is StepKind.ADD_CONCEPTS
    assert "no concepts yet" in step.reason


def test_a_fresh_course_starts_with_its_first_lesson_and_says_why() -> None:
    order = [
        concept("weights", lessons=(lesson("weights"),)),
        concept("activation", "weights", lessons=(lesson("activation"),)),
    ]
    result = plan(order, NOW, can_generate=False)
    step = result.recommended
    assert (step.kind, step.concept_id, step.lesson_id) == (
        StepKind.START_LESSON,
        "weights",
        "les_weights",
    )
    assert step.reason == "“Weights” is next in your course. It has no prerequisites."
    # What builds on something not yet met is not offered, even as an alternative.
    assert all(other.concept_id != "activation" for other in result.alternatives)


def test_what_was_started_is_finished_first() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
        ),
        concept(
            "activation",
            "weights",
            lessons=(lesson("activation", started=True, touched_at=AGO(days=2)),),
        ),
        concept("loss", lessons=(lesson("loss", started=True, touched_at=AGO(hours=1)),)),
    ]
    result = plan(order, NOW, can_generate=True)
    assert (result.recommended.kind, result.recommended.lesson_id) == (
        StepKind.RESUME_LESSON,
        "les_loss",
    )
    assert result.recommended.reason == "You stopped partway through this lesson."
    # The other unfinished lesson is the first alternative.
    assert result.alternatives[0].lesson_id == "les_activation"


def test_after_a_lesson_the_next_concept_is_suggested_and_names_what_it_builds_on() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            missing=("2 more correct answers without a hint",),
        ),
        concept("activation", "weights", lessons=(lesson("activation"),)),
    ]
    result = plan(order, NOW, can_generate=True)
    assert (result.recommended.kind, result.recommended.concept_id) == (
        StepKind.START_LESSON,
        "activation",
    )
    assert "It builds on “Weights”, which you’ve covered." in result.recommended.reason
    # Going through the finished lesson again is on offer, but never pushed.
    assert [other.kind for other in result.alternatives] == [StepKind.REPEAT_LESSON]


def test_practice_is_offered_beside_moving_on_when_there_is_something_fresh_to_ask() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=2,
            fresh_questions=2,
            missing=(
                "2 more correct answers without a hint",
                "a correct answer in a new situation",
            ),
        ),
        concept("activation", "weights", lessons=(lesson("activation"),)),
    ]
    result = plan(order, NOW, can_generate=True)
    assert result.recommended.kind is StepKind.START_LESSON
    practise = result.alternatives[0]
    assert (practise.kind, practise.concept_id) == (StepKind.PRACTISE, "weights")
    assert practise.reason == (
        "“Weights” is at “Learning”. Still needed: 2 more correct answers "
        "without a hint; a correct answer in a new situation."
    )


def test_a_review_that_is_due_comes_before_new_material() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            fresh_questions=3,
            review_due_at=AGO(days=2),
        ),
        concept("activation", "weights", lessons=(lesson("activation"),)),
    ]
    result = plan(order, NOW, can_generate=True)
    step = result.recommended
    assert (step.kind, step.concept_id) == (StepKind.REVIEW, "weights")
    assert step.reason.startswith("A review of “Weights” was due 2 days ago.")
    assert "after a gap" in step.reason
    assert StepKind.START_LESSON in [other.kind for other in result.alternatives]


def test_a_review_is_not_suggested_before_it_is_due_or_when_nothing_fresh_can_be_asked() -> None:
    upcoming = concept(
        "weights",
        lessons=(lesson("weights", completed=True),),
        state=MasteryState.BUILDING,
        answered=3,
        fresh_questions=3,
        review_due_at=NOW + timedelta(days=1),
    )
    assert plan([upcoming], NOW, can_generate=True).recommended.kind is not StepKind.REVIEW
    stale = concept(
        "weights",
        lessons=(lesson("weights", completed=True),),
        state=MasteryState.BUILDING,
        answered=3,
        fresh_questions=0,
        review_due_at=AGO(hours=1),
    )
    assert plan([stale], NOW, can_generate=True).recommended.kind is not StepKind.REVIEW


def test_the_longest_overdue_review_is_first() -> None:
    def due(key: str, days: int) -> ConceptStatus:
        return concept(
            key,
            lessons=(lesson(key, completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            fresh_questions=3,
            review_due_at=AGO(days=days),
        )

    result = plan([due("a", 1), due("b", 9), due("c", 3)], NOW, can_generate=True)
    assert result.recommended.concept_id == "b"
    assert [other.concept_id for other in result.alternatives[:2]] == ["c", "a"]


def test_a_suspicion_gets_a_question_not_a_verdict() -> None:
    suspicion = fold([Answer(AGO(days=1), "q_1", WRONG, suggests="causal_confusion")]).values()
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            fresh_questions=2,
            checkable=frozenset({"causal_confusion"}),
            hypotheses=tuple(suspicion),
        )
    ]
    step = plan(order, NOW, can_generate=True).recommended
    assert (step.kind, step.about) == (StepKind.CHECK, "causal_confusion")
    assert "will check" in step.reason
    # Without a question that could show it, nothing is claimed.
    uncheckable = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            hypotheses=tuple(suspicion),
        )
    ]
    assert plan(uncheckable, NOW, can_generate=True).recommended.kind is not StepKind.CHECK


def test_a_supported_gap_in_what_it_builds_on_sends_the_learner_back_there() -> None:
    gap = fold(
        [
            Answer(AGO(days=2), "q_1", WRONG, suggests="prerequisite_gap"),
            Answer(AGO(days=1), "q_2", WRONG, suggests="prerequisite_gap"),
        ]
    ).values()
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=2,
        ),
        concept(
            "activation",
            "weights",
            lessons=(lesson("activation", completed=True),),
            state=MasteryState.BUILDING,
            answered=4,
            hypotheses=tuple(gap),
        ),
    ]
    step = plan(order, NOW, can_generate=True).recommended
    assert (step.kind, step.concept_id, step.lesson_id) == (
        StepKind.REVISIT_PREREQUISITE,
        "weights",
        "les_weights",
    )
    assert "suggests that something this builds on may be missing" in step.reason
    assert "“Activation” builds on “Weights”, which isn’t solid yet." in step.reason


def test_a_run_of_misses_never_leads_back_into_the_same_lesson() -> None:
    struggling: dict[str, object] = {
        "lessons": (lesson("activation", completed=True),),
        "state": MasteryState.BUILDING,
        "answered": 5,
        "fresh_questions": 0,
        "recent": (RIGHT, WRONG, WRONG, RIGHT, WRONG, WRONG, WRONG),
    }
    # With something it builds on that is not solid: look there first.
    with_weak_base = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=2,
        ),
        concept("activation", "weights", **struggling),
    ]
    step = plan(with_weak_base, NOW, can_generate=True).recommended
    assert (step.kind, step.concept_id) == (StepKind.REVISIT_PREREQUISITE, "weights")
    assert "Your last few answers on “Activation” didn’t go well." in step.reason

    # With a solid base: a different explanation, not more of the same.
    with_solid_base = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.DEMONSTRATED,
            answered=5,
        ),
        concept("activation", "weights", **struggling),
    ]
    result = plan(with_solid_base, NOW, can_generate=True)
    assert (result.recommended.kind, result.recommended.concept_id) == (
        StepKind.ANOTHER_EXPLANATION,
        "activation",
    )
    assert "than repeating the same lesson" in result.recommended.reason
    every = [result.recommended, *result.alternatives]
    assert all(
        not (offered.kind is StepKind.REPEAT_LESSON and offered.concept_id == "activation")
        for offered in every
    )


def test_when_things_go_badly_the_suggestion_says_that_stopping_is_fine() -> None:
    order = [
        concept("weights", lessons=(lesson("weights", completed=True),), answered=5),
        concept(
            "activation",
            "weights",
            lessons=(lesson("activation", completed=True),),
            state=MasteryState.BUILDING,
            answered=4,
            recent=(WRONG, WRONG, WRONG, WRONG),
        ),
    ]
    result = plan(order, NOW, can_generate=True)
    assert result.recommended.kind is StepKind.REVISIT_PREREQUISITE
    assert result.note == PAUSE_NOTE
    # An ordinary suggestion carries no such note.
    calm = [concept("weights", lessons=(lesson("weights"),))]
    assert plan(calm, NOW, can_generate=True).note is None


def test_saying_an_explanation_did_not_help_leads_to_a_different_one() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", started=True, touched_at=AGO(minutes=5)),),
            asked_for_another=True,
        )
    ]
    result = plan(order, NOW, can_generate=True)
    step = result.recommended
    assert (step.kind, step.concept_id) == (StepKind.ANOTHER_EXPLANATION, "weights")
    assert step.reason.startswith("You said an explanation of “Weights” didn’t help.")
    assert result.note == PAUSE_NOTE
    # The lesson they were in is still there to continue, but it is not pressed on them.
    assert [other.kind for other in result.alternatives] == [StepKind.RESUME_LESSON]

    # Without a key the request is still answered first; it says what it needs.
    without_key = plan(order, NOW, can_generate=False)
    assert without_key.recommended.kind is StepKind.ANOTHER_EXPLANATION
    assert without_key.recommended.needs_key


def test_an_explanation_already_there_and_not_yet_tried_is_offered_before_a_new_one() -> None:
    order = [
        concept(
            "weights",
            lessons=(
                lesson("weights", completed=True),
                LessonStatus(
                    id="les_other", title="Weights, by example", started=False, completed=False
                ),
            ),
            state=MasteryState.BUILDING,
            answered=4,
            recent=(WRONG, WRONG, WRONG, WRONG),
        )
    ]
    step = plan(order, NOW, can_generate=True).recommended
    assert (step.kind, step.lesson_id) == (StepKind.START_LESSON, "les_other")
    assert step.title == "Try “Weights, by example”"
    assert "another explanation you haven’t tried" in step.reason


def test_explanations_of_one_concept_are_not_added_without_end() -> None:
    many = tuple(
        LessonStatus(id=f"les_{n}", title=f"Take {n}", started=True, completed=True)
        for n in range(MAX_LESSONS_PER_CONCEPT)
    )
    order = [
        concept(
            "weights",
            lessons=many,
            state=MasteryState.BUILDING,
            answered=8,
            fresh_questions=2,
            recent=(WRONG, WRONG, WRONG, WRONG),
            missing=("3 more correct answers without a hint",),
        )
    ]
    result = plan(order, NOW, can_generate=True)
    kinds = [result.recommended.kind, *(other.kind for other in result.alternatives)]
    assert StepKind.ANOTHER_EXPLANATION not in kinds
    assert StepKind.REPEAT_LESSON not in kinds
    # What is left is practice, offered without pressure.
    assert result.recommended.kind is StepKind.PRACTISE
    assert result.note is None


def test_an_explanation_made_since_the_learner_left_the_old_one_comes_first() -> None:
    old = LessonStatus(
        id="les_old",
        title="Weights, in pictures",
        started=True,
        completed=False,
        touched_at=AGO(hours=2),
        added_at=AGO(days=3),
    )
    new = LessonStatus(
        id="les_new",
        title="Weights, by example",
        started=False,
        completed=False,
        added_at=AGO(minutes=10),
    )
    result = plan([concept("weights", lessons=(old, new))], NOW, can_generate=True)
    step = result.recommended
    assert (step.kind, step.lesson_id, step.title) == (
        StepKind.START_LESSON,
        "les_new",
        "Try “Weights, by example”",
    )
    assert step.reason == "There’s another explanation of “Weights” you haven’t tried."
    # The old one can still be continued. It is simply no longer what is suggested.
    assert [(other.kind, other.lesson_id) for other in result.alternatives] == [
        (StepKind.RESUME_LESSON, "les_old")
    ]


def test_an_explanation_that_was_already_there_is_only_an_alternative() -> None:
    old = LessonStatus(
        id="les_old",
        title="Weights, in pictures",
        started=True,
        completed=False,
        touched_at=AGO(hours=2),
        added_at=AGO(days=3),
    )
    other = LessonStatus(
        id="les_other",
        title="Weights, by example",
        started=False,
        completed=False,
        added_at=AGO(days=3),
    )
    result = plan([concept("weights", lessons=(old, other))], NOW, can_generate=True)
    assert (result.recommended.kind, result.recommended.lesson_id) == (
        StepKind.RESUME_LESSON,
        "les_old",
    )
    assert [(step.kind, step.lesson_id) for step in result.alternatives] == [
        (StepKind.START_LESSON, "les_other")
    ]


def test_practice_is_not_suggested_for_what_practice_cannot_supply() -> None:
    standing = fold(
        [
            Answer(AGO(hours=2), "q_1", WRONG, suggests="causal_confusion"),
            Answer(AGO(hours=1), "q_2", WRONG, suggests="causal_confusion"),
        ]
    ).values()
    waiting = concept(
        "weights",
        lessons=(lesson("weights", completed=True),),
        state=MasteryState.NEEDS_EVIDENCE,
        answered=6,
        # There are questions to ask, but none of them could show the mistake.
        fresh_questions=2,
        checkable=frozenset(),
        hypotheses=tuple(standing),
        missing=("a possible misunderstanding to clear up",),
        review_due_at=NOW + timedelta(days=1),
    )
    result = plan([waiting], NOW, can_generate=True)
    assert result.recommended.kind is StepKind.NOTHING_DUE
    assert "needs time to settle" in result.recommended.reason
    purpose, reason = practice_purpose(waiting, NOW)
    assert purpose is PracticePurpose.PRACTISE
    assert "can be asked again later. This is extra practice in the meantime" in reason

    # When something else is missing too, practice is offered for that, and only that.
    more = concept(
        "weights",
        lessons=(lesson("weights", completed=True),),
        state=MasteryState.NEEDS_EVIDENCE,
        answered=6,
        fresh_questions=2,
        hypotheses=tuple(standing),
        missing=(
            "a correct answer to another kind of question",
            "a possible misunderstanding to clear up",
        ),
    )
    step = plan([more], NOW, can_generate=True).recommended
    assert step.kind is StepKind.PRACTISE
    assert step.reason.endswith("Still needed: a correct answer to another kind of question.")

    # And once a question that would show it can be asked, the check is the suggestion.
    checkable = concept(
        "weights",
        lessons=(lesson("weights", completed=True),),
        state=MasteryState.NEEDS_EVIDENCE,
        answered=6,
        fresh_questions=2,
        checkable=frozenset({"causal_confusion"}),
        hypotheses=tuple(standing),
        missing=("a possible misunderstanding to clear up",),
    )
    assert plan([checkable], NOW, can_generate=True).recommended.kind is StepKind.CHECK


def test_three_misses_out_of_four_is_a_run_two_is_not() -> None:
    assert concept("a", recent=(WRONG, WRONG, RIGHT, WRONG)).struggling
    assert not concept("a", recent=(WRONG, RIGHT, RIGHT, WRONG)).struggling
    # Too few answers to call it anything.
    assert not concept("a", recent=(WRONG, WRONG, WRONG)).struggling
    # Old misses are forgotten once the recent answers are right.
    assert not concept("a", recent=(WRONG, WRONG, WRONG, WRONG, RIGHT, RIGHT, RIGHT)).struggling


def test_a_concept_without_a_lesson_asks_for_one_and_says_if_a_key_is_needed() -> None:
    order = [concept("weights")]
    with_key = plan(order, NOW, can_generate=True).recommended
    assert (with_key.kind, with_key.needs_key) == (StepKind.CREATE_LESSON, False)
    assert "has no lesson yet" in with_key.reason
    without = plan(order, NOW, can_generate=False).recommended
    assert (without.kind, without.needs_key) == (StepKind.CREATE_LESSON, True)


def test_a_step_that_needs_a_key_is_never_put_before_something_that_can_be_done() -> None:
    order = [
        concept("weights"),  # no lesson, and no key to make one
        concept("loss", lessons=(lesson("loss"),)),
    ]
    result = plan(order, NOW, can_generate=False)
    assert (result.recommended.kind, result.recommended.concept_id) == (
        StepKind.START_LESSON,
        "loss",
    )
    assert result.alternatives[0].needs_key


def test_someone_who_says_they_know_it_is_checked_rather_than_taught_again() -> None:
    order = [
        concept(
            "weights",
            lessons=(lesson("weights"),),
            claims_familiarity=True,
            fresh_questions=3,
            state=MasteryState.NEEDS_EVIDENCE,
        )
    ]
    step = plan(order, NOW, can_generate=True).recommended
    assert step.kind is StepKind.PRACTISE
    assert step.reason.startswith("You said you already know “Weights”.")
    assert "you can skip the lesson" in step.reason


def test_when_nothing_is_worth_doing_it_says_so_and_when_there_will_be() -> None:
    settling = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=3,
            fresh_questions=0,
            review_due_at=NOW + timedelta(days=1),
        )
    ]
    result = plan(settling, NOW, can_generate=True)
    assert result.recommended.kind is StepKind.NOTHING_DUE
    assert "needs time to settle" in result.recommended.reason
    assert "Next review: “Weights”, in a day." in result.recommended.reason
    assert [other.kind for other in result.alternatives] == [StepKind.REPEAT_LESSON]

    done = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.DEMONSTRATED,
            answered=6,
            review_due_at=NOW + timedelta(days=5),
        )
    ]
    finished = plan(done, NOW, can_generate=True)
    assert finished.recommended.kind is StepKind.NOTHING_DUE
    assert "You’ve covered every concept in this course for now." in finished.recommended.reason
    assert "in 5 days" in finished.recommended.reason
    assert finished.alternatives == ()


def test_no_reason_ever_contains_a_score() -> None:
    hypotheses = fold(
        [
            Answer(AGO(days=2), "q_1", WRONG, suggests="definition_confusion"),
            Answer(AGO(days=1), "q_2", WRONG, suggests="definition_confusion"),
        ]
    ).values()
    order = [
        concept(
            "weights",
            lessons=(lesson("weights", completed=True),),
            state=MasteryState.BUILDING,
            answered=4,
            fresh_questions=2,
            review_due_at=AGO(days=1),
            checkable=frozenset({"definition_confusion"}),
            hypotheses=tuple(hypotheses),
            recent=(WRONG, WRONG, WRONG, WRONG),
            missing=("2 more correct answers without a hint",),
        ),
        concept("activation", "weights", lessons=(lesson("activation", started=True),)),
        concept("loss"),
    ]
    result = plan(order, NOW, can_generate=False)
    for step in (result.recommended, *result.alternatives):
        assert "%" not in step.reason
        assert "probab" not in step.reason.lower()
        assert "score" not in step.reason.lower()
        assert step.title
        assert step.reason.endswith((".", "?"))


@given(
    st.lists(
        st.tuples(
            st.sampled_from(list(MasteryState)),
            st.sampled_from(["none", "new", "started", "completed"]),
            st.integers(min_value=0, max_value=4),
            st.one_of(st.none(), st.integers(min_value=-5, max_value=5)),
            st.lists(st.sampled_from([RIGHT, WRONG]), max_size=6),
            st.booleans(),
        ),
        max_size=7,
    ),
    st.booleans(),
)
def test_any_course_gets_one_coherent_suggestion(
    spec: list[tuple[MasteryState, str, int, int | None, list[Outcome], bool]], can_generate: bool
) -> None:
    order = []
    for index, (state, lessons, fresh, due_in, recent, claims) in enumerate(spec):
        key = f"c{index}"
        order.append(
            ConceptStatus(
                id=key,
                title=key,
                prerequisites=(f"c{index - 1}",) if index and index % 2 else (),
                state=state,
                answered=len(recent),
                claims_familiarity=claims,
                review_due_at=None if due_in is None else NOW + timedelta(days=due_in),
                lessons=()
                if lessons == "none"
                else (lesson(key, started=lessons != "new", completed=lessons == "completed"),),
                fresh_questions=fresh,
                recent=tuple(recent),
            )
        )
    result = plan(order, NOW, can_generate=can_generate)
    steps = [result.recommended, *result.alternatives]
    assert len(result.alternatives) <= MAX_ALTERNATIVES
    # Nothing is offered twice.
    assert len({step.identity for step in steps}) == len(steps)
    known = {status.id for status in order}
    for step in steps:
        assert step.reason
        assert step.concept_id is None or step.concept_id in known
        if step.kind in (StepKind.START_LESSON, StepKind.RESUME_LESSON, StepKind.REPEAT_LESSON):
            assert step.lesson_id is not None
        # A key is only ever needed for something the provider would do.
        if step.needs_key:
            assert step.kind in (StepKind.CREATE_LESSON, StepKind.ANOTHER_EXPLANATION)
            assert not can_generate
    # Something that can be done is never placed behind something that cannot.
    if result.recommended.needs_key:
        assert all(
            other.needs_key or other.kind in (StepKind.REPEAT_LESSON, StepKind.RESUME_LESSON)
            for other in result.alternatives
        )
