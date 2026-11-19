"""Schema, migrations, and the guarantees around a learner's data file."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from importlib import resources
from pathlib import Path

import pytest
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
from adle_core.infrastructure.orm import Course, Source, SourceChunk, SourceSection

EXTRA_REVISION = '''"""Add a notes table (test-only revision)."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
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
    (copy / "versions" / "0002_test_notes.py").write_text(
        EXTRA_REVISION.format(failure=failure), encoding="utf-8"
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
            # The FTS index and its shadow tables are created with raw SQL on purpose.
            if "source_chunks_fts" not in repr(difference)
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

    assert (outcome.previous_revision, outcome.current_revision) == ("0001", "0002")
    assert outcome.backup_path is not None
    assert outcome.backup_path.parent == backups
    # The backup is a complete, openable copy of the data as it was before the upgrade.
    assert "test_notes" not in table_names(outcome.backup_path)
    copy = sqlite3.connect(outcome.backup_path)
    try:
        assert copy.execute("SELECT title FROM courses").fetchall() == [("Kept across upgrades",)]
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001",)
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
        assert MigrationContext.configure(connection).get_current_revision() == "0001"
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
        assert (outcome.previous_revision, outcome.current_revision) == ("0001", "0002")
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
