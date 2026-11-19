"""The HTTP boundary: authentication, host checks, and the error contract."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from adle_core import __version__
from adle_core.api.auth import MIN_TOKEN_LENGTH, LaunchToken
from tests.conftest import TEST_TOKEN


def test_health_reports_version(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "api_version": "v1"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer wrong-token-0123456789abcdef0123456789"},
        {"Authorization": f"Basic {TEST_TOKEN}"},
        {"Authorization": TEST_TOKEN},
        {"X-Launch-Token": TEST_TOKEN},
    ],
)
def test_every_route_requires_the_launch_token(
    anonymous_client: TestClient, headers: dict[str, str]
) -> None:
    for path in ("/v1/health", "/v1/provider"):
        response = anonymous_client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_token_scheme_is_case_insensitive(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/v1/health", headers={"Authorization": f"bearer {TEST_TOKEN}"})
    assert response.status_code == 200


def test_unknown_host_header_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/health", headers={"Host": "attacker.example"})
    assert response.status_code == 400


def test_unknown_route_uses_the_error_contract(client: TestClient) -> None:
    response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_interactive_documentation_is_not_served(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_no_cors_headers_are_ever_sent(client: TestClient) -> None:
    response = client.get("/v1/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers


def test_validation_errors_do_not_echo_submitted_values(client: TestClient) -> None:
    secret = "short"
    response = client.put("/v1/provider/credential", json={"api_key": secret})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["detail"][0]["field"] == "body.api_key"
    assert secret not in response.text


def test_launch_token_rejects_short_values_and_hides_itself() -> None:
    with pytest.raises(ValueError, match="too short"):
        LaunchToken("x" * (MIN_TOKEN_LENGTH - 1))
    token = LaunchToken(TEST_TOKEN)
    assert TEST_TOKEN not in repr(token)
    assert token.matches(TEST_TOKEN)
    assert not token.matches(TEST_TOKEN + "x")
    assert not token.matches("")
