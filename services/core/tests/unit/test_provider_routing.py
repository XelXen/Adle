"""Every provider the learner has a key for, each used for what it is good at (ADR-023,
ADR-039).

The rules are pure (``generation.routing``); the gateway applies them to real counts and
real failures. No request in this file leaves the process.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from adle_core.application.model_gateway import (
    ACCOUNT_REST,
    PROVIDER_REST,
    ModelGateway,
    QuotaExhaustedError,
)
from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import (
    AIHUBMIX,
    NVIDIA,
    ChatClient,
    ChatRequest,
    ProviderError,
    ProviderKeyMissingError,
    ProviderKeyRejectedError,
    RequestCancelledError,
)
from adle_core.generation.quota import QuotaLimits
from adle_core.generation.routing import AUTOMATIC, PURPOSES, Standing, plan
from adle_core.infrastructure.orm import ModelUsage
from tests.support.model import FakeProvider

AIHUBMIX_KEY = "sk-test-aihubmix-0123456789abcdef"
NVIDIA_KEY = "nvapi-test-0123456789abcdefghijkl"
AIHUBMIX_URL = "https://aihubmix.com/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
START = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
BOTH = "AIHubMix, then NVIDIA NIM if needed"


def coder(**changes: Any) -> Standing:
    """A provider like AIHubMix: its model is made for code, so it draws the pictures."""
    values: dict[str, Any] = {
        "provider_id": "aihubmix",
        "name": "AIHubMix",
        "has_key": True,
        "first_for": frozenset({"scene"}),
    }
    return Standing(**{**values, **changes})


def writer(**changes: Any) -> Standing:
    """A provider like NVIDIA NIM: it writes everything but the pictures."""
    values: dict[str, Any] = {
        "provider_id": "nvidia",
        "name": "NVIDIA NIM",
        "has_key": True,
        "first_for": frozenset(PURPOSES) - {"scene"},
    }
    return Standing(**{**values, **changes})


# -- the rules -----------------------------------------------------------------------------


@pytest.mark.parametrize("purpose", ["ask", "curriculum", "lesson", "scene", "check"])
def test_one_provider_chosen_is_the_whole_plan_whatever_has_happened_to_it(purpose: str) -> None:
    standings = [coder(), writer(has_key=False, spent=True, resting=True)]
    found = plan(purpose, "nvidia", standings)
    assert found.provider_ids == ("nvidia",)
    assert (found.automatic, found.reason, found.sentence) == (False, "", "NVIDIA NIM")


def test_pictures_go_first_to_the_provider_whose_model_is_made_for_code() -> None:
    # However much of its day is gone, as long as something is left: it is kept for these.
    found = plan("scene", AUTOMATIC, [coder(used=0.97), writer()])
    assert found.provider_ids == ("aihubmix", "nvidia")
    assert found.automatic is True
    assert found.sentence == BOTH
    assert found.reason == "AIHubMix draws the pictures: its model is made for code."


@pytest.mark.parametrize("purpose", ["ask", "curriculum", "lesson", "check"])
def test_everything_else_goes_first_to_the_other_and_the_coder_is_kept_for_pictures(
    purpose: str,
) -> None:
    found = plan(purpose, AUTOMATIC, [coder(), writer()])
    # The one kept for pictures is still there to fall back on.
    assert found.provider_ids == ("nvidia", "aihubmix")
    assert found.sentence == "NVIDIA NIM, then AIHubMix if needed"
    assert found.reason == "NVIDIA NIM writes this, and AIHubMix is kept for the pictures."


def test_with_no_preference_between_them_the_first_listed_is_first() -> None:
    every = frozenset(PURPOSES)
    found = plan("lesson", AUTOMATIC, [coder(first_for=every), writer(first_for=every)])
    assert found.provider_ids == ("aihubmix", "nvidia")
    assert found.reason == ""


def test_a_provider_with_nothing_left_today_is_not_in_the_plan_while_another_is() -> None:
    found = plan("scene", AUTOMATIC, [coder(spent=True, used=1.0), writer()])
    assert found.provider_ids == ("nvidia",)
    assert found.sentence == "NVIDIA NIM"
    assert found.reason == "AIHubMix has no allowance left today."


def test_a_provider_that_just_failed_is_asked_second_not_dropped() -> None:
    found = plan("scene", AUTOMATIC, [coder(resting=True), writer()])
    assert found.provider_ids == ("nvidia", "aihubmix")
    assert found.reason == "AIHubMix couldn’t answer earlier, so it’s paused for now."
    # And when both failed a moment ago there is still a plan.
    assert plan("ask", AUTOMATIC, [coder(resting=True), writer(resting=True)]).provider_ids


def test_when_every_provider_is_spent_the_first_says_so() -> None:
    found = plan("lesson", AUTOMATIC, [coder(spent=True), writer(spent=True)])
    assert found.provider_ids == ("aihubmix",)
    assert found.reason == ""


def test_only_providers_with_a_key_are_ever_planned() -> None:
    assert plan("ask", AUTOMATIC, [coder(has_key=False), writer()]).provider_ids == ("nvidia",)
    assert plan("lesson", AUTOMATIC, [coder(), writer(has_key=False)]).provider_ids == ("aihubmix",)
    # With no key anywhere the first provider is named, so the refusal can say whose key.
    nobody = plan("lesson", AUTOMATIC, [coder(has_key=False), writer(has_key=False)])
    assert nobody.provider_ids == ("aihubmix",)
    assert nobody.automatic is True


def test_a_choice_adle_does_not_know_is_treated_as_automatic() -> None:
    assert plan("ask", "somewhere-else", [coder(), writer()]).automatic is True


_standing = st.builds(
    Standing,
    provider_id=st.sampled_from(["a", "b", "c", "d"]),
    name=st.sampled_from(["A", "B", "C", "D"]),
    has_key=st.booleans(),
    first_for=st.frozensets(st.sampled_from(PURPOSES)),
    used=st.floats(min_value=0, max_value=1.5),
    spent=st.booleans(),
    resting=st.booleans(),
)


@given(
    purpose=st.sampled_from(["ask", "curriculum", "lesson", "scene", "check"]),
    standings=st.lists(_standing, min_size=1, max_size=4, unique_by=lambda item: item.provider_id),
    selection=st.sampled_from([AUTOMATIC, "a", "b", "zzz"]),
)
def test_a_plan_never_sends_anything_where_the_learner_did_not_agree(
    purpose: str, standings: list[Standing], selection: str
) -> None:
    found = plan(purpose, selection, standings)
    by_id = {item.provider_id: item for item in standings}
    assert found.provider_ids, "there is always someone to name"
    assert len(set(found.provider_ids)) == len(found.provider_ids)
    assert set(found.provider_ids) <= set(by_id)
    assert [by_id[name].name for name in found.provider_ids] == list(found.names)
    if selection in by_id:
        # One provider chosen: that one, alone, and never a stand-in.
        assert found.provider_ids == (selection,)
        assert found.automatic is False
        return
    keyed = {item.provider_id for item in standings if item.has_key}
    if keyed:
        # A provider without a key of its own is never asked.
        assert set(found.provider_ids) <= keyed
        usable = {name for name in keyed if not by_id[name].spent}
        if usable:
            # Nothing that can still be asked today is left out, and nothing spent is in.
            assert set(found.provider_ids) == usable
    else:
        assert len(found.provider_ids) == 1


# -- the gateway, with both providers and the learner letting Adle choose -------------------


class Fleet:
    """Both providers behind one transport. Each answers, or fails as it was told to."""

    def __init__(self) -> None:
        self.failing: dict[str, int | Exception] = {}
        self.calls: list[tuple[str, str | None]] = []
        self.hold: threading.Event | None = None
        self.entered = threading.Event()

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append((url, request.headers.get("authorization")))
        trouble = self.failing.get(url)
        if isinstance(trouble, Exception):
            raise trouble
        if isinstance(trouble, int):
            return httpx.Response(trouble, text="no")
        if self.hold is not None:
            self.entered.set()
            self.hold.wait(20)
        event = {"choices": [{"delta": {"content": "ready"}, "finish_reason": "stop"}]}
        body = f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def automatic(
    services: Services,
    fleet: Fleet,
    *,
    keys: tuple[str, ...] = ("aihubmix", "nvidia"),
    limits: QuotaLimits | None = QuotaLimits(requests_per_minute=600),
) -> tuple[ModelGateway, Clock, CredentialVault]:
    """A gateway over both providers with the learner's choice left at "automatic"."""
    vault = CredentialVault()
    transport = httpx.MockTransport(fleet)
    clients = [
        ChatClient(AIHUBMIX, vault, transport=transport),
        ChatClient(NVIDIA, vault, transport=transport),
    ]
    clock = Clock()
    gateway = ModelGateway(
        services.database, clients, limits=limits, clock=clock.clock, sleep=clock.sleep
    )
    if "aihubmix" in keys:
        vault.set_api_key(AIHUBMIX_KEY, "aihubmix")
    if "nvidia" in keys:
        vault.set_api_key(NVIDIA_KEY, "nvidia")
    return gateway, clock, vault


