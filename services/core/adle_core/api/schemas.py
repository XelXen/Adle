"""Request and response models for the HTTP API.

Inputs forbid unknown fields and bound every string. Responses are built from
service records with ``from_attributes`` so the wire shape is defined here, in
one place, and exported to TypeScript by ``npm run contracts``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CourseOrigin = Literal["sample", "topic", "materials"]
SourceKind = Literal["pdf", "docx", "markdown", "text", "authored"]
SourceStatus = Literal["extracted", "needs_attention"]
SectionKind = Literal["document", "page", "heading"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -- courses ---------------------------------------------------------------


class CourseCreate(_Input):
    title: Title
    description: LongText = ""
    #: A learner creates a course from a topic or from materials. Sample courses are built in.
    origin: Literal["topic", "materials"]
    topic: LongText | None = None


class CourseUpdate(_Input):
    title: Title | None = None
    description: LongText | None = None


class Course(_Output):
    id: str
    title: str
    description: str
    origin: CourseOrigin
    topic: str | None
    source_count: int
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None


class CourseList(_Output):
    courses: list[Course]


# -- sources ---------------------------------------------------------------


class Source(_Output):
    id: str
    course_id: str
    display_name: str
    kind: SourceKind
    status: SourceStatus
    #: Learner-readable notes about anything extraction may have missed.
    warnings: list[str]
    size_bytes: int
    char_count: int
    section_count: int
    chunk_count: int
    #: Number of pages with extracted text, for paged documents; otherwise 0.
    page_count: int
    created_at: datetime


class SourceList(_Output):
    sources: list[Source]


class SourceSection(_Output):
    id: str
    ordinal: int
    kind: SectionKind
    title: str | None
    page_number: int | None
    level: int | None
    char_count: int
    #: 0–1: how far the extracted text of this section can be trusted.
    confidence: float


class SourceDetail(_Output):
    source: Source
    sections: list[SourceSection]


class ImportRequest(_Input):
    """Absolute paths chosen by the learner. Only the desktop shell may send this."""

    paths: list[Annotated[str, StringConstraints(min_length=1, max_length=4096)]] = Field(
        min_length=1, max_length=50
    )


class HighlightSegment(_Output):
    text: str
    highlighted: bool


class SearchHit(_Output):
    chunk_id: int
    source_id: str
    source_name: str
    section_title: str | None
    page_number: int | None
    #: The matching passage, split so matched words can be emphasised without markup.
    excerpt: list[HighlightSegment]


class SearchResults(_Output):
    query: str
    hits: list[SearchHit]


# -- jobs ------------------------------------------------------------------


class Job(_Output):
    id: str
    kind: str
    course_id: str | None
    status: JobStatus
    progress_done: int
    progress_total: int
    progress_message: str
    #: Present once the job has finished (or was cancelled part-way).
    result: Any | None
    error_code: str | None
    error_message: str | None
