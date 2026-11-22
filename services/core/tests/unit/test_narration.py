"""A lesson's narration in a natural voice, recorded on this computer (ADR-042).

With a stand-in for the engine (tests/support/fake_voice_engine.py): the same protocol, no
models, nothing downloaded and no graphics card.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.narration import KIND_NARRATION, NarrationService
from adle_core.application.services import Services
from adle_core.voice.catalog import ALIGNER, DEFAULT_DESIGN, TIERS, Tier
from adle_core.voice.catalog import tier as find_tier
from adle_core.voice.engine import spoken_number, words_of
from adle_core.voice.hardware import Hardware, fit, nvidia_card
from adle_core.voice.install import Cancelled, Report, VoiceInstaller, VoiceSetupError
from adle_core.voice.runtime import SETUP_MARK, VoiceEngine, VoicePaths, setup_mark

FAKE_ENGINE = Path(__file__).resolve().parents[1] / "support" / "fake_voice_engine.py"
DESKTOP = Hardware(system="win32", machine="amd64", gpu=None, gpu_memory_gb=None)
WITH_CARD = Hardware(
    system="win32", machine="amd64", gpu="NVIDIA GeForce RTX 4080", gpu_memory_gb=12.0
)


def place(paths: VoicePaths, tier: Tier) -> None:
    """A size of voice on disk as an installation leaves it: its models (empty here), the
    aligner if it needs it, and the mark that its programs are this Adle's."""
    for repo in tier.repos:
        for file in repo.files:
            path = paths.models / repo.folder / file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
    if tier.aligned:
        paths.aligner_file().parent.mkdir(parents=True, exist_ok=True)
        paths.aligner_file().write_bytes(b"")
    mark = setup_mark(tier.family)
    assert mark is not None
    paths.environment(tier.family).mkdir(parents=True, exist_ok=True)
    (paths.environment(tier.family) / SETUP_MARK).write_text(json.dumps(mark), "utf-8")


def set_up(root: Path, *tiers: str) -> VoicePaths:
    """A voice of these sizes on disk, as an installation leaves it, spoken by the stand-in."""
    python = Path(sys.executable)
    paths = VoicePaths(
        root=root,
        pythons={"kokoro": python, "qwen": python},
        models=root / "models",
        aligner=root / "aligner",
        engine=FAKE_ENGINE,
        clips=root / "clips",
        borrowed=False,
    )
    for tier_id in tiers:
        chosen = find_tier(tier_id)
        assert chosen is not None
        place(paths, chosen)
    assert Path(ALIGNER.path).name == paths.aligner_file().name
    return paths


@pytest.fixture
def voiced(services: Services, tmp_path: Path) -> Services:
    """The services, with a natural voice of every size set up."""
    paths = set_up(tmp_path / "voice", "kokoro", "standard", "expressive")
    services.narration = NarrationService(
        services.lessons, services.jobs, paths, hardware=lambda: WITH_CARD
    )
    return services


def a_lesson(client: TestClient) -> dict[str, Any]:
    """The first lesson of a newly installed sample course: its id, its course, and itself."""
    course = client.post("/v1/courses/sample").json()
    listed = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    view = client.get(f"/v1/lessons/{listed[0]['id']}").json()
    return {"id": listed[0]["id"], "course_id": course["id"], "lesson": view["lesson"]}


