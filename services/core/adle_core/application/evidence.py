"""Reading back what a learner did, in the form the rules in ``learner_model`` work on.

Hypotheses about mistakes are never stored. They are worked out from a
concept's answers and from what the learner has set aside, each time they are
needed, so these readers are the only place that decides which rows count.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from adle_core.infrastructure.orm import Attempt, LearnerEvent
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.misconceptions import Answer, Dismissal, Hypothesis, fold

EVENT_DISMISSED = "misconception_dismissed"
EVENT_UNHELPFUL = "explanation_unhelpful"
EVENT_LESSON_COMPLETED = "lesson_completed"


def question_key(lesson_id: str, question_id: str) -> str:
    """One question, told apart from a question with the same id in another lesson."""
    return f"{lesson_id}:{question_id}"


def as_answer(attempt: Attempt) -> Answer:
    return Answer(
        occurred_at=attempt.created_at,
        question_id=question_key(attempt.lesson_id, attempt.question_id),
        outcome=Outcome(attempt.outcome),
        hinted=attempt.hinted,
        unsure=attempt.unsure,
        suggests=attempt.misconception,
        reveals=frozenset(attempt.reveals),
    )


def as_dismissal(event: LearnerEvent) -> Dismissal | None:
    kind = event.detail.get("kind")
    if event.kind != EVENT_DISMISSED or not isinstance(kind, str):
        return None
    return Dismissal(occurred_at=event.occurred_at, kind=kind)


def events_by_concept(
    attempts: Iterable[Attempt], events: Iterable[LearnerEvent]
) -> dict[str, list[Answer | Dismissal]]:
    """Everything hypotheses are worked out from, grouped by concept, in the order it happened."""
    grouped: dict[str, list[Answer | Dismissal]] = defaultdict(list)
    for attempt in attempts:
        grouped[attempt.concept_id].append(as_answer(attempt))
    for event in events:
        dismissal = as_dismissal(event)
        if dismissal is not None and event.concept_id is not None:
            grouped[event.concept_id].append(dismissal)
    for items in grouped.values():
        items.sort(key=lambda item: item.occurred_at)
    return grouped


def concept_events(session: Session, concept_id: str) -> list[Answer | Dismissal]:
    """One concept's answers and dismissals, oldest first."""
    attempts = session.scalars(
        select(Attempt).where(Attempt.concept_id == concept_id).order_by(Attempt.id)
    )
    events = session.scalars(
        select(LearnerEvent)
        .where(LearnerEvent.concept_id == concept_id, LearnerEvent.kind == EVENT_DISMISSED)
        .order_by(LearnerEvent.id)
    )
    return events_by_concept(attempts, events).get(concept_id, [])


def concept_hypotheses(session: Session, concept_id: str) -> dict[str, Hypothesis]:
    return fold(concept_events(session, concept_id))
