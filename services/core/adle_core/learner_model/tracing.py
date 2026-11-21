"""Turn a learner's recorded observations into what Adle believes about a concept.

The state of a concept is never edited directly. It is the result of folding
the concept's observations, oldest first, through :func:`apply`. That makes
three things true by construction:

* every change of state has an observation that caused it and a sentence that
  explains it;
* the stored state can be thrown away and rebuilt (:func:`replay`);
* changing a parameter and replaying shows exactly what the change would do.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from adle_core.learner_model.bkt import (
    DEFAULT_PARAMETERS,
    BktParameters,
    Outcome,
    clamp,
    update,
)
from adle_core.learner_model.mastery import (
    DEFAULT_CRITERIA,
    STATE_LABELS,
    Assessment,
    Evidence,
    MasteryCriteria,
    MasteryState,
    assess,
)
from adle_core.learner_model.review import (
    DEFAULT_REVIEW_PARAMETERS,
    NOT_SCHEDULED,
    ReviewParameters,
    ReviewState,
    schedule,
)


class ObservationKind(StrEnum):
    #: A scored (or skipped) answer to a question about the concept.
    ANSWER = "answer"
    #: The learner's own statement of how well they know the concept.
    SELF_REPORT = "self_report"
    #: The learner said a suspected misunderstanding does not describe them.
    DISMISSAL = "dismissal"


class SelfReport(StrEnum):
    NEW = "new"
    SOME = "some"
    CONFIDENT = "confident"


#: Where a self-report places the estimate when there are no answers yet. Even
#: "I know this well" stays below the level at which Adle would rely on it.
SELF_REPORT_PRIORS: dict[SelfReport, float] = {
    SelfReport.NEW: 0.08,
    SelfReport.SOME: 0.35,
    SelfReport.CONFIDENT: 0.6,
}

#: Once there are answers, a self-report only nudges the estimate this far
#: towards its prior. What the learner did outweighs what they say.
SELF_REPORT_PULL = 0.25

#: The kinds of question Adle asks, with the phrase used for each in explanations.
#: The form whose answers the learner marks themselves against a list of points.
SELF_MARKED_FORM = "explanation"

QUESTION_FORM_LABELS: dict[str, str] = {
    "multiple_choice": "a multiple-choice question",
    "true_false": "a true-or-false question",
    "numeric": "a numeric question",
    "short_answer": "a short-answer question",
    "ordering": "an ordering question",
    "prediction": "a prediction question",
    "explanation": "an explain-in-your-own-words question",
}


@dataclass(frozen=True, slots=True)
class Observation:
    kind: ObservationKind
    occurred_at: datetime
    # -- answers --
    outcome: Outcome | None = None
    #: One of ``QUESTION_FORM_LABELS``.
    question_form: str | None = None
    #: The question applied the idea to a situation the lesson had not shown.
    is_transfer: bool = False
    hinted: bool = False
    #: The learner said they were not sure of their answer.
    unsure: bool = False
    #: Chance of a correct answer by guessing, when the question defines one.
    item_guess: float | None = None
    #: A wrong answer that shows the method was right and the execution slipped (the right
    #: number with the wrong sign). It is counted as partly right.
    slip: bool = False
    #: The same question was answered a short while ago, so its explanation is fresh in
    #: mind. Only changes the wording; the answer is recorded as an aided one (``hinted``).
    repeated: bool = False
    # -- self-reports --
    self_report: SelfReport | None = None
    # -- answers and dismissals --
    #: Whether, with this observation taken into account, a misunderstanding supported by
    #: more than one answer still stands (``learner_model.misconceptions``). ``None``
    #: leaves what was known unchanged.
    unresolved_misconception: bool | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("Observations must carry a timezone-aware time.")
        if self.kind is ObservationKind.DISMISSAL:
            if self.outcome is not None or self.self_report is not None:
                raise ValueError("A dismissal has no outcome and no self-report.")
            if self.unresolved_misconception is None:
                raise ValueError("A dismissal must say what still stands after it.")
            return
        if self.kind is ObservationKind.ANSWER:
            if self.outcome is None or self.self_report is not None:
                raise ValueError("An answer needs an outcome and no self-report.")
            if self.outcome is not Outcome.SKIPPED and self.question_form is None:
                raise ValueError("A scored answer needs its question form.")
            if self.question_form is not None and self.question_form not in QUESTION_FORM_LABELS:
                raise ValueError("Unknown question form.")
            if self.item_guess is not None and not 0.0 <= self.item_guess < 1.0:
                raise ValueError("item_guess must be a probability below 1.")
            if self.slip and self.outcome is not Outcome.INCORRECT:
                raise ValueError("Only a wrong answer can be a slip.")
        elif self.self_report is None or self.outcome is not None:
            raise ValueError("A self-report needs a level and no outcome.")


@dataclass(frozen=True, slots=True)
class ConceptKnowledge:
    """What the observations so far add up to, for one concept."""

    probability: float
    answered: int = 0
    correct: int = 0
    unaided_correct: int = 0
    hinted: int = 0
    skipped: int = 0
    forms_correct: frozenset[str] = frozenset()
    transfer_correct: int = 0
    self_report: SelfReport | None = None
    last_observed_at: datetime | None = None
    review: ReviewState = NOT_SCHEDULED
    #: A misunderstanding supported by more than one answer has not been cleared up.
    unresolved_misconception: bool = False

    def evidence(self) -> Evidence:
        return Evidence(
            probability=self.probability,
            answered=self.answered,
            unaided_correct=self.unaided_correct,
            forms_correct=self.forms_correct,
            transfer_correct=self.transfer_correct,
            claims_to_know=self.self_report is SelfReport.CONFIDENT,
            unresolved_misconception=self.unresolved_misconception,
        )


@dataclass(frozen=True, slots=True)
class Transition:
    """One observation's effect, with the reason in words."""

    before: ConceptKnowledge
    after: ConceptKnowledge
    state_before: MasteryState
    assessment: Assessment
    #: What happened and what it means, for the learner. Never contains a score.
    explanation: str

    @property
    def state_after(self) -> MasteryState:
        return self.assessment.state

    @property
    def state_changed(self) -> bool:
        return self.state_before is not self.assessment.state


