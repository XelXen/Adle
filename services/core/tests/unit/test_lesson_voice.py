"""A lesson in a natural voice is made with its voice (ADR-051).

Its models load as the lesson is asked for; it is recorded part by part as its parts are
written, by one recording on one engine; and it is ready once its first part can be heard.
With the stand-in engine (tests/support/fake_voice_engine.py) and the scripted provider:
no models, no graphics card, and no request leaves the process.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.narration import (
    KIND_NARRATION,
    KIND_VOICE_WARMUP,
    READY_GUESS_SECONDS,
    NarrationService,
)
from adle_core.application.services import Services
from adle_core.voice.catalog import Family
from adle_core.voice.runtime import VoiceEngine, VoicePaths
from tests.support.model import LESSON, FakeProvider
from tests.unit.test_lesson_part_by_part import KEY, Partway, a_concept, begun, running
from tests.unit.test_narration import WITH_CARD, set_up


class Engines:
    """The engine maker, counting the engines made: a model is loaded once per engine."""

    def __init__(self) -> None:
        self.made: list[VoiceEngine] = []

    def __call__(self, paths: VoicePaths, family: Family) -> VoiceEngine:
        engine = VoiceEngine(paths, family)
        self.made.append(engine)
        return engine


@pytest.fixture
def engines() -> Engines:
    return Engines()


@pytest.fixture
def voiced(services: Services, tmp_path: Path, engines: Engines) -> Services:
    """The services with a natural voice set up and chosen, wired as `build_services` wires
    them: the lesson's voice warmed when it is asked for, recorded as it is stored, and the
    lesson ready when its first part can be heard."""
    paths = set_up(tmp_path / "voice", "kokoro")
    narration = NarrationService(
        services.lessons,
        services.jobs,
        paths,
        hardware=lambda: WITH_CARD,
        engine=engines,
        idle_seconds=3.0,
    )
    services.narration = narration
    generation = services.generation
    generation._on_stored = narration.record_ahead
    generation._on_begun = narration.warm
    generation._voice_pending = narration.voice_pending
    generation._voice_wait = narration.ready_after
    narration.on_voiced = generation.voiced
    yield services
    narration.close()


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def lines_of(services: Services, lesson_id: str) -> list[str]:
    found: list[str] = []
    for segment in services.lessons.get_lesson(lesson_id).segments:
        for beat in getattr(segment, "narration", None) or []:
            if beat.text not in found:
                found.append(beat.text)
    return found


def recordings(services: Services, lesson_id: str) -> int:
    """How many recordings were ever made of a lesson."""
    with services.database.read() as session:
        from adle_core.infrastructure.orm import Job

        return (
            session.query(Job)
            .filter(Job.kind == KIND_NARRATION, Job.subject_id == lesson_id)
            .count()
        )


def eventually(check: Callable[[], bool], what: str, seconds: float = 30.0) -> None:
    for _ in range(int(seconds / 0.02)):
        if check():
            return
        threading_wait(0.02)
    raise AssertionError(f"never: {what}")


def threading_wait(seconds: float) -> None:
    import threading

    threading.Event().wait(seconds)


def test_a_lesson_is_recorded_part_by_part_by_one_recording_on_one_engine(
    keyed: TestClient,
    voiced: Services,
    provider: FakeProvider,
    engines: Engines,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.05")
    _, concept = a_concept(keyed)
    answer = Partway(LESSON)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        lesson_id = running(voiced, job_id, begun).result["lesson_id"]
        # The first part is recorded while the rest is still being written.
        first = lines_of(voiced, lesson_id)
        eventually(
            lambda: len(voiced.narration.clips(lesson_id)) == len(first),
            "the first part was recorded",
        )
        assert voiced.lessons.is_writing(lesson_id)
        # And the recording waits for the next part rather than ending.
        assert voiced.jobs.find_active(KIND_NARRATION, lesson_id) is not None
    finally:
        answer.go_on.set()
    done = voiced.jobs.wait(job_id, timeout=60)
    assert done.status == "succeeded", done.error_message
    every = lines_of(voiced, lesson_id)
    assert len(every) > len(first)
    eventually(
        lambda: voiced.jobs.find_active(KIND_NARRATION, lesson_id) is None,
        "the recording ended once the lesson was whole",
    )
    assert [line.text for line in voiced.narration.clips(lesson_id)] == every
    # One recording followed the lesson from its first part to its last, on one engine:
    # its models were loaded once, with the warm-up the lesson's asking began.
    assert recordings(voiced, lesson_id) == 1
    assert len(engines.made) == 1
    assert voiced.narration.voiced_parts(lesson_id) == len(LESSON["segments"])


def test_a_lesson_in_a_natural_voice_is_ready_when_its_first_part_can_be_heard(
    keyed: TestClient, voiced: Services, provider: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Slower than the words: the first part is written long before it can be heard.
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.4")
    _, concept = a_concept(keyed)
    answer = Partway(LESSON)
    provider.queue(answer)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    try:
        assert answer.waiting.wait(20)
        snapshot = running(voiced, job_id, begun)
        lesson_id = snapshot.result["lesson_id"]
        assert snapshot.result["voicing"] is True
        heard = running(voiced, job_id, lambda job: job.result.get("voicing") is False)
        assert voiced.narration.voiced_parts(lesson_id) >= 1
        assert heard.status == "running"
    finally:
        answer.go_on.set()
    done = voiced.jobs.wait(job_id, timeout=60)
    assert done.status == "succeeded", done.error_message
    assert done.result["voicing"] is False


def test_a_lesson_whose_words_are_written_before_its_voice_waits_for_its_first_part(
    keyed: TestClient, voiced: Services, provider: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.5")
    _, concept = a_concept(keyed)
    provider.queue(LESSON)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    stages: list[Any] = []

    def watch(job: Any) -> bool:
        stages.append((job.progress_detail or {}).get("stage"))
        return job.finished

    running(voiced, job_id, watch)
    done = voiced.jobs.get(job_id)
    assert done.status == "succeeded", done.error_message
    # It said what it waited for, and was done once the first part could be heard.
    assert "voicing" in stages
    assert done.result["voicing"] is False
    assert voiced.narration.voiced_parts(done.result["lesson_id"]) >= 1


def test_a_voice_that_fails_holds_the_lesson_back_no_longer(
    keyed: TestClient, voiced: Services, provider: FakeProvider
) -> None:
    refused = copy.deepcopy(LESSON)
    # The stand-in refuses a line with FAIL in it, as the engine refuses what it cannot say.
    refused["segments"][0]["beats"][0]["say"] = "FAIL to say this, the voice will."
    _, concept = a_concept(keyed)
    provider.queue(refused)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    done = voiced.jobs.wait(job_id, timeout=60)
    assert done.status == "succeeded", done.error_message
    # Nothing is being recorded any more, so nothing is waited for: it is read as before.
    assert done.result["voicing"] is False
    assert voiced.narration.voice_pending(done.result["lesson_id"]) is False


def test_the_voice_is_warmed_as_a_lesson_is_asked_for_and_then_let_go(
    voiced: Services, engines: Engines
) -> None:
    voiced.narration.warm()
    warm = voiced.jobs.latest(KIND_VOICE_WARMUP, "kokoro")
    assert warm is not None
    assert voiced.jobs.wait(warm.id, timeout=30).status == "succeeded"
    assert len(engines.made) == 1
    engine = engines.made[0]
    assert engine._process is not None
    # Kept loaded for a while for the lesson about to be stored, then let go.
    eventually(lambda: engine._process is None, "the idle engine was closed", seconds=10)


def test_with_no_voice_chosen_nothing_is_warmed_and_nothing_waits(
    keyed: TestClient, voiced: Services, provider: FakeProvider, engines: Engines
) -> None:
    voiced.narration.choose(enabled=False)
    voiced.narration.warm()
    assert voiced.jobs.latest(KIND_VOICE_WARMUP, "kokoro") is None
    _, concept = a_concept(keyed)
    provider.queue(LESSON)
    job_id = keyed.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    done = voiced.jobs.wait(job_id, timeout=60)
    assert done.result["voicing"] is False
    assert engines.made == []
    assert voiced.narration.ready_after() is None


def test_how_long_a_lesson_usually_takes_counts_its_voice(voiced: Services) -> None:
    text = voiced.generation.expected_wait("lesson").seconds
    guess = READY_GUESS_SECONDS["kokoro"]
    assert voiced.narration.ready_after() == guess
    assert text >= guess
    # Once timed here, the time measured counts, as a running mean.
    voiced.narration._warmed_at = 0.0
    voiced.narration._timing.parent.mkdir(parents=True, exist_ok=True)
    voiced.narration._timing.write_text('{"kokoro": 200.0}', encoding="utf-8")
    assert voiced.narration.ready_after() == 200.0
    assert voiced.generation.expected_wait("lesson").seconds >= 200


def test_removing_a_lesson_stops_its_recording(
    client: TestClient, voiced: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.5")
    course = client.post("/v1/courses/sample").json()
    lesson_id = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]["id"]
    started = client.post(f"/v1/lessons/{lesson_id}/narration").json()
    running(voiced, started["id"], lambda job: job.status == "running")
    assert client.delete(f"/v1/lessons/{lesson_id}").status_code == 204
    ended = voiced.jobs.wait(started["id"], timeout=30)
    assert ended.status == "cancelled"
