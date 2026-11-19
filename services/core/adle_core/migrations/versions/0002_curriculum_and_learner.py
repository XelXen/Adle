"""Curriculum graph and learner model.

Revision: 0002
Previous: 0001
Created:  2026-11-19
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from adle_core.infrastructure.database import UtcDateTime

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

_ORIGINS = "origin IN ('learner', 'outline', 'model', 'sample')"


def _owned_by(column: str, table: str, **options: Any) -> sa.Column[str]:
    """A reference whose row is deleted together with the row it points to."""
    return sa.Column(
        column, sa.String(32), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), **options
    )


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(32), primary_key=True),
        _owned_by("course_id", "courses", nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("complexity", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(_ORIGINS, name="origin_allowed"),
        sa.CheckConstraint("complexity BETWEEN 1 AND 3", name="complexity_range"),
    )
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"])

    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.String(32), primary_key=True),
        _owned_by("concept_id", "concepts", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("statement", sa.String(400), nullable=False),
    )
    op.create_index("ix_learning_objectives_concept_id", "learning_objectives", ["concept_id"])

    op.create_table(
        "concept_edges",
        _owned_by("concept_id", "concepts", primary_key=True),
        _owned_by("prerequisite_id", "concepts", primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.CheckConstraint("concept_id <> prerequisite_id", name="no_self_prerequisite"),
        sa.CheckConstraint(_ORIGINS, name="origin_allowed"),
    )
    op.create_index("ix_concept_edges_prerequisite_id", "concept_edges", ["prerequisite_id"])

    op.create_table(
        "concept_source_refs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _owned_by("concept_id", "concepts", nullable=False),
        _owned_by("source_id", "sources", nullable=False),
        _owned_by("section_id", "source_sections", nullable=False),
        sa.UniqueConstraint("concept_id", "section_id", name="uq_concept_source_refs_section"),
    )
    op.create_index("ix_concept_source_refs_concept_id", "concept_source_refs", ["concept_id"])
    op.create_index("ix_concept_source_refs_source_id", "concept_source_refs", ["source_id"])

    op.create_table(
        "learner_preferences",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )

    op.create_table(
        "learner_observations",
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
        sa.CheckConstraint("kind IN ('answer', 'self_report')", name="kind_allowed"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'partial', 'incorrect', 'skipped')",
            name="outcome_allowed",
        ),
        sa.CheckConstraint(
            "self_report IS NULL OR self_report IN ('new', 'some', 'confident')",
            name="self_report_allowed",
        ),
    )
    op.create_index("ix_learner_observations_concept", "learner_observations", ["concept_id", "id"])
    op.create_index("ix_learner_observations_course_id", "learner_observations", ["course_id"])

    op.create_table(
        "learner_concept_states",
        _owned_by("concept_id", "concepts", primary_key=True),
        _owned_by("course_id", "courses", nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("missing", sa.JSON(), nullable=False),
        sa.Column("answered", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("unaided_correct", sa.Integer(), nullable=False),
        sa.Column("hinted", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("forms_correct", sa.JSON(), nullable=False),
        sa.Column("transfer_correct", sa.Integer(), nullable=False),
        sa.Column("self_report", sa.String(20)),
        sa.Column("last_observed_at", UtcDateTime()),
        sa.Column("review_interval_days", sa.Float()),
        sa.Column("review_due_at", UtcDateTime()),
        sa.Column("review_streak", sa.Integer(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('not_assessed', 'building', 'needs_evidence', 'demonstrated')",
            name="state_allowed",
        ),
    )
    op.create_index("ix_learner_concept_states_course_id", "learner_concept_states", ["course_id"])
    op.create_index(
        "ix_learner_concept_states_review_due_at", "learner_concept_states", ["review_due_at"]
    )


def downgrade() -> None:
    op.drop_table("learner_concept_states")
    op.drop_table("learner_observations")
    op.drop_table("learner_preferences")
    op.drop_table("concept_source_refs")
    op.drop_table("concept_edges")
    op.drop_table("learning_objectives")
    op.drop_table("concepts")
