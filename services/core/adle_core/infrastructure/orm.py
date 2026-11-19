"""Persisted models.

These classes describe storage. Rules about what the data *means* (graph
validity, mastery, scheduling) live in ``adle_core.domain`` and operate on
plain values, so they can be tested without a database.

Schema changes always go through an Alembic migration in
``adle_core/migrations/versions``; never rely on ``create_all`` outside tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adle_core.infrastructure.database import Base, UtcDateTime, utc_now

COURSE_ORIGINS = ("sample", "topic", "materials")
SOURCE_KINDS = ("pdf", "docx", "markdown", "text", "authored")
SOURCE_STATUSES = ("extracted", "needs_attention")
SECTION_KINDS = ("document", "page", "heading")
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


def _one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=f"{column}_allowed")


class AppSetting(Base):
    """A single application-level setting (provider address, model, preferences)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (_one_of("origin", COURSE_ORIGINS),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: How the course came to exist. ``sample`` content is authored by Adle and
    #: is always labelled as such in the interface.
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    #: What the learner asked to learn, for courses started from a topic.
    topic: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
    last_opened_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    sources: Mapped[list[Source]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )


class Source(Base):
    """One imported document. The original file is kept under a generated name."""

    __tablename__ = "sources"
    __table_args__ = (
        # The same file imported twice into a course is one source.
        UniqueConstraint("course_id", "content_hash", name="uq_sources_course_hash"),
        _one_of("kind", SOURCE_KINDS),
        _one_of("status", SOURCE_STATUSES),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The name the learner knows the file by. Never used as a path.
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: File name inside the app's ``sources`` directory; ``None`` for authored content.
    stored_name: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Learner-readable extraction warnings, e.g. pages with no selectable text.
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parser: Mapped[str] = mapped_column(String(40), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    course: Mapped[Course] = relationship(back_populates="sources")
    sections: Mapped[list[SourceSection]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceSection.ordinal",
    )
    chunks: Mapped[list[SourceChunk]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceChunk.ordinal",
    )


class SourceSection(Base):
    """A structural unit of a source: a page, a headed section, or the whole document."""

    __tablename__ = "source_sections"
    __table_args__ = (
        UniqueConstraint("source_id", "ordinal", name="uq_source_sections_ordinal"),
        _one_of("kind", SECTION_KINDS),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    #: 1-based page number, for paged formats.
    page_number: Mapped[int | None] = mapped_column(Integer)
    #: Heading depth (1 = top level), for headed formats.
    level: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 0–1. How much the extracted text can be trusted (1 = clean text layer).
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    source: Mapped[Source] = relationship(back_populates="sections")


class SourceChunk(Base):
    """A retrievable passage. Every chunk knows exactly where it came from."""

    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "ordinal", name="uq_source_chunks_ordinal"),
        Index("ix_source_chunks_course", "course_id"),
    )

    # An integer key so the FTS5 index can use it as its rowid.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[str] = mapped_column(
        ForeignKey("source_sections.id", ondelete="CASCADE"), nullable=False
    )
    #: Denormalised so a search can be scoped to a course without joins.
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Offsets into the section's extracted text.
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    source: Mapped[Source] = relationship(back_populates="chunks")
    section: Mapped[SourceSection] = relationship()


class Job(Base):
    """A long-running piece of work the interface can watch and cancel."""

    __tablename__ = "jobs"
    __table_args__ = (_one_of("status", JOB_STATUSES),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    #: ``{"done": int, "total": int, "message": str}``
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[Any | None] = mapped_column(JSON)
    #: ``{"code": str, "message": str}`` when the job failed.
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
