"""Shared fixtures. Every test gets an isolated data directory and service container."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.ingestion.extract import extract_in_process

TEST_TOKEN = "test-launch-token-0123456789abcdef0123456789"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()
    return settings


@pytest.fixture
def services(settings: Settings) -> Iterator[Services]:
    """Real services on a fresh database. Documents are parsed in-process for speed;
    the child-process path has its own integration tests."""
    services = build_services(settings, LaunchToken(TEST_TOKEN), extract=extract_in_process)
    yield services
    services.close()


@pytest.fixture
def anonymous_client(services: Services) -> Iterator[TestClient]:
    """A client that presents no credentials."""
    with TestClient(create_app(services)) as client:
        yield client


@pytest.fixture
def client(services: Services) -> Iterator[TestClient]:
    """A client authenticated the way the Electron main process is."""
    with TestClient(
        create_app(services), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as client:
        yield client
