"""Initial schema: settings, courses, sources with full-text search, jobs.

Revision: 0001
Previous: None
Created:  2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("topic", sa.Text()),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.Column("last_opened_at", UtcDateTime()),
        sa.CheckConstraint("origin IN ('sample', 'topic', 'materials')", name="origin_allowed"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(32),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("stored_name", sa.String(80)),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("parser", sa.String(40), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("course_id", "content_hash", name="uq_sources_course_hash"),
        sa.CheckConstraint(
            "kind IN ('pdf', 'docx', 'markdown', 'text', 'authored')", name="kind_allowed"
        ),
        sa.CheckConstraint("status IN ('extracted', 'needs_attention')", name="status_allowed"),
    )
    op.create_index("ix_sources_course_id", "sources", ["course_id"])

    op.create_table(
        "source_sections",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(32),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300)),
        sa.Column("page_number", sa.Integer()),
        sa.Column("level", sa.Integer()),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.UniqueConstraint("source_id", "ordinal", name="uq_source_sections_ordinal"),
        sa.CheckConstraint("kind IN ('document', 'page', 'heading')", name="kind_allowed"),
    )
    op.create_index("ix_source_sections_source_id", "source_sections", ["source_id"])

    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.String(32),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.String(32),
            sa.ForeignKey("source_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.String(32),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("source_id", "ordinal", name="uq_source_chunks_ordinal"),
    )
    op.create_index("ix_source_chunks_source_id", "source_chunks", ["source_id"])
    op.create_index("ix_source_chunks_course", "source_chunks", ["course_id"])

    # Full-text index over chunk text. It is an "external content" index: the
    # text lives once, in source_chunks, and triggers keep the index in step.
    # It can always be rebuilt from the table:
    #   INSERT INTO source_chunks_fts(source_chunks_fts) VALUES ('rebuild');
    op.execute(
        """
        CREATE VIRTUAL TABLE source_chunks_fts USING fts5(
            text,
            content='source_chunks',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_after_insert AFTER INSERT ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(rowid, text) VALUES (new.id, new.text);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_after_delete AFTER DELETE ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(source_chunks_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_after_update AFTER UPDATE OF text ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(source_chunks_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
            INSERT INTO source_chunks_fts(rowid, text) VALUES (new.id, new.text);
        END
        """
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("course_id", sa.String(32), sa.ForeignKey("courses.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="status_allowed",
        ),
    )
    op.create_index("ix_jobs_course_id", "jobs", ["course_id"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.execute("DROP TRIGGER source_chunks_after_update")
    op.execute("DROP TRIGGER source_chunks_after_delete")
    op.execute("DROP TRIGGER source_chunks_after_insert")
    op.execute("DROP TABLE source_chunks_fts")
    op.drop_table("source_chunks")
    op.drop_table("source_sections")
    op.drop_table("sources")
    op.drop_table("courses")
    op.drop_table("app_settings")
