"""Schema, migrations, and the guarantees around a learner's data file."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from importlib import resources
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from adle_core.infrastructure import migrate as migrate_module
from adle_core.infrastructure.database import Base, Database
from adle_core.infrastructure.migrate import (
    MAX_AUTOMATIC_BACKUPS,
    DatabaseTooNewError,
    InvalidBackupError,
    MigrationError,
    UnrecognisedDatabaseError,
    backup_database,
    head_revision,
    migrate,
    restore_database,
)
from adle_core.infrastructure.orm import (
    Course,
    LearnerEvent,
    Source,
    SourceChunk,
    SourceSection,
)

#: The newest real revision, read before any test swaps the migration scripts.
REAL_HEAD = head_revision()
#: A revision that exists only in tests, one step after the real head.
TEST_REVISION = "t001"

EXTRA_REVISION = '''"""Add a notes table (test-only revision)."""

import sqlalchemy as sa
from alembic import op

revision = "t001"
down_revision = "{previous}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("test_notes", sa.Column("id", sa.Integer(), primary_key=True))
    {failure}


def downgrade() -> None:
    op.drop_table("test_notes")
'''


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "data" / "adle.db")
    yield database
    database.dispose()


@pytest.fixture
def backups(tmp_path: Path) -> Path:
    return tmp_path / "backups"


def use_migrations_with_extra_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, failing: bool = False
) -> None:
    """Point the migrator at a copy of the real migrations plus one more revision."""
    real = Path(str(resources.files("adle_core").joinpath("migrations")))
    copy = tmp_path / "migrations"
    shutil.copytree(real, copy, ignore=shutil.ignore_patterns("__pycache__"))
    failure = 'raise RuntimeError("simulated migration failure")' if failing else ""
    (copy / "versions" / "t001_test_notes.py").write_text(
        EXTRA_REVISION.format(failure=failure, previous=REAL_HEAD), encoding="utf-8"
    )

    def config() -> Config:
        cfg = Config()
        cfg.set_main_option("script_location", str(copy))
        return cfg

    monkeypatch.setattr(migrate_module, "_alembic_config", config)


def add_course_with_id(database: Database, course_id: str, title: str) -> None:
    with database.session() as session:
        session.add(Course(id=course_id, title=title, origin="topic"))


def add_course(database: Database, title: str = "Kept across upgrades") -> None:
    add_course_with_id(database, "crs_00000000000000000001", title)


def table_names(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()


# -- fresh databases -------------------------------------------------------


def test_a_new_database_is_created_at_the_head_revision_without_a_backup(
    database: Database, backups: Path
) -> None:
    outcome = migrate(database, backups)
    assert outcome.previous_revision is None
    assert outcome.current_revision == head_revision()
    assert outcome.changed
    assert outcome.backup_path is None
    assert not backups.exists() or not list(backups.iterdir())


def test_migrating_twice_changes_nothing(database: Database, backups: Path) -> None:
    migrate(database, backups)
    again = migrate(database, backups)
    assert not again.changed
    assert again.backup_path is None


def test_the_migrated_schema_matches_the_models_exactly(database: Database, backups: Path) -> None:
    """If this fails, a model changed without a migration (or the reverse)."""
    migrate(database, backups)
    with database.engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "render_as_batch": True}
        )
        differences = [
            difference
            for difference in compare_metadata(context, Base.metadata)
            # The full-text indexes and their shadow tables are created with raw SQL on purpose.
            if "source_chunks_fts" not in repr(difference)
            and "source_chunks_stems" not in repr(difference)
        ]
    assert differences == []


def test_connections_enforce_foreign_keys_and_use_wal(database: Database, backups: Path) -> None:
    migrate(database, backups)
    with database.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"


# -- existing data is protected --------------------------------------------


def test_an_existing_database_is_backed_up_before_it_is_upgraded(
    database: Database, backups: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate(database, backups)
    add_course(database)

    use_migrations_with_extra_revision(monkeypatch, tmp_path)
    outcome = migrate(database, backups)

    assert (outcome.previous_revision, outcome.current_revision) == (REAL_HEAD, TEST_REVISION)
    assert outcome.backup_path is not None
    assert outcome.backup_path.parent == backups
    # The backup is a complete, openable copy of the data as it was before the upgrade.
    assert "test_notes" not in table_names(outcome.backup_path)
    copy = sqlite3.connect(outcome.backup_path)
    try:
        assert copy.execute("SELECT title FROM courses").fetchall() == [("Kept across upgrades",)]
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone() == (REAL_HEAD,)
    finally:
        copy.close()
    # The live database was upgraded and kept its data.
    assert "test_notes" in table_names(database.path)
    with database.session() as session:
        assert session.get(Course, "crs_00000000000000000001") is not None


def test_a_failed_migration_leaves_the_data_untouched_and_reports_the_backup(
    database: Database, backups: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate(database, backups)
    add_course(database)

    use_migrations_with_extra_revision(monkeypatch, tmp_path, failing=True)
    with pytest.raises(MigrationError) as raised:
        migrate(database, backups)

    assert "safety copy" in str(raised.value)
    assert raised.value.backup_path is not None
    assert raised.value.backup_path.exists()
    # The half-applied revision was rolled back: schema and version are as before.
    assert "test_notes" not in table_names(database.path)
    with database.engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == REAL_HEAD
    with database.session() as session:
        assert session.get(Course, "crs_00000000000000000001").title == "Kept across upgrades"


def test_data_from_a_newer_version_is_refused_not_downgraded(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    add_course(database)
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '9999'"))

    with pytest.raises(DatabaseTooNewError) as raised:
        migrate(database, backups)
    assert "newer version of Adle" in str(raised.value)
    with database.session() as session:
        assert session.get(Course, "crs_00000000000000000001") is not None


def test_a_database_adle_did_not_create_is_never_modified(tmp_path: Path, backups: Path) -> None:
    path = tmp_path / "foreign.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE somebody_elses_data (value TEXT)")
    connection.execute("INSERT INTO somebody_elses_data VALUES ('precious')")
    connection.commit()
    connection.close()

    database = Database(path)
    try:
        with pytest.raises(UnrecognisedDatabaseError):
            migrate(database, backups)
    finally:
        database.dispose()
    assert table_names(path) == {"somebody_elses_data"}


def test_only_the_most_recent_automatic_backups_are_kept(
    database: Database, backups: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate(database, backups)
    backups.mkdir(parents=True, exist_ok=True)
    for index in range(MAX_AUTOMATIC_BACKUPS + 3):
        (backups / f"adle-before-old-{index:02d}.db").write_bytes(b"old backup")
    (backups / "my-own-copy.db").write_bytes(b"not ours to delete")

    use_migrations_with_extra_revision(monkeypatch, tmp_path)
    outcome = migrate(database, backups)

    automatic = sorted(backups.glob("adle-before-*.db"))
    assert len(automatic) == MAX_AUTOMATIC_BACKUPS
    assert outcome.backup_path in automatic
    assert (backups / "my-own-copy.db").exists()


def test_backup_captures_changes_still_in_the_write_ahead_log(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "Only in the WAL so far")
    destination = tmp_path / "copy.db"
    backup_database(database.path, destination)
    copy = sqlite3.connect(destination)
    try:
        assert copy.execute("SELECT title FROM courses").fetchone() == ("Only in the WAL so far",)
    finally:
        copy.close()


# -- restoring a backup ----------------------------------------------------


def course_titles(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("SELECT title FROM courses ORDER BY title")]
    finally:
        connection.close()


def test_a_backup_can_be_restored_and_the_data_it_replaces_is_kept(
    tmp_path: Path, backups: Path
) -> None:
    # A folder name with characters that are special in a SQLite URI.
    path = tmp_path / "my data #1 (100%)" / "adle.db"
    database = Database(path)
    migrate(database, backups)
    add_course(database, "As it was")
    saved = tmp_path / "my data #1 (100%)" / "saved copy.db"
    backup_database(path, saved)

    with database.session() as session:
        course = session.get(Course, "crs_00000000000000000001")
        assert course is not None
        course.title = "Changed afterwards"
    database.dispose()

    replaced = restore_database(saved, path, backups)

    # The app opens the restored file like any other: current schema, earlier data.
    restored = Database(path)
    try:
        assert not migrate(restored, backups).changed
        with restored.session() as session:
            course = session.get(Course, "crs_00000000000000000001")
            assert course is not None
            assert course.title == "As it was"
    finally:
        restored.dispose()
    # Restoring discards nothing: what was replaced is itself kept as a backup.
    assert replaced is not None
    assert replaced.parent == backups
    assert course_titles(replaced) == ["Changed afterwards"]
    assert not list(path.parent.glob("*.restoring"))


def test_an_older_backup_is_restored_then_upgraded_like_any_database(
    tmp_path: Path, backups: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "data" / "adle.db"
    database = Database(path)
    migrate(database, backups)
    add_course(database, "From the older version")
    saved = tmp_path / "saved.db"
    backup_database(path, saved)
    database.dispose()

    use_migrations_with_extra_revision(monkeypatch, tmp_path)
    restore_database(saved, path, backups)
    restored = Database(path)
    try:
        outcome = migrate(restored, backups)
        assert (outcome.previous_revision, outcome.current_revision) == (REAL_HEAD, TEST_REVISION)
        assert course_titles(path) == ["From the older version"]
    finally:
        restored.dispose()


def test_restoring_where_there_is_no_data_yet_replaces_nothing(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "Brought to a new computer")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)

    fresh = tmp_path / "new-profile" / "adle.db"
    assert restore_database(saved, fresh, tmp_path / "new-profile" / "backups") is None
    assert course_titles(fresh) == ["Brought to a new computer"]


def write_plain_sqlite(path: Path, statements: list[str]) -> None:
    connection = sqlite3.connect(path)
    try:
        for statement in statements:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize("kind", ["missing", "empty", "text", "other-database", "two-versions"])
def test_a_file_that_is_not_an_adle_backup_is_refused_and_nothing_changes(
    database: Database, backups: Path, tmp_path: Path, kind: str
) -> None:
    migrate(database, backups)
    add_course(database, "Still here")
    database.dispose()

    offered = tmp_path / "offered.db"
    if kind == "empty":
        offered.write_bytes(b"")
    elif kind == "text":
        offered.write_text("These are my lecture notes, not a database.", encoding="utf-8")
    elif kind == "other-database":
        write_plain_sqlite(offered, ["CREATE TABLE recipes (name TEXT)"])
    elif kind == "two-versions":
        write_plain_sqlite(
            offered,
            [
                "CREATE TABLE alembic_version (version_num TEXT)",
                "INSERT INTO alembic_version VALUES ('0001'), ('0001')",
            ],
        )

    with pytest.raises(InvalidBackupError) as raised:
        restore_database(offered, database.path, backups)

    assert "not changed" in str(raised.value)
    assert course_titles(database.path) == ["Still here"]
    assert not backups.exists() or not list(backups.glob("adle-replaced-*"))
    assert not list(database.path.parent.glob("*.restoring"))


def test_a_backup_from_a_newer_version_is_refused_and_nothing_changes(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "Still here")
    database.dispose()
    offered = tmp_path / "from-the-future.db"
    write_plain_sqlite(
        offered,
        [
            "CREATE TABLE alembic_version (version_num TEXT)",
            "INSERT INTO alembic_version VALUES ('9999')",
        ],
    )

    with pytest.raises(DatabaseTooNewError):
        restore_database(offered, database.path, backups)

    assert course_titles(database.path) == ["Still here"]


def test_a_database_that_is_open_elsewhere_is_not_replaced(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "In use")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)

    # Another connection is in the middle of reading: the checkpoint cannot complete.
    reader = sqlite3.connect(database.path)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM courses").fetchone()
        add_course_with_id(database, "crs_00000000000000000002", "Written while it reads")
        with pytest.raises(MigrationError) as raised:
            restore_database(saved, database.path, backups)
    finally:
        reader.close()

    assert not isinstance(raised.value, InvalidBackupError)
    assert "left as it was" in str(raised.value)
    assert course_titles(database.path) == ["In use", "Written while it reads"]
    # Nothing was replaced, so nothing says otherwise: no safety copy, no working file.
    assert not list(backups.glob("adle-replaced-*"))
    assert not list(database.path.parent.glob("*.restoring*"))


def test_a_backup_is_a_single_file_and_looking_at_it_creates_nothing_beside_it(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "In the backup")
    folder = tmp_path / "somewhere of the learner's"
    saved = folder / "saved.db"
    backup_database(database.path, saved)
    assert [entry.name for entry in folder.iterdir()] == ["saved.db"]

    # Restoring from a file only reads it. A copy left in the live database's
    # write-ahead mode would gain two files beside it here, and keep them.
    fresh = tmp_path / "new-profile" / "adle.db"
    restore_database(saved, fresh, tmp_path / "new-profile" / "backups")

    assert [entry.name for entry in folder.iterdir()] == ["saved.db"]
    assert course_titles(fresh) == ["In the backup"]


def test_what_prepares_a_restore_runs_on_a_working_copy_and_can_stop_it(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "As it was")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)
    with database.session() as session:
        course = session.get(Course, "crs_00000000000000000001")
        assert course is not None
        course.title = "Current"
    database.dispose()
    seen: list[Path] = []

    def refuse(working_copy: Path) -> None:
        seen.append(working_copy)
        assert course_titles(working_copy) == ["As it was"]
        raise MigrationError("This copy will not do.")

    with pytest.raises(MigrationError, match="will not do"):
        restore_database(saved, database.path, backups, prepare=refuse)

    assert len(seen) == 1
    assert seen[0] not in {saved, database.path}
    assert course_titles(database.path) == ["Current"]
    assert not list(backups.glob("adle-replaced-*"))
    assert not list(database.path.parent.glob("*.restoring*"))

    def rename(working_copy: Path) -> None:
        connection = sqlite3.connect(working_copy)
        try:
            connection.execute("UPDATE courses SET title = 'Prepared'")
            connection.commit()
        finally:
            connection.close()

    restore_database(saved, database.path, backups, prepare=rename)

    # What was prepared is what is restored; the file it came from is untouched.
    assert course_titles(database.path) == ["Prepared"]
    assert course_titles(saved) == ["As it was"]


def test_a_restore_that_fails_for_any_reason_leaves_no_working_file(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "Current")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)
    database.dispose()

    def break_unexpectedly(_working_copy: Path) -> None:
        raise RuntimeError("not a failure anyone planned for")

    with pytest.raises(RuntimeError, match="not a failure anyone planned for"):
        restore_database(saved, database.path, backups, prepare=break_unexpectedly)

    assert course_titles(database.path) == ["Current"]
    assert not list(database.path.parent.glob("*.restoring*"))
    assert not list(backups.glob("adle-replaced-*"))


def test_only_the_newest_copies_of_replaced_data_are_kept(
    database: Database, backups: Path, tmp_path: Path
) -> None:
    migrate(database, backups)
    add_course(database, "Restored again and again")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)
    database.dispose()
    backups.mkdir(parents=True, exist_ok=True)
    # Other files in the folder are not ours to tidy: an automatic backup, something of the learner's.
    (backups / "adle-before-0002-from-0001-20260101T000000Z.db").write_bytes(b"kept")
    (backups / "my-own-copy.db").write_bytes(b"kept")

    replaced = [
        restore_database(saved, database.path, backups)
        for _ in range(migrate_module.MAX_REPLACED_BACKUPS + 2)
    ]

    kept = sorted(path.name for path in backups.glob("adle-replaced-*.db"))
    assert len(kept) == migrate_module.MAX_REPLACED_BACKUPS
    # The newest ones, so the latest restore can always be undone.
    newest = [path.name for path in replaced[-migrate_module.MAX_REPLACED_BACKUPS :] if path]
    assert kept == sorted(newest)
    assert (backups / "adle-before-0002-from-0001-20260101T000000Z.db").exists()
    assert (backups / "my-own-copy.db").exists()


def test_copies_of_replaced_data_made_in_the_same_moment_are_all_kept(
    database: Database, backups: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate(database, backups)
    add_course(database, "Restored twice at once")
    saved = tmp_path / "saved.db"
    backup_database(database.path, saved)
    database.dispose()

    class StoppedClock(datetime):
        """Reads the same every time, as Windows' clock does for about 15 ms."""

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> StoppedClock:
            return cls(2026, 11, 23, 17, 44, 15, 744545, tzinfo=tz)

    monkeypatch.setattr(migrate_module, "datetime", StoppedClock)
    replaced = [restore_database(saved, database.path, backups) for _ in range(3)]

    # None replaced the one before it, and their names keep the order they were made in.
    names = [path.name for path in replaced if path]
    assert len(set(names)) == 3
    assert names == sorted(names)
    assert sorted(path.name for path in backups.glob("adle-replaced-*.db")) == names
    assert all(course_titles(path) == ["Restored twice at once"] for path in replaced if path)


