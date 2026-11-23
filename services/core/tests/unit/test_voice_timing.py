"""Every voice is timed on the computer it runs on (ADR-052): at setup, and by every line it
records; and a voice slower than speech gives a lesson a head start before it is ready.

With the stand-in engine (tests/support/fake_voice_engine.py), which takes
``ADLE_FAKE_VOICE_DELAY`` seconds over each line, as a slower voice would.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adle_core.application.narration import (
    KIND_NARRATION,
    READY_GUESS_SECONDS,
    NarrationService,
)
from adle_core.application.services import Services
from adle_core.voice.catalog import Tier
from adle_core.voice.catalog import tier as find_tier
from adle_core.voice.install import Cancelled, Report, VoiceInstaller
from adle_core.voice.runtime import VoicePaths
from adle_core.voice.timing import (
    LESSON_SPEECH,
    MARGIN,
    SETUP_LINES,
    VoiceTiming,
    kept,
    kept_ahead,
    mean,
    read_timing,
    ready_after,
    speech_of,
)
from tests.unit.test_narration import WITH_CARD, place, set_up

# -- the rules ------------------------------------------------------------------------------


def test_a_voice_faster_than_speech_keeps_ahead_once_anything_can_be_heard() -> None:
    assert kept_ahead(None, 5.0, 150.0)
    assert kept_ahead(0.24, 5.0, 150.0)
    assert kept_ahead(1.0, 5.0, 150.0)


@pytest.mark.parametrize("rate", [1.5, 2.0, 3.0])
def test_a_voice_slower_than_speech_needs_a_head_start_of_its_share_of_the_lesson(
    rate: float,
) -> None:
    lesson = 150.0
    needed = MARGIN * lesson * (1 - 1 / rate)
    assert not kept_ahead(rate, needed - 1, lesson)
    assert kept_ahead(rate, needed, lesson)
    # Checked against a learner listening from the start: with that much recorded, the
    # voice reaches every second of the lesson before the learner does.
    for listened in range(int(lesson) + 1):
        recorded = min(lesson, needed + listened / rate)
        assert recorded >= min(lesson, listened)


def test_how_long_a_lesson_usually_takes_comes_from_this_computer_first() -> None:
    assert ready_after(VoiceTiming(), 30.0) == 30.0
    assert ready_after(VoiceTiming(start=12.0, rate=0.3), 30.0) == 12.0
    # A voice slower than speech: the head start counts, at its rate.
    slow = ready_after(VoiceTiming(start=12.0, rate=2.0), 30.0)
    assert slow == pytest.approx(12.0 + 2.0 * MARGIN * LESSON_SPEECH * 0.5)
    # What lessons made here took beats any estimate.
    assert ready_after(VoiceTiming(ready=41.0, start=12.0, rate=2.0), 30.0) == 41.0


def test_a_timing_is_read_as_it_was_kept_and_as_it_was_kept_before() -> None:
    assert read_timing(44.5) == VoiceTiming(ready=44.5)
    assert read_timing({"ready": 40, "start": 12.5, "rate": 0.39}) == VoiceTiming(
        ready=40.0, start=12.5, rate=0.39
    )
    assert read_timing({"rate": "fast", "start": -3, "ready": True}) == VoiceTiming()
    assert read_timing(None) == VoiceTiming()
    assert kept(VoiceTiming(start=12.34567, rate=0.391)) == {"start": 12.346, "rate": 0.391}
    assert mean(None, 2.0) == 2.0
    assert mean(1.0, 2.0) == pytest.approx(1.4)
    assert speech_of("x" * 140) == pytest.approx(10.0)


# -- at setup ---------------------------------------------------------------------------------


def test_a_voice_is_timed_where_it_is_set_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.2")
    paths = set_up(tmp_path / "voice", "kokoro")
    kokoro = find_tier("kokoro")
    assert kokoro is not None
    timed = VoiceInstaller(paths).verify(kokoro)
    assert timed is not None
    # As much as a lesson's first part, from an engine started cold.
    assert timed["start"] >= 0.2 * len(SETUP_LINES)
    # The last line: its words take 0.3 s each to say, and 0.2 s more to make.
    words = len(SETUP_LINES[-1].replace(",", "").split())
    assert timed["rate"] > 0.2 / (0.3 * words)
    assert not list(paths.root.glob("probe*"))


def test_what_a_setup_timed_is_kept_and_counted_in_how_long_a_lesson_takes(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    class Installer(VoiceInstaller):
        def install(
            self, tier: Tier, report: Report, cancelled: Cancelled
        ) -> dict[str, float] | None:
            place(self._paths, tier)
            return {"start": 12.0, "rate": 2.0}

    paths = set_up(tmp_path / "voice")
    services.narration = NarrationService(
        services.lessons, services.jobs, paths, hardware=lambda: WITH_CARD, installer=Installer
    )
    started = client.post("/v1/voice/setup", json={"tier": "kokoro"})
    assert services.jobs.wait(started.json()["id"], timeout=30).status == "succeeded"
    assert services.narration.timing("kokoro") == VoiceTiming(start=12.0, rate=2.0)
    expected = 12.0 + 2.0 * MARGIN * LESSON_SPEECH * 0.5
    assert services.narration.ready_after() == pytest.approx(expected)
    assert READY_GUESS_SECONDS["kokoro"] < expected


# -- in a lesson ------------------------------------------------------------------------------


def a_lesson(client: TestClient) -> str:
    course = client.post("/v1/courses/sample").json()
    return str(client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]["id"])


def recorded_as_far_as(
    narration: NarrationService, paths: VoicePaths, lesson_id: str, count: int, seconds: float
) -> list[str]:
    """The first ``count`` lines of a lesson as if recorded, each ``seconds`` long."""
    _, voice = narration._voice(lesson_id)
    lines = narration._lines(lesson_id)
    folder = paths.clips / lesson_id
    folder.mkdir(parents=True, exist_ok=True)
    for text in lines[:count]:
        name = narration._name(voice, text)
        (folder / f"{name}.clip").write_bytes(b"")
        (folder / f"{name}.json").write_text(
            json.dumps({"seconds": seconds, "words": [], "tier": "kokoro"}), encoding="utf-8"
        )
    return lines


def test_a_lesson_in_a_voice_slower_than_speech_is_ready_once_it_has_a_head_start(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    paths = set_up(tmp_path / "voice", "kokoro")
    narration = NarrationService(services.lessons, services.jobs, paths, hardware=lambda: WITH_CARD)
    lesson_id = a_lesson(client)
    narration._recording.add(lesson_id)
    first_part = getattr(services.lessons.get_lesson(lesson_id).segments[0], "narration", None)
    lines = recorded_as_far_as(narration, paths, lesson_id, len(first_part or []), 5.0)
    # Faster than speech here: ready once its first part can be heard.
    narration._keep_timing("kokoro", VoiceTiming(rate=0.4))
    assert narration.voice_pending(lesson_id) is False
    # Three times slower than speech: not until two thirds of it, and a little more, are.
    narration._keep_timing("kokoro", VoiceTiming(rate=3.0))
    assert narration.voice_pending(lesson_id) is True
    total = 5.0 * len(lines)
    enough = 0
    while 5.0 * enough < MARGIN * total * (2 / 3):
        enough += 1
    recorded_as_far_as(narration, paths, lesson_id, enough - 1, 5.0)
    assert narration.voice_pending(lesson_id) is True
    recorded_as_far_as(narration, paths, lesson_id, enough, 5.0)
    assert narration.voice_pending(lesson_id) is False


def test_a_lesson_s_recording_times_the_voice_line_by_line(
    client: TestClient, services: Services, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADLE_FAKE_VOICE_DELAY", "0.05")
    paths = set_up(tmp_path / "voice", "kokoro")
    services.narration = NarrationService(
        services.lessons, services.jobs, paths, hardware=lambda: WITH_CARD
    )
    lesson_id = a_lesson(client)
    started = client.post(f"/v1/lessons/{lesson_id}/narration").json()
    assert services.jobs.wait(started["id"], timeout=60).status == "succeeded"
    timing = services.narration.timing("kokoro")
    # Measured from the lines said once loaded: the stand-in is far faster than speech.
    assert timing.rate is not None
    assert 0 < timing.rate < 1
    assert services.jobs.latest(KIND_NARRATION, lesson_id) is not None
    services.narration.close()
