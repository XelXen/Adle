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
    Boolean,
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
CONCEPT_ORIGINS = ("learner", "outline", "model", "sample")
CONCEPT_TAGS = ("conceptual", "calculation", "visual", "procedural")
OBSERVATION_KINDS = ("answer", "self_report")
MASTERY_STATES = ("not_assessed", "building", "needs_evidence", "demonstrated")
LESSON_ORIGINS = ("sample", "generated")
MODEL_USAGE_OUTCOMES = (
    "pending",
    "ok",
    "rate_limited",
    "refused",
    "unavailable",
    "unreadable",
    "cancelled",
)


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


class Concept(Base):
    """One thing to learn in a course: a node of the curriculum graph."""

    __tablename__ = "concepts"
    __table_args__ = (
        _one_of("origin", CONCEPT_ORIGINS),
        CheckConstraint("complexity BETWEEN 1 AND 3", name="complexity_range"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: The learner's own ordering. The learning order also respects prerequisites.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Expected lesson size: 1 short, 2 medium, 3 long.
    complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    #: Kinds of learning involved, from ``CONCEPT_TAGS``.
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    #: Who proposed the concept. Anything not from the learner stays labelled.
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)

    objectives: Mapped[list[LearningObjective]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LearningObjective.position",
    )
    prerequisite_links: Mapped[list[ConceptEdge]] = relationship(
        foreign_keys="ConceptEdge.concept_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    source_refs: Mapped[list[ConceptSourceRef]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="ConceptSourceRef.id"
    )


class LearningObjective(Base):
    """Something observable a learner should be able to do once they have the concept."""

    __tablename__ = "learning_objectives"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    statement: Mapped[str] = mapped_column(String(400), nullable=False)


class ConceptEdge(Base):
    """``concept_id`` needs ``prerequisite_id`` first."""

    __tablename__ = "concept_edges"
    __table_args__ = (
        CheckConstraint("concept_id <> prerequisite_id", name="no_self_prerequisite"),
        _one_of("origin", CONCEPT_ORIGINS),
    )

    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    prerequisite_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    #: Why the prerequisite is needed, in words the learner can read.
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(20), nullable=False)


class ConceptSourceRef(Base):
    """Where in the learner's materials a concept is covered."""

    __tablename__ = "concept_source_refs"
    __table_args__ = (
        UniqueConstraint("concept_id", "section_id", name="uq_concept_source_refs_section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[str] = mapped_column(
        ForeignKey("source_sections.id", ondelete="CASCADE"), nullable=False
    )

    source: Mapped[Source] = relationship()
    section: Mapped[SourceSection] = relationship()


class LearnerPreference(Base):
    """One explicit choice the learner has made about how they like to learn."""

    __tablename__ = "learner_preferences"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class LearnerObservation(Base):
    """One piece of evidence about a concept, with the change it caused. Append-only.

    The state of a concept is the fold of these rows (``learner_model.tracing``),
    so every change of state has a row that caused it and a sentence that
    explains it.
    """

    __tablename__ = "learner_observations"
    __table_args__ = (
        _one_of("kind", OBSERVATION_KINDS),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'partial', 'incorrect', 'skipped')",
            name="outcome_allowed",
        ),
        CheckConstraint(
            "self_report IS NULL OR self_report IN ('new', 'some', 'confident')",
            name="self_report_allowed",
        ),
        Index("ix_learner_observations_concept", "concept_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(20))
    question_form: Mapped[str | None] = mapped_column(String(30))
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hinted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unsure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    item_guess: Mapped[float | None] = mapped_column(Float)
    self_report: Mapped[str | None] = mapped_column(String(20))
    state_before: Mapped[str] = mapped_column(String(20), nullable=False)
    state_after: Mapped[str] = mapped_column(String(20), nullable=False)
    #: What happened and what it means, as shown to the learner.
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    #: Which tracing parameters produced the change (``TracingConfig.version``).
    config_version: Mapped[str] = mapped_column(String(20), nullable=False)


class LearnerConceptState(Base):
    """What the observations of one concept add up to. Rebuildable from them at any time."""

    __tablename__ = "learner_concept_states"
    __table_args__ = (_one_of("state", MASTERY_STATES),)

    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Internal estimate. Never sent to the interface.
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    #: What is still needed before the concept counts as demonstrated.
    missing: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unaided_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hinted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forms_correct: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    transfer_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    self_report: Mapped[str | None] = mapped_column(String(20))
    last_observed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    review_interval_days: Mapped[float | None] = mapped_column(Float)
    review_due_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    review_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class StoredLesson(Base):
    """A validated lesson (``lessons.ir.Lesson``), kept as the document the player loads."""

    __tablename__ = "lessons"
    __table_args__ = (_one_of("origin", LESSON_ORIGINS),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The first concept the lesson teaches; lessons are listed under it.
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: ``sample`` lessons were written by Adle; ``generated`` ones by the configured model.
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The lesson exactly as validated. Read back through the IR, never used raw.
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    scenes: Mapped[list[StoredScene]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="StoredScene.position"
    )
    progress: Mapped[LessonProgress | None] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class StoredScene(Base):
    """One complete scene file belonging to a lesson (``lessons.ir.SceneArtifact``)."""

    __tablename__ = "lesson_scenes"

    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    scene_id: Mapped[str] = mapped_column(String(44), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class LessonProgress(Base):
    """Where the learner is in a lesson, saved at segment boundaries."""

    __tablename__ = "lesson_progress"

    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    #: Index of the segment to resume at.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class Attempt(Base):
    """One answer (or explicit skip) to a question of a lesson."""

    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_question", "lesson_id", "question_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(44), nullable=False)
    form: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    hinted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unsure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: The kind of mistake the answer suggests, if any. A hypothesis only.
    misconception: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class ModelUsage(Base):
    """One request sent to the model provider.

    The local estimate of how much of the provider's allowance has been used is
    computed from these rows (``generation.quota``). A row is written before the
    request is sent, so a request that never returns still counts.
    """

    __tablename__ = "model_usage"
    __table_args__ = (_one_of("outcome", MODEL_USAGE_OUTCOMES),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, index=True)
    #: What the request was for (``curriculum``, ``lesson``, ``scene``). Never its content.
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: True while the token counts are Adle's own estimate rather than the provider's report.
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class Job(Base):
    """A long-running piece of work the interface can watch and cancel."""

    __tablename__ = "jobs"
    __table_args__ = (_one_of("status", JOB_STATUSES),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    #: What the job is about, when it is about one thing (a concept for a lesson job).
    #: Lets a repeated request find the job that is already doing the work.
    subject_id: Mapped[str | None] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    #: ``{"done": int, "total": int, "message": str}``
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[Any | None] = mapped_column(JSON)
    #: ``{"code": str, "message": str}`` when the job failed.
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