def request(purpose: str) -> ChatRequest:
    return ChatRequest(purpose=purpose, system="Be brief.", user="Hello.", max_output_tokens=200)


def spend(services: Services, provider_id: str, count: int, when: datetime = START) -> None:
    """Record requests that were sent earlier today."""
    with services.database.session() as session:
        for _ in range(count):
            session.add(
                ModelUsage(
                    started_at=when - timedelta(hours=1),
                    provider=provider_id,
                    purpose="lesson",
                    model="m",
                    prompt_tokens=10,
                    completion_tokens=10,
                    estimated=True,
                    outcome="ok",
                )
            )


def test_with_both_keys_each_kind_of_request_goes_where_it_is_best_served(
    services: Services,
) -> None:
    fleet = Fleet()
    gateway, _, _ = automatic(services, fleet)
    assert gateway.selection == AUTOMATIC
    assert gateway.has_key is True

    answer = gateway.complete(request("ask"))
    assert (answer.provider_name, answer.instead_of_provider) == ("NVIDIA NIM", "")
    gateway.complete(request("curriculum"))
    gateway.complete(request("lesson"))
    assert gateway.complete(request("scene")).provider_name == "AIHubMix"
    assert fleet.urls == [NVIDIA_URL, NVIDIA_URL, NVIDIA_URL, AIHUBMIX_URL]

    # However much of its day is gone, the pictures stay with the model made for code.
    limits = gateway.limits_for(AIHUBMIX)
    spend(services, "aihubmix", limits.requests_per_day // 2)
    assert gateway.complete(request("scene")).provider_name == "AIHubMix"
    assert gateway.complete(request("lesson")).provider_name == "NVIDIA NIM"


def test_a_key_still_only_ever_goes_to_the_provider_it_was_given_for(services: Services) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = 500
    gateway, _, _ = automatic(services, fleet)
    gateway.complete(request("scene"))
    gateway.complete(request("lesson"))
    assert dict(fleet.calls) == {
        AIHUBMIX_URL: f"Bearer {AIHUBMIX_KEY}",
        NVIDIA_URL: f"Bearer {NVIDIA_KEY}",
    }


def test_when_the_first_provider_cannot_answer_the_next_is_asked_and_it_is_said(
    services: Services,
) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = httpx.ConnectError("no route")
    gateway, clock, _ = automatic(services, fleet)
    said: list[tuple[str, str, str]] = []

    answer = gateway.complete(
        request("scene"), on_fallback=lambda *told: said.append((told[0], told[1], told[2]))
    )
    assert said == [("AIHubMix", "NVIDIA NIM", "unreachable")]
    assert (answer.provider_name, answer.instead_of_provider) == ("NVIDIA NIM", "AIHubMix")
    assert fleet.urls == [AIHUBMIX_URL, NVIDIA_URL]

    # For a while the one that failed is asked second, so a lesson does not keep finding
    # out the same thing; then it is first again.
    assert gateway.plan("scene").provider_ids == ("nvidia", "aihubmix")
    assert (
        gateway.plan("scene").reason == "AIHubMix couldn’t answer earlier, so it’s paused for now."
    )
    fleet.failing.clear()
    assert gateway.complete(request("scene")).provider_name == "NVIDIA NIM"
    clock.now += PROVIDER_REST + timedelta(seconds=1)
    assert gateway.plan("scene").provider_ids == ("aihubmix", "nvidia")
    assert gateway.complete(request("scene")).instead_of_provider == ""


@pytest.mark.parametrize(
    ("status", "why"),
    [(401, "key_rejected"), (500, "failing"), (429, "rate_limited")],
)
def test_whatever_stops_the_first_provider_the_reason_has_words(
    services: Services, status: int, why: str
) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = status
    gateway, _, _ = automatic(services, fleet)
    said: list[str] = []
    answer = gateway.complete(request("scene"), on_fallback=lambda *told: said.append(told[2]))
    assert said == [why]
    assert answer.provider_name == "NVIDIA NIM"


def test_an_account_that_is_refusing_is_left_alone_until_its_key_changes(
    services: Services,
) -> None:
    """Each try at an account that says no can be one of a handful it allows."""
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = 401
    gateway, clock, vault = automatic(services, fleet)

    assert gateway.complete(request("scene")).instead_of_provider == "AIHubMix"
    # Ten minutes is how long a provider that stumbled is asked second. Not this one.
    clock.now += PROVIDER_REST + timedelta(minutes=1)
    assert gateway.plan("scene").provider_ids == ("nvidia", "aihubmix")
    gateway.complete(request("scene"))
    assert fleet.urls.count(AIHUBMIX_URL) == 1

    # A new key is a new start, straight away.
    fleet.failing.clear()
    vault.set_api_key("sk-test-another-0123456789abcdef", "aihubmix")
    gateway.forget_trouble("aihubmix")
    assert gateway.plan("scene").provider_ids == ("aihubmix", "nvidia")
    assert gateway.complete(request("scene")).provider_name == "AIHubMix"

    # And without one, it is asked first again after some hours.
    fleet.failing[AIHUBMIX_URL] = 401
    gateway.complete(request("scene"))
    clock.now += ACCOUNT_REST + timedelta(minutes=1)
    assert gateway.plan("scene").provider_ids == ("aihubmix", "nvidia")


def test_a_check_that_fails_is_remembered_by_what_is_asked_next(services: Services) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = 401
    gateway, _, _ = automatic(services, fleet)
    with pytest.raises(ProviderKeyRejectedError):
        gateway.complete(request("check"), provider_id="aihubmix")
    # The question that follows does not spend another try finding out the same thing.
    assert gateway.plan("scene").provider_ids == ("nvidia", "aihubmix")
    assert gateway.complete(request("scene")).instead_of_provider == ""
    assert fleet.urls == [AIHUBMIX_URL, NVIDIA_URL]


def test_an_allowance_that_is_used_up_moves_the_request_on_without_a_rest(
    services: Services,
) -> None:
    fleet = Fleet()
    gateway, _, _ = automatic(services, fleet, limits=None)
    limits = gateway.limits_for(AIHUBMIX)
    spend(services, "aihubmix", limits.requests_per_day)
    # It is not even in the plan: nothing is sent to it, and nothing has to fail first.
    assert gateway.plan("scene").provider_ids == ("nvidia",)
    answer = gateway.complete(request("scene"))
    assert (answer.provider_name, answer.instead_of_provider) == ("NVIDIA NIM", "")
    assert fleet.urls == [NVIDIA_URL]


def test_when_the_last_provider_in_the_plan_fails_too_its_failure_is_the_answer(
    services: Services,
) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = 500
    fleet.failing[NVIDIA_URL] = 401
    gateway, _, _ = automatic(services, fleet)
    with pytest.raises(ProviderKeyRejectedError):
        gateway.complete(request("scene"))
    assert fleet.urls[0] == AIHUBMIX_URL
    assert fleet.urls[-1] == NVIDIA_URL


def test_with_one_key_automatic_is_that_provider_and_the_other_is_never_contacted(
    services: Services,
) -> None:
    fleet = Fleet()
    fleet.failing[NVIDIA_URL] = 500
    gateway, _, _ = automatic(services, fleet, keys=("nvidia",))
    assert gateway.plan("ask").sentence == "NVIDIA NIM"
    with pytest.raises(ProviderError):
        gateway.complete(request("ask"))
    assert set(fleet.urls) == {NVIDIA_URL}


def test_with_one_provider_chosen_its_failure_is_never_taken_elsewhere(services: Services) -> None:
    fleet = Fleet()
    fleet.failing[AIHUBMIX_URL] = 500
    gateway, _, _ = automatic(services, fleet)
    gateway.select("aihubmix")
    with pytest.raises(ProviderError):
        gateway.complete(request("ask"))
    assert set(fleet.urls) == {AIHUBMIX_URL}
    # And an allowance that is used up is not a reason either.
    fleet.failing.clear()
    spend(services, "aihubmix", gateway.limits_for(AIHUBMIX).requests_per_day)
    with pytest.raises(QuotaExhaustedError):
        gateway.complete(request("lesson"))
    assert set(fleet.urls) == {AIHUBMIX_URL}


def test_no_key_anywhere_is_refused_before_anything_is_sent(services: Services) -> None:
    fleet = Fleet()
    gateway, _, _ = automatic(services, fleet, keys=())
    assert gateway.has_key is False
    with pytest.raises(ProviderKeyMissingError):
        gateway.complete(request("lesson"))
    assert fleet.calls == []


def test_one_provider_can_be_asked_by_name_whatever_the_plan_would_be(services: Services) -> None:
    fleet = Fleet()
    gateway, _, _ = automatic(services, fleet)
    answer = gateway.complete(request("check"), provider_id="nvidia")
    assert (answer.provider_name, fleet.urls) == ("NVIDIA NIM", [NVIDIA_URL])
    fleet.failing[NVIDIA_URL] = 500
    # By name means that one and no other: there is no stand-in.
    with pytest.raises(ProviderError):
        gateway.complete(request("check"), provider_id="nvidia")
    assert AIHUBMIX_URL not in fleet.urls
    with pytest.raises(Exception, match="Unknown AI provider"):
        gateway.complete(request("check"), provider_id="openai")


def test_one_request_at_a_time_at_each_provider_and_the_other_is_not_held_up(
    services: Services,
) -> None:
    fleet = Fleet()
    fleet.hold = threading.Event()
    gateway, _, _ = automatic(services, fleet)
    first: list[str] = []
    worker = threading.Thread(
        target=lambda: first.append(gateway.complete(request("scene")).provider_name)
    )
    worker.start()
    try:
        assert fleet.entered.wait(20)
        # AIHubMix is in the middle of an answer. A second request there waits its turn,
        # says so, and can be given up.
        waited_for: list[str] = []
        stop = threading.Event()

        def cancelled() -> bool:
            return stop.is_set()

        def busy(name: str) -> None:
            waited_for.append(name)
            stop.set()

        with pytest.raises(RequestCancelledError):
            gateway.complete(request("scene"), cancelled=cancelled, on_busy=busy)
        assert waited_for == ["AIHubMix"]
        assert fleet.urls == [AIHUBMIX_URL]
    finally:
        hold, fleet.hold = fleet.hold, None
        hold.set()
        worker.join(20)
    assert first == ["AIHubMix"]
    # Nothing was left locked behind the request that was given up.
    assert gateway.complete(request("scene")).provider_name == "AIHubMix"


def test_what_to_expect_is_what_is_usual_until_it_has_been_measured_here(
    services: Services,
) -> None:
    gateway, _, _ = automatic(services, Fleet())
    assert gateway.seconds_for("nvidia", "lesson") == (NVIDIA.typical.lesson, False)
    assert gateway.seconds_for("aihubmix", "ask") == (AIHUBMIX.typical.ask, False)
    with services.database.session() as session:
        for seconds in (40.0, 90.0, 50.0):
            session.add(
                ModelUsage(
                    started_at=START,
                    provider="nvidia",
                    purpose="lesson",
                    model="m",
                    prompt_tokens=1,
                    completion_tokens=1,
                    estimated=True,
                    outcome="ok",
                    seconds=seconds,
                )
            )
        # One that failed, and one too quick to be a real answer, say nothing.
        session.add(
            ModelUsage(
                started_at=START,
                provider="nvidia",
                purpose="lesson",
                model="m",
                prompt_tokens=1,
                completion_tokens=0,
                estimated=True,
                outcome="unavailable",
                seconds=999.0,
            )
        )
    assert gateway.seconds_for("nvidia", "lesson") == (50, True)
    # Each provider and each kind of request is measured alone.
    assert gateway.seconds_for("aihubmix", "lesson") == (AIHUBMIX.typical.lesson, False)
    assert gateway.seconds_for("nvidia", "scene") == (NVIDIA.typical.scene, False)


def test_how_long_an_answer_took_is_kept_with_it(services: Services) -> None:
    gateway, _, _ = automatic(services, Fleet())
    gateway.complete(request("ask"))
    with services.database.read() as session:
        row = session.query(ModelUsage).one()
        assert (row.outcome, row.purpose) == ("ok", "ask")
        assert row.seconds is not None
        assert row.seconds >= 0


# -- through the API -----------------------------------------------------------------------


def choose(client: TestClient, selection: str) -> int:
    return client.put("/v1/provider/selection", json={"selection": selection}).status_code


def give_keys(client: TestClient, *providers: str) -> None:
    keys = {"aihubmix": AIHUBMIX_KEY, "nvidia": NVIDIA_KEY}
    for name in providers:
        response = client.put(
            "/v1/provider/credential", json={"api_key": keys[name], "provider_id": name}
        )
        assert response.status_code == 204


def test_the_interface_is_told_where_each_kind_of_request_would_go(client: TestClient) -> None:
    before = client.get("/v1/provider").json()
    assert (before["selection"], before["key_configured"]) == ("auto", False)
    assert before["routes"]["lesson"]["sentence"] == "AIHubMix"
    assert [choice["in_use"] for choice in before["providers"]] == [False, False]

    give_keys(client, "nvidia")
    one = client.get("/v1/provider").json()
    # One key: automatic is simply that provider.
    assert one["key_configured"] is True
    assert (one["provider_id"], one["routes"]["ask"]["sentence"]) == ("nvidia", "NVIDIA NIM")
    assert [choice["in_use"] for choice in one["providers"]] == [False, True]

    give_keys(client, "aihubmix")
    both = client.get("/v1/provider").json()
    assert both["selection"] == "auto"
    for work in ("ask", "curriculum", "lesson"):
        route = both["routes"][work]
        assert route["provider_ids"] == ["nvidia", "aihubmix"]
        assert route["sentence"] == "NVIDIA NIM, then AIHubMix if needed"
        assert route["reason"]
        assert route["model_name"] == NVIDIA.models_for(work)[0].name
        assert (route["wait_seconds"] > 0, route["wait_measured"]) == (True, False)
    pictures = both["routes"]["scene"]
    assert pictures["provider_ids"] == ["aihubmix", "nvidia"]
    assert (pictures["sentence"], pictures["model_name"]) == (BOTH, "Coding Kimi K3 (free)")
    # A lesson is long to write; a question is one short answer.
    assert both["routes"]["lesson"]["wait_seconds"] > both["routes"]["ask"]["wait_seconds"]
    assert [(choice["in_use"], choice["first_for"]) for choice in both["providers"]] == [
        (True, ["scene"]),
        (True, ["ask", "check", "curriculum", "film", "lesson", "read", "storyboard"]),
    ]
    # A film's chapters go to NVIDIA, whose model for code writes them, and AIHubMix's small
    # allowance is kept for the pictures of lessons (ADR-065).
    film = both["routes"]["film"]
    assert film["provider_ids"] == ["nvidia", "aihubmix"]
    assert film["model_name"] == "Kimi K3.1 Pro"
    assert film["wait_seconds"] > both["routes"]["lesson"]["wait_seconds"]
    # Pages that are pictures go to NVIDIA alone: AIHubMix's model is not sent one (ADR-060).
    assert both["routes"]["read"]["provider_ids"] == ["nvidia"]
    # So do a film's pictures, to be looked over by the model that reads them (ADR-066).
    storyboard = both["routes"]["storyboard"]
    assert storyboard["provider_ids"] == ["nvidia"]
    assert (storyboard["sentence"], storyboard["model_name"]) == (
        "NVIDIA NIM",
        "Nemotron 3.5 Super",
    )
    assert storyboard["wait_seconds"] > both["routes"]["ask"]["wait_seconds"]
    assert [choice["reads_pictures"] for choice in both["providers"]] == [False, True]
    assert [choice["usage"]["provider_id"] for choice in both["providers"]] == [
        "aihubmix",
        "nvidia",
    ]

    assert choose(client, "nvidia") == 204
    alone = client.get("/v1/provider").json()
    assert alone["routes"]["ask"]["sentence"] == "NVIDIA NIM"
    assert alone["routes"]["ask"]["reason"] == ""
    assert [choice["in_use"] for choice in alone["providers"]] == [False, True]
    # With NVIDIA alone it draws the pictures too, with its model for code.
    assert alone["routes"]["scene"]["sentence"] == "NVIDIA NIM"
    assert alone["routes"]["scene"]["model_name"] == "Kimi K3.1 Pro"

    assert choose(client, "auto") == 204
    assert client.get("/v1/provider").json()["selection"] == "auto"
    assert AIHUBMIX_KEY not in client.get("/v1/provider").text


def wait_for(services: Services, response: Any) -> Any:
    assert response.status_code == 202, response.text
    return services.jobs.wait(response.json()["id"], timeout=30)


def test_a_key_can_be_checked_and_the_check_goes_to_that_provider_alone(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    give_keys(client, "aihubmix", "nvidia")
    job = wait_for(services, client.post("/v1/provider/check", json={"provider_id": "nvidia"}))
    assert job.status == "succeeded", job.error_message
    assert job.result["kind"] == "provider_check"
    assert (job.result["provider_id"], job.result["provider"]) == ("nvidia", "NVIDIA NIM")
    assert job.result["model"] == NVIDIA.models_for("check")[0].name
    assert job.result["seconds"] >= 0
    assert provider.urls == [NVIDIA_URL]
    assert provider.authorizations == [f"Bearer {NVIDIA_KEY}"]
    assert provider.kinds() == ["check"]
    # Nothing of the learner's is in it.
    assert provider.prompt() == (
        'You are checking that a connection works.\nReply with the single word "ready".'
    )
    usage = client.get("/v1/provider/usage", params={"provider_id": "nvidia"}).json()
    assert usage["requests_today"] == 1


def test_a_check_that_fails_says_why_and_is_not_tried_elsewhere(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    give_keys(client, "aihubmix", "nvidia")
    provider.queue(httpx.Response(401, text="no"))
    job = wait_for(services, client.post("/v1/provider/check", json={"provider_id": "aihubmix"}))
    assert (job.status, job.error_code) == ("failed", "provider_key_rejected")
    assert provider.urls == [AIHUBMIX_URL]


def test_a_check_needs_a_provider_adle_knows_and_a_key_for_it(client: TestClient) -> None:
    give_keys(client, "nvidia")
    missing = client.post("/v1/provider/check", json={"provider_id": "aihubmix"})
    assert (missing.status_code, missing.json()["error"]["code"]) == (409, "provider_key_missing")
    assert client.post("/v1/provider/check", json={"provider_id": "openai"}).status_code == 404
    assert client.post("/v1/provider/check", json={"provider_id": "NVIDIA"}).status_code == 422
    assert client.post("/v1/provider/check", json={}).status_code == 422


def test_long_work_under_way_can_be_seen_from_anywhere(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    give_keys(client, "aihubmix")
    assert client.get("/v1/jobs").json() == {"jobs": []}
    course = client.post(
        "/v1/courses", json={"title": "Calculus", "origin": "topic", "topic": "Limits."}
    ).json()
    started, release = threading.Event(), threading.Event()

    def slow(body: dict[str, Any]) -> str:
        started.set()
        release.wait(20)
        return json.dumps({"concepts": []})

    provider.queue(slow)
    job = client.post(f"/v1/courses/{course['id']}/curriculum/proposal")
    try:
        assert started.wait(20)
        writing = client.get("/v1/jobs").json()["jobs"]
        assert [(item["id"], item["kind"], item["course_id"]) for item in writing] == [
            (job.json()["id"], "curriculum_proposal", course["id"])
        ]
        assert writing[0]["created_at"]
        # A check of a key is short work: it is not in this list, and it does not wait
        # behind the long work either. It waits only for its turn at the same provider.
        check = client.post("/v1/provider/check", json={"provider_id": "aihubmix"})
        assert check.status_code == 202
        assert len(client.get("/v1/jobs").json()["jobs"]) == 1
    finally:
        release.set()
    services.jobs.wait(job.json()["id"], timeout=30)
    assert services.jobs.wait(check.json()["id"], timeout=30).status == "succeeded"
    assert client.get("/v1/jobs").json() == {"jobs": []}


def test_the_reason_is_about_the_provider_that_is_away_not_the_one_that_is_used() -> None:
    """A lesson, and the provider meant for it unable to answer."""
    resting = plan("lesson", AUTOMATIC, [coder(used=0.8), writer(resting=True)])
    assert resting.provider_ids == ("aihubmix", "nvidia")
    assert resting.reason == "NVIDIA NIM couldn’t answer earlier, so it’s paused for now."
    spent = plan("lesson", AUTOMATIC, [coder(used=0.8), writer(spent=True)])
    assert spent.provider_ids == ("aihubmix",)
    assert spent.reason == "NVIDIA NIM has no allowance left today."
    # Nothing untrue is said of the one that is asked instead.
    assert "AIHubMix couldn’t" not in resting.reason + spent.reason


def test_what_a_request_finds_out_with_the_old_key_is_not_held_against_the_new_one(
    services: Services,
) -> None:
    arrived = threading.Event()
    go_on = threading.Event()

    class RefusesLate(Fleet):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if str(request.url) == AIHUBMIX_URL and not go_on.is_set():
                self.calls.append((AIHUBMIX_URL, request.headers.get("authorization")))
                arrived.set()
                go_on.wait(20)
                return httpx.Response(401, text="no")
            return super().__call__(request)

    gateway, _, vault = automatic(services, RefusesLate())
    raised: list[BaseException] = []

    def check() -> None:
        try:
            gateway.complete(request("check"), provider_id="aihubmix")
        except BaseException as error:
            raised.append(error)

    thread = threading.Thread(target=check)
    thread.start()
    assert arrived.wait(10)
    # The learner replaces the key while the check of the old one is still out.
    vault.set_api_key("sk-test-another-0123456789abcdef", "aihubmix")
    gateway.forget_trouble("aihubmix")
    go_on.set()
    thread.join(10)
    assert [type(error) for error in raised] == [ProviderKeyRejectedError]
    # The old key was refused. That says nothing about the new one: it is asked first.
    assert gateway.plan("scene").provider_ids == ("aihubmix", "nvidia")


def test_changing_or_removing_a_key_stops_a_check_of_the_key_before_it(
    client: TestClient, services: Services
) -> None:
    import time

    from adle_core.application.jobs import LANE_QUICK, JobContext

    give_keys(client, "nvidia")

    def started_check() -> Any:
        running = threading.Event()

        def work(context: JobContext) -> None:
            running.set()
            while not context.cancelled:
                time.sleep(0.01)
            context.check_cancelled()

        job = services.jobs.submit("provider_check", work, subject_id="nvidia", lane=LANE_QUICK)
        assert running.wait(5)
        return job

    first = started_check()
    replaced = client.put(
        "/v1/provider/credential",
        json={"api_key": "nvapi-test-another-0123456789abcd", "provider_id": "nvidia"},
    )
    assert replaced.status_code == 204
    assert services.jobs.wait(first.id, timeout=10).status == "cancelled"

    second = started_check()
    removed = client.delete("/v1/provider/credential", params={"provider_id": "nvidia"})
    assert removed.status_code == 204
    assert services.jobs.wait(second.id, timeout=10).status == "cancelled"
