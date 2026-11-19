"""Bayesian Knowledge Tracing: a small, transparent model of what a learner knows.

For each concept the model keeps one number: the probability that the learner
has the concept. Every scored answer updates it in two steps.

1. **Evidence.** Bayes' rule, using how likely a correct answer is from someone
   who has the concept (``1 - slip``) and from someone who has not (``guess``).
2. **Learning.** Whatever the answer, the attempt itself gives a chance
   (``learn``) of moving from "not known" to "known".

The parameters are configuration, not facts about any learner; they are
documented in ``BktParameters`` and can be changed without touching this code.

The probability is an internal estimate. It is never shown to a learner as a
number: after a handful of answers it is far too uncertain for that, and the
qualitative states in ``mastery`` say what the evidence actually supports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: The estimate is kept away from 0 and 1. At exactly 0 or 1 Bayes' rule can
#: never move it again, however much evidence arrives.
FLOOR = 0.001
CEILING = 0.999

#: ``guess + slip`` must stay below 1, or a correct answer would count against
#: the learner. Adjusted guess values are capped to keep this margin.
_MARGIN = 0.05


class Outcome(StrEnum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    #: The learner chose not to answer. It is recorded, and it is not evidence.
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BktParameters:
    #: Probability that a learner already has a concept before any evidence.
    prior: float = 0.2
    #: Probability of acquiring the concept at each attempt.
    learn: float = 0.15
    #: Probability of a correct answer without having the concept.
    guess: float = 0.2
    #: Probability of a wrong answer despite having the concept.
    slip: float = 0.1
    #: ``guess`` when the answer came after a hint: the hint did part of the work.
    hinted_guess: float = 0.5
    #: ``guess`` when the learner said they were unsure and was still right.
    unsure_guess: float = 0.4

    def __post_init__(self) -> None:
        for name in ("prior", "learn", "guess", "slip", "hinted_guess", "unsure_guess"):
            value = getattr(self, name)
            if not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be between 0 and 1 (exclusive), not {value!r}.")
        widest_guess = max(self.guess, self.hinted_guess, self.unsure_guess)
        if widest_guess + self.slip > 1.0 - _MARGIN:
            raise ValueError("guess + slip must stay below 1, or correct answers stop counting.")


DEFAULT_PARAMETERS = BktParameters()


def clamp(probability: float) -> float:
    return min(CEILING, max(FLOOR, probability))


def effective_guess(
    parameters: BktParameters,
    *,
    item_guess: float | None = None,
    hinted: bool = False,
    unsure: bool = False,
) -> float:
    """How likely a correct answer was without the concept, for this particular answer.

    ``item_guess`` comes from the question itself when it is known (one in four
    for a four-option choice). A hint or a stated lack of confidence can only
    raise the value: they make a correct answer weaker evidence, never stronger.
    """
    guess = parameters.guess if item_guess is None else item_guess
    if hinted:
        guess = max(guess, parameters.hinted_guess)
    if unsure:
        guess = max(guess, parameters.unsure_guess)
    return min(max(guess, FLOOR), 1.0 - parameters.slip - _MARGIN)


def evidence_step(probability: float, outcome: Outcome, *, guess: float, slip: float) -> float:
    """The probability after seeing ``outcome``, before any learning is credited."""
    known = clamp(probability)
    unknown = 1.0 - known
    if_correct = known * (1.0 - slip) / (known * (1.0 - slip) + unknown * guess)
    if_incorrect = known * slip / (known * slip + unknown * (1.0 - guess))
    if outcome is Outcome.CORRECT:
        return if_correct
    if outcome is Outcome.INCORRECT:
        return if_incorrect
    if outcome is Outcome.PARTIAL:
        # Half-way between the two: partial credit is ambiguous evidence.
        return (if_correct + if_incorrect) / 2.0
    return known


def learning_step(probability: float, learn: float) -> float:
    return probability + (1.0 - probability) * learn


def update(
    probability: float,
    outcome: Outcome,
    parameters: BktParameters = DEFAULT_PARAMETERS,
    *,
    item_guess: float | None = None,
    hinted: bool = False,
    unsure: bool = False,
) -> float:
    """The new estimate after one answer. A skipped question changes nothing."""
    if outcome is Outcome.SKIPPED:
        return clamp(probability)
    guess = effective_guess(parameters, item_guess=item_guess, hinted=hinted, unsure=unsure)
    after_evidence = evidence_step(probability, outcome, guess=guess, slip=parameters.slip)
    return clamp(learning_step(after_evidence, parameters.learn))
