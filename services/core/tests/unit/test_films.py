"""A film of a whole course (ADR-065), made with the stand-in engine and provider.

The engine here is ``tests/support/fake_film_engine.py``: ManimGX's command line and report,
with nothing drawn, and a small real video handed back for a render. The provider is the
scripted one; its default answer for a chapter is ``fixtures/model-answers/film-chapter.py``,
which passes the rules and runs clean in the real engine. No request leaves the process.
"""

from __future__ import annotations

import base64
import sys
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from adle_core.api.app import create_app
from adle_core.application.films import FilmService
from adle_core.application.narration import NarrationService
from adle_core.application.services import Services
from adle_core.film.runtime import FilmPaths
from adle_core.infrastructure.orm import Film, ModelUsage
from tests.support.model import FILM_CHAPTER, FakeProvider, pictures_of
from tests.unit.test_narration import WITH_CARD, set_up

KEY = "sk-test-0123456789abcdefghijklmnop"
NVIDIA_KEY = "nvapi-test-0000000000000000000000000000"
#: The model that sees pictures (ADR-060, ADR-066).
SUPER_VL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
SUPPORT = Path(__file__).resolve().parents[1] / "support"
FAKE_ENGINE = SUPPORT / "fake_film_engine.py"
VIDEO = (SUPPORT / "film.mp4").read_bytes()

#: Refused by the rules before anything of it runs.
REFUSED = "import os\nimport manimgx as m\n\n\nclass Chapter(m.Scene):\n    def construct(self):\n        os.system('x')\n"


def marked(mark: str) -> str:
    """The good chapter, with a comment asking the stand-in engine for trouble."""
    return FILM_CHAPTER.replace(
        '        self.say("Each square is one square unit',
        f'        # fake: {mark}\n        self.say("Each square is one square unit',
    )


def paths_in(root: Path) -> FilmPaths:
    """A film maker "set up by hand": the core's own Python, running the stand-in."""
    return FilmPaths(
        root=root / "film-engine",
        python=Path(sys.executable),
        engine=FAKE_ENGINE,
        borrowed=True,
        work=root / "film-work",
        films=root / "films",
    )


def film_service(services: Services, paths: FilmPaths) -> FilmService:
    return FilmService(
        services.database,
        services.jobs,
        services.gateway,
        services.curriculum,
        services.generation,
        services.narration,
        paths,
        handover_dir=services.settings.handover_dir,
    )


@pytest.fixture
def filming(services: Services, tmp_path: Path) -> Services:
    services.films = film_service(services, paths_in(tmp_path))
    return services


@pytest.fixture
def keyed(client: TestClient, filming: Services) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


@pytest.fixture
def seeing(client: TestClient, filming: Services) -> TestClient:
    """NVIDIA NIM chosen, with a key: its chapters are looked over by a model that sees
    pictures (ADR-066)."""
    filming.credentials.set_api_key(NVIDIA_KEY, "nvidia")
    filming.gateway.select("nvidia")
    return client


def a_course(client: TestClient, *titles: str) -> str:
    course = client.post(
        "/v1/courses",
        json={"title": "Area and volume", "origin": "topic", "topic": "Measuring shapes."},
    ).json()
    for title in titles:
        response = client.post(
            f"/v1/courses/{course['id']}/concepts",
            json={
                "title": title,
                "summary": f"What {title.lower()} is.",
                "objectives": [f"Find {title.lower()} by counting.", "Say why it works."],
            },
        )
        assert response.status_code in (200, 201), response.text
    return str(course["id"])


def made(services: Services, client: TestClient, course_id: str) -> dict[str, Any]:
    started = client.post(f"/v1/courses/{course_id}/film")
    assert started.status_code == 202, started.text
    job = services.jobs.wait(started.json()["id"], timeout=60)
    assert job.status == "succeeded", (job.error_code, job.error_message)
    film = client.get(f"/v1/courses/{course_id}/film").json()["film"]
    assert film is not None
    return dict(film)


