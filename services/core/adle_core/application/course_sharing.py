"""A course saved as a file, and brought in from one (ADR-063).

Saving reads a course and writes what the learner asked to be in the file. Bringing one in
makes a *new* course, always: nothing in a file can name, change or replace anything that is
here. Everything is given identifiers of its own, and goes in by the roads everything else
goes in by: the curriculum through ``CurriculumService`` (so it stays learnable), a lesson
through ``lessons.bundle.parse_bundle`` and ``LessonService.store`` (so its scenes pass the
policy and its references resolve), what the learner showed through
``LearnerService.replay`` (so every state is worked out here, from the answers, and none is
taken from the file). A lesson that cannot be used is left out and counted; half a course
is removed again.
"""

from __future__ import annotations

import hashlib
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from adle_core import logs
from adle_core.application import course_file as files
from adle_core.application.asks import MAX_ASKS_PER_LESSON, AskCitation, AskService
from adle_core.application.courses import CourseService, get_course_or_404
from adle_core.application.curriculum import CurriculumService
from adle_core.application.learner import LearnerService
from adle_core.application.lessons import LessonService
from adle_core.application.sources import CopiedSource, SourceService
from adle_core.errors import AdleError, ValidationFailedError
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import (
    CONCEPT_TAGS,
    Attempt,
    Concept,
    LearnerEvent,
    LearnerObservation,
    LessonAsk,
    LessonProgress,
    Source,
    StoredLesson,
)
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.tracing import Observation, ObservationKind, SelfReport
from adle_core.lessons.bundle import parse_bundle
from adle_core.lessons.ir import MISCONCEPTION_KINDS, QUESTION_FORMS, Lesson, is_plain_text

logger = logging.getLogger(__name__)

#: A file being handed to the desktop shell, by the only kind of name it may have.
HANDED_OVER = re.compile(r"^course-[0-9a-f]{20}\.zip$")
_ID = re.compile(r"^[a-z]{2,5}_[0-9a-f]{20}$")
#: Characters a file name may not have on one system or another.
_NOT_IN_A_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class Holds:
    """What goes into a file, or is brought in from one. The curriculum always is."""

    lessons: bool = True
    #: The documents the course was made from, and their text.
    materials: bool = False
    #: The learner's own: answers, what they showed, where they stopped.
    progress: bool = False
    #: The questions they asked during lessons, and the answers.
    notes: bool = False

    @classmethod
    def of(cls, kind: str) -> Holds:
        """What each kind of file holds unless the learner says otherwise: a template the
        course and its lessons, a transfer everything."""
        whole = kind == "transfer"
        return cls(lessons=True, materials=whole, progress=whole, notes=whole)


@dataclass(frozen=True, slots=True)
class SavedCourse:
    #: Its name in the folder of files being handed over. Never a path.
    name: str
    #: What a learner would call the file.
    suggested_name: str
    counts: files.Counts
    #: Lessons still being written or drawn, which were left out.
    lessons_left_out: int


@dataclass(frozen=True, slots=True)
class CourseInFile:
    """What a file says it is, for asking the learner before anything is brought in."""

    title: str
    kind: str
    counts: files.Counts
    made_by: str
    made_at: datetime


@dataclass(frozen=True, slots=True)
class BroughtIn:
    course_id: str
    title: str
    concepts: int
    lessons: int
    #: Lessons this Adle could not use, which were left out.
    lessons_left_out: int
    materials: int
    progress: bool
    notes: int


def file_name_for(title: str) -> str:
    """A course's name as a file's: nothing a file name may not have, and not too long."""
    plain = " ".join(_NOT_IN_A_NAME.sub(" ", title).split()).strip(". ")
    return f"{plain[:80].strip() or 'Course'}.adle-course.zip"


