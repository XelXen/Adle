"""The provider client against a transport that never leaves the process."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import (
    BASE_URL_ENV,
    MODEL_ENV,
    ChatClient,
    ChatRequest,
    ProviderBadResponseError,
    ProviderConfig,
    ProviderConfigError,
    ProviderKeyMissingError,
    ProviderKeyRejectedError,
    ProviderRateLimitedError,
    ProviderRequestRefusedError,
    ProviderUnavailableError,
    RequestCancelledError,
)

KEY = "sk-test-0123456789abcdefghijklmnop"
REQUEST = ChatRequest(
    purpose="lesson",
    system="You write lessons.",
    user="Write about weights.",
    max_output_tokens=2000,
    json_output=True,
)

Handler = Callable[[httpx.Request], httpx.Response]


def sse(*events: Any) -> httpx.Response:
    body = "".join(
        f"data: {event if isinstance(event, str) else json.dumps(event)}\n\n" for event in events
    )
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


def delta(text: str, finish: str | None = None) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": finish}]}


def client_for(handler: Handler, *, key: str | None = KEY, **options: Any) -> ChatClient:
    vault = CredentialVault()
    if key:
        vault.set_api_key(key)
    return ChatClient(ProviderConfig(), vault, transport=httpx.MockTransport(handler), **options)


# -- configuration ------------------------------------------------------------


def test_the_default_provider_is_the_documented_one() -> None:
    config = ProviderConfig.from_environment({})
    assert (config.provider_id, config.display_name) == ("aihubmix", "AIHubMix")
    assert config.base_url == "https://aihubmix.com/v1"
    assert config.model == "coding-kimi-k3-free"


def test_another_endpoint_is_named_as_such_so_it_is_never_used_silently() -> None:
    config = ProviderConfig.from_environment(
        {BASE_URL_ENV: "http://127.0.0.1:8123/v1/", MODEL_ENV: "local-model"}
    )
    assert config.provider_id == "custom"
    assert config.display_name == "Custom endpoint (127.0.0.1)"
    assert config.base_url == "http://127.0.0.1:8123/v1"
    assert config.model == "local-model"
    # Only the model changed: it is still the documented provider.
    same = ProviderConfig.from_environment({MODEL_ENV: "another-model"})
    assert (same.provider_id, same.model) == ("aihubmix", "another-model")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://example.com/v1",
        "ftp://example.com/v1",
        "https://user:secret@example.com/v1",
        "https://example.com/v1?key=1",
        "https://example.com/v1#x",
        "https:///v1",
        "not a url",
        "http://127.0.0.1.example.com/v1",
        "http://[::1/v1",
    ],
)
def test_an_endpoint_that_is_not_plain_https_is_refused(base_url: str) -> None:
    with pytest.raises(ProviderConfigError):
        ProviderConfig.from_environment({BASE_URL_ENV: base_url})


@pytest.mark.parametrize("model", ["two words", "x" * 101, "tab\tname"])
def test_a_model_name_must_be_one_short_word(model: str) -> None:
    with pytest.raises(ProviderConfigError):
        ProviderConfig.from_environment({MODEL_ENV: model})


# -- a request ------------------------------------------------------------------


def test_one_request_is_sent_to_the_configured_endpoint_with_the_key_in_one_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return sse(
            delta('{"title": '),
            delta('"Weights"}', finish="stop"),
            {"choices": [], "usage": {"prompt_tokens": 321, "completion_tokens": 12}},
            "[DONE]",
        )

    result = client_for(handler).complete(REQUEST)

    assert result.text == '{"title": "Weights"}'
    assert (result.prompt_tokens, result.completion_tokens) == (321, 12)
    assert result.usage_reported is True
    assert result.finish_reason == "stop"

    assert len(seen) == 1
    sent = seen[0]
    assert (sent.method, str(sent.url)) == ("POST", "https://aihubmix.com/v1/chat/completions")
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    assert sent.headers["user-agent"] == "Adle"
    body = json.loads(sent.content)
    assert body["model"] == "coding-kimi-k3-free"
    assert body["messages"] == [
        {"role": "system", "content": "You write lessons."},
        {"role": "user", "content": "Write about weights."},
    ]
    assert body["max_tokens"] == 2000
    assert body["stream"] is True
    # The documented model fixes its own sampling; nothing about it is sent.
    assert not {"temperature", "top_p", "presence_penalty", "frequency_penalty"} & set(body)
    assert body["response_format"] == {"type": "json_object"}
    # The key is in the header and nowhere else.
    assert KEY not in sent.content.decode()
    assert KEY not in str(sent.url)


def test_free_text_requests_do_not_ask_for_json() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return sse(delta("from manim import *", finish="stop"), "[DONE]")

    scene = ChatRequest(purpose="scene", system="s", user="u", max_output_tokens=10)
    result = client_for(handler).complete(scene)
    assert result.text == "from manim import *"
    assert "response_format" not in bodies[0]
    # No usage was reported: the caller will have to estimate.
    assert result.usage_reported is False


def test_a_server_that_does_not_stream_is_understood_too() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "whole answer"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )

    result = client_for(handler).complete(REQUEST)
    assert (result.text, result.finish_reason, result.usage_reported) == (
        "whole answer",
        "length",
        True,
    )


def test_thinking_and_keepalive_events_are_not_mistaken_for_the_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            ": keep-alive\n\n"
            'data: {"choices": [{"delta": {"reasoning_content": "let me think"}}]}\n\n'
            'data: {"choices": [{"delta": {"role": "assistant", "content": ""}}]}\n\n'
            'data: {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

    assert client_for(handler).complete(REQUEST).text == "answer"


def test_without_a_key_nothing_is_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may be made without a key")

    with pytest.raises(ProviderKeyMissingError) as raised:
        client_for(handler, key=None).complete(REQUEST)
    assert raised.value.code == "provider_key_missing"


@pytest.mark.parametrize(
    ("status", "error", "code"),
    [
        (401, ProviderKeyRejectedError, "provider_key_rejected"),
        (403, ProviderKeyRejectedError, "provider_key_rejected"),
        (400, ProviderRequestRefusedError, "provider_request_refused"),
        (404, ProviderRequestRefusedError, "provider_request_refused"),
        (422, ProviderRequestRefusedError, "provider_request_refused"),
        (500, ProviderUnavailableError, "provider_unavailable"),
        (503, ProviderUnavailableError, "provider_unavailable"),
    ],
)
def test_a_refusal_becomes_a_readable_error_that_quotes_nothing(
    status: int, error: type[Exception], code: str, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": f"bad key {KEY} for PRIVATE"}})

    with caplog.at_level(logging.DEBUG), pytest.raises(error) as raised:
        client_for(handler).complete(REQUEST)
    assert getattr(raised.value, "code", None) == code
    message = str(raised.value)
    assert KEY not in message
    assert "PRIVATE" not in message
    # Nothing the provider said, and nothing that was sent, reaches the log.
    assert KEY not in caplog.text
    assert "PRIVATE" not in caplog.text
    assert "Write about weights" not in caplog.text


def test_a_fault_at_the_provider_is_not_blamed_on_the_learners_connection() -> None:
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "do request failed"}})

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(ProviderUnavailableError) as at_provider:
        client_for(failing).complete(REQUEST)
    with pytest.raises(ProviderUnavailableError) as on_the_way:
        client_for(offline).complete(REQUEST)

    assert "on its side" in str(at_provider.value)
    assert "connection" not in str(at_provider.value)
    assert "could not be reached" in str(on_the_way.value)
    # One code for the interface either way: nothing arrived, try again later.
    assert at_provider.value.code == on_the_way.value.code == "provider_unavailable"


def test_a_redirect_is_not_followed_with_the_key() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://elsewhere.example/v1/chat"})

    with pytest.raises(ProviderUnavailableError):
        client_for(handler).complete(REQUEST)
    assert requests == ["https://aihubmix.com/v1/chat/completions"]


@pytest.mark.parametrize(
    ("header", "expected"),
    [("12", 12.0), ("0.5", 0.5), ("100000", 90.0), ("-3", 0.0), (None, None)],
)
def test_rate_limiting_reports_how_long_to_wait_within_reason(
    header: str | None, expected: float | None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"retry-after": header} if header is not None else {}
        return httpx.Response(429, headers=headers, json={"error": {"message": "slow down"}})

    with pytest.raises(ProviderRateLimitedError) as raised:
        client_for(handler).complete(REQUEST)
    assert raised.value.retry_after_seconds == expected
    assert raised.value.code == "provider_rate_limited"


def test_a_retry_after_date_is_ignored_rather_than_trusting_a_remote_clock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})

    with pytest.raises(ProviderRateLimitedError) as raised:
        client_for(handler).complete(REQUEST)
    assert raised.value.retry_after_seconds is None


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("cut")],
)
def test_network_trouble_is_one_recoverable_error(failure: Exception) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise failure

    with pytest.raises(ProviderUnavailableError):
        client_for(handler).complete(REQUEST)


@pytest.mark.parametrize(
    "response",
    [
        sse("this is not json", "[DONE]"),
        sse("[1, 2, 3]", "[DONE]"),
        sse("[DONE]"),
        httpx.Response(200, text="<html>gateway</html>"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    ],
    ids=["not json", "not an object", "nothing at all", "html", "no choice", "no text"],
)
def test_an_answer_that_cannot_be_read_is_reported_as_such(response: httpx.Response) -> None:
    with pytest.raises(ProviderBadResponseError):
        client_for(lambda request: response).complete(REQUEST)


def test_an_error_inside_the_stream_is_a_provider_failure() -> None:
    response = sse(delta("partial"), {"error": {"message": "upstream died"}})
    with pytest.raises(ProviderUnavailableError):
        client_for(lambda request: response).complete(REQUEST)


def test_an_answer_that_never_stops_is_cut_off() -> None:
    chunk = delta("x" * 50_000)
    response = sse(*([chunk] * 10))
    with pytest.raises(ProviderBadResponseError):
        client_for(lambda request: response).complete(REQUEST)


def test_a_request_can_be_abandoned_between_chunks() -> None:
    response = sse(delta("one"), delta("two"), delta("three"), "[DONE]")
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    with pytest.raises(RequestCancelledError):
        client_for(lambda request: response).complete(REQUEST, cancelled=cancelled)


def test_a_request_has_a_total_time_budget_however_steadily_it_drips() -> None:
    response = sse(*[delta("drip") for _ in range(50)], "[DONE]")
    now = 0.0

    def clock() -> float:
        nonlocal now
        now += 30.0  # half a minute passes between every look at the clock
        return now

    with pytest.raises(ProviderUnavailableError):
        client_for(lambda request: response, monotonic=clock).complete(REQUEST)
