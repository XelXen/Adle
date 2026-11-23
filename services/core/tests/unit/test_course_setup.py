"""A course made from files and set up by Adle (ADR-053): left unnamed, Adle names it from
its first file and then as the AI suggests; asked to set it up, Adle adds what the AI
suggests and begins the first lesson. Against the scripted provider: no request leaves the
process.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.generation import KIND_LESSON, _course_title
from adle_core.application.services import Services
from tests.support.model import CURRICULUM, LESSON, FakeProvider
from tests.unit.test_courses_and_sources import import_files
from tests.unit.test_generation_api import KEY


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def unnamed(client: TestClient, **extra: Any) -> dict[str, Any]:
    response = client.post("/v1/courses", json={"origin": "materials", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def proposal(client: TestClient, services: Services, course_id: str, **body: Any) -> dict[str, Any]:
    started = client.post(f"/v1/courses/{course_id}/curriculum/proposal", json=body or None)
    assert started.status_code == 202, started.text
    services.jobs.wait(started.json()["id"], timeout=60)
    job = client.get(f"/v1/jobs/{started.json()['id']}").json()
    assert job["status"] == "succeeded", job
    return job


def named(answer: dict[str, Any], title: str) -> dict[str, Any]:
    return {"course_title": title, **copy.deepcopy(answer)}


def test_a_course_left_unnamed_is_named_by_adle_from_its_first_file(
    client: TestClient, services: Services
) -> None:
    course = unnamed(client)
    assert (course["title"], course["named_by_adle"]) == ("New course", True)
    import_files(client, services, course["id"], "neural-networks-syllabus.md")
    after = client.get(f"/v1/courses/{course['id']}").json()
    assert (after["title"], after["named_by_adle"]) == ("Neural networks syllabus", True)
    # A second file does not rename it again.
    import_files(client, services, course["id"], "lecture-notes.pdf")
    assert client.get(f"/v1/courses/{course['id']}").json()["title"] == "Neural networks syllabus"


def test_the_ai_names_a_course_left_to_adle_and_never_one_the_learner_named(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course = unnamed(keyed, origin="topic", topic="Limits and derivatives.")
    provider.queue(named(CURRICULUM, "  Limits and derivatives.  "))
    job = proposal(keyed, services, course["id"])
    assert 'Add "course_title"' in provider.prompt()
    assert job["result"]["course_title"] == "Limits and derivatives"
    after = keyed.get(f"/v1/courses/{course['id']}").json()
    assert (after["title"], after["named_by_adle"]) == ("Limits and derivatives", False)
    # Nothing added: without "set it up" the learner still picks (ADR-012).
    assert keyed.get(f"/v1/courses/{course['id']}/curriculum").json()["concepts"] == []

    # Named by the learner: never renamed, and the AI is not asked to.
    mine = keyed.post(
        "/v1/courses", json={"title": "My calculus", "origin": "topic", "topic": "Limits."}
    ).json()
    provider.queue(named(CURRICULUM, "Something else"))
    proposal(keyed, services, mine["id"])
    assert "course_title" not in provider.prompt()
    assert keyed.get(f"/v1/courses/{mine['id']}").json()["title"] == "My calculus"


def test_a_learner_who_renames_the_course_takes_the_name_back_from_adle(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course = unnamed(keyed, origin="topic", topic="Limits.")
    renamed = keyed.patch(f"/v1/courses/{course['id']}", json={"title": "Calculus, my way"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["named_by_adle"] is False
    provider.queue(named(CURRICULUM, "Limits"))
    proposal(keyed, services, course["id"])
    assert keyed.get(f"/v1/courses/{course['id']}").json()["title"] == "Calculus, my way"


def test_a_course_set_up_by_adle_has_what_was_suggested_and_its_first_lesson_begun(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course = unnamed(keyed, origin="topic", topic="Limits and derivatives.")
    provider.queue(named(CURRICULUM, "Limits and derivatives"), LESSON)
    job = proposal(keyed, services, course["id"], setup=True)
    result = job["result"]
    assert (result["accepted"], result["setup"]) == (True, True)
    concepts = keyed.get(f"/v1/courses/{course['id']}/curriculum").json()["concepts"]
    assert [concept["title"] for concept in concepts] == [
        concept["title"] for concept in CURRICULUM["concepts"]
    ]
    # The first that can be taught has its lesson begun, as if the learner had asked.
    lesson_job = services.jobs.wait(result["lesson_job_id"], timeout=60)
    assert lesson_job.kind == KIND_LESSON
    assert lesson_job.subject_id == result["first_concept_id"] == concepts[0]["id"]
    assert lesson_job.status == "succeeded", lesson_job.error_message
    assert provider.kinds()[:2] == ["curriculum", "lesson"]
    # Nothing is left to review: the suggestions were added.
    again = keyed.post(f"/v1/jobs/{job['id']}/accept", json={"selected": [0]})
    assert again.status_code == 409


@pytest.mark.parametrize(
    ("given", "taken"),
    [
        ("Probability and counting", "Probability and counting"),
        ('  "Probability"  .', "Probability"),
        ("Line one\nline two", "Line one line two"),
        ("x" * 81, None),
        ("A", None),
        ("<b>Bold</b>", None),
        ("$x^2$", None),
        (42, None),
    ],
)
def test_the_name_the_ai_gives_is_one_plain_line(given: object, taken: str | None) -> None:
    assert _course_title(given) == taken
