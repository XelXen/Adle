"""Asking the model for a curriculum or a lesson.

Both start a background job and return at once. The interface watches the job
(``jobs.get``), may cancel it (``jobs.cancel``), and for a proposal decides
afterwards what, if anything, to add.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from adle_core.api import schemas
from adle_core.application.scene_trials import TrialFailure
from adle_core.application.services import Services, get_services

router = APIRouter(tags=["generation"])

ServicesDep = Annotated[Services, Depends(get_services)]


@router.post(
    "/courses/{course_id}/curriculum/proposal",
    operation_id="generation.propose_curriculum",
    response_model=schemas.Job,
    status_code=202,
)
def propose_curriculum(
    course_id: str, services: ServicesDep, body: schemas.ProposalRequest | None = None
) -> schemas.Job:
    setup = body.setup if body is not None else False
    return schemas.Job.model_validate(
        services.generation.propose_curriculum(course_id, setup=setup)
    )


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


@router.get("/scene-trials", operation_id="scenes.trials", response_model=schemas.SceneTrialList)
def scene_trials(services: ServicesDep) -> schemas.SceneTrialList:
    """Pictures to try in the player before a learner is shown them (ADR-038).

    The app asks while a lesson is being written; asking is also how it says that it is
    there to try them.
    """
    return schemas.SceneTrialList(
        trials=[
            schemas.SceneTrial(
                id=trial.id,
                scene_class=trial.scene_class,
                source=trial.source,
                interactive=trial.interactive,
                controls=list(trial.controls),
                steps=trial.steps,
            )
            for trial in services.generation.trials.waiting()
        ]
    )


@router.post("/scene-trials/{trial_id}", operation_id="scenes.report_trial", status_code=204)
def report_scene_trial(
    trial_id: str, body: schemas.SceneTrialReport, services: ServicesDep
) -> Response:
    """How a trial went. A report nobody is waiting for any more is let go."""
    failure = (
        None if body.passed else TrialFailure(stage=body.stage or "runtime", message=body.message)
    )
    services.generation.trials.report(trial_id, failure)
    return Response(status_code=204)


@router.get("/jobs", operation_id="jobs.list_writing", response_model=schemas.JobList)
def list_writing(services: ServicesDep) -> schemas.JobList:
    """Lessons and lists of concepts being written, in any course.

    So that the app can say, wherever the learner is, that something is on its way.
    """
    return schemas.JobList(
        jobs=[schemas.Job.model_validate(job) for job in services.generation.writing()]
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