def lines_of(lesson: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for segment in lesson["lesson"]["segments"]:
        for beat in segment.get("narration") or []:
            if beat["text"] not in found:
                found.append(beat["text"])
    return found


def record(client: TestClient, services: Services, lesson_id: str) -> Any:
    response = client.post(f"/v1/lessons/{lesson_id}/narration")
    assert response.status_code == 202, response.text
    return services.jobs.wait(response.json()["id"], timeout=60)


# -- what fits this computer ------------------------------------------------------------------


def test_each_size_says_what_it_needs_and_the_richest_that_fits_is_offered() -> None:
    kokoro, standard, expressive = TIERS
    assert [tier.id for tier in TIERS] == ["kokoro", "standard", "expressive"]
    assert fit(kokoro, DESKTOP).fits
    assert not fit(standard, DESKTOP).fits
    assert fit(standard, DESKTOP).why == "It needs an NVIDIA graphics card."
    small = Hardware(system="linux", machine="x86_64", gpu="Small card", gpu_memory_gb=6.0)
    assert fit(standard, small).fits
    assert fit(expressive, small).why == (
        "It needs an NVIDIA graphics card with 8 GB of memory; this one has 6 GB."
    )
    assert fit(expressive, WITH_CARD).fits
    mac = Hardware(system="darwin", machine="arm64", gpu=None, gpu_memory_gb=None)
    assert fit(kokoro, mac).fits
    assert "can’t use" in fit(expressive, mac).why
    intel_mac = Hardware(system="darwin", machine="x86_64", gpu=None, gpu_memory_gb=None)
    assert not fit(kokoro, intel_mac).fits


def test_the_card_is_read_from_its_drivers_own_tool() -> None:
    def answered(stdout: str, code: int = 0) -> Any:
        def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], code, stdout=stdout, stderr="")

        return run

    def there(name: str) -> str:
        return "nvidia-smi"

    found = nvidia_card(answered("NVIDIA GeForce RTX 4080 Laptop GPU, 12282\n"), there)
    assert found == ("NVIDIA GeForce RTX 4080 Laptop GPU", 12.0)
    assert nvidia_card(answered("", 9), there) is None
    assert nvidia_card(answered("garbled"), there) is None
    assert nvidia_card(answered("x, 1"), lambda name: None) is None


# -- what is said, and where its words are -------------------------------------------------


def test_a_number_is_found_as_it_is_said() -> None:
    assert spoken_number("2") == "two"
    assert spoken_number("0.5") == "zero point five"
    assert spoken_number("42") == "forty two"
    assert spoken_number("1300") == "one thousand three hundred"
    assert spoken_number("123456") == "one two three four five six"
    text = "Add 0.5 to the weight’s value."
    assert [text[index : index + length] for index, length, _ in words_of(text)] == [
        "Add",
        "0.5",
        "to",
        "the",
        "weight’s",
        "value",
    ]


# -- the voice, chosen ---------------------------------------------------------------------


def test_without_a_voice_lessons_are_read_as_before(client: TestClient) -> None:
    status = client.get("/v1/voice").json()
    assert (status["tier"], status["enabled"]) == (None, False)
    assert [tier["ready"] for tier in status["tiers"]] == [False, False, False]
    lesson = a_lesson(client)
    assert client.get(f"/v1/lessons/{lesson['id']}/narration").json() == {
        "lines": [],
        "recording": None,
    }
    refused = client.post(f"/v1/lessons/{lesson['id']}/narration")
    assert refused.json()["error"]["code"] == "voice_unavailable"


def test_the_richest_voice_here_reads_the_lessons_and_any_can_be_chosen(
    client: TestClient, voiced: Services
) -> None:
    status = client.get("/v1/voice").json()
    assert [tier["id"] for tier in status["tiers"]] == ["kokoro", "standard", "expressive"]
    assert all(tier["ready"] and tier["fits"] for tier in status["tiers"])
    assert (status["tier"], status["enabled"], status["recommended"]) == (
        "expressive",
        True,
        "expressive",
    )
    assert status["speakers"] == {"kokoro": "af_heart", "standard": "Aiden"}
    assert status["gpu"] == "NVIDIA GeForce RTX 4080"
    kokoro = status["tiers"][0]
    assert kokoro["min_memory_gb"] is None
    assert [speaker["name"] for speaker in kokoro["speakers"]][:2] == ["Heart", "Bella"]
    assert status["tiers"][2]["speakers"] == []

    chosen = client.put("/v1/voice", json={"tier": "kokoro", "speaker": "bf_emma"}).json()
    assert (chosen["tier"], chosen["speakers"]["kokoro"]) == ("kokoro", "bf_emma")
    off = client.put("/v1/voice", json={"enabled": False}).json()
    assert (off["tier"], off["enabled"]) == ("kokoro", False)
    # A voice of another size, or of none, is not one of this size's.
    assert client.put("/v1/voice", json={"tier": "kokoro", "speaker": "Aiden"}).status_code == 404
    assert client.put("/v1/voice", json={"speaker": "nobody"}).status_code == 404
    assert client.put("/v1/voice", json={"tier": "huge"}).status_code == 422
    assert client.put("/v1/voice", json={"enabled": "yes"}).status_code == 422


