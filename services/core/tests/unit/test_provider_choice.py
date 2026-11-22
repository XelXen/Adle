"""More than one provider: one chosen, whose key goes where, and which model answers.

Everything here is about a learner who chose one provider. What happens when they let
Adle use every provider they have a key for is in ``test_provider_routing.py``.

No request in this file leaves the process (ADR-021).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from adle_core.application.model_gateway import MODEL_REST, ModelGateway
from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault, SecretRedactionFilter
from adle_core.generation.provider import (
    AIHUBMIX,
    BASE_URL_ENV,
    ENDPOINTS_ENV,
    MODEL_ENV,
    NVIDIA,
    NVIDIA_LIMITS,
    ChatClient,
    ChatRequest,
    NoModelAnsweredError,
    ProviderCatalogue,
    ProviderConfigError,
    ProviderError,
    ProviderKeyMissingError,
    ProviderKeyRejectedError,
    ProviderModelUnavailableError,
    ProviderRateLimitedError,
    ProviderRequestRefusedError,
    ProviderUnavailableError,
    RequestCancelledError,
)
from adle_core.generation.quota import DEFAULT_LIMITS, QuotaLimits
from adle_core.infrastructure.orm import ModelUsage
from tests.support.model import CURRICULUM, FakeProvider

AIHUBMIX_KEY = "sk-test-aihubmix-0123456789abcdef"
NVIDIA_KEY = "nvapi-test-0123456789abcdefghijkl"
#: NVIDIA's models for a lesson (``REQUEST``), in the order they are asked (ADR-039).
FIRST, SECOND, THIRD = (model.id for model in NVIDIA.models_for("lesson"))
FIRST_NAME, SECOND_NAME, THIRD_NAME = (model.name for model in NVIDIA.models_for("lesson"))
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
AIHUBMIX_URL = "https://aihubmix.com/v1/chat/completions"
START = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
REQUEST = ChatRequest(
    purpose="lesson",
    system="Be brief.",
    user="Explain weights.",
    max_output_tokens=500,
    json_output=True,
)


def stream(text: str, *, usage: dict[str, int] | None = None, thinking: str = "") -> httpx.Response:
    """A streamed answer, with the model's thinking beside it the way NVIDIA sends it."""
    events: list[dict[str, Any]] = []
    if thinking:
        events.append({"choices": [{"delta": {"content": None, "reasoning_content": thinking}}]})
    events.append({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})
    if usage is not None:
        events.append({"choices": [], "usage": usage})
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


class Endpoint:
    """A provider scripted model by model: each answers, or is in the trouble it was given."""

    def __init__(self, **trouble: int | Exception) -> None:
        names = {"first": FIRST, "second": SECOND, "third": THIRD}
        self.trouble: dict[str, int | Exception] = {
            names[name]: what for name, what in trouble.items()
        }
        self.asked: list[str] = []
        self.bodies: list[dict[str, Any]] = []
        self.urls: list[str] = []
        self.keys: list[str | None] = []

    def recover(self, model: str) -> None:
        self.trouble.pop(model, None)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.asked.append(body["model"])
        self.bodies.append(body)
        self.urls.append(str(request.url))
        self.keys.append(request.headers.get("authorization"))
        trouble = self.trouble.get(body["model"])
        if isinstance(trouble, Exception):
            raise trouble
        if isinstance(trouble, int):
            return httpx.Response(trouble, text="404 page not found")
        return stream(f"written by {body['model']}")


class FakeTime:
    """A clock that only moves when something sleeps, or a test moves it."""

    def __init__(self) -> None:
        self.now = START
        self.slept = 0.0

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.now += timedelta(seconds=seconds)


def both_providers(
    services: Services,
    endpoint: Endpoint,
    *,
    limits: QuotaLimits | None = QuotaLimits(requests_per_minute=600),
) -> tuple[ModelGateway, FakeTime, CredentialVault]:
    """A gateway over both providers, a key for each, and NVIDIA chosen by the learner."""
    vault = CredentialVault()
    transport = httpx.MockTransport(endpoint)
    clients = [
        ChatClient(AIHUBMIX, vault, transport=transport),
        ChatClient(NVIDIA, vault, transport=transport),
    ]
    fake = FakeTime()
    gateway = ModelGateway(
        services.database, clients, limits=limits, clock=fake.clock, sleep=fake.sleep
    )
    vault.set_api_key(AIHUBMIX_KEY, "aihubmix")
    vault.set_api_key(NVIDIA_KEY, "nvidia")
    gateway.select("nvidia")
    return gateway, fake, vault


def rows(services: Services) -> list[ModelUsage]:
    with services.database.session() as session:
        found = list(session.scalars(select(ModelUsage).order_by(ModelUsage.id)))
        session.expunge_all()
        return found


# -- which providers there are ---------------------------------------------------------


def test_two_providers_are_offered_and_the_first_is_used_until_another_is_chosen() -> None:
    catalogue = ProviderCatalogue.from_environment({})
    assert [provider.provider_id for provider in catalogue.providers] == ["aihubmix", "nvidia"]
    assert catalogue.default.provider_id == "aihubmix"
    assert catalogue.get("nvidia") is NVIDIA
    assert catalogue.get("somewhere-else") is None


