"""Shared types for document ingestion.

Ingestion turns a file on disk into sections of plain text with provenance.
Everything a document contains is untrusted *data*: it is never interpreted
as instructions, and nothing in it can change what the application does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from adle_core.errors import AdleError


class DocumentKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TEXT = "text"


class SectionKind(StrEnum):
    DOCUMENT = "document"
    PAGE = "page"
    HEADING = "heading"


@dataclass(frozen=True, slots=True)
class Limits:
    """Bounds that keep one import from exhausting memory, disk, or patience."""

    max_file_bytes: int = 50 * 1024 * 1024
    max_text_file_bytes: int = 10 * 1024 * 1024
    max_pages: int = 2_000
    max_characters: int = 5_000_000
    parse_timeout_seconds: float = 120.0


DEFAULT_LIMITS = Limits()


@dataclass(frozen=True, slots=True)
class ExtractedSection:
    kind: SectionKind
    text: str
    title: str | None = None
    #: 1-based, for paged documents.
    page_number: int | None = None
    #: Heading depth, 1 = top level.
    level: int | None = None
    #: 0–1: how far the extracted text can be trusted.
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    kind: DocumentKind
    sections: tuple[ExtractedSection, ...]
    parser: str
    parser_version: str
    #: Learner-readable notes about anything that may have been lost.
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def character_count(self) -> int:
        return sum(len(section.text) for section in self.sections)


class IngestionError(AdleError):
    """A file could not be imported. The message tells the learner what to do about it."""

    status_code = 422

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message, code=code)


def unsupported_type(detail: str) -> IngestionError:
    return IngestionError(
        "unsupported_type",
        f"{detail} Adle can import PDF, Word (.docx), Markdown (.md), and plain text (.txt) "
        "files. Export or save the file in one of those formats and try again.",
    )
