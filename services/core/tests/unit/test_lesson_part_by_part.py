"""A lesson can be taken at its first part while the rest is still being written (ADR-048).

Against the scripted provider, with an answer that stops partway until the test lets it go
on: what the learner can do meanwhile is looked at there. No request leaves the process.
"""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable, Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.generation.provider import ProviderUnavailableError
from adle_core.generation.stream import PartStream
from tests.support.model import LESSON, FakeProvider

KEY = "sk-test-0123456789abcdefghijklmnop"


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def a_concept(client: TestClient) -> tuple[str, str]:
    course = client.post(
        "/v1/courses",
        json={"title": "Neural networks", "origin": "topic", "topic": "How a neuron computes."},
    ).json()
    curriculum = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={
            "title": "Weights and bias",
            "summary": "How a neuron combines its inputs.",
            "objectives": [
                "Compute a weighted sum by hand.",
                "Say what a weight means for an input.",
                "Explain what the bias changes.",
            ],
        },
    ).json()
    concept = next(c["id"] for c in curriculum["concepts"] if c["title"] == "Weights and bias")
    return course["id"], concept


def until_parts(text: str, count: int) -> int:
    """Where in ``text`` the first ``count`` parts of the lesson have been written."""
    stream = PartStream()
    for at in range(1, len(text) + 1):
        if stream.add(text[at - 1 : at]).parts and stream.count >= count:
            return at
    raise AssertionError("the answer has fewer parts")


def event(text: str) -> bytes:
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n".encode()


