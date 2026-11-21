"""A lesson that can be taken before its pictures are drawn, and who wrote it.

Revision: 0008
Previous: 0007
Created:  2026-11-21

``lessons.pending_scenes`` lists the pictures a stored lesson is still waiting for: a
lesson is stored when its text is ready, and each picture is added as it is drawn
(ADR-031). ``lessons.written_by`` keeps who wrote the lesson with the lesson, not only with
the job that made it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "lessons", sa.Column("pending_scenes", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column("lessons", sa.Column("written_by", sa.JSON()))


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch:
        batch.drop_column("written_by")
        batch.drop_column("pending_scenes")
