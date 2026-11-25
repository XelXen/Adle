"""A course as a file (ADR-063): saved for the learner, and brought in from one.

Every route here is *internal*: only the desktop shell calls it, and the page cannot.

Saving writes the file in a folder of the core's own, under a name the core makes, and says
that name. The shell asks the learner where the file should go, in a window of the operating
system, and moves it there (or removes it, if they back out): the core is never told a
place to write (the one route that is remains ``data.save_copy``). Looking at a file and
bringing one in take the path of a file the learner chose in such a window: a path to read,
which the page cannot name.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from adle_core.application.course_file import CourseFileError
from adle_core.application.course_sharing import Holds
from adle_core.application.services import Services, get_services
from adle_core.errors import NotFoundError, ValidationFailedError

router = APIRouter(tags=["courses"])

INTERNAL = {"x-adle-internal": True}
ServicesDep = Annotated[Services, Depends(get_services)]

#: A course file larger than this is not one Adle made.
MAX_COURSE_FILE_BYTES = 4 * 1024 * 1024 * 1024


class CourseFileHolds(BaseModel):
    """What goes into a file, or is brought in from one. The curriculum always is."""

    model_config = ConfigDict(extra="forbid")

    lessons: StrictBool = True
    #: The documents the course was made from, and their text.
    materials: StrictBool = False
    #: The learner's own: answers, what they showed, where they stopped.
    progress: StrictBool = False
    #: The questions they asked during lessons, and the answers.
    notes: StrictBool = False

    def as_holds(self) -> Holds:
        return Holds(
            lessons=self.lessons,
            materials=self.materials,
            progress=self.progress,
            notes=self.notes,
        )


class CourseFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: A template (the course and its lessons, nothing of the learner) or a transfer
    #: (everything, to carry the course to another computer).
    kind: Literal["template", "transfer"]
    #: What it holds, when the learner chose: otherwise what its kind holds.
    holds: CourseFileHolds | None = None


class CourseFileCounts(BaseModel):
    concepts: int
    lessons: int
    materials: int
    #: Of the materials, how many have the document itself in the file.
    files: int
    progress: bool
    notes: int


class SavedCourseFile(BaseModel):
    #: Its name in the folder of files being handed over. Never a path.
    name: str
    #: What a learner would call the file.
    suggested_name: str
    counts: CourseFileCounts
    #: Lessons still being written or drawn, which were left out.
    lessons_left_out: int


class CourseFilePath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Absolute path of a file the learner chose, as the open dialog returned it.
    path: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")


class CourseFileSummary(BaseModel):
    """What a file says it is, for asking the learner before anything is brought in."""

    title: str
    kind: Literal["template", "transfer"]
    counts: CourseFileCounts
    made_by: str
    made_at: datetime


class CourseFileToBringIn(CourseFilePath):
    holds: CourseFileHolds


class BroughtInCourse(BaseModel):
    course_id: str
    title: str
    concepts: int
    lessons: int
    #: Lessons this Adle could not use, which were left out.
    lessons_left_out: int
    materials: int
    progress: bool
    notes: int


def _chosen(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise ValidationFailedError("The file’s path must be absolute.")
    try:
        if not path.is_file():
            raise NotFoundError("The file could not be opened. It may have been moved.")
        if path.stat().st_size > MAX_COURSE_FILE_BYTES:
            raise CourseFileError()
    except OSError as error:
        raise NotFoundError("The file could not be opened. It may have been moved.") from error
    return path


@router.post(
    "/courses/{course_id}/file",
    operation_id="courses.save_file",
    response_model=SavedCourseFile,
    status_code=201,
    openapi_extra=INTERNAL,
)
def save_course_file(
    course_id: str, body: CourseFileRequest, services: ServicesDep
) -> SavedCourseFile:
    holds = body.holds.as_holds() if body.holds is not None else Holds.of(body.kind)
    saved = services.course_files.save(course_id, body.kind, holds)
    return SavedCourseFile(
        name=saved.name,
        suggested_name=saved.suggested_name,
        counts=CourseFileCounts.model_validate(saved.counts.model_dump()),
        lessons_left_out=saved.lessons_left_out,
    )


@router.post(
    "/course-files/look",
    operation_id="courses.look_at_file",
    response_model=CourseFileSummary,
    openapi_extra=INTERNAL,
)
def look_at_course_file(body: CourseFilePath, services: ServicesDep) -> CourseFileSummary:
    found = services.course_files.look(_chosen(body.path))
    return CourseFileSummary(
        title=found.title,
        kind=found.kind,
        counts=CourseFileCounts.model_validate(found.counts.model_dump()),
        made_by=found.made_by,
        made_at=found.made_at,
    )


@router.post(
    "/course-files/bring-in",
    operation_id="courses.bring_in_file",
    response_model=BroughtInCourse,
    status_code=201,
    openapi_extra=INTERNAL,
)
def bring_in_course_file(body: CourseFileToBringIn, services: ServicesDep) -> BroughtInCourse:
    brought = services.course_files.bring_in(_chosen(body.path), body.holds.as_holds())
    return BroughtInCourse(
        course_id=brought.course_id,
        title=brought.title,
        concepts=brought.concepts,
        lessons=brought.lessons,
        lessons_left_out=brought.lessons_left_out,
        materials=brought.materials,
        progress=brought.progress,
        notes=brought.notes,
    )
