"""Scoring answers to closed questions. Deterministic: no model is involved.

Each question form has one rule, written down here and tested. A response that
does not fit the question (an option that does not exist, an order that is not
a permutation) is a malformed request, not a wrong answer, and is refused.

Open "explain in your own words" questions are scored from the rubric points
the learner says their answer covered, after seeing a model answer. That is
self-assessment, so the result is always recorded as lighter evidence.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from adle_core.learner_model.bkt import Outcome
from adle_core.lessons.ir import (
    AssessmentItem,
    ChoiceItem,
    ExplanationItem,
    NumericItem,
    OrderingItem,
    ShortAnswerItem,
    TrueFalseItem,
)

MAX_ANSWER_CHARACTERS = 400


class MalformedResponseError(ValueError):
    """The response does not fit the question it was given for."""


@dataclass(frozen=True, slots=True)
class Response:
    """What the learner submitted. Exactly one field is set, matching the question's form."""

    option_id: str | None = None
    truth: bool | None = None
    number: float | None = None
    text: str | None = None
    order: tuple[str, ...] | None = None
    covered: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class Score:
    outcome: Outcome
    #: Specific to what was answered (for a choice, the chosen option's feedback).
    feedback: str | None = None
    #: The kind of mistake this answer suggests. A hypothesis, never a diagnosis.
    misconception: str | None = None
    #: The answer rests on the learner's own judgement of it.
    self_assessed: bool = False
    #: The correct response, in words, to show after answering.
    correct_answer: str = ""
    #: Which of the offered options was right (``true`` / ``false`` for a true-or-false
    #: question), so the interface can mark it among the options it is showing.
    correct_option: str | None = None


_ARTICLES = re.compile(r"^(?:the|a|an)\s+")
_PUNCTUATION = re.compile(r"[^\w\s./+-]")


def normalise_answer(text: str) -> str:
    """Fold case, accents, punctuation, spacing, and a leading article."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = _PUNCTUATION.sub(" ", folded)
    folded = " ".join(folded.split()).strip(" .")
    return _ARTICLES.sub("", folded)


def _longest_common_subsequence(first: tuple[str, ...], second: tuple[str, ...]) -> int:
    lengths = [[0] * (len(second) + 1) for _ in range(len(first) + 1)]
    for i, left in enumerate(first, start=1):
        for j, right in enumerate(second, start=1):
            lengths[i][j] = (
                lengths[i - 1][j - 1] + 1
                if left == right
                else max(lengths[i - 1][j], lengths[i][j - 1])
            )
    return lengths[-1][-1]


def _format_number(value: float) -> str:
    return str(int(value)) if value == int(value) and abs(value) < 1e15 else f"{value:g}"


def _score_choice(item: ChoiceItem, response: Response) -> Score:
    chosen = next((option for option in item.options if option.id == response.option_id), None)
    if chosen is None:
        raise MalformedResponseError("That is not one of the options.")
    right = next(option for option in item.options if option.id == item.correct_option)
    correct = chosen.id == item.correct_option
    return Score(
        outcome=Outcome.CORRECT if correct else Outcome.INCORRECT,
        feedback=chosen.feedback,
        misconception=None if correct else chosen.misconception,
        correct_answer=right.text,
        correct_option=right.id,
    )


def _score_true_false(item: TrueFalseItem, response: Response) -> Score:
    if response.truth is None:
        raise MalformedResponseError("Answer true or false.")
    return Score(
        outcome=Outcome.CORRECT if response.truth is item.correct else Outcome.INCORRECT,
        correct_answer="True" if item.correct else "False",
        correct_option="true" if item.correct else "false",
    )


def _score_numeric(item: NumericItem, response: Response) -> Score:
    value = response.number
    if value is None or not math.isfinite(value):
        raise MalformedResponseError("Enter a number.")
    # A hair of slack so that 0.1 + 0.2 typed as 0.3 is not marked wrong by floating point.
    slack = item.tolerance + 1e-9 * max(1.0, abs(item.expected))
    correct = abs(value - item.expected) <= slack
    answer = _format_number(item.expected) + (f" {item.unit}" if item.unit else "")
    misconception = None
    if not correct and item.expected != 0 and abs(value + item.expected) <= slack:
        # The right size with the wrong sign: far more often a slip than a misunderstanding.
        misconception = "arithmetic_slip"
    return Score(
        outcome=Outcome.CORRECT if correct else Outcome.INCORRECT,
        misconception=misconception,
        correct_answer=answer,
    )


def _score_short_answer(item: ShortAnswerItem, response: Response) -> Score:
    if response.text is None or not response.text.strip():
        raise MalformedResponseError("Type an answer.")
    if len(response.text) > MAX_ANSWER_CHARACTERS:
        raise MalformedResponseError("That answer is too long for this question.")
    given = normalise_answer(response.text)
    correct = given in {normalise_answer(accepted) for accepted in item.accepted}
    return Score(
        outcome=Outcome.CORRECT if correct else Outcome.INCORRECT,
        correct_answer=item.accepted[0],
    )


def _score_ordering(item: OrderingItem, response: Response) -> Score:
    expected = tuple(entry.id for entry in item.items)
    given = response.order
    if given is None or sorted(given) != sorted(expected):
        raise MalformedResponseError("Put every item in the order, once each.")
    if given == expected:
        outcome = Outcome.CORRECT
    elif _longest_common_subsequence(given, expected) >= len(expected) - 1:
        # One item out of place: most of the order is understood.
        outcome = Outcome.PARTIAL
    else:
        outcome = Outcome.INCORRECT
    return Score(
        outcome=outcome,
        misconception="procedure_order" if outcome is Outcome.INCORRECT else None,
        correct_answer="; then ".join(entry.text for entry in item.items),
    )


def _score_explanation(item: ExplanationItem, response: Response) -> Score:
    known = {point.id for point in item.rubric}
    covered = response.covered
    if covered is None or len(set(covered)) != len(covered) or not set(covered) <= known:
        raise MalformedResponseError("Tick the points your answer included.")
    if len(covered) >= item.required_points:
        outcome = Outcome.CORRECT
    elif covered:
        outcome = Outcome.PARTIAL
    else:
        outcome = Outcome.INCORRECT
    return Score(outcome=outcome, self_assessed=True, correct_answer=item.sample_answer)


def score(item: AssessmentItem, response: Response) -> Score:
    """Score ``response`` against ``item``. Raises ``MalformedResponseError`` if they do not fit."""
    if isinstance(item, ChoiceItem):
        return _score_choice(item, response)
    if isinstance(item, TrueFalseItem):
        return _score_true_false(item, response)
    if isinstance(item, NumericItem):
        return _score_numeric(item, response)
    if isinstance(item, ShortAnswerItem):
        return _score_short_answer(item, response)
    if isinstance(item, OrderingItem):
        return _score_ordering(item, response)
    return _score_explanation(item, response)


def reveals(item: AssessmentItem) -> frozenset[str]:
    """The kinds of mistake an answer to this question is able to point at.

    Recorded with every answer: a right answer counts against a suspected
    mistake only if the question could have shown it.
    """
    if isinstance(item, ChoiceItem):
        return frozenset(
            option.misconception
            for option in item.options
            if option.misconception and option.id != item.correct_option
        )
    if isinstance(item, NumericItem):
        return frozenset({"arithmetic_slip"}) if item.expected != 0 else frozenset()
    if isinstance(item, OrderingItem):
        return frozenset({"procedure_order"})
    return frozenset()
