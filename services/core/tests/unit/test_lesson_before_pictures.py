"""A lesson can be taken as soon as its text is written; its pictures follow (ADR-031).

Against the scripted provider: no request in this file leaves the process.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable, Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.generation.quota import QuotaLimits
from adle_core.ingestion.extract import extract_in_process
from adle_core.lessons.bundle import LessonInvalidError, Problem, parse_bundle
from tests.conftest import LOOPBACK, TEST_TOKEN
from tests.support.model import FORBIDDEN_SCENE, LESSON, FakeProvider

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


class Held:
    """An answer that does not come until the test lets it: a picture being drawn."""

    def __init__(self, provider: FakeProvider, answer: Any = None) -> None:
        self.asked = threading.Event()
        self.release = threading.Event()
        self._provider = provider
        self._answer = answer

    def __call__(self, body: dict[str, Any]) -> Any:
        self.asked.set()
        self.release.wait(20)
        return self._answer if self._answer is not None else self._provider.default(body)


def running(services: Services, job_id: str, until: Callable[[Any], bool]) -> Any:
    """The job once it is in the state asked for, without waiting for it to end."""
    for _ in range(1000):
        snapshot = services.jobs.get(job_id)
        if until(snapshot):
            return snapshot
        threading.Event().wait(0.02)
    raise AssertionError(f"the job never got there: {services.jobs.get(job_id)}")


def test_a_lesson_can_be_taken_as_soon_as_its_text_is_written(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    first = Held(provider)
    provider.queue(LESSON, first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert first.asked.wait(20)
        job = running(services, job_id, lambda snapshot: snapshot.result is not None)

        # The work is still under way, and already says which lesson it is.
        assert job.status == "running"
        assert job.progress_message.startswith("Drawing picture 1 of 2")
        result = job.result
        assert result["kind"] == "lesson_generation"
        assert (result["pictures_planned"], result["pictures_made"]) == (2, 0)
        assert result["pictures_pending"] == 2

        # It is listed and can be opened; it says which pictures it is waiting for.
        listed = keyed.get(f"/v1/courses/{course}/lessons").json()["lessons"]
        assert [(item["id"], item["pictures_pending"]) for item in listed] == [
            (result["lesson_id"], 2)
        ]
        loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
        assert loaded["pending_scene_ids"] == ["scn_1", "scn_2"]
        assert loaded["scenes"] == []
        # The parts keep their place and their kind, and each carries its picture in words.
        waiting = [
            (segment["type"], segment["scene"]["scene_id"])
            for segment in loaded["lesson"]["segments"]
            if segment.get("scene")
        ]
        assert waiting == [("visualization", "scn_1"), ("interaction", "scn_2")]
        assert all(
            segment["scene"]["fallback_text"]
            for segment in loaded["lesson"]["segments"]
            if segment.get("scene")
        )

        # It can be taken: a question is scored and the learner's place is kept.
        answered = keyed.post(
            f"/v1/lessons/{result['lesson_id']}/questions/q_2/answer", json={"number": 3}
        )
        assert answered.json()["outcome"] == "correct"
        saved = keyed.put(
            f"/v1/lessons/{result['lesson_id']}/progress", json={"position": 3, "completed": False}
        )
        assert saved.status_code == 200
    finally:
        first.release.set()

    done = services.jobs.wait(job_id, timeout=30)
    assert done.status == "succeeded", done
    assert (done.result["pictures_made"], done.result["pictures_pending"]) == (2, 0)
    assert done.result["notes"] == []
    # One request for the text and one for each picture, as before: only the order of
    # "stored" and "drawn" has changed.
    assert provider.kinds() == ["lesson", "scene", "scene"]
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    assert loaded["pending_scene_ids"] == []
    assert [scene["id"] for scene in loaded["scenes"]] == ["scn_1", "scn_2"]
    # The learner's place was not moved by the pictures arriving.
    assert loaded["progress"]["position"] == 3


def test_each_picture_is_added_when_it_is_drawn(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    second = Held(provider)
    provider.queue(LESSON, provider.default, second)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert second.asked.wait(20)
        job = running(
            services,
            job_id,
            lambda snapshot: bool(snapshot.result) and snapshot.result["pictures_made"] == 1,
        )
        assert job.result["pictures_pending"] == 1
        loaded = keyed.get(f"/v1/lessons/{job.result['lesson_id']}").json()
        assert [scene["id"] for scene in loaded["scenes"]] == ["scn_1"]
        assert loaded["pending_scene_ids"] == ["scn_2"]
    finally:
        second.release.set()
    assert services.jobs.wait(job_id, timeout=30).status == "succeeded"


def test_a_picture_that_cannot_be_drawn_is_said_in_words_and_no_longer_waited_for(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    second = Held(provider)
    # Two tries at the first picture, both unusable; the second is held.
    provider.queue(LESSON, FORBIDDEN_SCENE, "this is not python at all (", second)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert second.asked.wait(20)
        job = running(
            services,
            job_id,
            lambda snapshot: bool(snapshot.result) and snapshot.result["pictures_pending"] == 1,
        )
        assert job.result["notes"] == [
            "The picture for “The weighted sum” couldn’t be made, so that part is explained "
            "in words."
        ]
        loaded = keyed.get(f"/v1/lessons/{job.result['lesson_id']}").json()
        assert loaded["pending_scene_ids"] == ["scn_2"]
        part = loaded["lesson"]["segments"][1]
        assert (part["type"], part["title"]) == ("explanation", "The weighted sum")
        assert part.get("scene") is None
    finally:
        second.release.set()
    done = services.jobs.wait(job_id, timeout=30)
    assert (done.status, done.result["pictures_made"]) == ("succeeded", 1)


def test_stopping_once_there_is_a_lesson_stops_the_pictures_and_keeps_the_lesson(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    first = Held(provider)
    provider.queue(LESSON, first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert first.asked.wait(20)
        running(services, job_id, lambda snapshot: snapshot.result is not None)
        assert keyed.post(f"/v1/jobs/{job_id}/cancel").status_code == 200
        done = services.jobs.wait(job_id, timeout=30)
    finally:
        first.release.set()

    # The lesson was already there, so the work ends with a lesson, not with nothing.
    assert done.status == "succeeded", done
    assert (done.result["pictures_made"], done.result["pictures_pending"]) == (0, 0)
    assert done.result["notes"] == ["You stopped the pictures, so 2 parts are explained in words."]
    # The picture that was being drawn was the last thing asked for.
    assert provider.kinds() == ["lesson", "scene"]
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    assert loaded["pending_scene_ids"] == []
    assert loaded["scenes"] == []
    assert all(segment.get("scene") is None for segment in loaded["lesson"]["segments"])
    assert keyed.get(f"/v1/courses/{course}/jobs").json()["jobs"] == []


def test_stopping_before_there_is_a_lesson_still_saves_nothing(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    text = Held(provider, LESSON)
    provider.queue(text)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert text.asked.wait(20)
        assert keyed.post(f"/v1/jobs/{job_id}/cancel").status_code == 200
        done = services.jobs.wait(job_id, timeout=30)
    finally:
        text.release.set()
    assert done.status == "cancelled"
    assert done.result is None
    assert keyed.get(f"/v1/courses/{course}/lessons").json()["lessons"] == []


def test_removing_the_lesson_while_its_pictures_are_drawn_ends_the_work(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    first = Held(provider)
    provider.queue(LESSON, first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert first.asked.wait(20)
        job = running(services, job_id, lambda snapshot: snapshot.result is not None)
        assert keyed.delete(f"/v1/lessons/{job.result['lesson_id']}").status_code == 204
        # The work ends there and then. The picture it had asked for would take far longer
        # than this to arrive.
        done = services.jobs.wait(job_id, timeout=5)
    finally:
        first.release.set()
    # Nothing left to draw for: no second picture is asked for, and nothing comes back.
    assert done.status == "cancelled"
    assert done.result is None
    assert provider.kinds() == ["lesson", "scene"]
    assert keyed.get(f"/v1/courses/{course}/lessons").json()["lessons"] == []
    assert keyed.get(f"/v1/courses/{course}/jobs").json()["jobs"] == []


def test_removing_a_course_stops_what_is_being_written_for_it(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course, concept = a_concept(keyed)
    first = Held(provider)
    provider.queue(LESSON, first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert first.asked.wait(20)
        running(services, job_id, lambda snapshot: snapshot.result is not None)
        assert keyed.delete(f"/v1/courses/{course}").status_code == 204
        # The picture that was asked for never arrives, and nothing waits for it: a lesson
        # for another course is written from start to end meanwhile.
        _, other = a_concept(keyed)
        next_id = keyed.post(f"/v1/concepts/{other}/lessons").json()["id"]
        done = services.jobs.wait(next_id, timeout=10)
    finally:
        first.release.set()
    assert done.status == "succeeded", done
    # One picture asked for the course that went away, and no second one.
    assert provider.kinds() == ["lesson", "scene", "lesson", "scene", "scene"]


def test_a_picture_the_lesson_cannot_take_is_said_in_words_and_the_work_goes_on(
    keyed: TestClient,
    services: Services,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, concept = a_concept(keyed)
    attach = services.lessons.settle_scene

    def refuse_the_first(lesson_id: str, scene_id: str, scene: Any) -> Any:
        if scene is not None and scene_id == "scn_1":
            raise LessonInvalidError([Problem("scenes.0", "made up for this test")])
        return attach(lesson_id, scene_id, scene)

    monkeypatch.setattr(services.lessons, "settle_scene", refuse_the_first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    done = services.jobs.wait(job_id, timeout=30)

    # The lesson was there already. Losing a picture does not undo it.
    assert done.status == "succeeded", done
    assert (done.result["pictures_made"], done.result["pictures_pending"]) == (1, 0)
    assert done.result["notes"] == [
        "The picture for “The weighted sum” couldn’t be made, so that part is explained in words."
    ]
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    assert [scene["id"] for scene in loaded["scenes"]] == ["scn_2"]
    assert loaded["pending_scene_ids"] == []


def test_who_wrote_a_lesson_is_kept_with_the_lesson(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    _, concept = a_concept(keyed)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    done = services.jobs.wait(job_id, timeout=30)
    loaded = keyed.get(f"/v1/lessons/{done.result['lesson_id']}").json()
    written_by = loaded["written_by"]
    assert written_by["provider"] == done.result["written_by"]["provider"]
    assert written_by["models"] == done.result["written_by"]["models"]
    assert written_by["note"] == ""
    # Names and a sentence, and nothing else: no key, no address.
    assert set(written_by) == {"provider", "models", "note"}
    assert KEY not in str(loaded)


def test_a_sample_lesson_says_nothing_about_a_writer_and_waits_for_nothing(
    client: TestClient,
) -> None:
    course = client.post("/v1/courses/sample").json()
    listed = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    assert listed
    assert all(item["pictures_pending"] == 0 for item in listed)
    loaded = client.get(f"/v1/lessons/{listed[0]['id']}").json()
    assert loaded["pending_scene_ids"] == []
    assert loaded["written_by"] is None


# -- the gate ----------------------------------------------------------------------------


def a_compiled_lesson(keyed: TestClient, services: Services, provider: FakeProvider) -> Any:
    """A stored lesson's own document and scenes, to put through the gate again."""
    _, concept = a_concept(keyed)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    done = services.jobs.wait(job_id, timeout=30)
    return services.lessons.get(done.result["lesson_id"])


