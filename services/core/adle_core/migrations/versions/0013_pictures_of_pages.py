"""Pages that are pictures.

Revision: 0013
Previous: 0012
Created:  2026-11-24

``sources`` gains ``picture_pages`` (ADR-060): the pages of a file that are pictures, with
no text to select, waiting to be read by a model that sees pictures at the learner's word.
A page leaves the list when it has been read. A file imported before this revision has
none listed: its pages with no text were skipped, as they were then.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as table:
        table.add_column(sa.Column("picture_pages", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("sources") as table:
        table.drop_column("picture_pages")
