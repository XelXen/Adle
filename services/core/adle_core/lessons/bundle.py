"""Turning untrusted input into a lesson bundle that may be stored and played.

Whatever wrote a lesson (a model, a fixture file, an import), it reaches the
database only through :func:`parse_bundle`. That is the single place where the
shape is validated and every scene is put through the static policy; nothing a
bundle says about its own scenes is taken on trust.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from adle_core.errors import AdleError
from adle_core.generation.scene_policy import (
    PolicyViolation,
    check_scene_source,
    normalise_source,
)
from adle_core.lessons.ir import LessonBundle, SceneArtifact

#: How many separate problems are reported for one rejected lesson.
MAX_REPORTED_PROBLEMS = 12


@dataclass(frozen=True, slots=True)
class Problem:
    """One reason a lesson or scene was rejected.

    ``where`` locates it (``lesson.segments.2.question.options``); ``message``
    says what is wrong without quoting the content, which may be long, private,
    or hostile.
    """

    where: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"where": self.where, "message": self.message}


class LessonInvalidError(AdleError):
    """The lesson does not fit the Lesson IR, or one of its scenes is not allowed."""

    status_code = 422
    code = "lesson_invalid"

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems[:MAX_REPORTED_PROBLEMS]
        super().__init__(
            "This lesson could not be used because it is not in the form Adle expects. "
            "Nothing was saved.",
            detail={"problems": [problem.as_dict() for problem in self.problems]},
        )


class SceneRejectedError(AdleError):
    """A scene file broke the static policy."""

    status_code = 422
    code = "scene_rejected"

    def __init__(self, scene_id: str, violations: tuple[PolicyViolation, ...]) -> None:
        self.scene_id = scene_id
        self.violations = violations
        super().__init__(
            "A visual in this lesson is not something Adle will run. Nothing was saved.",
            detail={
                "scene_id": scene_id,
                "violations": [
                    {"code": item.code, "message": item.message, "line": item.line}
                    for item in violations[:MAX_REPORTED_PROBLEMS]
                ],
            },
        )


def inspect_scene(scene_id: str, purpose: str, source: str) -> SceneArtifact:
    """Check a scene file and describe it. Raises ``SceneRejectedError`` if it is not allowed."""
    report = check_scene_source(source)
    if not report.ok:
        raise SceneRejectedError(scene_id, report.violations)
    if len(report.scene_classes) != 1:
        raise SceneRejectedError(
            scene_id,
            (
                PolicyViolation(
                    "one_scene_per_file",
                    "A scene file must define exactly one scene class.",
                ),
            ),
        )
    return SceneArtifact(
        id=scene_id,
        purpose=purpose,
        source=normalise_source(source),
        content_hash=report.content_hash,
        wanim_version=report.wanim_version,
        scene_class=report.scene_classes[0],
        interactive=report.interactive,
        controls=list(report.controls),
        events=list(report.events),
    )


def _problems(error: ValidationError) -> list[Problem]:
    problems = []
    for item in error.errors(include_input=False, include_url=False):
        where = ".".join(str(part) for part in item["loc"]) or "lesson"
        message = str(item["msg"])
        # Pydantic prefixes messages raised by our own validators.
        problems.append(Problem(where=where, message=message.removeprefix("Value error, ")))
    return problems


def parse_bundle(data: object) -> LessonBundle:
    """Validate ``data`` as a lesson bundle and re-derive every scene's description.

    ``data`` is either a mapping with ``lesson`` and ``scenes``, where each
    scene needs only ``id``, ``purpose``, and ``source``, or the full stored
    form. ``pending_scene_ids`` lists scenes that parts refer to and that are
    still being drawn (ADR-031). Raises ``LessonInvalidError`` or
    ``SceneRejectedError``.
    """
    if not isinstance(data, dict):
        raise LessonInvalidError([Problem("lesson", "The lesson is not a JSON object.")])
    raw_scenes = data.get("scenes", [])
    if not isinstance(raw_scenes, list):
        raise LessonInvalidError([Problem("scenes", "The scenes are not a list.")])

    scenes: list[dict[str, object]] = []
    for index, raw in enumerate(raw_scenes):
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("id"), str)
            or not isinstance(raw.get("purpose"), str)
            or not isinstance(raw.get("source"), str)
        ):
            raise LessonInvalidError(
                [Problem(f"scenes.{index}", "A scene needs an id, a purpose, and its source.")]
            )
        try:
            # The description is computed here; whatever the input claimed is discarded.
            scenes.append(inspect_scene(raw["id"], raw["purpose"], raw["source"]).model_dump())
        except ValidationError as error:
            raise LessonInvalidError(
                [
                    Problem(f"scenes.{index}.{problem.where}", problem.message)
                    for problem in _problems(error)
                ]
            ) from error

    try:
        return LessonBundle.model_validate(
            {
                "lesson": data.get("lesson"),
                "scenes": scenes,
                "pending_scene_ids": data.get("pending_scene_ids", []),
            }
        )
    except ValidationError as error:
        raise LessonInvalidError(_problems(error)) from error
