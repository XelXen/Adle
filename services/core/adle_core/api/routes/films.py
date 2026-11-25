"""A film of a whole course (ADR-065), and the film maker that makes it.

The page asks whether the film maker is set up, sets it up (at the learner's word: it is
downloaded) or takes it away, asks what a course's film would be and how it stands, begins
or continues it, removes it, and fetches it to play: the video a part at a time, and its
words. A film is named by the core and never by a path. Saving one where the learner
chooses is internal: the core writes it in a folder of its own and the desktop shell
moves it, as for a course file (ADR-063).
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from adle_core.api import schemas
from adle_core.application.films import FilmPlan, FilmRecord
from adle_core.application.services import Services, get_services

router = APIRouter(tags=["films"])

INTERNAL = {"x-adle-internal": True}
ServicesDep = Annotated[Services, Depends(get_services)]


class FilmMakerStatus(BaseModel):
    """Whether the film maker is on this computer, and what setting it up takes."""

    ready: bool
    #: It runs on this kind of computer.
    fits: bool
    #: Set up by a developer elsewhere: used as it is, never removed from here.
    borrowed: bool
    #: The setup under way, if there is one.
    setting_up: schemas.Job | None
    #: What setting it up downloads, and about what it then takes on the disk.
    download_bytes: int
    installed_bytes: int
    #: Where a setup downloads from, as a person would name each place.
    sources: list[str]


class FilmChapter(BaseModel):
    title: str
    #: ``waiting`` to be written, ``writing`` now (several at once where the provider takes
    #: several requests at once, ADR-068), ``written`` by the AI and checked, or
    #: ``in_words``: told in words by Adle, when no version the AI wrote would run.
    state: Literal["waiting", "writing", "written", "in_words"]
    #: How many problems of layout are still in it, for a chapter the AI wrote.
    problems: int
    #: When it begins in the video, once the film is made.
    start: float | None


class Film(BaseModel):
    id: str
    #: ``making``, ``unfinished`` (stopped, failed, or left when Adle closed: it can be
    #: continued), or ``ready`` to watch.
    status: Literal["making", "unfinished", "ready"]
    title: str
    chapters: list[FilmChapter]
    #: The natural voice it is read in, by its name; none for a film without a voice.
    voice: str | None
    seconds: float | None
    size: int | None
    #: Sentences for the learner about how it was made.
    notes: list[str]
    #: Which provider and model wrote its chapters (see ``schemas.Job`` results).
    written_by: dict[str, Any]
    #: Why it is unfinished, when it is.
    reason: str | None
    created_at: datetime | None
    finished_at: datetime | None
    #: The work under way on it, if any.
    making: schemas.Job | None


class FilmPlanOut(BaseModel):
    """What a film of the course would be, before it is begun or continued."""

    chapters: list[str]
    #: The most requests it may send: each chapter once, three more to mend it, and one to
    #: look over its pictures when they are looked over.
    requests_at_most: int
    #: The natural voice it would be read in; none for a film without a voice.
    voice: str | None
    #: Why it cannot be made now, in a sentence.
    blocked: str | None
    #: Whether each chapter's pictures are looked over by a model that sees them (ADR-066).
    checks_pictures: bool


class CourseFilm(BaseModel):
    plan: FilmPlanOut
    film: Film | None


class FilmVideoPart(BaseModel):
    """A part of a film's video, for the page to put together and play."""

    part: int
    parts: int
    size: int
    mime: Literal["video/mp4"]
    #: The bytes, in base 64.
    data: str


class FilmCue(BaseModel):
    start: float
    end: float
    text: str


class FilmCaptions(BaseModel):
    cues: list[FilmCue]


class SavedFilmFile(BaseModel):
    """A film written for the desktop shell to move where the learner chose."""

    file_name: str
    captions_name: str | None
    suggested_name: str


def _maker(services: Services) -> FilmMakerStatus:
    status = services.films.engine_status()
    return FilmMakerStatus(
        ready=status.ready,
        fits=status.fits,
        borrowed=status.borrowed,
        setting_up=schemas.Job.model_validate(status.setting_up) if status.setting_up else None,
        download_bytes=status.download_bytes,
        installed_bytes=status.installed_bytes,
        sources=list(status.sources),
    )


