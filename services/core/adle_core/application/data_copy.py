"""The learner's data as a whole: saving a copy of it, and restoring from one.

A copy is the database, written as one self-contained file. It holds everything Adle
needs to carry on: courses, the text taken from imported materials and where each
passage came from, the curriculum, lessons, answers, and what has been learnt about
the learner.

It does not hold the files that were imported. Nothing reads them after import, so a
restored copy works without them, and nothing may come to depend on a stored original
being present. It does not hold the provider key either: that is never in the database.

Both directions are reached only from the Electron main process, with a path the
learner chose in a dialog of the operating system (ADR-016). Saving a copy is the one
place where the core writes outside its own data directory.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from pathlib import Path

from adle_core.config import Settings
from adle_core.errors import AdleError, ValidationFailedError
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.migrate import (
    CopyOutOfDateError,
    MigrationError,
    backup_database,
    migrate,
    restore_database,
)

logger = logging.getLogger(__name__)

#: A copy of the data is a single file with this extension.
COPY_SUFFIX = ".adle"
#: While a copy is being written it has this added to its name, so a file with the
#: real name is always a complete copy.
_PARTIAL_SUFFIX = ".part"


class CopyNotSavedError(AdleError):
    """The copy could not be written where the learner asked."""

    status_code = 400
    code = "copy_not_saved"


def _destination(settings: Settings, requested: Path) -> Path:
    """Check where a copy is to be written. Raises unless it is a place a copy can go."""
    elsewhere = ValidationFailedError("Adle cannot save a copy there. Choose another place.")
    if not requested.is_absolute():
        raise elsewhere
    try:
        destination = requested.resolve()
        data_dir = settings.data_dir.resolve()
    except OSError as error:
        raise elsewhere from error
    if destination.suffix.lower() != COPY_SUFFIX:
        raise ValidationFailedError(f"A copy of your data is a file that ends in {COPY_SUFFIX}.")
    # A copy kept inside the folder it is a copy of would be deleted or replaced with it.
    if destination.is_relative_to(data_dir):
        raise ValidationFailedError("Choose a place outside Adle's own data folder.")
    if not destination.parent.is_dir():
        raise ValidationFailedError("That folder does not exist. Choose another place.")
    if destination.is_dir():
        raise elsewhere
    return destination


def save_copy(settings: Settings, requested: Path) -> Path:
    """Write a copy of everything to ``requested``, replacing a file already there.

    The service keeps running: the copy is a consistent picture of one moment. It is
    written under another name and renamed when complete, so a failure part-way never
    leaves a damaged file under the name the learner chose, nor destroys an older
    copy that was there.
    """
    destination = _destination(settings, requested)
    partial = destination.with_name(destination.name + _PARTIAL_SUFFIX)
    try:
        partial.unlink(missing_ok=True)
        backup_database(settings.db_path, partial)
        partial.replace(destination)
    except (OSError, sqlite3.Error) as error:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise CopyNotSavedError(
            "Adle could not save the copy there. Check that the folder can be written to "
            "and has room, or choose another place."
        ) from error
    logger.info("Saved a copy of the data")
    return destination


def restore_copy(settings: Settings, copy: Path) -> Path | None:
    """Replace the data with ``copy``. Only before anything has opened the database.

    All or nothing. The copy is checked, then brought to this version's schema in a
    working file of its own, and only then put in place of the current data, which is
    first kept as a safety copy (its path is returned; ``None`` if there was no data).
    If any step fails, the current data has not been touched and the reason is raised
    as a ``MigrationError`` whose message is written for the learner.
    """

    def bring_up_to_date(working_copy: Path) -> None:
        database = Database(working_copy)
        try:
            migrate(database, settings.backups_dir, keep_backup=False)
        except MigrationError as error:
            raise CopyOutOfDateError(
                "That copy could not be brought up to date with this version of Adle, "
                "so it was not restored. Your current data was not changed."
            ) from error
        finally:
            database.dispose()

    return restore_database(copy, settings.db_path, settings.backups_dir, prepare=bring_up_to_date)