class Chunks(httpx.SyncByteStream):
    """A streamed body that arrives as its iterator gives it, waits included."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        yield from self._chunks


class Partway:
    """An answer that is written as far as the end of its first ``parts`` parts and waits
    there until the test lets it go on, or ends there with ``fail``."""

    def __init__(self, lesson: dict[str, Any], parts: int = 1, *, fail: bool = False) -> None:
        self.text = json.dumps(lesson)
        self.cut = until_parts(self.text, parts)
        self.waiting = threading.Event()
        self.go_on = threading.Event()
        self.fail = fail

    def chunks(self) -> Iterator[bytes]:
        yield event(self.text[: self.cut])
        self.waiting.set()
        self.go_on.wait(20)
        if self.fail:
            raise httpx.ReadError("the provider went away")
        yield event(self.text[self.cut :])
        yield b'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'
        yield b"data: [DONE]\n\n"

    def __call__(self, body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=Chunks(self.chunks()),
        )


def running(services: Services, job_id: str, until: Callable[[Any], bool]) -> Any:
    for _ in range(1000):
        snapshot = services.jobs.get(job_id)
        if until(snapshot):
            return snapshot
        threading.Event().wait(0.02)
    raise AssertionError(f"the job never got there: {services.jobs.get(job_id)}")


def begun(snapshot: Any) -> bool:
    return isinstance(snapshot.result, dict) and bool(snapshot.result.get("lesson_id"))


def test_a_lesson_can_be_taken_at_its_first_part_while_the_rest_is_written(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    answer = Partway(LESSON)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        snapshot = running(services, job_id, begun)
        # Begun at its first part, the rest still to come.
        assert snapshot.status == "running"
        assert snapshot.progress_message == "Writing the rest of the lesson"
        lesson_id = snapshot.result["lesson_id"]
        early = keyed.get(f"/v1/lessons/{lesson_id}").json()
        assert early["writing"] is True
        assert [part["title"] for part in early["lesson"]["segments"]] == [
            LESSON["segments"][0]["title"]
        ]
        # Who is writing it is said already, as it will be once it has been written.
        assert early["written_by"] == {
            "provider": "AIHubMix",
            "models": ["Coding Kimi K3 (free)"],
            "note": "",
        }
        assert snapshot.result["written_by"]["models"] == ["Coding Kimi K3 (free)"]
        # It is a lesson like any other already: listed, and its place can be kept.
        course_id = early["lesson"]["course_id"]
        listed = keyed.get(f"/v1/courses/{course_id}/lessons").json()["lessons"]
        assert [(item["id"], item["writing"]) for item in listed] == [(lesson_id, True)]
        saved = keyed.put(f"/v1/lessons/{lesson_id}/progress", json={"position": 0})
        assert saved.status_code == 200, saved.text
    finally:
        answer.go_on.set()
    done = services.jobs.wait(job_id, timeout=60)
    assert done.status == "succeeded", done.error_message
    whole = keyed.get(f"/v1/lessons/{lesson_id}").json()
    assert whole["writing"] is False
    listed = keyed.get(f"/v1/courses/{course_id}/lessons").json()["lessons"]
    assert [item["writing"] for item in listed] == [False]
    assert whole["written_by"] == early["written_by"]
    # Every part, in order, and the part already there as it was.
    assert [part["title"] for part in whole["lesson"]["segments"]] == [
        part["title"] for part in LESSON["segments"]
    ]
    assert whole["lesson"]["segments"][0] == early["lesson"]["segments"][0]
    # One request for the words, as ever.
    assert provider.kinds().count("lesson") == 1


def test_a_lesson_taken_whole_and_one_taken_part_by_part_are_the_same_lesson(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    """The ids of its parts, questions and pictures follow from the parts kept, however
    the answer came."""
    _, concept = a_concept(keyed)
    provider.queue(LESSON)
    first = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    by_parts = services.jobs.wait(first, timeout=60).result["lesson_id"]
    provider.queue({"segments": LESSON["segments"], **LESSON})  # parts first: taken whole
    second = keyed.post(f"/v1/concepts/{concept}/lessons", json={}).json()["id"]
    whole = services.jobs.wait(second, timeout=60).result["lesson_id"]

    def shape(lesson_id: str) -> list[Any]:
        lesson = keyed.get(f"/v1/lessons/{lesson_id}").json()["lesson"]
        return [
            (
                part["id"],
                part["type"],
                (part.get("question") or {}).get("id"),
                (part.get("scene") or {}).get("scene_id"),
            )
            for part in lesson["segments"]
        ]

    assert shape(by_parts) == shape(whole)


def test_a_later_part_that_is_not_whole_is_left_out_and_the_lesson_is_not_written_again(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    broken = copy.deepcopy(LESSON)
    broken["segments"][4]["type"] = "lecture"  # not a kind of part Adle has
    provider.queue(broken)
    job = services.jobs.wait(keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"], timeout=60)
    assert job.status == "succeeded", job.error_message
    assert provider.kinds().count("lesson") == 1
    assert "1 part of this lesson couldn’t be used, so it was left out." in job.result["notes"]
    lesson = keyed.get(f"/v1/lessons/{job.result['lesson_id']}").json()["lesson"]
    assert len(lesson["segments"]) == len(LESSON["segments"]) - 1


def test_a_first_part_that_is_not_whole_begins_nothing_and_the_whole_answer_decides(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    broken = copy.deepcopy(LESSON)
    broken["segments"][0]["type"] = "lecture"
    provider.queue(broken, LESSON)
    job = services.jobs.wait(keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"], timeout=60)
    assert job.status == "succeeded", job.error_message
    # Nothing was stored from the first answer: it was written again, told why.
    assert provider.kinds().count("lesson") == 2
    assert "is not a kind of segment Adle has" in provider.prompt(1)
    listed = keyed.get(f"/v1/courses/{course}/lessons").json()["lessons"]
    assert [item["id"] for item in listed] == [job.result["lesson_id"]]
    lesson = keyed.get(f"/v1/lessons/{job.result['lesson_id']}").json()
    assert len(lesson["lesson"]["segments"]) == len(LESSON["segments"])


def test_stopping_once_the_lesson_has_begun_keeps_the_parts_it_has(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    answer = Partway(LESSON, parts=2)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        running(services, job_id, begun)
        assert keyed.post(f"/v1/jobs/{job_id}/cancel").status_code == 200
        done = services.jobs.wait(job_id, timeout=30)
    finally:
        answer.go_on.set()
    assert done.status == "succeeded", done
    assert (
        "You stopped this lesson while it was being written, so it ends early."
        in (done.result["notes"])
    )
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    assert loaded["writing"] is False
    assert len(loaded["lesson"]["segments"]) == 2
    # Still said to be written by the model that wrote what there is.
    assert loaded["written_by"]["models"] == ["Coding Kimi K3 (free)"]
    # Nothing waits for a picture that will not be asked for, and nothing more is asked.
    assert loaded["pending_scene_ids"] == []
    assert provider.kinds() == ["lesson"]
    assert keyed.get(f"/v1/courses/{course}/jobs").json()["jobs"] == []


def test_a_provider_that_fails_once_the_lesson_has_begun_leaves_it_shorter_not_gone(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    answer = Partway(LESSON, parts=2, fail=True)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    assert answer.waiting.wait(20)
    running(services, job_id, begun)
    answer.go_on.set()
    done = services.jobs.wait(job_id, timeout=30)
    assert done.status == "succeeded", done
    assert "The AI stopped partway through this lesson, so it ends early." in (done.result["notes"])
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    assert loaded["writing"] is False
    assert len(loaded["lesson"]["segments"]) == 2
    assert loaded["written_by"]["models"] == ["Coding Kimi K3 (free)"]


def test_removing_a_lesson_while_it_is_written_ends_the_work(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    answer = Partway(LESSON)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        lesson_id = running(services, job_id, begun).result["lesson_id"]
        assert keyed.delete(f"/v1/lessons/{lesson_id}").status_code == 204
        done = services.jobs.wait(job_id, timeout=30)
    finally:
        answer.go_on.set()
    assert done.status == "cancelled", done
    assert keyed.get(f"/v1/lessons/{lesson_id}").status_code == 404


def test_a_lesson_left_being_written_when_the_app_closed_ends_at_the_next_start(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    answer = Partway(LESSON)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        lesson_id = running(services, job_id, begun).result["lesson_id"]
        # What the core does as it starts: nothing is being written then.
        services.lessons.settle_unfinished()
        assert keyed.get(f"/v1/lessons/{lesson_id}").json()["writing"] is False
    finally:
        answer.go_on.set()
        services.jobs.wait(job_id, timeout=30)


def test_a_model_that_fails_before_its_first_part_is_passed_over_as_before(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    """Nothing is begun from an answer that never reached a whole part: the request fails
    as it always did."""
    _, concept = a_concept(keyed)
    provider.queue(ProviderUnavailableError())
    job = services.jobs.wait(keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"], timeout=30)
    assert job.status == "failed"
