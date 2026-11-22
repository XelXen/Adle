"""Ask the real providers for real work, by hand, and keep what came back for reading.

This is a developer's tool, never part of a test run: no test may call a real provider
(AGENTS.md). It exists because the only way to know that a prompt, a model, or a provider
behaves as Adle expects is to try it, and trying it by pasting requests into a terminal
leaves nothing to compare the next time.

    uv run --directory services/core python ../../scripts/dev/real_provider_check.py \\
        --out <a folder outside the repository> \\
        [--aihubmix <file holding that key>] [--nvidia <file holding that key>] \\
        [--selection auto|aihubmix|nvidia] [steps ...]

Steps, in the order given (default: check ask curriculum lesson):

    check                 one word from each provider that has a key
    ask                   a question about the first part of a sample lesson
    curriculum            a list of concepts for a small course
    lesson[:<concept>]    a lesson, with its pictures, for a concept of the sample course
    document:<file>       a whole way through a document, each step timed: import, a plan
                          for a course, a lesson on its first concept, a question

A key is read from a file, held in memory, and never printed or written anywhere. Every
prompt and every answer is saved under ``--out`` (which is refused if it is inside the
repository: what a model wrote for you does not belong in git), with ``calls.json`` saying
which provider and model each request went to and how long it took. The data folder it
leaves behind can be opened in the app: start Adle with ``ADLE_USER_DATA_DIR=<out>/profile``.

It spends real allowance: a lesson is three requests, and a slow model takes minutes.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from adle_core.api.auth import LaunchToken
from adle_core.application.services import Services, build_services
from adle_core.config import Settings
from adle_core.generation.provider import ChatClient, ChatRequest
from adle_core.ingestion.extract import extract_in_process

REPOSITORY = Path(__file__).resolve().parents[2]
QUESTION = "Why is the bias added after the weighted sum, and not multiplied in like a weight?"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--aihubmix", type=Path, help="a file holding the AIHubMix key")
    parser.add_argument("--nvidia", type=Path, help="a file holding the NVIDIA key")
    parser.add_argument("--selection", default="auto", choices=["auto", "aihubmix", "nvidia"])
    parser.add_argument("steps", nargs="*", default=["check", "ask", "curriculum", "lesson"])
    return parser.parse_args()


def say(*parts: object) -> None:
    print(*parts, flush=True)


def record_requests(client: ChatClient, out: Path, calls: list[dict[str, Any]]) -> None:
    """Keep every prompt and answer of one provider's client, and how long each took."""
    original = client.complete

    def recorded(request: ChatRequest, **options: Any) -> Any:
        number = len(calls) + 1
        spec = options.get("model") or client.config.models[0]
        stem = out / f"{number:02d}-{client.config.provider_id}-{request.purpose}"
        Path(f"{stem}.prompt.txt").write_text(
            request.system + "\n\n===== USER =====\n\n" + request.user, encoding="utf-8"
        )
        started = time.monotonic()
        entry: dict[str, Any] = {
            "n": number,
            "provider": client.config.provider_id,
            "model": spec.id,
            "purpose": request.purpose,
            "prompt_chars": len(request.system) + len(request.user),
        }
        calls.append(entry)
        try:
            result = original(request, **options)
        except Exception as error:
            entry.update(
                seconds=round(time.monotonic() - started, 1),
                error=type(error).__name__,
                code=getattr(error, "code", None),
            )
            say("  request", json.dumps(entry))
            raise
        Path(f"{stem}.answer.txt").write_text(result.text, encoding="utf-8")
        entry.update(
            seconds=round(time.monotonic() - started, 1),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            usage_reported=result.usage_reported,
            answer_chars=len(result.text),
            thinking_chars=result.thinking_characters,
        )
        say("  request", json.dumps(entry))
        return result

    client.complete = recorded  # type: ignore[method-assign]


def wait(services: Services, job_id: str, limit: float = 3000.0) -> Any:
    """Follow a job, saying what it says, until it has finished."""
    last = ""
    usable = False
    started = time.monotonic()
    while time.monotonic() - started < limit:
        snapshot = services.jobs.get(job_id)
        if not usable and not snapshot.finished and snapshot.result is not None:
            # A lesson can be taken from here on, while its pictures are drawn (ADR-031).
            usable = True
            say(f"  [usable] {round(time.monotonic() - started)}s there is something to start")
        if snapshot.progress_message != last:
            last = snapshot.progress_message
            say(f"  [{snapshot.status}] {round(time.monotonic() - started)}s {last}")
        if snapshot.finished:
            say(
                f"  -> {snapshot.status} after {round(time.monotonic() - started)}s",
                snapshot.error_code or "",
                snapshot.error_message or "",
            )
            return snapshot
        time.sleep(1.0)
    raise TimeoutError(job_id)


