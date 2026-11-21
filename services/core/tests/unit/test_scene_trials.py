"""A picture is tried in the app's player before a learner is shown it (ADR-038).

Against the scripted provider, with the app's side played by a thread that asks for trials
and answers them as told. No request in this file leaves the process.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.scene_trials import (
    PRESENT_SECONDS,
    SceneTrials,
    TrialFailure,
)
from adle_core.application.services import Services
from tests.support.model import ANIMATION_SCENE, INTERACTIVE_SCENE, LESSON, FakeProvider

KEY = "sk-test-0123456789abcdefghijklmnop"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# -- the registry ----------------------------------------------------------------------------


def test_the_app_is_there_while_it_asks_and_not_after() -> None:
    clock = Clock()
    trials = SceneTrials(clock)
    assert not trials.present()
    assert trials.waiting() == []
    assert trials.present()
    clock.now += PRESENT_SECONDS + 1
    assert not trials.present()


def test_a_trial_is_offered_answered_and_withdrawn() -> None:
    trials = SceneTrials()
    trial_id = trials.offer(
        scene_class="Weights", source="from manim import *", interactive=True, controls=("w",)
    )
    (offered,) = trials.waiting()
    assert (offered.id, offered.scene_class, offered.interactive, offered.controls) == (
        trial_id,
        "Weights",
        True,
        ("w",),
    )
    failure = TrialFailure("runtime", "NameError: name 'Arow' is not defined")
    assert trials.report(trial_id, failure)
    # Answered once: a second answer is not taken, and nothing is offered any more.
    assert not trials.report(trial_id, None)
    assert trials.waiting() == []
    assert trials.wait(trial_id, timeout=1) == failure
    # Withdrawn once it has been read: an answer now is let go.
    assert not trials.report(trial_id, None)


def test_a_trial_nobody_answers_is_untried_and_so_is_one_given_up() -> None:
    trials = SceneTrials()
    first = trials.offer(scene_class="A", source="x", interactive=False, controls=())
    assert trials.wait(first, timeout=0.3) == "untried"
    assert trials.waiting() == []
    second = trials.offer(scene_class="B", source="x", interactive=False, controls=())
    assert trials.wait(second, timeout=30, cancelled=lambda: True) == "untried"
    assert trials.wait("trial_00000000000000000000", timeout=1) == "untried"


def test_a_failure_is_told_to_the_model_in_one_short_line() -> None:
    problem = TrialFailure("controls", "TypeError:\n  bad value " + "x" * 900).as_problem()
    assert problem.startswith("The scene failed when a control was moved: TypeError: bad value")
    assert "\n" not in problem
    assert len(problem) < 600
    assert TrialFailure("unresponsive", "").as_problem() == (
        "The scene stopped responding (an endless loop?)"
    )


# -- the routes ------------------------------------------------------------------------------


def test_the_app_asks_for_trials_and_says_how_they_went(
    client: TestClient, services: Services
) -> None:
    assert client.get("/v1/scene-trials").json() == {"trials": []}
    trials = services.generation.trials
    trial_id = trials.offer(
        scene_class="Weights", source=INTERACTIVE_SCENE, interactive=True, controls=("weight",)
    )
    listed = client.get("/v1/scene-trials").json()["trials"]
    assert listed == [
        {
            "id": trial_id,
            "scene_class": "Weights",
            "source": INTERACTIVE_SCENE,
            "interactive": True,
            "controls": ["weight"],
        }
    ]
    report = {"passed": False, "stage": "controls", "message": "TypeError: bad value"}
    assert client.post(f"/v1/scene-trials/{trial_id}", json=report).status_code == 204
    assert trials.wait(trial_id, timeout=1) == TrialFailure("controls", "TypeError: bad value")
    # A report for a trial nobody is waiting for is let go.
    assert client.post(f"/v1/scene-trials/{trial_id}", json={"passed": True}).status_code == 204


@pytest.mark.parametrize(
    "report",
    [
        {"passed": "yes"},
        {"passed": False, "stage": "anywhere"},
        {"passed": False, "stage": "runtime", "message": "x" * 2001},
        {"passed": True, "extra": 1},
    ],
)
def test_a_report_that_is_not_one_is_refused(client: TestClient, report: dict[str, Any]) -> None:
    assert client.post("/v1/scene-trials/trial_00000000000000000000", json=report).status_code == (
        422
    )


# -- a lesson's pictures ---------------------------------------------------------------------


class App:
    """The app's side: asks for trials as the app does, and answers each as it is told to."""

    def __init__(self, services: Services, verdicts: list[TrialFailure | None]) -> None:
        self.tried: list[Any] = []
        self._trials = services.generation.trials
        self._verdicts = verdicts
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> App:
        self._trials.waiting()  # there before the first picture is drawn
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(5)

    def _run(self) -> None:
        while not self._stop.is_set():
            for trial in self._trials.waiting():
                self.tried.append(trial)
                verdict = self._verdicts.pop(0) if self._verdicts else None
                self._trials.report(trial.id, verdict)
            self._stop.wait(0.02)


