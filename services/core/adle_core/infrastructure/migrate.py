"""Bring the database to the current schema, safely.

Rules (PLAN.md §5.5, PROMPT.md §13):

* A learner's database is never replaced or silently reset.
* Before changing an existing database, a consistent copy is written to the
  backups directory. If a migration fails, that copy is intact and its path is
  reported.
* A database created by a newer Adle, or one this code does not recognise, is
  refused rather than "fixed".
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import inspect

from adle_core.infrastructure.database import Database

logger = logging.getLogger(__name__)

#: Automatic backups kept per database. Older ones are removed after a successful migration.
MAX_AUTOMATIC_BACKUPS = 5


class MigrationError(RuntimeError):
    """The database could not be brought to the current schema."""

    def __init__(self, message: str, *, backup_path: Path | None = None) -> None:
        super().__init__(message)
        self.backup_path = backup_path


class DatabaseTooNewError(MigrationError):
    """The data was written by a newer version of Adle than this one."""


class UnrecognisedDatabaseError(MigrationError):
    """The file holds tables but was not created by Adle's migrations."""


class InvalidBackupError(MigrationError):
    """The file offered for restoring is not a usable Adle database."""


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    previous_revision: str | None
    current_revision: str
    #: Where the pre-migration copy was written, if the database already held data.
    backup_path: Path | None

    @property
    def changed(self) -> bool:
        return self.previous_revision != self.current_revision


def _alembic_config() -> Config:
    config = Config()
    location = resources.files("adle_core").joinpath("migrations")
    config.set_main_option("script_location", str(location))
    return config


def head_revision() -> str:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    if head is None:
        raise MigrationError("No migrations are defined.")
    return head


def _read_only_uri(path: Path) -> str:
    """A SQLite URI that opens ``path`` read-only, whatever characters its name contains."""
    return f"file:{quote(path.as_posix(), safe='/:')}?mode=ro"


def backup_database(source: Path, destination: Path) -> None:
    """Write a consistent copy of a live SQLite database, including WAL contents."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(_read_only_uri(source), uri=True) as original,
        sqlite3.connect(destination) as copy,
    ):
        original.backup(copy)
    # `with` on a sqlite3 connection only ends the transaction; close explicitly.
    original.close()
    copy.close()


def _prune_backups(directory: Path) -> None:
    backups = sorted(directory.glob("adle-before-*.db"), key=lambda path: path.stat().st_mtime)
    for stale in backups[:-MAX_AUTOMATIC_BACKUPS]:
        stale.unlink(missing_ok=True)


def _check_backup(backup: Path) -> None:
    """Raise unless ``backup`` is an intact Adle database this build can open."""
    not_usable = InvalidBackupError(
        "That file is not an Adle backup, or it is damaged. Your current data was not changed."
    )
    try:
        connection = sqlite3.connect(_read_only_uri(backup), uri=True)
    except sqlite3.Error as error:
        raise not_usable from error
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    except sqlite3.Error as error:
        raise not_usable from error
    finally:
        connection.close()
    if integrity != [("ok",)] or len(revisions) != 1:
        raise not_usable
    try:
        ScriptDirectory.from_config(_alembic_config()).get_revision(str(revisions[0][0]))
    except CommandError as error:
        raise DatabaseTooNewError(
            "That backup was saved by a newer version of Adle. Update Adle to restore it; "
            "your current data was not changed."
        ) from error


def _fold_in_write_ahead_log(path: Path) -> None:
    """Move pending changes into the database file so it stands alone.

    A leftover ``-wal`` file must never be paired with a different database, so the
    file about to be replaced is checkpointed first. This fails while anything else
    has the database open, which is exactly when replacing it would be unsafe.
    """
    connection = sqlite3.connect(path, timeout=1.0)
    try:
        busy, _, _ = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        connection.close()
    if busy:
        raise sqlite3.OperationalError("database is in use")


def restore_database(backup: Path, target: Path, backups_dir: Path) -> Path | None:
    """Replace the database at ``target`` with ``backup``.

    Nothing is discarded. The backup is checked before the current data is touched,
    and the database being replaced is first copied into ``backups_dir``; that copy's
    path is returned (``None`` if there was nothing to replace), so a restore can
    itself be undone.

    ``target`` must not be open anywhere. The restored data may be at an older schema
    revision: run :func:`migrate` on it afterwards, as at any start-up.
    """
    _check_backup(backup)
    staged = target.with_name(target.name + ".restoring")
    replaced: Path | None = None
    try:
        staged.unlink(missing_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_database(backup, staged)
        if target.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            replaced = backups_dir / f"adle-replaced-{stamp}.db"
            backup_database(target, replaced)
            _fold_in_write_ahead_log(target)
        staged.replace(target)
    except (OSError, sqlite3.Error) as error:
        staged.unlink(missing_ok=True)
        raise MigrationError(
            "Adle could not restore that backup, so your current data was left as it was. "
            "Close any other copy of Adle and try again.",
            backup_path=replaced,
        ) from error
    logger.info("Restored the database from a backup")
    return replaced


def migrate(database: Database, backups_dir: Path) -> MigrationOutcome:
    """Upgrade ``database`` to the newest revision, backing it up first if it holds data."""
    config = _alembic_config()
    scripts = ScriptDirectory.from_config(config)
    head = head_revision()

    with database.engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
        tables = set(inspect(connection).get_table_names())

    if current == head:
        return MigrationOutcome(previous_revision=current, current_revision=head, backup_path=None)

    if current is None and tables - {"alembic_version"}:
        raise UnrecognisedDatabaseError(
            "The data file was not created by Adle and will not be changed. "
            "Move it out of the data folder to start fresh."
        )

    backup_path: Path | None = None
    if current is not None:
        try:
            scripts.get_revision(current)
        except CommandError as error:
            raise DatabaseTooNewError(
                "This data was saved by a newer version of Adle. "
                "Update Adle to open it; nothing has been changed."
            ) from error

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backups_dir / f"adle-before-{head}-from-{current}-{stamp}.db"
        try:
            backup_database(database.path, backup_path)
        except (OSError, sqlite3.Error) as error:
            raise MigrationError(
                "Adle could not make a safety copy of your data before updating it, "
                "so nothing was changed. Check that the disk is not full."
            ) from error
        logger.info("Backed up the database before migrating from %s to %s", current, head)

    try:
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception as error:
        raise MigrationError(
            "Adle could not update its data to this version. Your data was not lost"
            + (": a safety copy was made first." if backup_path else "."),
            backup_path=backup_path,
        ) from error

    if backup_path is not None:
        _prune_backups(backups_dir)
    logger.info("Database schema is at revision %s", head)
    return MigrationOutcome(
        previous_revision=current, current_revision=head, backup_path=backup_path
    )
