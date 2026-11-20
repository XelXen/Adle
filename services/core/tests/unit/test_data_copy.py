"""Saving a copy of everything, and restoring from one (ADR-016)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application import data_copy
from adle_core.application.data_copy import restore_copy
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.generation.quota import QuotaLimits
from adle_core.infrastructure.asset_store import AssetStore
from adle_core.infrastructure.migrate import CopyOutOfDateError, InvalidBackupError
from adle_core.ingestion.extract import extract_in_process
from tests.conftest import TEST_TOKEN
from tests.support.model import FakeProvider
from tests.unit.test_courses_and_sources import create_course, import_files
from tests.unit.test_database import (
    REAL_HEAD,
    TEST_REVISION,
    use_migrations_with_extra_revision,
)


@contextmanager
def running(settings: Settings) -> Iterator[tuple[Services, TestClient]]:
    """The service on the data in ``settings``, as one run of the app. Closed afterwards."""
    services = build_services(
        settings,
        LaunchToken(TEST_TOKEN),
        extract=extract_in_process,
        provider_transport=httpx.MockTransport(FakeProvider()),
        quota_limits=QuotaLimits(requests_per_minute=600),
    )
    try:
        with TestClient(
            create_app(services), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        ) as client:
            yield services, client
    finally:
        services.close()


def save(client: TestClient, destination: Path) -> None:
    response = client.post("/v1/data/copy", json={"path": str(destination)})
    assert response.status_code == 204, response.text


def titles(client: TestClient) -> list[str]:
    return sorted(course["title"] for course in client.get("/v1/courses").json()["courses"])


def query(path: Path, statement: str) -> list[Any]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute(statement)]
    finally:
        connection.close()


def titles_in(path: Path) -> list[str]:
    return query(path, "SELECT title FROM courses ORDER BY title")


def beside(path: Path) -> list[str]:
    """The names of everything in the folder that holds ``path``."""
    return sorted(entry.name for entry in path.parent.iterdir())


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    """Where a learner might keep a copy: a folder of their own, with an awkward name."""
    folder = tmp_path / "my copies #1 (100%)"
    folder.mkdir()
    return folder / "Adle data 2026-11-19.adle"


# -- saving a copy ---------------------------------------------------------


def test_a_copy_is_one_self_contained_file_with_everything_in_it(
    client: TestClient, copy: Path
) -> None:
    create_course(client, title="Kept in the copy")

    save(client, copy)

    assert beside(copy) == [copy.name]
    # SQLite's single-file mode: it can be read from anywhere, and reading it
    # creates nothing beside it.
    assert copy.read_bytes()[18:20] == b"\x01\x01"
    assert titles_in(copy) == ["Kept in the copy"]
    assert query(copy, "PRAGMA integrity_check") == ["ok"]
    assert beside(copy) == [copy.name]


def test_the_provider_key_is_not_in_a_copy(client: TestClient, copy: Path) -> None:
    key = "sk-test-0123456789abcdefghijklmnop"
    assert client.put("/v1/provider/credential", json={"api_key": key}).status_code == 204
    create_course(client)

    save(client, copy)

    assert b"sk-test" not in copy.read_bytes()


def test_saving_again_replaces_the_older_copy_with_a_complete_one(
    client: TestClient, copy: Path
) -> None:
    create_course(client, title="First")
    save(client, copy)
    create_course(client, title="Second")

    save(client, copy)

    assert titles_in(copy) == ["First", "Second"]
    assert beside(copy) == [copy.name]


def test_a_copy_that_cannot_be_completed_leaves_the_older_one_untouched(
    client: TestClient, copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_course(client, title="In the older copy")
    save(client, copy)
    before = copy.read_bytes()

    def fail_half_way(_source: Path, partial: Path) -> None:
        partial.write_bytes(b"half a copy")
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(data_copy, "backup_database", fail_half_way)
    response = client.post("/v1/data/copy", json={"path": str(copy)})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "copy_not_saved"
    assert "disk is full" not in error["message"]
    assert copy.read_bytes() == before
    assert beside(copy) == [copy.name]


@pytest.mark.parametrize(
    "kind",
    [
        "relative",
        "wrong-ending",
        "no-ending",
        "inside-the-data-folder",
        "folder-missing",
        "a-folder",
    ],
)
def test_a_copy_is_not_written_where_it_should_not_go(
    client: TestClient, settings: Settings, tmp_path: Path, kind: str
) -> None:
    create_course(client)
    if kind == "relative":
        path = "relative-copy.adle"
    elif kind == "wrong-ending":
        path = str(tmp_path / "copy.db")
    elif kind == "no-ending":
        path = str(tmp_path / "copy")
    elif kind == "inside-the-data-folder":
        path = str(settings.backups_dir / "copy.adle")
    elif kind == "folder-missing":
        path = str(tmp_path / "nowhere" / "copy.adle")
    else:
        (tmp_path / "taken.adle").mkdir()
        path = str(tmp_path / "taken.adle")

    response = client.post("/v1/data/copy", json={"path": path})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    # Written for the learner, and never repeating what was submitted.
    assert path not in error["message"]
    assert not Path("relative-copy.adle").exists()
    assert not (tmp_path / "nowhere").exists()
    written = [entry for entry in tmp_path.rglob("*") if entry.is_file()]
    assert all(entry.name.startswith("adle.db") for entry in written), written


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"path": ""},
        {"path": 7},
        {"path": "C:/copies/a\x00b.adle"},
        {"path": "C:/copies/a.adle", "overwrite": True},
        {"path": "x" * 5000 + ".adle"},
    ],
)
def test_a_malformed_request_to_save_a_copy_is_refused(
    client: TestClient, body: dict[str, Any]
) -> None:
    response = client.post("/v1/data/copy", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_saving_a_copy_is_for_the_desktop_shell_only(services: Services) -> None:
    """The page must never be able to name a file. The renderer's allowlist of
    operations is generated from this flag; losing it would expose the route."""
    spec = create_app(services).openapi()
    assert spec["paths"]["/v1/data/copy"]["post"]["x-adle-internal"] is True

    schemas = spec["components"]["schemas"]
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            body = operation.get("requestBody", {}).get("content", {})
            reference = body.get("application/json", {}).get("schema", {}).get("$ref", "")
            properties = schemas.get(reference.rsplit("/", 1)[-1], {}).get("properties", {})
            if {"path", "paths"} & set(properties):
                assert operation.get("x-adle-internal") is True, (method, path)


# -- restoring from a copy -------------------------------------------------


def test_restoring_brings_back_what_the_copy_held_and_keeps_what_it_replaced(
    settings: Settings, copy: Path
) -> None:
    with running(settings) as (_, client):
        create_course(client, title="In the copy")
        save(client, copy)
        create_course(client, title="Added afterwards")

    replaced = restore_copy(settings, copy)

    with running(settings) as (_, client):
        assert titles(client) == ["In the copy"]
    # Nothing is discarded: what was replaced is itself kept, and is a copy like any other.
    assert replaced is not None
    assert titles_in(replaced) == ["Added afterwards", "In the copy"]
    assert [entry.name for entry in settings.backups_dir.iterdir()] == [replaced.name]
    # Nothing is left lying about, beside the data or beside the learner's own file.
    assert not list(settings.data_dir.glob("*.restoring*"))
    assert beside(copy) == [copy.name]


def test_a_safety_copy_can_itself_be_restored(settings: Settings, copy: Path) -> None:
    with running(settings) as (_, client):
        create_course(client, title="In the copy")
        save(client, copy)
        create_course(client, title="Added afterwards")
    replaced = restore_copy(settings, copy)
    assert replaced is not None

    restore_copy(settings, replaced)

    with running(settings) as (_, client):
        assert titles(client) == ["Added afterwards", "In the copy"]


def test_a_copy_can_be_restored_where_there_is_no_data_yet(
    settings: Settings, copy: Path, tmp_path: Path
) -> None:
    with running(settings) as (_, client):
        create_course(client, title="Brought to a new computer")
        save(client, copy)
    elsewhere = Settings(data_dir=tmp_path / "another computer" / "data")
    elsewhere.ensure_directories()

    assert restore_copy(elsewhere, copy) is None

    with running(elsewhere) as (_, client):
        assert titles(client) == ["Brought to a new computer"]


def test_an_older_copy_is_brought_up_to_date_before_it_replaces_anything(
    settings: Settings, copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with running(settings) as (_, client):
        create_course(client, title="From the older version")
        save(client, copy)
    use_migrations_with_extra_revision(monkeypatch, tmp_path)

    replaced = restore_copy(settings, copy)

    assert query(settings.db_path, "SELECT version_num FROM alembic_version") == [TEST_REVISION]
    assert titles_in(settings.db_path) == ["From the older version"]
    # The working copy was a copy of a copy, so no safety copy of *it* was made:
    # the only one is of the data that was replaced.
    assert replaced is not None
    assert [entry.name for entry in settings.backups_dir.iterdir()] == [replaced.name]
    # The learner's own file is as they saved it.
    assert query(copy, "SELECT version_num FROM alembic_version") == [REAL_HEAD]
    assert not list(settings.data_dir.glob("*.restoring*"))


def test_a_copy_that_cannot_be_brought_up_to_date_replaces_nothing(
    settings: Settings, copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with running(settings) as (_, client):
        create_course(client, title="In the copy")
        save(client, copy)
        create_course(client, title="Current")
    use_migrations_with_extra_revision(monkeypatch, tmp_path, failing=True)

    with pytest.raises(CopyOutOfDateError) as raised:
        restore_copy(settings, copy)

    assert "not changed" in str(raised.value)
    assert titles_in(settings.db_path) == ["Current", "In the copy"]
    assert query(settings.db_path, "SELECT version_num FROM alembic_version") == [REAL_HEAD]
    assert not list(settings.data_dir.glob("*.restoring*"))
    assert not list(settings.backups_dir.iterdir())


def test_another_programs_database_is_refused_even_with_a_version_table(
    settings: Settings, tmp_path: Path
) -> None:
    with running(settings) as (_, client):
        create_course(client, title="Still here")
    offered = tmp_path / "theirs.adle"
    connection = sqlite3.connect(offered)
    try:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
        connection.execute("INSERT INTO alembic_version VALUES (?)", (REAL_HEAD,))
        connection.execute("CREATE TABLE recipes (name TEXT)")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(InvalidBackupError) as raised:
        restore_copy(settings, offered)

    assert "not changed" in str(raised.value)
    assert titles_in(settings.db_path) == ["Still here"]
    assert not list(settings.backups_dir.iterdir())


def test_the_data_in_use_is_not_a_copy_of_itself(settings: Settings) -> None:
    with running(settings) as (_, client):
        create_course(client, title="Still here")

    with pytest.raises(InvalidBackupError) as raised:
        restore_copy(settings, settings.db_path)

    assert "using now" in str(raised.value)
    assert titles_in(settings.db_path) == ["Still here"]
    assert not list(settings.backups_dir.iterdir())


def test_a_restore_that_breaks_unexpectedly_is_reported_without_naming_the_file(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The service must still start, and neither the answer nor the log may carry the path."""
    from adle_core import __main__ as entry

    copy = tmp_path / "Anna's private folder" / "copy.adle"

    def break_unexpectedly(_settings: Settings, offered: Path) -> None:
        raise PermissionError(13, "Access is denied", str(offered))

    monkeypatch.setattr(entry, "restore_copy", break_unexpectedly)
    with caplog.at_level("INFO", logger="adle_core"):
        report = entry._restore(settings, copy)

    assert report["ok"] is False
    assert "not changed" in report["message"]
    assert "Anna" not in report["message"]
    assert "Anna" not in caplog.text
    assert "PermissionError" in caplog.text


