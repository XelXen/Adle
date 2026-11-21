"""The provider key: held in memory only, never returned, never logged."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault, SecretRedactionFilter

API_KEY = "sk-test-provider-key-0123456789"


def test_status_reflects_whether_a_key_is_configured(client: TestClient) -> None:
    assert client.get("/v1/provider").json()["key_configured"] is False

    assert client.put("/v1/provider/credential", json={"api_key": API_KEY}).status_code == 204
    status = client.get("/v1/provider").json()
    assert status["key_configured"] is True
    assert status["base_url"] == "https://aihubmix.com/v1"
    assert status["model"] == "coding-kimi-k3-free"

    assert client.delete("/v1/provider/credential").status_code == 204
    assert client.get("/v1/provider").json()["key_configured"] is False


def test_the_key_is_never_returned_by_any_endpoint(client: TestClient) -> None:
    put = client.put("/v1/provider/credential", json={"api_key": API_KEY})
    assert API_KEY not in put.text
    assert API_KEY not in client.get("/v1/provider").text
    assert API_KEY not in client.get("/v1/health").text


def test_the_key_is_not_written_to_the_data_directory(
    client: TestClient, services: Services
) -> None:
    client.put("/v1/provider/credential", json={"api_key": API_KEY})
    for file in services.settings.data_dir.rglob("*"):
        if file.is_file():
            assert API_KEY.encode() not in file.read_bytes()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"api_key": "has spaces in it"},
        {"api_key": "line\nbreak-in-key-value"},
        {"api_key": "k" * 513},
        {"api_key": API_KEY, "base_url": "https://attacker.example"},
    ],
)
def test_malformed_credentials_are_rejected(client: TestClient, payload: dict[str, str]) -> None:
    assert client.put("/v1/provider/credential", json=payload).status_code == 422
    assert client.get("/v1/provider").json()["key_configured"] is False


def test_credential_routes_are_marked_internal(services: Services) -> None:
    """The renderer allowlist is generated from this flag; losing it would expose the routes."""
    from adle_core.api.app import create_app

    paths = create_app(services).openapi()["paths"]
    credential = paths["/v1/provider/credential"]
    assert credential["put"]["x-adle-internal"] is True
    assert credential["delete"]["x-adle-internal"] is True
    assert "x-adle-internal" not in paths["/v1/provider"]["get"]


def test_vault_repr_never_contains_the_key() -> None:
    vault = CredentialVault()
    vault.set_api_key(API_KEY)
    assert API_KEY not in repr(vault)
    assert vault.has_api_key
    vault.clear_api_key()
    assert vault.api_key() is None


def test_redaction_filter_scrubs_secrets_from_log_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    vault = CredentialVault()
    vault.set_api_key(API_KEY)
    logger = logging.getLogger("adle_core.test.redaction")
    logger.addFilter(SecretRedactionFilter(vault, extra_secrets=("launch-token-value",)))

    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("request failed: Authorization: Bearer %s", API_KEY)
        logger.info("token=launch-token-value")
        logger.info("nothing sensitive here")

    assert API_KEY not in caplog.text
    assert "launch-token-value" not in caplog.text
    assert caplog.text.count("[redacted]") == 2
    assert "nothing sensitive here" in caplog.text


def test_a_key_inside_the_text_of_an_error_is_removed_from_its_traceback_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A traceback is formatted from the exception, after the message has been cleaned."""
    vault = CredentialVault()
    vault.set_api_key(API_KEY)
    logger = logging.getLogger("adle_core.test.redaction.trace")
    logger.addFilter(SecretRedactionFilter(vault))

    with caplog.at_level(logging.INFO, logger=logger.name):
        try:
            raise RuntimeError(f"401 for Authorization: Bearer {API_KEY}")
        except RuntimeError:
            logger.exception("a request failed")

    assert API_KEY not in caplog.text
    (record,) = caplog.records
    assert record.exc_info is None
    assert "RuntimeError" in (record.exc_text or "")
    assert "[redacted]" in (record.exc_text or "")
    assert API_KEY not in (record.exc_text or "")
