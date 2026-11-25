"""A course brought in from a file.

Revision: 0015
Previous: 0014
Created:  2026-11-24

``courses`` gains ``brought_in`` (ADR-063): whether a course came in a file, so that the
interface can say that what it holds was made elsewhere. Every course from before was made
here.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Added in place: rebuilding ``courses`` would take everything that hangs from a
    # course with it (its rows are removed with the old table).
    op.add_column(
        "courses",
        sa.Column("brought_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("courses", "brought_in")
