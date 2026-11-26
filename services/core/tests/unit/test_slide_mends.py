"""A slide whose words were in each other's way as it was tried is mended (ADR-073)."""

from __future__ import annotations

import copy
import json
import re
import threading
from typing import Any

from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.generation import slide_mends
from adle_core.tools.export_slides import CROWDED
from tests.support.model import LESSON, FakeProvider, text_of

NVIDIA_KEY = "nvapi-test-0000000000000000000000000000"
CROWDED_NOTE = (
    "0 overlapping, 1 under a line, 0 past the edge, 0 without a shadow; water under heat"
)
ELEMENTS = {"ice", "water", "steam", "heat", "note"}


def test_what_a_slide_said_is_read_into_sentences_naming_its_own_elements() -> None:
    notes = [
        "2 overlapping, 1 under a line, 1 past the edge, 0 without a shadow; "
        "note over water; nodes.3 over nodes.1; water under heat; ghost over water",
    ]
    assert slide_mends.crowded(notes)
    assert slide_mends.weight(notes) == 3
    assert slide_mends.faults(notes, ELEMENTS | {"nodes"}) == [
        'The words of "note" lie over the words of "water".',
        'Two of the words of "nodes" lie over each other.',
        'A line of "heat" runs through the words of "water".',
        "Something lies past the edge of the screen.",
    ]
    # Nothing but counts, or nothing over anything: nothing to mend.
    assert not slide_mends.crowded(["0 overlapping, 0 under a line, 2 past the edge, 0 without"])
    assert slide_mends.faults(["1 overlapping, 0 under a line, 0 past the edge"], ELEMENTS) == []


def _lesson_with_a_crowded_slide() -> dict[str, Any]:
    """The stand-in lesson with an arrow through a word on its first part's slide."""
    lesson = copy.deepcopy(LESSON)
    first = lesson["segments"][0]
    first["visual"] = copy.deepcopy(CROWDED["arrow_through_words"])
    first["beats"] = [
        {"say": "Ice, water and steam are one substance in three states."},
        {"say": "[Heat] carries it from one state to the next."},
    ]
    return lesson


def _mended(body: dict[str, Any]) -> str:
    """The model that mends: the same slide, its words moved, the same steps."""
    user = text_of(body["messages"][1]["content"])
    found = re.search(r'<learner_material kind="picture">\n(.*?)\n</learner_material>', user, re.S)
    assert found is not None
    script = json.loads(found.group(1))
    for element in script["elements"]:
        if element["id"] == "water":
            element["text"] = "Water, apart"
            element["place"] = "top"
    return json.dumps({"paragraphs": ["The words are clear now."], "visual": script})


class _App:
    """The app's side: tries each picture, and says the first slide was crowded."""

    def __init__(self, services: Services) -> None:
        self._trials = services.generation.trials
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.slides = 0

    def __enter__(self) -> _App:
        self._trials.waiting()
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(5)

    def _run(self) -> None:
        while not self._stop.is_set():
            for trial in self._trials.waiting():
                notes: tuple[str, ...] = ()
                if trial.scene_class == "Slide":
                    self.slides += 1
                    notes = (CROWDED_NOTE,) if self.slides == 1 else ()
                self._trials.report(trial.id, None, notes)
            self._stop.wait(0.02)


def test_a_crowded_slide_is_sent_back_named_and_mended_beside_the_writing(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    services.credentials.set_api_key(NVIDIA_KEY, "nvidia")
    services.gateway.select("nvidia")
    provider.queue(_lesson_with_a_crowded_slide())
    provider.queue_for("mend", _mended)
    course = client.post(
        "/v1/courses", json={"title": "Matter", "origin": "topic", "topic": "States."}
    ).json()
    curriculum = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={"title": "States of water", "summary": "", "objectives": ["Name the states."]},
    ).json()
    concept = curriculum["concepts"][-1]["id"]
    with _App(services) as app:
        job_id = client.post(f"/v1/concepts/{concept}/lessons").json()["id"]
        job = services.jobs.wait(job_id, timeout=60)
    assert job.status == "succeeded", job.error_message
    # Sent back once, told which of its elements were in whose way, and tried again.
    assert provider.kinds().count("mend") == 1
    mend = provider.prompt(provider.kinds().index("mend"))
    assert 'A line of "heat" runs through the words of "water".' in mend
    assert app.slides == 2
    # Kept in its place, under the same name: a lesson open now finds it there.
    lesson_id = job.result["lesson_id"]
    stored = client.get(f"/v1/lessons/{lesson_id}").json()
    slide = next(scene for scene in stored["scenes"] if scene["scene_class"] == "Slide")
    first = stored["lesson"]["segments"][0]
    assert first["scene"]["scene_id"] == slide["id"]
    assert "Water, apart" in slide["source"]
    assert stored["mending"] is False


def test_a_crowded_slide_keeps_its_shadows_where_the_provider_takes_one_request(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    # AIHubMix takes one request at a time: its small day is not spent on mends.
    assert (
        client.put(
            "/v1/provider/credential", json={"api_key": "sk-test-0123456789abcdefghijklmnop"}
        ).status_code
        == 204
    )
    provider.queue(_lesson_with_a_crowded_slide())
    course = client.post(
        "/v1/courses", json={"title": "Matter", "origin": "topic", "topic": "States."}
    ).json()
    curriculum = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={"title": "States of water", "summary": "", "objectives": ["Name the states."]},
    ).json()
    with _App(services):
        job_id = client.post(f"/v1/concepts/{curriculum['concepts'][-1]['id']}/lessons").json()[
            "id"
        ]
        job = services.jobs.wait(job_id, timeout=60)
    assert job.status == "succeeded", job.error_message
    assert "mend" not in provider.kinds()
