"""A sitting: one stretch of work on a course, and what it showed.

Nothing in the record says "session": the learner never starts or ends one, and is
never asked to. A sitting is read off the record instead. It is the latest run of
activity with no pause in it longer than ``SITTING_GAP``. While the learner could
still be in it, it is "this session"; after that it is "last time", which is what a
learner coming back wants to be reminded of.

What a sitting showed is said in counts of answers and in the words the rest of the
interface already uses for a concept. There is no score here and none can be derived:
one sitting is never enough to call anything demonstrated, so "demonstrated" is only
ever reported as the state the concept is in now, by the criteria that decide it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from adle_core.learner_model.mastery import MasteryState

#: A pause longer than this ends a sitting. Long enough for a break in the middle of
#: a lesson, short enough that coming back after lunch is a new one.
SITTING_GAP = timedelta(minutes=45)


@dataclass(frozen=True, slots=True)
class Activity:
    """Something the learner did on a concept, as far as a sitting is concerned."""

    at: datetime
    concept_id: str
    #: A question was answered and scored. A skip is activity, but not an answer.
    answered: bool = False
    #: The answer was right, however it was reached.
    right: bool = False
    #: It was right without a hint, without "I am not sure", not marked by the learner
    #: themselves, and not a repeat of a question answered moments before: exactly what
    #: counts as unaided evidence. A right answer that is not this is lighter evidence.
    right_unaided: bool = False
    lesson_completed: bool = False

    def __post_init__(self) -> None:
        if self.right and not self.answered:
            raise ValueError("Only an answer can be right.")
        if self.right_unaided and not self.right:
            raise ValueError("An unaided right answer is a right answer.")


@dataclass(frozen=True, slots=True)
class ConceptNow:
    """A concept as it stands at the end, in learning order."""

    id: str
    title: str
    state: MasteryState
    #: What is still needed before it counts as demonstrated. Empty exactly then.
    missing: tuple[str, ...] = ()
    review_due_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Shown:
    concept_id: str
    title: str
    #: Right answers in this sitting. At least one.
    right: int
    #: Those of them that count in full. The rest are lighter evidence.
    right_unaided: int
    #: The concept counts as demonstrated now, by the usual criteria.
    demonstrated: bool


@dataclass(frozen=True, slots=True)
class StillNeeded:
    concept_id: str
    title: str
    state: MasteryState
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlannedReview:
    concept_id: str
    title: str
    due_at: datetime


@dataclass(frozen=True, slots=True)
class Sitting:
    started_at: datetime
    ended_at: datetime
    #: The learner may still be in it: the last thing they did is less than a gap ago.
    current: bool
    lessons_completed: int
    answered: int
    #: Concepts worked on in which something was shown, in learning order.
    shown: tuple[Shown, ...]
    #: Concepts worked on that are not demonstrated yet, with what is missing.
    still_needed: tuple[StillNeeded, ...]
    #: Concepts worked on that now have a review planned, soonest first.
    reviews: tuple[PlannedReview, ...]


def latest_sitting(
    activities: Iterable[Activity], concepts: Sequence[ConceptNow], now: datetime
) -> Sitting | None:
    """The most recent sitting and what it showed, or ``None`` if nothing has been done.

    ``concepts`` gives the order of the lines and what each concept looks like now.
    Activity on a concept that is not among them (it was removed since) still counts
    towards the totals, but has no line. Activity dated after ``now`` is ignored: the
    clock was changed, and a sitting that ends in the future would never end.
    """
    past = sorted((item for item in activities if item.at <= now), key=lambda item: item.at)
    if not past:
        return None

    first = len(past) - 1
    while first > 0 and past[first].at - past[first - 1].at <= SITTING_GAP:
        first -= 1
    during = past[first:]

    touched = {item.concept_id for item in during}
    right = Counter(item.concept_id for item in during if item.right)
    unaided = Counter(item.concept_id for item in during if item.right_unaided)
    worked_on = [concept for concept in concepts if concept.id in touched]
    return Sitting(
        started_at=during[0].at,
        ended_at=during[-1].at,
        current=now - during[-1].at <= SITTING_GAP,
        lessons_completed=sum(1 for item in during if item.lesson_completed),
        answered=sum(1 for item in during if item.answered),
        shown=tuple(
            Shown(
                concept_id=concept.id,
                title=concept.title,
                right=right[concept.id],
                right_unaided=unaided[concept.id],
                demonstrated=concept.state is MasteryState.DEMONSTRATED,
            )
            for concept in worked_on
            if right[concept.id] > 0
        ),
        still_needed=tuple(
            StillNeeded(
                concept_id=concept.id,
                title=concept.title,
                state=concept.state,
                missing=concept.missing,
            )
            for concept in worked_on
            if concept.state is not MasteryState.DEMONSTRATED
        ),
        reviews=tuple(
            sorted(
                (
                    PlannedReview(concept_id=concept.id, title=concept.title, due_at=due)
                    for concept in worked_on
                    if (due := concept.review_due_at) is not None
                ),
                key=lambda review: review.due_at,
            )
        ),
    )