def test_a_refused_restore_is_reported_in_the_words_written_for_the_learner(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from adle_core import __main__ as entry

    offered = tmp_path / "Anna's private folder" / "notes.adle"
    offered.parent.mkdir()
    offered.write_text("These are my lecture notes.", encoding="utf-8")

    with caplog.at_level("INFO", logger="adle_core"):
        report = entry._restore(settings, offered)

    assert report == {
        "ok": False,
        "message": "That file is not a copy of Adle's data, or it is damaged. "
        "Your current data was not changed.",
    }
    assert "Anna" not in caplog.text


# -- the originals of imported files ---------------------------------------


def stored_originals(settings: Settings) -> list[str]:
    return sorted(entry.name for entry in settings.sources_dir.iterdir() if entry.is_file())


def test_after_a_restore_originals_that_nothing_refers_to_are_removed(
    settings: Settings, copy: Path
) -> None:
    with running(settings) as (services, client):
        course = create_course(client)
        import_files(client, services, course["id"], "study-notes.txt")
        in_the_copy = stored_originals(settings)
        save(client, copy)
        import_files(client, services, course["id"], "neural-networks-syllabus.md")
        assert len(stored_originals(settings)) == 2
        # While every file belongs to a source, nothing is removed.
        assert services.sources.forget_unreferenced_files() == 0
        assert len(stored_originals(settings)) == 2

    restore_copy(settings, copy)

    with running(settings) as (services, client):
        assert services.sources.forget_unreferenced_files() == 1
        assert stored_originals(settings) == in_the_copy
        # The source in the copy is whole, with or without its original.
        sources = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
        assert [source["display_name"] for source in sources] == ["study-notes.txt"]


def test_a_source_whose_original_is_missing_still_works_and_can_be_removed(
    settings: Settings, copy: Path, tmp_path: Path
) -> None:
    """A copy does not carry the imported files, so on another computer they are absent."""
    with running(settings) as (services, client):
        course = create_course(client)
        import_files(client, services, course["id"], "study-notes.txt")
        save(client, copy)
    elsewhere = Settings(data_dir=tmp_path / "another computer" / "data")
    elsewhere.ensure_directories()
    restore_copy(elsewhere, copy)

    with running(elsewhere) as (services, client):
        assert stored_originals(elsewhere) == []
        assert services.sources.forget_unreferenced_files() == 0
        sources = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
        assert [source["display_name"] for source in sources] == ["study-notes.txt"]
        found = client.get(f"/v1/courses/{course['id']}/search", params={"q": "gradient"})
        assert found.status_code == 200
        assert client.delete(f"/v1/sources/{sources[0]['id']}").status_code == 204
        assert client.delete(f"/v1/courses/{course['id']}").status_code == 204


def test_keeping_only_named_files_spares_folders_and_what_is_named(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "sources")
    (store.root / "src_kept.pdf").write_bytes(b"kept")
    (store.root / "src_orphan.txt").write_bytes(b"orphan")
    (store.root / "src_interrupted.pdf.part").write_bytes(b"half")
    (store.root / "a folder").mkdir()
    (store.root / "a folder" / "inside.txt").write_bytes(b"not ours to judge")

    assert store.keep_only({"src_kept.pdf", "src_named_but_absent.md"}) == 2

    assert sorted(entry.name for entry in store.root.iterdir()) == ["a folder", "src_kept.pdf"]
    assert (store.root / "a folder" / "inside.txt").exists()
