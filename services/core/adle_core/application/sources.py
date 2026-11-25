"""Importing documents into a course and searching what was imported.

Everything here is local. A source keeps its identity (file name, page or
section) all the way down to each retrievable passage, so anything Adle later
says "comes from your notes" can be traced to the exact place.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from adle_core.application.courses import (
    PROVISIONAL_TITLE,
    get_course_or_404,
    place,
    title_from_file,
)
from adle_core.application.jobs import (
    JobCancelledError,
    JobContext,
    JobRunner,
    JobSnapshot,
    WorkContext,
    side_by_side,
)
from adle_core.errors import NotFoundError, ValidationFailedError
from adle_core.generation.prompts import read_page_request
from adle_core.generation.provider import RequestCancelledError
from adle_core.infrastructure.asset_store import AssetStore, hash_file
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Source, SourceChunk, SourceSection
from adle_core.ingestion.chunking import chunk_document
from adle_core.ingestion.extract import Extractor, extract_isolated, render_isolated
from adle_core.ingestion.parsers import clean_text
from adle_core.ingestion.types import (
    DEFAULT_LIMITS,
    ExtractedDocument,
    ExtractedSection,
    IngestionError,
    Limits,
    SectionKind,
    picture_sentence,
    too_large,
)

if TYPE_CHECKING:
    from adle_core.application.model_gateway import ModelGateway

MAX_FILES_PER_IMPORT = 50
#: The work of reading a file's pages that are pictures (ADR-060).
KIND_READ_PICTURES = "read_pictures"
MAX_SEARCH_RESULTS = 20
_MAX_QUERY_TERMS = 12
# Private-use characters cannot occur in stored text (clean_text removes them),
# so they are safe delimiters for search highlights.
_MARK_OPEN = chr(0xE000)
_MARK_CLOSE = chr(0xE001)
_WORD = re.compile(r"\w+", re.UNICODE)
#: How far a page read from its picture is trusted (ADR-060): a model wrote it out, and a
#: word can be misread, as "fuIcrum" was for "fulcrum" on 2026-11-24.
READ_CONFIDENCE = 0.8
#: The most of a page read from its picture that is kept. A dense page is about 4,000
#: characters; a model that does not stop is not a page.
MAX_READ_CHARACTERS = 20_000
#: What a model writes for a page with nothing on it.
_NO_TEXT = re.compile(r"^\[no text\]\W*$", re.IGNORECASE)

#: Draws one page of a PDF as a PNG picture: the parser worker, or a stand-in in tests.
PageDrawer = Callable[[Path, int], bytes]


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
    #: Pages that are pictures, not read yet (ADR-060).
    picture_pages: list[int] = field(default_factory=list)


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
class CopiedSource:
    """A document as it was read somewhere else: what a course file holds of one."""

    display_name: str
    kind: str
    content_hash: str
    size_bytes: int
    warnings: list[str]
    picture_pages: list[int]
    parser: str
    parser_version: str
    #: Each section: its kind, title, page number, heading level, and how far its text
    #: can be trusted.
    sections: list[tuple[str, str | None, int | None, int | None, float]]
    #: Each passage: which section it is of (by its place above), its text, and where
    #: in the section's text it begins and ends.
    chunks: list[tuple[int, str, int, int]]


@dataclass(frozen=True, slots=True)
class CopiedIds:
    source_id: str
    #: The new identifier of each section, in the order the sections were given.
    section_ids: list[str]


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


def _warnings(stored: Any, picture_pages: Any) -> list[str]:
    """What the learner is told about a file: what was stored, and its pages still pictures."""
    pages = list(picture_pages or [])
    return [*list(stored), *([picture_sentence(pages)] if pages else [])]


#: The most pages read at once, where the provider that reads them takes several requests
#: at once (ADR-068). A page is one request either way (ADR-060).
PAGES_AT_ONCE = 4


def _reading_result(source_id: str, read: list[int], writer: dict[str, str]) -> dict[str, Any]:
    return {"source_id": source_id, "pages_read": sorted(read), "written_by": dict(writer)}


def _waiting(said: Callable[[int, str], None], index: int, seconds: float) -> None:
    said(index, f"Waiting about {max(1, round(seconds))} seconds to stay under the rate limit")


def _busy(said: Callable[[int, str], None], index: int, provider: str) -> None:
    said(index, f"Waiting for {provider} to finish another request")


class SourceService:
    def __init__(
        self,
        database: Database,
        files: AssetStore,
        jobs: JobRunner,
        *,
        extract: Extractor = extract_isolated,
        limits: Limits = DEFAULT_LIMITS,
        gateway: ModelGateway | None = None,
        draw_page: PageDrawer = render_isolated,
    ) -> None:
        self._database = database
        self._files = files
        self._jobs = jobs
        self._extract = extract
        self._limits = limits
        self._gateway = gateway
        self._draw_page = draw_page
        # Looking for a reading under way and starting one are one step.
        self._starting = threading.Lock()

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
                warnings=_warnings(source.warnings, source.picture_pages),
                size_bytes=source.size_bytes,
                char_count=source.char_count,
                section_count=section_count,
                chunk_count=chunk_count,
                page_count=page_count,
                created_at=source.created_at,
                picture_pages=list(source.picture_pages),
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
        # Its pictures stop being read first: nothing more is sent for a file the learner
        # is removing (ADR-060).
        reading = self._jobs.find_active(KIND_READ_PICTURES, source_id)
        if reading is not None:
            with contextlib.suppress(NotFoundError):
                self._jobs.cancel(reading.id)
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
        the files of whatever was there before; and a file removed while a page of it was
        being drawn can leave its original behind (``AssetStore.delete``). Nothing lists
        them and nothing would ever delete them, so a file the learner can no longer see
        would stay on disk. The reverse case needs nothing: a source whose original is
        missing works, and says so where its pictures would be read (ADR-060).

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
            # Asked before any of it is read: a file far past every limit is refused at
            # once, not after reading all of it to see whether it is here already.
            if path.stat().st_size > self._limits.max_file_bytes:
                raise too_large(self._limits.max_file_bytes)
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
            warnings=_warnings(document.warnings, document.picture_pages),
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

    def original_of(self, stored_name: str | None) -> Path | None:
        """Where a source's document is kept, if it still is: a copy of the data does
        not carry the documents, so one may be gone."""
        if not stored_name:
            return None
        try:
            path = self._files.path_for(stored_name)
        except ValueError:
            return None
        return path if path.is_file() else None

    def add_copied(self, course_id: str, copied: CopiedSource, original: Path | None) -> CopiedIds:
        """Add a document as it was read somewhere else (a course brought in from a
        file, ADR-063): its sections and passages as they are given, under identifiers
        made here, and the document itself if it came too. Nothing is read again: a
        page read from a picture at the learner's word (ADR-060) is in the passages
        and in no document."""
        source_id = new_id("src")
        stored_name = (
            self._files.import_file(original, source_id, copied.display_name)
            if original is not None
            else None
        )
        section_ids = [new_id("sec") for _ in copied.sections]
        try:
            with self._database.session() as session:
                get_course_or_404(session, course_id)
                session.add(
                    Source(
                        id=source_id,
                        course_id=course_id,
                        display_name=copied.display_name,
                        kind=copied.kind,
                        content_hash=copied.content_hash,
                        stored_name=stored_name,
                        size_bytes=copied.size_bytes,
                        status=(
                            "needs_attention"
                            if copied.warnings or copied.picture_pages
                            else "extracted"
                        ),
                        warnings=list(copied.warnings),
                        picture_pages=list(copied.picture_pages),
                        parser=copied.parser,
                        parser_version=copied.parser_version,
                        char_count=sum(len(text) for _, text, _, _ in copied.chunks),
                    )
                )
                lengths = [0] * len(copied.sections)
                for section, text, _, end in copied.chunks:
                    lengths[section] = max(lengths[section], end, len(text))
                for ordinal, (kind, title, page_number, level, confidence) in enumerate(
                    copied.sections
                ):
                    session.add(
                        SourceSection(
                            id=section_ids[ordinal],
                            source_id=source_id,
                            ordinal=ordinal,
                            kind=kind,
                            title=title,
                            page_number=page_number,
                            level=level,
                            char_count=lengths[ordinal],
                            confidence=confidence,
                        )
                    )
                session.flush()
                for ordinal, (section, text, start, end) in enumerate(copied.chunks):
                    session.add(
                        SourceChunk(
                            source_id=source_id,
                            section_id=section_ids[section],
                            course_id=course_id,
                            ordinal=ordinal,
                            text=text,
                            char_start=start,
                            char_end=end,
                            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        )
                    )
        except BaseException:
            self._files.delete(stored_name)
            raise
        return CopiedIds(source_id=source_id, section_ids=section_ids)

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
            course = get_course_or_404(session, course_id)
            if course.named_by_adle and course.title == PROVISIONAL_TITLE:
                # Left to Adle to name: for now, after its first file (ADR-053).
                course.title = title_from_file(display_name)
                place(course)
            session.add(
                Source(
                    id=source_id,
                    course_id=course_id,
                    display_name=display_name,
                    kind=kind or document.kind.value,
                    content_hash=content_hash,
                    stored_name=stored_name,
                    size_bytes=size_bytes,
                    status=(
                        "needs_attention"
                        if document.warnings or document.picture_pages
                        else "extracted"
                    ),
                    warnings=list(document.warnings),
                    picture_pages=list(document.picture_pages),
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

    # -- pictures of pages (ADR-060) ----------------------------------------

    def start_reading(self, source_id: str) -> JobSnapshot:
        """Read the pages of a file that are pictures, with a model that sees pictures.

        At the learner's word, for this file alone (ADR-060). Each page is drawn from the
        original in the parser worker, sent as a picture, and what the model writes out
        becomes the page's text: in its place among the file's pages, and searchable and
        quoted like any other as soon as it is stored. A page whose turn comes after the
        file was removed, or after it was read, is left alone.
        """
        if self._gateway is None:
            raise ValidationFailedError("Pictures of pages cannot be read here.")
        with self._database.read() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise NotFoundError("That source no longer exists.")
            pages = list(source.picture_pages)
            course_id, name, stored_name = source.course_id, source.display_name, source.stored_name
        if not pages:
            raise ValidationFailedError("Every page of this file has been read already.")
        original = self._files.path_for(stored_name) if stored_name else None
        if original is None or not original.is_file():
            raise ValidationFailedError(
                "The file itself is no longer here, only its text. Import it again to read "
                "its pictures."
            )
        # Refused before anything is drawn: nobody to ask, or no key to ask with.
        self._gateway.ready_for("read")
        gateway = self._gateway
        with self._starting:
            # Asked twice at once, one reading: the second is shown the first.
            running = self._jobs.find_active(KIND_READ_PICTURES, source_id)
            if running is not None:
                return running
            return self._jobs.submit(
                KIND_READ_PICTURES,
                self._reading(source_id, pages, original, name, gateway),
                course_id=course_id,
                subject_id=source_id,
            )

    def _reading(
        self,
        source_id: str,
        pages: list[int],
        original: Path,
        name: str,
        gateway: ModelGateway,
    ) -> Callable[[JobContext], dict[str, Any]]:
        """The work of reading a file's pictures, a page a request: several pages at once
        where the provider takes several requests at once (ADR-068), each drawn in turn."""

        def work(context: JobContext) -> dict[str, Any]:
            read: list[int] = []
            writer: dict[str, str] = {}
            guard = threading.Lock()
            drawing = threading.Lock()

            def said(done: int, message: str) -> None:
                context.report(done, len(pages), message)

            def one(page: int, shared: WorkContext) -> None:
                with guard:
                    shared.check_cancelled(_reading_result(source_id, read, writer))
                if not self._waiting_to_be_read(source_id, page):
                    return
                said(len(read), f"Reading page {page}")
                try:
                    with drawing:
                        # Not drawn once the reading has stopped: the file may be going.
                        if shared.cancelled:
                            with guard:
                                stopped = _reading_result(source_id, read, writer)
                            raise JobCancelledError(stopped)
                        picture = self._draw_page(original, page)
                except IngestionError:
                    # This page cannot be drawn; the others can still be read.
                    return
                try:
                    result = gateway.complete(
                        read_page_request(name, page, picture),
                        cancelled=lambda: shared.cancelled,
                        on_wait=partial(_waiting, said, len(read)),
                        on_busy=partial(_busy, said, len(read)),
                    )
                except RequestCancelledError as error:
                    with guard:
                        partial_result = _reading_result(source_id, read, writer)
                    raise JobCancelledError(partial_result) from error
                self._store_read_page(source_id, page, result.text)
                with guard:
                    read.append(page)
                    writer.update(provider=result.provider_name, model=result.model_name)

            side_by_side(pages, one, context, min(PAGES_AT_ONCE, gateway.at_once("read")))
            said(len(pages), "")
            return _reading_result(source_id, read, writer)

        return work

    def _waiting_to_be_read(self, source_id: str, page: int) -> bool:
        with self._database.read() as session:
            source = session.get(Source, source_id)
            return source is not None and page in source.picture_pages

    def _store_read_page(self, source_id: str, page: int, written: str) -> None:
        """A page read from its picture, kept as the page's text in its place in the file.

        The file's sections and passages are numbered again so that the page comes where it
        stands in the file; what was there keeps its rows, and every passage its id.
        """
        text = clean_text(written)[:MAX_READ_CHARACTERS]
        if _NO_TEXT.match(text):
            text = ""
        section = ExtractedSection(
            kind=SectionKind.PAGE, text=text, page_number=page, confidence=READ_CONFIDENCE
        )
        chunks = chunk_document((section,)) if text else []
        with self._database.session() as session:
            source = session.get(Source, source_id)
            if source is None or page not in source.picture_pages:
                return
            source.picture_pages = [listed for listed in source.picture_pages if listed != page]
            if not source.warnings and not source.picture_pages:
                source.status = "extracted"
            if not text:
                return
            source.char_count += len(text)
            sections = list(
                session.scalars(
                    select(SourceSection)
                    .where(SourceSection.source_id == source_id)
                    .order_by(SourceSection.ordinal)
                )
            )
            # Where the page goes: before the first section that begins after it.
            place = next(
                (
                    position
                    for position, existing in enumerate(sections)
                    if existing.page_number is not None and existing.page_number > page
                ),
                len(sections),
            )
            stored = SourceSection(
                id=new_id("sec"),
                source_id=source_id,
                ordinal=-1,
                kind=section.kind.value,
                title=None,
                page_number=page,
                level=None,
                char_count=len(text),
                confidence=READ_CONFIDENCE,
            )
            ordered = [*sections[:place], stored, *sections[place:]]
            passages = list(
                session.scalars(
                    select(SourceChunk)
                    .where(SourceChunk.source_id == source_id)
                    .order_by(SourceChunk.ordinal)
                )
            )
            # Numbered again in two steps: every number unique at every moment.
            for offset, existing in enumerate(sections):
                existing.ordinal = -(offset + 2)
            for offset, passage in enumerate(passages):
                passage.ordinal = -(offset + 2)
            session.add(stored)
            session.flush()
            for ordinal, row in enumerate(ordered):
                row.ordinal = ordinal
            by_section: dict[str, list[SourceChunk]] = {}
            for passage in passages:
                by_section.setdefault(passage.section_id, []).append(passage)
            ordinal = 0
            for row in ordered:
                if row is stored:
                    for chunk in chunks:
                        session.add(
                            SourceChunk(
                                source_id=source_id,
                                section_id=stored.id,
                                course_id=source.course_id,
                                ordinal=ordinal,
                                text=chunk.text,
                                char_start=chunk.char_start,
                                char_end=chunk.char_end,
                                content_hash=chunk.content_hash,
                            )
                        )
                        ordinal += 1
                    continue
                for passage in by_section.get(row.id, []):
                    passage.ordinal = ordinal
                    ordinal += 1

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