def test_each_kind_of_request_goes_to_the_nvidia_model_measured_to_do_it_best() -> None:
    assert NVIDIA.base_url == "https://integrate.api.nvidia.com/v1"
    ultra, super_, kimi, mistral = (
        "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "moonshotai/kimi-k3.1-pro",
        "mistralai/mistral-large-4-1t-a52b",
    )
    assert [model.id for model in NVIDIA.models] == [ultra, super_, kimi, mistral]
    orders = {
        purpose: [model.id for model in NVIDIA.models_for(purpose)]
        for purpose in ("ask", "check", "curriculum", "lesson", "scene")
    }
    # What the learner waits for goes to the quickest; Kimi, a model for code, draws the
    # pictures; a lesson goes to the model that wrote a usable one soonest (2026-11-21).
    assert orders == {
        "ask": [super_, ultra, kimi],
        "check": [super_, ultra],
        "curriculum": [ultra, super_, kimi, mistral],
        "lesson": [ultra, kimi, mistral],
        "scene": [kimi, ultra],
    }
    # AIHubMix's one model is asked for everything when it is the provider chosen.
    assert [model.id for model in AIHUBMIX.models_for("lesson")] == ["coding-kimi-k3-free"]
    # Limits NVIDIA does not publish are Adle's own, and are said to be.
    assert NVIDIA.limits is NVIDIA_LIMITS
    assert NVIDIA.limits_published is False
    assert AIHUBMIX.limits_published is True


def test_a_developers_single_endpoint_replaces_the_choice_and_says_so() -> None:
    catalogue = ProviderCatalogue.from_environment(
        {BASE_URL_ENV: "http://127.0.0.1:9000/v1", MODEL_ENV: "local-model"}
    )
    (only,) = catalogue.providers
    assert (only.provider_id, only.display_name) == ("custom", "Custom endpoint (127.0.0.1)")
    assert only.model == "local-model"


def test_known_providers_can_be_moved_and_then_say_where_they_are() -> None:
    catalogue = ProviderCatalogue.from_environment(
        {ENDPOINTS_ENV: json.dumps({"nvidia": "http://127.0.0.1:9100/v1/"})}
    )
    aihubmix, nvidia = catalogue.providers
    assert aihubmix is AIHUBMIX
    assert nvidia.provider_id == "nvidia"
    assert nvidia.base_url == "http://127.0.0.1:9100/v1"
    # Never silently somewhere else: the name carries the address.
    assert nvidia.display_name == "NVIDIA NIM (custom endpoint 127.0.0.1)"
    assert nvidia.models == NVIDIA.models


@pytest.mark.parametrize(
    "value",
    [
        "not json",
        '["nvidia"]',
        '{"openai": "https://api.example/v1"}',
        '{"nvidia": 12}',
        '{"nvidia": "http://example.com/v1"}',
        '{"nvidia": "https://user:secret@example.com/v1"}',
    ],
    ids=["not json", "a list", "unknown provider", "not an address", "plain http", "credentials"],
)
def test_a_list_of_endpoints_that_cannot_be_trusted_is_refused(value: str) -> None:
    with pytest.raises(ProviderConfigError):
        ProviderCatalogue.from_environment({ENDPOINTS_ENV: value})


# -- only what each model's reference lists is sent to it -------------------------------


def client_for(config: Any, endpoint: Any, *, keys: dict[str, str] | None = None) -> ChatClient:
    vault = CredentialVault()
    for provider_id, key in (keys or {"aihubmix": AIHUBMIX_KEY, "nvidia": NVIDIA_KEY}).items():
        vault.set_api_key(key, provider_id)
    return ChatClient(config, vault, transport=httpx.MockTransport(endpoint))


MESSAGES = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "Explain weights."},
]


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (
            0,
            # A lesson is asked for with the reasoning its reference lists as "none": a
            # lesson as a slideshow can be begun in seconds rather than minutes, and what
            # thinking caught is caught in drafts (ADR-049; ADR-048 had "medium").
            {
                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                "messages": MESSAGES,
                "max_tokens": 500,
                "stream": True,
                "reasoning_effort": "none",
            },
        ),
        (
            1,
            {
                "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
                "messages": MESSAGES,
                "max_tokens": 500,
                "stream": True,
            },
        ),
        (
            2,
            {
                "model": "moonshotai/kimi-k3.1-pro",
                "messages": MESSAGES,
                # Its thinking counts in the bound, so the bound has a floor.
                "max_tokens": 16_384,
                "stream": True,
                "stream_options": {"include_usage": True},
                # Documented, and not optional in practice: without it this model thinks
                # for minutes before it writes a word.
                "reasoning_effort": "low",
            },
        ),
        (
            3,
            {
                "model": "mistralai/mistral-large-4-1t-a52b",
                "messages": MESSAGES,
                "max_tokens": 16_384,
                "stream": True,
                # The value the endpoint accepts, which is not the one its reference
                # lists: "none" is refused, and without the field it thinks for minutes.
                "reasoning_effort": "low",
            },
        ),
    ],
    ids=["ultra", "super", "kimi", "mistral"],
)
def test_each_model_is_sent_exactly_the_fields_its_reference_lists(
    position: int, expected: dict[str, Any]
) -> None:
    endpoint = Endpoint()
    # JSON was asked for. None of these lists a way to ask, so none is sent one.
    client_for(NVIDIA, endpoint).complete(REQUEST, model=NVIDIA.models[position])
    assert endpoint.bodies == [expected]
    assert endpoint.urls == [NVIDIA_URL]


