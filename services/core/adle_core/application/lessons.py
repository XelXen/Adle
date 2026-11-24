"""Storing lessons and handing them to the player.

A lesson is stored only as a validated :class:`~adle_core.lessons.ir.LessonBundle`
whose every reference (course, concepts, objectives, cited sections) points at
something that exists. It is read back through the IR again, so a document
written by an older version is caught rather than half-understood, and its
scenes are put through the static policy again before they are handed out.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from adle_core.application.courses import get_course_or_404
from adle_core.application.evidence import EVENT_LESSON_COMPLETED
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.generation.drafts import as_visualization, minutes_for, without_scene
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
from adle_core.lessons.bundle import SceneRejectedError, inspect_scene, parse_bundle
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
    #: Pictures the lesson is still waiting for. It can be taken meanwhile (ADR-031).
    pictures_pending: int = 0
    #: Its later parts are still being written. It can be taken meanwhile (ADR-048).
    writing: bool = False


@dataclass(frozen=True, slots=True)
class LessonForPlayer:
    lesson: Lesson
    scenes: list[SceneArtifact]
    origin: str
    progress: ProgressRecord
    #: Scenes that parts refer to and that are still being drawn.
    pending_scene_ids: list[str]
    #: Who wrote it, where a model did: provider, models, and a note. ``None`` otherwise.
    written_by: dict[str, Any] | None
    #: The rest of it is still being written; its parts come after these (ADR-048).
    writing: bool = False


@dataclass(frozen=True, slots=True)
class SettledScene:
    """What became of a picture a lesson was waiting for."""

    #: It is in the lesson now.
    added: bool
    #: It was asked for as something to try, and came out as something to watch.
    as_animation: bool = False


def _author(written_by: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Who wrote a lesson, reduced to what is ever shown: names and one sentence."""
    if not written_by:
        return None
    provider = written_by.get("provider")
    if not isinstance(provider, str) or not provider:
        return None
    models = written_by.get("models")
    note = written_by.get("note")
    return {
        "provider": provider[:120],
        "models": [str(model)[:120] for model in models[:8]] if isinstance(models, list) else [],
        "note": note[:400] if isinstance(note, str) else "",
    }


def _asks_to_try(document: Mapping[str, Any], scene_id: str) -> bool:
    """Whether the part that shows this scene is one where the learner operates it."""
    return any(
        segment.get("type") == "interaction"
        and (segment.get("scene") or {}).get("scene_id") == scene_id
        for segment in document.get("segments", [])
    )


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
        pictures_pending=len(row.pending_scenes or []),
        writing=row.writing,
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
            "This lesson was made by a different version of Adle and can’t be played. Create it "
            "again to continue."
        ) from error


def _read_scene(row: StoredScene) -> SceneArtifact | None:
    """The stored scene, described afresh from its source, or ``None`` if it may not run."""
    document = row.document
    try:
        return inspect_scene(row.scene_id, document["purpose"], document["source"])
    except (KeyError, TypeError, ValueError, SceneRejectedError, RecursionError, MemoryError):
        # A stored scene that cannot even be examined is withheld like one that may not run.
        return None


