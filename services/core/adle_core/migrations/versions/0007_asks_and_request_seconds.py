"""Questions asked during a lesson, and how long each model request took.

Revision: 0007
Previous: 0006
Created:  2026-11-20

``lesson_asks`` holds what the learner asked Adle about one part of a lesson and the
answer that came back (ADR-024). ``model_usage.seconds`` is how long an answer took to
arrive, so that the next wait can be described from what was measured on this computer.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def _owned_by(column: str, table: str, **options: Any) -> sa.Column[str]:
    """A reference whose row is deleted together with the row it points to."""
    return sa.Column(
        column, sa.String(32), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), **options
    )


def upgrade() -> None:
    op.add_column("model_usage", sa.Column("seconds", sa.Float()))

    op.create_table(
        "lesson_asks",
        sa.Column("id", sa.String(32), primary_key=True),
        _owned_by("course_id", "courses", nullable=False),
        _owned_by("lesson_id", "lessons", nullable=False),
        sa.Column("segment_id", sa.String(44), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("written_by", sa.JSON(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_lesson_asks_course_id", "lesson_asks", ["course_id"])
    op.create_index("ix_lesson_asks_lesson_id", "lesson_asks", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("lesson_asks")
    with op.batch_alter_table("model_usage") as batch:
        batch.drop_column("seconds")
