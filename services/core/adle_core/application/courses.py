"""Courses: the container for a learner's sources, curriculum, and progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from adle_core.errors import NotFoundError
from adle_core.infrastructure.asset_store import AssetStore
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Course, Source


@dataclass(frozen=True, slots=True)
class CourseRecord:
    id: str
    title: str
    description: str
    origin: str
    topic: str | None
    source_count: int
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None


def get_course_or_404(session: Session, course_id: str) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise NotFoundError("That course no longer exists.")
    return course


def _record(course: Course, source_count: int) -> CourseRecord:
    return CourseRecord(
        id=course.id,
        title=course.title,
        description=course.description,
        origin=course.origin,
        topic=course.topic,
        source_count=source_count,
        created_at=course.created_at,
        updated_at=course.updated_at,
        last_opened_at=course.last_opened_at,
    )


class CourseService:
    def __init__(self, database: Database, source_files: AssetStore) -> None:
        self._database = database
        self._source_files = source_files

    def list_all(self) -> list[CourseRecord]:
        """Every course, most recently used first."""
        counts = (
            select(Source.course_id, func.count(Source.id).label("source_count"))
            .group_by(Source.course_id)
            .subquery()
        )
        statement = (
            select(Course, func.coalesce(counts.c.source_count, 0))
            .outerjoin(counts, counts.c.course_id == Course.id)
            .order_by(func.coalesce(Course.last_opened_at, Course.created_at).desc(), Course.id)
        )
        with self._database.session() as session:
            return [_record(course, count) for course, count in session.execute(statement)]

    def create(
        self, *, title: str, description: str = "", origin: str, topic: str | None = None
    ) -> CourseRecord:
        with self._database.session() as session:
            course = Course(
                id=new_id("crs"),
                title=title.strip(),
                description=description.strip(),
                origin=origin,
                topic=topic.strip() if topic and topic.strip() else None,
            )
            session.add(course)
            session.flush()
            return _record(course, 0)

    def get(self, course_id: str, *, mark_opened: bool = False) -> CourseRecord:
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            if mark_opened:
                course.last_opened_at = utc_now()
                session.flush()
            count = session.scalar(
                select(func.count(Source.id)).where(Source.course_id == course_id)
            )
            return _record(course, count or 0)

    def update(
        self, course_id: str, *, title: str | None = None, description: str | None = None
    ) -> CourseRecord:
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            if title is not None:
                course.title = title.strip()
            if description is not None:
                course.description = description.strip()
            session.flush()
            count = session.scalar(
                select(func.count(Source.id)).where(Source.course_id == course_id)
            )
            return _record(course, count or 0)

    def delete(self, course_id: str) -> None:
        """Permanently remove a course, everything derived from it, and its stored files."""
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            stored_names = list(
                session.scalars(select(Source.stored_name).where(Source.course_id == course_id))
            )
            session.delete(course)
        # Files go only after the database change is durable: an orphaned file
        # wastes space, but a row pointing at a missing file would be a broken course.
        for stored_name in stored_names:
            self._source_files.delete(stored_name)