# -- recording a lesson --------------------------------------------------------------------


def test_each_line_of_a_lesson_is_recorded_once_with_where_its_words_are(
    client: TestClient, voiced: Services
) -> None:
    client.put("/v1/voice", json={"tier": "kokoro"})
    lesson = a_lesson(client)
    job = record(client, voiced, lesson["id"])
    assert job.status == "succeeded", job.error_message
    expected = lines_of(lesson)
    assert job.result["lines"] == len(expected)

    narration = client.get(f"/v1/lessons/{lesson['id']}/narration").json()
    assert narration["recording"] is None
    assert [line["text"] for line in narration["lines"]] == expected
    first = narration["lines"][0]
    words = first["words"]
    assert [first["text"][word["index"] : word["index"] + word["length"]] for word in words] == [
        first["text"][index : index + length] for index, length, _ in words_of(first["text"])
    ]
    assert first["seconds"] > 0

    clip = client.get(f"/v1/lessons/{lesson['id']}/narration/{first['clip']}").json()
    assert clip["mime"] == "audio/wav"
    assert base64.b64decode(clip["data"]).startswith(b"RIFF")

    # Asked again, nothing is recorded twice.
    again = record(client, voiced, lesson["id"])
    assert again.result["recorded"] == 0


def recorded_lines(client: TestClient, lesson_id: str, expected: int) -> list[str]:
    """The lines recorded for a lesson, once there are as many as expected (or a minute)."""
    for _ in range(600):
        narration = client.get(f"/v1/lessons/{lesson_id}/narration").json()
        if len(narration["lines"]) >= expected and narration["recording"] is None:
            break
        threading.Event().wait(0.1)
    return [line["text"] for line in narration["lines"]]


def test_a_lesson_is_recorded_as_soon_as_it_is_stored_when_a_voice_reads_the_lessons(
    client: TestClient, voiced: Services
) -> None:
    client.put("/v1/voice", json={"tier": "kokoro"})
    lesson = a_lesson(client)
    voiced.narration.record_ahead(lesson["id"])
    # Recorded without the lesson being opened: its clips are there when it is.
    assert recorded_lines(client, lesson["id"], len(lines_of(lesson))) == lines_of(lesson)


def test_without_a_voice_nothing_is_recorded_ahead(client: TestClient, services: Services) -> None:
    lesson = a_lesson(client)
    services.narration.record_ahead(lesson["id"])
    assert services.jobs.find_active(KIND_NARRATION, lesson["id"]) is None
    assert client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"] == []


def test_a_line_is_recorded_again_in_another_voice_and_never_played_in_the_old_one(
    client: TestClient, voiced: Services
) -> None:
    client.put("/v1/voice", json={"tier": "kokoro"})
    lesson = a_lesson(client)
    record(client, voiced, lesson["id"])
    assert client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"]
    client.put("/v1/voice", json={"speaker": "am_michael"})
    assert client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"] == []
    record(client, voiced, lesson["id"])
    lines = client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"]
    assert len(lines) == len(lines_of(lesson))


def test_a_clip_is_named_by_the_core_and_never_by_a_path(
    client: TestClient, voiced: Services
) -> None:
    lesson = a_lesson(client)
    # (A name with a slash in it, or "..", never reaches this route: the address is read
    # before it does.)
    for name in (
        "preferences.json",
        "..%2Fpreferences",
        "ABCDEF0123456789abcdef01",
        "x" * 25,
    ):
        response = client.get(f"/v1/lessons/{lesson['id']}/narration/{name}")
        assert response.status_code == 404, name
    response = client.get(f"/v1/lessons/not-a-lesson/narration/{'a' * 24}")
    assert response.status_code == 404


def test_a_lesson_that_goes_takes_its_recordings_with_it(
    client: TestClient, voiced: Services, tmp_path: Path
) -> None:
    client.put("/v1/voice", json={"tier": "standard"})
    lesson = a_lesson(client)
    record(client, voiced, lesson["id"])
    folder = tmp_path / "voice" / "clips" / lesson["id"]
    assert any(folder.iterdir())
    assert client.delete(f"/v1/lessons/{lesson['id']}").status_code == 204
    assert not folder.exists()

    # And a course that goes takes those of all its lessons.
    other = a_lesson(client)
    record(client, voiced, other["id"])
    assert client.delete(f"/v1/courses/{other['course_id']}").status_code == 204
    assert not (tmp_path / "voice" / "clips" / other["id"]).exists()


