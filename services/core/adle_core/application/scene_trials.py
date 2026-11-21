"""Pictures tried in the app's player before a learner is shown them (ADR-038).

A scene is code a model wrote. The static rules (``scene_policy``) say what it may not do;
only running it says whether it works. It can only run in the app's scene player: in a
sandboxed frame of the desktop app, never here. So a job that has drawn a picture offers
it for a trial and waits, and the app runs it there, as fast as it can be drawn, operates
its controls, and says how it went.

Nothing here decides what happens to a picture that fails: the job does (one more request,
told what went wrong, and words if that fails too). This only carries the question and the
answer, and knows whether anyone is there to answer.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from adle_core.infrastructure.ids import new_id

#: The ways a trial can fail, as the player names them, and ``controls``: a control of an
#: interactive picture, operated, broke it.
TrialStage = Literal["boot", "compile", "runtime", "timeout", "unresponsive", "controls"]

#: How long a job waits for a trial before keeping the picture untried, as before trials:
#: the player still says it in words if it fails in front of the learner.
TRIAL_WAIT_SECONDS = 60.0
#: Someone who asked for trials within this long is there to run them. The app asks every
#: second or so while a lesson is being written.
PRESENT_SECONDS = 10.0
#: What a failure may say, at most: it is told to the model, quoted, so it is kept short.
MAX_FAILURE_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class TrialFailure:
    """How a picture failed when it was run: where, and in the player's words."""

    stage: TrialStage
    message: str

    def as_problem(self) -> str:
        """The failure as a line for the model that will be asked to write the file again."""
        where = {
            "boot": "The player could not start",
            "compile": "The file did not compile",
            "runtime": "The scene failed while it ran",
            "timeout": "The scene took too long to prepare",
            "unresponsive": "The scene stopped responding (an endless loop?)",
            "controls": "The scene failed when a control was moved",
        }[self.stage]
        message = " ".join(self.message.split())[:MAX_FAILURE_CHARACTERS]
        return f"{where}: {message}" if message else where


@dataclass(frozen=True, slots=True)
class OpenTrial:
    """A picture waiting to be tried: what the app needs to run it, and nothing else."""

    id: str
    scene_class: str
    source: str
    interactive: bool
    controls: tuple[str, ...]


Verdict = TrialFailure | Literal["passed", "untried"]


@dataclass(slots=True)
class _Trial:
    open: OpenTrial
    answered: threading.Event = field(default_factory=threading.Event)
    verdict: TrialFailure | Literal["passed"] | None = None


class SceneTrials:
    """Trials offered by jobs and answered by the app. Thread-safe; nothing is stored."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._trials: dict[str, _Trial] = {}
        self._asked_at: float | None = None

    def present(self) -> bool:
        """Whether the app has asked for trials lately, and so is there to run one."""
        with self._lock:
            return self._asked_at is not None and (
                self._clock() - self._asked_at <= PRESENT_SECONDS
            )

    def waiting(self) -> list[OpenTrial]:
        """What the app should try now, oldest first. Asking is also how it says it is there."""
        with self._lock:
            self._asked_at = self._clock()
            return [trial.open for trial in self._trials.values() if trial.verdict is None]

    def offer(
        self, *, scene_class: str, source: str, interactive: bool, controls: tuple[str, ...]
    ) -> str:
        trial_id = new_id("trial")
        with self._lock:
            self._trials[trial_id] = _Trial(
                OpenTrial(trial_id, scene_class, source, interactive, controls)
            )
        return trial_id

    def report(self, trial_id: str, failure: TrialFailure | None) -> bool:
        """The app's answer. False when nobody is waiting for it (any more)."""
        with self._lock:
            trial = self._trials.get(trial_id)
            if trial is None or trial.verdict is not None:
                return False
            trial.verdict = failure if failure is not None else "passed"
        trial.answered.set()
        return True

    def wait(
        self,
        trial_id: str,
        *,
        timeout: float = TRIAL_WAIT_SECONDS,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Verdict:
        """The verdict on a trial, or ``untried`` if none came in time. Always withdraws it."""
        with self._lock:
            trial = self._trials.get(trial_id)
        if trial is None:
            return "untried"
        deadline = self._clock() + timeout
        try:
            while not trial.answered.wait(0.2):
                if cancelled() or self._clock() >= deadline:
                    return "untried"
            return trial.verdict or "untried"
        finally:
            with self._lock:
                self._trials.pop(trial_id, None)
