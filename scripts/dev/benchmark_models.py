"""Time a provider's models on Adle's own work, by hand, and keep what came back.

A developer's tool, never part of a test run: no test may call a real provider (AGENTS.md).
It asks each model for the four kinds of thing Adle asks for (an answer to a question, a
list of concepts, a lesson's text, a scene's code), with the very prompts the app would
send, and records how long each took to begin, how long to finish, and whether what came
back is something Adle could use.

    cd services/core
    uv run python ../../scripts/dev/benchmark_models.py --key <file> --out <folder> list
    uv run python ../../scripts/dev/benchmark_models.py --key <file> --out <folder> \\
        run --models a,b,c --tasks ask,curriculum,scene,lesson [--max-requests 20]

The key is read from a file, held in memory, and never printed or written. ``--out`` must
be outside the repository. One request at a time, never more than four a minute.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx2 as httpx

from adle_core.api.auth import LaunchToken
from adle_core.application.services import build_services
from adle_core.config import Settings
from adle_core.generation import drafts
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.drafts import SceneBrief
from adle_core.generation.prompts import scene_request
from adle_core.generation.provider import (
    NVIDIA,
    NVIDIA_MODELS,
    ChatClient,
    ChatRequest,
    ModelSpec,
    RequestCancelledError,
)
from adle_core.generation.scene_policy import check_scene_source
from adle_core.ingestion.extract import extract_in_process

QUESTION = "Why is the bias added after the weighted sum, and not multiplied in like a weight?"
#: Never more than four requests a minute at one provider.
SECONDS_BETWEEN_REQUESTS = 16.0

SCENES = {
    "scene": SceneBrief(
        scene_id="bench-animation",
        segment_id="bench-1",
        kind="animation",
        title="A weighted sum, one term at a time",
        brief=(
            "Two inputs x1 = 2 and x2 = 3 on the left, each joined by an arrow to one neuron "
            "drawn as a circle. The arrows carry the weights w1 = 0.5 and w2 = -1. Below, "
            "build the sum one term at a time: 0.5 * 2, then + (-1) * 3, then + b with "
            "b = 1, and finally show the result -1. Highlight each arrow as its term is added."
        ),
        description=(
            "Each input is multiplied by the weight on its arrow, the products are added, "
            "and the bias is added last: 0.5 times 2, minus 3, plus 1 gives minus 1."
        ),
        narration=[
            "Each input travels along an arrow, and each arrow has a weight.",
            "Multiply each input by its weight and add the products.",
            "Then add the bias. That single number is what the neuron works with.",
        ],
    ),
    "interactive": SceneBrief(
        scene_id="bench-interactive",
        segment_id="bench-2",
        kind="interactive",
        title="What the weight does to the line",
        brief=(
            "Axes from -4 to 4. The line y = w * x + b. One slider for w from -2 to 2 and "
            "one for b from -3 to 3. As the sliders move, the line turns and shifts, and a "
            "label shows the current equation."
        ),
        description=(
            "Changing the weight turns the line about the point where it crosses the "
            "vertical axis; changing the bias slides the whole line up or down."
        ),
        narration=["Drag the weight and watch the line turn.", "Now drag the bias."],
    ),
}


def verdict(outcome: Any) -> str:
    return "usable" if outcome.usable else ("answered" if outcome.ok else "FAILED")


def say(*parts: object) -> None:
    print(*parts, flush=True)  # noqa: T201 - a tool run by hand says what it is doing


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--key", required=True, type=Path, help="a file holding the key")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("action", choices=["list", "run"])
    parser.add_argument("--models", default="")
    parser.add_argument("--tasks", default="ask,curriculum,scene,lesson")
    parser.add_argument("--max-requests", type=int, default=20)
    #: id=value pairs for models whose reference lists reasoning_effort.
    parser.add_argument("--effort", default="")
    return parser.parse_args()


def list_models(key: str) -> list[str]:
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=30.0) as client:
        answer = client.get(f"{NVIDIA.base_url}/models", headers={"Authorization": f"Bearer {key}"})
        answer.raise_for_status()
        return sorted(item["id"] for item in answer.json().get("data", []) if "id" in item)


def captured_requests(out: Path) -> tuple[dict[str, ChatRequest], dict[str, Any]]:
    """The requests the app itself would send, taken from its own services and not sent."""
    services = build_services(
        Settings(data_dir=out / "capture" / "data"),
        LaunchToken("benchmark-capture-0123456789abcdef0123456789"),
        extract=extract_in_process,
    )
    found: dict[str, ChatRequest] = {}
    context: dict[str, Any] = {}
    try:
        # Never sent anywhere: every client is replaced before anything is asked.
        services.credentials.set_api_key("capture-only-this-is-not-a-key", "nvidia")
        services.generation.select_provider("nvidia")

        def capture(request: ChatRequest, **_: Any) -> Any:
            found.setdefault(request.purpose, request)
            raise RequestCancelledError

        for client in services.provider_clients:
            client.complete = capture  # type: ignore[method-assign]

        course = services.sample_course.install()
        lesson = services.lessons.list_for_course(course.id)[0]
        first = services.lessons.get_lesson(lesson.id).segments[0]
        concept = next(
            item
            for item in services.curriculum.get(course.id).concepts
            if item.title == "Activation functions"
        )
        context["objectives"] = [
            drafts.ObjectiveRef(id=objective.id, statement=objective.statement)
            for objective in concept.objectives
        ]
        context["course_id"] = course.id
        context["concept_id"] = concept.id
        topic = services.courses.create(
            title="Probability for data analysis",
            origin="topic",
            topic=(
                "Conditional probability and Bayes' theorem, for someone who knows "
                "fractions and basic algebra and wants to reason about test results."
            ),
        )
        jobs = [
            services.generation.ask(lesson.id, first.id, QUESTION).id,
            services.generation.propose_curriculum(topic.id).id,
            services.generation.generate_lesson(concept.id).id,
        ]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if all(services.jobs.get(job).finished for job in jobs):
                break
            time.sleep(0.2)
    finally:
        services.close()
    for name, brief in SCENES.items():
        found[name] = scene_request(brief)
    return found, context


@dataclass
class Outcome:
    model: str
    task: str
    ok: bool = False
    usable: bool = False
    seconds_to_first: float | None = None
    seconds_to_writing: float | None = None
    seconds: float = 0.0
    completion_tokens: int = 0
    usage_reported: bool = False
    answer_chars: int = 0
    thinking_chars: int = 0
    finish_reason: str | None = None
    error: str = ""
    notes: list[str] = field(default_factory=list)


def judge(task: str, text: str, context: dict[str, Any], outcome: Outcome) -> None:
    """Whether Adle could use what came back, by Adle's own rules."""
    try:
        if task == "ask":
            answer = drafts.compile_answer(text)
            outcome.notes.append(f"{len(answer.paragraphs)} paragraphs")
        elif task == "curriculum":
            data = drafts.extract_json_object(text)
            draft = drafts.CurriculumDraft.model_validate(data)
            outcome.notes.append(f"{len(draft.concepts)} concepts")
        elif task == "lesson":
            data = drafts.extract_json_object(text)
            draft = drafts.parse_lesson_draft(data)
            compiled = drafts.compile_lesson(
                draft,
                drafts.LessonContext(
                    lesson_id="bench-lesson",
                    course_id=context["course_id"],
                    concept_id=context["concept_id"],
                    objectives=context["objectives"],
                ),
            )
            kinds = [segment.type for segment in draft.segments]
            outcome.notes.append(
                f"{len(draft.segments)} parts ({', '.join(kinds)}); "
                f"{len(compiled.scenes)} pictures; {len(draft.practice)} practice"
            )
        else:
            source = drafts.extract_python_file(text)
            report = check_scene_source(source)
            if not report.ok:
                outcome.notes.extend(
                    f"line {violation.line}: {violation.message}"
                    for violation in report.violations[:6]
                )
                return
            outcome.notes.append(f"{len(source.splitlines())} lines; passes the static rules")
        outcome.usable = True
    except Exception as error:  # what a model writes can be wrong in any way
        problems = getattr(error, "problems", None)
        outcome.notes.append(
            f"{type(error).__name__}: {'; '.join(problems[:4]) if problems else str(error)[:300]}"
        )