def test_the_expressive_voice_is_designed_from_what_the_lesson_says_of_its_narrator(
    client: TestClient, voiced: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put("/v1/voice", json={"tier": "expressive"})
    lesson = a_lesson(client)
    asked: list[dict[str, Any]] = []
    speak = VoiceEngine.speak

    def heard(self: VoiceEngine, text: str, voice: dict[str, Any], *rest: Any, **named: Any) -> Any:
        asked.append(dict(voice))
        return speak(self, text, voice, *rest, **named)

    monkeypatch.setattr(VoiceEngine, "speak", heard)
    record(client, voiced, lesson["id"])
    # The sample course's lessons say nothing of their narrator: Adle's own voice.
    assert {entry["design"] for entry in asked} == {DEFAULT_DESIGN}

    stored = voiced.lessons.get_lesson
    monkeypatch.setattr(
        voiced.lessons,
        "get_lesson",
        lambda lesson_id: stored(lesson_id).model_copy(update={"voice": "A bright, quick voice."}),
    )
    # Another voice: nothing recorded in the old one is played.
    assert client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"] == []
    asked.clear()
    record(client, voiced, lesson["id"])
    assert {entry["design"] for entry in asked} == {"A bright, quick voice."}
    # Designed once, for this lesson, and kept beside its recordings.
    (reference,) = {entry["reference"] for entry in asked}
    assert Path(reference).parent.name == lesson["id"]
    lines = client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"]
    assert len(lines) == len(lines_of(lesson))


def test_a_line_the_voice_cannot_say_fails_the_recording_and_is_said_plainly(
    client: TestClient, voiced: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    lesson = a_lesson(client)
    original = NarrationService._lines

    def with_a_bad_line(self: NarrationService, lesson_id: str) -> list[str]:
        return ["This line FAILs.", *original(self, lesson_id)]

    monkeypatch.setattr(NarrationService, "_lines", with_a_bad_line)
    job = record(client, voiced, lesson["id"])
    assert (job.status, job.error_code) == ("failed", "voice_failed")
    assert job.error_message == "The natural voice couldn’t speak this."


# -- setting a size up, and taking it away -------------------------------------------------


def an_installer(
    *, held: threading.Event | None = None, failure: str | None = None
) -> Callable[[VoicePaths], VoiceInstaller]:
    """Sets a size up as an installation leaves it, fetching nothing. ``held``: it waits until
    that is set, or until it is stopped. ``failure``: it fails, saying this."""

    class Installer(VoiceInstaller):
        def install(self, tier: Tier, report: Report, cancelled: Cancelled) -> None:
            report("Downloading the voice", 1, 4)
            while held is not None and not held.wait(0.05):
                if cancelled():
                    raise VoiceSetupError("Stopped.")
            if failure is not None:
                raise VoiceSetupError(failure)
            place(self._paths, tier)
            report("Trying the voice", 1, 1)

    return Installer


def with_voice(
    services: Services,
    tmp_path: Path,
    *tiers: str,
    hardware: Hardware = WITH_CARD,
    installer: Callable[[VoicePaths], VoiceInstaller] | None = None,
) -> VoicePaths:
    paths = set_up(tmp_path / "voice", *tiers)
    services.narration = NarrationService(
        services.lessons,
        services.jobs,
        paths,
        hardware=lambda: hardware,
        installer=installer or an_installer(),
    )
    return paths


def test_a_size_is_set_up_in_the_background_and_then_reads_the_lessons(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    with_voice(services, tmp_path, "kokoro")
    started = client.post("/v1/voice/setup", json={"tier": "expressive"})
    assert started.status_code == 202, started.text
    job = services.jobs.wait(started.json()["id"], timeout=30)
    assert (job.kind, job.status, job.subject_id) == ("voice_setup", "succeeded", "expressive")
    status = client.get("/v1/voice").json()
    assert [tier["ready"] for tier in status["tiers"]] == [True, False, True]
    assert (status["tier"], status["enabled"], status["setting_up"]) == ("expressive", True, None)
    # What each size takes to set up is said before it is: its models, and its programs.
    assert all(tier["model_bytes"] > 0 and tier["program_bytes"] > 0 for tier in status["tiers"])


def test_one_size_is_set_up_at_a_time_and_a_setup_can_be_stopped(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    held = threading.Event()
    with_voice(services, tmp_path, installer=an_installer(held=held))
    first = client.post("/v1/voice/setup", json={"tier": "standard"}).json()
    try:
        # Asked again, it is the same setup; another size waits for it.
        assert client.post("/v1/voice/setup", json={"tier": "standard"}).json()["id"] == first["id"]
        other = client.post("/v1/voice/setup", json={"tier": "expressive"})
        assert other.status_code == 409
        assert other.json()["error"]["message"] == (
            "Another voice is being set up. Wait for it, or stop it."
        )
        setting_up = client.get("/v1/voice").json()["setting_up"]
        assert (setting_up["id"], setting_up["subject_id"]) == (first["id"], "standard")
        # Nothing is taken away while a voice is being set up.
        assert client.delete("/v1/voice/kokoro").status_code == 409
        assert client.post(f"/v1/jobs/{first['id']}/cancel").status_code == 200
        stopped = services.jobs.wait(first["id"], timeout=30)
        assert stopped.status == "cancelled"
    finally:
        held.set()
    status = client.get("/v1/voice").json()
    assert (status["setting_up"], status["tier"]) == (None, None)


def test_a_size_this_computer_cannot_run_is_not_set_up(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    with_voice(services, tmp_path, hardware=DESKTOP)
    refused = client.post("/v1/voice/setup", json={"tier": "standard"})
    assert refused.status_code == 409
    assert refused.json()["error"]["message"] == "It needs an NVIDIA graphics card."
    assert client.post("/v1/voice/setup", json={"tier": "huge"}).status_code == 422
    assert client.post("/v1/voice/setup", json={"tier": "kokoro", "x": 1}).status_code == 422


def test_a_setup_that_fails_says_why(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    why = "Couldn’t download the voice. Check the connection and try again."
    with_voice(services, tmp_path, installer=an_installer(failure=why))
    job = services.jobs.wait(
        client.post("/v1/voice/setup", json={"tier": "kokoro"}).json()["id"], timeout=30
    )
    assert (job.status, job.error_code, job.error_message) == ("failed", "voice_setup_failed", why)
    assert client.get("/v1/voice").json()["tier"] is None


def test_a_voice_set_up_by_hand_is_never_set_up_or_taken_away_from_here(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    paths = with_voice(services, tmp_path, "kokoro")
    services.narration = NarrationService(
        services.lessons,
        services.jobs,
        dataclasses.replace(paths, borrowed=True),
        hardware=lambda: WITH_CARD,
    )
    for response in (
        client.post("/v1/voice/setup", json={"tier": "standard"}),
        client.delete("/v1/voice/kokoro"),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["message"] == (
            "The voice here was set up by hand, and is used as it is."
        )


def test_taking_a_size_away_takes_what_it_recorded_and_leaves_the_others(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    paths = with_voice(services, tmp_path, "kokoro", "standard")
    lesson = a_lesson(client)
    client.put("/v1/voice", json={"tier": "kokoro"})
    record(client, services, lesson["id"])
    client.put("/v1/voice", json={"tier": "standard"})
    record(client, services, lesson["id"])
    folder = paths.clips / lesson["id"]
    assert len(list(folder.glob("*.clip"))) == 2 * len(lines_of(lesson))

    status = client.delete("/v1/voice/standard").json()
    assert [tier["ready"] for tier in status["tiers"]] == [True, False, False]
    # The voice that is left reads the lessons, and what it recorded is still there.
    assert (status["tier"], status["enabled"]) == ("kokoro", True)
    assert len(list(folder.glob("*.clip"))) == len(lines_of(lesson))
    lines = client.get(f"/v1/lessons/{lesson['id']}/narration").json()["lines"]
    assert len(lines) == len(lines_of(lesson))
    assert not (paths.models / "Qwen3-TTS-12Hz-0.6B-CustomVoice").exists()
    assert not paths.environment("qwen").exists()
    assert client.delete("/v1/voice/huge").status_code == 404