@pytest.mark.parametrize("purpose", ["ask", "curriculum", "check", "scene"])
def test_only_a_lesson_is_asked_for_with_less_reasoning(purpose: str) -> None:
    """Measured to help a lesson's words and not a course plan: every other kind of request
    is sent nothing, and the model reasons as its provider set it to."""
    endpoint = Endpoint()
    request = ChatRequest(purpose=purpose, system="s", user="u", max_output_tokens=500)
    client_for(NVIDIA, endpoint).complete(request, model=NVIDIA.models[0])
    assert "reasoning_effort" not in endpoint.bodies[0]


def test_a_request_that_asks_for_more_than_the_floor_keeps_what_it_asked_for() -> None:
    endpoint = Endpoint()
    large = ChatRequest(purpose="lesson", system="s", user="u", max_output_tokens=20_000)
    client_for(NVIDIA, endpoint).complete(large)
    assert endpoint.bodies[0]["max_tokens"] == 20_000


def test_a_model_of_another_provider_cannot_be_asked_through_this_one() -> None:
    endpoint = Endpoint()
    with pytest.raises(ValueError, match="does not belong"):
        client_for(AIHUBMIX, endpoint).complete(REQUEST, model=NVIDIA.models[0])
    assert endpoint.asked == []


# -- a key goes only where it was given for --------------------------------------------


def test_a_key_is_only_ever_sent_to_the_provider_it_was_given_for() -> None:
    endpoint = Endpoint()
    client_for(NVIDIA, endpoint).complete(REQUEST)
    client_for(AIHUBMIX, endpoint).complete(REQUEST)
    assert list(zip(endpoint.urls, endpoint.keys, strict=True)) == [
        (NVIDIA_URL, f"Bearer {NVIDIA_KEY}"),
        (AIHUBMIX_URL, f"Bearer {AIHUBMIX_KEY}"),
    ]


@pytest.mark.parametrize(
    ("config", "held"),
    [(NVIDIA, {"aihubmix": AIHUBMIX_KEY}), (AIHUBMIX, {"nvidia": NVIDIA_KEY})],
    ids=["nvidia without its key", "aihubmix without its key"],
)
def test_another_providers_key_never_stands_in_for_a_missing_one(
    config: Any, held: dict[str, str]
) -> None:
    endpoint = Endpoint()
    client = client_for(config, endpoint, keys=held)
    assert client.has_key is False
    with pytest.raises(ProviderKeyMissingError):
        client.complete(REQUEST)
    # Nothing was sent anywhere, with any key.
    assert endpoint.urls == []


def test_the_vault_keeps_a_key_for_each_provider_and_knows_what_was_chosen() -> None:
    vault = CredentialVault()
    # Until the learner says otherwise: every provider they give a key to.
    assert vault.selection == "auto"
    assert vault.default_provider_id == "aihubmix"
    assert vault.has_api_key is False

    vault.select("aihubmix")
    vault.set_api_key(NVIDIA_KEY, "nvidia")
    # A key for a provider that was not chosen does not make "there is a key" true.
    assert vault.has_api_key is False
    assert vault.has_key_for("nvidia") is True

    vault.select("nvidia")
    assert vault.has_api_key is True
    assert vault.api_key("nvidia") == NVIDIA_KEY
    assert vault.api_key("aihubmix") is None
    # Without a name, a key is the first provider's: never "whichever is in use".
    assert vault.api_key() is None

    vault.set_api_key(AIHUBMIX_KEY, "aihubmix")
    vault.clear_api_key("nvidia")
    assert vault.has_api_key is False
    assert vault.api_key("aihubmix") == AIHUBMIX_KEY
    assert vault.api_key() == AIHUBMIX_KEY


def test_no_key_of_any_provider_appears_in_the_vaults_description_or_in_a_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    vault = CredentialVault()
    vault.set_api_key(AIHUBMIX_KEY, "aihubmix")
    vault.set_api_key(NVIDIA_KEY, "nvidia")
    assert AIHUBMIX_KEY not in repr(vault)
    assert NVIDIA_KEY not in repr(vault)

    logger = logging.getLogger("adle_core.test.every_key")
    logger.addFilter(SecretRedactionFilter(vault))
    with caplog.at_level(logging.INFO, logger=logger.name):
        # The key of the provider that is not in use is scrubbed all the same.
        logger.info("sent Bearer %s and then Bearer %s", AIHUBMIX_KEY, NVIDIA_KEY)
    assert AIHUBMIX_KEY not in caplog.text
    assert NVIDIA_KEY not in caplog.text
    assert caplog.text.count("[redacted]") == 2


# -- what counts as a model being away --------------------------------------------------


@pytest.mark.parametrize(
    ("trouble", "kind"),
    [
        (404, "gone"),
        (410, "gone"),
        (500, "failing"),
        (503, "failing"),
        (httpx.ReadTimeout("silent"), "silent"),
    ],
    ids=["404", "410", "500", "503", "no answer in time"],
)
def test_a_model_that_is_gone_failing_or_silent_is_unavailable(
    trouble: int | Exception, kind: str
) -> None:
    with pytest.raises(ProviderModelUnavailableError) as raised:
        client_for(NVIDIA, Endpoint(first=trouble)).complete(REQUEST)
    assert raised.value.trouble == kind
    # One code for the interface, whatever the reason: nothing arrived, try again later.
    assert raised.value.code == "provider_unavailable"
    assert "Try again" in str(raised.value)
    assert NVIDIA_KEY not in str(raised.value)


