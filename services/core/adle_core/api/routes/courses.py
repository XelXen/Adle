"""Courses, their sources, search, and background jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from adle_core.api import schemas
from adle_core.application.services import Services, get_services
from adle_core.errors import ValidationFailedError
from adle_core.lessons import axioms

router = APIRouter(tags=["courses"])

INTERNAL = {"x-adle-internal": True}
ServicesDep = Annotated[Services, Depends(get_services)]


# -- courses ---------------------------------------------------------------


@router.get("/courses", operation_id="courses.list", response_model=schemas.CourseList)
def list_courses(services: ServicesDep) -> schemas.CourseList:
    courses = [schemas.Course.model_validate(record) for record in services.courses.list_all()]
    return schemas.CourseList(courses=courses)


@router.post(
    "/courses", operation_id="courses.create", response_model=schemas.Course, status_code=201
)
def create_course(body: schemas.CourseCreate, services: ServicesDep) -> schemas.Course:
    if body.origin == "topic" and not body.topic:
        raise ValidationFailedError("Describe the topic you want to learn.")
    record = services.courses.create(
        title=body.title, description=body.description, origin=body.origin, topic=body.topic
    )
    return schemas.Course.model_validate(record)


@router.get("/courses/{course_id}", operation_id="courses.get", response_model=schemas.Course)
def get_course(
    course_id: str,
    services: ServicesDep,
    opened: Annotated[
        bool, Query(description="Record that the learner opened the course.")
    ] = False,
) -> schemas.Course:
    return schemas.Course.model_validate(services.courses.get(course_id, mark_opened=opened))


@router.patch("/courses/{course_id}", operation_id="courses.update", response_model=schemas.Course)
def update_course(
    course_id: str, body: schemas.CourseUpdate, services: ServicesDep
) -> schemas.Course:
    record = services.courses.update(
        course_id, title=body.title, description=body.description, subject=body.subject
    )
    return schemas.Course.model_validate(record)


@router.get("/lesson-rules", operation_id="lessons.rules", response_model=schemas.LessonRules)
def lesson_rules() -> schemas.LessonRules:
    """How a lesson is formed: said to the learner as it is said to a lesson's writer,
    from the one place it is written down (``lessons/axioms.py``)."""
    return schemas.LessonRules(
        rules=axioms.rules_for_learner(),
        subjects=[
            schemas.SubjectWay.model_validate(
                {
                    "key": subject.key,
                    "name": subject.name,
                    "steps": list(subject.steps),
                    "strategies": list(axioms.ways_for(subject.key)),
                }
            )
            for subject in axioms.offered()
        ],
    )


@router.delete("/courses/{course_id}", operation_id="courses.delete", status_code=204)
def delete_course(course_id: str, services: ServicesDep) -> Response:
    # Whatever is being written or read for it stops first: nothing more is asked of a
    # provider for a course the learner is removing. Its film stops too (ADR-065).
    services.films.stop_for_course(course_id)
    services.generation.stop_for_course(course_id)
    services.courses.delete(course_id)
    # Its lessons' recorded narration goes with them (ADR-042).
    services.narration.tidy()
    return Response(status_code=204)


# -- sources ---------------------------------------------------------------


@router.get(
    "/courses/{course_id}/sources",
    operation_id="sources.list",
    response_model=schemas.SourceList,
)
def list_sources(course_id: str, services: ServicesDep) -> schemas.SourceList:
    sources = [
        schemas.Source.model_validate(record)
        for record in services.sources.list_for_course(course_id)
    ]
    return schemas.SourceList(sources=sources)


@router.post(
    "/courses/{course_id}/sources/import",
    operation_id="sources.import_paths",
    response_model=schemas.Job,
    status_code=202,
    # Paths come from the operating system's file picker or a drop, resolved by
    # the desktop shell. Renderer script must never be able to name a path.
    openapi_extra=INTERNAL,
)
def import_sources(
    course_id: str, body: schemas.ImportRequest, services: ServicesDep
) -> schemas.Job:
    paths = [Path(raw) for raw in body.paths]
    if any(not path.is_absolute() for path in paths):
        raise ValidationFailedError("Import paths must be absolute.")
    return schemas.Job.model_validate(services.sources.start_import(course_id, paths))


@router.get("/sources/{source_id}", operation_id="sources.get", response_model=schemas.SourceDetail)
def get_source(source_id: str, services: ServicesDep) -> schemas.SourceDetail:
    return schemas.SourceDetail.model_validate(services.sources.get(source_id))


@router.delete("/sources/{source_id}", operation_id="sources.delete", status_code=204)
def delete_source(source_id: str, services: ServicesDep) -> Response:
    services.sources.delete(source_id)
    return Response(status_code=204)


@router.post(
    "/sources/{source_id}/read-pictures",
    operation_id="sources.read_pictures",
    response_model=schemas.Job,
    status_code=202,
)
def read_pictures(source_id: str, services: ServicesDep) -> schemas.Job:
    """Read the pages of a file that are pictures, at the learner's word (ADR-060)."""
    return schemas.Job.model_validate(services.sources.start_reading(source_id))


@router.get(
    "/courses/{course_id}/search",
    operation_id="sources.search",
    response_model=schemas.SearchResults,
)
def search_sources(
    course_id: str,
    services: ServicesDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> schemas.SearchResults:
    hits = services.sources.search(course_id, q, limit)
    return schemas.SearchResults(
        query=q, hits=[schemas.SearchHit.model_validate(hit) for hit in hits]
    )


# -- jobs ------------------------------------------------------------------


@router.get("/jobs/{job_id}", operation_id="jobs.get", response_model=schemas.Job)
def get_job(job_id: str, services: ServicesDep) -> schemas.Job:
    return schemas.Job.model_validate(services.jobs.get(job_id))


@router.post("/jobs/{job_id}/cancel", operation_id="jobs.cancel", response_model=schemas.Job)
def cancel_job(job_id: str, services: ServicesDep) -> schemas.Job:
    return schemas.Job.model_validate(services.jobs.cancel(job_id))