@dataclass(frozen=True, slots=True)
class TracingConfig:
    bkt: BktParameters = DEFAULT_PARAMETERS
    criteria: MasteryCriteria = DEFAULT_CRITERIA
    review: ReviewParameters = DEFAULT_REVIEW_PARAMETERS
    #: Stored with every observation so a later change of parameters is visible in the record.
    version: str = "bkt-2"


DEFAULT_CONFIG = TracingConfig()


def initial_knowledge(config: TracingConfig = DEFAULT_CONFIG) -> ConceptKnowledge:
    return ConceptKnowledge(probability=config.bkt.prior)


def _apply_answer(
    knowledge: ConceptKnowledge, observation: Observation, config: TracingConfig
) -> tuple[ConceptKnowledge, str | None]:
    outcome = observation.outcome
    if outcome is None:  # pragma: no cover - excluded by Observation.__post_init__
        raise ValueError("An answer needs an outcome.")
    if outcome is Outcome.SKIPPED:
        return replace(knowledge, skipped=knowledge.skipped + 1), None

    probability = update(
        knowledge.probability,
        # A slip shows the method and misses the result: ambiguous evidence, like an
        # answer that is partly right, and not a sign that the idea is missing.
        Outcome.PARTIAL if observation.slip else outcome,
        config.bkt,
        item_guess=observation.item_guess,
        hinted=observation.hinted,
        unsure=observation.unsure,
    )
    correct = outcome is Outcome.CORRECT
    unaided = correct and not observation.hinted and not observation.unsure
    form = observation.question_form
    decision = schedule(
        knowledge.review,
        outcome=outcome,
        probability=probability,
        now=observation.occurred_at,
        hinted=observation.hinted,
        unsure=observation.unsure,
        parameters=config.review,
    )
    after = replace(
        knowledge,
        probability=probability,
        answered=knowledge.answered + 1,
        correct=knowledge.correct + (1 if correct else 0),
        unaided_correct=knowledge.unaided_correct + (1 if unaided else 0),
        hinted=knowledge.hinted + (1 if observation.hinted else 0),
        forms_correct=knowledge.forms_correct | {form}
        if unaided and form is not None
        else knowledge.forms_correct,
        transfer_correct=knowledge.transfer_correct
        + (1 if unaided and observation.is_transfer else 0),
        review=decision.state,
    )
    return after, decision.reason


