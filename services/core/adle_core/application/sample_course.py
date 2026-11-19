"""The sample course that ships with Adle.

Its content lives in ``adle_core/sample_course`` as data: one course outline,
one file per lesson, and one Python file per scene. Installing it goes through
the same services and the same validation as anything a learner or a model
creates, so the sample cannot contain a lesson Adle would otherwise refuse.

The course is created with origin ``sample`` and is labelled as written by
Adle everywhere it appears.
"""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from sqlalchemy import select

from adle_core.application.courses import CourseRecord, CourseService
from adle_core.application.curriculum import CurriculumService
from adle_core.application.lessons import LessonService
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Course
from adle_core.lessons.bundle import parse_bundle


def content_root() -> Traversable:
    return resources.files("adle_core.sample_course")


def load_outline() -> dict[str, Any]:
    outline: dict[str, Any] = json.loads(
        content_root().joinpath("course.json").read_text(encoding="utf-8")
    )
    return outline


def load_lesson_template(key: str) -> dict[str, Any]:
    template: dict[str, Any] = json.loads(
        content_root().joinpath("lessons", f"{key}.json").read_text(encoding="utf-8")
    )
    return template


def load_scene_source(file_name: str) -> str:
    return content_root().joinpath("scenes", file_name).read_text(encoding="utf-8")


def _resolve(value: Any, ids: dict[str, str]) -> Any:
    """Replace every ``"@name"`` placeholder in a template with the id it stands for."""
    if isinstance(value, str):
        if value.startswith("@"):
            if value not in ids:
                raise KeyError(f"The sample course refers to {value!r}, which is not defined.")
            return ids[value]
        return value
    if isinstance(value, list):
        return [_resolve(item, ids) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, ids) for key, item in value.items()}
    return value


def build_lesson_bundle(template: dict[str, Any], ids: dict[str, str]) -> dict[str, Any]:
    """Turn a lesson template into the input ``parse_bundle`` expects."""
    return {
        "lesson": _resolve(template["lesson"], ids),
        "scenes": [
            {
                "id": scene["id"],
                "purpose": scene["purpose"],
                "source": load_scene_source(scene["file"]),
            }
            for scene in template["scenes"]
        ],
    }


class SampleCourseService:
    def __init__(
        self,
        database: Database,
        courses: CourseService,
        curriculum: CurriculumService,
        lessons: LessonService,
    ) -> None:
        self._database = database
        self._courses = courses
        self._curriculum = curriculum
        self._lessons = lessons

    def install(self) -> CourseRecord:
        """Create the sample course, or return it if it is already there."""
        with self._database.session() as session:
            existing = session.scalar(
                select(Course.id).where(Course.origin == "sample").order_by(Course.created_at)
            )
        if existing is not None:
            return self._courses.get(existing)

        outline = load_outline()
        course = self._courses.create(
            title=outline["title"], description=outline["description"], origin="sample"
        )
        try:
            self._fill(course.id, outline)
        except BaseException:
            # Half a sample course is worse than none; the learner can simply try again.
            self._courses.delete(course.id)
            raise
        return self._courses.get(course.id)

    def _fill(self, course_id: str, outline: dict[str, Any]) -> None:
        ids: dict[str, str] = {"@course": course_id}

        for concept in outline["concepts"]:
            curriculum = self._curriculum.create_concept(
                course_id,
                title=concept["title"],
                summary=concept["summary"],
                objectives=[objective["statement"] for objective in concept["objectives"]],
                origin="sample",
            )
            created = curriculum.concepts[-1]
            ids[f"@concept:{concept['key']}"] = created.id
            for objective, stored in zip(concept["objectives"], created.objectives, strict=True):
                ids[f"@objective:{concept['key']}.{objective['key']}"] = stored.id
            self._curriculum.update_concept(
                created.id, complexity=concept["complexity"], tags=concept["tags"]
            )

        for concept in outline["concepts"]:
            if concept["needs"]:
                self._curriculum.set_prerequisites(
                    ids[f"@concept:{concept['key']}"],
                    [
                        (ids[f"@concept:{need['concept']}"], need["reason"])
                        for need in concept["needs"]
                    ],
                    origin="sample",
                )

        for key in outline["lessons"]:
            lesson_ids = {**ids, "@lesson": new_id("les")}
            bundle = parse_bundle(build_lesson_bundle(load_lesson_template(key), lesson_ids))
            self._lessons.store(bundle, origin="sample")