# -- model behaviour -------------------------------------------------------


def test_timestamps_are_stored_in_utc_and_naive_values_are_refused(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    tokyo = timezone(timedelta(hours=9))
    opened = datetime(2026, 11, 19, 18, 30, tzinfo=tokyo)
    with database.session() as session:
        session.add(
            Course(id="crs_00000000000000000002", title="T", origin="topic", last_opened_at=opened)
        )
    with database.session() as session:
        stored = session.get(Course, "crs_00000000000000000002").last_opened_at
    assert stored == opened
    assert stored.tzinfo is UTC

    with pytest.raises(Exception, match="timezone-aware"), database.session() as session:
        session.add(
            Course(
                id="crs_00000000000000000003",
                title="T",
                origin="topic",
                last_opened_at=datetime(2026, 1, 1),
            )
        )


def test_invalid_enumerated_values_are_rejected_by_the_database(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    with pytest.raises(Exception, match="origin_allowed"), database.session() as session:
        session.add(Course(id="crs_00000000000000000004", title="T", origin="imaginary"))


def _add_source_with_chunk(database: Database, chunk_text: str) -> None:
    with database.session() as session:
        session.add(
            Source(
                id="src_00000000000000000001",
                course_id="crs_00000000000000000001",
                display_name="notes.txt",
                kind="text",
                content_hash="a" * 64,
                size_bytes=10,
                status="extracted",
                warnings=[],
                parser="text",
                parser_version="1",
                char_count=len(chunk_text),
            )
        )
        session.add(
            SourceSection(
                id="sec_00000000000000000001",
                source_id="src_00000000000000000001",
                ordinal=0,
                kind="document",
                char_count=len(chunk_text),
                confidence=1.0,
            )
        )
        session.flush()
        session.add(
            SourceChunk(
                source_id="src_00000000000000000001",
                section_id="sec_00000000000000000001",
                course_id="crs_00000000000000000001",
                ordinal=0,
                text=chunk_text,
                char_start=0,
                char_end=len(chunk_text),
                content_hash="b" * 64,
            )
        )


def _fts_matches(database: Database, term: str) -> int:
    with database.engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM source_chunks_fts WHERE source_chunks_fts MATCH :term"),
            {"term": term},
        ).scalar_one()


def _fts_is_consistent(database: Database) -> None:
    with database.engine.begin() as connection:
        # Raises if the index disagrees with the content table.
        connection.execute(
            text("INSERT INTO source_chunks_fts(source_chunks_fts) VALUES ('integrity-check')")
        )


def test_the_full_text_index_follows_inserts_updates_and_cascading_deletes(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    add_course(database)
    _add_source_with_chunk(database, "Backpropagation applies the chain rule.")
    assert _fts_matches(database, "backpropagation") == 1
    _fts_is_consistent(database)

    with database.session() as session:
        chunk = session.query(SourceChunk).one()
        chunk.text = "Gradient descent follows the slope."
    assert _fts_matches(database, "backpropagation") == 0
    assert _fts_matches(database, "gradient") == 1
    _fts_is_consistent(database)

    # Deleting the course cascades to sources, sections, and chunks, and the
    # index entries must go with them.
    with database.session() as session:
        session.delete(session.get(Course, "crs_00000000000000000001"))
    assert _fts_matches(database, "gradient") == 0
    with database.session() as session:
        assert session.query(Source).count() == 0
        assert session.query(SourceSection).count() == 0
        assert session.query(SourceChunk).count() == 0
    _fts_is_consistent(database)


def test_the_same_file_cannot_be_stored_twice_in_one_course(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    add_course(database)
    _add_source_with_chunk(database, "text")
    with pytest.raises(Exception, match="UNIQUE"), database.session() as session:
        session.add(
            Source(
                id="src_00000000000000000002",
                course_id="crs_00000000000000000001",
                display_name="copy.txt",
                kind="text",
                content_hash="a" * 64,
                size_bytes=10,
                status="extracted",
                warnings=[],
                parser="text",
                parser_version="1",
                char_count=4,
            )
        )


# -- upgrading real data across a table rebuild ----------------------------------


def _upgrade_to(database: Database, revision: str) -> None:
    config = migrate_module._alembic_config()
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def test_requests_recorded_before_there_was_a_choice_belong_to_the_only_provider_there_was(
    database: Database, backups: Path
) -> None:
    """Revision 0006 says which provider each request went to. Before it, there was one."""
    _upgrade_to(database, "0005")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO model_usage (started_at, purpose, model, prompt_tokens, "
                "completion_tokens, estimated, outcome) VALUES "
                "('2026-11-19 10:00:00.000000', 'lesson', 'coding-kimi-k3-free', 900, 400, 0, 'ok')"
            )
        )

    outcome = migrate(database, backups)
    assert (outcome.previous_revision, outcome.current_revision) == ("0005", head_revision())

    with database.engine.begin() as connection:
        rows = connection.execute(
            text("SELECT provider, model, prompt_tokens, outcome FROM model_usage")
        ).all()
        # Nothing that was counted is lost, and it is counted for the right provider.
        assert [tuple(row) for row in rows] == [("aihubmix", "coding-kimi-k3-free", 900, "ok")]
        # A row written without saying where it went cannot be for anyone else either.
        connection.execute(
            text(
                "INSERT INTO model_usage (started_at, purpose, model, prompt_tokens, "
                "completion_tokens, estimated, outcome) VALUES "
                "('2026-11-20 10:00:00.000000', 'scene', 'm', 1, 1, 1, 'ok')"
            )
        )
        providers = connection.execute(text("SELECT DISTINCT provider FROM model_usage")).all()
        assert [tuple(row) for row in providers] == [("aihubmix",)]


def test_learner_evidence_survives_the_rebuild_that_adds_dismissals(
    database: Database, backups: Path
) -> None:
    """Revision 0005 rebuilds ``learner_observations``. Nothing recorded before it may be lost."""
    _upgrade_to(database, "0004")
    stamp = "2026-11-01 10:00:00.000000"
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO courses (id, title, description, origin, created_at, updated_at) "
                "VALUES ('crs_00000000000000000001', 'Kept', '', 'topic', :at, :at)"
            ),
            {"at": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO concepts (id, course_id, title, summary, position, complexity, "
                "tags, origin, created_at, updated_at) VALUES ('con_00000000000000000001', "
                "'crs_00000000000000000001', 'Weights', '', 0, 2, '[]', 'learner', :at, :at)"
            ),
            {"at": stamp},
        )
        for outcome in ("correct", "incorrect"):
            connection.execute(
                text(
                    "INSERT INTO learner_observations (concept_id, course_id, occurred_at, kind, "
                    "outcome, question_form, is_transfer, hinted, unsure, item_guess, "
                    "state_before, state_after, explanation, config_version) VALUES "
                    "('con_00000000000000000001', 'crs_00000000000000000001', :at, 'answer', "
                    ":outcome, 'numeric', 0, 1, 0, 0.02, 'not_assessed', 'building', "
                    "'An explanation worth keeping.', 'bkt-1')"
                ),
                {"at": stamp, "outcome": outcome},
            )
        connection.execute(
            text(
                "INSERT INTO learner_concept_states (concept_id, course_id, probability, state, "
                "missing, answered, correct, unaided_correct, hinted, skipped, forms_correct, "
                "transfer_correct, review_streak, updated_at) VALUES ('con_00000000000000000001', "
                "'crs_00000000000000000001', 0.4, 'building', '[]', 2, 1, 0, 2, 0, '[]', 0, 0, :at)"
            ),
            {"at": stamp},
        )

    outcome = migrate(database, backups)
    assert (outcome.previous_revision, outcome.current_revision) == ("0004", head_revision())
    assert outcome.backup_path is not None
    assert outcome.backup_path.exists()

    with database.engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT id, outcome, hinted, explanation, config_version, slip, "
                "unresolved_misconception FROM learner_observations ORDER BY id"
            )
        ).all()
        assert [tuple(row) for row in rows] == [
            (1, "correct", 1, "An explanation worth keeping.", "bkt-1", 0, None),
            (2, "incorrect", 1, "An explanation worth keeping.", "bkt-1", 0, None),
        ]
        state = connection.execute(
            text("SELECT answered, unresolved_misconception FROM learner_concept_states")
        ).one()
        assert tuple(state) == (2, 0)
        indexes = {
            row[1] for row in connection.execute(text("PRAGMA index_list('learner_observations')"))
        }
        assert {"ix_learner_observations_concept", "ix_learner_observations_course_id"} <= indexes

        # The new kind is accepted, and the rule that there are only a few kinds still holds.
        insert = text(
            "INSERT INTO learner_observations (concept_id, course_id, occurred_at, kind, "
            "is_transfer, hinted, unsure, slip, unresolved_misconception, state_before, "
            "state_after, explanation, config_version) VALUES ('con_00000000000000000001', "
            "'crs_00000000000000000001', :at, :kind, 0, 0, 0, 0, 0, 'building', 'building', "
            "'x', 'bkt-2')"
        )
        connection.execute(insert, {"at": stamp, "kind": "dismissal"})
        with pytest.raises(Exception, match="kind_allowed"):
            connection.execute(insert, {"at": stamp, "kind": "rumour"})


