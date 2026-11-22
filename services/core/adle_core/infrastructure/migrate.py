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

import contextlib
import logging
import re
import sqlite3
from collections.abc import Callable
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
#: Copies of data that a restore replaced. Enough to undo a mistake several times over;
#: without a limit, each restore would leave another whole database behind for ever.
MAX_REPLACED_BACKUPS = 5


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


class CopyOutOfDateError(MigrationError):
    """The copy offered for restoring could not be brought to this version's schema."""


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
    """Write a consistent copy of a live SQLite database as one self-contained file.

    The copy includes what is still in the write-ahead log. It is then switched to
    SQLite's single-file mode. Left as it was, merely opening it to look at it, even
    read-only, would create two more files beside it and leave them there, and it
    could not be read from a disk that cannot be written to. A copy is something a
    learner keeps in a folder of their own, so it is one file and stays one file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    # `with` on a sqlite3 connection only ends a transaction, so close explicitly:
    # on Windows a file that is still open cannot be moved or deleted.
    original = sqlite3.connect(_read_only_uri(source), uri=True)
    try:
        copy = sqlite3.connect(destination)
        try:
            original.backup(copy)
            copy.execute("PRAGMA journal_mode = DELETE")
        finally:
            copy.close()
    finally:
        original.close()


def _prune_backups(
    directory: Path, pattern: str = "adle-before-*.db", keep: int = MAX_AUTOMATIC_BACKUPS
) -> None:
    """Keep the newest ``keep`` safety copies of one kind. Files named otherwise are not ours.

    The newest by the time in its name, which is when the copy was made: the time a file was
    last changed is not that (a copy can keep the time of what it copied), and copies made
    within moments of each other were seen to be kept out of order by it."""
    backups = sorted(directory.glob(pattern), key=_made_at)
    for stale in backups[:-keep]:
        stale.unlink(missing_ok=True)


#: The time in a safety copy's name: 20261122T182931Z, or with microseconds before the Z.
_STAMP = re.compile(r"(\d{8}T\d{6})(\d{0,6})Z")


def _made_at(path: Path) -> tuple[str, str, float]:
    found = _STAMP.search(path.name)
    stamp = (found.group(1), found.group(2).ljust(6, "0")) if found else ("", "")
    return (*stamp, path.stat().st_mtime)


#: Tables created by the first revision and present in every one since.
_TABLES_OF_EVERY_REVISION = frozenset({"courses", "sources", "app_settings"})


def _check_backup(backup: Path) -> None:
    """Raise unless ``backup`` is an intact Adle database this build can open.

    The file may come from anywhere, so it is only read here, with nothing in its
    schema trusted, and nothing of it is used until all of this has passed.
    """
    not_usable = InvalidBackupError(
        "That file is not a copy of Adle's data, or it is damaged. "
        "Your current data was not changed."
    )
    try:
        connection = sqlite3.connect(_read_only_uri(backup), uri=True)
    except sqlite3.Error as error:
        raise not_usable from error
    try:
        connection.execute("PRAGMA trusted_schema = OFF")
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
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
            "That copy was saved by a newer version of Adle. Update Adle to restore it; "
            "your current data was not changed."
        ) from error
    # Another program's database can carry a version table too. Every revision of
    # Adle's schema has had these tables, so their absence means it is not ours.
    if not _TABLES_OF_EVERY_REVISION.issubset(tables):
        raise not_usable


def _remove_database_files(path: Path) -> None:
    """Delete a database file that is not open anywhere, with anything SQLite left beside it."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        with contextlib.suppress(OSError):
            path.with_name(path.name + suffix).unlink(missing_ok=True)


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


def restore_database(
    backup: Path,
    target: Path,
    backups_dir: Path,
    *,
    prepare: Callable[[Path], None] | None = None,
) -> Path | None:
    """Replace the database at ``target`` with ``backup``.

    Nothing is discarded. The backup is checked before the current data is touched,
    and the database being replaced is first copied into ``backups_dir``; that copy's
    path is returned (``None`` if there was nothing to replace), so a restore can
    itself be undone.

    ``prepare`` is given a private working copy of the backup before anything is
    replaced, to do whatever must succeed first (bringing it to the current schema).
    If it raises, the current data has not been touched.

    ``target`` must not be open anywhere. Without ``prepare`` the restored data may be
    at an older schema revision: run :func:`migrate` on it afterwards, as at any start-up.
    """
    _check_backup(backup)
    try:
        is_the_data_itself = target.exists() and backup.samefile(target)
    except OSError:
        is_the_data_itself = False
    if is_the_data_itself:
        raise InvalidBackupError(
            "That file is the data Adle is using now, not a copy of it. "
            "Your current data was not changed."
        )
    staged = target.with_name(target.name + ".restoring")
    replaced: Path | None = None
    try:
        _remove_database_files(staged)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_database(backup, staged)
        if prepare is not None:
            prepare(staged)
            # Whatever prepared it has closed it; make sure it stands alone before it moves.
            _fold_in_write_ahead_log(staged)
        if target.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            replaced = backups_dir / f"adle-replaced-{stamp}.db"
            backup_database(target, replaced)
            _fold_in_write_ahead_log(target)
        # The one step that changes the learner's data, and it is all or nothing.
        staged.replace(target)
    except (OSError, sqlite3.Error) as error:
        _remove_database_files(staged)
        if replaced is not None:
            # Nothing was replaced, so a file that says otherwise would only mislead.
            _remove_database_files(replaced)
        raise MigrationError(
            "Adle could not restore from that copy, so your current data was left as it was. "
            "Close any other window of Adle and try again."
        ) from error
    except BaseException:
        # Whatever else went wrong (what prepared the copy refused it), leave no trace.
        _remove_database_files(staged)
        raise
    if replaced is not None:
        with contextlib.suppress(OSError):
            _prune_backups(backups_dir, "adle-replaced-*.db", MAX_REPLACED_BACKUPS)
    logger.info("Restored the database from a copy")
    return replaced


def migrate(database: Database, backups_dir: Path, *, keep_backup: bool = True) -> MigrationOutcome:
    """Upgrade ``database`` to the newest revision, backing it up first if it holds data.

    ``keep_backup=False`` is for a working copy that is itself a copy of something kept
    (a restore being prepared): there is nothing to protect, and a backup of it would
    push a real one out of the few that are kept.
    """
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

        if keep_backup:
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
