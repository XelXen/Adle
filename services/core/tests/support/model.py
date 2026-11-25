"""A stand-in for the model provider that never leaves the process.

``FakeProvider`` is an httpx transport handler. By default it answers each kind
of request (curriculum, lesson, scene, ask, check, read, film) with a good canned answer; a test can
queue specific answers, failures, or malformed output ahead of the defaults.
Everything that was asked is recorded so tests can assert on what was sent.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2 as httpx

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = REPO_ROOT / "skills" / "wanim-scene-authoring" / "examples"

ANIMATION_SCENE = (EXAMPLES / "weighted_sum.py").read_text(encoding="utf-8")
INTERACTIVE_SCENE = (EXAMPLES / "neuron_weight.py").read_text(encoding="utf-8")

#: Breaks the static policy: an import Adle does not allow.
FORBIDDEN_SCENE = "import os\nfrom manim import *\n\n\nclass Bad(Scene):\n    def construct(self):\n        self.wait(1)\n"

#: Good answers, shared with the end-to-end suite's fake provider.
ANSWERS = REPO_ROOT / "fixtures" / "model-answers"
CURRICULUM: dict[str, Any] = json.loads((ANSWERS / "curriculum.json").read_text("utf-8"))
LESSON: dict[str, Any] = json.loads((ANSWERS / "lesson.json").read_text("utf-8"))
#: An answer to something the learner asked in the middle of a lesson.
ANSWER: dict[str, Any] = json.loads((ANSWERS / "answer.json").read_text("utf-8"))
#: A chapter of a film (ADR-065): passes the rules, and runs clean in the real engine.
FILM_CHAPTER = (ANSWERS / "film-chapter.py").read_text("utf-8")
#: A part's picture drawn again as the learner asked (ADR-067): the hydrogen bond between
#: two water molecules, as a slide.
REDRAW: dict[str, Any] = json.loads((ANSWERS / "redraw.json").read_text("utf-8"))


def sse(text: str, *, usage: dict[str, int] | None = None) -> httpx.Response:
    """A streamed completion carrying ``text`` in a few chunks."""
    step = max(1, len(text) // 3)
    events: list[dict[str, Any]] = [
        {"choices": [{"delta": {"content": text[index : index + step]}}]}
        for index in range(0, len(text), step)
    ]
    events.append({"choices": [{"delta": {}, "finish_reason": "stop"}]})
    events.append(
        {"choices": [], "usage": usage or {"prompt_tokens": 900, "completion_tokens": 400}}
    )
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


Answer = str | dict[str, Any] | httpx.Response | Exception | Callable[[dict[str, Any]], Any]

#: What the fake reads off a picture of a page, unless told otherwise.
READ_PAGE = "Levers - my notes\nMA = load / effort\n[A drawing of a lever on a fulcrum]"


def text_of(content: Any) -> str:
    """The words of a message: itself, or its text parts when it also carries pictures."""
    if isinstance(content, str):
        return content
    return "\n".join(part["text"] for part in content if part.get("type") == "text")


def pictures_of(body: dict[str, Any]) -> list[str]:
    """The pictures a request carried, as their data URLs."""
    found: list[str] = []
    for message in body["messages"]:
        if isinstance(message["content"], list):
            found += [
                part["image_url"]["url"]
                for part in message["content"]
                if part.get("type") == "image_url"
            ]
    return found


class FakeProvider:
    def __init__(self) -> None:
        #: The body of every request that arrived, in order.
        self.requests: list[dict[str, Any]] = []
        #: The ``Authorization`` header of every request.
        self.authorizations: list[str | None] = []
        #: The address every request was sent to.
        self.urls: list[str] = []
        self._queued: list[Answer] = []
        #: Answers kept for the requests of one kind, or for those whose words say something,
        #: each in the order they arrive: requests sent side by side (ADR-068) arrive in no
        #: order of their own.
        self._kept: list[tuple[Callable[[dict[str, Any]], bool], list[Answer]]] = []
        self._lock = threading.Lock()

    def queue(self, *answers: Answer) -> None:
        """Answer the next requests with these, before falling back to the defaults."""
        with self._lock:
            self._queued.extend(answers)

    def queue_for(self, kind: str, *answers: Answer) -> None:
        """Answer the next requests of this kind with these, whatever else arrives first."""
        with self._lock:
            self._kept.append((lambda body: self.kind(body) == kind, list(answers)))

    def when(self, words: str, *answers: Answer) -> None:
        """Answer the next requests whose system or user text says ``words`` with these."""

        def says(body: dict[str, Any]) -> bool:
            return any(words in text_of(message["content"]) for message in body["messages"])

        with self._lock:
            self._kept.append((says, list(answers)))

    def _answer_for(self, body: dict[str, Any]) -> Answer:
        with self._lock:
            self.requests.append(body)
            for matches, answers in self._kept:
                if answers and matches(body):
                    return answers.pop(0)
            if self._queued:
                return self._queued.pop(0)
        return self.default(body)

    @staticmethod
    def kind(body: dict[str, Any]) -> str:
        system = body["messages"][0]["content"]
        if "design the curriculum" in system:
            return "curriculum"
        if "Wanim scene file" in system:
            return "scene"
        # Before "partway through a lesson", which a redraw's instructions say too (ADR-067).
        if "You draw pictures for Adle" in system:
            return "redraw"
        if "partway through a lesson" in system:
            return "ask"
        if "checking that a connection works" in system:
            return "check"
        if "from a picture of it" in system:
            return "read"
        if "one chapter of a narrated teaching film" in system:
            return "film"
        if "looking over pictures of one chapter" in system:
            return "storyboard"
        return "lesson"

    def kinds(self) -> list[str]:
        return [self.kind(body) for body in self.requests]

    def prompt(self, index: int = -1) -> str:
        """Everything the model was shown in one request: system and user text."""
        messages = self.requests[index]["messages"]
        return "\n".join(text_of(message["content"]) for message in messages)

    def default(self, body: dict[str, Any]) -> Answer:
        kind = self.kind(body)
        if kind == "curriculum":
            return CURRICULUM
        if kind == "lesson":
            return LESSON
        if kind == "ask":
            return ANSWER
        if kind == "check":
            return "ready"
        if kind == "read":
            return READ_PAGE
        if kind == "film":
            return FILM_CHAPTER
        if kind == "storyboard":
            return "NOTHING"
        if kind == "redraw":
            return REDRAW
        user = text_of(body["messages"][1]["content"])
        return INTERACTIVE_SCENE if "Kind: interactive" in user else ANIMATION_SCENE

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.authorizations.append(request.headers.get("authorization"))
        self.urls.append(str(request.url))
        answer: Answer = self._answer_for(body)
        if callable(answer) and not isinstance(answer, httpx.Response | Exception):
            answer = answer(body)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx.Response):
            return answer
        return sse(answer if isinstance(answer, str) else json.dumps(answer))