def test_the_gate_lets_a_part_refer_to_a_picture_that_is_included_or_still_to_come(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    whole = a_compiled_lesson(keyed, services, provider)
    lesson = whole.lesson.model_dump(mode="json")
    scenes = [
        {"id": scene.id, "purpose": scene.purpose, "source": scene.source} for scene in whole.scenes
    ]

    # Both still to come, one of each, both included: all three are lessons.
    for included, coming in (([], ["scn_1", "scn_2"]), (scenes[:1], ["scn_2"]), (scenes, [])):
        bundle = parse_bundle(
            {"lesson": copy.deepcopy(lesson), "scenes": included, "pending_scene_ids": coming}
        )
        assert bundle.pending_scene_ids == coming
        assert [scene.id for scene in bundle.scenes] == [scene["id"] for scene in included]

    refused: list[tuple[list[Any], Any]] = [
        # A part refers to a picture that is neither here nor coming.
        (scenes[:1], []),
        # A picture cannot be both.
        (scenes, ["scn_2"]),
        # Nothing may be waited for that no part shows.
        (scenes, ["scn_9"]),
        # Named twice.
        ([], ["scn_1", "scn_1", "scn_2"]),
        # Not a list of ids at all.
        (scenes, "scn_1"),
        (scenes, [1]),
        ([], ["scn_1", "SCENE TWO"]),
    ]
    for included, coming in refused:
        with pytest.raises(LessonInvalidError):
            parse_bundle(
                {"lesson": copy.deepcopy(lesson), "scenes": included, "pending_scene_ids": coming}
            )


# -- when the app was closed while a picture was being drawn -------------------------------


@pytest.fixture
def restarted(settings: Settings, provider: FakeProvider) -> Iterator[Callable[[], Services]]:
    """Build the services again on the same data, as the next start of the core does."""
    made: list[Services] = []

    def again() -> Services:
        services = build_services(
            settings,
            LaunchToken(TEST_TOKEN),
            extract=extract_in_process,
            provider_transport=httpx.MockTransport(provider),
            quota_limits=QuotaLimits(requests_per_minute=600),
        )
        made.append(services)
        return services

    yield again
    for services in made:
        services.close()


def test_a_lesson_left_waiting_when_the_app_closed_is_settled_at_the_next_start(
    keyed: TestClient,
    services: Services,
    provider: FakeProvider,
    restarted: Callable[[], Services],
) -> None:
    _, concept = a_concept(keyed)
    first = Held(provider)
    provider.queue(LESSON, first)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    assert first.asked.wait(20)
    lesson_id = running(services, job_id, lambda snapshot: snapshot.result is not None).result[
        "lesson_id"
    ]
    # The app goes away with the first picture half drawn: the lesson is waiting for two.
    assert len(services.lessons.get(lesson_id).pending_scene_ids) == 2

    try:
        later = restarted()
        loaded = later.lessons.get(lesson_id)
        # Nothing is being drawn any more, so nothing is waited for: both parts in words.
        assert loaded.pending_scene_ids == []
        assert loaded.scenes == []
        assert all(getattr(segment, "scene", None) is None for segment in loaded.lesson.segments)
        with TestClient(
            create_app(later),
            base_url=LOOPBACK,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        ) as client:
            listed = client.get(f"/v1/lessons/{lesson_id}").json()
            assert listed["pending_scene_ids"] == []
    finally:
        first.release.set()
        services.jobs.wait(job_id, timeout=30)