def test_an_error_in_the_middle_of_an_answer_is_the_model_failing() -> None:
    body = (
        'data: {"choices": [{"delta": {"content": "partial"}}]}\n\n'
        'data: {"error": {"message": "upstream died"}}\n\n'
    )
    response = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)
    with pytest.raises(ProviderModelUnavailableError) as raised:
        client_for(NVIDIA, lambda request: response).complete(REQUEST)
    assert raised.value.trouble == "failing"


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("refused"), httpx.ConnectTimeout("slow"), httpx.RemoteProtocolError("cut")],
    ids=["refused", "no connection in time", "cut off"],
)
def test_not_reaching_the_provider_is_not_blamed_on_a_model(failure: Exception) -> None:
    with pytest.raises(ProviderUnavailableError) as raised:
        client_for(NVIDIA, Endpoint(first=failure)).complete(REQUEST)
    # Another model of the same provider is behind the same connection.
    assert not isinstance(raised.value, ProviderModelUnavailableError)
    assert "Couldn’t reach the AI provider" in str(raised.value)


def test_a_models_thinking_is_counted_and_never_taken_for_its_answer() -> None:
    response = stream('{"ready": true}', thinking="The user wants JSON. " * 10)
    result = client_for(NVIDIA, lambda request: response).complete(REQUEST)
    assert result.text == '{"ready": true}'
    assert result.thinking_characters == 210
    assert result.model_name == FIRST_NAME


def test_what_the_model_is_doing_is_reported_once_each_as_it_begins() -> None:
    seen: list[str] = []
    response = stream('{"ready": true}', thinking="The user wants JSON. " * 10)
    client_for(NVIDIA, lambda request: response).complete(REQUEST, on_stage=seen.append)
    assert seen == ["thinking", "writing"]


def test_a_model_that_does_not_think_is_only_ever_said_to_be_writing() -> None:
    seen: list[str] = []
    client_for(NVIDIA, lambda request: stream("plain")).complete(REQUEST, on_stage=seen.append)
    assert seen == ["writing"]


def test_thinking_again_while_writing_is_not_reported_as_going_back() -> None:
    events = [
        {"choices": [{"delta": {"reasoning_content": "first, "}}]},
        {"choices": [{"delta": {"content": "an answer"}}]},
        {"choices": [{"delta": {"reasoning_content": "on reflection, "}}]},
        {"choices": [{"delta": {"content": " in two parts"}, "finish_reason": "stop"}]},
    ]
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    response = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)
    seen: list[str] = []
    result = client_for(NVIDIA, lambda request: response).complete(REQUEST, on_stage=seen.append)
    assert seen == ["thinking", "writing"]
    assert result.text == "an answer in two parts"


#: What arrives while a model has not begun to answer: lines that keep the connection
#: open, and its thinking. Not one of them is a piece of the answer.
WAITING = (
    ": keep-alive\n\n" * 4
    + 'data: {"choices": [{"delta": {"content": null, "reasoning_content": "hm"}}]}\n\n' * 4
)


def waiting_response() -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=WAITING)


def test_a_request_can_be_stopped_before_the_model_has_begun_to_answer() -> None:
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    # The reading itself, without the waiting beside it (see the next test).
    client = client_for(NVIDIA, lambda request: waiting_response())
    with pytest.raises(RequestCancelledError):
        client._send(REQUEST, NVIDIA.models[0], cancelled, None)
    # Stopped at the second line that arrived: a line that only kept the connection open.
    assert checks == 2


def test_a_request_is_given_up_at_once_however_silent_the_provider_is() -> None:
    """A model can take a minute before its first word. "Stop" must not take a minute too."""
    reached, release = threading.Event(), threading.Event()
    stop = threading.Event()
    stages: list[str] = []

    def silent(request: httpx.Request) -> httpx.Response:
        reached.set()
        # Nothing at all comes back until the test lets it: no status line, no keep-alive.
        release.wait(30)
        return stream("too late", thinking="still thinking")

    client = client_for(NVIDIA, silent)
    failure: list[BaseException] = []

    def ask() -> None:
        try:
            client.complete(REQUEST, cancelled=stop.is_set, on_stage=stages.append)
        except BaseException as error:
            failure.append(error)

    asking = threading.Thread(target=ask)
    asking.start()
    try:
        assert reached.wait(20)
        began = time.monotonic()
        stop.set()
        asking.join(10)
        # Whoever asked is told straight away, while the provider is still saying nothing.
        assert not asking.is_alive()
        assert time.monotonic() - began < 5
        assert [type(error) for error in failure] == [RequestCancelledError]
    finally:
        release.set()
    # What arrives afterwards is dropped: nobody is told a model is thinking or writing.
    time.sleep(0.5)
    assert stages == []
    client.close()


def test_the_time_limit_runs_while_the_model_is_only_thinking() -> None:
    moments = iter([0.0, 1.0, NVIDIA.total_timeout_seconds + 1.0])
    vault = CredentialVault()
    vault.set_api_key(NVIDIA_KEY, "nvidia")
    client = ChatClient(
        NVIDIA,
        vault,
        transport=httpx.MockTransport(lambda request: waiting_response()),
        monotonic=lambda: next(moments),
    )
    with pytest.raises(ProviderModelUnavailableError) as raised:
        client.complete(REQUEST)
    # Given up on at the second line, long before any answer: the next model's turn.
    assert raised.value.trouble == "silent"
    assert "took too long to answer" in str(raised.value)