def _apply_self_report(knowledge: ConceptKnowledge, observation: Observation) -> ConceptKnowledge:
    level = observation.self_report
    if level is None:  # pragma: no cover - excluded by Observation.__post_init__
        raise ValueError("A self-report needs a level.")
    target = SELF_REPORT_PRIORS[level]
    if knowledge.answered == 0:
        probability = target
    else:
        probability = knowledge.probability + SELF_REPORT_PULL * (target - knowledge.probability)
    return replace(knowledge, probability=clamp(probability), self_report=level)


def _what_happened(observation: Observation) -> str:
    if observation.kind is ObservationKind.SELF_REPORT:
        return {
            SelfReport.NEW: "You said this is new to you.",
            SelfReport.SOME: "You said you know some of this.",
            SelfReport.CONFIDENT: "You said you already know this well.",
            None: "",
        }[observation.self_report]

    if observation.kind is ObservationKind.DISMISSAL:
        return "You marked a suspected mix-up as a slip, so it’s set aside."

    question = QUESTION_FORM_LABELS.get(observation.question_form or "", "a question")
    if observation.is_transfer:
        question += " that applied the idea to a new situation"
    if observation.outcome is Outcome.SKIPPED:
        return "You skipped a question. Skips don’t count either way."
    if observation.outcome is Outcome.CORRECT:
        if observation.repeated:
            return (
                f"You answered {question} correctly. You’d just seen its explanation, so it "
                "counts a little less."
            )
        if observation.hinted:
            return f"You answered {question} correctly after a hint, which counts a little less."
        if observation.unsure and observation.question_form == SELF_MARKED_FORM:
            # Nobody said they were unsure: the answer was the learner's own judgement.
            return (
                "You marked your own explanation as covering the points. Self-marked answers "
                "count a little less."
            )
        if observation.unsure:
            return (
                f"You answered {question} correctly but weren’t sure, which counts a little less."
            )
        return f"You answered {question} correctly."
    if observation.outcome is Outcome.PARTIAL:
        return f"Your answer to {question} was partly right."
    if observation.slip:
        return (
            f"Your answer to {question} wasn’t right, but it looks like a slip, not a gap. It "
            "counts as partly right."
        )
    return f"Your answer to {question} wasn’t right."


def _what_it_means(state_before: MasteryState, assessment: Assessment) -> str:
    label = STATE_LABELS[assessment.state]
    if assessment.state is MasteryState.DEMONSTRATED:
        if state_before is MasteryState.DEMONSTRATED:
            return f"Still {label.lower()}."
        return f"Now: {label}. A review later will check that it stuck."
    still_needed = "; ".join(assessment.missing)
    if state_before is assessment.state:
        # The state is beside this sentence wherever it is shown: only what is left is news.
        return f"Still needed: {still_needed}."
    return f"Now: {label}. Still needed: {still_needed}."


def apply(
    knowledge: ConceptKnowledge,
    observation: Observation,
    config: TracingConfig = DEFAULT_CONFIG,
    *,
    note: str | None = None,
) -> Transition:
    """Fold one observation into what is known about a concept.

    ``note`` is a sentence about what the observation changed that this module cannot
    know (a suspected mistake opened or settled). It is placed in the explanation after
    what happened.
    """
    state_before = assess(knowledge.evidence(), config.criteria).state

    review_note: str | None = None
    if observation.kind is ObservationKind.ANSWER:
        after, review_note = _apply_answer(knowledge, observation, config)
    elif observation.kind is ObservationKind.SELF_REPORT:
        after = _apply_self_report(knowledge, observation)
    else:
        after = knowledge
    if observation.unresolved_misconception is not None:
        after = replace(after, unresolved_misconception=observation.unresolved_misconception)
    if observation.kind is not ObservationKind.DISMISSAL:
        # Setting a suspicion aside is not practice: it leaves "last practised" alone.
        after = replace(after, last_observed_at=observation.occurred_at)

    assessment = assess(after.evidence(), config.criteria)
    parts = [_what_happened(observation), note or "", _what_it_means(state_before, assessment)]
    if review_note:
        parts.append(review_note)
    return Transition(
        before=knowledge,
        after=after,
        state_before=state_before,
        assessment=assessment,
        explanation=" ".join(part for part in parts if part),
    )


def replay(
    observations: Iterable[Observation], config: TracingConfig = DEFAULT_CONFIG
) -> ConceptKnowledge:
    """Rebuild a concept's knowledge from its observations, oldest first."""
    knowledge = initial_knowledge(config)
    for observation in observations:
        knowledge = apply(knowledge, observation, config).after
    return knowledge