def write_a_lesson(client: TestClient, services: Services) -> Any:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    course = client.post(
        "/v1/courses",
        json={"title": "Neural networks", "origin": "topic", "topic": "How a neuron computes."},
    ).json()
    curriculum = client.post(
        f"/v1/courses/{course['id']}/concepts",
        json={
            "title": "Weights and bias",
            "summary": "How a neuron combines its inputs.",
            "objectives": ["Compute a weighted sum by hand.", "Say what a weight means."],
        },
    ).json()
    concept = curriculum["concepts"][-1]["id"]
    job_id = client.post(f"/v1/concepts/{concept}/lessons").json()["id"]
    job = services.jobs.wait(job_id, timeout=60)
    assert job.status == "succeeded", job.error_message
    return job


def test_each_picture_is_tried_before_it_is_kept(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(LESSON)
    with App(services, []) as app:
        job = write_a_lesson(client, services)
    assert provider.kinds() == ["lesson", "scene", "scene"]
    assert [trial.source for trial in app.tried] == [ANIMATION_SCENE, INTERACTIVE_SCENE]
    assert [trial.interactive for trial in app.tried] == [False, True]
    assert job.result["pictures_made"] == 2
    assert job.result["notes"] == []


def test_a_picture_that_fails_its_trial_is_written_again_told_what_went_wrong(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(LESSON)
    failure = TrialFailure("runtime", "NameError: name 'Arow' is not defined")
    with App(services, [failure]) as app:
        job = write_a_lesson(client, services)
    # The first picture twice, the second once: one more request, and no more.
    assert provider.kinds() == ["lesson", "scene", "scene", "scene"]
    again = provider.prompt(2)
    assert "was run in the player and failed" in again
    assert "NameError: name 'Arow' is not defined" in again
    # The file that failed is shown with its lines as they were.
    assert "class WeightedSum(Scene):\n" in again or ANIMATION_SCENE.splitlines()[0] in again
    assert len(app.tried) == 3
    assert job.result["pictures_made"] == 2
    assert job.result["notes"] == []


def test_a_picture_that_fails_twice_is_said_in_words(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(LESSON)
    failure = TrialFailure("compile", "SyntaxError: invalid syntax")
    with App(services, [failure, failure]):
        job = write_a_lesson(client, services)
    assert provider.kinds() == ["lesson", "scene", "scene", "scene"]
    assert job.result["pictures_made"] == 1
    assert job.result["notes"] == [
        "The picture for “The weighted sum” couldn’t be made, so that part is explained in words."
    ]
    lesson = client.get(f"/v1/lessons/{job.result['lesson_id']}").json()
    assert [scene["id"] for scene in lesson["scenes"]] == ["scn_2"]


def test_without_the_app_to_try_them_pictures_are_kept_untried(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    provider.queue(LESSON)
    job = write_a_lesson(client, services)
    # Nobody asked for trials, so nobody was waited for.
    assert provider.kinds() == ["lesson", "scene", "scene"]
    assert job.result["pictures_made"] == 2
