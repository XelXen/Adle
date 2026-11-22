"""A lesson's figures: drawn by the core from the lesson's own text, with no request of their
own (ADR-045). Against the scripted provider; no request leaves the process."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.generation.figures import beat_seconds, compile_figure
from tests.support.model import ANIMATION_SCENE, LESSON, FakeProvider

KEY = "sk-test-0123456789abcdefghijklmnop"

EQUATION = {
    "kind": "equation",
    "steps": ["z = w_1 x_1 + w_2 x_2 + b", "z = (0.5)(2) + (-1)(1) + 0.5", "z = 0.5"],
    "description": "The weighted sum is written out, then filled in with numbers, then worked out.",
}
GRAPH = {
    "kind": "graph",
    "x": [-2, 2],
    "x_label": "x",
    "curves": [{"f": "0.5x + 0.5", "label": "z = 0.5x + 0.5"}],
    "points": [{"x": 1, "label": "x = 1"}],
    "description": "A straight line rises as the input grows; at an input of 1 it reaches 1.",
}
SLIDER = {
    "kind": "graph",
    "x": [-2, 2],
    "curves": [{"f": "w x + 0.5", "label": "z"}],
    "slider": {"name": "w", "label": "w", "min": -2, "max": 2, "value": 0.5},
    "description": "Moving the weight tilts the line: a larger weight makes it steeper.",
}
TABLE = {
    "kind": "table",
    "header": ["input", "weight", "product"],
    "rows": [["2", "0.5", "1"], ["1", "-1", "-1"]],
    "highlight": [1, 2],
    "description": "Each input times its weight: 2 times 0.5 is 1, and 1 times minus 1 is minus 1.",
}


def drafted(**figures: dict[str, Any]) -> dict[str, Any]:
    """The stand-in lesson, with figures in place of its scenes where they are given."""
    lesson = copy.deepcopy(LESSON)
    places = {"explanation": 0, "visualization": 1, "interaction": 3, "worked_example": 4}
    for part, figure in figures.items():
        segment = lesson["segments"][places[part]]
        segment.pop("scene", None)
        segment["figure"] = figure
    return lesson


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def written(client: TestClient, services: Services) -> dict[str, Any]:
    course = client.post(
        "/v1/courses",
        json={"title": "Neural networks", "origin": "topic", "topic": "How a neuron works."},
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
    started = client.post(f"/v1/concepts/{concept}/lessons").json()
    job = services.jobs.wait(started["id"], timeout=60)
    assert job.status == "succeeded", job.error_message
    return dict(job.result)


def test_a_lesson_with_figures_is_written_in_one_request_and_has_them_all(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(
        drafted(explanation=EQUATION, visualization=GRAPH, interaction=SLIDER, worked_example=TABLE)
    )
    result = written(keyed, services)
    # No request for a picture: the core drew them.
    assert provider.kinds() == ["lesson"]
    assert (result["pictures_planned"], result["pictures_made"], result["notes"]) == (4, 4, [])

    loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
    assert loaded["pending_scene_ids"] == []
    scenes = {scene["id"]: scene for scene in loaded["scenes"]}
    by_part = {
        segment["type"]: segment["scene"]["scene_id"]
        for segment in loaded["lesson"]["segments"]
        if segment.get("scene")
    }
    assert set(by_part) == {"explanation", "visualization", "interaction", "worked_example"}
    assert scenes[by_part["interaction"]]["interactive"] is True
    assert scenes[by_part["interaction"]]["controls"] == ["w"]
    assert scenes[by_part["visualization"]]["interactive"] is False
    # Each is the file the figures module writes, paced to what is said over it.
    lesson = drafted(visualization=GRAPH)
    beats = [beat["say"] for beat in lesson["segments"][1]["beats"]]
    expected = compile_figure(GRAPH, beat_seconds=beat_seconds(beats)).source
    assert scenes[by_part["visualization"]]["source"] == expected
    assert scenes[by_part["visualization"]]["scene_class"] == "GraphFigure"
    # The description is what the learner reads when the picture is not seen.
    visual = next(s for s in loaded["lesson"]["segments"] if s["type"] == "visualization")
    assert visual["scene"]["fallback_text"] == GRAPH["description"]


def test_a_figure_that_cannot_be_drawn_costs_its_picture_and_not_the_lesson(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    broken = {**GRAPH, "curves": [{"f": "log(x)"}]}  # no value left of zero
    provider.queue(drafted(visualization=broken, explanation=EQUATION))
    result = written(keyed, services)
    # Not written again for it: one request, and the part is said in words.
    assert provider.kinds()[0] == "lesson"
    assert "lesson" not in provider.kinds()[1:]
    loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
    second = loaded["lesson"]["segments"][1]
    assert second["type"] == "explanation"
    assert loaded["lesson"]["segments"][0]["scene"]["scene_id"]


def test_a_figure_the_model_did_not_describe_is_described_by_adle(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    """A real model left out the description of all five of its figures (2026-11-22): the
    pictures are drawn, and stand in words for what Adle says of their data. A description
    with a link in it is never shown: Adle's stands in its place too."""
    silent = {key: value for key, value in EQUATION.items() if key != "description"}
    linked = {**TABLE, "description": "See https://example.com for the table."}
    provider.queue(drafted(explanation=silent, worked_example=linked))
    result = written(keyed, services)
    loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
    segments = loaded["lesson"]["segments"]
    said = {index: segments[index]["scene"]["fallback_text"] for index in (0, 4)}
    assert said[0] == (
        "The formula $z = w_1 x_1 + w_2 x_2 + b$ is rewritten step by step until it reads "
        "$z = 0.5$."
    )
    assert said[4] == "A table with the columns input, weight and product, and 2 rows."


def test_an_interaction_whose_figure_has_nothing_to_move_is_watched(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(drafted(interaction=GRAPH))
    result = written(keyed, services)
    loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
    fourth = loaded["lesson"]["segments"][3]
    assert fourth["type"] == "visualization"
    assert "prompt" not in fourth


def test_figures_and_a_scene_written_by_the_model_go_together(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(drafted(visualization=GRAPH, explanation=EQUATION), ANIMATION_SCENE)
    result = written(keyed, services)
    # One request for the lesson, and the rest for the one scene left, the interaction's
    # (asked for once more when what came back had nothing to move, as before).
    kinds = provider.kinds()
    assert kinds[0] == "lesson"
    assert set(kinds[1:]) == {"scene"}
    assert result["pictures_planned"] == 3
    loaded = keyed.get(f"/v1/lessons/{result['lesson_id']}").json()
    ids = [scene["id"] for scene in loaded["scenes"]]
    assert len(ids) == len(set(ids)) == 3
