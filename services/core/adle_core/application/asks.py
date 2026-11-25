"""Questions the learner puts to Adle in the middle of a lesson, kept beside it.

Called an "ask" to keep it apart from the questions a lesson puts to the learner.
An ask belongs to one part of one lesson. It is a note in the margin, not a
conversation: each stands alone, and nothing is scored from it.

That one was asked matters in exactly one place. If the part is a question the
lesson is asking, an answer given after asking Adle about it is an aided answer,
the same as one given after the hint (``asked_since``).

An answer can carry the part's picture drawn again, when the learner asked for that
(ADR-067). It joins the lesson only when the learner uses it, and the part's own picture is
kept with the note to be put back; removing the note puts it back too, so that nothing of a
removed note stays in the lesson.

Writing the answer is ``GenerationService``'s work; this module only keeps what
came back.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from adle_core.application.lessons import replace_picture
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


#: Where a picture drawn again for a note stands (ADR-067): offered beside the answer, or
#: in use in the lesson.
OFFERED, IN_USE = "offered", "in_use"


@dataclass(frozen=True, slots=True)
class AskPicture:
    """A part's picture, drawn again because the learner asked, kept with the answer."""

    state: str
    #: What it shows, in words.
    description: str


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
    #: The part's picture drawn again, when the learner asked for that.
    picture: AskPicture | None = None


def _picture(answer: Mapping[str, Any]) -> AskPicture | None:
    kept = answer.get("picture")
    if not isinstance(kept, dict) or not isinstance(kept.get("source"), str):
        return None
    return AskPicture(
        state=IN_USE if kept.get("in_use") else OFFERED,
        description=str(kept.get("described", "")),
    )


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
        picture=_picture(answer),
    )


def asked_since(session: Session, lesson_id: str, segment_id: str, since: datetime | None) -> bool:
    """Whether the learner asked Adle about this part, after ``since`` if that is given.

    A note the learner has since removed still counts: they read the answer.
    """
    statement = select(LessonAsk.id).where(
        LessonAsk.lesson_id == lesson_id, LessonAsk.segment_id == segment_id
    )
    if since is not None:
        statement = statement.where(LessonAsk.created_at > since)
    return session.scalars(statement.limit(1)).first() is not None


#: What is left of a note the learner removed: no words, only that it was asked.
REMOVED = ""
_KEPT = LessonAsk.question != REMOVED


class AskService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def count(self, lesson_id: str) -> int:
        with self._database.read() as session:
            found = session.scalar(
                select(func.count())
                .select_from(LessonAsk)
                .where(LessonAsk.lesson_id == lesson_id, _KEPT)
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
        picture: Mapping[str, Any] | None = None,
    ) -> AskRecord:
        """Keep an answer beside the part it was asked about, with the part's picture drawn
        again when the learner asked for that: its scene, what it shows, and where its steps
        fall in the part's words (ADR-067). Nothing of it joins the lesson yet."""
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
                    **({"picture": {**picture, "in_use": False}} if picture else {}),
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
                .where(LessonAsk.lesson_id == lesson_id, _KEPT)
                .order_by(LessonAsk.created_at, LessonAsk.id)
            )
            return [_record(row) for row in rows]

    def get(self, ask_id: str) -> AskRecord:
        with self._database.read() as session:
            row = session.get(LessonAsk, ask_id)
            if row is None or row.question == REMOVED:
                raise NotFoundError("That question no longer exists.")
            return _record(row)

    def delete(self, lesson_id: str, ask_id: str) -> None:
        with self._database.session() as session:
            row = _kept(session, lesson_id, ask_id)
            # A picture of this note's in the lesson goes with it: the part has its own back.
            lesson = session.get(StoredLesson, lesson_id)
            if lesson is not None:
                _put_back(session, lesson, row)
            # The words go: the learner's question, the answer, and who wrote it. That
            # something was asked about this part, and when, stays, because an answer
            # to the lesson's own question given afterwards was still an aided one.
            row.question = REMOVED
            row.answer = {}
            row.written_by = {}

    def use_picture(self, lesson_id: str, ask_id: str) -> None:
        """Put the picture a note drew into its part of the lesson, in place of the part's
        own (ADR-067), at the learner's press. Another note's picture in that part is taken
        out first, so that what is put back is always the part's own."""
        with self._database.session() as session:
            row = _kept(session, lesson_id, ask_id)
            kept = dict((row.answer or {}).get("picture") or {})
            if not isinstance(kept.get("source"), str):
                raise NotFoundError("That answer has no picture.")
            if kept.get("in_use"):
                return
            lesson = session.get(StoredLesson, lesson_id)
            if lesson is None:
                raise NotFoundError("That lesson no longer exists.")
            others = session.scalars(
                select(LessonAsk).where(
                    LessonAsk.lesson_id == lesson_id,
                    LessonAsk.segment_id == row.segment_id,
                    LessonAsk.id != row.id,
                )
            ).all()
            for other in others:
                _put_back(session, lesson, other)
            scene_id = f"scn_ask_{secrets.token_hex(5)}"
            given = kept.get("cues")
            cues: list[Any] = given if isinstance(given, list) else []
            had = replace_picture(
                session,
                lesson,
                row.segment_id,
                {
                    "id": scene_id,
                    "purpose": "This part's picture, drawn again as the learner asked.",
                    "source": kept["source"],
                    "fallback_text": str(kept.get("described") or "A picture of this part."),
                },
                [{"cues": line, "advance_scene": False} for line in cues],
            )
            row.answer = {
                **(row.answer or {}),
                "picture": {**kept, "in_use": True, "scene_id": scene_id, "original": had},
            }

    def put_back(self, lesson_id: str, ask_id: str) -> None:
        """Give a part its own picture back, in place of the one a note drew."""
        with self._database.session() as session:
            row = _kept(session, lesson_id, ask_id)
            lesson = session.get(StoredLesson, lesson_id)
            if lesson is None:
                raise NotFoundError("That lesson no longer exists.")
            _put_back(session, lesson, row)


def _kept(session: Session, lesson_id: str, ask_id: str) -> LessonAsk:
    row = session.get(LessonAsk, ask_id)
    if row is None or row.lesson_id != lesson_id or row.question == REMOVED:
        raise NotFoundError("That question no longer exists.")
    return row


def _put_back(session: Session, lesson: StoredLesson, row: LessonAsk) -> None:
    """The part's own picture back, if this note's is in use there; nothing otherwise."""
    kept = dict((row.answer or {}).get("picture") or {})
    if not kept.get("in_use"):
        return
    found = kept.get("original")
    original: dict[str, Any] = found if isinstance(found, dict) else {}
    scene = original.get("scene")
    narration = original.get("narration")
    replace_picture(
        session,
        lesson,
        row.segment_id,
        scene if isinstance(scene, dict) else None,
        narration if isinstance(narration, list) else [],
    )
    kept.pop("original", None)
    kept.pop("scene_id", None)
    kept["in_use"] = False
    row.answer = {**(row.answer or {}), "picture": kept}
