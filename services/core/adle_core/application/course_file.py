"""A course as a file (ADR-063): what is in one, and reading one that may come from anywhere.

A course file is a zip of a few JSON documents, and, when the learner asks for them, the
files the course was made from:

    adle-course.json        what this is, and what is in it
    curriculum.json         the concepts: objectives, what each needs first, where it is covered
    lessons/0001.json       a lesson (the Lesson IR) and its scenes, one file a lesson
    materials/0001.json     an imported document: its sections and passages
    materials/0001.file     that document as it was imported, if it was put in
    progress.json           the learner's own: answers, what they showed, where they stopped
    notes.json              the questions they asked during lessons, and the answers

Two kinds are made (the learner can change what either holds): a *template*, the course and
its lessons with nothing of the learner in it, for someone else to start from; and a
*transfer*, everything, to carry a course to another computer.

Reading is written for a file from anywhere. Nothing is ever extracted: a member is read
by a name this module made (a name in the file is never a path), up to a bound on its size
that does not trust what the file says its size is, and what is read is checked against a
closed description of it, unknown fields refused. Identifiers in a file are only names for
its own parts to refer to each other: whoever brings a course in gives everything new ones.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from adle_core.errors import AdleError

FORMAT: Final = "adle-course"
VERSION: Final = 1
MANIFEST: Final = "adle-course.json"
CURRICULUM: Final = "curriculum.json"
PROGRESS: Final = "progress.json"
NOTES: Final = "notes.json"

MAX_LESSONS: Final = 600
MAX_MATERIALS: Final = 200
#: The most a file may hold, as it is read: each kind of part, and all of it together.
MAX_MANIFEST_BYTES: Final = 64 * 1024
MAX_CURRICULUM_BYTES: Final = 8 * 1024 * 1024
MAX_LESSON_BYTES: Final = 2 * 1024 * 1024
MAX_MATERIAL_BYTES: Final = 48 * 1024 * 1024
MAX_PROGRESS_BYTES: Final = 32 * 1024 * 1024
MAX_NOTES_BYTES: Final = 16 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 2 * 1024 * 1024 * 1024
_BLOCK: Final = 1024 * 1024

_LESSON = re.compile(r"^lessons/(\d{4})\.json$")
_MATERIAL = re.compile(r"^materials/(\d{4})\.json$")
_ORIGINAL = re.compile(r"^materials/(\d{4})\.file$")


class CourseFileError(AdleError):
    """The file is not a course Adle made, or it is damaged."""

    status_code = 422
    code = "course_file_invalid"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "This file isn’t an Adle course, or it is damaged. Nothing was imported."
        )


class CourseFileNewerError(CourseFileError):
    code = "course_file_newer"

    def __init__(self) -> None:
        super().__init__(
            "This course was saved by a newer version of Adle. Update Adle to import it."
        )


# -- what is in a file --------------------------------------------------------------------------


class _Part(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,5}_[0-9a-f]{20}$")]
Line = Annotated[str, StringConstraints(max_length=400)]
Words = Annotated[str, StringConstraints(max_length=8_000)]
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Kind = Literal["template", "transfer"]


class Counts(_Part):
    """What a file holds, as its maker counted it: shown before anything is brought in, and
    never relied on."""

    concepts: int = Field(ge=0, le=10_000)
    lessons: int = Field(ge=0, le=10_000)
    materials: int = Field(ge=0, le=10_000)
    #: Of the materials, how many have the document itself in the file.
    files: int = Field(ge=0, le=10_000)
    progress: bool
    notes: int = Field(ge=0, le=100_000)


class CoursePart(_Part):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Words = ""
    topic: Words | None = None
    subject: Annotated[str, StringConstraints(max_length=30)] = "general"
    #: Adle placed the subject; false when the learner chose it.
    subject_by_adle: bool = True


class Manifest(_Part):
    format: Literal["adle-course"]
    version: int = Field(ge=1, le=1_000)
    kind: Kind
    #: The Adle that made it, as it names itself.
    made_by: Annotated[str, StringConstraints(max_length=60)]
    made_at: datetime
    course: CoursePart
    counts: Counts


class ObjectivePart(_Part):
    id: Identifier
    statement: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)
    ]


class NeedPart(_Part):
    concept_id: Identifier
    reason: Words = ""
    origin: Literal["learner", "outline", "model", "sample"] = "learner"


class ConceptPart(_Part):
    id: Identifier
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    summary: Words = ""
    complexity: int = Field(default=2, ge=1, le=3)
    tags: list[Annotated[str, StringConstraints(max_length=30)]] = Field(
        default_factory=list, max_length=8
    )
    origin: Literal["learner", "outline", "model", "sample"] = "learner"
    objectives: list[ObjectivePart] = Field(default_factory=list, max_length=12)
    needs: list[NeedPart] = Field(default_factory=list, max_length=12)
    #: Sections of the materials where it is covered.
    sections: list[Identifier] = Field(default_factory=list, max_length=24)


class Curriculum(_Part):
    concepts: list[ConceptPart] = Field(default_factory=list, max_length=200)


class ScenePart(_Part):
    id: Annotated[str, StringConstraints(pattern=r"^scn_[a-z0-9_]{1,40}$")]
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    source: Annotated[str, StringConstraints(min_length=1, max_length=40_000)]


class LessonPart(_Part):
    #: The lesson as the Lesson IR has it. It is given new identifiers and then put through
    #: ``lessons.bundle.parse_bundle`` like any lesson: nothing of it is trusted here.
    lesson: dict[str, Any]
    scenes: list[ScenePart] = Field(default_factory=list, max_length=14)
    #: Who wrote it, as it was recorded: names only.
    written_by: dict[str, Any] | None = None


class SectionPart(_Part):
    id: Identifier
    kind: Literal["document", "page", "heading"]
    title: Annotated[str, StringConstraints(max_length=300)] | None = None
    page_number: int | None = Field(default=None, ge=1, le=1_000_000)
    level: int | None = Field(default=None, ge=1, le=12)
    char_count: int = Field(default=0, ge=0, le=100_000_000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ChunkPart(_Part):
    #: The section it is a passage of, by where that section stands in ``sections``.
    section: int = Field(ge=0, le=100_000)
    text: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    char_start: int = Field(ge=0, le=100_000_000)
    char_end: int = Field(ge=0, le=100_000_000)
    content_hash: Hash


class SourcePart(_Part):
    id: Identifier
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    kind: Literal["pdf", "docx", "markdown", "text", "authored"]
    content_hash: Hash
    size_bytes: int = Field(ge=0, le=10_000_000_000)
    warnings: list[Annotated[str, StringConstraints(max_length=600)]] = Field(
        default_factory=list, max_length=60
    )
    picture_pages: list[Annotated[int, Field(ge=1, le=1_000_000)]] = Field(
        default_factory=list, max_length=20_000
    )
    parser: Annotated[str, StringConstraints(max_length=40)]
    parser_version: Annotated[str, StringConstraints(max_length=40)]
    char_count: int = Field(default=0, ge=0, le=1_000_000_000)
    sections: list[SectionPart] = Field(default_factory=list, max_length=20_000)
    chunks: list[ChunkPart] = Field(default_factory=list, max_length=60_000)


class ObservationPart(_Part):
    concept_id: Identifier
    occurred_at: datetime
    kind: Literal["answer", "self_report", "dismissal"]
    outcome: Literal["correct", "partial", "incorrect", "skipped"] | None = None
    question_form: Annotated[str, StringConstraints(max_length=30)] | None = None
    is_transfer: bool = False
    hinted: bool = False
    unsure: bool = False
    item_guess: float | None = Field(default=None, ge=0.0, le=1.0)
    slip: bool = False
    self_report: Literal["new", "some", "confident"] | None = None
    unresolved_misconception: bool | None = None


class AttemptPart(_Part):
    lesson_id: Identifier
    concept_id: Identifier
    question_id: Annotated[str, StringConstraints(pattern=r"^q_[a-z0-9_]{1,40}$")]
    form: Annotated[str, StringConstraints(max_length=30)]
    outcome: Literal["correct", "partial", "incorrect", "skipped"]
    hinted: bool = False
    unsure: bool = False
    misconception: Annotated[str, StringConstraints(max_length=40)] | None = None
    reveals: list[Annotated[str, StringConstraints(max_length=40)]] = Field(
        default_factory=list, max_length=16
    )
    created_at: datetime


class EventPart(_Part):
    concept_id: Identifier | None = None
    lesson_id: Identifier | None = None
    occurred_at: datetime
    kind: Literal[
        "misconception_dismissed",
        "explanation_unhelpful",
        "lesson_completed",
        "explanation_unhelpful_withdrawn",
    ]
    #: A few named facts, each short: the kind of mistake, the part of the lesson.
    detail: dict[
        Annotated[str, StringConstraints(max_length=40)],
        Annotated[str, StringConstraints(max_length=80)] | int | bool | None,
    ] = Field(default_factory=dict, max_length=8)


class LessonPlace(_Part):
    lesson_id: Identifier
    position: int = Field(ge=0, le=100)
    completed: bool = False


class Progress(_Part):
    observations: list[ObservationPart] = Field(default_factory=list, max_length=100_000)
    attempts: list[AttemptPart] = Field(default_factory=list, max_length=100_000)
    events: list[EventPart] = Field(default_factory=list, max_length=50_000)
    lessons: list[LessonPlace] = Field(default_factory=list, max_length=MAX_LESSONS)


class AskPart(_Part):
    lesson_id: Identifier
    segment_id: Annotated[str, StringConstraints(pattern=r"^seg_[a-z0-9_]{1,40}$")]
    question: Annotated[str, StringConstraints(max_length=2_000)]
    answer: dict[str, Any] = Field(default_factory=dict)
    written_by: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Notes(_Part):
    asks: list[AskPart] = Field(default_factory=list, max_length=20_000)


# -- a file that has been read -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CourseFile:
    manifest: Manifest
    curriculum: Curriculum
    lessons: tuple[LessonPart, ...]
    materials: tuple[SourcePart, ...]
    #: Which materials have the document itself in the file: by where each stands in
    #: ``materials``, the member that holds it.
    originals: dict[int, str]
    progress: Progress | None
    notes: Notes | None


def _numbered(kind: str, index: int, ending: str) -> str:
    return f"{kind}/{index + 1:04d}.{ending}"


def lesson_member(index: int) -> str:
    return _numbered("lessons", index, "json")


def material_member(index: int) -> str:
    return _numbered("materials", index, "json")


def original_member(index: int) -> str:
    return _numbered("materials", index, "file")


class _Reader:
    """A zip being read: a member by a name this module made, never past a bound."""

    def __init__(self, archive: zipfile.ZipFile) -> None:
        self._archive = archive
        self._read = 0
        infos = archive.infolist()
        if len(infos) > 2 * (MAX_LESSONS + MAX_MATERIALS) + 8:
            raise CourseFileError()
        self._members: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            if info.is_dir() or info.flag_bits & 0x1 or info.filename in self._members:
                # A folder (Adle writes none), a member locked with a password, or two
                # members of one name.
                raise CourseFileError()
            self._members[info.filename] = info

    def names(self) -> list[str]:
        return list(self._members)

    def has(self, name: str) -> bool:
        return name in self._members

    def blocks(self, name: str, limit: int) -> Iterator[bytes]:
        """A member's bytes, a block at a time: never more than ``limit``, whatever the
        file says its size is, and never more than a file may hold in all."""
        info = self._members.get(name)
        if info is None or info.file_size > limit:
            raise CourseFileError()
        taken = 0
        try:
            with self._archive.open(info) as member:
                while block := member.read(_BLOCK):
                    taken += len(block)
                    self._read += len(block)
                    if taken > limit or self._read > MAX_TOTAL_BYTES:
                        raise CourseFileError()
                    yield block
        except (zipfile.BadZipFile, OSError, EOFError, RuntimeError, ValueError) as error:
            raise CourseFileError() from error

    def document(self, name: str, limit: int) -> Any:
        try:
            return json.loads(b"".join(self.blocks(name, limit)).decode("utf-8"))
        except (ValueError, RecursionError) as error:
            raise CourseFileError() from error


def _checked[Model: BaseModel](model: type[Model], raw: Any) -> Model:
    try:
        return model.model_validate(raw)
    except (ValidationError, RecursionError) as error:
        raise CourseFileError() from error


def _open(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        raise CourseFileError() from error


def _manifest(reader: _Reader) -> Manifest:
    if not reader.has(MANIFEST):
        raise CourseFileError()
    raw = reader.document(MANIFEST, MAX_MANIFEST_BYTES)
    if isinstance(raw, dict) and raw.get("format") == FORMAT:
        version = raw.get("version")
        if isinstance(version, int) and not isinstance(version, bool) and version > VERSION:
            raise CourseFileNewerError()
    manifest = _checked(Manifest, raw)
    if manifest.version != VERSION:
        raise CourseFileError()
    return manifest


def read_manifest(path: Path) -> Manifest:
    """What a file says it is, and what it says is in it: for asking the learner before
    anything is brought in."""
    with _open(path) as archive:
        return _manifest(_Reader(archive))


def read_course_file(path: Path) -> CourseFile:
    """Everything in a course file but the documents themselves, each part checked."""
    with _open(path) as archive:
        reader = _Reader(archive)
        manifest = _manifest(reader)
        lessons: dict[int, str] = {}
        materials: dict[int, str] = {}
        originals: dict[int, str] = {}
        for name in reader.names():
            for pattern, found in (
                (_LESSON, lessons),
                (_MATERIAL, materials),
                (_ORIGINAL, originals),
            ):
                matched = pattern.match(name)
                if matched:
                    found[int(matched.group(1)) - 1] = name
                    break
            else:
                if name not in (MANIFEST, CURRICULUM, PROGRESS, NOTES):
                    # Nothing is in a course file that this module did not put there.
                    raise CourseFileError()
        if (
            len(lessons) > MAX_LESSONS
            or len(materials) > MAX_MATERIALS
            or sorted(lessons) != list(range(len(lessons)))
            or sorted(materials) != list(range(len(materials)))
            or not set(originals) <= set(materials)
            or not reader.has(CURRICULUM)
        ):
            raise CourseFileError()
        return CourseFile(
            manifest=manifest,
            curriculum=_checked(Curriculum, reader.document(CURRICULUM, MAX_CURRICULUM_BYTES)),
            lessons=tuple(
                _checked(LessonPart, reader.document(lessons[index], MAX_LESSON_BYTES))
                for index in range(len(lessons))
            ),
            materials=tuple(
                _checked(SourcePart, reader.document(materials[index], MAX_MATERIAL_BYTES))
                for index in range(len(materials))
            ),
            originals=originals,
            progress=(
                _checked(Progress, reader.document(PROGRESS, MAX_PROGRESS_BYTES))
                if reader.has(PROGRESS)
                else None
            ),
            notes=(
                _checked(Notes, reader.document(NOTES, MAX_NOTES_BYTES))
                if reader.has(NOTES)
                else None
            ),
        )


def copy_original(path: Path, member: str, out: IO[bytes], limit: int) -> None:
    """One document of a course file, written to ``out``: never more than ``limit``."""
    if not _ORIGINAL.match(member):
        raise CourseFileError()
    with _open(path) as archive:
        for block in _Reader(archive).blocks(member, limit):
            out.write(block)


# -- writing one ---------------------------------------------------------------------------------


def _document(part: BaseModel) -> bytes:
    return json.dumps(part.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")


def write_course_file(
    path: Path,
    *,
    manifest: Manifest,
    curriculum: Curriculum,
    lessons: list[LessonPart],
    materials: list[tuple[SourcePart, Path | None]],
    progress: Progress | None,
    notes: Notes | None,
) -> None:
    """Write a course file at ``path``: each material with the document itself where one
    is given."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(MANIFEST, _document(manifest))
        archive.writestr(CURRICULUM, _document(curriculum))
        for index, lesson in enumerate(lessons):
            archive.writestr(lesson_member(index), _document(lesson))
        for index, (source, original) in enumerate(materials):
            archive.writestr(material_member(index), _document(source))
            if original is not None:
                # A PDF or a Word file is packed already: stored as it is.
                archive.write(original, original_member(index), compress_type=zipfile.ZIP_STORED)
        if progress is not None:
            archive.writestr(PROGRESS, _document(progress))
        if notes is not None:
            archive.writestr(NOTES, _document(notes))
