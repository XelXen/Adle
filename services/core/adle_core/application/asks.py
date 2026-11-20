"""Questions the learner puts to Adle in the middle of a lesson, kept beside it.

Called an "ask" to keep it apart from the questions a lesson puts to the learner.
An ask belongs to one part of one lesson. It is a note in the margin, not a
conversation: each stands alone, and nothing is scored from it.

That one was asked matters in exactly one place. If the part is a question the
lesson is asking, an answer given after asking Adle about it is an aided answer,
the same as one given after the hint (``asked_since``).

Writing the answer is ``GenerationService``'s work; this module only keeps what
came back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from adle_core.errors import NotFoundError
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import LessonAsk, StoredLesson

#: A lesson is not a notebook. Past this many, an older one is removed first.
MAX_ASKS_PER_LESSON = 30
MIN_QUESTION_CHARACTERS = 3
MAX_QUESTION_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class AskCitation:
    """A place in the learner's materials that the answer says it drew on."""

    source_name: str
    locator: str


@dataclass(frozen=True, slots=True)
class AskRecord:
    id: str
    lesson_id: str
    #: The part of the lesson it was asked about.
    segment_id: str
    #: The learner's own words.
    question: str
    paragraphs: list[str]
    citations: list[AskCitation]
    #: Which provider and model wrote the answer, and a note if it was a stand-in.
    written_by: dict[str, Any]
    created_at: datetime


def _record(row: LessonAsk) -> AskRecord:
    answer = row.answer or {}
    return AskRecord(
        id=row.id,
        lesson_id=row.lesson_id,
        segment_id=row.segment_id,
        question=row.question,
        paragraphs=[str(text) for text in answer.get("paragraphs", [])],
        citations=[
            AskCitation(
                source_name=str(item.get("source_name", "")), locator=str(item.get("locator", ""))
            )
            for item in answer.get("citations", [])
            if isinstance(item, dict)
        ],
        written_by=dict(row.written_by or {}),
        created_at=row.created_at,
    )


def asked_since(session: Session, lesson_id: str, segment_id: str, since: datetime | None) -> bool:
    """Whether the learner asked Adle about this part, after ``since`` if that is given."""
    statement = select(LessonAsk.id).where(
        LessonAsk.lesson_id == lesson_id, LessonAsk.segment_id == segment_id
    )
    if since is not None:
        statement = statement.where(LessonAsk.created_at > since)
    return session.scalars(statement.limit(1)).first() is not None


class AskService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def count(self, lesson_id: str) -> int:
        with self._database.read() as session:
            found = session.scalar(
                select(func.count()).select_from(LessonAsk).where(LessonAsk.lesson_id == lesson_id)
            )
            return int(found or 0)

    def store(
        self,
        *,
        lesson_id: str,
        segment_id: str,
        question: str,
        paragraphs: list[str],
        citations: list[AskCitation],
        written_by: dict[str, Any],
        now: datetime | None = None,
    ) -> AskRecord:
        """Keep an answer beside the part it was asked about."""
        with self._database.session() as session:
            lesson = session.get(StoredLesson, lesson_id)
            if lesson is None:
                # Removed while the answer was being written. There is nowhere to keep it.
                raise NotFoundError("That lesson no longer exists.")
            row = LessonAsk(
                id=new_id("ask"),
                course_id=lesson.course_id,
                lesson_id=lesson_id,
                segment_id=segment_id,
                question=question,
                answer={
                    "paragraphs": paragraphs,
                    "citations": [
                        {"source_name": item.source_name, "locator": item.locator}
                        for item in citations
                    ],
                },
                written_by=written_by,
                created_at=now or utc_now(),
            )
            session.add(row)
            session.flush()
            return _record(row)

    def list_for_lesson(self, lesson_id: str) -> list[AskRecord]:
        """Everything asked about a lesson, oldest first."""
        with self._database.read() as session:
            if session.get(StoredLesson, lesson_id) is None:
                raise NotFoundError("That lesson no longer exists.")
            rows = session.scalars(
                select(LessonAsk)
                .where(LessonAsk.lesson_id == lesson_id)
                .order_by(LessonAsk.created_at, LessonAsk.id)
            )
            return [_record(row) for row in rows]

    def get(self, ask_id: str) -> AskRecord:
        with self._database.read() as session:
            row = session.get(LessonAsk, ask_id)
            if row is None:
                raise NotFoundError("That question is no longer kept.")
            return _record(row)

    def delete(self, lesson_id: str, ask_id: str) -> None:
        with self._database.session() as session:
            row = session.get(LessonAsk, ask_id)
            if row is None or row.lesson_id != lesson_id:
                raise NotFoundError("That question is no longer kept.")
            session.delete(row)
