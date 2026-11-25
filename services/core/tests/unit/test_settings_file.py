"""The core's part of a settings file (ADR-064): each setting brought in on its own, and a
voice that is not on this computer set up at the learner's word, replaced by the nearest
one this computer runs, or left to the computer's own voice, and that said."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from adle_core.application.narration import NarrationService
from adle_core.application.services import Services
from adle_core.application.settings_file import SettingsFileService
from adle_core.voice.catalog import DEFAULT_DESIGN
from adle_core.voice.hardware import Hardware
from tests.unit.test_narration import DESKTOP, WITH_CARD, an_installer, set_up

#: A computer no natural voice runs on.
ODD = Hardware(system="linux", machine="riscv64", gpu=None, gpu_memory_gb=None)
EXPRESSIVE = {"enabled": True, "tier": "expressive"}


def a_computer(
    services: Services, tmp_path: Path, *ready: str, hardware: Hardware = WITH_CARD
) -> SettingsFileService:
    """This computer with these voices set up, and the settings file's service on it."""
    paths = set_up(tmp_path / "voice", *ready)
    services.narration = NarrationService(
        services.lessons,
        services.jobs,
        paths,
        hardware=lambda: hardware,
        installer=an_installer(),
    )
    services.settings_file = SettingsFileService(services.learner, services.narration)
    return services.settings_file


def voice_here(client: TestClient) -> tuple[Any, Any]:
    status = client.get("/v1/voice").json()
    return status["tier"], status["enabled"]


# -- what is saved -----------------------------------------------------------------------------


