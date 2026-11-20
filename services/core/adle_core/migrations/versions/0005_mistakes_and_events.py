"""What a question can reveal, slips, dismissed suspicions, and a log of what the learner did.

Revision: 0005
Previous: 0004
Created:  2026-11-19

``learner_observations`` gains a third kind (``dismissal``). SQLite cannot change a
CHECK constraint in place, so the table is rebuilt and its rows copied across.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None

_KINDS_BEFORE = "kind IN ('answer', 'self_report')"
_KINDS_AFTER = "kind IN ('answer', 'self_report', 'dismissal')"
_EVENT_KINDS = "kind IN ('misconception_dismissed', 'explanation_unhelpful', 'lesson_completed')"


def _owned_by(column: str, table: str, **options: Any) -> sa.Column[str]:
    """A reference whose row is deleted together with the row it points to."""
    return sa.Column(
        column, sa.String(32), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), **options
    )


def _observations(kinds: str, *, with_new_columns: bool) -> sa.Table:
    """``learner_observations`` as it is before or after this revision."""
    columns: list[sa.Column[Any]] = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _owned_by("concept_id", "concepts", nullable=False),
        _owned_by("course_id", "courses", nullable=False),
        sa.Column("occurred_at", UtcDateTime(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20)),
        sa.Column("question_form", sa.String(30)),
        sa.Column("is_transfer", sa.Boolean(), nullable=False),
        sa.Column("hinted", sa.Boolean(), nullable=False),
        sa.Column("unsure", sa.Boolean(), nullable=False),
        sa.Column("item_guess", sa.Float()),
        sa.Column("self_report", sa.String(20)),
        sa.Column("state_before", sa.String(20), nullable=False),
        sa.Column("state_after", sa.String(20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("config_version", sa.String(20), nullable=False),
    ]
    if with_new_columns:
        columns += [
            sa.Column("slip", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("unresolved_misconception", sa.Boolean()),
        ]
    return sa.Table(
        "learner_observations",
        sa.MetaData(),
        *columns,
        sa.CheckConstraint(kinds, name="kind_allowed"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'partial', 'incorrect', 'skipped')",
            name="outcome_allowed",
        ),
        sa.CheckConstraint(
            "self_report IS NULL OR self_report IN ('new', 'some', 'confident')",
            name="self_report_allowed",
        ),
        sa.Index("ix_learner_observations_concept", "concept_id", "id"),
        sa.Index("ix_learner_observations_course_id", "course_id"),
    )


def upgrade() -> None:
    op.add_column("attempts", sa.Column("reveals", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "learner_concept_states",
        sa.Column(
            "unresolved_misconception", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    with op.batch_alter_table(
        "learner_observations",
        copy_from=_observations(_KINDS_BEFORE, with_new_columns=False),
        recreate="always",
    ) as batch:
        batch.add_column(sa.Column("slip", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("unresolved_misconception", sa.Boolean()))
        batch.drop_constraint("kind_allowed", type_="check")
        batch.create_check_constraint("kind_allowed", _KINDS_AFTER)

    op.create_table(
        "learner_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _owned_by("course_id", "courses", nullable=False),
        _owned_by("concept_id", "concepts"),
        _owned_by("lesson_id", "lessons"),
        sa.Column("occurred_at", UtcDateTime(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.CheckConstraint(_EVENT_KINDS, name="kind_allowed"),
    )
    op.create_index("ix_learner_events_course_id", "learner_events", ["course_id"])
    op.create_index("ix_learner_events_concept_id", "learner_events", ["concept_id"])


def downgrade() -> None:
    op.drop_table("learner_events")

    # A dismissal has no place in the older table.
    op.execute("DELETE FROM learner_observations WHERE kind = 'dismissal'")
    with op.batch_alter_table(
        "learner_observations",
        copy_from=_observations(_KINDS_AFTER, with_new_columns=True),
        recreate="always",
    ) as batch:
        batch.drop_column("slip")
        batch.drop_column("unresolved_misconception")
        batch.drop_constraint("kind_allowed", type_="check")
        batch.create_check_constraint("kind_allowed", _KINDS_BEFORE)

    with op.batch_alter_table("learner_concept_states") as batch:
        batch.drop_column("unresolved_misconception")
    with op.batch_alter_table("attempts") as batch:
        batch.drop_column("reveals")