def plans(services: Services) -> None:
    for work in ("ask", "curriculum", "lesson"):
        found = services.gateway.plan(work)
        wait_for = services.generation.expected_wait(work)
        say(
            f"  {work:<10} -> {found.sentence}"
            f"   (about {wait_for.seconds}s, {'measured' if wait_for.measured else 'usual'})"
            + (f"   because: {found.reason}" if found.reason else "")
        )


def sample_lesson(services: Services) -> tuple[str, str, str]:
    """The sample course's first lesson: its course, its id, and its first part."""
    course = services.sample_course.install()
    lesson = services.lessons.list_for_course(course.id)[0]
    first = services.lessons.get_lesson(lesson.id).segments[0]
    return course.id, lesson.id, first.id


def workflow(services: Services, document: Path, out: Path) -> None:
    """A learner's whole way through a document, each step timed: importing it, a plan for
    a course from it, a lesson on its first concept, and a question asked in that lesson."""
    say("DOCUMENT", document.name)
    timings: dict[str, float] = {}
    course = services.courses.create(title=document.stem, origin="materials")

    started = time.monotonic()
    snapshot = wait(services, services.sources.start_import(course.id, [document]).id)
    timings["import"] = round(time.monotonic() - started, 1)
    headings = services.curriculum.outline_candidates(course.id)
    say(f"  {len(headings)} headings:", "; ".join(item.title for item in headings))

    started = time.monotonic()
    snapshot = wait(services, services.generation.propose_curriculum(course.id).id)
    timings["course plan"] = round(time.monotonic() - started, 1)
    if snapshot.status != "succeeded":
        say("  no plan:", snapshot.error_code)
        return
    (out / "document-plan.json").write_text(
        json.dumps(snapshot.result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    concepts = snapshot.result["concepts"]
    for index, concept in enumerate(concepts, start=1):
        say(f"  {index}. {concept['title']}  (from headings {concept.get('section_ids')})")
    covered = {section for concept in concepts for section in concept.get("section_ids") or []}
    missed = [item.title for item in headings if item.section_id not in covered]
    say(f"  headings no concept comes from: {missed or 'none'}")
    services.generation.accept_proposal(snapshot.id, list(range(len(concepts))))

    first = services.curriculum.get(course.id).concepts[0]
    started = time.monotonic()
    job = services.generation.generate_lesson(first.id)
    usable_at: float | None = None
    written_at: float | None = None
    while True:
        current = services.jobs.get(job.id)
        if (
            usable_at is None
            and isinstance(current.result, dict)
            and current.result.get("lesson_id")
        ):
            # Begun at its first part (ADR-048).
            usable_at = round(time.monotonic() - started, 1)
        if written_at is None and (current.progress_detail or {}).get("stage") == "drawing":
            # Every part written: what is left is its pictures.
            written_at = round(time.monotonic() - started, 1)
        if current.finished:
            break
        time.sleep(0.5)
    timings["lesson: its first part, when it can be started"] = usable_at or -1
    timings["lesson: every part written"] = written_at or round(time.monotonic() - started, 1)
    timings["lesson: with every picture"] = round(time.monotonic() - started, 1)
    if current.status != "succeeded":
        say("  no lesson:", current.error_code, current.error_message)
        return
    loaded = services.lessons.get(current.result["lesson_id"])
    (out / "document-lesson.json").write_text(
        loaded.lesson.model_dump_json(indent=2), encoding="utf-8"
    )
    for scene in loaded.scenes:
        (out / f"document-scene-{scene.id}.py").write_text(scene.source, encoding="utf-8")
    pictured = [segment for segment in loaded.lesson.segments if getattr(segment, "scene", None)]
    say(
        f"  lesson “{loaded.lesson.title}”: {len(loaded.lesson.segments)} parts, "
        f"{len(pictured)} with a picture: {[scene.scene_class for scene in loaded.scenes]}"
    )
    say("  notes:", json.dumps(current.result.get("notes")))

    segment = next(item for item in loaded.lesson.segments if item.type != "checkpoint")
    started = time.monotonic()
    asked = wait(
        services,
        services.generation.ask(loaded.lesson.lesson_id, segment.id, QUESTION_ON_DOCUMENT).id,
    )
    timings["a question during the lesson"] = round(time.monotonic() - started, 1)
    if asked.status == "succeeded":
        for paragraph in services.asks.get(asked.result["ask_id"]).paragraphs:
            say("   ", paragraph[:200])
    say("  TIMINGS")
    for name, seconds in timings.items():
        say(f"    {name}: {seconds} s")
    (out / "document-timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")


QUESTION_ON_DOCUMENT = "Why is the probability of any single value zero, if the value can happen?"


def main() -> int:
    args = arguments()
    out: Path = args.out.resolve()
    if out == REPOSITORY or REPOSITORY in out.parents:
        say("--out must be outside the repository: what a model writes for you is not for git.")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s", stream=sys.stderr)
    for noisy in ("httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    services = build_services(
        Settings(data_dir=out / "profile" / "data"),
        LaunchToken("real-provider-check-0123456789abcdef0123456789"),
        extract=extract_in_process,
    )
    calls: list[dict[str, Any]] = []
    try:
        for provider_id, key_file in (("aihubmix", args.aihubmix), ("nvidia", args.nvidia)):
            if key_file is not None:
                key = key_file.read_text(encoding="utf-8").strip()
                services.credentials.set_api_key(key, provider_id)
        services.generation.select_provider(args.selection)
        for client in services.provider_clients:
            record_requests(client, out, calls)

        keyed = [
            config.display_name
            for config in services.gateway.providers
            if services.gateway.has_key_for(config.provider_id)
        ]
        say("SELECTION", services.gateway.selection, "| keys for:", ", ".join(keyed) or "none")
        plans(services)

        for step in args.steps:
            if step == "check":
                say("CHECK")
                for config in services.gateway.providers:
                    if services.gateway.has_key_for(config.provider_id):
                        snapshot = wait(
                            services, services.generation.check_provider(config.provider_id).id
                        )
                        say("  result:", json.dumps(snapshot.result))

            elif step == "ask":
                say("ASK")
                _, lesson_id, segment_id = sample_lesson(services)
                snapshot = wait(
                    services, services.generation.ask(lesson_id, segment_id, QUESTION).id
                )
                if snapshot.status == "succeeded":
                    kept = services.asks.get(snapshot.result["ask_id"])
                    (out / "answer.json").write_text(
                        json.dumps(
                            {
                                "question": kept.question,
                                "paragraphs": kept.paragraphs,
                                "written_by": kept.written_by,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    for paragraph in kept.paragraphs:
                        say("   ", paragraph)
                    say("  written by:", json.dumps(kept.written_by))

            elif step == "curriculum":
                say("CURRICULUM")
                topic = services.courses.create(
                    title="Probability for data analysis",
                    origin="topic",
                    topic=(
                        "Conditional probability and Bayes' theorem, for someone who knows "
                        "fractions and basic algebra and wants to reason about test results."
                    ),
                )
                snapshot = wait(services, services.generation.propose_curriculum(topic.id).id)
                if snapshot.status == "succeeded":
                    (out / "curriculum-job.json").write_text(
                        json.dumps(snapshot.result, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                    concepts = snapshot.result["concepts"]
                    for index, concept in enumerate(concepts, start=1):
                        say(f"  {index}. {concept['title']}")
                    say("  written by:", json.dumps(snapshot.result.get("written_by")))
                    services.generation.accept_proposal(snapshot.id, list(range(len(concepts))))

            elif step.startswith("lesson"):
                title = step.partition(":")[2] or "Activation functions"
                say("LESSON", title)
                course_id, _, _ = sample_lesson(services)
                concept = next(
                    item
                    for item in services.curriculum.get(course_id).concepts
                    if item.title == title
                )
                snapshot = wait(services, services.generation.generate_lesson(concept.id).id)
                if snapshot.status == "succeeded":
                    (out / "lesson-job.json").write_text(
                        json.dumps(snapshot.result, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                    loaded = services.lessons.get(snapshot.result["lesson_id"])
                    (out / "lesson.json").write_text(
                        loaded.lesson.model_dump_json(indent=2), encoding="utf-8"
                    )
                    for scene in loaded.scenes:
                        (out / f"scene-{scene.id}.py").write_text(scene.source, encoding="utf-8")
                    say(
                        "  lesson:",
                        loaded.lesson.title,
                        "|",
                        [segment.type for segment in loaded.lesson.segments],
                        "| scenes:",
                        [(scene.id, scene.interactive) for scene in loaded.scenes],
                    )
                    say("  written by:", json.dumps(snapshot.result.get("written_by")))
                    say("  notes:", json.dumps(snapshot.result.get("notes")))
            elif step.startswith("document:"):
                workflow(services, Path(step.partition(":")[2]), out)
            else:
                say("Unknown step:", step)
                return 2
            plans(services)
    finally:
        for config in services.gateway.providers:
            usage = services.gateway.usage(config.provider_id)
            say(
                f"USAGE {config.provider_id}: requests_today={usage.requests_today} "
                f"tokens_today={usage.tokens_today}"
            )
        (out / "calls.json").write_text(json.dumps(calls, indent=2), encoding="utf-8")
        services.close()
    say("Open what was written in the app with ADLE_USER_DATA_DIR=" + str(out / "profile"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
