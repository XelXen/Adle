"""A course's subject.

Revision: 0014
Previous: 0013
Created:  2026-11-24

``courses`` gains ``subject`` and ``subject_by_adle`` (ADR-061): the kind of subject a
course is, which decides how its lessons are formed, and whether Adle placed it or the
learner chose. A course made before this revision is general, placed by Adle: the core
places it by its name as it next starts (``CourseService.settle_subjects``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Added in place: rebuilding ``courses`` would take everything that hangs from a
    # course with it (its rows are removed with the old table).
    op.add_column(
        "courses",
        sa.Column("subject", sa.String(length=30), nullable=False, server_default="general"),
    )
    op.add_column(
        "courses",
        sa.Column("subject_by_adle", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    # Taken out in place, for the same reason (SQLite drops a plain column itself).
    op.drop_column("courses", "subject_by_adle")
    op.drop_column("courses", "subject")
