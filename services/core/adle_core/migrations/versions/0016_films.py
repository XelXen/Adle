"""Films of whole courses.

Revision: 0016
Previous: 0015
Created:  2026-11-24

``films`` holds a film of a whole course (ADR-065): one a course, its chapters and how
each was made, the voice it is read in, and, once it is made, how long it is and when each
chapter begins. The video itself is a file beside the database.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "films",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(32),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("chapters", sa.JSON(), nullable=False),
        sa.Column("voice", sa.JSON()),
        sa.Column("seconds", sa.Float()),
        sa.Column("size", sa.Integer()),
        sa.Column("marks", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("written_by", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.Column("finished_at", UtcDateTime()),
        sa.CheckConstraint("status IN ('making', 'unfinished', 'ready')", name="status_allowed"),
    )


def downgrade() -> None:
    op.drop_table("films")