def test_what_is_saved_is_the_preferences_and_the_voice_and_never_a_key(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro", "expressive")
    services.credentials.set_api_key("sk-a-key-that-must-not-be-saved-9Qw2", "aihubmix")
    client.patch("/v1/learner/preferences", json={"pace": "brisk", "volume": 40, "goal": "Pass."})
    client.put("/v1/voice", json={"tier": "kokoro", "speaker": "bf_emma"})
    client.put("/v1/voice", json={"parts": {"speaker": "man", "pace": "slow"}})
    saved = client.get("/v1/settings-file").json()
    assert saved["learning"] == {
        "pace": "brisk",
        "explanation_density": "balanced",
        "narration": True,
        "captions": True,
        "voice": "",
        "volume": 40,
        "goal": "Pass.",
    }
    assert saved["voice"] == {
        "enabled": True,
        "tier": "kokoro",
        "speakers": {"kokoro": "bf_emma"},
        "design": "A man with a clear voice, speaking natural English at a slow pace.",
        "parts": {"speaker": "man", "pace": "slow"},
    }
    assert "sk-a-key" not in json.dumps(saved)


def test_adles_own_voice_is_saved_by_saying_nothing(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path)
    voice = client.get("/v1/settings-file").json()["voice"]
    assert voice == {
        "enabled": False,
        "tier": None,
        "speakers": {"kokoro": "af_heart"},
        "design": "",
        "parts": {},
    }


# -- preferences ---------------------------------------------------------------------------------


def test_preferences_come_back_as_they_were_saved(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path)
    client.patch(
        "/v1/learner/preferences",
        json={
            "pace": "relaxed",
            "explanation_density": "detailed",
            "narration": False,
            "captions": False,
            "voice": "Microsoft Zira",
            "volume": 15,
            "goal": "Understand backpropagation.",
        },
    )
    saved = client.get("/v1/settings-file").json()["learning"]
    client.patch(
        "/v1/learner/preferences",
        json={
            "pace": "standard",
            "explanation_density": "balanced",
            "narration": True,
            "captions": True,
            "voice": "",
            "volume": 100,
            "goal": "",
        },
    )
    brought = client.post("/v1/settings-file", json={"learning": saved})
    assert brought.status_code == 200, brought.text
    assert brought.json() == {"notes": [], "setting_up": None}
    assert client.get("/v1/settings-file").json()["learning"] == saved


def test_each_preference_is_taken_on_its_own_and_one_that_cannot_be_is_left_as_it_is(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path)
    client.patch("/v1/learner/preferences", json={"pace": "brisk", "volume": 70, "goal": "Mine."})
    brought = client.post(
        "/v1/settings-file",
        json={
            "learning": {
                "pace": "warp speed",
                "volume": 400,
                "captions": False,
                "narration": "yes",
                "from_a_later_adle": {"anything": True},
            }
        },
    )
    assert brought.status_code == 200, brought.text
    kept = client.get("/v1/settings-file").json()["learning"]
    # What it may be is taken; what it may not be, and what is not known, changes nothing.
    assert kept["captions"] is False
    assert (kept["pace"], kept["volume"], kept["narration"], kept["goal"]) == (
        "brisk",
        70,
        True,
        "Mine.",
    )
    # A part that is not there changes nothing at all.
    client.post("/v1/settings-file", json={"learning": None, "voice": None})
    assert client.get("/v1/settings-file").json()["learning"] == kept


# -- the voice a file names, on this computer ------------------------------------------------------


def test_a_voice_that_is_here_is_used(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro", "expressive")
    client.put("/v1/voice", json={"enabled": False})
    looked = client.post("/v1/settings-file/look", json={"voice": EXPRESSIVE}).json()["voice"]
    assert looked == {
        "tier": "expressive",
        "name": "Expressive",
        "set_up": False,
        "download_bytes": 0,
        "sources": [],
        "note": "",
    }
    # Looking changed nothing.
    assert voice_here(client) == ("expressive", False)
    brought = client.post("/v1/settings-file", json={"voice": EXPRESSIVE}).json()
    assert brought == {"notes": [], "setting_up": None}
    assert voice_here(client) == ("expressive", True)


def test_a_voice_that_is_not_here_is_set_up_only_at_the_learners_word(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro")
    looked = client.post("/v1/settings-file/look", json={"voice": EXPRESSIVE}).json()["voice"]
    # What setting it up downloads, and from where, is said before anything is brought in.
    assert (looked["tier"], looked["set_up"], looked["note"]) == ("expressive", True, "")
    assert looked["download_bytes"] > 1_000_000_000
    assert "Hugging Face" in looked["sources"]

    # Not asked to: nothing is downloaded, and the voice in use stays.
    declined = client.post(
        "/v1/settings-file", json={"voice": EXPRESSIVE, "set_up_voice": False}
    ).json()
    assert declined["setting_up"] is None
    assert declined["notes"] == [
        "The Expressive voice isn’t set up on this computer. Set it up in Settings to use it."
    ]
    assert voice_here(client) == ("kokoro", True)
    assert client.get("/v1/voice").json()["setting_up"] is None

    # Asked to: it is set up in the background, and reads the lessons once it is ready.
    accepted = client.post(
        "/v1/settings-file", json={"voice": EXPRESSIVE, "set_up_voice": True}
    ).json()
    assert accepted["notes"] == [
        "The Expressive voice is being set up. Lessons are read in it once it is ready."
    ]
    job = services.jobs.wait(accepted["setting_up"]["id"], timeout=30)
    assert (job.kind, job.status, job.subject_id) == ("voice_setup", "succeeded", "expressive")
    assert voice_here(client) == ("expressive", True)


def test_a_voice_this_computer_cannot_run_becomes_the_nearest_one_it_can(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    # No graphics card here: the Expressive voice cannot run. The Natural voice is set up.
    a_computer(services, tmp_path, "kokoro", hardware=DESKTOP)
    client.put("/v1/voice", json={"enabled": False})
    note = "The Expressive voice can’t run on this computer, so the Natural voice is used."
    looked = client.post("/v1/settings-file/look", json={"voice": EXPRESSIVE}).json()["voice"]
    assert (looked["tier"], looked["set_up"], looked["note"]) == ("kokoro", False, note)
    brought = client.post("/v1/settings-file", json={"voice": EXPRESSIVE}).json()
    assert brought == {"notes": [note], "setting_up": None}
    assert voice_here(client) == ("kokoro", True)


def test_the_nearest_voice_is_set_up_too_when_it_is_not_here(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, hardware=DESKTOP)
    looked = client.post("/v1/settings-file/look", json={"voice": EXPRESSIVE}).json()["voice"]
    assert (looked["tier"], looked["name"], looked["set_up"]) == ("kokoro", "Natural", True)
    assert 0 < looked["download_bytes"] < 1_000_000_000
    brought = client.post(
        "/v1/settings-file", json={"voice": EXPRESSIVE, "set_up_voice": True}
    ).json()
    assert brought["notes"] == [
        "The Expressive voice can’t run on this computer, so the Natural voice is used.",
        "The Natural voice is being set up. Lessons are read in it once it is ready.",
    ]
    job = services.jobs.wait(brought["setting_up"]["id"], timeout=30)
    assert (job.status, job.subject_id) == ("succeeded", "kokoro")
    assert voice_here(client) == ("kokoro", True)


def test_where_no_voice_runs_the_computers_own_reads(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, hardware=ODD)
    note = "The Expressive voice can’t run on this computer, so the computer’s voice is used."
    looked = client.post("/v1/settings-file/look", json={"voice": EXPRESSIVE}).json()["voice"]
    assert looked == {
        "tier": None,
        "name": None,
        "set_up": False,
        "download_bytes": 0,
        "sources": [],
        "note": note,
    }
    brought = client.post(
        "/v1/settings-file", json={"voice": EXPRESSIVE, "set_up_voice": True}
    ).json()
    assert brought == {"notes": [note], "setting_up": None}
    assert voice_here(client) == (None, False)


def test_a_file_that_says_the_computers_voice_turns_the_natural_voice_off(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro")
    assert voice_here(client) == ("kokoro", True)
    looked = client.post("/v1/settings-file/look", json={"voice": {"enabled": False}}).json()
    assert (looked["voice"]["tier"], looked["voice"]["note"]) == (None, "")
    client.post("/v1/settings-file", json={"voice": {"enabled": False, "tier": "expressive"}})
    assert voice_here(client) == ("kokoro", False)


def test_a_voice_this_adle_does_not_know_leaves_the_voice_here_as_it_is(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro")
    for unknown in ({"tier": "standard"}, {"tier": 7}, {"tier": "../../x"}, {}):
        assert client.post("/v1/settings-file/look", json={"voice": unknown}).json() == {
            "voice": None
        }
        brought = client.post("/v1/settings-file", json={"voice": unknown, "set_up_voice": True})
        assert brought.json() == {"notes": [], "setting_up": None}
        assert voice_here(client) == ("kokoro", True)
    assert client.post("/v1/settings-file/look", json={}).json() == {"voice": None}


def test_who_speaks_comes_too_whether_or_not_that_voice_runs_here(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    a_computer(services, tmp_path, "kokoro", hardware=DESKTOP)
    brought = client.post(
        "/v1/settings-file",
        json={
            "voice": {
                "enabled": True,
                "tier": "kokoro",
                "speakers": {"kokoro": "bf_emma", "expressive": "nobody", "standard": "Aiden"},
                "parts": {"speaker": "woman", "feeling": "calm"},
                "design": "ignored when there are parts",
            }
        },
    ).json()
    assert brought["notes"] == []
    status = client.get("/v1/voice").json()
    assert status["speakers"] == {"kokoro": "bf_emma"}
    assert status["design_parts"] == {"speaker": "woman", "feeling": "calm"}
    assert status["design"].startswith("A calm woman with a clear voice")

    # In the learner's own words; and Adle's own, which a file says by saying nothing.
    client.post("/v1/settings-file", json={"voice": {"design": "A deep, slow voice."}})
    assert client.get("/v1/voice").json()["design"] == "A deep, slow voice."
    client.post("/v1/settings-file", json={"voice": {"design": "", "parts": {}}})
    assert client.get("/v1/voice").json()["design"] == DEFAULT_DESIGN

    # A description that cannot be one is said, and the voice's stays as it was.
    for wrong in ({"parts": {"speaker": "robot"}}, {"design": "As on https://example.com"}):
        refused = client.post("/v1/settings-file", json={"voice": wrong}).json()
        assert refused["notes"] == [
            "The Expressive voice’s description couldn’t be used, so it is as it was."
        ]
        assert client.get("/v1/voice").json()["design"] == DEFAULT_DESIGN


def test_a_voice_already_being_set_up_is_said_and_nothing_fails(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    import threading

    held = threading.Event()
    paths = set_up(tmp_path / "voice")
    services.narration = NarrationService(
        services.lessons,
        services.jobs,
        paths,
        hardware=lambda: WITH_CARD,
        installer=an_installer(held=held),
    )
    services.settings_file = SettingsFileService(services.learner, services.narration)
    try:
        first = client.post("/v1/voice/setup", json={"tier": "kokoro"})
        assert first.status_code == 202
        brought = client.post(
            "/v1/settings-file", json={"voice": EXPRESSIVE, "set_up_voice": True}
        ).json()
        assert brought["setting_up"] is None
        assert brought["notes"] == [
            "The Expressive voice couldn’t be set up now. "
            "Another voice is being set up. Wait for it, or stop it."
        ]
    finally:
        held.set()
        services.jobs.wait(first.json()["id"], timeout=30)


# -- the routes: only the desktop shell's ----------------------------------------------------------


def test_none_of_it_is_open_to_the_page_and_none_of_it_takes_a_path_or_a_key(
    client: TestClient,
) -> None:
    from adle_core.api.app import create_app

    document = create_app(client.app.state.services).openapi()  # type: ignore[attr-defined]
    found = {
        operation["operationId"]: operation.get("x-adle-internal")
        for methods in document["paths"].values()
        for operation in methods.values()
        if operation["operationId"].startswith("settings.")
    }
    assert found == {
        "settings.save_file": True,
        "settings.look_at_file": True,
        "settings.bring_in_file": True,
    }
    schemas = json.dumps(
        {
            name: schema
            for name, schema in document["components"]["schemas"].items()
            if name.startswith("Settings") or name in {"CoreSettings", "VoicePlan"}
        }
    )
    for word in ("path", "api_key", "password"):
        assert word not in schemas.lower(), word


def test_what_is_asked_is_bounded(client: TestClient) -> None:
    many = {f"setting_{index}": index for index in range(25)}
    assert client.post("/v1/settings-file", json={"learning": many}).status_code == 422
    assert client.post("/v1/settings-file", json={"learning": {"x" * 61: 1}}).status_code == 422
    assert client.post("/v1/settings-file", json={"keys": {}}).status_code == 422
    assert client.post("/v1/settings-file/look", json={"voice": [1]}).status_code == 422
    assert client.post("/v1/settings-file", json={"set_up_voice": "yes"}).status_code == 422