def main() -> int:
    args = arguments()
    out: Path = args.out.resolve()
    repository = Path(__file__).resolve()
    for parent in repository.parents:
        is_repository = (parent / "AGENTS.md").exists() and (parent / "services" / "core").exists()
        if is_repository and (out == parent or parent in out.parents):
            say("--out must be outside the repository.")
            return 2
    out.mkdir(parents=True, exist_ok=True)
    key = args.key.read_text(encoding="utf-8").strip()

    if args.action == "list":
        names = list_models(key)
        (out / "models.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
        say(f"{len(names)} models")
        for name in names:
            say(" ", name)
        return 0

    known = {spec.id: spec for spec in NVIDIA_MODELS}
    efforts = dict(pair.split("=", 1) for pair in args.effort.split(",") if "=" in pair)
    specs: list[ModelSpec] = []
    for model_id in [item.strip() for item in args.models.split(",") if item.strip()]:
        spec = known.get(model_id) or ModelSpec(id=model_id, name=model_id)
        if model_id in efforts:
            spec = ModelSpec(
                id=spec.id,
                name=spec.name,
                usage_option=spec.usage_option,
                json_mode=spec.json_mode,
                min_max_tokens=spec.min_max_tokens,
                reasoning_effort=efforts[model_id] or None,
            )
        specs.append(spec)
    if not specs:
        say("Give --models.")
        return 2
    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]

    requests, context = captured_requests(out)
    missing = [task for task in tasks if task not in requests]
    if missing:
        say("No request was captured for:", ", ".join(missing))
        return 2
    for task in tasks:
        request = requests[task]
        (out / f"prompt-{task}.txt").write_text(
            request.system + "\n\n===== USER =====\n\n" + request.user, encoding="utf-8"
        )

    vault = CredentialVault()
    vault.set_api_key(key, "nvidia")
    config = NVIDIA.__class__(
        provider_id="nvidia",
        display_name="NVIDIA NIM",
        base_url=NVIDIA.base_url,
        models=tuple(specs),
        limits=NVIDIA.limits,
        limits_published=False,
        quick=False,
        typical=NVIDIA.typical,
        read_timeout_seconds=180.0,
        total_timeout_seconds=900.0,
    )
    client = ChatClient(config, vault)
    results_file = out / "results.json"
    results: list[dict[str, Any]] = (
        json.loads(results_file.read_text(encoding="utf-8")) if results_file.exists() else []
    )
    done = {(item["model"], item["task"]) for item in results}
    sent = 0
    last = 0.0
    try:
        for task in tasks:
            for spec in specs:
                if (spec.id, task) in done:
                    continue
                if sent >= args.max_requests:
                    say("Stopped: the number of requests asked for is used up.")
                    return 0
                pause = SECONDS_BETWEEN_REQUESTS - (time.monotonic() - last)
                if last and pause > 0:
                    time.sleep(pause)
                outcome = Outcome(model=spec.id, task=task)
                started = time.monotonic()
                last = started
                sent += 1

                def reached(
                    stage: str, outcome: Outcome = outcome, started: float = started
                ) -> None:
                    elapsed = round(time.monotonic() - started, 1)
                    if outcome.seconds_to_first is None:
                        outcome.seconds_to_first = elapsed
                    if stage == "writing" and outcome.seconds_to_writing is None:
                        outcome.seconds_to_writing = elapsed

                say(f"[{sent}] {task:<11} {spec.id} ...")
                try:
                    result = client.complete(requests[task], model=spec, on_stage=reached)
                except Exception as error:  # recorded, and the next model is asked
                    outcome.seconds = round(time.monotonic() - started, 1)
                    outcome.error = (
                        f"{type(error).__name__} {getattr(error, 'code', '') or ''}".strip()
                    )
                else:
                    outcome.ok = True
                    outcome.seconds = round(time.monotonic() - started, 1)
                    outcome.completion_tokens = result.completion_tokens
                    outcome.usage_reported = result.usage_reported
                    outcome.answer_chars = len(result.text)
                    outcome.thinking_chars = result.thinking_characters
                    outcome.finish_reason = result.finish_reason
                    stem = f"{task}--{spec.id.replace('/', '_')}"
                    suffix = ".py" if task in SCENES else ".txt"
                    (out / f"{stem}{suffix}").write_text(result.text, encoding="utf-8")
                    judge(task, result.text, context, outcome)
                results.append(asdict(outcome))
                results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
                say(
                    f"     -> {verdict(outcome)}"
                    f" in {outcome.seconds}s (first sign {outcome.seconds_to_first}s, writing from"
                    f" {outcome.seconds_to_writing}s); {outcome.completion_tokens} tokens;"
                    f" {outcome.error or '; '.join(outcome.notes)[:300]}"
                )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
