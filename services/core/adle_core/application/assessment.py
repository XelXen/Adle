"""Answering a lesson's questions.

One call does three things in one transaction: scores the answer by the
question's rule, keeps the attempt, and records it as evidence about the
concept. What comes back is what the learner should see: whether it was right,
why the right answer is right, and what the answer changed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from adle_core.application.curriculum import (
    KnowledgeRecord,
    get_concept_or_404,
    knowledge_record,
)
from adle_core.application.learner import LearnerService
from adle_core.application.lessons import LessonService
from adle_core.errors import NotFoundError, ValidationFailedError
from adle_core.evaluation.scoring import MalformedResponseError, Response, Score, score
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import Attempt, LearnerConceptState
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.tracing import Observation, ObservationKind
from adle_core.lessons.ir import guess_probability


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
    ) -> AnswerResult:
        """Score an answer and record it. ``response`` is ``None`` for an explicit skip."""
        lesson = self._lessons.get_lesson(lesson_id)
        item = next(
            (question for question in lesson.questions() if question.id == question_id), None
        )
        if item is None:
            raise NotFoundError("That question is not part of this lesson.")

        if response is None:
            result = Score(outcome=Outcome.SKIPPED)
        else:
            try:
                result = score(item, response)
            except MalformedResponseError as error:
                raise ValidationFailedError(str(error)) from error

        with self._database.session() as session:
            concept = get_concept_or_404(session, item.concept_id)
            earlier = (
                session.scalar(
                    select(func.count(Attempt.id)).where(
                        Attempt.lesson_id == lesson_id,
                        Attempt.question_id == question_id,
                        Attempt.outcome != Outcome.SKIPPED.value,
                    )
                )
                or 0
            )
            # After a first answer the learner has seen the explanation, so a repeat
            # shows recall of that explanation at best. It counts as an aided answer.
            aided = hinted or earlier > 0
            skipped = result.outcome is Outcome.SKIPPED
            transition = self._learner.record_in(
                session,
                concept,
                Observation(
                    kind=ObservationKind.ANSWER,
                    occurred_at=utc_now(),
                    outcome=result.outcome,
                    question_form=None if skipped else item.form,
                    is_transfer=item.is_transfer and not skipped,
                    hinted=aided and not skipped,
                    unsure=(unsure or result.self_assessed) and not skipped,
                    item_guess=None if skipped else guess_probability(item),
                ),
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
                attempt_number=earlier + (0 if skipped else 1),
            )
