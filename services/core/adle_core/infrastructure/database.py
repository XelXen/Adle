"""SQLite engine and session handling.

SQLite is the source of truth for everything Adle knows: courses, sources,
curriculum, lessons, and learner state. Short-lived sessions per unit of work,
of two kinds:

* ``Database.session()`` may write. Its transaction takes the write lock when it
  begins (``BEGIN IMMEDIATE``). A transaction that began by reading and tried
  to write later would fail at once with "database is locked" if anything else
  had committed in between, and no timeout applies to that failure. Request
  handlers and background jobs do commit in between, so a unit of work that may
  write says so up front and waits its turn instead.
* ``Database.read()`` cannot write (``PRAGMA query_only``), takes no lock, and
  sees a consistent snapshot. It never waits for a writer and no writer waits
  for it.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.engine import URL, Connection, Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

#: How long a unit of work waits for another one to finish writing.
BUSY_TIMEOUT_MS = 15_000


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
        _distrust_the_file(cursor)
        # WAL lets the UI read while an import or generation job writes.
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
    finally:
        cursor.close()


def _distrust_the_file(cursor: sqlite3.Cursor) -> None:
    """Settings SQLite recommends for a database file that may have come from elsewhere.

    The learner can restore their data from a file of their choosing (ADR-016), so the
    file is not assumed to be one Adle wrote. Triggers and views in it may only use
    what SQLite marks as harmless, and a malformed page is reported instead of read.
    """
    cursor.execute("PRAGMA trusted_schema = OFF")
    cursor.execute("PRAGMA cell_size_check = ON")


def _configure_reader(dbapi_connection: Any, _record: Any) -> None:
    """Settings for a connection that only reads. It is refused any write by SQLite itself."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        _distrust_the_file(cursor)
        cursor.execute("PRAGMA query_only = ON")
    finally:
        cursor.close()


def _begin_for_writing(connection: Connection) -> None:
    # Take the write lock now, and wait for it if need be (see the module docstring).
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def _begin_for_reading(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN")


def create_database_engine(path: Path, *, read_only: bool = False) -> Engine:
    """Create an engine for the database file at ``path`` (created on first use)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        # Built from parts, not a string: a profile folder may contain "#", "%", or "?".
        URL.create("sqlite", database=path.as_posix()),
        # Request handlers run in a thread pool and jobs in a worker thread.
        connect_args={"check_same_thread": False, "timeout": BUSY_TIMEOUT_MS / 1000},
        # An error from the database names the statement and never its values: those are
        # the learner's documents, questions, and answers, and an error may be logged.
        hide_parameters=True,
    )
    event.listen(engine, "connect", _configure_reader if read_only else _configure_connection)
    event.listen(engine, "begin", _begin_for_reading if read_only else _begin_for_writing)
    return engine


class Database:
    """Owns the engine and hands out sessions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        #: The engine that may write. Migrations and maintenance use it directly.
        self.engine = create_database_engine(path)
        self._readers = create_database_engine(path, read_only=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self._read_sessions = sessionmaker(self._readers, expire_on_commit=False)
        self._thread = threading.local()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A unit of work that may write: commit on success, roll back on any error.

        Only one runs at a time; another waits for it. Opening a second one inside the
        first on the same thread could only wait for itself, so that is refused at once.
        """
        if getattr(self._thread, "writing", False):
            raise RuntimeError(
                "A unit of work that may write is already open on this thread. "
                "Close it first, or use read() for the inner one."
            )
        self._thread.writing = True
        session = self._sessions()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
            self._thread.writing = False

    @contextmanager
    def read(self) -> Iterator[Session]:
        """A unit of work that only reads, on a consistent snapshot. It cannot write."""
        session = self._read_sessions()
        try:
            yield session
        finally:
            # Nothing to commit; ending the transaction releases the snapshot.
            session.rollback()
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
        self._readers.dispose()
