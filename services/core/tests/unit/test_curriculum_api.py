"""The curriculum of a course, through the HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.retrieval import (
    Passage,
    any_term_query,
    key_terms,
    spread_across_sources,
)
from adle_core.application.services import Services

DOCUMENTS = Path(__file__).resolve().parents[4] / "fixtures" / "sample-documents"
UNKNOWN_CONCEPT = "con_00000000000000000000"
#: Joins the steps of a heading path in a stored section title.
ARROW = chr(0x203A)


def create_course(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {
        "title": "Neural networks",
        "origin": "topic",
        "topic": "How networks learn",
        **overrides,
    }
    response = client.post("/v1/courses", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def import_files(client: TestClient, services: Services, course_id: str, *names: str) -> None:
    paths = [str(DOCUMENTS / name) for name in names]
    response = client.post(f"/v1/courses/{course_id}/sources/import", json={"paths": paths})
    assert response.status_code == 202, response.text
    services.jobs.wait(response.json()["id"])


def add(client: TestClient, course_id: str, title: str, *objectives: str) -> dict[str, Any]:
    """Create a concept and return it as the API reports it."""
    response = client.post(
        f"/v1/courses/{course_id}/concepts",
        json={"title": title, "objectives": list(objectives)},
    )
    assert response.status_code == 201, response.text
    return response.json()["concepts"][-1]


def curriculum(client: TestClient, course_id: str) -> dict[str, Any]:
    response = client.get(f"/v1/courses/{course_id}/curriculum")
    assert response.status_code == 200, response.text
    return response.json()


def needs(client: TestClient, concept: dict[str, Any], *prerequisites: dict[str, Any]) -> Any:
    return client.put(
        f"/v1/concepts/{concept['id']}/prerequisites",
        json={"prerequisites": [{"concept_id": item["id"]} for item in prerequisites]},
    )


def titles(body: dict[str, Any]) -> list[str]:
    return [concept["title"] for concept in body["concepts"]]


def ordered_titles(body: dict[str, Any]) -> list[str]:
    by_id = {concept["id"]: concept["title"] for concept in body["concepts"]}
    return [by_id[concept_id] for concept_id in body["learning_order"]]


# -- concepts --------------------------------------------------------------


def test_a_new_course_has_an_empty_curriculum_that_cannot_be_started(client: TestClient) -> None:
    course = create_course(client)
    assert curriculum(client, course["id"]) == {
        "course_id": course["id"],
        "concepts": [],
        "learning_order": [],
        "issues": [],
        "startable": False,
    }
    assert client.get("/v1/courses/crs_00000000000000000000/curriculum").status_code == 404


def test_concepts_are_added_in_order_with_their_objectives(client: TestClient) -> None:
    course = create_course(client)
    first = add(client, course["id"], "  Weights   and biases ", "State what a weight does.")
    add(client, course["id"], "Activation functions")

    assert first["id"].startswith("con_")
    assert first["title"] == "Weights and biases"
    assert first["position"] == 0
    assert first["origin"] == "learner"
    assert first["layer"] == 0
    assert [objective["statement"] for objective in first["objectives"]] == [
        "State what a weight does."
    ]
    assert first["knowledge"] == {
        "state": "not_assessed",
        "label": "Not started",
        "missing": ["some answered questions"],
        "answered": 0,
        "self_report": None,
        "review_due_at": None,
    }

    body = curriculum(client, course["id"])
    assert titles(body) == ["Weights and biases", "Activation functions"]
    assert ordered_titles(body) == ["Weights and biases", "Activation functions"]
    assert body["startable"] is True
    # A concept with nothing to check understanding against is flagged, not blocked.
    assert [(issue["code"], issue["severity"]) for issue in body["issues"]] == [
        ("no_objective", "warning")
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "Loss", "objectives": [""]},
        {"title": "Loss", "objectives": ["Explain it."] * 13},
        {"title": "Loss", "position": 3},
    ],
)
def test_invalid_concepts_are_rejected(client: TestClient, body: dict[str, Any]) -> None:
    course = create_course(client)
    response = client.post(f"/v1/courses/{course['id']}/concepts", json=body)
    assert response.status_code == 422
    assert curriculum(client, course["id"])["concepts"] == []


def test_a_concept_can_be_renamed_described_and_classified(client: TestClient) -> None:
    course = create_course(client)
    concept = add(client, course["id"], "Los")
    response = client.patch(
        f"/v1/concepts/{concept['id']}",
        json={
            "title": "Loss",
            "summary": " How wrong a prediction is. ",
            "complexity": 1,
            "tags": ["visual", "conceptual"],
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()["concepts"][0]
    assert updated["title"] == "Loss"
    assert updated["summary"] == "How wrong a prediction is."
    assert updated["complexity"] == 1
    assert updated["tags"] == ["conceptual", "visual"]

    assert (
        client.patch(f"/v1/concepts/{concept['id']}", json={"tags": ["magic"]}).status_code == 422
    )
    assert client.patch(f"/v1/concepts/{concept['id']}", json={"complexity": 9}).status_code == 422
    assert client.patch(f"/v1/concepts/{UNKNOWN_CONCEPT}", json={"title": "x"}).status_code == 404


def test_objectives_keep_their_identity_when_edited(client: TestClient) -> None:
    course = create_course(client)
    concept = add(client, course["id"], "Loss", "Define loss.", "Compute a squared error.")
    define, compute = concept["objectives"]

    response = client.put(
        f"/v1/concepts/{concept['id']}/objectives",
        json={
            "objectives": [
                {"statement": "Say why errors are squared."},
                {"id": compute["id"], "statement": "Compute a mean squared error by hand."},
            ]
        },
    )
    assert response.status_code == 200, response.text
    objectives = response.json()["concepts"][0]["objectives"]
    assert [objective["statement"] for objective in objectives] == [
        "Say why errors are squared.",
        "Compute a mean squared error by hand.",
    ]
    assert objectives[1]["id"] == compute["id"]
    assert define["id"] not in {objective["id"] for objective in objectives}

    # An objective of another concept cannot be claimed.
    other = add(client, course["id"], "Gradient", "Define a gradient.")
    stolen = client.put(
        f"/v1/concepts/{concept['id']}/objectives",
        json={"objectives": [{"id": other["objectives"][0]["id"], "statement": "Mine now."}]},
    )
    assert stolen.status_code == 422
    assert "Reload" in stolen.json()["error"]["message"]


# -- order and prerequisites -----------------------------------------------


def test_the_learning_order_follows_prerequisites_then_the_learners_own_order(
    client: TestClient,
) -> None:
    course = create_course(client)
    descent = add(client, course["id"], "Gradient descent", "Apply an update step.")
    loss = add(client, course["id"], "Loss", "Define loss.")
    weights = add(client, course["id"], "Weights", "Say what a weight does.")

    assert needs(client, descent, loss).status_code == 200
    body = needs(client, loss, weights).json()

    assert titles(body) == ["Gradient descent", "Loss", "Weights"]
    assert ordered_titles(body) == ["Weights", "Loss", "Gradient descent"]
    layers = {concept["title"]: concept["layer"] for concept in body["concepts"]}
    assert layers == {"Weights": 0, "Loss": 1, "Gradient descent": 2}
    assert body["concepts"][0]["prerequisites"] == [
        {"concept_id": loss["id"], "title": "Loss", "reason": ""}
    ]
    assert body["issues"] == []


def test_the_learner_can_put_concepts_in_their_own_order(client: TestClient) -> None:
    course = create_course(client)
    for title in ("One", "Two", "Three", "Four"):
        add(client, course["id"], title, "Do it.")
    ids = [concept["id"] for concept in curriculum(client, course["id"])["concepts"]]
    url = f"/v1/courses/{course['id']}/concept-order"

    moved = client.put(url, json={"concept_ids": [ids[3], ids[0], ids[1], ids[2]]})
    assert moved.status_code == 200, moved.text
    assert titles(moved.json()) == ["Four", "One", "Two", "Three"]
    assert ordered_titles(moved.json()) == ["Four", "One", "Two", "Three"]
    assert [concept["position"] for concept in moved.json()["concepts"]] == [0, 1, 2, 3]

    # A prerequisite still wins over the learner's own order.
    four, one = moved.json()["concepts"][0], moved.json()["concepts"][1]
    assert ordered_titles(needs(client, four, one).json()) == ["One", "Four", "Two", "Three"]

    # The new order must name every concept of the course exactly once.
    for incomplete in (ids[:3], [*ids, ids[0]], [*ids[:3], UNKNOWN_CONCEPT], []):
        refused = client.put(url, json={"concept_ids": incomplete})
        assert refused.status_code == 422
        assert "exactly once" in refused.json()["error"]["message"]
    assert titles(curriculum(client, course["id"])) == ["Four", "One", "Two", "Three"]


def test_a_prerequisite_can_say_why_it_is_needed(client: TestClient) -> None:
    course = create_course(client)
    chain = add(client, course["id"], "Chain rule", "Differentiate a composition.")
    backprop = add(client, course["id"], "Backpropagation", "Trace a gradient backwards.")
    response = client.put(
        f"/v1/concepts/{backprop['id']}/prerequisites",
        json={
            "prerequisites": [
                {
                    "concept_id": chain["id"],
                    "reason": "  Backpropagation is the chain rule applied layer by layer.  ",
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["concepts"][1]["prerequisites"] == [
        {
            "concept_id": chain["id"],
            "title": "Chain rule",
            "reason": "Backpropagation is the chain rule applied layer by layer.",
        }
    ]
    # Replacing the list removes what is no longer in it.
    cleared = client.put(f"/v1/concepts/{backprop['id']}/prerequisites", json={"prerequisites": []})
    assert cleared.json()["concepts"][1]["prerequisites"] == []


def test_a_link_that_would_close_a_loop_is_refused_with_the_loop_spelled_out(
    client: TestClient,
) -> None:
    course = create_course(client)
    weights = add(client, course["id"], "Weights", "Do it.")
    loss = add(client, course["id"], "Loss", "Do it.")
    descent = add(client, course["id"], "Gradient descent", "Do it.")
    assert needs(client, loss, weights).status_code == 200
    assert needs(client, descent, loss).status_code == 200

    refused = needs(client, weights, descent)
    assert refused.status_code == 409
    error = refused.json()["error"]
    assert error["code"] == "prerequisite_loop"
    assert (
        'That would make a loop: "Weights" needs "Gradient descent" needs "Loss" needs "Weights".'
        in error["message"]
    )
    # Nothing was changed.
    body = curriculum(client, course["id"])
    assert body["concepts"][0]["prerequisites"] == []
    assert ordered_titles(body) == ["Weights", "Loss", "Gradient descent"]
    assert body["startable"] is True


def test_other_impossible_prerequisites_are_refused(client: TestClient) -> None:
    course = create_course(client)
    elsewhere = create_course(client, title="Another course")
    loss = add(client, course["id"], "Loss", "Do it.")
    weights = add(client, course["id"], "Weights", "Do it.")
    foreign = add(client, elsewhere["id"], "Not in this course", "Do it.")

    itself = needs(client, loss, loss)
    assert itself.status_code == 422
    assert "its own prerequisite" in itself.json()["error"]["message"]

    twice = needs(client, loss, weights, weights)
    assert twice.status_code == 422
    assert "twice" in twice.json()["error"]["message"]

    from_elsewhere = needs(client, loss, foreign)
    assert from_elsewhere.status_code == 422
    assert "no longer part of this course" in from_elsewhere.json()["error"]["message"]

    malformed = client.put(
        f"/v1/concepts/{loss['id']}/prerequisites",
        json={"prerequisites": [{"concept_id": "../../etc/passwd"}]},
    )
    assert malformed.status_code == 422
    assert "passwd" not in malformed.text
    assert curriculum(client, course["id"])["concepts"][0]["prerequisites"] == []


def test_removing_a_concept_removes_the_links_to_it(client: TestClient) -> None:
    course = create_course(client)
    weights = add(client, course["id"], "Weights", "Do it.")
    loss = add(client, course["id"], "Loss", "Do it.")
    descent = add(client, course["id"], "Gradient descent", "Do it.")
    needs(client, loss, weights)
    needs(client, descent, loss)

    response = client.delete(f"/v1/concepts/{loss['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert titles(body) == ["Weights", "Gradient descent"]
    assert [concept["position"] for concept in body["concepts"]] == [0, 1]
    assert body["concepts"][1]["prerequisites"] == []
    assert body["issues"] == []
    assert body["startable"] is True
    assert client.delete(f"/v1/concepts/{loss['id']}").status_code == 404


def test_a_course_has_a_limit_on_concepts(client: TestClient, services: Services) -> None:
    course = create_course(client)
    for index in range(200):
        services.curriculum.create_concept(course["id"], title=f"Concept {index}")
    response = client.post(f"/v1/courses/{course['id']}/concepts", json={"title": "One too many"})
    assert response.status_code == 422
    assert "at most 200" in response.json()["error"]["message"]


# -- materials -------------------------------------------------------------


def test_headings_of_imported_materials_are_offered_as_a_starting_outline(
    client: TestClient, services: Services
) -> None:
    course = create_course(client, origin="materials", topic=None)
    import_files(
        client, services, course["id"], "neural-networks-syllabus.md", "course-outline.docx"
    )

    response = client.get(f"/v1/courses/{course['id']}/outline")
    assert response.status_code == 200, response.text
    candidates = response.json()["candidates"]
    assert [(item["source_name"], item["title"]) for item in candidates] == [
        ("neural-networks-syllabus.md", "The perceptron"),
        ("neural-networks-syllabus.md", "Activation functions"),
        ("neural-networks-syllabus.md", "Forward propagation"),
        ("neural-networks-syllabus.md", "Loss"),
        ("neural-networks-syllabus.md", "Derivatives and the chain rule"),
        ("neural-networks-syllabus.md", "Backpropagation"),
        ("neural-networks-syllabus.md", "Gradient descent"),
        ("course-outline.docx", "Neurons"),
        ("course-outline.docx", "Learning"),
    ]
    # Looking at suggestions creates nothing.
    assert curriculum(client, course["id"])["concepts"] == []

    chosen = [candidates[0]["section_id"], candidates[3]["section_id"]]
    added = client.post(f"/v1/courses/{course['id']}/outline", json={"section_ids": chosen})
    assert added.status_code == 201, added.text
    body = added.json()
    assert titles(body) == ["The perceptron", "Loss"]
    perceptron = body["concepts"][0]
    assert perceptron["origin"] == "outline"
    assert perceptron["prerequisites"] == []
    assert [(ref["source_name"], ref["section_title"]) for ref in perceptron["source_refs"]] == [
        (
            "neural-networks-syllabus.md",
            f"Introduction to Neural Networks {ARROW} Unit 1: The perceptron",
        )
    ]

    # What has been added is not offered again, and adding it twice does nothing.
    remaining = client.get(f"/v1/courses/{course['id']}/outline").json()["candidates"]
    assert "Loss" not in [item["title"] for item in remaining]
    again = client.post(f"/v1/courses/{course['id']}/outline", json={"section_ids": chosen})
    assert titles(again.json()) == ["The perceptron", "Loss"]


def test_an_outline_can_only_use_headings_of_the_same_course(
    client: TestClient, services: Services
) -> None:
    course = create_course(client, origin="materials", topic=None)
    other = create_course(client, title="Other", origin="materials", topic=None)
    import_files(client, services, other["id"], "neural-networks-syllabus.md")
    foreign = client.get(f"/v1/courses/{other['id']}/outline").json()["candidates"][0]

    response = client.post(
        f"/v1/courses/{course['id']}/outline", json={"section_ids": [foreign["section_id"]]}
    )
    assert response.status_code == 404
    assert curriculum(client, course["id"])["concepts"] == []
    assert client.get(f"/v1/courses/{course['id']}/outline").json() == {"candidates": []}
    assert (
        client.post(f"/v1/courses/{course['id']}/outline", json={"section_ids": []}).status_code
        == 422
    )


def test_a_concept_can_be_linked_to_places_in_the_materials(
    client: TestClient, services: Services
) -> None:
    course = create_course(client, origin="materials", topic=None)
    import_files(client, services, course["id"], "lecture-notes.pdf", "study-notes.txt")
    loss = add(client, course["id"], "Loss function", "Define the mean squared error.")

    # A course built from materials says when a concept is not tied to them.
    assert [issue["code"] for issue in curriculum(client, course["id"])["issues"]] == [
        "no_source_reference"
    ]

    passages = client.get(f"/v1/concepts/{loss['id']}/passages").json()["passages"]
    assert passages
    best = passages[0]
    assert best["source_name"] == "lecture-notes.pdf"
    assert best["page_number"] == 1
    assert "mean squared error" in best["text"]

    linked = client.post(
        f"/v1/concepts/{loss['id']}/source-refs", json={"section_id": best["section_id"]}
    )
    assert linked.status_code == 200, linked.text
    refs = linked.json()["concepts"][0]["source_refs"]
    assert [(ref["source_name"], ref["page_number"]) for ref in refs] == [("lecture-notes.pdf", 1)]
    assert linked.json()["issues"] == []

    # Linking the same place twice changes nothing.
    again = client.post(
        f"/v1/concepts/{loss['id']}/source-refs", json={"section_id": best["section_id"]}
    )
    assert len(again.json()["concepts"][0]["source_refs"]) == 1

    removed = client.delete(f"/v1/concepts/{loss['id']}/source-refs/{refs[0]['id']}")
    assert removed.status_code == 200
    assert removed.json()["concepts"][0]["source_refs"] == []
    assert (
        client.delete(f"/v1/concepts/{loss['id']}/source-refs/{refs[0]['id']}").status_code == 404
    )


def test_links_to_materials_cannot_cross_courses(client: TestClient, services: Services) -> None:
    course = create_course(client, origin="materials", topic=None)
    other = create_course(client, title="Other", origin="materials", topic=None)
    import_files(client, services, other["id"], "study-notes.txt")
    source = client.get(f"/v1/courses/{other['id']}/sources").json()["sources"][0]
    section = client.get(f"/v1/sources/{source['id']}").json()["sections"][0]
    concept = add(client, course["id"], "Loss", "Do it.")

    response = client.post(
        f"/v1/concepts/{concept['id']}/source-refs", json={"section_id": section["id"]}
    )
    assert response.status_code == 404
    assert "no longer in this course" in response.json()["error"]["message"]


def test_removing_a_source_keeps_the_concept_and_says_it_lost_its_grounding(
    client: TestClient, services: Services
) -> None:
    course = create_course(client, origin="materials", topic=None)
    import_files(client, services, course["id"], "neural-networks-syllabus.md")
    candidates = client.get(f"/v1/courses/{course['id']}/outline").json()["candidates"]
    client.post(
        f"/v1/courses/{course['id']}/outline",
        json={"section_ids": [candidates[0]["section_id"]]},
    )
    source_id = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"][0]["id"]

    assert client.delete(f"/v1/sources/{source_id}").status_code == 204
    body = curriculum(client, course["id"])
    assert titles(body) == ["The perceptron"]
    assert body["concepts"][0]["source_refs"] == []
    assert "no_source_reference" in [issue["code"] for issue in body["issues"]]
    assert "“The perceptron” isn’t linked to anything in your materials." in [
        issue["message"] for issue in body["issues"]
    ]


def test_passages_for_a_concept_without_materials_is_an_empty_answer(client: TestClient) -> None:
    course = create_course(client)
    concept = add(client, course["id"], "Loss", "Define loss.")
    assert client.get(f"/v1/concepts/{concept['id']}/passages").json() == {"passages": []}
    assert client.get(f"/v1/concepts/{UNKNOWN_CONCEPT}/passages").status_code == 404
    assert (
        client.get(f"/v1/concepts/{concept['id']}/passages", params={"limit": 99}).status_code
        == 422
    )


def test_deleting_a_course_removes_its_curriculum(client: TestClient) -> None:
    course = create_course(client)
    weights = add(client, course["id"], "Weights", "Do it.")
    loss = add(client, course["id"], "Loss", "Do it.")
    needs(client, loss, weights)
    client.post(f"/v1/concepts/{loss['id']}/self-rating", json={"level": "some"})

    assert client.delete(f"/v1/courses/{course['id']}").status_code == 204
    assert client.get(f"/v1/concepts/{loss['id']}/evidence").status_code == 404
    assert client.patch(f"/v1/concepts/{weights['id']}", json={"title": "x"}).status_code == 404


# -- retrieval queries -----------------------------------------------------


def test_key_terms_drop_filler_and_repeats() -> None:
    assert key_terms("The loss of the network, and THE Loss function") == [
        "loss",
        "network",
        "function",
    ]
    assert key_terms("a of the") == []
    assert len(key_terms(" ".join(f"term{index}" for index in range(100)))) == 24


def test_retrieval_queries_never_carry_search_syntax() -> None:
    assert any_term_query("the of") is None
    assert any_term_query('loss" OR text:* NEAR(') == '"loss" OR "text" OR "near"'
    assert any_term_query("gradient-descent (SGD)") == '"gradient" OR "descent" OR "sgd"'


def passage(chunk_id: int, source: str, section: str) -> Passage:
    return Passage(
        chunk_id=chunk_id,
        source_id=source,
        source_name=f"{source}.md",
        section_id=section,
        section_title=section,
        page_number=None,
        text="text",
    )


def test_one_long_document_does_not_crowd_out_the_others() -> None:
    ranked = [
        passage(1, "syllabus", "s1"),
        passage(2, "syllabus", "s1"),  # the same section again
        passage(3, "syllabus", "s2"),
        passage(4, "syllabus", "s3"),
        passage(5, "syllabus", "s4"),
        passage(6, "notes", "n1"),
        passage(7, "notes", "n2"),
        passage(8, "syllabus", "s5"),
    ]
    chosen = spread_across_sources(ranked, 5)
    assert [item.chunk_id for item in chosen] == [1, 3, 4, 6, 7]
    assert len({item.section_id for item in chosen}) == 5


def test_a_single_source_still_fills_every_place() -> None:
    ranked = [passage(index, "syllabus", f"s{index}") for index in range(1, 9)]
    assert [item.chunk_id for item in spread_across_sources(ranked, 5)] == [1, 2, 3, 4, 5]
    assert spread_across_sources(ranked[:2], 5) == ranked[:2]
    assert spread_across_sources([], 5) == []
