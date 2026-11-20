"""What to do next, how a course is going, practice, and what the learner says about both."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Response as HttpResponse

from adle_core.api import schemas
from adle_core.application.services import Services, get_services
from adle_core.lessons import ir as lesson_ir

router = APIRouter(tags=["learning"])

ServicesDep = Annotated[Services, Depends(get_services)]


@router.get(
    "/courses/{course_id}/learning",
    operation_id="learning.overview",
    response_model=schemas.LearningOverview,
)
def learning_overview(course_id: str, services: ServicesDep) -> schemas.LearningOverview:
    """The suggested next step with its reason, the alternatives, and where each concept stands."""
    return schemas.LearningOverview.model_validate(services.learning.overview(course_id))


@router.post(
    "/concepts/{concept_id}/practice",
    operation_id="learning.start_practice",
    response_model=schemas.PracticeSet,
)
def start_practice(
    concept_id: str, body: schemas.PracticeRequest, services: ServicesDep
) -> schemas.PracticeSet:
    """Questions worth asking about a concept now. May be empty; the reason says why."""
    practice = services.learning.start_practice(concept_id, about=body.about, count=body.count)
    return schemas.PracticeSet.model_validate(practice)


@router.post(
    "/concepts/{concept_id}/hypotheses/{kind}/dismiss",
    operation_id="learning.dismiss_hypothesis",
    response_model=schemas.LearningOverview,
)
def dismiss_hypothesis(
    concept_id: str, kind: lesson_ir.MisconceptionKind, services: ServicesDep
) -> schemas.LearningOverview:
    """The learner says a suspected mistake does not describe them."""
    return schemas.LearningOverview.model_validate(
        services.learning.dismiss_hypothesis(concept_id, kind)
    )


@router.post(
    "/lessons/{lesson_id}/unhelpful",
    operation_id="lessons.report_unhelpful",
    status_code=204,
)
def report_unhelpful(
    lesson_id: str, body: schemas.UnhelpfulReport, services: ServicesDep
) -> HttpResponse:
    """The learner says an explanation did not help. It shapes what is suggested next."""
    services.learning.report_unhelpful(lesson_id, body.segment_id)
    return HttpResponse(status_code=204)