def _plan(plan: FilmPlan) -> FilmPlanOut:
    return FilmPlanOut(
        chapters=plan.chapters,
        requests_at_most=plan.requests_at_most,
        voice=plan.voice,
        blocked=plan.blocked,
        checks_pictures=plan.checks_pictures,
    )


def _film(film: FilmRecord) -> Film:
    return Film(
        id=film.id,
        status=film.status,
        title=film.title,
        chapters=[
            FilmChapter(
                title=chapter.title,
                state=chapter.state,
                problems=chapter.problems,
                start=chapter.start,
            )
            for chapter in film.chapters
        ],
        voice=film.voice,
        seconds=film.seconds,
        size=film.size,
        notes=film.notes,
        written_by=film.written_by,
        reason=film.reason,
        created_at=film.created_at,
        finished_at=film.finished_at,
        making=schemas.Job.model_validate(film.making) if film.making else None,
    )


@router.get("/film-maker", operation_id="films.maker_status", response_model=FilmMakerStatus)
def film_maker_status(services: ServicesDep) -> FilmMakerStatus:
    return _maker(services)


@router.post(
    "/film-maker/setup",
    operation_id="films.set_up_maker",
    response_model=schemas.Job,
    status_code=202,
)
def set_up_film_maker(services: ServicesDep) -> schemas.Job:
    """Set the film maker up: it is downloaded, at the learner's word (ADR-065)."""
    return schemas.Job.model_validate(services.films.install())


@router.delete("/film-maker", operation_id="films.remove_maker", response_model=FilmMakerStatus)
def remove_film_maker(services: ServicesDep) -> FilmMakerStatus:
    services.films.remove_engine()
    return _maker(services)


@router.get("/films/making", operation_id="films.making", response_model=schemas.JobList)
def films_being_made(services: ServicesDep) -> schemas.JobList:
    """Films being made, and the film maker being set up, in any course: for the app to
    say so wherever the learner is, and that a film is ready when it is."""
    return schemas.JobList(
        jobs=[schemas.Job.model_validate(job) for job in services.films.making()]
    )


@router.get("/courses/{course_id}/film", operation_id="films.get", response_model=CourseFilm)
def course_film(course_id: str, services: ServicesDep) -> CourseFilm:
    plan = services.films.plan(course_id)
    film = services.films.film_of(course_id)
    return CourseFilm(plan=_plan(plan), film=_film(film) if film is not None else None)


@router.post(
    "/courses/{course_id}/film",
    operation_id="films.make",
    response_model=schemas.Job,
    status_code=202,
)
def make_film(course_id: str, services: ServicesDep) -> schemas.Job:
    """Begin the course's film, or continue it where it was left."""
    return schemas.Job.model_validate(services.films.make(course_id))


@router.delete("/courses/{course_id}/film", operation_id="films.remove", status_code=204)
def remove_film(course_id: str, services: ServicesDep) -> Response:
    services.films.remove(course_id)
    return Response(status_code=204)


@router.get(
    "/films/{film_id}/video/{part}",
    operation_id="films.video_part",
    response_model=FilmVideoPart,
)
def film_video_part(film_id: str, part: int, services: ServicesDep) -> FilmVideoPart:
    found = services.films.video_part(film_id, part)
    return FilmVideoPart(
        part=found.part,
        parts=found.parts,
        size=found.size,
        mime="video/mp4",
        data=base64.b64encode(found.data).decode("ascii"),
    )


@router.get("/films/{film_id}/captions", operation_id="films.captions", response_model=FilmCaptions)
def film_captions(film_id: str, services: ServicesDep) -> FilmCaptions:
    return FilmCaptions(
        cues=[
            FilmCue(start=start, end=end, text=text)
            for start, end, text in services.films.captions(film_id)
        ]
    )


@router.post(
    "/films/{film_id}/file",
    operation_id="films.save_file",
    response_model=SavedFilmFile,
    openapi_extra=INTERNAL,
)
def save_film_file(film_id: str, services: ServicesDep) -> SavedFilmFile:
    """Write a film, and its subtitles, where the desktop shell collects them."""
    saved = services.films.save(film_id)
    return SavedFilmFile(
        file_name=saved.file_name,
        captions_name=saved.captions_name,
        suggested_name=saved.suggested_name,
    )
