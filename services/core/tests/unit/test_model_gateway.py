"""The gateway: quota, one request at a time, a record of everything sent."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from adle_core.application.model_gateway import ModelGateway, QuotaExhaustedError
from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import (
    ChatClient,
    ChatRequest,
    ProviderConfig,
    ProviderKeyMissingError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    RequestCancelledError,
)
from adle_core.generation.quota import QuotaLimits
from adle_core.infrastructure.orm import ModelUsage

KEY = "sk-test-0123456789abcdefghijklmnop"
START = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
REQUEST = ChatRequest(
    purpose="lesson", system="system " * 30, user="user " * 60, max_output_tokens=500
)

Handler = Callable[[httpx.Request], httpx.Response]


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = START
        self.slept = 0.0

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.now += timedelta(seconds=seconds)


def answer(text: str = "ok", usage: dict[str, int] | None = None) -> httpx.Response:
    events: list[dict[str, Any]] = [
        {"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]}
    ]
    if usage is not None:
        events.append({"choices": [], "usage": usage})
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


class Provider:
    """A scripted provider: answers from a list, then with a plain success."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        if not self.responses:
            return answer()
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def gateway_for(
    services: Services,
    provider: Handler,
    *,
    key: str | None = KEY,
    limits: QuotaLimits | None = None,
) -> tuple[ModelGateway, FakeTime]:
    vault = CredentialVault()
    if key:
        vault.set_api_key(key)
    fake = FakeTime()
    client = ChatClient(ProviderConfig(), vault, transport=httpx.MockTransport(provider))
    gateway = ModelGateway(
        services.database,
        client,
        limits=limits or QuotaLimits(),
        clock=fake.clock,
        sleep=fake.sleep,
    )
    return gateway, fake


def rows(services: Services) -> list[ModelUsage]:
    with services.database.session() as session:
        found = list(session.scalars(select(ModelUsage).order_by(ModelUsage.id)))
        session.expunge_all()
        return found


def test_a_request_is_answered_and_written_down_with_the_providers_own_count(
    services: Services,
) -> None:
    provider = Provider(answer("hello", {"prompt_tokens": 210, "completion_tokens": 7}))
    gateway, _ = gateway_for(services, provider)

    assert gateway.complete(REQUEST).text == "hello"

    (row,) = rows(services)
    assert (row.purpose, row.model, row.outcome) == ("lesson", "coding-kimi-k3-free", "ok")
    assert (row.prompt_tokens, row.completion_tokens, row.estimated) == (210, 7, False)
    usage = gateway.usage()
    assert (usage.requests_today, usage.tokens_today, usage.requests_last_minute) == (1, 217, 1)


def test_when_the_provider_reports_no_usage_the_count_is_an_estimate(services: Services) -> None:
    gateway, _ = gateway_for(services, Provider(answer("x" * 300)))
    gateway.complete(REQUEST)
    (row,) = rows(services)
    assert row.estimated is True
    assert row.prompt_tokens > 50
    assert row.completion_tokens >= 75


def test_without_a_key_nothing_is_sent_or_counted(services: Services) -> None:
    provider = Provider()
    gateway, _ = gateway_for(services, provider, key=None)
    assert gateway.has_key is False
    with pytest.raises(ProviderKeyMissingError):
        gateway.complete(REQUEST)
    assert provider.requests == 0
    assert rows(services) == []


def test_a_full_minute_is_waited_out_not_failed(services: Services) -> None:
    provider = Provider()
    gateway, fake = gateway_for(services, provider)
    waits: list[float] = []
    for _ in range(4):
        gateway.complete(REQUEST, on_wait=waits.append)
    assert waits == []
    assert fake.slept == 0

    gateway.complete(REQUEST, on_wait=waits.append)

    assert provider.requests == 5
    assert len(waits) == 1
    assert waits[0] == pytest.approx(60.0)
    # It waited as long as it said, and no longer than a moment more.
    assert 60.0 <= fake.slept <= 60.5


def test_the_daily_allowance_refuses_before_anything_is_sent(services: Services) -> None:
    provider = Provider()
    limits = QuotaLimits(requests_per_minute=10, requests_per_day=2, tokens_per_day=900_000)
    gateway, _ = gateway_for(services, provider, limits=limits)
    gateway.complete(REQUEST)
    gateway.complete(REQUEST)

    with pytest.raises(QuotaExhaustedError) as raised:
        gateway.complete(REQUEST)

    assert provider.requests == 2
    assert len(rows(services)) == 2
    error = raised.value
    assert error.code == "quota_exhausted"
    assert error.detail == {"resets_at": "2026-11-20T00:00:00+00:00", "limit": "requests"}
    assert "midnight UTC" in error.message


def test_the_token_allowance_counts_what_the_request_might_use(services: Services) -> None:
    provider = Provider()
    limits = QuotaLimits(requests_per_minute=10, requests_per_day=90, tokens_per_day=600)
    gateway, _ = gateway_for(services, provider, limits=limits)
    with pytest.raises(QuotaExhaustedError) as raised:
        gateway.complete(REQUEST)
    assert provider.requests == 0
    assert raised.value.detail["limit"] == "tokens"


