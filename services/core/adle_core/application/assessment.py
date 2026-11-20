"""Answering a question, in a lesson or in practice.

One call does four things in one transaction: scores the answer by the
question's rule, works out what it changes about any suspected mistake, keeps
the attempt, and records it as evidence about the concept. What comes back is
what the learner should see: whether it was right, why the right answer is
right, and what the answer changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from adle_core.application.asks import asked_since
from adle_core.application.curriculum import (
    KnowledgeRecord,
    get_concept_or_404,
    knowledge_record,
)
from adle_core.application.evidence import concept_events, question_key
from adle_core.application.learner import LearnerService
from adle_core.application.lessons import LessonService
from adle_core.errors import NotFoundError, ValidationFailedError
from adle_core.evaluation.scoring import (
    MalformedResponseError,
    Response,
    Score,
    reveals,
    score,
)
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import Attempt, LearnerConceptState
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.misconceptions import (
    SLIPS,
    Answer,
    blocks_mastery,
    describe_change,
    fold,
)
from adle_core.learner_model.practice import FRESH_AGAIN_AFTER
from adle_core.learner_model.tracing import Observation, ObservationKind
from adle_core.lessons.ir import CheckpointSegment, guess_probability


@dataclass(frozen=True, slots=True)
class AnswerResult:
    outcome: str
    #: About the answer that was given, when the question has something specific to say.
    feedback: str | None
    #: Why the right answer is right. Shown whatever was answered.
    explanation: str
    correct_answer: str
    #: The right one among the options that were offered, when the question had options.
    correct_option: str | None
    #: What the answer changed, in words.
    change: str
    knowledge: KnowledgeRecord
    #: 1 for the first answer to this question, 2 for the second, and so on.
    attempt_number: int


class AssessmentService:
    def __init__(self, database: Database, lessons: LessonService, learner: LearnerService) -> None:
        self._database = database
        self._lessons = lessons
        self._learner = learner

    def answer(
        self,
        lesson_id: str,
        question_id: str,
        response: Response | None,
        *,
        hinted: bool = False,
        unsure: bool = False,
        now: datetime | None = None,
    ) -> AnswerResult:
        """Score an answer and record it. ``response`` is ``None`` for an explicit skip."""
        moment = now or utc_now()
        lesson = self._lessons.get_lesson(lesson_id)
        item = next(
            (question for question in lesson.all_questions() if question.id == question_id), None
        )
        if item is None:
            raise NotFoundError("That question is not part of this lesson.")
        #: The part of the lesson that asks it, when it is asked in the lesson's flow.
        segment_id = next(
            (
                segment.id
                for segment in lesson.segments
                if isinstance(segment, CheckpointSegment) and segment.question.id == question_id
            ),
            None,
        )

        if response is None:
            result = Score(outcome=Outcome.SKIPPED)
        else:
            try:
                result = score(item, response)
            except MalformedResponseError as error:
                raise ValidationFailedError(str(error)) from error
        skipped = result.outcome is Outcome.SKIPPED
        can_reveal = reveals(item)

        with self._database.session() as session:
            concept = get_concept_or_404(session, item.concept_id)
            earlier = session.scalars(
                select(Attempt)
                .where(
                    Attempt.lesson_id == lesson_id,
                    Attempt.question_id == question_id,
                    Attempt.outcome != Outcome.SKIPPED.value,
                )
                .order_by(Attempt.id)
            ).all()
            # A little while after a first answer the learner still has its explanation in
            # mind, so a repeat shows recall of that explanation at best. It counts as an
            # aided answer. After a real gap, answering again is recall, and counts in full.
            repeated = bool(earlier) and moment - earlier[-1].created_at < FRESH_AGAIN_AFTER
            # Asking Adle about the question before answering it is help, like the hint.
            # What was asked is not looked at: that it was is enough (ADR-024).
            asked = segment_id is not None and asked_since(
                session, lesson_id, segment_id, earlier[-1].created_at if earlier else None
            )
            hinted = hinted or asked
            aided = hinted or repeated
            doubtful = unsure or result.self_assessed

            history = concept_events(session, concept.id)
            before = fold(history)
            after = before
            if not skipped:
                after = fold(
                    [
                        *history,
                        Answer(
                            occurred_at=moment,
                            question_id=question_key(lesson_id, question_id),
                            outcome=result.outcome,
                            hinted=aided,
                            unsure=doubtful,
                            suggests=result.misconception,
                            reveals=can_reveal,
                        ),
                    ]
                )

            transition = self._learner.record_in(
                session,
                concept,
                Observation(
                    kind=ObservationKind.ANSWER,
                    occurred_at=moment,
                    outcome=result.outcome,
                    question_form=None if skipped else item.form,
                    is_transfer=item.is_transfer and not skipped,
                    hinted=aided and not skipped,
                    unsure=doubtful and not skipped,
                    item_guess=None if skipped else guess_probability(item),
                    slip=result.outcome is Outcome.INCORRECT and result.misconception in SLIPS,
                    repeated=repeated and not hinted and not skipped,
                    unresolved_misconception=None if skipped else blocks_mastery(after.values()),
                ),
                note=describe_change(before, after) or None,
            )
            session.flush()
            session.add(
                Attempt(
                    course_id=lesson.course_id,
                    lesson_id=lesson_id,
                    concept_id=item.concept_id,
                    question_id=question_id,
                    form=item.form,
                    outcome=result.outcome.value,
                    hinted=aided and not skipped,
                    unsure=unsure and not skipped,
                    misconception=result.misconception,
                    reveals=sorted(can_reveal),
                    created_at=moment,
                )
            )
            session.flush()
            state = session.get(LearnerConceptState, item.concept_id)
            return AnswerResult(
                outcome=result.outcome.value,
                feedback=None if skipped else result.feedback,
                explanation=item.explanation,
                correct_answer=result.correct_answer if not skipped else "",
                correct_option=result.correct_option,
                change=transition.explanation,
                knowledge=knowledge_record(state),
                attempt_number=len(earlier) + (0 if skipped else 1),
            )
