"""Units of work: one that may write waits its turn; one that only reads cannot write."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from adle_core.infrastructure.database import Database
from adle_core.infrastructure.migrate import migrate
from adle_core.infrastructure.orm import Course

FIRST = "crs_00000000000000000001"
SECOND = "crs_00000000000000000002"


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "data" / "adle.db")
    migrate(database, tmp_path / "backups")
    with database.session() as session:
        session.add(Course(id=FIRST, title="First", origin="topic"))
        session.add(Course(id=SECOND, title="Second", origin="topic"))
    yield database
    database.dispose()


def title(database: Database, course_id: str) -> str:
    with database.read() as session:
        found = session.get(Course, course_id)
        assert found is not None
        return found.title


def test_reading_then_writing_survives_another_writer_arriving_in_between(
    database: Database,
) -> None:
    """The failure this guards against: "database is locked" on the first write of a unit
    of work that began by reading, because something else committed after it had read.
    A background job and a request did exactly that."""
    first_has_read = threading.Event()
    second_finished = threading.Event()
    errors: list[BaseException] = []

    def reads_then_writes() -> None:
        try:
            with database.session() as session:
                course = session.get(Course, FIRST)
                assert course is not None
                first_has_read.set()
                # Give the other writer every chance to get in between.
                second_finished.wait(0.4)
                course.title = "Renamed by the first"
        except BaseException as error:
            errors.append(error)

    def writes_meanwhile() -> None:
        first_has_read.wait(5)
        try:
            with database.session() as session:
                course = session.get(Course, SECOND)
                assert course is not None
                course.title = "Renamed by the second"
        except BaseException as error:
            errors.append(error)
        finally:
            second_finished.set()

    threads = [
        threading.Thread(target=reads_then_writes),
        threading.Thread(target=writes_meanwhile),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)

    assert errors == []
    assert title(database, FIRST) == "Renamed by the first"
    assert title(database, SECOND) == "Renamed by the second"


def test_a_reader_is_not_held_up_by_a_writer_and_sees_only_what_is_committed(
    database: Database,
) -> None:
    writer_has_written = threading.Event()
    reader_has_read = threading.Event()
    seen: list[str] = []

    def writes_slowly() -> None:
        with database.session() as session:
            course = session.get(Course, FIRST)
            assert course is not None
            course.title = "Not committed yet"
            session.flush()
            writer_has_written.set()
            reader_has_read.wait(5)

    writer = threading.Thread(target=writes_slowly)
    writer.start()
    assert writer_has_written.wait(5)
    # The write lock is held, and the change is not committed: the reader neither waits
    # nor sees it.
    seen.append(title(database, FIRST))
    reader_has_read.set()
    writer.join(10)
    seen.append(title(database, FIRST))
    assert seen == ["First", "Not committed yet"]


def write_while_only_reading(database: Database) -> None:
    with database.read() as session:
        course = session.get(Course, FIRST)
        assert course is not None
        course.title = "Changed where nothing may change"
        session.flush()


def test_a_unit_of_work_that_only_reads_cannot_write(database: Database) -> None:
    with pytest.raises(OperationalError, match="readonly"):
        write_while_only_reading(database)
    assert title(database, FIRST) == "First"


def test_reading_leaves_nothing_behind_even_if_objects_were_changed_in_memory(
    database: Database,
) -> None:
    with database.read() as session:
        course = session.get(Course, FIRST)
        assert course is not None
        # Never flushed, so never sent: a read ends by discarding, not committing.
        course.title = "Only in memory"
    assert title(database, FIRST) == "First"


def test_a_second_writing_unit_inside_the_first_is_refused_at_once(database: Database) -> None:
    """It could only wait for itself. Better a clear error now than a timeout later."""

    def open_another() -> None:
        with database.session():
            raise AssertionError("a second writing unit was opened inside the first")

    with database.session(), pytest.raises(RuntimeError, match="already open on this thread"):
        open_another()
    # The refusal leaves the outer unit of work, and the database, usable.
    with database.session() as session:
        session.add(Course(id="crs_00000000000000000003", title="Third", origin="topic"))
    with database.read() as session:
        assert len(session.scalars(select(Course.id)).all()) == 3


def test_reading_inside_a_writing_unit_is_allowed_and_sees_the_last_commit(
    database: Database,
) -> None:
    with database.session() as session:
        course = session.get(Course, FIRST)
        assert course is not None
        course.title = "Being changed"
        session.flush()
        # A snapshot of what is committed, not of this unit's unfinished work.
        assert title(database, FIRST) == "First"
    assert title(database, FIRST) == "Being changed"


def test_an_error_in_a_writing_unit_changes_nothing_and_frees_the_thread(
    database: Database,
) -> None:
    def change_then_fail() -> None:
        with database.session() as session:
            course = session.get(Course, FIRST)
            assert course is not None
            course.title = "Never kept"
            session.flush()
            raise ValueError("deliberate")

    with pytest.raises(ValueError, match="deliberate"):
        change_then_fail()
    assert title(database, FIRST) == "First"
    with database.session() as session:
        found = session.get(Course, FIRST)
        assert found is not None
        found.title = "Kept"
    assert title(database, FIRST) == "Kept"
