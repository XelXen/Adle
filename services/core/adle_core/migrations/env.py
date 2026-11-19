"""Alembic environment.

At run time the application passes an open connection in
``config.attributes["connection"]`` (see ``infrastructure/migrate.py``). The
command-line fallback exists only for authoring new revisions:

    cd services/core
    ADLE_DATA_DIR=./var/dev uv run alembic -c alembic.ini revision --autogenerate -m "..."
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection

from adle_core.infrastructure import orm  # noqa: F401  (registers every model on the metadata)
from adle_core.infrastructure.database import Base, create_database_engine

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot alter most column properties in place; batch mode
        # rewrites the table instead.
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    data_dir = os.environ.get("ADLE_DATA_DIR")
    if not data_dir:
        raise RuntimeError("Set ADLE_DATA_DIR to use the Alembic command line.")
    engine = create_database_engine(Path(data_dir) / "adle.db")
    with engine.connect() as cli_connection:
        _run(cli_connection)
        cli_connection.commit()
