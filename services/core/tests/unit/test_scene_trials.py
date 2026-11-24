"""A picture is tried in the app's player before a learner is shown it (ADR-038).

Against the scripted provider, with the app's side played by a thread that asks for trials
and answers them as told. No request in this file leaves the process.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application import generation as generation_module
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
            "steps": 0,
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
        #: How many pictures were waiting each time there were any.
        self.looks: list[int] = []
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
            waiting = self._trials.waiting()
            if waiting:
                self.looks.append(len(waiting))
            for trial in waiting:
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


FIGURES = {
    0: {
        "kind": "equation",
        "steps": ["z = w x + b", r"z = 2 \cdot 3 + 1", "z = 7"],
        "description": "The weighted sum is filled in and worked out to seven.",
    },
    1: {
        "kind": "bars",
        "labels": ["input 1", "input 2"],
        "values": [1, 3],
        "description": "Two bars: the second input counts three times as much.",
    },
    4: {
        "kind": "number_line",
        "from": 0,
        "to": 10,
        "marks": [{"at": 7, "label": "z"}],
        "description": "A number line from zero to ten with the sum marked at seven.",
    },
}


def with_figures(*, parts_first: bool = False) -> dict[str, Any]:
    """The stand-in lesson with three figures; ``parts_first`` writes its parts before its
    title, so that it cannot be begun before it is whole."""
    lesson = copy.deepcopy(LESSON)
    for index, figure in FIGURES.items():
        lesson["segments"][index].pop("scene", None)
        lesson["segments"][index]["figure"] = figure
    if parts_first:
        lesson = {"segments": lesson.pop("segments"), **lesson}
    return lesson


def test_each_figure_is_tried_as_soon_as_its_part_is_written(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    """A lesson begun at its first part (ADR-048) has each figure tried as its part comes:
    the learner may be about to begin that part."""
    provider.queue(with_figures())
    broken = TrialFailure("runtime", "non-finite point/vector value")
    with App(services, [None, None, broken]) as app:
        job = write_a_lesson(client, services)
    # One at a time, each as its part came; then the scene a model wrote for the interaction.
    assert app.looks == [1, 1, 1, 1]
    assert [trial.scene_class for trial in app.tried[:3]] == [
        "EquationFigure",
        "BarsFigure",
        "NumberLineFigure",
    ]
    assert job.result["pictures_made"] >= 2
    assert any("couldn’t be shown" in note for note in job.result["notes"])
    assert services.generation.trials.waiting() == []


def test_the_figures_of_a_lesson_taken_whole_are_offered_for_their_trials_all_at_once(
    client: TestClient, services: Services, provider: FakeProvider
) -> None:
    """The app runs them one after another in one look, instead of each figure waiting for
    the app's next look, a second later (ADR-045)."""
    provider.queue(with_figures(parts_first=True))
    broken = TrialFailure("runtime", "non-finite point/vector value")
    with App(services, [None, None, broken]) as app:
        job = write_a_lesson(client, services)
    # All three were waiting at the first look; the last one failed and is said in words.
    assert app.looks[0] == 3
    assert job.result["pictures_made"] >= 2
    assert any("couldn’t be shown" in note for note in job.result["notes"])
    assert services.generation.trials.waiting() == []


def test_the_figures_are_offered_together_however_long_the_gate_takes(
    client: TestClient,
    services: Services,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every figure is looked at by the gate before any is offered: a slow gate cannot split
    them across the app's looks (seen on a slower machine than this one, 2026-11-23, once
    each figure carried the methods that check its layout, ADR-055)."""
    gate = generation_module.inspect_scene

    def slow(*args: Any, **kwargs: Any) -> Any:
        time.sleep(0.1)
        return gate(*args, **kwargs)

    monkeypatch.setattr(generation_module, "inspect_scene", slow)
    provider.queue(with_figures(parts_first=True))
    with App(services, [None, None, None]) as app:
        write_a_lesson(client, services)
    assert app.looks[0] == 3


def test_a_figure_whose_trial_does_not_come_does_not_hold_up_the_rest_of_the_answer(
    client: TestClient,
    services: Services,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """While the answer is still being read, a figure's trial is waited for briefly: the
    parts after it are not read meanwhile (ADR-048). One that does not come keeps the figure
    untried, as before trials."""
    monkeypatch.setattr(generation_module, "FIGURE_WAIT_WHILE_WRITING", 0.3)
    provider.queue(with_figures())
    trials = services.generation.trials
    stop = threading.Event()

    def app() -> None:
        # There and asking, and answering the model's scene, but never a figure.
        while not stop.is_set():
            for trial in trials.waiting():
                if not trial.scene_class.endswith("Figure"):
                    trials.report(trial.id, None)
            stop.wait(0.02)

    trials.waiting()
    thread = threading.Thread(target=app, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        job = write_a_lesson(client, services)
    finally:
        stop.set()
        thread.join(5)
    # Three figures waited for a minute each would be three minutes.
    assert time.monotonic() - started < 30
    assert job.result["pictures_made"] >= 3
    assert trials.waiting() == []