# -- the next model, when one is away -----------------------------------------------------


def test_when_the_first_model_is_away_the_next_is_asked_and_it_is_said(
    services: Services,
) -> None:
    endpoint = Endpoint(first=404)
    gateway, _, _ = both_providers(services, endpoint)
    told: list[tuple[str, ...]] = []

    result = gateway.complete(REQUEST, on_fallback=lambda *said: told.append(said))

    assert endpoint.asked == [FIRST, SECOND]
    assert result.text == f"written by {SECOND}"
    # Who answered, and for whom: never left unsaid.
    assert (result.model_name, result.instead_of) == (SECOND_NAME, FIRST_NAME)
    assert told == [(FIRST_NAME, SECOND_NAME, "gone")]
    # The same provider, the same address, the same key: only the model changed.
    assert set(endpoint.urls) == {NVIDIA_URL}
    assert set(endpoint.keys) == {f"Bearer {NVIDIA_KEY}"}
    # Both attempts were requests, and both are written down.
    assert [(row.provider, row.model, row.outcome) for row in rows(services)] == [
        ("nvidia", FIRST, "unavailable"),
        ("nvidia", SECOND, "ok"),
    ]


def test_the_first_model_answering_is_not_reported_as_a_stand_in(services: Services) -> None:
    endpoint = Endpoint()
    gateway, _, _ = both_providers(services, endpoint)
    told: list[tuple[str, ...]] = []
    result = gateway.complete(REQUEST, on_fallback=lambda *said: told.append(said))
    assert endpoint.asked == [FIRST]
    assert (result.model_name, result.instead_of) == (FIRST_NAME, "")
    assert told == []


def test_a_model_that_was_away_is_left_alone_for_a_while_and_then_asked_first_again(
    services: Services,
) -> None:
    endpoint = Endpoint(first=503)
    gateway, fake, _ = both_providers(services, endpoint)
    gateway.complete(REQUEST)
    assert endpoint.asked == [FIRST, SECOND]

    # The rest of the same lesson does not find out the same thing again.
    fake.now += timedelta(minutes=5)
    again = gateway.complete(REQUEST)
    assert endpoint.asked == [FIRST, SECOND, SECOND]
    assert again.instead_of == FIRST_NAME

    # Later, the model the learner was promised is the first one asked again.
    endpoint.recover(FIRST)
    fake.now += MODEL_REST
    later = gateway.complete(REQUEST)
    assert endpoint.asked[-1] == FIRST
    assert (later.model_name, later.instead_of) == (FIRST_NAME, "")


def test_when_the_first_two_are_away_the_third_is_asked(services: Services) -> None:
    endpoint = Endpoint(first=404, second=httpx.ReadTimeout("silent"))
    gateway, _, _ = both_providers(services, endpoint)
    told: list[tuple[str, ...]] = []
    result = gateway.complete(REQUEST, on_fallback=lambda *said: told.append(said))
    assert endpoint.asked == [FIRST, SECOND, THIRD]
    assert (result.model_name, result.instead_of) == (THIRD_NAME, FIRST_NAME)
    assert told == [(FIRST_NAME, SECOND_NAME, "gone"), (SECOND_NAME, THIRD_NAME, "silent")]


@pytest.mark.parametrize("status", [400, 422])
def test_a_model_that_will_not_take_its_request_is_passed_over_and_it_is_said_why(
    services: Services, status: int
) -> None:
    """Each model is sent a request of its own; a refusal of one says nothing of the next.

    Mistral Large 4 was seen to refuse a value its own reference lists (2026-11-20).
    """
    endpoint = Endpoint(first=status)
    gateway, _, _ = both_providers(services, endpoint)
    told: list[tuple[str, ...]] = []
    result = gateway.complete(REQUEST, on_fallback=lambda *said: told.append(said))
    assert endpoint.asked == [FIRST, SECOND]
    assert (result.model_name, result.instead_of) == (SECOND_NAME, FIRST_NAME)
    assert told == [(FIRST_NAME, SECOND_NAME, "refused")]
    assert [(row.model, row.outcome) for row in rows(services)] == [
        (FIRST, "refused"),
        (SECOND, "ok"),
    ]


def test_a_provider_with_one_model_still_reports_a_refused_request_as_refused(
    services: Services,
) -> None:
    vault = CredentialVault()
    vault.set_api_key(AIHUBMIX_KEY)
    client = ChatClient(
        AIHUBMIX, vault, transport=httpx.MockTransport(lambda request: httpx.Response(400))
    )
    gateway = ModelGateway(services.database, client, limits=QuotaLimits(requests_per_minute=600))
    with pytest.raises(ProviderRequestRefusedError) as raised:
        gateway.complete(REQUEST)
    assert raised.value.code == "provider_request_refused"