class LessonService:
    def __init__(self, database: Database) -> None:
        self._database = database

    # -- storing -----------------------------------------------------------

    def store(
        self,
        bundle: LessonBundle,
        *,
        origin: str,
        written_by: Mapping[str, Any] | None = None,
        writing: bool = False,
    ) -> LessonSummary:
        """Store a validated bundle. Every id it refers to must exist in its course.

        A bundle may list scenes that are still to come (ADR-031): the lesson can be taken
        at once, and each is settled later with ``settle_scene``. With ``writing`` it is the
        beginning of a lesson still being written: its later parts are added with
        ``extend`` (ADR-048).
        """
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
                pending_scenes=list(bundle.pending_scene_ids),
                written_by=_author(written_by),
                writing=writing,
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

    # -- pictures that arrive after the lesson (ADR-031) -------------------

    def settle_scene(
        self, lesson_id: str, scene_id: str, scene: Mapping[str, str] | None
    ) -> SettledScene:
        """One picture a stored lesson was waiting for: here it is, or it is not coming.

        ``scene`` has the ``purpose`` and the ``source`` of the file, or is ``None`` when
        the picture could not be made. Either way the whole lesson goes through the gate
        again, with the picture in place or with that part turned into words, and the
        picture is no longer waited for.
        """
        with self._database.session() as session:
            return self._settle(session, _get_or_404(session, lesson_id), scene_id, scene)

    def extend(
        self,
        lesson_id: str,
        segments: Sequence[Mapping[str, Any]],
        pending: Sequence[str] = (),
        *,
        writing: bool,
        practice: Sequence[Mapping[str, Any]] | None = None,
        source_refs: Sequence[Mapping[str, Any]] | None = None,
        grounding: str | None = None,
    ) -> None:
        """Add parts of a lesson that is still being written, after the parts it has
        (ADR-048), with the pictures they are waiting for. A part already there never
        changes: the learner may be in it, and nor does its narrator's voice. The whole
        lesson goes through the gate again, as when a picture joins it. ``writing`` false
        ends its writing; the questions kept for practice come with that, which are written
        last, and the passages it draws on where they were named only after its parts.
        """
        with self._database.session() as session:
            row = _get_or_404(session, lesson_id)
            document: dict[str, Any] = dict(row.document)
            document["segments"] = [*document["segments"], *segments]
            document["estimated_minutes"] = minutes_for(document["segments"])
            if practice is not None:
                document["practice"] = list(practice)
            if source_refs is not None:
                document["source_refs"] = list(source_refs)
            if grounding is not None:
                document["grounding"] = grounding
            scenes = [
                {
                    "id": stored.scene_id,
                    "purpose": stored.document["purpose"],
                    "source": stored.document["source"],
                }
                for stored in row.scenes
            ]
            coming = [*row.pending_scenes, *pending]
            bundle = parse_bundle(
                {"lesson": document, "scenes": scenes, "pending_scene_ids": coming}
            )
            if source_refs is not None:
                # What it cites must still be in its course, as when a lesson is stored.
                self._check_references(session, bundle.lesson)
            row.document = bundle.lesson.model_dump(mode="json")
            row.pending_scenes = coming
            row.estimated_minutes = bundle.lesson.estimated_minutes
            row.segment_count = len(bundle.lesson.segments)
            row.writing = writing
            session.flush()

    def settle_unfinished(self, lesson_id: str | None = None) -> int:
        """Say in words every picture that is not coming after all. Returns how many.

        For one lesson, when its pictures were stopped. For every lesson when the core
        starts: nothing is being drawn then, so whatever is still waited for was left by
        a run that ended.
        """
        settled = 0
        with self._database.session() as session:
            waiting = select(StoredLesson).where(
                func.json_array_length(StoredLesson.pending_scenes) > 0
            )
            if lesson_id is not None:
                waiting = waiting.where(StoredLesson.id == lesson_id)
            for row in session.scalars(waiting).all():
                for scene_id in list(row.pending_scenes):
                    try:
                        self._settle(session, row, scene_id, None)
                    except (AdleError, ValueError, KeyError, TypeError) as error:
                        # A lesson that no longer passes the gate is still not waiting for
                        # anything. Its parts that refer to a missing picture are shown in
                        # words by the player, as for any picture that is withheld.
                        logger.warning(
                            "lesson.settle_failed lesson=%s kind=%s", row.id, type(error).__name__
                        )
                        row.pending_scenes = [
                            item for item in row.pending_scenes if item != scene_id
                        ]
                    settled += 1
            # Nor is anything being written: a lesson stored at its first part keeps the
            # parts it has (ADR-048).
            unended = select(StoredLesson).where(StoredLesson.writing.is_(True))
            if lesson_id is not None:
                unended = unended.where(StoredLesson.id == lesson_id)
            for row in session.scalars(unended).all():
                row.writing = False
        return settled

    def set_written_by(self, lesson_id: str, written_by: Mapping[str, Any] | None) -> None:
        """Record who wrote a lesson, once all of it is written. Nothing if it is gone."""
        with self._database.session() as session:
            row = session.get(StoredLesson, lesson_id)
            if row is not None:
                row.written_by = _author(written_by)

    @staticmethod
    def _settle(
        session: Session, row: StoredLesson, scene_id: str, scene: Mapping[str, str] | None
    ) -> SettledScene:
        if scene_id not in row.pending_scenes:
            raise ConflictError("This lesson is not waiting for that picture.")
        coming = [item for item in row.pending_scenes if item != scene_id]
        document: dict[str, Any] = dict(row.document)
        scenes = [
            {
                "id": stored.scene_id,
                "purpose": stored.document["purpose"],
                "source": stored.document["source"],
            }
            for stored in row.scenes
        ]
        as_animation = False
        if scene is None:
            document = without_scene(document, scene_id)
        else:
            artifact = inspect_scene(scene_id, scene["purpose"], scene["source"])
            if not artifact.interactive and _asks_to_try(document, scene_id):
                document = as_visualization(document, scene_id)
                as_animation = True
            scenes.append({"id": scene_id, "purpose": scene["purpose"], "source": scene["source"]})
        bundle = parse_bundle({"lesson": document, "scenes": scenes, "pending_scene_ids": coming})
        row.document = bundle.lesson.model_dump(mode="json")
        row.pending_scenes = coming
        row.estimated_minutes = bundle.lesson.estimated_minutes
        row.segment_count = len(bundle.lesson.segments)
        if scene is not None:
            added = bundle.scenes[-1]
            # Through the lesson's own list, so that it is there for whatever looks next.
            row.scenes.append(
                StoredScene(
                    scene_id=added.id,
                    position=len(row.scenes),
                    content_hash=added.content_hash,
                    document=added.model_dump(mode="json"),
                )
            )
        session.flush()
        return SettledScene(added=scene is not None, as_animation=as_animation)

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
                pending_scene_ids=list(row.pending_scenes or []),
                written_by=row.written_by,
                writing=row.writing,
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

    def unfinished(self, limit: int) -> list[str]:
        """The lessons the learner has opened and not finished, the one opened last first:
        what they are likely to open next."""
        with self._database.read() as session:
            rows = session.scalars(
                select(LessonProgress.lesson_id)
                .where(LessonProgress.completed.is_(False))
                .order_by(LessonProgress.updated_at.desc(), LessonProgress.lesson_id)
                .limit(limit)
            ).all()
        return list(rows)

    def exists(self, lesson_id: str) -> bool:
        """Whether the lesson is still there: the learner can remove one at any time."""
        with self._database.read() as session:
            return session.get(StoredLesson, lesson_id) is not None

    def is_writing(self, lesson_id: str) -> bool:
        """Whether more of the lesson's parts are still to come (ADR-048)."""
        with self._database.read() as session:
            return bool(_get_or_404(session, lesson_id).writing)

    def delete(self, lesson_id: str) -> None:
        with self._database.session() as session:
            session.delete(_get_or_404(session, lesson_id))