def test_a_rate_limit_answer_is_waited_out_and_tried_once_more(services: Services) -> None:
    limited = httpx.Response(429, headers={"retry-after": "7"})
    provider = Provider(limited, answer("second time"))
    gateway, fake = gateway_for(services, provider)
    waits: list[float] = []

    result = gateway.complete(REQUEST, on_wait=waits.append)

    assert result.text == "second time"
    assert provider.requests == 2
    assert waits == [7.0]
    assert 7.0 <= fake.slept <= 7.5
    # Both attempts were sent, so both count.
    assert [row.outcome for row in rows(services)] == ["rate_limited", "ok"]


def test_a_second_rate_limit_answer_ends_it_there(services: Services) -> None:
    provider = Provider(httpx.Response(429), httpx.Response(429), answer("never reached"))
    gateway, fake = gateway_for(services, provider)

    with pytest.raises(ProviderRateLimitedError):
        gateway.complete(REQUEST)

    # No storm: exactly one retry, after a pause.
    assert provider.requests == 2
    assert fake.slept >= 20.0
    assert [row.outcome for row in rows(services)] == ["rate_limited", "rate_limited"]


@pytest.mark.parametrize(
    ("response", "outcome", "error"),
    [
        (httpx.Response(500), "unavailable", ProviderUnavailableError),
        (httpx.ConnectError("down"), "unavailable", ProviderUnavailableError),
        (httpx.Response(400), "refused", Exception),
        (httpx.Response(401), "refused", Exception),
        (httpx.Response(200, text="not an answer"), "unreadable", Exception),
    ],
)
def test_other_failures_are_recorded_and_never_retried(
    services: Services, response: httpx.Response | Exception, outcome: str, error: type[Exception]
) -> None:
    provider = Provider(response, answer("never reached"))
    gateway, fake = gateway_for(services, provider)

    with pytest.raises(error):
        gateway.complete(REQUEST)

    assert provider.requests == 1
    assert fake.slept == 0
    assert [row.outcome for row in rows(services)] == [outcome]
    # A request that was sent counts, whatever came back.
    assert gateway.usage().requests_today == 1


def test_cancelling_while_waiting_sends_nothing_more(services: Services) -> None:
    provider = Provider()
    gateway, fake = gateway_for(services, provider)
    for _ in range(4):
        gateway.complete(REQUEST)

    with pytest.raises(RequestCancelledError):
        gateway.complete(REQUEST, cancelled=lambda: fake.slept >= 3.0)

    assert provider.requests == 4
    assert fake.slept < 4.0


def test_cancelling_while_the_answer_arrives_is_recorded_as_such(services: Services) -> None:
    gateway, _ = gateway_for(services, Provider(answer("partial")))
    with pytest.raises(RequestCancelledError):
        gateway.complete(REQUEST, cancelled=lambda: True)
    assert [row.outcome for row in rows(services)] == ["cancelled"]


def test_only_one_request_is_in_flight_at_a_time(services: Services) -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    in_flight = 0
    most_at_once = 0
    guard = threading.Lock()

    def slow(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, most_at_once
        with guard:
            in_flight += 1
            most_at_once = max(most_at_once, in_flight)
        first_started.set()
        release_first.wait(5)
        with guard:
            in_flight -= 1
        return answer()

    gateway, _ = gateway_for(services, slow)
    threads = [threading.Thread(target=gateway.complete, args=(REQUEST,)) for _ in range(3)]
    for thread in threads:
        thread.start()
    assert first_started.wait(5)
    release_first.set()
    for thread in threads:
        thread.join(10)
    assert most_at_once == 1
    assert len(rows(services)) == 3


def test_usage_older_than_a_day_no_longer_counts(services: Services) -> None:
    gateway, fake = gateway_for(services, Provider())
    gateway.complete(REQUEST)
    fake.now += timedelta(days=1, minutes=1)
    usage = gateway.usage()
    assert (usage.requests_today, usage.requests_last_minute) == (0, 0)
    assert usage.resets_at == datetime(2026, 11, 21, tzinfo=UTC)


# -- through the API -----------------------------------------------------------


def test_the_interface_can_read_the_provider_and_the_local_estimate(client: TestClient) -> None:
    provider = client.get("/v1/provider").json()
    # Every provider there is, and where each kind of request would go, come with it
    # (test_provider_choice.py, test_provider_routing.py).
    provider.pop("providers")
    provider.pop("routes")
    assert provider.pop("selection") == "auto"
    assert provider == {
        "provider_id": "aihubmix",
        "display_name": "AIHubMix",
        "base_url": "https://aihubmix.com/v1",
        "model": "coding-kimi-k3-free",
        "model_name": "Coding Kimi K3 (free)",
        "key_configured": False,
    }
    usage = client.get("/v1/provider/usage").json()
    # AIHubMix publishes its limits, and Adle stays under them.
    assert (usage["provider_id"], usage["limits_published"]) == ("aihubmix", True)
    assert usage["requests_today"] == 0
    assert usage["tokens_today"] == 0
    # The daily allowance is the real default; the test fixture lifts the per-minute limit.
    assert (usage["requests_per_day"], usage["tokens_per_day"]) == (90, 900_000)
    assert usage["requests_per_minute"] >= 1
    assert usage["resets_at"].endswith(("Z", "+00:00"))
