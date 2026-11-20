"""Importing documents into a course and searching what was imported.

Everything here is local. A source keeps its identity (file name, page or
section) all the way down to each retrievable passage, so anything Adle later
says "comes from your notes" can be traced to the exact place.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from adle_core.application.courses import get_course_or_404
from adle_core.application.jobs import JobContext, JobRunner, JobSnapshot
from adle_core.errors import NotFoundError, ValidationFailedError
from adle_core.infrastructure.asset_store import AssetStore, hash_file
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Source, SourceChunk, SourceSection
from adle_core.ingestion.chunking import chunk_document
from adle_core.ingestion.extract import Extractor, extract_isolated
from adle_core.ingestion.types import DEFAULT_LIMITS, ExtractedDocument, IngestionError, Limits

MAX_FILES_PER_IMPORT = 50
MAX_SEARCH_RESULTS = 20
_MAX_QUERY_TERMS = 12
# Private-use characters cannot occur in stored text (clean_text removes them),
# so they are safe delimiters for search highlights.
_MARK_OPEN = chr(0xE000)
_MARK_CLOSE = chr(0xE001)
_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SourceRecord:
    id: str
    course_id: str
    display_name: str
    kind: str
    status: str
    warnings: list[str]
    size_bytes: int
    char_count: int
    section_count: int
    chunk_count: int
    page_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SectionRecord:
    id: str
    ordinal: int
    kind: str
    title: str | None
    page_number: int | None
    level: int | None
    char_count: int
    confidence: float


@dataclass(frozen=True, slots=True)
class SourceDetail:
    source: SourceRecord
    sections: list[SectionRecord]


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    file_name: str
    #: ``imported``, ``duplicate`` (already in this course), or ``rejected``.
    outcome: str
    source_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "outcome": self.outcome,
            "source_id": self.source_id,
            "error_code": self.error_code,
            "message": self.message,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class HighlightSegment:
    text: str
    highlighted: bool


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: int
    source_id: str
    source_name: str
    section_title: str | None
    page_number: int | None
    excerpt: list[HighlightSegment]


def display_name_for(path: Path) -> str:
    """A safe label for a file: its base name, without control characters, bounded."""
    name = "".join(ch for ch in path.name if unicodedata.category(ch)[0] != "C").strip()
    return name[:255] or "Untitled file"


def build_match_query(query: str, *, require_all: bool) -> str | None:
    """Turn free text into an FTS5 query. Returns ``None`` if there is nothing to search for.

    Every term is quoted, so no user input is ever interpreted as FTS5 syntax.
    The final term matches as a prefix, which suits searching while typing.
    """
    terms = _WORD.findall(query)[:_MAX_QUERY_TERMS]
    if not terms:
        return None
    quoted = [f'"{term}"' for term in terms]
    quoted[-1] += "*"
    return (" AND " if require_all else " OR ").join(quoted)


def _split_highlights(marked: str) -> list[HighlightSegment]:
    segments: list[HighlightSegment] = []
    for index, piece in enumerate(re.split(f"[{_MARK_OPEN}{_MARK_CLOSE}]", marked)):
        if piece:
            segments.append(HighlightSegment(text=piece, highlighted=index % 2 == 1))
    return segments


class SourceService:
    def __init__(
        self,
        database: Database,
        files: AssetStore,
        jobs: JobRunner,
        *,
        extract: Extractor = extract_isolated,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        self._database = database
        self._files = files
        self._jobs = jobs
        self._extract = extract
        self._limits = limits

    # -- reading -----------------------------------------------------------

    def _records(self, session: Session, *conditions: Any) -> list[SourceRecord]:
        sections = (
            select(
                SourceSection.source_id,
                func.count(SourceSection.id).label("section_count"),
                func.count(SourceSection.page_number).label("page_count"),
            )
            .group_by(SourceSection.source_id)
            .subquery()
        )
        chunks = (
            select(SourceChunk.source_id, func.count(SourceChunk.id).label("chunk_count"))
            .group_by(SourceChunk.source_id)
            .subquery()
        )
        statement = (
            select(
                Source,
                func.coalesce(sections.c.section_count, 0),
                func.coalesce(sections.c.page_count, 0),
                func.coalesce(chunks.c.chunk_count, 0),
            )
            .outerjoin(sections, sections.c.source_id == Source.id)
            .outerjoin(chunks, chunks.c.source_id == Source.id)
            .where(*conditions)
            .order_by(Source.created_at, Source.id)
        )
        return [
            SourceRecord(
                id=source.id,
                course_id=source.course_id,
                display_name=source.display_name,
                kind=source.kind,
                status=source.status,
                warnings=list(source.warnings),
                size_bytes=source.size_bytes,
                char_count=source.char_count,
                section_count=section_count,
                chunk_count=chunk_count,
                page_count=page_count,
                created_at=source.created_at,
            )
            for source, section_count, page_count, chunk_count in session.execute(statement)
        ]

    def list_for_course(self, course_id: str) -> list[SourceRecord]:
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            return self._records(session, Source.course_id == course_id)

    def get(self, source_id: str) -> SourceDetail:
        with self._database.read() as session:
            records = self._records(session, Source.id == source_id)
            if not records:
                raise NotFoundError("That source no longer exists.")
            sections = session.scalars(
                select(SourceSection)
                .where(SourceSection.source_id == source_id)
                .order_by(SourceSection.ordinal)
            )
            return SourceDetail(
                source=records[0],
                sections=[
                    SectionRecord(
                        id=section.id,
                        ordinal=section.ordinal,
                        kind=section.kind,
                        title=section.title,
                        page_number=section.page_number,
                        level=section.level,
                        char_count=section.char_count,
                        confidence=section.confidence,
                    )
                    for section in sections
                ],
            )

    def delete(self, source_id: str) -> None:
        with self._database.session() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError("That source no longer exists.")
            stored_name = source.stored_name
            session.delete(source)
        self._files.delete(stored_name)

    def forget_unreferenced_files(self) -> int:
        """Delete stored originals that no source refers to. Returns how many.

        After the data has been replaced by a copy, the folder of originals still holds
        the files of whatever was there before. Nothing lists them and nothing would
        ever delete them, so a file the learner can no longer see would stay on disk.
        The reverse case needs nothing: a source whose original is missing works, since
        an original is not read again after import, and nothing may come to rely on it.

        Call only while nothing is being imported (at start-up, before serving).
        """
        with self._database.read() as session:
            names = {name for name in session.scalars(select(Source.stored_name)) if name}
        return self._files.keep_only(names)

    # -- importing ---------------------------------------------------------

    def start_import(self, course_id: str, paths: list[Path]) -> JobSnapshot:
        """Queue an import of ``paths`` into the course and return the job to watch."""
        if not paths:
            raise ValidationFailedError("Choose at least one file to import.")
        if len(paths) > MAX_FILES_PER_IMPORT:
            raise ValidationFailedError(f"Import at most {MAX_FILES_PER_IMPORT} files at a time.")
        with self._database.read() as session:
            get_course_or_404(session, course_id)

        def work(context: JobContext) -> dict[str, Any]:
            outcomes: list[dict[str, Any]] = []
            for index, path in enumerate(paths):
                context.check_cancelled({"files": outcomes})
                context.report(index, len(paths), display_name_for(path))
                outcomes.append(self.import_file(course_id, path).as_dict())
            context.report(len(paths), len(paths))
            return {"files": outcomes}

        return self._jobs.submit("import_sources", work, course_id=course_id)

    def import_file(self, course_id: str, path: Path) -> ImportOutcome:
        """Import one file. Never raises for a bad file: the outcome says what happened."""
        name = display_name_for(path)
        try:
            if not path.is_file():
                raise IngestionError(
                    "file_unreadable",
                    "The file could not be opened. It may have been moved or deleted.",
                )
            content_hash, size = hash_file(path)
            with self._database.session() as session:
                existing = session.scalar(
                    select(Source.id).where(
                        Source.course_id == course_id, Source.content_hash == content_hash
                    )
                )
            if existing is not None:
                return ImportOutcome(
                    file_name=name,
                    outcome="duplicate",
                    source_id=existing,
                    message="This file is already in the course.",
                )
            document = self._extract(path, name, self._limits)
        except IngestionError as error:
            return ImportOutcome(
                file_name=name, outcome="rejected", error_code=error.code, message=error.message
            )
        except OSError:
            return ImportOutcome(
                file_name=name,
                outcome="rejected",
                error_code="file_unreadable",
                message="The file could not be read. Check that it still exists and try again.",
            )

        source_id = new_id("src")
        stored_name = self._files.import_file(path, source_id, name)
        try:
            self._store(course_id, source_id, name, content_hash, size, stored_name, document)
        except IntegrityError:
            # Lost a race with an identical import; the other copy is the source.
            self._files.delete(stored_name)
            return ImportOutcome(
                file_name=name, outcome="duplicate", message="This file is already in the course."
            )
        except BaseException:
            self._files.delete(stored_name)
            raise
        return ImportOutcome(
            file_name=name,
            outcome="imported",
            source_id=source_id,
            warnings=list(document.warnings),
        )

    def add_authored_source(
        self, course_id: str, display_name: str, document: ExtractedDocument, content_hash: str
    ) -> str:
        """Add content written by Adle itself (the sample course). No file is stored."""
        source_id = new_id("src")
        self._store(
            course_id, source_id, display_name, content_hash, 0, None, document, kind="authored"
        )
        return source_id

    def _store(
        self,
        course_id: str,
        source_id: str,
        display_name: str,
        content_hash: str,
        size_bytes: int,
        stored_name: str | None,
        document: ExtractedDocument,
        *,
        kind: str | None = None,
    ) -> None:
        chunks = chunk_document(document.sections)
        with self._database.session() as session:
            get_course_or_404(session, course_id)
            session.add(
                Source(
                    id=source_id,
                    course_id=course_id,
                    display_name=display_name,
                    kind=kind or document.kind.value,
                    content_hash=content_hash,
                    stored_name=stored_name,
                    size_bytes=size_bytes,
                    status="needs_attention" if document.warnings else "extracted",
                    warnings=list(document.warnings),
                    parser=document.parser,
                    parser_version=document.parser_version,
                    char_count=document.character_count,
                )
            )
            section_ids: list[str] = []
            for ordinal, section in enumerate(document.sections):
                section_id = new_id("sec")
                section_ids.append(section_id)
                session.add(
                    SourceSection(
                        id=section_id,
                        source_id=source_id,
                        ordinal=ordinal,
                        kind=section.kind.value,
                        title=section.title,
                        page_number=section.page_number,
                        level=section.level,
                        char_count=len(section.text),
                        confidence=section.confidence,
                    )
                )
            session.flush()
            for ordinal, chunk in enumerate(chunks):
                session.add(
                    SourceChunk(
                        source_id=source_id,
                        section_id=section_ids[chunk.section_index],
                        course_id=course_id,
                        ordinal=ordinal,
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        content_hash=chunk.content_hash,
                    )
                )

    # -- searching ---------------------------------------------------------

    def search(self, course_id: str, query: str, limit: int = 8) -> list[SearchHit]:
        """Keyword search over a course's passages, best matches first, with provenance.

        Tries to match every term; if nothing does, falls back to any term so a
        slightly-off query still finds something.
        """
        limit = max(1, min(limit, MAX_SEARCH_RESULTS))
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            for require_all in (True, False):
                match = build_match_query(query, require_all=require_all)
                if match is None:
                    return []
                hits = self._run_search(session, course_id, match, limit)
                if hits:
                    return hits
        return []

    def _run_search(
        self, session: Session, course_id: str, match: str, limit: int
    ) -> list[SearchHit]:
        statement = text(
            """
            SELECT chunk.id, source.id, source.display_name, section.title, section.page_number,
                   snippet(source_chunks_fts, 0, :open, :close, '…', 40) AS excerpt
            FROM source_chunks_fts
            JOIN source_chunks AS chunk ON chunk.id = source_chunks_fts.rowid
            JOIN sources AS source ON source.id = chunk.source_id
            JOIN source_sections AS section ON section.id = chunk.section_id
            WHERE source_chunks_fts MATCH :match AND chunk.course_id = :course_id
            ORDER BY bm25(source_chunks_fts), chunk.id
            LIMIT :limit
            """
        )
        rows = session.execute(
            statement,
            {
                "match": match,
                "course_id": course_id,
                "limit": limit,
                "open": _MARK_OPEN,
                "close": _MARK_CLOSE,
            },
        )
        return [
            SearchHit(
                chunk_id=row[0],
                source_id=row[1],
                source_name=row[2],
                section_title=row[3],
                page_number=row[4],
                excerpt=_split_highlights(row[5]),
            )
            for row in rows
        ]