def eventually(check: Callable[[], bool], what: str, seconds: float = 30.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if check():
            return
        threading.Event().wait(0.05)
    raise AssertionError(f"never: {what}")


def test_a_film_is_a_chapter_a_concept_each_written_checked_and_put_together(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area", "Volume")
    plan = keyed.get(f"/v1/courses/{course}/film").json()["plan"]
    # AIHubMix alone has no model that sees pictures: nothing is looked over (ADR-066).
    assert plan == {
        "chapters": ["Area", "Volume"],
        "requests_at_most": 8,
        "voice": None,
        "blocked": None,
        "checks_pictures": False,
    }

    film = made(filming, keyed, course)

    # One request a chapter: each ran clean the first time.
    assert provider.kinds() == ["film", "film"]
    assert "Write chapter 1 of 2" in provider.prompt(0)
    assert "Write chapter 2 of 2" in provider.prompt(1)
    assert film["status"] == "ready"
    assert [chapter["state"] for chapter in film["chapters"]] == ["written", "written"]
    starts = [chapter["start"] for chapter in film["chapters"]]
    assert starts[0] is not None
    assert 0 < starts[0] < starts[1]
    assert film["seconds"] > starts[1]
    assert film["written_by"]["models"]
    # Without a natural voice it is quiet, and says so.
    assert film["voice"] is None
    assert any("no voice" in note for note in film["notes"])

    part = keyed.get(f"/v1/films/{film['id']}/video/0").json()
    assert (part["part"], part["parts"], part["size"], part["mime"]) == (
        0,
        1,
        len(VIDEO),
        "video/mp4",
    )
    assert base64.b64decode(part["data"]) == VIDEO
    assert keyed.get(f"/v1/films/{film['id']}/video/1").status_code == 404
    cues = keyed.get(f"/v1/films/{film['id']}/captions").json()["cues"]
    assert cues[0]["text"] == "This film goes through Area and volume, in 2 chapters."
    assert "How much floor does a rug cover? Let us count it." in [cue["text"] for cue in cues]
    # Its work is not kept once it is made.
    assert not (filming.films._paths.work / film["id"]).exists()


def test_a_film_of_one_chapter_says_so(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    film = made(filming, keyed, course)
    cues = keyed.get(f"/v1/films/{film['id']}/captions").json()["cues"]
    assert cues[0]["text"] == "This film goes through Area and volume, in one chapter."


def test_a_chapter_is_sent_back_with_what_the_rules_and_the_engine_found(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    provider.queue(REFUSED, marked("overlap"), FILM_CHAPTER)

    film = made(filming, keyed, course)

    assert provider.kinds() == ["film", "film", "film"]
    # Told what the rules refused, with the file it wrote.
    assert "Import only" in provider.prompt(1)
    assert "os.system" in provider.prompt(1)
    # Then told what the engine saw, by the line of its own file.
    assert "overlaps title" in provider.prompt(2)
    assert film["chapters"][0] == {
        "title": "Area",
        "state": "written",
        "problems": 0,
        "start": film["chapters"][0]["start"],
    }


def test_a_chapter_still_wrong_after_its_mends_is_kept_at_its_best_and_said(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    provider.queue(*[marked("overlap")] * 4)

    film = made(filming, keyed, course)

    # Asked once, and mended three times: never more.
    assert provider.kinds() == ["film"] * 4
    assert film["chapters"][0]["state"] == "written"
    assert film["chapters"][0]["problems"] == 1
    assert any("lie over others" in note for note in film["notes"])


def test_a_chapter_no_version_of_which_runs_is_told_in_words(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area", "Volume")
    provider.queue(REFUSED, marked("stop"), REFUSED, marked("stop"))

    film = made(filming, keyed, course)

    assert provider.kinds() == ["film"] * 5
    assert [chapter["state"] for chapter in film["chapters"]] == ["in_words", "written"]
    assert any("told in words" in note for note in film["notes"])
    cues = [cue["text"] for cue in keyed.get(f"/v1/films/{film['id']}/captions").json()["cues"]]
    assert "Find area by counting." in cues


def test_a_chapter_is_not_blamed_for_a_film_maker_that_starts_cold(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    # The first run in an empty engine home is slow while the graphics driver compiles its
    # shaders into it (2026-11-25); the next finds them kept.
    filming.films = FilmService(
        filming.database,
        filming.jobs,
        filming.gateway,
        filming.curriculum,
        filming.generation,
        filming.narration,
        filming.films._paths,
        handover_dir=filming.settings.handover_dir,
        inspect_seconds=2.0,
    )
    course = a_course(keyed, "Area")
    provider.queue(marked("cold"))

    film = made(filming, keyed, course)

    # Looked at again, and not sent back: nothing was wrong with the chapter.
    assert provider.kinds() == ["film"]
    assert film["chapters"][0]["state"] == "written"
    assert (filming.films._paths.home / "home" / "warm").is_file()


def test_a_chapter_that_stops_only_once_joined_is_told_in_words_and_the_film_made(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area", "Volume")
    provider.queue(FILM_CHAPTER, marked("stop when joined"))

    film = made(filming, keyed, course)

    assert provider.kinds() == ["film", "film"]
    assert [chapter["state"] for chapter in film["chapters"]] == ["written", "in_words"]


def test_a_film_stopped_is_unfinished_and_continued_where_it_was_left(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area", "Volume")
    provider.queue(FILM_CHAPTER, marked("hang"))
    job = keyed.post(f"/v1/courses/{course}/film").json()
    eventually(lambda: len(provider.requests) == 2, "the second chapter was asked for")
    eventually(
        lambda: "Checking chapter 2" in filming.jobs.get(job["id"]).progress_message,
        "the second chapter is being checked",
    )
    filming.jobs.cancel(job["id"])
    assert filming.jobs.wait(job["id"], timeout=30).status == "cancelled"
    left = keyed.get(f"/v1/courses/{course}/film").json()["film"]
    assert left["status"] == "unfinished"
    assert left["reason"].startswith("Stopped.")
    assert [chapter["state"] for chapter in left["chapters"]] == ["written", "waiting"]

    film = made(filming, keyed, course)

    # The first chapter was kept: only the second is asked for again.
    assert provider.kinds() == ["film", "film", "film"]
    assert film["status"] == "ready"


def test_a_film_left_by_a_closed_adle_is_unfinished_and_a_video_that_is_gone_is_not_offered(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    film = made(filming, keyed, course)
    other = a_course(keyed, "Volume")
    with filming.database.session() as session:
        session.add(
            Film(
                id="flm_0123456789abcdef0123",
                course_id=other,
                status="making",
                title="Area and volume",
                chapters=[],
                marks=[],
                notes=[],
                written_by={},
            )
        )
    stray = filming.films._paths.films / "flm_ffffffffffffffffffff"
    stray.mkdir(parents=True)
    (filming.films._paths.films / film["id"] / "film.mp4").unlink()

    filming.films.settle()

    assert keyed.get(f"/v1/courses/{course}/film").json()["film"] is None
    unfinished = keyed.get(f"/v1/courses/{other}/film").json()["film"]
    assert unfinished["status"] == "unfinished"
    assert "closed" in unfinished["reason"]
    assert not stray.exists()


def test_removing_a_film_or_its_course_stops_it_and_takes_its_files(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    film = made(filming, keyed, course)
    folder = filming.films._paths.films / film["id"]
    assert folder.is_dir()
    assert keyed.delete(f"/v1/courses/{course}/film").status_code == 204
    assert not folder.exists()
    assert keyed.get(f"/v1/courses/{course}/film").json()["film"] is None
    assert keyed.delete(f"/v1/courses/{course}/film").status_code == 404

    # While it is being made, its course is removed: the work stops.
    provider.queue(marked("hang"))
    job = keyed.post(f"/v1/courses/{course}/film").json()
    eventually(
        lambda: "Checking chapter 1" in filming.jobs.get(job["id"]).progress_message,
        "the chapter is being checked",
    )
    assert keyed.delete(f"/v1/courses/{course}").status_code == 204
    eventually(lambda: filming.jobs.find_active("film_making", course) is None, "it stopped")
    with filming.database.read() as session:
        assert session.query(Film).count() == 0


def test_a_film_is_saved_where_the_shell_collects_it_with_its_subtitles(
    keyed: TestClient, filming: Services
) -> None:
    course = a_course(keyed, "Area")
    film = made(filming, keyed, course)

    saved = filming.films.save(film["id"])

    handover = filming.settings.handover_dir
    assert (handover / saved.file_name).read_bytes() == VIDEO
    assert saved.captions_name is not None
    assert "Let us count it." in (handover / saved.captions_name).read_text(encoding="utf-8")
    assert saved.suggested_name == "Area and volume.mp4"
    # The page cannot ask for it: the route is the shell's.
    described = create_app(filming).openapi()
    assert described["paths"]["/v1/films/{film_id}/file"]["post"]["x-adle-internal"] is True


def test_what_stands_in_the_way_is_said_and_nothing_is_sent(
    client: TestClient, filming: Services, provider: FakeProvider, tmp_path: Path
) -> None:
    empty = a_course(client)
    assert (
        client.get(f"/v1/courses/{empty}/film").json()["plan"]["blocked"].startswith("Add concepts")
    )
    course = a_course(client, "Area")
    blocked = client.get(f"/v1/courses/{course}/film").json()["plan"]["blocked"]
    assert blocked.startswith("Add an AI provider’s key")
    assert client.post(f"/v1/courses/{course}/film").status_code == 409
    filming.films = film_service(
        filming,
        FilmPaths(
            root=tmp_path / "none",
            python=tmp_path / "none" / "python.exe",
            engine=None,
            borrowed=False,
            work=tmp_path / "work",
            films=tmp_path / "films",
        ),
    )
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    plan = client.get(f"/v1/courses/{course}/film").json()["plan"]
    assert plan["blocked"] == "Set up the film maker first."
    assert client.post(f"/v1/courses/{course}/film").status_code == 409
    assert client.get("/v1/courses/crs_00000000000000000000/film").status_code == 404
    assert provider.requests == []


def test_when_the_days_allowance_is_used_up_what_was_made_is_kept(
    keyed: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    with filming.database.session() as session:
        for _ in range(90):
            session.add(
                ModelUsage(
                    started_at=datetime.now(UTC),
                    purpose="film",
                    model="m",
                    prompt_tokens=10,
                    completion_tokens=10,
                    estimated=False,
                    outcome="ok",
                )
            )
    job = keyed.post(f"/v1/courses/{course}/film").json()
    done = filming.jobs.wait(job["id"], timeout=30)
    assert (done.status, done.error_code) == ("failed", "quota_exhausted")
    film = keyed.get(f"/v1/courses/{course}/film").json()["film"]
    assert film["status"] == "unfinished"
    assert "continue then" in film["reason"]
    assert provider.requests == []


@pytest.fixture
def voiced_filming(filming: Services, tmp_path: Path) -> Iterator[Services]:
    """A natural voice set up and chosen, spoken by the stand-in (a third of a second a
    word), and the film service using it."""
    narration = NarrationService(
        filming.lessons,
        filming.jobs,
        set_up(tmp_path / "voice", "kokoro"),
        hardware=lambda: WITH_CARD,
        idle_seconds=3.0,
    )
    filming.narration = narration
    filming.films = FilmService(
        filming.database,
        filming.jobs,
        filming.gateway,
        filming.curriculum,
        filming.generation,
        narration,
        filming.films._paths,
        handover_dir=filming.settings.handover_dir,
    )
    yield filming
    narration.close()


def test_a_film_is_read_in_the_natural_voice_and_its_words_are_timed_by_it(
    keyed: TestClient, voiced_filming: Services, provider: FakeProvider
) -> None:
    course = a_course(keyed, "Area")
    assert keyed.get(f"/v1/courses/{course}/film").json()["plan"]["voice"] == "Natural (Heart)"

    film = made(voiced_filming, keyed, course)

    assert film["voice"] == "Natural (Heart)"
    assert not any("no voice" in note for note in film["notes"])
    cues = keyed.get(f"/v1/films/{film['id']}/captions").json()["cues"]
    opening = cues[0]
    # The stand-in voice says a word in 0.3 s: the film is timed by what it recorded.
    words = len(opening["text"].split())
    assert opening["end"] - opening["start"] == pytest.approx(words * 0.3, abs=0.05)
    # A chapter's line too, though the chapter was looked at alone, quiet, before its lines
    # were recorded: what the engine kept of that is not what the film says.
    line = next(cue for cue in cues if cue["text"].startswith("How much floor"))
    spoken = len(line["text"].split())
    assert line["end"] - line["start"] == pytest.approx(spoken * 0.3, abs=0.05)


# -- a chapter's pictures, looked over (ADR-066) --------------------------------------------


def test_a_chapters_pictures_are_looked_over_once_and_what_is_seen_is_mended(
    seeing: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(seeing, "Area", "Volume")
    plan = seeing.get(f"/v1/courses/{course}/film").json()["plan"]
    # Each chapter once, mended three times at most, and looked over once: said before.
    assert (plan["checks_pictures"], plan["requests_at_most"]) == (True, 10)
    provider.queue(
        FILM_CHAPTER,
        "Each in turn.\n#1: The label '2 tall' sits far from the grid; put it beside it.",
        FILM_CHAPTER,
        FILM_CHAPTER,
        "NOTHING",
    )

    film = made(filming, seeing, course)

    # Looked over when it first ran clean; mended for what was seen, and not looked over
    # again. The second chapter was seen to be right.
    assert provider.kinds() == ["film", "storyboard", "film", "film", "storyboard"]
    look = provider.requests[1]
    assert look["model"] == SUPER_VL
    # The stand-in draws a sheet for every six of the chapter's seventeen animations.
    sheets = pictures_of(look)
    assert len(sheets) == 3
    for sheet in sheets:
        assert sheet.startswith("data:image/png;base64,")
        assert base64.b64decode(sheet.split(",", 1)[1]).startswith(b"\x89PNG")
    # With what is said while each animation plays, quoted.
    assert '#0: "How much floor does a rug cover? Let us count it."' in provider.prompt(1)
    mend = provider.prompt(2)
    assert "looked at a picture of the screen at the end of each animation" in mend
    assert "line 22, in the picture at " in mend
    assert "The label '2 tall' sits far from the grid; put it beside it." in mend
    assert film["status"] == "ready"
    assert [chapter["state"] for chapter in film["chapters"]] == ["written", "written"]
    assert "Nemotron 3.5 Super" in film["written_by"]["models"]


def test_a_chapter_not_clean_by_its_last_mend_is_looked_over_before_it(
    seeing: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(seeing, "Area")
    provider.queue(
        marked("overlap"),
        marked("overlap"),
        marked("overlap"),
        "#0: The title is squeezed into the top of the screen.",
        FILM_CHAPTER,
    )

    film = made(filming, seeing, course)

    assert provider.kinds() == ["film", "film", "film", "storyboard", "film"]
    # The one mend left is told what the engine found and what was seen, together.
    last = provider.prompt(4)
    assert "overlaps title" in last
    assert "line 14, in the picture at " in last
    assert "The title is squeezed into the top of the screen." in last
    assert film["chapters"][0]["problems"] == 0


def test_a_look_that_fails_or_cannot_be_read_is_passed_over(
    seeing: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(seeing, "Area", "Volume")
    provider.queue(
        FILM_CHAPTER,
        httpx.Response(400, json={"error": {"message": "That request was refused."}}),
        FILM_CHAPTER,
        "I can't make out the pictures, sorry.",
    )

    film = made(filming, seeing, course)

    # Nothing waits on a look: each chapter is kept as it ran, and nothing more is asked.
    assert provider.kinds() == ["film", "storyboard", "film", "storyboard"]
    assert film["status"] == "ready"
    assert [chapter["state"] for chapter in film["chapters"]] == ["written", "written"]


def test_a_chapter_with_no_storyboard_is_not_looked_over(
    seeing: TestClient, filming: Services, provider: FakeProvider
) -> None:
    course = a_course(seeing, "Area")
    provider.queue(marked("no storyboard"))

    film = made(filming, seeing, course)

    assert provider.kinds() == ["film"]
    assert film["chapters"][0]["state"] == "written"
