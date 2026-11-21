"""From evidence to the words a learner sees.

The tracing model produces a probability. A learner never sees it. What they
see is one of four states, chosen by explicit, configurable criteria, together
with what is still missing. The criteria exist so that one lucky answer can
never look like understanding (PLAN.md 8.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MasteryState(StrEnum):
    NOT_ASSESSED = "not_assessed"
    BUILDING = "building"
    NEEDS_EVIDENCE = "needs_evidence"
    DEMONSTRATED = "demonstrated"


#: How an unresolved misunderstanding is named among the things still needed.
MISUNDERSTANDING_TO_CLEAR = "a possible misunderstanding to clear up"

STATE_LABELS: dict[MasteryState, str] = {
    MasteryState.NOT_ASSESSED: "Not started",
    MasteryState.BUILDING: "Learning",
    MasteryState.NEEDS_EVIDENCE: "Nearly there",
    MasteryState.DEMONSTRATED: "Understood",
}


@dataclass(frozen=True, slots=True)
class MasteryCriteria:
    """What "demonstrated" requires. All of it, not any of it."""

    #: The estimate must be at least this high.
    demonstrated_probability: float = 0.85
    #: From here up, the picture is promising but not yet established.
    promising_probability: float = 0.65
    #: Correct answers given without a hint and without the learner saying they were unsure.
    min_unaided_correct: int = 3
    #: Those answers must span at least this many kinds of question.
    min_question_forms: int = 2
    #: At least one must apply the idea to a situation the lesson did not show.
    require_transfer: bool = True

    def __post_init__(self) -> None:
        if not 0.0 < self.promising_probability <= self.demonstrated_probability < 1.0:
            raise ValueError("Thresholds must satisfy 0 < promising <= demonstrated < 1.")
        if self.min_unaided_correct < 2:
            # One answer must never be enough, whatever the configuration says.
            raise ValueError("At least two unaided correct answers must be required.")
        if self.min_question_forms < 1:
            raise ValueError("At least one question form must be required.")


DEFAULT_CRITERIA = MasteryCriteria()


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything observed about one concept, reduced to what the criteria need."""

    probability: float
    #: Scored answers of any outcome. Skipped questions and self-reports do not count.
    answered: int = 0
    unaided_correct: int = 0
    #: The kinds of question answered correctly without help.
    forms_correct: frozenset[str] = frozenset()
    transfer_correct: int = 0
    #: The learner has said they already know this well.
    claims_to_know: bool = False
    #: A suspected misunderstanding has not been cleared up yet (set by M6).
    unresolved_misconception: bool = False
    #: False for the rare concept where a transfer question makes no sense.
    transfer_applicable: bool = True


@dataclass(frozen=True, slots=True)
class Assessment:
    state: MasteryState
    #: What is still needed before the concept counts as demonstrated, in plain
    #: words. Empty exactly when ``state`` is ``DEMONSTRATED``.
    missing: tuple[str, ...]

    @property
    def label(self) -> str:
        return STATE_LABELS[self.state]


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def assess(evidence: Evidence, criteria: MasteryCriteria = DEFAULT_CRITERIA) -> Assessment:
    """The state the evidence supports, and what is missing for the next one."""
    if evidence.answered == 0:
        if evidence.claims_to_know:
            return Assessment(
                MasteryState.NEEDS_EVIDENCE,
                ("a few questions to confirm what you know",),
            )
        return Assessment(MasteryState.NOT_ASSESSED, ("some answered questions",))

    missing: list[str] = []
    short_by = criteria.min_unaided_correct - evidence.unaided_correct
    if short_by > 0:
        missing.append(
            _plural(short_by, "more correct answer", "more correct answers") + " without a hint"
        )
    if len(evidence.forms_correct) < criteria.min_question_forms:
        missing.append("a correct answer to another kind of question")
    if criteria.require_transfer and evidence.transfer_applicable and evidence.transfer_correct < 1:
        missing.append("a correct answer in a new situation")
    if evidence.unresolved_misconception:
        missing.append(MISUNDERSTANDING_TO_CLEAR)
    if not missing and evidence.probability < criteria.demonstrated_probability:
        missing.append("more consistent correct answers")

    if not missing:
        return Assessment(MasteryState.DEMONSTRATED, ())
    if evidence.probability >= criteria.promising_probability:
        return Assessment(MasteryState.NEEDS_EVIDENCE, tuple(missing))
    return Assessment(MasteryState.BUILDING, tuple(missing))
