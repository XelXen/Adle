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

#: Joins the chain of headings above a section into its title: "Chapter 2 › Loss".
#: Parsers remove the separator from heading text, so a title always splits cleanly.
HEADING_PATH_SEPARATOR = " › "


def heading_leaf(path: str) -> str:
    """The innermost heading of a stored heading path ("Chapter 2 › Loss" gives "Loss")."""
    return path.rsplit(HEADING_PATH_SEPARATOR, 1)[-1]


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
    #: Pages that are pictures: no text to select (a scan, a photograph, handwriting), or a
    #: drawing the reader could not take apart. A model that sees pictures can read them,
    #: at the learner's word (ADR-060). 1-based, in order.
    picture_pages: tuple[int, ...] = field(default_factory=tuple)

    @property
    def character_count(self) -> int:
        return sum(len(section.text) for section in self.sections)


def picture_sentence(pages: tuple[int, ...] | list[int]) -> str:
    """What the learner is told about the pages of a file that are pictures."""
    if not pages:
        return ""
    if len(pages) == 1:
        return f"Page {pages[0]} is a picture, with no text to select."
    if len(pages) > 6:
        return f"{len(pages)} pages are pictures, with no text to select."
    listed = ", ".join(str(page) for page in pages[:-1])
    return (
        f"{len(pages)} pages are pictures, with no text to select (pages {listed} and {pages[-1]})."
    )


class IngestionError(AdleError):
    """A file could not be imported. The message tells the learner what to do about it."""

    status_code = 422

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message, code=code)


def too_large(ceiling: int) -> IngestionError:
    """A file over the limit for its kind, in megabytes a learner can act on."""
    return IngestionError(
        "file_too_large",
        f"The file is larger than {ceiling // (1024 * 1024)} MB. "
        "Split it into smaller parts and import them separately.",
    )


def unsupported_type(detail: str) -> IngestionError:
    return IngestionError(
        "unsupported_type",
        f"{detail} Adle can import PDF, Word (.docx), Markdown (.md), and plain text (.txt) "
        "files. Export or save the file in one of those formats and try again.",
    )
