"""Pages that are pictures, read by a model that sees pictures, at the learner's word (ADR-060).

The provider is the in-process stand-in: nothing here reaches a real one.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.prompts import read_page_request
from adle_core.generation.provider import AIHUBMIX, NVIDIA, ChatClient
from adle_core.generation.routing import Standing, plan
from tests.support.model import READ_PAGE, FakeProvider, pictures_of, sse

DOCUMENTS = Path(__file__).resolve().parents[4] / "fixtures" / "sample-documents"
NVIDIA_KEY = "nvapi-test-0000000000000000000000000000"
AIHUBMIX_KEY = "sk-test-00000000000000000000000000000000"
SUPER_VL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
PNG = bytes.fromhex("89504e470d0a1a0a")
TYPED = (
    "Week 3: Simple machines\nA lever is a rigid bar that turns about a fixed point, the fulcrum."
)


def keys(services: Services, *providers: str, selection: str = "auto") -> None:
    for provider_id in providers:
        services.credentials.set_api_key(
            NVIDIA_KEY if provider_id == "nvidia" else AIHUBMIX_KEY, provider_id
        )
    services.gateway.select(selection)


def notes(client: TestClient, services: Services) -> dict[str, Any]:
    """A course with the scanned notes in it: typed, handwritten, and a page of text."""
    course = client.post("/v1/courses", json={"title": "Levers", "origin": "materials"}).json()
    path = str(DOCUMENTS / "scanned-notes.pdf")
    job = client.post(f"/v1/courses/{course['id']}/sources/import", json={"paths": [path]})
    services.jobs.wait(job.json()["id"])
    (source,) = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
    assert source["picture_pages"] == [1, 2]
    return source


def read(client: TestClient, services: Services, source_id: str) -> Any:
    response = client.post(f"/v1/sources/{source_id}/read-pictures")
    assert response.status_code == 202, response.text
    return services.jobs.wait(response.json()["id"], timeout=60)


def test_a_file_s_pictures_are_read_page_by_page_and_become_its_text(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    keys(services, "nvidia", "aihubmix")
    source = notes(client, services)
    # The pages are read side by side (ADR-068): each answered for what it shows.
    provider.when("scanned-notes.pdf, page 1", TYPED)
    provider.when("scanned-notes.pdf, page 2", READ_PAGE)

    job = read(client, services, source["id"])

    assert job.status == "succeeded"
    assert job.result["pages_read"] == [1, 2]
    assert job.result["written_by"] == {"provider": "NVIDIA NIM", "model": "Nemotron 3.5 Super"}
    # One picture to a request, each a PNG, to the one model seen to read pictures.
    assert provider.kinds() == ["read", "read"]
    for body in provider.requests:
        assert body["model"] == SUPER_VL
        (picture,) = pictures_of(body)
        assert picture.startswith("data:image/png;base64,")
        assert base64.b64decode(picture.split(",", 1)[1]).startswith(PNG)
    # The file's name is the learner's text, in a block of its own.
    prompts = [provider.prompt(index) for index in range(2)]
    assert any('<learner_material kind="file">\nscanned-notes.pdf, page 1' in p for p in prompts)

    (after,) = client.get(f"/v1/courses/{source['course_id']}/sources").json()["sources"]
    assert after["picture_pages"] == []
    assert after["warnings"] == []
    assert after["status"] == "extracted"
    detail = client.get(f"/v1/sources/{source['id']}").json()
    # The pages read come where they stand in the file, trusted a little less.
    assert [section["page_number"] for section in detail["sections"]] == [1, 2, 3]
    assert [section["ordinal"] for section in detail["sections"]] == [0, 1, 2]
    assert [section["confidence"] for section in detail["sections"]][:2] == [0.8, 0.8]
    # What was read is searched and quoted like any other page.
    hits = client.get(f"/v1/courses/{source['course_id']}/search", params={"q": "rigid"}).json()[
        "hits"
    ]
    assert [hit["page_number"] for hit in hits] == [1]


def test_only_a_model_that_sees_pictures_is_sent_one(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    # AIHubMix's model has not been seen to read a picture: chosen alone, nothing is sent.
    keys(services, "aihubmix", selection="aihubmix")
    source = notes(client, services)
    refused = client.post(f"/v1/sources/{source['id']}/read-pictures")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "pictures_unreadable"
    assert "AIHubMix can’t read pictures" in refused.json()["error"]["message"]
    # Every provider allowed, and a key only for AIHubMix: the same.
    services.gateway.select("auto")
    assert client.post(f"/v1/sources/{source['id']}/read-pictures").status_code == 409
    # NVIDIA chosen, with no key yet: the key is what is missing.
    services.gateway.select("nvidia")
    missing = client.post(f"/v1/sources/{source['id']}/read-pictures")
    assert missing.json()["error"]["code"] == "provider_key_missing"
    assert provider.requests == []


def test_pages_are_read_side_by_side_where_the_provider_takes_several_at_once(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    # NVIDIA takes several requests at once (ADR-068): both pages are being read together,
    # or the first waits here in vain and fails. Each is still drawn in turn.
    both_read = threading.Barrier(2, timeout=20)

    def together(answer: str) -> Callable[[dict[str, Any]], str]:
        def read_together(body: dict[str, Any]) -> str:
            both_read.wait()
            return answer

        return read_together

    keys(services, "nvidia")
    source = notes(client, services)
    provider.when("scanned-notes.pdf, page 1", together(TYPED))
    provider.when("scanned-notes.pdf, page 2", together(READ_PAGE))

    job = read(client, services, source["id"])

    assert job.status == "succeeded"
    assert not both_read.broken
    assert job.result["pages_read"] == [1, 2]
    detail = client.get(f"/v1/sources/{source['id']}").json()
    assert [section["page_number"] for section in detail["sections"]] == [1, 2, 3]


def test_where_a_page_would_be_read_is_said_before_it_is_sent(
    client: TestClient, services: Services
) -> None:
    keys(services, "aihubmix", selection="aihubmix")
    assert client.get("/v1/provider").json()["routes"]["read"]["provider_ids"] == []
    keys(services, "nvidia", selection="auto")
    route = client.get("/v1/provider").json()["routes"]["read"]
    assert route["names"] == ["NVIDIA NIM"]
    assert route["sentence"] == "NVIDIA NIM"
    assert route["model_name"] == "Nemotron 3.5 Super"


def test_a_page_with_nothing_on_it_is_read_once_and_adds_nothing(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    keys(services, "nvidia")
    source = notes(client, services)
    provider.when("scanned-notes.pdf, page 1", "[no text]")
    assert read(client, services, source["id"]).status == "succeeded"
    detail = client.get(f"/v1/sources/{source['id']}").json()
    assert [section["page_number"] for section in detail["sections"]] == [2, 3]
    assert detail["source"]["picture_pages"] == []


def test_removing_the_file_stops_its_reading(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    keys(services, "nvidia")
    source = notes(client, services)

    sent_by_then: list[int] = []
    removed = threading.Event()

    def removed_while_read(body: dict[str, Any]) -> str:
        # Removed as its first page is read, and while the next may be drawn from it.
        services.sources.delete(source["id"])
        sent_by_then.append(len(provider.requests))
        removed.set()
        return READ_PAGE

    provider.when("scanned-notes.pdf, page 1", removed_while_read)
    job = read(client, services, source["id"])
    assert job.status == "cancelled"
    # The reading stops at once; the removal can take a few seconds more, while Windows
    # lets go of a file a page is being drawn from (ADR-068). Seen ending first, 2026-11-26.
    assert removed.wait(30), "the file was removed"
    # The pages being read when the file went are the last requests: nothing more is sent.
    assert len(provider.requests) == sent_by_then[0]
    assert client.get(f"/v1/sources/{source['id']}").status_code == 404


def test_a_file_whose_original_is_gone_says_to_import_it_again(
    client: TestClient, services: Services
) -> None:
    keys(services, "nvidia")
    source = notes(client, services)
    for stored in services.settings.sources_dir.iterdir():
        stored.unlink()
    refused = client.post(f"/v1/sources/{source['id']}/read-pictures")
    assert refused.status_code == 422
    assert "Import it again" in refused.json()["error"]["message"]


def test_a_picture_goes_with_the_words_as_a_part_of_the_message() -> None:
    sent: list[dict[str, Any]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return sse("Levers")

    vault = CredentialVault()
    vault.set_api_key(NVIDIA_KEY, "nvidia")
    client = ChatClient(NVIDIA, vault, transport=httpx.MockTransport(endpoint))
    request = read_page_request("notes.pdf", 2, PNG + b"picture")
    (reader,) = NVIDIA.models_for("read")
    assert client.complete(request, model=reader).text == "Levers"
    system, user = sent[0]["messages"]
    assert isinstance(system["content"], str)
    assert user["content"][0]["type"] == "text"
    assert user["content"][1] == {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(PNG + b"picture").decode()
        },
    }
    # A model that does not see pictures is never sent one.
    with pytest.raises(ValueError, match="not sent pictures"):
        client.complete(request, model=NVIDIA.models[0])
    assert len(sent) == 1


def test_a_provider_without_a_model_that_sees_pictures_cannot_be_asked_to_read_one() -> None:
    assert AIHUBMIX.models_for("read") == ()
    assert [spec.id for spec in NVIDIA.models_for("read")] == [SUPER_VL]
    # Nor to look over a film's pictures (ADR-066).
    assert not AIHUBMIX.serves("storyboard")
    assert [spec.id for spec in NVIDIA.models_for("storyboard")] == [SUPER_VL]
    reads = frozenset({"ask", "curriculum", "lesson", "scene", "check"})
    aihubmix = Standing("aihubmix", "AIHubMix", has_key=True, serves=reads)
    nvidia = Standing("nvidia", "NVIDIA NIM", has_key=False)
    # Chosen alone, it is asked nothing; with every provider allowed, the one that could
    # read it is named, so that the refusal can say whose key is missing.
    assert plan("read", "aihubmix", [aihubmix, nvidia]).provider_ids == ()
    assert plan("read", "auto", [aihubmix, nvidia]).provider_ids == ("nvidia",)
    assert plan("read", "auto", [aihubmix]).provider_ids == ()
    # Anything else goes where it always went.
    assert plan("lesson", "aihubmix", [aihubmix, nvidia]).provider_ids == ("aihubmix",)