def test_when_no_model_answers_the_error_names_them_and_the_next_request_costs_one_attempt(
    services: Services,
) -> None:
    endpoint = Endpoint(first=404, second=500, third=httpx.ReadTimeout("silent"))
    gateway, fake, _ = both_providers(services, endpoint)

    with pytest.raises(NoModelAnsweredError) as raised:
        gateway.complete(REQUEST)
    assert endpoint.asked == [FIRST, SECOND, THIRD]
    message = str(raised.value)
    assert "None of NVIDIA NIM’s models answered" in message
    assert all(name in message for name in (FIRST_NAME, SECOND_NAME, THIRD_NAME))
    assert raised.value.code == "provider_unavailable"

    # Nothing is known to work. Trying again asks one model, not three: the one that
    # has been left alone longest.
    fake.now += timedelta(seconds=30)
    with pytest.raises(ProviderUnavailableError):
        gateway.complete(REQUEST)
    assert endpoint.asked == [FIRST, SECOND, THIRD, FIRST]

    # And a different one each time, so the first to come back is found.
    endpoint.recover(SECOND)
    fake.now += timedelta(seconds=30)
    assert gateway.complete(REQUEST).model_name == SECOND_NAME
    assert endpoint.asked == [FIRST, SECOND, THIRD, FIRST, SECOND]


@pytest.mark.parametrize(
    ("status", "error", "asked"),
    [
        (401, ProviderKeyRejectedError, 1),
        (403, ProviderKeyRejectedError, 1),
        # Told to slow down: waited out and asked once more, of the same model.
        (429, ProviderRateLimitedError, 2),
    ],
)
def test_a_refusal_that_is_about_the_account_is_not_taken_to_another_model(
    services: Services, status: int, error: type[ProviderError], asked: int
) -> None:
    endpoint = Endpoint(first=status)
    gateway, _, _ = both_providers(services, endpoint)
    told: list[tuple[str, ...]] = []
    with pytest.raises(error):
        gateway.complete(REQUEST, on_fallback=lambda *said: told.append(said))
    # The next model is behind the same key and the same account: it would say the same.
    assert endpoint.asked == [FIRST] * asked
    assert told == []


def test_not_reaching_the_provider_is_not_tried_on_another_model(services: Services) -> None:
    endpoint = Endpoint(first=httpx.ConnectError("offline"))
    gateway, _, _ = both_providers(services, endpoint)
    with pytest.raises(ProviderUnavailableError):
        gateway.complete(REQUEST)
    assert endpoint.asked == [FIRST]


def test_a_provider_with_one_model_fails_as_it_always_did(services: Services) -> None:
    requests: list[str] = []

    def failing(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(500, json={"error": {"message": "do request failed"}})

    vault = CredentialVault()
    vault.set_api_key(AIHUBMIX_KEY)
    client = ChatClient(AIHUBMIX, vault, transport=httpx.MockTransport(failing))
    gateway = ModelGateway(services.database, client, limits=QuotaLimits(requests_per_minute=600))
    with pytest.raises(ProviderUnavailableError) as raised:
        gateway.complete(REQUEST)
    assert not isinstance(raised.value, NoModelAnsweredError)
    assert "on its side" in str(raised.value)
    assert requests == [AIHUBMIX_URL]


# -- each provider is counted alone, against its own limits ---------------------------


def test_each_provider_has_its_own_count_and_its_own_limits(services: Services) -> None:
    endpoint = Endpoint()
    gateway, _, _ = both_providers(services, endpoint, limits=None)

    gateway.complete(REQUEST)
    gateway.complete(REQUEST)
    at_nvidia = gateway.usage()
    assert at_nvidia.requests_today == 2
    assert at_nvidia.limits == NVIDIA_LIMITS

    # What was sent to one provider is not held against the other.
    gateway.select("aihubmix")
    at_aihubmix = gateway.usage()
    assert at_aihubmix.requests_today == 0
    assert at_aihubmix.limits == DEFAULT_LIMITS

    gateway.complete(REQUEST)
    assert gateway.usage().requests_today == 1
    assert endpoint.urls == [NVIDIA_URL, NVIDIA_URL, AIHUBMIX_URL]
    assert [row.provider for row in rows(services)] == ["nvidia", "nvidia", "aihubmix"]


def test_the_gateway_only_changes_provider_to_one_it_was_given(services: Services) -> None:
    gateway, _, vault = both_providers(services, Endpoint())
    with pytest.raises(Exception, match="Unknown AI provider") as raised:
        gateway.select("somewhere-else")
    assert getattr(raised.value, "status_code", None) == 404
    assert vault.selection == "nvidia"


def test_where_no_count_comes_back_the_estimate_includes_what_the_model_thought(
    services: Services,
) -> None:
    answer = "x" * 300
    thinking = "y" * 600
    gateway, _, _ = both_providers(
        services,
        lambda request: stream(answer, thinking=thinking),  # type: ignore[arg-type]
    )
    gateway.complete(REQUEST)
    (row,) = rows(services)
    assert row.estimated is True
    # About three characters to a token, for the answer and for the thinking alike.
    assert row.completion_tokens >= (300 + 600) // 3


# -- through the API ---------------------------------------------------------------------


def choose(client: TestClient, selection: str) -> Any:
    return client.put("/v1/provider/selection", json={"selection": selection})


def topic_course(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/v1/courses",
        json={"title": "Calculus", "origin": "topic", "topic": "Limits and derivatives."},
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def add_concept(client: TestClient, course_id: str) -> str:
    curriculum = client.post(
        f"/v1/courses/{course_id}/concepts",
        json={
            "title": "Weights and bias",
            "summary": "How a neuron combines its inputs.",
            "objectives": ["Compute a weighted sum by hand.", "Say what a weight means."],
        },
    )
    assert curriculum.status_code in (200, 201), curriculum.text
    return str(curriculum.json()["concepts"][0]["id"])


def test_the_interface_is_told_every_provider_and_what_was_chosen(client: TestClient) -> None:
    status = client.get("/v1/provider").json()
    assert (status["provider_id"], status["model_name"]) == ("aihubmix", "Coding Kimi K3 (free)")
    # Nothing has been chosen yet, so no one provider is "the" one.
    assert status["selection"] == "auto"
    assert [
        (choice["provider_id"], choice["selected"], choice["key_configured"])
        for choice in status["providers"]
    ] == [("aihubmix", False, False), ("nvidia", False, False)]
    assert choose(client, "aihubmix").status_code == 204
    assert [choice["selected"] for choice in client.get("/v1/provider").json()["providers"]] == [
        True,
        False,
    ]
    nvidia = status["providers"][1]
    assert nvidia["display_name"] == "NVIDIA NIM"
    assert nvidia["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert [model["id"] for model in nvidia["models"]] == [model.id for model in NVIDIA.models]
    assert [model["name"] for model in nvidia["models"]] == [
        "Nemotron 3 Ultra",
        "Nemotron 3.5 Super",
        "Kimi K3.1 Pro",
        "Mistral Large 4",
    ]
    assert nvidia["limits_published"] is False


def test_choosing_a_provider_changes_what_is_in_use_and_nothing_else(client: TestClient) -> None:
    client.put("/v1/provider/credential", json={"api_key": AIHUBMIX_KEY})
    assert choose(client, "nvidia").status_code == 204

    status = client.get("/v1/provider").json()
    assert (status["provider_id"], status["display_name"]) == ("nvidia", "NVIDIA NIM")
    assert (status["selection"], status["model"]) == ("nvidia", FIRST)
    # The key that was there belongs to the other provider. This one has none yet.
    assert status["key_configured"] is False
    assert [
        (choice["provider_id"], choice["selected"], choice["key_configured"])
        for choice in status["providers"]
    ] == [("aihubmix", False, True), ("nvidia", True, False)]
    usage = client.get("/v1/provider/usage").json()
    assert (usage["provider_id"], usage["limits_published"]) == ("nvidia", False)

    # Choosing the one already in use is not an error.
    assert choose(client, "nvidia").status_code == 204
    assert choose(client, "aihubmix").status_code == 204
    assert client.get("/v1/provider").json()["key_configured"] is True


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"selection": "openai"}, 404),
        ({"selection": "NVIDIA"}, 422),
        ({"selection": "https://example.com/v1"}, 422),
        ({"selection": "nvidia", "base_url": "https://attacker.example"}, 422),
        # The name the field had before the choice could be "automatic".
        ({"provider_id": "nvidia"}, 422),
        ({}, 422),
    ],
)
def test_only_a_provider_adle_knows_can_be_chosen(
    client: TestClient, payload: dict[str, str], status: int
) -> None:
    assert choose(client, "aihubmix").status_code == 204
    assert client.put("/v1/provider/selection", json=payload).status_code == status
    after = client.get("/v1/provider").json()
    assert (after["selection"], after["provider_id"]) == ("aihubmix", "aihubmix")


