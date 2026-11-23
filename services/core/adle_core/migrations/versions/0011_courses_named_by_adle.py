"""A course whose name was left to Adle.

Revision: 0011
Previous: 0010
Created:  2026-11-23

``courses.named_by_adle`` is true for a course the learner created without naming it:
Adle names it, first from the first file imported into it and then as the AI suggests
with the course's concepts (ADR-053). It is false once the learner names it themselves,
and for every course created before this.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("named_by_adle", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch:
        batch.drop_column("named_by_adle")
