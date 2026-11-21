"""Knowledge tracing: the estimate, the states a learner sees, and the reasons given."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.learner_model.bkt import (
    CEILING,
    FLOOR,
    BktParameters,
    Outcome,
    effective_guess,
    evidence_step,
    update,
)
from adle_core.learner_model.mastery import (
    Evidence,
    MasteryCriteria,
    MasteryState,
    assess,
)
from adle_core.learner_model.tracing import (
    DEFAULT_CONFIG,
    QUESTION_FORM_LABELS,
    ConceptKnowledge,
    Observation,
    ObservationKind,
    SelfReport,
    apply,
    initial_knowledge,
    replay,
)

START = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
PARAMETERS = BktParameters()
probabilities = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
scored = st.sampled_from([Outcome.CORRECT, Outcome.PARTIAL, Outcome.INCORRECT])


def answer(
    outcome: Outcome = Outcome.CORRECT,
    form: str = "multiple_choice",
    *,
    minutes: int = 0,
    transfer: bool = False,
    hinted: bool = False,
    unsure: bool = False,
    item_guess: float | None = None,
) -> Observation:
    return Observation(
        kind=ObservationKind.ANSWER,
        occurred_at=START + timedelta(minutes=minutes),
        outcome=outcome,
        question_form=None if outcome is Outcome.SKIPPED else form,
        is_transfer=transfer,
        hinted=hinted,
        unsure=unsure,
        item_guess=item_guess,
    )


def self_report(level: SelfReport, *, minutes: int = 0) -> Observation:
    return Observation(
        kind=ObservationKind.SELF_REPORT,
        occurred_at=START + timedelta(minutes=minutes),
        self_report=level,
    )


def run(observations: list[Observation]) -> tuple[ConceptKnowledge, list[MasteryState], list[str]]:
    knowledge = initial_knowledge()
    states: list[MasteryState] = []
    explanations: list[str] = []
    for observation in observations:
        transition = apply(knowledge, observation)
        knowledge = transition.after
        states.append(transition.state_after)
        explanations.append(transition.explanation)
    return knowledge, states, explanations


# -- the estimate ----------------------------------------------------------


def test_the_update_matches_the_textbook_formula() -> None:
    # P(L) = 0.2, guess 0.2, slip 0.1, learn 0.15, correct answer:
    #   evidence: 0.2 * 0.9 / (0.2 * 0.9 + 0.8 * 0.2) = 0.18 / 0.34
    #   learning: p + (1 - p) * 0.15
    after_evidence = 0.18 / 0.34
    assert evidence_step(0.2, Outcome.CORRECT, guess=0.2, slip=0.1) == pytest.approx(after_evidence)
    assert update(0.2, Outcome.CORRECT, PARAMETERS) == pytest.approx(
        after_evidence + (1 - after_evidence) * 0.15
    )
    # Incorrect answer: 0.2 * 0.1 / (0.2 * 0.1 + 0.8 * 0.8) = 0.02 / 0.66
    wrong = 0.02 / 0.66
    assert update(0.2, Outcome.INCORRECT, PARAMETERS) == pytest.approx(wrong + (1 - wrong) * 0.15)


@given(probabilities, scored, st.booleans(), st.booleans())
def test_the_estimate_always_stays_a_usable_probability(
    probability: float, outcome: Outcome, hinted: bool, unsure: bool
) -> None:
    updated = update(probability, outcome, PARAMETERS, hinted=hinted, unsure=unsure)
    assert FLOOR <= updated <= CEILING


@given(probabilities)
def test_a_better_answer_never_gives_a_lower_estimate(probability: float) -> None:
    correct = update(probability, Outcome.CORRECT, PARAMETERS)
    partial = update(probability, Outcome.PARTIAL, PARAMETERS)
    incorrect = update(probability, Outcome.INCORRECT, PARAMETERS)
    assert correct >= partial >= incorrect


@given(st.floats(min_value=FLOOR, max_value=CEILING))
def test_evidence_moves_the_estimate_in_the_direction_of_the_answer(probability: float) -> None:
    up = evidence_step(probability, Outcome.CORRECT, guess=PARAMETERS.guess, slip=PARAMETERS.slip)
    down = evidence_step(
        probability, Outcome.INCORRECT, guess=PARAMETERS.guess, slip=PARAMETERS.slip
    )
    assert down <= probability <= up


@given(probabilities)
def test_help_and_doubt_make_a_correct_answer_count_for_less(probability: float) -> None:
    plain = update(probability, Outcome.CORRECT, PARAMETERS)
    assert update(probability, Outcome.CORRECT, PARAMETERS, hinted=True) <= plain
    assert update(probability, Outcome.CORRECT, PARAMETERS, unsure=True) <= plain


@given(probabilities)
def test_skipping_is_not_evidence(probability: float) -> None:
    assert update(probability, Outcome.SKIPPED, PARAMETERS) == pytest.approx(
        min(CEILING, max(FLOOR, probability))
    )


def test_an_easily_guessed_question_is_weaker_evidence() -> None:
    hard_to_guess = update(0.3, Outcome.CORRECT, PARAMETERS, item_guess=0.05)
    coin_flip = update(0.3, Outcome.CORRECT, PARAMETERS, item_guess=0.5)
    assert hard_to_guess > coin_flip
    # A hint can only raise the guess value, never lower it.
    assert effective_guess(PARAMETERS, item_guess=0.7, hinted=True) == pytest.approx(0.7)
    assert effective_guess(PARAMETERS, item_guess=0.05, hinted=True) == PARAMETERS.hinted_guess


def test_certainty_never_locks_the_estimate() -> None:
    from_zero = update(0.0, Outcome.CORRECT, PARAMETERS)
    from_one = update(1.0, Outcome.INCORRECT, PARAMETERS)
    assert from_zero > FLOOR
    assert from_one < CEILING


def test_repeated_success_raises_the_estimate_steadily() -> None:
    probability = PARAMETERS.prior
    seen = [probability]
    for _ in range(8):
        probability = update(probability, Outcome.CORRECT, PARAMETERS)
        seen.append(probability)
    assert seen == sorted(seen)
    assert seen[-1] > 0.95


@pytest.mark.parametrize(
    "changes",
    [
        {"prior": 0.0},
        {"learn": 1.0},
        {"guess": -0.1},
        {"slip": 1.2},
        {"guess": 0.6, "slip": 0.4},
        {"hinted_guess": 0.95, "slip": 0.1},
    ],
)
def test_parameters_that_would_break_the_model_are_refused(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"must|guess"):
        BktParameters(**changes)


# -- the states a learner sees ---------------------------------------------


def test_nothing_answered_is_not_assessed() -> None:
    assessment = assess(Evidence(probability=0.2))
    assert assessment.state is MasteryState.NOT_ASSESSED
    assert assessment.label == "Not started"
    assert assessment.missing


def test_one_lucky_answer_is_never_mastery() -> None:
    knowledge, states, _ = run([answer(item_guess=0.01)])
    assert knowledge.probability > 0.85  # the estimate alone would look convincing
    assert states == [MasteryState.NEEDS_EVIDENCE]


@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.integers(min_value=0, max_value=2),
    st.integers(min_value=1, max_value=50),
    st.frozensets(st.sampled_from(sorted(QUESTION_FORM_LABELS)), max_size=7),
    st.integers(min_value=0, max_value=5),
)
def test_fewer_than_three_unaided_correct_answers_is_never_demonstrated(
    probability: float, unaided: int, answered: int, forms: frozenset[str], transfer: int
) -> None:
    evidence = Evidence(
        probability=probability,
        answered=max(answered, unaided),
        unaided_correct=unaided,
        forms_correct=forms,
        transfer_correct=transfer,
    )
    assert assess(evidence).state is not MasteryState.DEMONSTRATED


def test_demonstrated_needs_several_answers_across_forms_including_transfer() -> None:
    _, states, explanations = run(
        [
            answer(form="multiple_choice", minutes=0),
            answer(form="multiple_choice", minutes=1),
            answer(form="multiple_choice", minutes=2),
            answer(form="numeric", minutes=3),
            answer(form="prediction", transfer=True, minutes=4),
        ]
    )
    assert states == [
        MasteryState.BUILDING,
        MasteryState.NEEDS_EVIDENCE,
        MasteryState.NEEDS_EVIDENCE,
        MasteryState.NEEDS_EVIDENCE,
        MasteryState.DEMONSTRATED,
    ]
    # Three right answers of one kind still name what is missing.
    assert "a correct answer to another kind of question" in explanations[2]
    assert "in a new situation" in explanations[3]
    assert "Now: Understood." in explanations[4]


def test_hinted_and_unsure_answers_do_not_count_towards_the_criteria() -> None:
    knowledge, states, explanations = run(
        [
            answer(form="multiple_choice", hinted=True, minutes=0),
            answer(form="numeric", unsure=True, minutes=1),
            answer(form="prediction", transfer=True, hinted=True, minutes=2),
            answer(form="ordering", hinted=True, minutes=3),
            answer(form="short_answer", unsure=True, minutes=4),
        ]
    )
    assert knowledge.correct == 5
    assert knowledge.unaided_correct == 0
    assert knowledge.forms_correct == frozenset()
    assert knowledge.transfer_correct == 0
    assert MasteryState.DEMONSTRATED not in states
    assert "after a hint, which counts a little less" in explanations[0]
    assert "weren’t sure" in explanations[1]


def test_an_answer_the_learner_marked_themselves_is_described_as_that() -> None:
    """Such an answer is recorded as unsure, but nobody said they were unsure."""
    knowledge, _, explanations = run([answer(form="explanation", unsure=True, minutes=0)])
    assert knowledge.unaided_correct == 0
    assert explanations[0].startswith(
        "You marked your own explanation as covering the points. "
        "Self-marked answers count a little less."
    )
    assert "unsure" not in explanations[0]


def test_understanding_can_be_lost_again_and_the_reason_is_given() -> None:
    earned = [
        answer(form="multiple_choice", minutes=0),
        answer(form="numeric", minutes=1),
        answer(form="prediction", transfer=True, minutes=2),
    ]
    knowledge, states, _ = run(earned)
    assert states[-1] is MasteryState.DEMONSTRATED

    slipped = apply(knowledge, answer(Outcome.INCORRECT, form="numeric", minutes=3))
    slipped_again = apply(slipped.after, answer(Outcome.INCORRECT, form="numeric", minutes=4))
    assert slipped.state_before is MasteryState.DEMONSTRATED
    assert slipped_again.state_after is not MasteryState.DEMONSTRATED
    assert "wasn’t right" in slipped_again.explanation
    assert "more consistent correct answers" in slipped_again.explanation


def test_an_unresolved_misunderstanding_blocks_demonstrated() -> None:
    evidence = Evidence(
        probability=0.97,
        answered=5,
        unaided_correct=4,
        forms_correct=frozenset({"numeric", "prediction"}),
        transfer_correct=1,
        unresolved_misconception=True,
    )
    assessment = assess(evidence)
    assert assessment.state is MasteryState.NEEDS_EVIDENCE
    assert assessment.missing == ("a possible misunderstanding to clear up",)


def test_the_criteria_are_configuration() -> None:
    evidence = Evidence(
        probability=0.9, answered=2, unaided_correct=2, forms_correct=frozenset({"numeric"})
    )
    assert assess(evidence).state is MasteryState.NEEDS_EVIDENCE
    relaxed = MasteryCriteria(min_unaided_correct=2, min_question_forms=1, require_transfer=False)
    assert assess(evidence, relaxed).state is MasteryState.DEMONSTRATED
    with pytest.raises(ValueError, match="two unaided"):
        MasteryCriteria(min_unaided_correct=1)
    with pytest.raises(ValueError, match="Thresholds"):
        MasteryCriteria(promising_probability=0.9, demonstrated_probability=0.8)


# -- self-reports ----------------------------------------------------------


def test_saying_you_know_something_asks_for_evidence_rather_than_granting_it() -> None:
    knowledge, states, explanations = run([self_report(SelfReport.CONFIDENT)])
    assert states == [MasteryState.NEEDS_EVIDENCE]
    assert knowledge.answered == 0
    assert explanations[0].startswith("You said you already know this well.")
    assert "confirm what you know" in explanations[0]


@pytest.mark.parametrize("level", [SelfReport.NEW, SelfReport.SOME])
def test_other_self_reports_shift_the_starting_point_without_claiming_anything(
    level: SelfReport,
) -> None:
    knowledge, states, _ = run([self_report(level)])
    assert states == [MasteryState.NOT_ASSESSED]
    assert knowledge.self_report is level


def test_what_the_learner_did_outweighs_what_they_say() -> None:
    wrong_answers = [answer(Outcome.INCORRECT, minutes=index) for index in range(3)]
    after_answers, _, _ = run(wrong_answers)
    after_claim, states, _ = run([*wrong_answers, self_report(SelfReport.CONFIDENT, minutes=5)])
    assert after_claim.probability > after_answers.probability
    assert after_claim.probability < 0.3
    assert states[-1] is MasteryState.BUILDING


# -- explanations and the record -------------------------------------------


def test_explanations_never_contain_a_score() -> None:
    observations = [
        self_report(SelfReport.SOME),
        answer(Outcome.SKIPPED, minutes=1),
        answer(Outcome.INCORRECT, form="numeric", minutes=2),
        answer(Outcome.PARTIAL, form="explanation", minutes=3),
        answer(form="numeric", hinted=True, minutes=4),
        answer(form="multiple_choice", minutes=5),
        answer(form="prediction", transfer=True, minutes=6),
        answer(form="numeric", minutes=7),
    ]
    _, _, explanations = run(observations)
    assert len(explanations) == len(observations)
    for explanation in explanations:
        assert "%" not in explanation
        assert not re.search(r"\d\.\d", explanation)
        assert "probab" not in explanation.lower()
        assert re.search(r"(Still|Now)[: ]", explanation)
    assert explanations[1].startswith("You skipped a question.")
    assert "partly right" in explanations[3]


@given(
    st.lists(
        st.one_of(
            st.builds(
                answer,
                outcome=st.sampled_from(list(Outcome)),
                form=st.sampled_from(sorted(QUESTION_FORM_LABELS)),
                transfer=st.booleans(),
                hinted=st.booleans(),
                unsure=st.booleans(),
            ),
            st.builds(self_report, st.sampled_from(list(SelfReport))),
        ),
        max_size=30,
    )
)
def test_replaying_the_record_reproduces_the_state_exactly(observations: list[Observation]) -> None:
    step_by_step, states, explanations = run(observations)
    assert replay(observations) == step_by_step
    # Counters never disagree with each other, whatever the sequence.
    assert step_by_step.unaided_correct <= step_by_step.correct <= step_by_step.answered
    assert step_by_step.transfer_correct <= step_by_step.unaided_correct
    assert len(step_by_step.forms_correct) <= step_by_step.unaided_correct
    assert FLOOR <= step_by_step.probability <= CEILING
    if step_by_step.unaided_correct < DEFAULT_CONFIG.criteria.min_unaided_correct:
        assert MasteryState.DEMONSTRATED not in states
    assert all(explanations)


def test_every_change_of_state_is_tied_to_the_observation_that_caused_it() -> None:
    observations = [
        answer(form="multiple_choice", minutes=0),
        answer(form="numeric", minutes=1),
        answer(form="prediction", transfer=True, minutes=2),
    ]
    knowledge = initial_knowledge()
    previous = MasteryState.NOT_ASSESSED
    for observation in observations:
        transition = apply(knowledge, observation)
        assert transition.state_before is previous
        assert transition.before == knowledge
        assert transition.after.last_observed_at == observation.occurred_at
        assert transition.state_changed == (transition.state_after is not previous)
        knowledge, previous = transition.after, transition.state_after
    assert previous is MasteryState.DEMONSTRATED


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": ObservationKind.ANSWER},
        {"kind": ObservationKind.ANSWER, "outcome": Outcome.CORRECT},
        {"kind": ObservationKind.ANSWER, "outcome": Outcome.CORRECT, "question_form": "essay"},
        {
            "kind": ObservationKind.ANSWER,
            "outcome": Outcome.CORRECT,
            "question_form": "numeric",
            "item_guess": 1.0,
        },
        {"kind": ObservationKind.SELF_REPORT},
        {
            "kind": ObservationKind.SELF_REPORT,
            "self_report": SelfReport.NEW,
            "outcome": Outcome.CORRECT,
        },
    ],
)
def test_malformed_observations_are_refused(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"needs|Unknown|item_guess"):
        Observation(occurred_at=START, **fields)  # type: ignore[arg-type]


def test_observations_need_an_unambiguous_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Observation(
            kind=ObservationKind.SELF_REPORT,
            occurred_at=datetime(2026, 11, 19, 9, 0),  # deliberately without a timezone
            self_report=SelfReport.NEW,
        )
