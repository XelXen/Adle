"""Lessons: listing them, loading one for the player, and remembering progress."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Response as HttpResponse

from adle_core.api import schemas
from adle_core.application.asks import MAX_ASKS_PER_LESSON
from adle_core.application.services import Services, get_services
from adle_core.evaluation.scoring import Response
from adle_core.lessons.player import player_view

router = APIRouter(tags=["lessons"])

ServicesDep = Annotated[Services, Depends(get_services)]


@router.post(
    "/courses/sample",
    operation_id="courses.install_sample",
    response_model=schemas.Course,
)
def install_sample_course(services: ServicesDep) -> schemas.Course:
    """Add the sample course that ships with Adle, or return it if it is already there."""
    return schemas.Course.model_validate(services.sample_course.install())


@router.get(
    "/courses/{course_id}/lessons",
    operation_id="lessons.list",
    response_model=schemas.LessonList,
)
def list_lessons(course_id: str, services: ServicesDep) -> schemas.LessonList:
    lessons = services.lessons.list_for_course(course_id)
    return schemas.LessonList(
        lessons=[schemas.LessonSummary.model_validate(lesson) for lesson in lessons]
    )


@router.get(
    "/lessons/{lesson_id}",
    operation_id="lessons.get",
    response_model=schemas.LessonForPlayer,
)
def get_lesson(lesson_id: str, services: ServicesDep) -> schemas.LessonForPlayer:
    loaded = services.lessons.get(lesson_id)
    return schemas.LessonForPlayer(
        lesson=player_view(loaded.lesson, services.item_mask),
        scenes=loaded.scenes,
        origin=loaded.origin,
        progress=schemas.LessonProgress.model_validate(loaded.progress),
        pending_scene_ids=loaded.pending_scene_ids,
        written_by=(
            schemas.LessonAuthor.model_validate(loaded.written_by) if loaded.written_by else None
        ),
    )


@router.put(
    "/lessons/{lesson_id}/progress",
    operation_id="lessons.save_progress",
    response_model=schemas.LessonProgress,
)
def save_progress(
    lesson_id: str, body: schemas.LessonProgressUpdate, services: ServicesDep
) -> schemas.LessonProgress:
    progress = services.lessons.save_progress(lesson_id, body.position, completed=body.completed)
    return schemas.LessonProgress.model_validate(progress)


@router.post(
    "/lessons/{lesson_id}/questions/{question_id}/answer",
    operation_id="lessons.answer",
    response_model=schemas.AnswerResult,
)
def answer_question(
    lesson_id: str, question_id: str, body: schemas.AnswerRequest, services: ServicesDep
) -> schemas.AnswerResult:
    """Score an answer, keep it, and record it as evidence about the concept."""
    response = (
        None
        if body.skipped
        else Response(
            option_id=body.option_id,
            truth=body.truth,
            number=body.number,
            text=body.text,
            order=tuple(body.order) if body.order is not None else None,
            covered=tuple(body.covered) if body.covered is not None else None,
        )
    )
    result = services.assessment.answer(
        lesson_id, question_id, response, hinted=body.hinted, unsure=body.unsure
    )
    return schemas.AnswerResult.model_validate(result)


@router.post(
    "/lessons/{lesson_id}/asks",
    operation_id="lessons.ask",
    response_model=schemas.Job,
    status_code=202,
)
def ask_about_lesson(
    lesson_id: str, body: schemas.AskRequest, services: ServicesDep
) -> schemas.Job:
    """Ask Adle something about one part of a lesson. The answer is written by a model.

    Starts a job and returns at once. When it has finished, the answer is among
    ``lessons.list_asks``.
    """
    return schemas.Job.model_validate(
        services.generation.ask(lesson_id, body.segment_id, body.question)
    )


@router.get(
    "/lessons/{lesson_id}/asks",
    operation_id="lessons.list_asks",
    response_model=schemas.AskList,
)
def list_asks(lesson_id: str, services: ServicesDep) -> schemas.AskList:
    """Everything the learner has asked about this lesson, oldest first."""
    return schemas.AskList(
        asks=[schemas.Ask.model_validate(ask) for ask in services.asks.list_for_lesson(lesson_id)],
        limit=MAX_ASKS_PER_LESSON,
    )


@router.delete(
    "/lessons/{lesson_id}/asks/{ask_id}", operation_id="lessons.delete_ask", status_code=204
)
def delete_ask(lesson_id: str, ask_id: str, services: ServicesDep) -> HttpResponse:
    services.asks.delete(lesson_id, ask_id)
    return HttpResponse(status_code=204)


@router.delete("/lessons/{lesson_id}", operation_id="lessons.delete", status_code=204)
def delete_lesson(lesson_id: str, services: ServicesDep) -> HttpResponse:
    services.lessons.delete(lesson_id)
    # Its pictures may still have been on their way (ADR-031): that work stops with it.
    services.generation.stop_for_lesson(lesson_id)
    # And its recorded narration goes (ADR-042).
    services.narration.forget(lesson_id)
    return HttpResponse(status_code=204)