def test_keys_are_handed_over_and_taken_back_one_provider_at_a_time(client: TestClient) -> None:
    def configured() -> dict[str, bool]:
        return {
            choice["provider_id"]: choice["key_configured"]
            for choice in client.get("/v1/provider").json()["providers"]
        }

    put = client.put(
        "/v1/provider/credential", json={"api_key": NVIDIA_KEY, "provider_id": "nvidia"}
    )
    assert put.status_code == 204
    assert configured() == {"aihubmix": False, "nvidia": True}
    # With no provider named, the key is for the first provider there is.
    assert client.put("/v1/provider/credential", json={"api_key": AIHUBMIX_KEY}).status_code == 204
    assert configured() == {"aihubmix": True, "nvidia": True}

    assert (
        client.delete("/v1/provider/credential", params={"provider_id": "nvidia"}).status_code
        == 204
    )
    assert configured() == {"aihubmix": True, "nvidia": False}

    # A key for a provider Adle does not know is not held for anyone.
    unknown = client.put(
        "/v1/provider/credential", json={"api_key": NVIDIA_KEY, "provider_id": "openai"}
    )
    assert unknown.status_code == 404
    assert (
        client.delete("/v1/provider/credential", params={"provider_id": "openai"}).status_code
        == 404
    )
    assert configured() == {"aihubmix": True, "nvidia": False}
    assert NVIDIA_KEY not in client.get("/v1/provider").text


def test_the_route_that_changes_provider_is_not_open_to_the_interface(services: Services) -> None:
    """The renderer allowlist is generated from this flag; losing it would expose the route."""
    from adle_core.api.app import create_app

    paths = create_app(services).openapi()["paths"]
    assert paths["/v1/provider/selection"]["put"]["x-adle-internal"] is True


