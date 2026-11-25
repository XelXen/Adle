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
from adle_core.infrastructure.orm import Concept, Course, Source
from adle_core.lessons import axioms


@dataclass(frozen=True, slots=True)
class CourseRecord:
    id: str
    title: str
    description: str
    origin: str
    topic: str | None
    source_count: int
    concept_count: int
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    #: Its name was left to Adle (ADR-053).
    named_by_adle: bool = False
    #: The kind of subject it is, which decides how its lessons are formed (ADR-061).
    subject: str = axioms.GENERAL
    #: Adle placed it; the learner has not chosen.
    subject_by_adle: bool = True
    #: It was brought in from a file (ADR-063).
    brought_in: bool = False


#: What a course is called until Adle has something better to call it.
PROVISIONAL_TITLE = "New course"

#: What the learner says to hand the choice of a course's subject back to Adle.
AUTO_SUBJECT = "auto"


def title_from_file(display_name: str) -> str:
    """A course's name from the name of a file in it: "neural-networks_notes.pdf" is
    "Neural networks notes". Until the AI names it, better than "New course"."""
    stem = display_name.rsplit(".", 1)[0] if "." in display_name else display_name
    words = " ".join(stem.replace("_", " ").replace("-", " ").split())
    if not words:
        return PROVISIONAL_TITLE
    return (words[0].upper() + words[1:])[:200]


def get_course_or_404(session: Session, course_id: str) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise NotFoundError("That course no longer exists.")
    return course


def _record(course: Course, source_count: int, concept_count: int) -> CourseRecord:
    return CourseRecord(
        id=course.id,
        title=course.title,
        description=course.description,
        origin=course.origin,
        topic=course.topic,
        source_count=source_count,
        concept_count=concept_count,
        created_at=course.created_at,
        updated_at=course.updated_at,
        last_opened_at=course.last_opened_at,
        named_by_adle=bool(course.named_by_adle),
        subject=axioms.subject(course.subject).key,
        subject_by_adle=bool(course.subject_by_adle),
        brought_in=bool(course.brought_in),
    )


def place(course: Course) -> None:
    """Adle's own guess at a course's subject, from what the course says of itself, unless
    the learner has chosen one (ADR-061). A guess that finds nothing leaves it as it is: a
    subject the AI named with the course's plan is not undone by a name that says less."""
    if not course.subject_by_adle:
        return
    guessed = axioms.guess(course.title, course.topic, course.description)
    if guessed != axioms.GENERAL:
        course.subject = guessed


def place_as(course: Course, subject: object) -> None:
    """The subject the AI named with a course's plan becomes the course's, unless the
    learner has chosen one, or the AI named none (ADR-061)."""
    key = axioms.subject_key(subject)
    if course.subject_by_adle and key is not None and key != axioms.GENERAL:
        course.subject = key


class CourseService:
    def __init__(self, database: Database, source_files: AssetStore) -> None:
        self._database = database
        self._source_files = source_files

    def list_all(self) -> list[CourseRecord]:
        """Every course, most recently used first."""
        sources = (
            select(Source.course_id, func.count(Source.id).label("source_count"))
            .group_by(Source.course_id)
            .subquery()
        )
        concepts = (
            select(Concept.course_id, func.count(Concept.id).label("concept_count"))
            .group_by(Concept.course_id)
            .subquery()
        )
        statement = (
            select(
                Course,
                func.coalesce(sources.c.source_count, 0),
                func.coalesce(concepts.c.concept_count, 0),
            )
            .outerjoin(sources, sources.c.course_id == Course.id)
            .outerjoin(concepts, concepts.c.course_id == Course.id)
            .order_by(func.coalesce(Course.last_opened_at, Course.created_at).desc(), Course.id)
        )
        with self._database.read() as session:
            return [
                _record(course, source_count, concept_count)
                for course, source_count, concept_count in session.execute(statement)
            ]

    @staticmethod
    def _counted(session: Session, course: Course) -> CourseRecord:
        sources = session.scalar(select(func.count(Source.id)).where(Source.course_id == course.id))
        concepts = session.scalar(
            select(func.count(Concept.id)).where(Concept.course_id == course.id)
        )
        return _record(course, sources or 0, concepts or 0)

    def create(
        self,
        *,
        title: str | None,
        description: str = "",
        origin: str,
        topic: str | None = None,
    ) -> CourseRecord:
        """A new course. Without a name, Adle names it (ADR-053): "New course" for now,
        then from its first file, then as the AI suggests with its concepts."""
        named = (title or "").strip()
        with self._database.session() as session:
            course = Course(
                id=new_id("crs"),
                title=named or PROVISIONAL_TITLE,
                description=description.strip(),
                origin=origin,
                topic=topic.strip() if topic and topic.strip() else None,
                named_by_adle=not named,
                subject=axioms.GENERAL,
                subject_by_adle=True,
            )
            place(course)
            session.add(course)
            session.flush()
            return _record(course, 0, 0)

    def get(self, course_id: str, *, mark_opened: bool = False) -> CourseRecord:
        unit = self._database.session() if mark_opened else self._database.read()
        with unit as session:
            course = get_course_or_404(session, course_id)
            if mark_opened:
                course.last_opened_at = utc_now()
                session.flush()
            return self._counted(session, course)

    def update(
        self,
        course_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        subject: str | None = None,
    ) -> CourseRecord:
        """Change what the learner may change. ``subject`` is a subject's key, which then
        stands, or ``"auto"``, which hands the choice back to Adle (ADR-061)."""
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            if title is not None:
                course.title = title.strip()
                # Named by the learner: Adle never renames it again.
                course.named_by_adle = False
            if description is not None:
                course.description = description.strip()
            if subject == AUTO_SUBJECT:
                course.subject_by_adle = True
                course.subject = axioms.GENERAL
            elif subject is not None:
                course.subject = axioms.subject(subject).key
                course.subject_by_adle = False
            place(course)
            session.flush()
            return self._counted(session, course)

    def mark_brought_in(self, course_id: str, subject: object, *, by_adle: bool) -> None:
        """A course just made of what a file holds (ADR-063): it says so, and it is
        taught as the file says it was, if that is a subject Adle knows. A subject the
        learner had chosen stands as theirs; one Adle had placed may be placed again."""
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            course.brought_in = True
            key = axioms.subject_key(subject)
            if key is not None and key != axioms.GENERAL:
                course.subject = key
                course.subject_by_adle = by_adle

    def settle_subjects(self) -> None:
        """Courses Adle has not placed are given its guess, as the core starts: one made by
        a version that knew no subjects is placed too, and so is one whose name says more
        to a later version than it did to this one."""
        with self._database.session() as session:
            unplaced = session.scalars(
                select(Course).where(
                    Course.subject == axioms.GENERAL, Course.subject_by_adle.is_(True)
                )
            )
            for course in unplaced:
                place(course)

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
