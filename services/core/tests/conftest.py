"""Shared fixtures. Every test gets an isolated data directory and service container."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.generation.quota import QuotaLimits
from adle_core.ingestion.extract import extract_in_process
from adle_core.ingestion.render import page_picture
from tests.support.model import FakeProvider

TEST_TOKEN = "test-launch-token-0123456789abcdef0123456789"
#: The core answers only to the loopback names; a test client says it is one of them.
LOOPBACK = "http://127.0.0.1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()
    return settings


@pytest.fixture
def provider() -> FakeProvider:
    """The model provider, replaced by a scripted stand-in. No test reaches the real one."""
    return FakeProvider()


@pytest.fixture
def services(settings: Settings, provider: FakeProvider) -> Iterator[Services]:
    """Real services on a fresh database. Documents are parsed in-process for speed;
    the child-process path has its own integration tests."""
    services = build_services(
        settings,
        LaunchToken(TEST_TOKEN),
        extract=extract_in_process,
        draw_page=page_picture,
        provider_transport=httpx.MockTransport(provider),
        # The daily allowance is the real one. The per-minute limit is lifted so that a
        # test which makes five requests does not sit waiting for a minute to pass.
        quota_limits=QuotaLimits(requests_per_minute=600),
    )
    yield services
    services.close()


@pytest.fixture
def anonymous_client(services: Services) -> Iterator[TestClient]:
    """A client that presents no credentials."""
    with TestClient(create_app(services), base_url=LOOPBACK) as client:
        yield client


@pytest.fixture
def client(services: Services) -> Iterator[TestClient]:
    """A client authenticated the way the Electron main process is."""
    with TestClient(
        create_app(services),
        base_url=LOOPBACK,
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        yield client
