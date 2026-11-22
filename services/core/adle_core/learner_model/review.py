"""Spaced retrieval practice, in a form that can be explained in one sentence.

After a concept is on reasonably firm ground, Adle asks about it again later.
Each successful recall pushes the next review further away; a miss brings it
close again. How far depends on the quality of the recall and on how much
evidence there is overall, not only on the calendar (PLAN.md 8.5).

Nothing here claims that anything has been retained. A review being scheduled
means "worth checking then", and only an answer on that day is evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from adle_core.learner_model.bkt import Outcome


@dataclass(frozen=True, slots=True)
class ReviewParameters:
    #: The gap after the first successful answer, and after any miss.
    first_interval_days: float = 1.0
    #: How much a recall without help multiplies the gap.
    clean_growth: float = 2.5
    #: The same for a recall that needed a hint or that the learner was unsure of.
    assisted_growth: float = 1.3
    max_interval_days: float = 90.0
    #: Below this estimate the concept is still being learned, and is not scheduled.
    min_probability: float = 0.65
    #: Answering again before this fraction of the gap has passed earns no credit:
    #: repeating something five times in ten minutes is not five recalls.
    min_elapsed_fraction: float = 0.5
    #: Recalling after a much longer gap than planned earns credit for that gap,
    #: up to this multiple of the planned one.
    late_credit_limit: float = 2.0

    def __post_init__(self) -> None:
        if not 0.0 < self.first_interval_days <= self.max_interval_days:
            raise ValueError("Intervals must satisfy 0 < first <= max.")
        if not 1.0 < self.assisted_growth <= self.clean_growth:
            raise ValueError("Growth factors must satisfy 1 < assisted <= clean.")
        if not 0.0 < self.min_probability < 1.0:
            raise ValueError("min_probability must be between 0 and 1.")
        if not 0.0 <= self.min_elapsed_fraction <= 1.0 or self.late_credit_limit < 1.0:
            raise ValueError("Elapsed-time limits are out of range.")


DEFAULT_REVIEW_PARAMETERS = ReviewParameters()


@dataclass(frozen=True, slots=True)
class ReviewState:
    #: The planned gap, in days. ``None`` until a first review is scheduled.
    interval_days: float | None = None
    due_at: datetime | None = None
    #: Successful recalls in a row.
    streak: int = 0

    @property
    def scheduled(self) -> bool:
        return self.due_at is not None and self.interval_days is not None


NOT_SCHEDULED = ReviewState()


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    state: ReviewState
    #: Why, in a sentence a learner can read. ``None`` when nothing changed.
    reason: str | None


def describe_gap(days: float) -> str:
    """A gap in everyday words: "tomorrow", "in about 5 days", "in about 3 weeks"."""
    if days < 1.5:
        return "tomorrow"
    if days < 14:
        return f"in about {round(days)} days"
    if days < 60:
        return f"in about {round(days / 7)} weeks"
    return f"in about {round(days / 30)} months"


def _evidence_strength(probability: float, parameters: ReviewParameters) -> float:
    """From 0.5 (the estimate has only just reached the threshold) to 1.0 (as high as it gets)."""
    span = 1.0 - parameters.min_probability
    return 0.5 + 0.5 * max(0.0, min(1.0, (probability - parameters.min_probability) / span))


def schedule(
    state: ReviewState,
    *,
    outcome: Outcome,
    probability: float,
    now: datetime,
    hinted: bool = False,
    unsure: bool = False,
    parameters: ReviewParameters = DEFAULT_REVIEW_PARAMETERS,
) -> ReviewDecision:
    """Decide when a concept should next be reviewed, after one answer.

    ``probability`` is the estimate *after* the answer has been taken into account.
    """
    if now.tzinfo is None:
        raise ValueError("Review times must be timezone-aware.")
    if outcome is Outcome.SKIPPED:
        return ReviewDecision(state, None)

    if probability < parameters.min_probability:
        if not state.scheduled:
            return ReviewDecision(NOT_SCHEDULED, None)
        return ReviewDecision(
            NOT_SCHEDULED,
            "You’re working on this concept again, so its reviews are paused.",
        )

    if outcome is not Outcome.CORRECT:
        gap = parameters.first_interval_days
        return ReviewDecision(
            ReviewState(interval_days=gap, due_at=now + timedelta(days=gap), streak=0),
            f"That one slipped, so it’ll come back {describe_gap(gap)}.",
        )

    planned = state.interval_days
    if planned is None or state.due_at is None:
        gap = parameters.first_interval_days
        return ReviewDecision(
            ReviewState(interval_days=gap, due_at=now + timedelta(days=gap), streak=1),
            f"First review {describe_gap(gap)}.",
        )

    last_practised = state.due_at - timedelta(days=planned)
    elapsed = max(0.0, (now - last_practised).total_seconds() / 86_400)
    if elapsed < planned * parameters.min_elapsed_fraction:
        return ReviewDecision(
            state, "Practiced before the review was due. The schedule is unchanged."
        )

    assisted = hinted or unsure
    growth = parameters.assisted_growth if assisted else parameters.clean_growth
    growth = 1.0 + (growth - 1.0) * _evidence_strength(probability, parameters)
    survived = min(max(elapsed, planned), planned * parameters.late_credit_limit)
    gap = min(parameters.max_interval_days, survived * growth)
    recalled = "Recalled with some help" if assisted else "Recalled without help"
    return ReviewDecision(
        ReviewState(interval_days=gap, due_at=now + timedelta(days=gap), streak=state.streak + 1),
        f"{recalled}. Next review {describe_gap(gap)}.",
    )


def is_due(state: ReviewState, now: datetime) -> bool:
    return state.due_at is not None and state.due_at <= now
