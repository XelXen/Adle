"""A lesson that can be taken while the rest of it is still being written.

Revision: 0010
Previous: 0009
Created:  2026-11-22

``lessons.writing`` is true while the model is still writing a lesson that is stored
already: it was stored at its first part, and each part after it is added as it is
written (ADR-048). It is false for every lesson once its writing has ended, however it
ended, and for every lesson stored before this.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "lessons",
        sa.Column("writing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch:
        batch.drop_column("writing")