def test_removing_a_course_removes_what_the_learner_did_in_it(
    database: Database, backups: Path
) -> None:
    migrate(database, backups)
    add_course(database)
    with database.session() as session:
        session.add(
            LearnerEvent(
                course_id="crs_00000000000000000001",
                occurred_at=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
                kind="lesson_completed",
                detail={},
            )
        )
    with pytest.raises(Exception, match="kind_allowed"), database.session() as session:
        session.add(
            LearnerEvent(
                course_id="crs_00000000000000000001",
                occurred_at=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
                kind="mood_inferred",
                detail={},
            )
        )
    with database.session() as session:
        session.delete(session.get(Course, "crs_00000000000000000001"))
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM learner_events")).scalar_one() == 0


def test_an_error_from_the_database_never_carries_the_values_of_its_statement(
    tmp_path: Path,
) -> None:
    """Those values are the learner's documents, questions, and answers, and errors are logged."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    database = Database(tmp_path / "adle.db")
    try:
        with pytest.raises(SQLAlchemyError) as raised, database.session() as session:
            session.execute(
                text("INSERT INTO no_such_table (words) VALUES (:words)"),
                {"words": "what the learner wrote, word for word"},
            )
        assert "word for word" not in str(raised.value)
        assert "no_such_table" in str(raised.value)
    finally:
        database.dispose()
