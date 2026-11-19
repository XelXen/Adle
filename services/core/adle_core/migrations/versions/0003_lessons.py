"""Lessons, their scenes, where the learner is in each, and their answers.

Revision: 0003
Previous: 0002
Created:  2026-11-19
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def _owned_by(column: str, table: str, **options: Any) -> sa.Column[str]:
    """A reference whose row is deleted together with the row it points to."""
    return sa.Column(
        column, sa.String(32), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), **options
    )


def upgrade() -> None:
    op.create_table(
        "lessons",
        sa.Column("id", sa.String(32), primary_key=True),
        _owned_by("course_id", "courses", nullable=False),
        _owned_by("concept_id", "concepts", nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("schema_version", sa.String(10), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("origin IN ('sample', 'generated')", name="origin_allowed"),
    )
    op.create_index("ix_lessons_course_id", "lessons", ["course_id"])
    op.create_index("ix_lessons_concept_id", "lessons", ["concept_id"])

    op.create_table(
        "lesson_scenes",
        _owned_by("lesson_id", "lessons", primary_key=True),
        sa.Column("scene_id", sa.String(44), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
    )

    op.create_table(
        "lesson_progress",
        _owned_by("lesson_id", "lessons", primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("started_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _owned_by("course_id", "courses", nullable=False),
        _owned_by("lesson_id", "lessons", nullable=False),
        _owned_by("concept_id", "concepts", nullable=False),
        sa.Column("question_id", sa.String(44), nullable=False),
        sa.Column("form", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("hinted", sa.Boolean(), nullable=False),
        sa.Column("unsure", sa.Boolean(), nullable=False),
        sa.Column("misconception", sa.String(40)),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_attempts_course_id", "attempts", ["course_id"])
    op.create_index("ix_attempts_concept_id", "attempts", ["concept_id"])
    op.create_index("ix_attempts_question", "attempts", ["lesson_id", "question_id"])


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("lesson_progress")
    op.drop_table("lesson_scenes")
    op.drop_table("lessons")
