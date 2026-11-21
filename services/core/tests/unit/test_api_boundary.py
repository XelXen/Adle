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


def test_the_name_a_test_client_uses_by_default_is_not_a_name_the_core_answers_to(
    client: TestClient,
) -> None:
    response = client.get("/v1/health", headers={"Host": "testserver"})
    assert response.status_code == 400


# -- the gate: nothing is read without the token, and no body is larger than the app's own --


def _scope(headers: dict[str, str]) -> dict[str, object]:
    return {
        "type": "http",
        "method": "POST",
        "path": "/v1/courses",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }


def _run_gate(
    headers: dict[str, str], chunks: list[bytes], *, limit: int = 64
) -> tuple[list[dict[str, object]], int, list[int]]:
    """Put one request through the gate: what was sent, how often its body was read, what got in."""
    import asyncio

    from adle_core.api.gate import Gate

    sent: list[dict[str, object]] = []
    reads = 0
    reached: list[int] = []
    pending = list(chunks)

    async def receive() -> dict[str, object]:
        nonlocal reads
        reads += 1
        body = pending.pop(0) if pending else b""
        return {"type": "http.request", "body": body, "more_body": bool(pending)}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    async def routes(scope: object, receive_: object, send_: object) -> None:
        total = 0
        while True:
            message = await receive_()  # type: ignore[operator]
            total += len(message["body"])
            if not message["more_body"]:
                break
        reached.append(total)

    gate = Gate(routes, token=LaunchToken(TEST_TOKEN), max_body_bytes=limit)  # type: ignore[arg-type]
    try:
        asyncio.run(gate(_scope(headers), receive, send))  # type: ignore[arg-type]
    except Exception as error:
        sent.append({"raised": getattr(error, "status_code", type(error).__name__)})
    return sent, reads, reached


def test_without_the_token_nothing_of_a_request_is_read() -> None:
    sent, reads, reached = _run_gate({"Content-Length": "999999999"}, [b"x" * 1000])
    assert sent[0]["status"] == 401
    assert reads == 0
    assert reached == []
    # The same shape every other refusal has.
    import json

    assert json.loads(sent[1]["body"]) == {  # type: ignore[arg-type]
        "error": {"code": "unauthorized", "message": "This request is not authorised."}
    }


def test_a_body_larger_than_anything_the_app_sends_is_refused_before_it_is_read() -> None:
    authorised = {"Authorization": f"Bearer {TEST_TOKEN}"}
    sent, reads, reached = _run_gate({**authorised, "Content-Length": "65"}, [b"x" * 65])
    assert sent[0]["status"] == 413
    assert reads == 0
    assert reached == []
    # A length that is not a number is not trusted either.
    sent, reads, _ = _run_gate({**authorised, "Content-Length": "lots"}, [b"x"])
    assert sent[0]["status"] == 400
    assert reads == 0


def test_a_body_that_does_not_say_how_long_it_is_is_cut_off_at_the_limit() -> None:
    authorised = {"Authorization": f"Bearer {TEST_TOKEN}"}
    # Sent in pieces with no length declared: reading stops at the piece that passes the limit.
    sent, reads, reached = _run_gate(authorised, [b"x" * 40, b"x" * 40, b"x" * 40, b"x" * 40])
    assert sent == [{"raised": 413}]
    assert reads == 2
    assert reached == []
    # Within the limit it goes through untouched.
    sent, _, reached = _run_gate(authorised, [b"x" * 30, b"x" * 30])
    assert reached == [60]
    assert sent == []


def test_a_request_too_large_is_told_so_in_the_usual_shape(client: TestClient) -> None:
    response = client.post("/v1/courses", content=b"x" * (2 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
