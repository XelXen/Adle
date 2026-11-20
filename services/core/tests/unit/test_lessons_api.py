"""Lessons and the sample course, through the HTTP API and the services."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from adle_core.application import sample_course
from adle_core.application.sample_course import (
    build_lesson_bundle,
    content_root,
    load_lesson_template,
    load_outline,
)
from adle_core.application.services import Services
from adle_core.generation.scene_policy import check_scene_source
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Course, StoredLesson, StoredScene
from adle_core.lessons.bundle import LessonInvalidError, parse_bundle
from adle_core.lessons.player import PlayerLesson

#: One lesson for each concept of the sample course.
SAMPLE_LESSONS = 8


def install(client: TestClient) -> dict[str, Any]:
    response = client.post("/v1/courses/sample")
    assert response.status_code == 200, response.text
    return response.json()


def first_lesson(client: TestClient, course_id: str) -> dict[str, Any]:
    lessons = client.get(f"/v1/courses/{course_id}/lessons").json()["lessons"]
    return client.get(f"/v1/lessons/{lessons[0]['id']}").json()


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings(item)]
    return []


# -- the sample course ------------------------------------------------------


def test_the_sample_course_installs_as_a_complete_learnable_course(client: TestClient) -> None:
    course = install(client)
    assert course["origin"] == "sample"
    assert course["title"] == "Introduction to neural networks"
    assert "written by Adle" in course["description"]

    curriculum = client.get(f"/v1/courses/{course['id']}/curriculum").json()
    by_id = {concept["id"]: concept for concept in curriculum["concepts"]}
    assert [by_id[concept_id]["title"] for concept_id in curriculum["learning_order"]] == [
        "Weights and bias",
        "Activation functions",
        "The perceptron",
        "Forward propagation",
        "Loss",
        "Derivatives and the chain rule",
        "Gradient descent",
        "Backpropagation",
    ]
    assert curriculum["issues"] == []
    assert curriculum["startable"] is True
    for concept in curriculum["concepts"]:
        assert concept["origin"] == "sample"
        assert len(concept["objectives"]) >= 2
        assert concept["summary"]
        for prerequisite in concept["prerequisites"]:
            assert prerequisite["reason"], f"{concept['title']} needs a reason for each link"
    backprop = next(c for c in curriculum["concepts"] if c["title"] == "Backpropagation")
    assert [item["title"] for item in backprop["prerequisites"]] == [
        "Forward propagation",
        "Derivatives and the chain rule",
        "Gradient descent",
    ]


def test_installing_the_sample_course_twice_gives_the_same_course(
    client: TestClient, services: Services
) -> None:
    first = install(client)
    second = install(client)
    assert second["id"] == first["id"]
    with services.database.session() as session:
        assert session.scalar(select(func.count(Course.id))) == 1
        assert session.scalar(select(func.count(StoredLesson.id))) == len(load_outline()["lessons"])


def test_a_sample_lesson_is_served_ready_for_the_player(client: TestClient) -> None:
    course = install(client)
    lessons = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    summary = lessons[0]
    assert summary["title"] == "Weights and bias: how a neuron adds things up"
    assert summary["origin"] == "sample"
    assert summary["progress"] == {"position": 0, "completed": False, "started": False}

    loaded = client.get(f"/v1/lessons/{summary['id']}").json()
    lesson = loaded["lesson"]
    assert lesson["lesson_id"] == summary["id"]
    assert lesson["course_id"] == course["id"]
    assert lesson["grounding"] == "sample"
    assert len(lesson["segments"]) == summary["segment_count"]
    # Every placeholder of the template was replaced by a real identifier.
    assert not [text for text in strings(lesson) if text.startswith("@")]
    assert lesson["concept_ids"] == [summary["concept_id"]]

    scenes = {scene["id"]: scene for scene in loaded["scenes"]}
    assert set(scenes) == {"scn_weighted_sum", "scn_neuron_weight"}
    assert scenes["scn_neuron_weight"]["interactive"] is True
    assert scenes["scn_neuron_weight"]["controls"] == ["weight", "bias_on"]
    assert "class NeuronWeight(InteractiveScene)" in scenes["scn_neuron_weight"]["source"]
    # What is served fits the player's contract, and carries no answer keys.
    PlayerLesson.model_validate(lesson)
    served = client.get(f"/v1/lessons/{summary['id']}").text
    for secret in ("correct_option", '"expected"', '"accepted"', "misconception", '"feedback"'):
        assert secret not in served, secret
    assert "fifteen times larger" not in served  # the feedback for the right option
    questions = [
        segment["question"] for segment in lesson["segments"] if segment["type"] == "checkpoint"
    ]
    assert [question["form"] for question in questions] == [
        "multiple_choice",
        "numeric",
        "multiple_choice",
    ]
    assert sorted(option["id"] for option in questions[0]["options"]) == ["a", "b", "c"]
    assert questions[0]["hint"] == "Look at what each input is multiplied by."


def test_all_sample_content_is_valid_and_all_of_it_is_used() -> None:
    outline = load_outline()
    ids = {"@course": new_id("crs"), "@lesson": new_id("les")}
    for concept in outline["concepts"]:
        ids[f"@concept:{concept['key']}"] = new_id("con")
        for objective in concept["objectives"]:
            ids[f"@objective:{concept['key']}.{objective['key']}"] = new_id("obj")

    used_scenes: set[str] = set()
    for key in outline["lessons"]:
        template = load_lesson_template(key)
        used_scenes.update(scene["file"] for scene in template["scenes"])
        bundle = parse_bundle(build_lesson_bundle(template, ids))
        # A sample lesson teaches, shows something, and checks understanding.
        kinds = {segment.type for segment in bundle.lesson.segments}
        assert {"explanation", "checkpoint", "summary"} <= kinds, key
        assert bundle.scenes, key
        assert len(bundle.lesson.questions()) >= 2, key
        forms = {question.form for question in bundle.lesson.questions()}
        assert len(forms) >= 2, f"{key}: one kind of question cannot demonstrate understanding"
        assert any(question.is_transfer for question in bundle.lesson.questions()), key

    lesson_files = {
        entry.name.removesuffix(".json") for entry in content_root().joinpath("lessons").iterdir()
    }
    assert lesson_files == set(outline["lessons"])
    scene_files = {
        entry.name
        for entry in content_root().joinpath("scenes").iterdir()
        if entry.name.endswith(".py")
    }
    assert scene_files == used_scenes
    for name in sorted(scene_files):
        report = check_scene_source(sample_course.load_scene_source(name))
        assert report.ok, (name, report.violations)


def test_a_broken_sample_leaves_no_half_built_course_behind(
    client: TestClient, services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(key: str) -> dict[str, Any]:
        template = load_lesson_template(key)
        template["lesson"]["segments"] = []
        return template

    monkeypatch.setattr(sample_course, "load_lesson_template", broken)
    with pytest.raises(LessonInvalidError):
        services.sample_course.install()
    assert client.get("/v1/courses").json() == {"courses": []}


def test_a_template_that_names_something_undefined_fails_clearly() -> None:
    template = load_lesson_template("weighted_sum")
    with pytest.raises(KeyError, match="@concept:weighted_sum"):
        build_lesson_bundle(template, {"@course": "crs_x", "@lesson": "les_x"})


# -- progress ---------------------------------------------------------------


def test_progress_is_remembered_and_a_finished_lesson_stays_finished(client: TestClient) -> None:
    course = install(client)
    lesson_id = first_lesson(client, course["id"])["lesson"]["lesson_id"]
    url = f"/v1/lessons/{lesson_id}/progress"

    moved = client.put(url, json={"position": 3})
    assert moved.status_code == 200, moved.text
    assert moved.json() == {"position": 3, "completed": False, "started": True}
    assert client.get(f"/v1/lessons/{lesson_id}").json()["progress"]["position"] == 3

    last = client.get(f"/v1/lessons/{lesson_id}").json()["lesson"]["segments"]
    done = client.put(url, json={"position": len(last) - 1, "completed": True})
    assert done.json()["completed"] is True
    # Going back to review does not undo having finished.
    again = client.put(url, json={"position": 0})
    assert again.json() == {"position": 0, "completed": True, "started": True}
    listed = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"][0]
    assert listed["progress"] == {"position": 0, "completed": True, "started": True}


@pytest.mark.parametrize("body", [{"position": -1}, {"position": 99}, {}, {"position": "two"}])
def test_progress_outside_the_lesson_is_refused(client: TestClient, body: dict[str, Any]) -> None:
    course = install(client)
    lesson_id = first_lesson(client, course["id"])["lesson"]["lesson_id"]
    assert client.put(f"/v1/lessons/{lesson_id}/progress", json=body).status_code == 422


def test_unknown_lessons_are_not_found(client: TestClient) -> None:
    unknown = "les_00000000000000000000"
    assert client.get(f"/v1/lessons/{unknown}").status_code == 404
    assert client.put(f"/v1/lessons/{unknown}/progress", json={"position": 0}).status_code == 404
    assert client.delete(f"/v1/lessons/{unknown}").status_code == 404
    assert client.get("/v1/courses/crs_00000000000000000000/lessons").status_code == 404


# -- storing ----------------------------------------------------------------


def stored_bundle(client: TestClient, services: Services, course_id: str) -> dict[str, Any]:
    """The full stored lesson (with its answers), which only the core ever sees."""
    lesson_id = first_lesson(client, course_id)["lesson"]["lesson_id"]
    loaded = services.lessons.get(lesson_id)
    return {
        "lesson": loaded.lesson.model_dump(mode="json"),
        "scenes": [scene.model_dump(mode="json") for scene in loaded.scenes],
    }


def test_a_lesson_must_belong_to_its_course_in_every_reference(
    client: TestClient, services: Services
) -> None:
    course = install(client)
    data = stored_bundle(client, services, course["id"])
    data["lesson"]["lesson_id"] = new_id("les")

    other = client.post(
        "/v1/courses", json={"title": "Other", "origin": "topic", "topic": "Something else"}
    ).json()
    elsewhere = json.loads(json.dumps(data))
    elsewhere["lesson"]["course_id"] = other["id"]
    with pytest.raises(Exception, match="not in this course"):
        services.lessons.store(parse_bundle(elsewhere), origin="generated")

    wrong_objective = json.loads(json.dumps(data))
    wrong_objective["lesson"]["objectives"][0]["objective_id"] = new_id("obj")
    with pytest.raises(Exception, match="learning objective"):
        services.lessons.store(parse_bundle(wrong_objective), origin="generated")

    invented = json.loads(json.dumps(data))
    invented["lesson"]["grounding"] = "materials"
    invented["lesson"]["source_refs"] = [
        {
            "source_id": new_id("src"),
            "section_id": new_id("sec"),
            "source_name": "notes.pdf",
            "locator": "page 9",
        }
    ]
    with pytest.raises(Exception, match="cites a passage that is not in this course"):
        services.lessons.store(parse_bundle(invented), origin="generated")

    # The same lesson under a new id is accepted; under an existing id it is not.
    assert services.lessons.store(parse_bundle(data), origin="generated").origin == "generated"
    with pytest.raises(Exception, match="already exists"):
        services.lessons.store(parse_bundle(data), origin="generated")
    lessons = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    assert len(lessons) == SAMPLE_LESSONS + 1
    assert [item["origin"] for item in lessons].count("generated") == 1


def test_a_lesson_written_for_another_version_is_reported_not_half_played(
    client: TestClient, services: Services
) -> None:
    course = install(client)
    lesson_id = first_lesson(client, course["id"])["lesson"]["lesson_id"]
    with services.database.session() as session:
        row = session.get(StoredLesson, lesson_id)
        assert row is not None
        row.document = {**row.document, "segments": [{"type": "hologram"}]}

    response = client.get(f"/v1/lessons/{lesson_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "lesson_outdated"
    assert "different version" in response.json()["error"]["message"]
    # It can still be listed and removed.
    listed = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    assert lesson_id in [item["id"] for item in listed]
    assert client.delete(f"/v1/lessons/{lesson_id}").status_code == 204
    remaining = client.get(f"/v1/courses/{course['id']}/lessons").json()["lessons"]
    assert lesson_id not in [item["id"] for item in remaining]
    assert len(remaining) == SAMPLE_LESSONS - 1


def _stored_scene(services: Services, lesson_id: str, scene_id: str) -> dict[str, Any]:
    with services.database.session() as session:
        row = session.get(StoredScene, (lesson_id, scene_id))
        assert row is not None
        return dict(row.document)


def _overwrite_scene(
    services: Services, lesson_id: str, scene_id: str, changes: dict[str, Any]
) -> None:
    """Change a stored scene behind the service's back, as a restored or edited database would."""
    with services.database.session() as session:
        row = session.get(StoredScene, (lesson_id, scene_id))
        assert row is not None
        row.document = {**row.document, **changes}