def without_citations(lesson: dict[str, Any]) -> dict[str, Any]:
    """A lesson as it stands without the materials it was written from: it cites nothing,
    and no longer says it is grounded in materials the reader does not have."""
    changed = dict(lesson)
    changed["source_refs"] = []
    if changed.get("grounding") == "materials":
        changed["grounding"] = "general_knowledge"
    return changed


def _renamed(value: Any, names: dict[str, str]) -> Any:
    """``value`` with every identifier in it that the file used replaced by its new one."""
    if isinstance(value, str):
        return names.get(value, value)
    if isinstance(value, list):
        return [_renamed(item, names) for item in value]
    if isinstance(value, dict):
        return {key: _renamed(item, names) for key, item in value.items()}
    return value


def _names_only(written_by: object) -> dict[str, Any] | None:
    """Who wrote something, as a file says: short plain names, or nothing."""
    if not isinstance(written_by, dict):
        return None
    kept: dict[str, Any] = {}
    for key, value in list(written_by.items())[:8]:
        if not isinstance(key, str) or len(key) > 40:
            continue
        if isinstance(value, str) and len(value) <= 240 and is_plain_text(value or "x"):
            kept[key] = value
        elif isinstance(value, list) and len(value) <= 8:
            kept[key] = [
                item
                for item in value
                if isinstance(item, str) and len(item) <= 120 and is_plain_text(item or "x")
            ]
    return kept or None


