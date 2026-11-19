"""A record of each request sent to the model provider, and what a job is about.

Revision: 0004
Previous: 0003
Created:  2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "model_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", UtcDateTime(), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('pending', 'ok', 'rate_limited', 'refused', 'unavailable', "
            "'unreadable', 'cancelled')",
            name="outcome_allowed",
        ),
    )
    op.create_index("ix_model_usage_started_at", "model_usage", ["started_at"])

    op.add_column("jobs", sa.Column("subject_id", sa.String(32)))
    op.create_index("ix_jobs_subject_id", "jobs", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_subject_id", table_name="jobs")
    op.drop_column("jobs", "subject_id")
    op.drop_table("model_usage")
