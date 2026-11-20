"""Which provider each model request went to.

Revision: 0006
Previous: 0005
Created:  2026-11-20

Adle can now use more than one provider (ADR-021), and each has its own allowance.
Every request recorded before this went to the only provider there was.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "model_usage",
        sa.Column("provider", sa.String(40), nullable=False, server_default="aihubmix"),
    )


def downgrade() -> None:
    with op.batch_alter_table("model_usage") as batch:
        batch.drop_column("provider")
