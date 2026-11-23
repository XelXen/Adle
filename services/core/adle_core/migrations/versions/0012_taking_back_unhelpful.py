"""Taking back "this did not help".

Revision: 0012
Previous: 0011
Created:  2026-11-23

``learner_events`` gains a kind, ``explanation_unhelpful_withdrawn`` (ADR-054): the
learner takes back what they said about a part of a lesson, in a row of its own after
the report. SQLite cannot change a CHECK constraint in place, so the table is rebuilt
and its rows copied across.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None

_KINDS_BEFORE = "kind IN ('misconception_dismissed', 'explanation_unhelpful', 'lesson_completed')"
_KINDS_AFTER = (
    "kind IN ('misconception_dismissed', 'explanation_unhelpful', 'lesson_completed', "
    "'explanation_unhelpful_withdrawn')"
)


def _owned_by(column: str, table: str, **options: Any) -> sa.Column[str]:
    """A reference whose row is deleted together with the row it points to."""
    return sa.Column(
        column, sa.String(32), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), **options
    )


def _events(kinds: str) -> sa.Table:
    """``learner_events`` as it is before or after this revision."""
    return sa.Table(
        "learner_events",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _owned_by("course_id", "courses", nullable=False),
        _owned_by("concept_id", "concepts"),
        _owned_by("lesson_id", "lessons"),
        sa.Column("occurred_at", UtcDateTime(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.CheckConstraint(kinds, name="kind_allowed"),
        sa.Index("ix_learner_events_course_id", "course_id"),
        sa.Index("ix_learner_events_concept_id", "concept_id"),
    )


def upgrade() -> None:
    with op.batch_alter_table(
        "learner_events", copy_from=_events(_KINDS_BEFORE), recreate="always"
    ) as batch:
        batch.drop_constraint("kind_allowed", type_="check")
        batch.create_check_constraint("kind_allowed", _KINDS_AFTER)


def downgrade() -> None:
    # The older kinds cannot say that something was taken back: what was taken back goes
    # with what took it back, and what still stands is kept.
    op.execute(
        "DELETE FROM learner_events WHERE kind = 'explanation_unhelpful' AND EXISTS ("
        "SELECT 1 FROM learner_events AS later "
        "WHERE later.kind = 'explanation_unhelpful_withdrawn' "
        "AND later.lesson_id IS learner_events.lesson_id "
        "AND json_extract(later.detail, '$.segment_id') "
        "IS json_extract(learner_events.detail, '$.segment_id') "
        "AND later.id > learner_events.id)"
    )
    op.execute("DELETE FROM learner_events WHERE kind = 'explanation_unhelpful_withdrawn'")
    with op.batch_alter_table(
        "learner_events", copy_from=_events(_KINDS_AFTER), recreate="always"
    ) as batch:
        batch.drop_constraint("kind_allowed", type_="check")
        batch.create_check_constraint("kind_allowed", _KINDS_BEFORE)
