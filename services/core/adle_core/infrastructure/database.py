"""SQLite engine and session handling.

SQLite is the source of truth for everything Adle knows: courses, sources,
curriculum, lessons, and learner state. One engine per process; short-lived
sessions per unit of work.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.engine import URL, Connection, Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

BUSY_TIMEOUT_MS = 5_000


def utc_now() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """A timezone-aware UTC timestamp.

    SQLite has no timezone support, so values are stored as naive UTC and
    returned as aware datetimes. Naive values are refused on the way in: an
    ambiguous timestamp in a review schedule would be a silent bug.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Declarative base for all persisted models."""


def _configure_connection(dbapi_connection: Any, _record: Any) -> None:
    """Apply per-connection settings. SQLite forgets these on every new connection."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    # Hand transaction control to SQLAlchemy (see `_begin_transaction`). The
    # driver's default mode commits implicitly around schema statements, which
    # would let a failed migration leave a half-changed database.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        # WAL lets the UI read while an import or generation job writes.
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
    finally:
        cursor.close()


def _begin_transaction(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN")


def create_database_engine(path: Path) -> Engine:
    """Create the engine for the database file at ``path`` (created on first use)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        # Built from parts, not a string: a profile folder may contain "#", "%", or "?".
        URL.create("sqlite", database=path.as_posix()),
        # Request handlers run in a thread pool and jobs in a worker thread.
        connect_args={"check_same_thread": False, "timeout": BUSY_TIMEOUT_MS / 1000},
    )
    event.listen(engine, "connect", _configure_connection)
    event.listen(engine, "begin", _begin_transaction)
    return engine


class Database:
    """Owns the engine and hands out sessions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.engine = create_database_engine(path)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A transactional unit of work: commit on success, roll back on any error."""
        session = self._sessions()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
