"""A course saved as a file and brought in from one (ADR-063): a template has nothing of the
learner in it, a transfer carries everything, what is brought in is always a new course made
by the ordinary roads, and what cannot be used is left out and counted."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from adle_core.application import course_file as files
from adle_core.application.asks import AskCitation
from adle_core.application.course_file import CourseFileError
from adle_core.application.course_sharing import (
    HANDED_OVER,
    CourseFileService,
    Holds,
    file_name_for,
    without_citations,
)
from adle_core.application.services import Services
from adle_core.errors import AdleError
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import (
    Attempt,
    Concept,
    Course,
    LearnerConceptState,
    LearnerEvent,
    LearnerObservation,
    LessonAsk,
    LessonProgress,
    Source,
    SourceChunk,
    StoredLesson,
)
from adle_core.lessons.bundle import parse_bundle

EVERYTHING = Holds(lessons=True, materials=True, progress=True, notes=True)
NOTES = "# Limits\n\nA limit is the value a function approaches as its input approaches a point.\n"


def sample(client: TestClient) -> dict[str, Any]:
    return client.post("/v1/courses/sample").json()


def lessons_of(client: TestClient, course_id: str) -> list[dict[str, Any]]:
    return client.get(f"/v1/courses/{course_id}/lessons").json()["lessons"]


def curriculum_of(client: TestClient, course_id: str) -> list[dict[str, Any]]:
    return client.get(f"/v1/courses/{course_id}/curriculum").json()["concepts"]


def saved(services: Services, course_id: str, kind: str, holds: Holds | None = None) -> Path:
    made = services.course_files.save(course_id, kind, holds or Holds.of(kind))  # type: ignore[arg-type]
    assert HANDED_OVER.match(made.name)
    return services.settings.handover_dir / made.name


def shape(concepts: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """A curriculum without its identifiers: what must be the same after a journey."""
    titles = {concept["id"]: concept["title"] for concept in concepts}
    return [
        (
            concept["title"],
            concept["summary"],
            concept["complexity"],
            concept["tags"],
            [objective["statement"] for objective in concept["objectives"]],
            sorted(
                (titles[need["concept_id"]], need["reason"]) for need in concept["prerequisites"]
            ),
        )
        for concept in concepts
    ]


def count(services: Services, model: Any, course_id: str) -> int:
    with services.database.read() as session:
        found = session.scalar(
            select(func.count()).select_from(model).where(model.course_id == course_id)
        )
    return int(found or 0)


def with_materials(client: TestClient, services: Services, tmp_path: Path) -> dict[str, Any]:
    """The sample course with a document of the learner's in it, a concept linked to a
    place in it, and a lesson that cites it."""
    course = sample(client)
    notes = tmp_path / "limits notes.md"
    notes.write_text(NOTES, encoding="utf-8")
    outcome = services.sources.import_file(course["id"], notes)
    assert outcome.outcome == "imported", outcome
    detail = services.sources.get(outcome.source_id or "")
    section = detail.sections[0]
    concept = curriculum_of(client, course["id"])[0]
    services.curriculum.add_source_ref(concept["id"], section.id)
    with services.database.read() as session:
        first = session.scalars(
            select(StoredLesson).where(StoredLesson.concept_id == concept["id"])
        ).first()
        assert first is not None
        document = dict(first.document)
        scenes = [
            {
                "id": scene.scene_id,
                "purpose": scene.document["purpose"],
                "source": scene.document["source"],
            }
            for scene in first.scenes
        ]
    document.update(
        lesson_id=new_id("les"),
        title="A limit, from the notes",
        grounding="materials",
        source_refs=[
            {
                "source_id": outcome.source_id,
                "section_id": section.id,
                "source_name": "limits notes.md",
                "locator": "Limits",
            }
        ],
    )
    cited = services.lessons.store(
        parse_bundle({"lesson": document, "scenes": scenes}), origin="generated"
    )
    return {"course": course, "source_id": outcome.source_id, "cited_lesson": cited.id}


# -- a template ----------------------------------------------------------------------------------


def test_a_template_carries_the_course_and_its_lessons_and_nothing_of_the_learner(
    client: TestClient, services: Services
) -> None:
    course = sample(client)
    first = client.get(f"/v1/lessons/{lessons_of(client, course['id'])[0]['id']}").json()["lesson"]
    answered = client.post(
        f"/v1/lessons/{first['lesson_id']}/questions/q_influence/answer", json={"option_id": "a"}
    )
    assert answered.status_code == 200
    path = saved(services, course["id"], "template")

    found = services.course_files.look(path)
    assert (found.title, found.kind) == (course["title"], "template")
    assert found.counts.concepts == len(curriculum_of(client, course["id"]))
    assert found.counts.lessons == len(lessons_of(client, course["id"]))
    assert (found.counts.progress, found.counts.notes, found.counts.materials) == (False, 0, 0)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert "progress.json" not in names
        assert "notes.json" not in names
        everything = b"".join(archive.read(name) for name in names).decode("utf-8")
    # Nothing in it says what the learner answered, or what they know.
    for word in ('q_influence", "form', "state_after", "probability", "observations"):
        assert word not in everything

    brought = services.course_files.bring_in(path, EVERYTHING)
    assert brought.course_id != course["id"]
    assert (brought.concepts, brought.lessons, brought.lessons_left_out) == (
        found.counts.concepts,
        found.counts.lessons,
        0,
    )
    assert (brought.progress, brought.notes, brought.materials) == (False, 0, 0)

    made = client.get(f"/v1/courses/{brought.course_id}").json()
    assert made["title"] == course["title"]
    assert made["brought_in"] is True
    # Never as Adle's own sample, whatever a file says of itself.
    assert made["origin"] == "topic"
    assert made["subject"] == course["subject"]
    assert client.get(f"/v1/courses/{course['id']}").json()["brought_in"] is False
    assert shape(curriculum_of(client, brought.course_id)) == shape(
        curriculum_of(client, course["id"])
    )
    # Everything has identifiers of its own: nothing here is the other course's.
    theirs = {concept["id"] for concept in curriculum_of(client, course["id"])}
    ours = {concept["id"] for concept in curriculum_of(client, brought.course_id)}
    assert not theirs & ours
    assert count(services, LearnerObservation, brought.course_id) == 0
    assert count(services, Attempt, brought.course_id) == 0
    assert count(services, LearnerObservation, course["id"]) == 1

    # Every lesson plays: it went through the gate every lesson goes through.
    for summary in lessons_of(client, brought.course_id):
        view = client.get(f"/v1/lessons/{summary['id']}")
        assert view.status_code == 200, view.text
        lesson = view.json()["lesson"]
        assert lesson["course_id"] == brought.course_id
        assert set(lesson["concept_ids"]) <= ours
        assert lesson["grounding"] == "general_knowledge"
        assert summary["origin"] == "generated"
    # And its questions are answered and scored here, like any lesson's.
    again = client.get(f"/v1/lessons/{lessons_of(client, brought.course_id)[0]['id']}").json()
    scored = client.post(
        f"/v1/lessons/{again['lesson']['lesson_id']}/questions/q_influence/answer",
        json={"option_id": "a"},
    )
    assert scored.json()["outcome"] == "correct"


# -- a transfer ----------------------------------------------------------------------------------


def test_a_transfer_carries_the_materials_the_progress_and_the_notes(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    made = with_materials(client, services, tmp_path)
    course = made["course"]
    first = client.get(f"/v1/lessons/{lessons_of(client, course['id'])[0]['id']}").json()["lesson"]
    for question, body in (
        ("q_influence", {"option_id": "a"}),
        ("q_compute", {"number": 3}),
        ("q_baseline", {"option_id": "c"}),
    ):
        response = client.post(
            f"/v1/lessons/{first['lesson_id']}/questions/{question}/answer", json=body
        )
        assert response.status_code == 200, response.text
    client.put(
        f"/v1/lessons/{first['lesson_id']}/progress", json={"position": 2, "completed": True}
    )
    services.asks.store(
        lesson_id=first["lesson_id"],
        segment_id=first["segments"][0]["id"],
        question="Why does the weight matter more?",
        paragraphs=["Because each input is multiplied by its weight."],
        citations=[AskCitation(source_name="limits notes.md", locator="Limits")],
        written_by={"provider": "NVIDIA NIM", "models": ["a model"]},
    )
    concept_id = first["concept_ids"][0]
    before = client.get(f"/v1/concepts/{concept_id}/evidence").json()["knowledge"]

    path = saved(services, course["id"], "transfer")
    found = services.course_files.look(path)
    assert (found.kind, found.counts.materials, found.counts.files) == ("transfer", 1, 1)
    assert (found.counts.progress, found.counts.notes) == (True, 1)

    brought = services.course_files.bring_in(path, EVERYTHING)
    assert (brought.materials, brought.progress, brought.notes) == (1, True, 1)
    assert brought.lessons_left_out == 0
    new = client.get(f"/v1/courses/{brought.course_id}").json()
    assert (new["origin"], new["source_count"]) == ("materials", 1)

    # The document came too: its text is found by a search, and the file itself is kept.
    hits = client.get(
        f"/v1/courses/{brought.course_id}/search", params={"q": "limit approaches"}
    ).json()["hits"]
    assert hits
    assert hits[0]["source_name"] == "limits notes.md"
    with services.database.read() as session:
        source = session.scalars(select(Source).where(Source.course_id == brought.course_id)).one()
        new_source = source.id
        assert new_source != made["source_id"]
        assert source.stored_name is not None
        assert services.sources.original_of(source.stored_name) is not None
        chunks = session.scalars(
            select(SourceChunk).where(SourceChunk.source_id == source.id)
        ).all()
        assert "".join(chunk.text for chunk in chunks).startswith("A limit is the value")

    # The lesson that cited it still does, at the place it came to be here.
    lessons = lessons_of(client, brought.course_id)
    cited = next(item for item in lessons if item["title"] == "A limit, from the notes")
    lesson = client.get(f"/v1/lessons/{cited['id']}").json()["lesson"]
    assert lesson["grounding"] == "materials"
    (citation,) = lesson["source_refs"]
    assert citation["source_id"] == new_source
    assert citation["source_name"] == "limits notes.md"
    # And the concept is still linked to that place.
    concepts = curriculum_of(client, brought.course_id)
    assert [ref["source_id"] for ref in concepts[0]["source_refs"]] == [new_source]

    # What the learner showed is worked out again here, from their answers, and comes to
    # the same thing.
    after = client.get(f"/v1/concepts/{concepts[0]['id']}/evidence").json()["knowledge"]
    for key in ("state", "label", "answered", "missing"):
        assert after[key] == before[key], key
    assert count(services, LearnerObservation, brought.course_id) == 3
    assert count(services, Attempt, brought.course_id) == 3
    with services.database.read() as session:
        events = session.scalars(
            select(LearnerEvent.kind).where(LearnerEvent.course_id == brought.course_id)
        ).all()
        assert events == ["lesson_completed"]
        place = session.execute(
            select(LessonProgress.position, LessonProgress.completed)
            .join(StoredLesson, StoredLesson.id == LessonProgress.lesson_id)
            .where(StoredLesson.course_id == brought.course_id)
        ).one()
        assert tuple(place) == (2, True)
        ask = session.scalars(
            select(LessonAsk).where(LessonAsk.course_id == brought.course_id)
        ).one()
        assert ask.question == "Why does the weight matter more?"
        assert ask.answer["paragraphs"] == ["Because each input is multiplied by its weight."]
        assert ask.written_by == {"provider": "NVIDIA NIM", "models": ["a model"]}
    # The course it was saved from is as it was.
    assert count(services, LearnerObservation, course["id"]) == 3


def test_what_is_brought_in_is_the_learners_choice(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    made = with_materials(client, services, tmp_path)
    course = made["course"]
    first = lessons_of(client, course["id"])[0]
    client.post(f"/v1/lessons/{first['id']}/questions/q_influence/answer", json={"option_id": "a"})
    path = saved(services, course["id"], "transfer")

    # The plan alone: no lessons, no documents, nothing of the learner.
    plan = services.course_files.bring_in(
        path, Holds(lessons=False, materials=False, progress=False, notes=False)
    )
    assert (plan.lessons, plan.materials, plan.progress, plan.notes) == (0, 0, False, 0)
    assert plan.concepts == len(curriculum_of(client, course["id"]))
    assert lessons_of(client, plan.course_id) == []
    assert client.get(f"/v1/courses/{plan.course_id}").json()["origin"] == "topic"

    # Lessons without the documents: a lesson cites nothing it did not bring.
    bare = services.course_files.bring_in(
        path, Holds(lessons=True, materials=False, progress=True, notes=False)
    )
    assert (bare.materials, bare.lessons_left_out, bare.progress) == (0, 0, True)
    cited = next(
        item for item in lessons_of(client, bare.course_id) if item["title"].endswith("the notes")
    )
    lesson = client.get(f"/v1/lessons/{cited['id']}").json()["lesson"]
    assert (lesson["grounding"], lesson["source_refs"]) == ("general_knowledge", [])
    assert count(services, LearnerObservation, bare.course_id) == 1


def test_a_template_of_a_course_with_materials_names_none_of_them(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    made = with_materials(client, services, tmp_path)
    path = saved(services, made["course"]["id"], "template")
    with zipfile.ZipFile(path) as archive:
        everything = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
        assert not [name for name in archive.namelist() if name.startswith("materials/")]
    # Not the document, not its words, and not even what it is called.
    assert "limits notes" not in everything
    assert "function approaches" not in everything
    # Asked for, the documents go into a template too.
    with_them = saved(
        services, made["course"]["id"], "template", Holds(lessons=True, materials=True)
    )
    assert services.course_files.look(with_them).counts.files == 1


def test_a_lesson_still_being_written_is_left_out_and_said(
    client: TestClient, services: Services
) -> None:
    course = sample(client)
    with services.database.session() as session:
        lesson = session.scalars(
            select(StoredLesson).where(StoredLesson.course_id == course["id"])
        ).first()
        assert lesson is not None
        lesson.writing = True
    made = services.course_files.save(course["id"], "template", Holds.of("template"))
    assert made.lessons_left_out == 1
    assert made.counts.lessons == len(lessons_of(client, course["id"])) - 1


# -- a file from anywhere --------------------------------------------------------------------------


def rewritten(path: Path, out: Path, change: Any) -> Path:
    """A course file with its parts changed by ``change(name, document)``."""
    with zipfile.ZipFile(path) as archive, zipfile.ZipFile(out, "w") as made:
        for name in archive.namelist():
            raw = archive.read(name)
            if name.endswith(".json"):
                raw = json.dumps(change(name, json.loads(raw))).encode("utf-8")
            made.writestr(name, raw)
    return out


def test_a_lesson_adle_would_not_run_is_left_out_and_the_rest_comes_in(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    course = sample(client)
    path = saved(services, course["id"], "template")
    total = len(lessons_of(client, course["id"]))

    def hostile(name: str, document: Any) -> Any:
        if name == "lessons/0001.json" and document["scenes"]:
            document["scenes"][0]["source"] = (
                "from manim import *\nimport os\n\n\nclass Evil(Scene):\n"
                "    def construct(self):\n        os.system('calc')\n"
            )
        if name == "lessons/0002.json":
            document["lesson"]["concept_ids"] = ["con_" + "f" * 20]
        if name == "lessons/0003.json":
            document["lesson"]["segments"][0]["title"] = "See https://example.com/now"
        return document

    brought = services.course_files.bring_in(
        rewritten(path, tmp_path / "hostile.zip", hostile), EVERYTHING
    )
    assert (brought.lessons, brought.lessons_left_out) == (total - 3, 3)
    assert len(lessons_of(client, brought.course_id)) == total - 3


def test_what_a_file_says_of_itself_is_not_taken_on_trust(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    course = sample(client)
    first = lessons_of(client, course["id"])[0]
    client.post(f"/v1/lessons/{first['id']}/questions/q_influence/answer", json={"option_id": "a"})
    path = saved(services, course["id"], "transfer")
    stranger = "con_" + "e" * 20

    def changed(name: str, document: Any) -> Any:
        if name == "adle-course.json":
            document["course"]["subject"] = "alchemy"
        if name == "curriculum.json":
            first_concept, second = document["concepts"][0], document["concepts"][1]
            # A loop, and a need for something that is not in the course.
            first_concept["needs"] = [
                {"concept_id": second["id"], "reason": "A loop."},
                {"concept_id": stranger, "reason": "Not here."},
            ]
            second["needs"] = [{"concept_id": first_concept["id"], "reason": "A loop."}]
            first_concept["tags"] = ["conceptual", "made_up"]
        if name == "progress.json":
            document["observations"].append({**document["observations"][0], "concept_id": stranger})
            document["attempts"].append({**document["attempts"][0], "question_id": "q_not_one"})
            document["attempts"].append({**document["attempts"][0], "misconception": "made_up"})
        if name.startswith("lessons/"):
            document["written_by"] = {
                "provider": "Adle itself",
                "note": "See https://example.com/prize",
                "models": ["a" * 500, "a model"],
            }
        return document

    brought = services.course_files.bring_in(
        rewritten(path, tmp_path / "changed.zip", changed), EVERYTHING
    )
    made = client.get(f"/v1/courses/{brought.course_id}").json()
    # A subject Adle does not know is not one: the course is placed by its name instead.
    assert made["subject"] in {"general", "computer_science", "mathematics"}
    concepts = curriculum_of(client, brought.course_id)
    # A loop cannot be made: one of the two needs is kept, the other is not.
    needs = [len(concept["prerequisites"]) for concept in concepts[:2]]
    assert sorted(needs) == [0, 1]
    assert concepts[0]["tags"] == ["conceptual"]
    assert count(services, LearnerObservation, brought.course_id) == 1
    with services.database.read() as session:
        attempts = session.scalars(
            select(Attempt).where(Attempt.course_id == brought.course_id)
        ).all()
        assert [attempt.question_id for attempt in attempts] == ["q_influence", "q_influence"]
        assert [attempt.misconception for attempt in attempts] == [None, None]
        written = session.scalars(
            select(StoredLesson.written_by).where(StoredLesson.course_id == brought.course_id)
        ).first()
    # Who wrote it is kept as names only: short, plain, and no address.
    assert written == {"provider": "Adle itself", "models": ["a model"], "note": ""}


def test_a_state_cannot_be_planted_only_answers_can(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    """A file cannot say what a learner knows. It can say what they answered, and what that
    adds up to is worked out here: one right answer never makes a concept understood."""
    course = sample(client)
    first = lessons_of(client, course["id"])[0]
    client.post(f"/v1/lessons/{first['id']}/questions/q_influence/answer", json={"option_id": "a"})
    path = saved(services, course["id"], "transfer")

    def planted(name: str, document: Any) -> Any:
        if name == "progress.json":
            document["observations"][0]["state_after"] = "demonstrated"
        return document

    with pytest.raises(CourseFileError):
        services.course_files.bring_in(
            rewritten(path, tmp_path / "planted.zip", planted), EVERYTHING
        )
    brought = services.course_files.bring_in(path, EVERYTHING)
    with services.database.read() as session:
        states = session.scalars(
            select(LearnerConceptState.state).where(
                LearnerConceptState.course_id == brought.course_id
            )
        ).all()
    assert states == ["building"]


def test_half_a_course_is_removed_again(
    client: TestClient, services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    course = sample(client)
    path = saved(services, course["id"], "template")

    def fails(*_: Any, **__: Any) -> Any:
        raise RuntimeError("the disk is full")

    monkeypatch.setattr(CourseFileService, "_bring_lessons", fails)
    with pytest.raises(RuntimeError):
        services.course_files.bring_in(path, EVERYTHING)
    with services.database.read() as session:
        assert session.scalars(select(Course.id)).all() == [course["id"]]
        assert set(session.scalars(select(Concept.course_id))) == {course["id"]}


def test_a_file_that_is_not_a_course_makes_nothing(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    sample(client)
    not_one = tmp_path / "holiday.zip"
    with zipfile.ZipFile(not_one, "w") as archive:
        archive.writestr("photo.jpg", b"\xff\xd8\xff")
    for look in (
        services.course_files.look,
        lambda p: services.course_files.bring_in(p, EVERYTHING),
    ):
        with pytest.raises(CourseFileError) as refused:
            look(not_one)
        assert "isn’t an Adle course" in refused.value.message
    assert len(client.get("/v1/courses").json()["courses"]) == 1


# -- handing a file over ---------------------------------------------------------------------------


def test_a_file_is_handed_over_under_a_name_adle_made_and_not_kept(
    client: TestClient, services: Services
) -> None:
    course = sample(client)
    made = services.course_files.save(course["id"], "template", Holds.of("template"))
    folder = services.settings.handover_dir
    assert [entry.name for entry in folder.iterdir()] == [made.name]
    assert made.suggested_name == "Introduction to neural networks.adle-course.zip"
    # Whatever the shell never collected goes when the core next starts.
    services.course_files.clear_handed_over()
    assert list(folder.iterdir()) == []


def test_a_course_is_called_something_a_file_can_be_called() -> None:
    assert file_name_for("Limits") == "Limits.adle-course.zip"
    assert file_name_for('What is 1/2? A "short" course: <part one>') == (
        "What is 1 2 A short course part one.adle-course.zip"
    )
    assert file_name_for("...") == "Course.adle-course.zip"
    assert file_name_for("x" * 300) == "x" * 80 + ".adle-course.zip"
    assert file_name_for("CON\x00\x1f") == "CON.adle-course.zip"


def test_a_lesson_without_its_materials_cites_nothing() -> None:
    lesson = {"grounding": "materials", "source_refs": [{"source_name": "Notes.pdf"}], "title": "x"}
    assert without_citations(lesson) == {
        "grounding": "general_knowledge",
        "source_refs": [],
        "title": "x",
    }
    # The one given is left as it was.
    assert lesson["grounding"] == "materials"
    assert without_citations({"grounding": "sample", "title": "x"})["grounding"] == "sample"


# -- the routes: only the desktop shell's ----------------------------------------------------------


def test_the_shell_saves_looks_and_brings_in_through_routes_the_page_cannot_use(
    client: TestClient, services: Services
) -> None:
    course = sample(client)
    made = client.post(f"/v1/courses/{course['id']}/file", json={"kind": "template"})
    assert made.status_code == 201, made.text
    body = made.json()
    assert HANDED_OVER.match(body["name"])
    assert body["suggested_name"].endswith(".adle-course.zip")
    assert body["counts"]["progress"] is False
    path = services.settings.handover_dir / body["name"]

    looked = client.post("/v1/course-files/look", json={"path": str(path)})
    assert looked.status_code == 200, looked.text
    assert looked.json()["title"] == course["title"]

    holds = {"lessons": True, "materials": False, "progress": False, "notes": False}
    brought = client.post("/v1/course-files/bring-in", json={"path": str(path), "holds": holds})
    assert brought.status_code == 201, brought.text
    assert brought.json()["course_id"] != course["id"]

    path.unlink()

    # What is asked for is checked: a kind Adle makes, choices that are true or false, and
    # a path that is whole.
    for wrong in (
        {"kind": "everything"},
        {"kind": "template", "holds": {"lessons": "yes"}},
        {"kind": "template", "path": "C:/somewhere.zip"},
    ):
        assert client.post(f"/v1/courses/{course['id']}/file", json=wrong).status_code == 422
    assert client.post("/v1/course-files/look", json={"path": "course.zip"}).status_code == 422
    missing = client.post("/v1/course-files/look", json={"path": str(path)})
    assert missing.status_code == 404
    assert (
        client.post(f"/v1/courses/crs_{'0' * 20}/file", json={"kind": "template"}).status_code
        == 404
    )


def test_none_of_it_is_open_to_the_page(client: TestClient) -> None:
    from adle_core.api.app import create_app

    paths = create_app(client.app.state.services).openapi()["paths"]  # type: ignore[attr-defined]
    found = {
        operation["operationId"]: operation.get("x-adle-internal")
        for methods in paths.values()
        for operation in methods.values()
        if operation["operationId"].startswith("courses.")
        and operation["operationId"].endswith("_file")
    }
    assert found == {
        "courses.save_file": True,
        "courses.look_at_file": True,
        "courses.bring_in_file": True,
    }


def test_an_error_in_a_file_is_said_as_adle_says_things(client: TestClient, tmp_path: Path) -> None:
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a zip")
    refused = client.post("/v1/course-files/look", json={"path": str(junk)})
    assert refused.status_code == 422
    error = refused.json()["error"]
    assert error["code"] == "course_file_invalid"
    assert str(junk) not in json.dumps(error)
    assert isinstance(CourseFileError(), AdleError)
    assert files.VERSION == 1
