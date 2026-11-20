"""Storing lessons and handing them to the player.

A lesson is stored only as a validated :class:`~adle_core.lessons.ir.LessonBundle`
whose every reference (course, concepts, objectives, cited sections) points at
something that exists. It is read back through the IR again, so a document
written by an older version is caught rather than half-understood, and its
scenes are put through the static policy again before they are handed out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from adle_core.application.courses import get_course_or_404
from adle_core.application.evidence import EVENT_LESSON_COMPLETED
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import (
    Concept,
    LearnerEvent,
    LearningObjective,
    LessonProgress,
    Source,
    SourceSection,
    StoredLesson,
    StoredScene,
)
from adle_core.lessons.bundle import SceneRejectedError, inspect_scene
from adle_core.lessons.ir import SCHEMA_VERSION, Lesson, LessonBundle, SceneArtifact

logger = logging.getLogger(__name__)


class LessonOutdatedError(AdleError):
    """A stored lesson no longer fits the current Lesson IR."""

    status_code = 409
    code = "lesson_outdated"


@dataclass(frozen=True, slots=True)
class ProgressRecord:
    #: Index of the segment to resume at.
    position: int
    completed: bool
    #: False until the learner has opened the lesson at least once.
    started: bool


NOT_STARTED = ProgressRecord(position=0, completed=False, started=False)


@dataclass(frozen=True, slots=True)
class LessonSummary:
    id: str
    course_id: str
    concept_id: str
    title: str
    origin: str
    estimated_minutes: int
    segment_count: int
    progress: ProgressRecord


@dataclass(frozen=True, slots=True)
class LessonForPlayer:
    lesson: Lesson
    scenes: list[SceneArtifact]
    origin: str
    progress: ProgressRecord


def _progress(row: LessonProgress | None) -> ProgressRecord:
    if row is None:
        return NOT_STARTED
    return ProgressRecord(position=row.position, completed=row.completed, started=True)


def _summary(row: StoredLesson) -> LessonSummary:
    return LessonSummary(
        id=row.id,
        course_id=row.course_id,
        concept_id=row.concept_id,
        title=row.title,
        origin=row.origin,
        estimated_minutes=row.estimated_minutes,
        segment_count=row.segment_count,
        progress=_progress(row.progress),
    )


def _get_or_404(session: Session, lesson_id: str) -> StoredLesson:
    row = session.get(StoredLesson, lesson_id)
    if row is None:
        raise NotFoundError("That lesson no longer exists.")
    return row


def _read_lesson(row: StoredLesson) -> Lesson:
    """The stored lesson, through the IR again, or ``LessonOutdatedError``."""
    try:
        if row.schema_version != SCHEMA_VERSION:
            raise ValueError("schema version")
        return Lesson.model_validate(row.document)
    except ValueError as error:  # includes pydantic's ValidationError
        raise LessonOutdatedError(
            "This lesson was made by a different version of Adle and cannot be "
            "played as it is. Create it again to continue."
        ) from error


def _read_scene(row: StoredScene) -> SceneArtifact | None:
    """The stored scene, described afresh from its source, or ``None`` if it may not run."""
    document = row.document
    try:
        return inspect_scene(row.scene_id, document["purpose"], document["source"])
    except (KeyError, TypeError, ValueError, SceneRejectedError):
        return None


class LessonService:
    def __init__(self, database: Database) -> None:
        self._database = database

    # -- storing -----------------------------------------------------------

    def store(self, bundle: LessonBundle, *, origin: str) -> LessonSummary:
        """Store a validated bundle. Every id it refers to must exist in its course."""
        lesson = bundle.lesson
        with self._database.session() as session:
            get_course_or_404(session, lesson.course_id)
            if session.get(StoredLesson, lesson.lesson_id) is not None:
                raise ConflictError("A lesson with that identifier already exists.")
            self._check_references(session, lesson)
            row = StoredLesson(
                id=lesson.lesson_id,
                course_id=lesson.course_id,
                concept_id=lesson.concept_ids[0],
                title=lesson.title,
                origin=origin,
                schema_version=lesson.schema_version,
                estimated_minutes=lesson.estimated_minutes,
                segment_count=len(lesson.segments),
                document=lesson.model_dump(mode="json"),
            )
            session.add(row)
            for position, scene in enumerate(bundle.scenes):
                session.add(
                    StoredScene(
                        lesson_id=lesson.lesson_id,
                        scene_id=scene.id,
                        position=position,
                        content_hash=scene.content_hash,
                        document=scene.model_dump(mode="json"),
                    )
                )
            session.flush()
            return _summary(row)

    @staticmethod
    def _check_references(session: Session, lesson: Lesson) -> None:
        concepts = set(
            session.scalars(
                select(Concept.id).where(
                    Concept.course_id == lesson.course_id, Concept.id.in_(lesson.concept_ids)
                )
            )
        )
        if concepts != set(lesson.concept_ids):
            raise ValidationFailedError("The lesson is about a concept that is not in this course.")

        objective_ids = {
            objective.objective_id for objective in lesson.objectives if objective.objective_id
        } | {question.objective_id for question in lesson.all_questions() if question.objective_id}
        if objective_ids:
            known = set(
                session.scalars(
                    select(LearningObjective.id).where(
                        LearningObjective.id.in_(objective_ids),
                        LearningObjective.concept_id.in_(lesson.concept_ids),
                    )
                )
            )
            if known != objective_ids:
                raise ValidationFailedError(
                    "The lesson refers to a learning objective that its concepts do not have."
                )

        section_ids = {citation.section_id for citation in lesson.source_refs}
        if section_ids:
            cited = set(
                session.scalars(
                    select(SourceSection.id)
                    .join(Source, Source.id == SourceSection.source_id)
                    .where(SourceSection.id.in_(section_ids), Source.course_id == lesson.course_id)
                )
            )
            # A citation of something that is not in the learner's materials is an invented one.
            if cited != section_ids:
                raise ValidationFailedError(
                    "The lesson cites a passage that is not in this course's materials."
                )

    # -- reading -----------------------------------------------------------

    def list_for_course(self, course_id: str) -> list[LessonSummary]:
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            rows = session.scalars(
                select(StoredLesson)
                .join(Concept, Concept.id == StoredLesson.concept_id)
                .where(StoredLesson.course_id == course_id)
                .order_by(Concept.position, StoredLesson.created_at, StoredLesson.id)
                .options(selectinload(StoredLesson.progress))
            )
            return [_summary(row) for row in rows]

    def get_lesson(self, lesson_id: str) -> Lesson:
        """The lesson without its scenes: all that scoring an answer needs."""
        with self._database.read() as session:
            return _read_lesson(_get_or_404(session, lesson_id))

    def get(self, lesson_id: str) -> LessonForPlayer:
        """A lesson with the scenes that may be played.

        Every scene goes through the static policy again, whatever the database
        says about it: a database can be restored from a file made elsewhere,
        and the policy can become stricter between versions. A scene that does
        not pass is withheld. The player then shows that part's description in
        words, and the rest of the lesson is unaffected.
        """
        with self._database.read() as session:
            row = _get_or_404(session, lesson_id)
            lesson = _read_lesson(row)
            scenes = []
            for stored in row.scenes:
                scene = _read_scene(stored)
                if scene is None:
                    logger.warning(
                        "lesson.scene_withheld lesson=%s scene=%s", row.id, stored.scene_id
                    )
                else:
                    scenes.append(scene)
            return LessonForPlayer(
                lesson=lesson,
                scenes=scenes,
                origin=row.origin,
                progress=_progress(row.progress),
            )

    # -- progress ----------------------------------------------------------

    def save_progress(self, lesson_id: str, position: int, *, completed: bool) -> ProgressRecord:
        """Remember where the learner is. A finished lesson stays finished when revisited."""
        with self._database.session() as session:
            row = _get_or_404(session, lesson_id)
            if not 0 <= position < row.segment_count:
                raise ValidationFailedError("That is not a part of this lesson.")
            progress = row.progress
            if progress is None:
                progress = LessonProgress(lesson_id=lesson_id, position=position, completed=False)
                session.add(progress)
            progress.position = position
            if completed and not progress.completed:
                # Kept as an event because the progress row moves on when the lesson is
                # opened again, and "when was this finished" would be lost with it.
                session.add(
                    LearnerEvent(
                        course_id=row.course_id,
                        concept_id=row.concept_id,
                        lesson_id=row.id,
                        occurred_at=utc_now(),
                        kind=EVENT_LESSON_COMPLETED,
                        detail={},
                    )
                )
            progress.completed = progress.completed or completed
            session.flush()
            return _progress(progress)

    def delete(self, lesson_id: str) -> None:
        with self._database.session() as session:
            session.delete(_get_or_404(session, lesson_id))
