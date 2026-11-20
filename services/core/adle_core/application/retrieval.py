"""Find the passages of a course's materials that bear on a question.

Used wherever Adle needs evidence from the learner's own documents: linking a
concept to its sources, and later grounding generated lessons. Every passage
comes back with its source, section, and page, so nothing retrieved can lose
track of where it came from (PLAN.md 7.3).

Retrieval is behind a small interface. Today it is keyword search (SQLite
FTS5, ranked with BM25), which needs no model and no network. A vector index
can be added as a second implementation without touching callers.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text

from adle_core.infrastructure.database import Database

MAX_PASSAGES = 12
MAX_PASSAGE_CHARACTERS = 2_000
_MAX_TERMS = 24
_CANDIDATE_FACTOR = 5
_WORD = re.compile(r"\w+", re.UNICODE)

_STOP_WORD_LIST = """
    a about above after again against all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its itself just
    me more most my no nor not now of off on once only or other our ours out over own same she
    should so some such than that the their theirs them then there these they this those through
    to too under until up use used using very was we were what when where which while who whom
    why will with would you your yours
"""
#: Words too common to say anything about what a passage is about.
_STOP_WORDS = frozenset(_STOP_WORD_LIST.split())


@dataclass(frozen=True, slots=True)
class Passage:
    chunk_id: int
    source_id: str
    source_name: str
    section_id: str
    section_title: str | None
    page_number: int | None
    text: str


class Retriever(Protocol):
    def retrieve(self, course_id: str, query: str, *, limit: int = 6) -> list[Passage]:
        """The passages of the course most relevant to ``query``, best first."""
        ...


def key_terms(query: str) -> list[str]:
    """The distinct, meaningful words of ``query``, in order."""
    seen: dict[str, None] = {}
    for word in _WORD.findall(query.casefold()):
        if len(word) > 1 and word not in _STOP_WORDS:
            seen.setdefault(word)
    return list(seen)[:_MAX_TERMS]


def any_term_query(query: str) -> str | None:
    """An FTS5 query matching passages that contain any key term. Terms are always quoted."""
    terms = key_terms(query)
    return " OR ".join(f'"{term}"' for term in terms) if terms else None


def spread_across_sources(ranked: Sequence[Passage], limit: int) -> list[Passage]:
    """The best ``limit`` passages, without letting one document crowd out the rest.

    ``ranked`` is best first. A section appears at most once (linking and citing
    work per section), and no source takes more than about half the places while
    another source still has something to offer.
    """
    best_per_section: dict[str, Passage] = {}
    for passage in ranked:
        best_per_section.setdefault(passage.section_id, passage)

    cap = max(1, (limit + 1) // 2)
    taken: Counter[str] = Counter()
    chosen: list[Passage] = []
    held_back: list[Passage] = []
    for passage in best_per_section.values():
        if taken[passage.source_id] < cap:
            chosen.append(passage)
            taken[passage.source_id] += 1
        else:
            held_back.append(passage)
    # Places nobody else wanted go back to the source that was held to its share.
    return [*chosen[:limit], *held_back[: max(0, limit - len(chosen))]]


class FtsRetriever:
    """Keyword retrieval over the full-text index of a course's passages."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def retrieve(self, course_id: str, query: str, *, limit: int = 6) -> list[Passage]:
        match = any_term_query(query)
        if match is None:
            return []
        statement = text(
            """
            SELECT chunk.id, source.id, source.display_name, section.id, section.title,
                   section.page_number, chunk.text
            FROM source_chunks_fts
            JOIN source_chunks AS chunk ON chunk.id = source_chunks_fts.rowid
            JOIN sources AS source ON source.id = chunk.source_id
            JOIN source_sections AS section ON section.id = chunk.section_id
            WHERE source_chunks_fts MATCH :match AND chunk.course_id = :course_id
            ORDER BY bm25(source_chunks_fts), chunk.id
            LIMIT :limit
            """
        )
        limit = max(1, min(limit, MAX_PASSAGES))
        with self._database.read() as session:
            rows = session.execute(
                statement,
                # More than asked for, so that one long document cannot fill every place.
                {"match": match, "course_id": course_id, "limit": limit * _CANDIDATE_FACTOR},
            ).all()
        ranked = [
            Passage(
                chunk_id=row[0],
                source_id=row[1],
                source_name=row[2],
                section_id=row[3],
                section_title=row[4],
                page_number=row[5],
                text=row[6][:MAX_PASSAGE_CHARACTERS],
            )
            for row in rows
        ]
        return spread_across_sources(ranked, limit)