def test_the_provider_is_not_changed_while_it_is_writing_something(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    client.put("/v1/provider/credential", json={"api_key": AIHUBMIX_KEY})
    assert choose(client, "aihubmix").status_code == 204
    course = topic_course(client)
    started, release = threading.Event(), threading.Event()

    def slow(body: dict[str, Any]) -> dict[str, Any]:
        started.set()
        release.wait(20)
        return CURRICULUM

    provider.queue(slow)
    job = client.post(f"/v1/courses/{course['id']}/curriculum/proposal")
    assert job.status_code == 202
    try:
        assert started.wait(20)
        refused = choose(client, "nvidia")
        assert refused.status_code == 409
        # It says what is happening, and what to do.
        message = refused.json()["error"]["message"]
        assert "Something is being written right now" in message
        assert "then change the provider" in message
        # Letting Adle choose is a change of provider like any other.
        assert choose(client, "auto").status_code == 409
        assert client.get("/v1/provider").json()["selection"] == "aihubmix"
    finally:
        release.set()
    assert services.jobs.wait(job.json()["id"], timeout=30).status == "succeeded"
    assert choose(client, "nvidia").status_code == 204


def test_a_lesson_through_nvidia_goes_only_there_and_says_which_model_wrote_it(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    client.put("/v1/provider/credential", json={"api_key": AIHUBMIX_KEY})
    client.put("/v1/provider/credential", json={"api_key": NVIDIA_KEY, "provider_id": "nvidia"})
    assert choose(client, "nvidia").status_code == 204
    concept = add_concept(client, topic_course(client)["id"])
    # The first model is not there when the lesson is asked for.
    provider.queue(httpx.Response(404, text="404 page not found"))

    response = client.post(f"/v1/concepts/{concept}/lessons")
    assert response.status_code == 202, response.text
    job = services.jobs.wait(response.json()["id"], timeout=30)
    assert job.status == "succeeded", job.error_message

    # Asked once of the model that was away, then everything of the next one.
    assert [body["model"] for body in provider.requests] == [FIRST, SECOND, SECOND, SECOND]
    assert set(provider.urls) == {NVIDIA_URL}
    assert set(provider.authorizations) == {f"Bearer {NVIDIA_KEY}"}
    note = f"{FIRST_NAME} wasn’t available, so {SECOND_NAME} wrote this instead."
    assert job.result["written_by"] == {
        "provider": "NVIDIA NIM",
        "models": [SECOND_NAME],
        "authors": [{"provider": "NVIDIA NIM", "model": SECOND_NAME}],
        "instead_of": FIRST_NAME,
        "note": note,
    }
    # And the learner is told, where the other things that did not go to plan are told.
    assert note in job.result["notes"]

    usage = client.get("/v1/provider/usage").json()
    assert (usage["provider_id"], usage["requests_today"]) == ("nvidia", 4)
    assert {row.provider for row in rows(services)} == {"nvidia"}


def test_a_long_wait_says_what_the_model_is_doing(
    client: TestClient,
    services: Services,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that thinks for minutes must not look like a job that has stalled."""
    # Suggested concepts have an order of their own (ADR-039).
    first, second = (model.name for model in NVIDIA.models_for("curriculum")[:2])
    said: list[str] = []
    details: list[dict[str, Any] | None] = []
    update = services.jobs._update

    def recording(job_id: str, **fields: Any) -> None:
        if "progress" in fields:
            message = fields["progress"]["message"]
            # The sentence is said again beside each title written: once is enough here.
            if not said or said[-1] != message:
                said.append(message)
            details.append(fields["progress"].get("detail"))
        update(job_id, **fields)

    monkeypatch.setattr(services.jobs, "_update", recording)
    client.put("/v1/provider/credential", json={"api_key": NVIDIA_KEY, "provider_id": "nvidia"})
    assert choose(client, "nvidia").status_code == 204
    course = topic_course(client)
    # The first model is away; the second thinks, and then writes.
    provider.queue(
        httpx.Response(404, text="404 page not found"),
        stream(json.dumps(CURRICULUM), thinking="Limits come first. " * 20),
    )

    response = client.post(f"/v1/courses/{course['id']}/curriculum/proposal")
    job = services.jobs.wait(response.json()["id"], timeout=30)
    assert job.status == "succeeded", job.error_message

    assert said == [
        "Suggesting concepts",
        f"{first} isn’t available right now. Asking {second} instead",
        f"Suggesting concepts: {second} is thinking",
        f"Suggesting concepts: {second} is writing",
        "Done",
    ]
    # Beside the sentences, what stage the work is at and which concepts have been
    # written so far: their titles, one more each time, and nothing else of the answer.
    stages = [detail.get("stage") for detail in details if detail]
    assert stages[:3] == ["waiting", "thinking", "writing"]
    outlines = [detail["outline"] for detail in details if detail and detail.get("outline")]
    titles = [concept["title"] for concept in CURRICULUM["concepts"]]
    assert outlines[-1] == titles
    # Here the answer arrives in one piece; piece by piece, see test_writing_outline.py.
    lengths = [len(outline) for outline in outlines]
    assert lengths == sorted(lengths)
    summaries = [concept["summary"] for concept in CURRICULUM["concepts"]]
    assert not any(summary in str(details) for summary in summaries)


def test_what_the_first_model_wrote_carries_no_note(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    client.put("/v1/provider/credential", json={"api_key": AIHUBMIX_KEY})
    course = topic_course(client)
    response = client.post(f"/v1/courses/{course['id']}/curriculum/proposal")
    job = services.jobs.wait(response.json()["id"], timeout=30)
    assert job.status == "succeeded", job.error_message
    assert job.result["written_by"] == {
        "provider": "AIHubMix",
        "models": ["Coding Kimi K3 (free)"],
        "authors": [{"provider": "AIHubMix", "model": "Coding Kimi K3 (free)"}],
        "instead_of": "",
        "note": "",
    }
    assert set(provider.urls) == {AIHUBMIX_URL}