def test_a_stored_scene_is_described_again_from_its_source_when_a_lesson_is_opened(
    client: TestClient, services: Services
) -> None:
    course = install(client)
    lesson_id = first_lesson(client, course["id"])["lesson"]["lesson_id"]
    honest = _stored_scene(services, lesson_id, "scn_weighted_sum")
    # The database now claims things about the scene that its source does not support.
    _overwrite_scene(
        services,
        lesson_id,
        "scn_weighted_sum",
        {
            "scene_class": "SomethingElse",
            "interactive": True,
            "controls": ["invented"],
            "content_hash": "0" * 64,
        },
    )

    scenes = {
        scene["id"]: scene for scene in client.get(f"/v1/lessons/{lesson_id}").json()["scenes"]
    }
    described = scenes["scn_weighted_sum"]
    assert described["scene_class"] == "WeightedSum"
    assert described["interactive"] is False
    assert described["controls"] == []
    assert described["content_hash"] == honest["content_hash"]


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "import os\nfrom manim import *\n\n\nclass S(Scene):\n    pass\n"},
        {"source": "this is ( not python"},
        {"source": 12},
        {"purpose": None},
    ],
    ids=["forbidden import", "does not parse", "source is not text", "no purpose"],
)
def test_a_stored_scene_that_may_not_run_is_withheld_and_the_lesson_still_opens(
    client: TestClient, services: Services, changes: dict[str, Any]
) -> None:
    course = install(client)
    lesson_id = first_lesson(client, course["id"])["lesson"]["lesson_id"]
    _overwrite_scene(services, lesson_id, "scn_weighted_sum", changes)

    response = client.get(f"/v1/lessons/{lesson_id}")
    assert response.status_code == 200, response.text
    loaded = response.json()
    assert [scene["id"] for scene in loaded["scenes"]] == ["scn_neuron_weight"]
    # The part that used the scene is still there, with its description in words.
    segment = next(item for item in loaded["lesson"]["segments"] if item["id"] == "seg_sum")
    assert segment["scene"]["scene_id"] == "scn_weighted_sum"
    assert segment["scene"]["fallback_text"].startswith("A diagram shows two inputs")
    # Answering questions does not depend on the scenes at all.
    answered = client.post(
        f"/v1/lessons/{lesson_id}/questions/q_compute/answer", json={"number": 3}
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["outcome"] == "correct"


def test_deleting_a_course_or_a_concept_removes_its_lessons(
    client: TestClient, services: Services
) -> None:
    course = install(client)
    loaded = first_lesson(client, course["id"])
    client.put(f"/v1/lessons/{loaded['lesson']['lesson_id']}/progress", json={"position": 1})

    concept_id = loaded["lesson"]["concept_ids"][0]
    lesson_id = loaded["lesson"]["lesson_id"]
    assert client.delete(f"/v1/concepts/{concept_id}").status_code == 200
    with services.database.read() as session:
        # The concept's lesson and its scenes go with it; the other lessons stay.
        assert session.get(StoredLesson, lesson_id) is None
        assert (
            session.scalar(
                select(func.count(StoredScene.scene_id)).where(StoredScene.lesson_id == lesson_id)
            )
            == 0
        )
        assert session.scalar(select(func.count(StoredLesson.id))) == SAMPLE_LESSONS - 1

    assert client.delete(f"/v1/courses/{course['id']}").status_code == 204
    with services.database.read() as session:
        assert session.scalar(select(func.count(StoredLesson.id))) == 0
        assert session.scalar(select(func.count(StoredScene.scene_id))) == 0
    again = install(client)
    assert again["id"] != course["id"]
    lessons = client.get(f"/v1/courses/{again['id']}/lessons").json()["lessons"]
    assert len(lessons) == SAMPLE_LESSONS