class CourseFileService:
    def __init__(
        self,
        database: Database,
        courses: CourseService,
        curriculum: CurriculumService,
        sources: SourceService,
        lessons: LessonService,
        learner: LearnerService,
        asks: AskService,
        *,
        handover_dir: Path,
        made_by: str,
        max_file_bytes: int,
    ) -> None:
        self._database = database
        self._courses = courses
        self._curriculum = curriculum
        self._sources = sources
        self._lessons = lessons
        self._learner = learner
        self._asks = asks
        self._handover = handover_dir
        self._made_by = made_by
        self._max_file_bytes = max_file_bytes

    # -- saving ------------------------------------------------------------------------------

    def clear_handed_over(self) -> None:
        """Files written for the shell to hand to the learner are not kept: whatever is
        left when the core starts was never collected."""
        if not self._handover.is_dir():
            return
        for entry in self._handover.iterdir():
            if entry.is_file():
                entry.unlink(missing_ok=True)

    def save(self, course_id: str, kind: files.Kind, holds: Holds) -> SavedCourse:
        """Write a course as a file in the folder of files being handed over."""
        with self._database.read() as session:
            course = get_course_or_404(session, course_id)
            title = course.title
            curriculum = self._curriculum_of(session, course_id, with_sections=holds.materials)
            lessons, left_out = (
                self._lessons_of(session, course_id, cited=holds.materials)
                if holds.lessons
                else ([], 0)
            )
            materials = self._materials_of(session, course_id) if holds.materials else []
            kept = {
                lesson.lesson["lesson_id"] for lesson in lessons if "lesson_id" in lesson.lesson
            }
            progress = self._progress_of(session, course_id, kept) if holds.progress else None
            notes = self._notes_of(session, course_id, kept) if holds.notes else None
            manifest = files.Manifest(
                format="adle-course",
                version=files.VERSION,
                kind=kind,
                made_by=self._made_by,
                made_at=utc_now(),
                course=files.CoursePart(
                    title=title,
                    description=course.description,
                    topic=course.topic,
                    subject=course.subject,
                    subject_by_adle=course.subject_by_adle,
                ),
                counts=files.Counts(
                    concepts=len(curriculum.concepts),
                    lessons=len(lessons),
                    materials=len(materials),
                    files=sum(1 for _, original in materials if original is not None),
                    progress=progress is not None,
                    notes=len(notes.asks) if notes else 0,
                ),
            )
        self._handover.mkdir(parents=True, exist_ok=True)
        name = f"course-{new_id('x').split('_', 1)[1]}.zip"
        target = self._handover / name
        try:
            files.write_course_file(
                target,
                manifest=manifest,
                curriculum=curriculum,
                lessons=lessons,
                materials=materials,
                progress=progress,
                notes=notes,
            )
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return SavedCourse(
            name=name,
            suggested_name=file_name_for(title),
            counts=manifest.counts,
            lessons_left_out=left_out,
        )

    @staticmethod
    def _curriculum_of(
        session: Session, course_id: str, *, with_sections: bool
    ) -> files.Curriculum:
        concepts = session.scalars(
            select(Concept).where(Concept.course_id == course_id).order_by(Concept.position)
        ).all()
        return files.Curriculum(
            concepts=[
                files.ConceptPart(
                    id=concept.id,
                    title=concept.title,
                    summary=concept.summary,
                    complexity=concept.complexity,
                    tags=list(concept.tags or []),
                    origin=concept.origin,
                    objectives=[
                        files.ObjectivePart(id=objective.id, statement=objective.statement)
                        for objective in concept.objectives
                    ],
                    needs=[
                        files.NeedPart(
                            concept_id=link.prerequisite_id, reason=link.reason, origin=link.origin
                        )
                        for link in concept.prerequisite_links
                    ],
                    sections=(
                        [ref.section_id for ref in concept.source_refs] if with_sections else []
                    ),
                )
                for concept in concepts
            ]
        )

    @staticmethod
    def _lessons_of(
        session: Session, course_id: str, *, cited: bool
    ) -> tuple[list[files.LessonPart], int]:
        rows = session.scalars(
            select(StoredLesson)
            .where(StoredLesson.course_id == course_id)
            .order_by(StoredLesson.created_at, StoredLesson.id)
        ).all()
        found: list[files.LessonPart] = []
        left_out = 0
        for row in rows:
            if row.writing or row.pending_scenes:
                # Still being written or drawn: a file holds whole lessons.
                left_out += 1
                continue
            document = dict(row.document)
            try:
                found.append(
                    files.LessonPart(
                        lesson=document if cited else without_citations(document),
                        scenes=[
                            files.ScenePart(
                                id=scene.scene_id,
                                purpose=scene.document["purpose"],
                                source=scene.document["source"],
                            )
                            for scene in row.scenes
                        ],
                        written_by=row.written_by,
                    )
                )
            except (KeyError, TypeError, ValueError):
                left_out += 1
        return found, left_out

    def _materials_of(
        self, session: Session, course_id: str
    ) -> list[tuple[files.SourcePart, Path | None]]:
        found: list[tuple[files.SourcePart, Path | None]] = []
        rows = session.scalars(
            select(Source)
            .where(Source.course_id == course_id)
            .order_by(Source.created_at, Source.id)
        ).all()
        for row in rows:
            place = {section.id: index for index, section in enumerate(row.sections)}
            part = files.SourcePart(
                id=row.id,
                display_name=row.display_name,
                kind=row.kind,
                content_hash=row.content_hash,
                size_bytes=row.size_bytes,
                warnings=list(row.warnings or []),
                picture_pages=list(row.picture_pages or []),
                parser=row.parser,
                parser_version=row.parser_version,
                char_count=row.char_count,
                sections=[
                    files.SectionPart(
                        id=section.id,
                        kind=section.kind,
                        title=section.title,
                        page_number=section.page_number,
                        level=section.level,
                        char_count=section.char_count,
                        confidence=section.confidence,
                    )
                    for section in row.sections
                ],
                chunks=[
                    files.ChunkPart(
                        section=place[chunk.section_id],
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        content_hash=chunk.content_hash,
                    )
                    for chunk in row.chunks
                    if chunk.section_id in place and chunk.text
                ],
            )
            found.append((part, self._sources.original_of(row.stored_name)))
        return found

    @staticmethod
    def _progress_of(session: Session, course_id: str, lessons: set[str]) -> files.Progress:
        observations = session.scalars(
            select(LearnerObservation)
            .where(LearnerObservation.course_id == course_id)
            .order_by(LearnerObservation.id)
        ).all()
        attempts = session.scalars(
            select(Attempt).where(Attempt.course_id == course_id).order_by(Attempt.id)
        ).all()
        events = session.scalars(
            select(LearnerEvent)
            .where(LearnerEvent.course_id == course_id)
            .order_by(LearnerEvent.id)
        ).all()
        places = session.execute(
            select(LessonProgress)
            .join(StoredLesson, StoredLesson.id == LessonProgress.lesson_id)
            .where(StoredLesson.course_id == course_id)
        ).scalars()
        return files.Progress(
            observations=[
                files.ObservationPart(
                    concept_id=row.concept_id,
                    occurred_at=row.occurred_at,
                    kind=row.kind,
                    outcome=row.outcome,
                    question_form=row.question_form,
                    is_transfer=row.is_transfer,
                    hinted=row.hinted,
                    unsure=row.unsure,
                    item_guess=row.item_guess,
                    slip=row.slip,
                    self_report=row.self_report,
                    unresolved_misconception=row.unresolved_misconception,
                )
                for row in observations
            ],
            attempts=[
                files.AttemptPart(
                    lesson_id=row.lesson_id,
                    concept_id=row.concept_id,
                    question_id=row.question_id,
                    form=row.form,
                    outcome=row.outcome,
                    hinted=row.hinted,
                    unsure=row.unsure,
                    misconception=row.misconception,
                    reveals=list(row.reveals or []),
                    created_at=row.created_at,
                )
                for row in attempts
                if row.lesson_id in lessons
            ],
            events=[
                files.EventPart(
                    concept_id=row.concept_id,
                    lesson_id=row.lesson_id,
                    occurred_at=row.occurred_at,
                    kind=row.kind,
                    detail={
                        str(key)[:40]: value
                        for key, value in (row.detail or {}).items()
                        if value is None
                        or isinstance(value, bool | int)
                        or (isinstance(value, str) and len(value) <= 80)
                    },
                )
                for row in events
                if row.lesson_id is None or row.lesson_id in lessons
            ],
            lessons=[
                files.LessonPlace(
                    lesson_id=row.lesson_id, position=row.position, completed=row.completed
                )
                for row in places
                if row.lesson_id in lessons
            ],
        )

    @staticmethod
    def _notes_of(session: Session, course_id: str, lessons: set[str]) -> files.Notes:
        rows = session.scalars(
            select(LessonAsk)
            .where(LessonAsk.course_id == course_id)
            .order_by(LessonAsk.created_at, LessonAsk.id)
        ).all()
        return files.Notes(
            asks=[
                files.AskPart(
                    lesson_id=row.lesson_id,
                    segment_id=row.segment_id,
                    question=row.question,
                    # A note's words; a picture it drew is in the lesson, if it is in use there
                    # (ADR-067), and a note brought in carries words only.
                    answer={
                        key: value
                        for key, value in (row.answer or {}).items()
                        if key in ("paragraphs", "citations")
                    },
                    written_by=dict(row.written_by or {}),
                    created_at=row.created_at,
                )
                for row in rows
                if row.lesson_id in lessons
            ]
        )

    # -- bringing one in -----------------------------------------------------------------------

    @staticmethod
    def look(path: Path) -> CourseInFile:
        manifest = files.read_manifest(path)
        return CourseInFile(
            title=manifest.course.title,
            kind=manifest.kind,
            counts=manifest.counts,
            made_by=manifest.made_by,
            made_at=manifest.made_at,
        )

    def bring_in(self, path: Path, holds: Holds) -> BroughtIn:
        """Make a new course of what a file holds, as much of it as the learner asked for."""
        file = files.read_course_file(path)
        said = file.manifest.course
        with_materials = holds.materials and bool(file.materials)
        course = self._courses.create(
            title=said.title,
            description=said.description,
            # Never as Adle's own sample, whatever a file says of itself.
            origin="materials" if with_materials else "topic",
            topic=said.topic,
        )
        try:
            self._courses.mark_brought_in(course.id, said.subject, by_adle=said.subject_by_adle)
            return self._fill(course.id, said.title, file, holds, path)
        except BaseException:
            # Half a course is worse than none: the file is still there to try again.
            self._courses.delete(course.id)
            raise

    def _fill(
        self, course_id: str, title: str, file: files.CourseFile, holds: Holds, path: Path
    ) -> BroughtIn:
        names: dict[str, str] = {}
        materials = self._bring_materials(course_id, file, path, names) if holds.materials else 0
        concepts = self._bring_curriculum(course_id, file.curriculum, names)
        lessons, left_out = (
            self._bring_lessons(course_id, file, names, cited=materials > 0)
            if holds.lessons
            else (0, 0)
        )
        progress = False
        if holds.progress and file.progress is not None:
            self._bring_progress(course_id, file.progress, names)
            progress = True
        notes = 0
        if holds.notes and file.notes is not None:
            notes = self._bring_notes(file.notes, names)
        return BroughtIn(
            course_id=course_id,
            title=title,
            concepts=concepts,
            lessons=lessons,
            lessons_left_out=left_out,
            materials=materials,
            progress=progress,
            notes=notes,
        )

    def _bring_materials(
        self, course_id: str, file: files.CourseFile, path: Path, names: dict[str, str]
    ) -> int:
        brought = 0
        seen: set[str] = set()
        for index, part in enumerate(file.materials):
            if part.content_hash in seen:
                continue
            seen.add(part.content_hash)
            original = self._original(path, file.originals.get(index), part)
            try:
                copied = self._sources.add_copied(course_id, self._as_copied(part), original)
            finally:
                if original is not None:
                    original.unlink(missing_ok=True)
            names[part.id] = copied.source_id
            for section, new in zip(part.sections, copied.section_ids, strict=True):
                names[section.id] = new
            brought += 1
        return brought

    def _original(self, path: Path, member: str | None, part: files.SourcePart) -> Path | None:
        """The document itself, copied out of the file to a place of Adle's own, if it is
        there and is what its material says it is: by its size and its hash."""
        if member is None or part.kind == "authored" or part.size_bytes > self._max_file_bytes:
            return None
        self._handover.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0

        class _Counted:
            def __init__(self, handle: Any) -> None:
                self._handle = handle

            def write(self, block: bytes) -> int:
                nonlocal size
                digest.update(block)
                size += len(block)
                return int(self._handle.write(block))

        with tempfile.NamedTemporaryFile(
            dir=self._handover, prefix="original-", suffix=".part", delete=False
        ) as handle:
            copy = Path(handle.name)
            try:
                files.copy_original(path, member, _Counted(handle), self._max_file_bytes)  # type: ignore[arg-type]
            except BaseException:
                handle.close()
                copy.unlink(missing_ok=True)
                raise
        if size != part.size_bytes or digest.hexdigest() != part.content_hash:
            # Not the document its text was read from: the text is kept, the file is not.
            copy.unlink(missing_ok=True)
            return None
        return copy

    @staticmethod
    def _as_copied(part: files.SourcePart) -> CopiedSource:
        sections = len(part.sections)
        return CopiedSource(
            display_name=part.display_name,
            kind=part.kind,
            content_hash=part.content_hash,
            size_bytes=part.size_bytes,
            warnings=[warning for warning in part.warnings if is_plain_text(warning or "x")],
            picture_pages=sorted(set(part.picture_pages)),
            parser=part.parser,
            parser_version=part.parser_version,
            sections=[
                (
                    section.kind,
                    section.title,
                    section.page_number,
                    section.level,
                    section.confidence,
                )
                for section in part.sections
            ],
            chunks=[
                (chunk.section, chunk.text, chunk.char_start, chunk.char_end)
                for chunk in part.chunks
                if chunk.section < sections and chunk.char_end >= chunk.char_start
            ],
        )

    def _bring_curriculum(
        self, course_id: str, curriculum: files.Curriculum, names: dict[str, str]
    ) -> int:
        made: list[tuple[files.ConceptPart, str]] = []
        for concept in curriculum.concepts:
            if concept.id in names:
                continue
            created = self._curriculum.create_concept(
                course_id,
                title=concept.title,
                summary=concept.summary,
                objectives=[objective.statement for objective in concept.objectives],
                origin=concept.origin,
            ).concepts[-1]
            names[concept.id] = created.id
            # Objectives that say nothing are not kept, so they are matched by what they say.
            statements = {objective.statement: objective.id for objective in created.objectives}
            for objective in concept.objectives:
                new = statements.get(" ".join(objective.statement.split()))
                if new is not None:
                    names.setdefault(objective.id, new)
            self._curriculum.update_concept(
                created.id,
                complexity=concept.complexity,
                tags=[tag for tag in concept.tags if tag in CONCEPT_TAGS],
            )
            made.append((concept, created.id))
        for concept, new_id_ in made:
            needs: dict[str, tuple[str, str]] = {}
            for need in concept.needs:
                needed = names.get(need.concept_id)
                if needed is not None and needed != new_id_:
                    needs.setdefault(needed, (need.reason, need.origin))
            if needs:
                try:
                    self._curriculum.set_prerequisites(
                        new_id_,
                        [(needed, reason) for needed, (reason, _) in needs.items()],
                        origin=next(iter(needs.values()))[1],
                    )
                except AdleError as error:
                    # A loop, as only a file made by hand could have: the concept is kept
                    # without what it was said to need.
                    logger.info("course_file.needs_left_out %s", logs.where(error))
            for section in concept.sections:
                linked = names.get(section)
                if linked is None:
                    continue
                try:
                    self._curriculum.add_source_ref(new_id_, linked)
                except AdleError:
                    break
        return len(made)

    def _bring_lessons(
        self, course_id: str, file: files.CourseFile, names: dict[str, str], *, cited: bool
    ) -> tuple[int, int]:
        brought = left_out = 0
        for part in file.lessons:
            old = part.lesson.get("lesson_id")
            lesson_id = new_id("les")
            document = _renamed(part.lesson, names)
            if not isinstance(document, dict):
                left_out += 1
                continue
            document["lesson_id"] = lesson_id
            document["course_id"] = course_id
            if not cited:
                document = without_citations(document)
            if document.get("grounding") == "sample":
                # Adle's own sample is the one Adle installs: this one came in a file.
                document["grounding"] = "general_knowledge"
            try:
                bundle = parse_bundle(
                    {
                        "lesson": document,
                        "scenes": [scene.model_dump() for scene in part.scenes],
                    }
                )
                self._lessons.store(
                    bundle, origin="generated", written_by=_names_only(part.written_by)
                )
            except AdleError as error:
                logger.info("course_file.lesson_left_out %s", logs.where(error))
                left_out += 1
                continue
            if isinstance(old, str) and _ID.match(old):
                names.setdefault(old, lesson_id)
            brought += 1
        return brought, left_out

    def _bring_progress(
        self, course_id: str, progress: files.Progress, names: dict[str, str]
    ) -> None:
        # What the learner showed: every answer again, in the order they gave them, so that
        # each state is the one this Adle works out from them.
        self._learner.replay(
            course_id,
            [
                (
                    names[item.concept_id],
                    Observation(
                        kind=ObservationKind(item.kind),
                        occurred_at=item.occurred_at,
                        outcome=Outcome(item.outcome) if item.outcome else None,
                        question_form=item.question_form
                        if item.question_form in QUESTION_FORMS
                        else None,
                        is_transfer=item.is_transfer,
                        hinted=item.hinted,
                        unsure=item.unsure,
                        item_guess=item.item_guess,
                        slip=item.slip,
                        self_report=SelfReport(item.self_report) if item.self_report else None,
                        unresolved_misconception=item.unresolved_misconception,
                    ),
                )
                for item in sorted(progress.observations, key=lambda item: item.occurred_at)
                if item.concept_id in names
            ],
        )
        with self._database.session() as session:
            lessons = {
                row.id: row
                for row in session.scalars(
                    select(StoredLesson).where(StoredLesson.course_id == course_id)
                )
            }
            questions: dict[str, set[str]] = {}
            for lesson_id, row in lessons.items():
                try:
                    asked = Lesson.model_validate(row.document).all_questions()
                except ValueError:
                    asked = []
                questions[lesson_id] = {question.id for question in asked}
            for attempt in progress.attempts:
                lesson_id = names.get(attempt.lesson_id, "")
                concept_id = names.get(attempt.concept_id)
                if (
                    concept_id is None
                    or attempt.question_id not in questions.get(lesson_id, ())
                    or attempt.form not in QUESTION_FORMS
                ):
                    continue
                session.add(
                    Attempt(
                        course_id=course_id,
                        lesson_id=lesson_id,
                        concept_id=concept_id,
                        question_id=attempt.question_id,
                        form=attempt.form,
                        outcome=attempt.outcome,
                        hinted=attempt.hinted,
                        unsure=attempt.unsure,
                        misconception=attempt.misconception
                        if attempt.misconception in MISCONCEPTION_KINDS
                        else None,
                        reveals=[kind for kind in attempt.reveals if kind in MISCONCEPTION_KINDS],
                        created_at=attempt.created_at,
                    )
                )
            for event in progress.events:
                about = names.get(event.concept_id) if event.concept_id else None
                during = names.get(event.lesson_id) if event.lesson_id else None
                if (event.concept_id and about is None) or (
                    event.lesson_id and during not in lessons
                ):
                    continue
                session.add(
                    LearnerEvent(
                        course_id=course_id,
                        concept_id=about,
                        lesson_id=during,
                        occurred_at=event.occurred_at,
                        kind=event.kind,
                        detail=dict(event.detail),
                    )
                )
            for place in progress.lessons:
                stored = lessons.get(names.get(place.lesson_id, ""))
                if stored is None or stored.progress is not None:
                    continue
                session.add(
                    LessonProgress(
                        lesson_id=stored.id,
                        position=min(place.position, max(0, stored.segment_count - 1)),
                        completed=place.completed,
                    )
                )

    def _bring_notes(self, notes: files.Notes, names: dict[str, str]) -> int:
        brought = 0
        each: dict[str, int] = {}
        for ask in notes.asks:
            lesson_id = names.get(ask.lesson_id)
            if lesson_id is None or each.get(lesson_id, 0) >= MAX_ASKS_PER_LESSON:
                continue
            paragraphs = [
                paragraph
                for paragraph in ask.answer.get("paragraphs", [])[:12]
                if isinstance(paragraph, str) and 0 < len(paragraph) <= 4_000
            ]
            citations = [
                AskCitation(source_name=item["source_name"], locator=item["locator"])
                for item in ask.answer.get("citations", [])[:12]
                if isinstance(item, dict)
                and isinstance(item.get("source_name"), str)
                and isinstance(item.get("locator"), str)
                and len(item["source_name"]) <= 255
                and len(item["locator"]) <= 200
            ]
            try:
                self._asks.store(
                    lesson_id=lesson_id,
                    segment_id=ask.segment_id,
                    question=ask.question,
                    paragraphs=paragraphs,
                    citations=citations,
                    written_by=_names_only(ask.written_by) or {},
                    now=ask.created_at,
                )
            except AdleError:
                continue
            each[lesson_id] = each.get(lesson_id, 0) + 1
            brought += 1
        return brought


__all__ = [
    "HANDED_OVER",
    "BroughtIn",
    "CourseFileService",
    "CourseInFile",
    "Holds",
    "SavedCourse",
    "ValidationFailedError",
    "file_name_for",
    "without_citations",
]
