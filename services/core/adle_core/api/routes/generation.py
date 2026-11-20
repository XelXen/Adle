"""Asking the model for a curriculum or a lesson.

Both start a background job and return at once. The interface watches the job
(``jobs.get``), may cancel it (``jobs.cancel``), and for a proposal decides
afterwards what, if anything, to add.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from adle_core.api import schemas
from adle_core.application.services import Services, get_services

router = APIRouter(tags=["generation"])

ServicesDep = Annotated[Services, Depends(get_services)]


@router.post(
    "/courses/{course_id}/curriculum/proposal",
    operation_id="generation.propose_curriculum",
    response_model=schemas.Job,
    status_code=202,
)
def propose_curriculum(course_id: str, services: ServicesDep) -> schemas.Job:
    return schemas.Job.model_validate(services.generation.propose_curriculum(course_id))


@router.get(
    "/courses/{course_id}/curriculum/proposal",
    operation_id="generation.latest_proposal",
    response_model=schemas.LatestJob,
)
def latest_proposal(course_id: str, services: ServicesDep) -> schemas.LatestJob:
    """The newest proposal for a course, so one that finished unseen can still be reviewed."""
    job = services.generation.latest_proposal(course_id)
    return schemas.LatestJob(job=schemas.Job.model_validate(job) if job else None)


@router.post(
    "/jobs/{job_id}/dismiss",
    operation_id="generation.dismiss_proposal",
    response_model=schemas.Job,
)
def dismiss_proposal(job_id: str, services: ServicesDep) -> schemas.Job:
    return schemas.Job.model_validate(services.generation.dismiss_proposal(job_id))


@router.post(
    "/jobs/{job_id}/accept",
    operation_id="generation.accept_proposal",
    response_model=schemas.Curriculum,
)
def accept_proposal(
    job_id: str, body: schemas.ProposalAcceptance, services: ServicesDep
) -> schemas.Curriculum:
    return schemas.Curriculum.model_validate(
        services.generation.accept_proposal(job_id, body.selected)
    )


@router.post(
    "/concepts/{concept_id}/lessons",
    operation_id="generation.generate_lesson",
    response_model=schemas.Job,
    status_code=202,
)
def generate_lesson(
    concept_id: str, services: ServicesDep, body: schemas.LessonRequest | None = None
) -> schemas.Job:
    """Start writing a lesson. The body is optional: without it Adle chooses how to teach."""
    strategy = body.strategy if body is not None else None
    return schemas.Job.model_validate(
        services.generation.generate_lesson(concept_id, strategy=strategy)
    )


@router.get(
    "/courses/{course_id}/jobs",
    operation_id="jobs.list_active",
    response_model=schemas.JobList,
)
def list_active_jobs(course_id: str, services: ServicesDep) -> schemas.JobList:
    """Work still in progress for a course, so a screen can pick it up again after navigating."""
    services.courses.get(course_id)
    return schemas.JobList(
        jobs=[schemas.Job.model_validate(job) for job in services.jobs.list_active(course_id)]
    )
