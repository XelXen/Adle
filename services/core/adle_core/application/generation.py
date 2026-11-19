"""Asking the model for a curriculum or a lesson, as background jobs.

Each job is a short, fixed sequence of requests. Nothing here loops on the
model's output:

* a **curriculum proposal** is one request (two if the first answer was not
  usable). Its result is only a proposal: nothing is added to the course until
  the learner picks from it (``accept_proposal``).
* a **lesson** is one request for the lesson (two at most), then one request
  per scene (two at most each), and a lesson asks for at most two scenes.

A scene that cannot be made does not cost the learner the lesson: that part is
kept as words. Everything the model writes goes through the same validation as
any other lesson before it is stored.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select

from adle_core.application.courses import get_course_or_404
from adle_core.application.curriculum import (
    ConceptRecord,
    CurriculumRecord,
    CurriculumService,
    ProposedConceptInput,
    get_concept_or_404,
)
from adle_core.application.jobs import JobCancelledError, JobContext, JobRunner, JobSnapshot
from adle_core.application.learner import LearnerService
from adle_core.application.lessons import LessonService
from adle_core.application.model_gateway import ModelGateway, QuotaExhaustedError
from adle_core.application.retrieval import Passage as StoredPassage
from adle_core.application.retrieval import Retriever
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.generation import prompts
from adle_core.generation.drafts import (
    DraftError,
    LessonContext,
    ObjectiveRef,
    PassageRef,
    SceneBrief,
    as_visualization,
    compile_curriculum,
    compile_lesson,
    extract_json_object,
    extract_python_file,
    parse_lesson_draft,
    without_scene,
)
from adle_core.generation.provider import (
    ChatRequest,
    ChatResult,
    ProviderError,
    ProviderKeyMissingError,
    RequestCancelledError,
)
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Concept, Course
from adle_core.ingestion.types import heading_leaf
from adle_core.learner_model.preferences import LearnerPreferences
from adle_core.lessons.bundle import SceneRejectedError, inspect_scene, parse_bundle
from adle_core.lessons.ir import Lesson, SceneArtifact

logger = logging.getLogger(__name__)

KIND_CURRICULUM = "curriculum_proposal"
KIND_LESSON = "lesson_generation"

_PACE = {"relaxed": "unhurried", "standard": "moderate", "brisk": "brisk"}
_DENSITY = {
    "concise": "brief: the essential steps only",
    "balanced": "moderate",
    "detailed": "thorough: every step spelled out",
}
_SELF_REPORT = {
    "new": "They say this is new to them.",
    "some": "They say they know some of it.",
    "confident": "They say they already know it well; this has not been checked yet.",
}


class GenerationFailedError(AdleError):
    """The model answered, twice, with something that could not be used."""

    status_code = 502
    code = "generation_failed"


@dataclass(frozen=True, slots=True)
class _LessonInputs:
    course_title: str
    concept: prompts.ConceptBrief
    learner: prompts.LearnerBrief
    passages: list[prompts.Passage]
    context: LessonContext


def _locator(passage: StoredPassage) -> str:
    if passage.page_number is not None:
        return f"page {passage.page_number}"
    title = heading_leaf(passage.section_title or "")
    return title or "the document"


def _citable(text: str) -> str:
    """A file name or heading as it may appear in a citation: no notation, bounded."""
    cleaned = " ".join(text.replace("$", "").replace("\\", " ").replace("<", "").split())
    return cleaned[:200] or "your materials"


#: Names the Lesson IR uses for things the draft calls something else.
_DRAFT_NAMES = {
    "narration": "beats",
    "fallback_text": "description",
    "expected": "answer",
    "is_transfer": "transfer",
}


def _draft_path(location: Sequence[object]) -> str:
    """Where a problem is, in the words of the draft the model wrote.

    Validation reports places in the Lesson IR (``segments.0.explanation.narration.1.text``).
    The model never saw the IR: it wrote ``segments[0].beats[1].say``.
    """
    parts = [str(part) for part in location]
    named: list[str] = []
    for index, part in enumerate(parts):
        before = parts[index - 1] if index else ""
        # The kind of a segment or question appears as a step of its own; the draft has none.
        if before == "question" or (index == 2 and parts[0] == "segments" and before.isdigit()):
            continue
        if part == "text" and index >= 2 and parts[index - 2] == "narration":
            named.append("say")
        else:
            named.append(_DRAFT_NAMES.get(part, part))
    return ".".join(named)


def _problem_list(error: ValidationError) -> list[str]:
    """What was wrong, by place, without quoting anything the model wrote."""
    found = []
    for item in error.errors(include_input=False, include_url=False):
        where = _draft_path(item["loc"])
        message = str(item["msg"]).removeprefix("Value error, ")
        found.append(f"{where}: {message}" if where else message)
    return found[:12]


class GenerationService:
    def __init__(
        self,
        database: Database,
        jobs: JobRunner,
        gateway: ModelGateway,
        curriculum: CurriculumService,
        lessons: LessonService,
        learner: LearnerService,
        retriever: Retriever,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._gateway = gateway
        self._curriculum = curriculum
        self._lessons = lessons
        self._learner = learner
        self._retriever = retriever

    # -- the one way a request is made ---------------------------------------

    def _ask(self, request: ChatRequest, context: JobContext, done: int, total: int) -> ChatResult:
        """Send one request from inside a job, keeping the job's progress honest while it waits."""

        def waiting(seconds: float) -> None:
            context.report(
                done,
                total,
                f"Waiting about {max(1, round(seconds))} seconds to stay within the "
                "provider's rate limit",
            )

        try:
            return self._gateway.complete(
                request, cancelled=lambda: context.cancelled, on_wait=waiting
            )
        except RequestCancelledError as error:
            raise JobCancelledError from error

    def _require_key(self) -> None:
        if not self._gateway.has_key:
            raise ProviderKeyMissingError

    # -- curriculum ------------------------------------------------------------

    def propose_curriculum(self, course_id: str) -> JobSnapshot:
        """Start a job that asks the model for concepts this course could teach."""
        with self._database.session() as session:
            get_course_or_404(session, course_id)
        self._require_key()
        running = self._jobs.find_active(KIND_CURRICULUM, course_id)
        if running is not None:
            return running
        return self._jobs.submit(
            KIND_CURRICULUM,
            lambda context: self._propose(course_id, context),
            course_id=course_id,
            subject_id=course_id,
        )

    def _propose(self, course_id: str, context: JobContext) -> dict[str, Any]:
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            title, topic, description = course.title, course.topic or "", course.description
            existing = list(
                session.scalars(
                    select(Concept.title)
                    .where(Concept.course_id == course_id)
                    .order_by(Concept.position)
                )
            )
        candidates = self._curriculum.outline_candidates(course_id)[: prompts.MAX_HEADINGS]
        headings = [f"{candidate.title} (in {candidate.source_name})" for candidate in candidates]
        section_ids = [candidate.section_id for candidate in candidates]
        query = " ".join([title, topic, description])
        excerpts = [
            prompts.Passage(
                source_name=passage.source_name, locator=_locator(passage), text=passage.text
            )
            for passage in self._retriever.retrieve(course_id, query, limit=4)
        ]
        goal = self._learner.get_preferences().goal

        problems: list[str] = []
        for attempt in (1, 2):
            context.check_cancelled()
            context.report(
                attempt - 1,
                2,
                "Asking for a list of concepts"
                if attempt == 1
                else "The first answer was not usable. Asking once more",
            )
            request = prompts.curriculum_request(
                course_title=title,
                topic=topic,
                description=description,
                goal=goal,
                existing_titles=existing,
                headings=headings,
                passages=excerpts,
                problems=problems,
            )
            result = self._ask(request, context, attempt - 1, 2)
            try:
                proposed = compile_curriculum(
                    extract_json_object(result.text),
                    existing_titles=existing,
                    section_ids=section_ids,
                )
            except DraftError as error:
                logger.info("generation.curriculum_unusable attempt=%s", attempt)
                problems = error.problems
                continue
            context.report(2, 2, "Done")
            return {
                "kind": KIND_CURRICULUM,
                "concepts": [concept.as_dict() for concept in proposed],
                "grounded_in_materials": bool(headings),
                "accepted": False,
                "dismissed": False,
            }
        raise GenerationFailedError(
            "The AI's proposal did not come out in a usable form, twice. Nothing was added. "
            "You can try again, or add concepts by hand."
        )

    def latest_proposal(self, course_id: str) -> JobSnapshot | None:
        """The newest proposal job for a course: under way, waiting to be reviewed, or done with."""
        with self._database.session() as session:
            get_course_or_404(session, course_id)
        return self._jobs.latest(KIND_CURRICULUM, course_id)

    def _finished_proposal(self, job_id: str) -> tuple[JobSnapshot, dict[str, Any]]:
        job = self._jobs.get(job_id)
        result = job.result
        if (
            job.kind != KIND_CURRICULUM
            or job.status != "succeeded"
            or job.course_id is None
            or not isinstance(result, dict)
        ):
            raise NotFoundError("That proposal is no longer available. Ask for a new one.")
        if result.get("accepted"):
            raise ConflictError("That proposal has already been added to the course.")
        if result.get("dismissed"):
            raise ConflictError("That proposal was set aside. Ask for a new one.")
        return job, result

    def dismiss_proposal(self, job_id: str) -> JobSnapshot:
        """Set a finished proposal aside without adding anything from it."""
        _, result = self._finished_proposal(job_id)
        self._jobs.set_result(job_id, {**result, "dismissed": True})
        return self._jobs.get(job_id)

    def accept_proposal(self, job_id: str, selected: Sequence[int]) -> CurriculumRecord:
        """Add the concepts the learner picked from a finished proposal. Usable once."""
        job, result = self._finished_proposal(job_id)
        assert job.course_id is not None
        concepts = result.get("concepts")
        if not isinstance(concepts, list):
            raise NotFoundError("That proposal is no longer available. Ask for a new one.")
        chosen = sorted({index for index in selected if 0 <= index < len(concepts)})
        if not chosen:
            raise ValidationFailedError("Choose at least one concept to add.")

        position = {index: place for place, index in enumerate(chosen)}
        inputs = []
        for index in chosen:
            concept = concepts[index]
            inputs.append(
                ProposedConceptInput(
                    title=str(concept.get("title", "")),
                    summary=str(concept.get("summary", "")),
                    objectives=[str(text) for text in concept.get("objectives", [])],
                    # A need that was not chosen is dropped; the learner can add it by hand.
                    needs=[
                        (position[need["index"]], str(need.get("reason", "")))
                        for need in concept.get("needs", [])
                        if isinstance(need, dict) and need.get("index") in position
                    ],
                    section_ids=[str(section) for section in concept.get("section_ids", [])],
                )
            )
        curriculum = self._curriculum.add_proposed(job.course_id, inputs)
        self._jobs.set_result(job_id, {**result, "accepted": True})
        return curriculum

    # -- lessons ---------------------------------------------------------------

    def generate_lesson(self, concept_id: str) -> JobSnapshot:
        """Start a job that writes a lesson for one concept."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            course_id = concept.course_id
            if not concept.objectives:
                raise ValidationFailedError(
                    "Give this concept at least one learning objective first, "
                    "so the lesson has something to aim at."
                )
        self._require_key()
        running = self._jobs.find_active(KIND_LESSON, concept_id)
        if running is not None:
            return running
        return self._jobs.submit(
            KIND_LESSON,
            lambda context: self._write_lesson(concept_id, context),
            course_id=course_id,
            subject_id=concept_id,
        )

    def _lesson_inputs(self, concept_id: str) -> _LessonInputs:
        with self._database.session() as session:
            concept_row = get_concept_or_404(session, concept_id)
            course: Course = get_course_or_404(session, concept_row.course_id)
            course_id, course_title = course.id, course.title
        curriculum = self._curriculum.get(course_id)
        concept = next((item for item in curriculum.concepts if item.id == concept_id), None)
        if concept is None:
            raise NotFoundError("That concept no longer exists.")
        stored = self._curriculum.related_passages(concept_id, limit=prompts.MAX_PASSAGES)
        preferences = self._learner.get_preferences()
        return _LessonInputs(
            course_title=course_title,
            concept=prompts.ConceptBrief(
                title=concept.title,
                summary=concept.summary,
                objectives=[objective.statement for objective in concept.objectives],
                prerequisites=[item.title for item in concept.prerequisites],
            ),
            learner=self._learner_brief(concept, preferences),
            passages=[
                prompts.Passage(
                    source_name=passage.source_name, locator=_locator(passage), text=passage.text
                )
                for passage in stored
            ],
            context=LessonContext(
                lesson_id=new_id("les"),
                course_id=course_id,
                concept_id=concept_id,
                objectives=[
                    ObjectiveRef(id=objective.id, statement=objective.statement)
                    for objective in concept.objectives
                ],
                passages=[
                    PassageRef(
                        source_id=passage.source_id,
                        section_id=passage.section_id,
                        source_name=_citable(passage.source_name),
                        locator=_citable(_locator(passage)),
                    )
                    for passage in stored
                ],
            ),
        )

    @staticmethod
    def _learner_brief(
        concept: ConceptRecord, preferences: LearnerPreferences
    ) -> prompts.LearnerBrief:
        knowledge = concept.knowledge
        said = [f"{knowledge.label}."]
        if knowledge.self_report in _SELF_REPORT:
            said.append(_SELF_REPORT[knowledge.self_report])
        if knowledge.answered == 0:
            said.append("They have not answered any question about it yet.")
        return prompts.LearnerBrief(
            knowledge=" ".join(said),
            pace=_PACE.get(preferences.pace, "moderate"),
            explanation_density=_DENSITY.get(preferences.explanation_density, "moderate"),
            goal=preferences.goal,
        )

    def _write_lesson(self, concept_id: str, context: JobContext) -> dict[str, Any]:
        inputs = self._lesson_inputs(concept_id)
        # One request for the lesson and, usually, two for its pictures.
        planned = 3

        lesson: dict[str, Any] | None = None
        briefs: list[SceneBrief] = []
        problems: list[str] = []
        for attempt in (1, 2):
            context.check_cancelled()
            context.report(
                0,
                planned,
                "Writing the lesson"
                if attempt == 1
                else "The first draft was not usable. Writing it once more",
            )
            request = prompts.lesson_request(
                course_title=inputs.course_title,
                concept=inputs.concept,
                learner=inputs.learner,
                passages=inputs.passages,
                problems=problems,
            )
            result = self._ask(request, context, 0, planned)
            try:
                compiled = compile_lesson(
                    parse_lesson_draft(extract_json_object(result.text)), inputs.context
                )
                # Checked before any picture is asked for: a lesson that will not validate
                # is not worth two more requests.
                Lesson.model_validate(compiled.lesson)
            except DraftError as error:
                problems = error.problems
            except ValidationError as error:
                problems = _problem_list(error)
            else:
                lesson, briefs = compiled.lesson, compiled.scenes
                break
            logger.info("generation.lesson_unusable attempt=%s", attempt)
        if lesson is None:
            raise GenerationFailedError(
                "The AI's lesson did not come out in a usable form, twice. Nothing was saved. "
                "You can try again."
            )

        total = 1 + len(briefs)
        scenes: list[dict[str, str]] = []
        notes: list[str] = []
        for number, brief in enumerate(briefs, start=1):
            context.check_cancelled()
            label = f"Drawing picture {number} of {len(briefs)}"
            context.report(number, total, label)
            try:
                artifact = self._write_scene(brief, context, number, total, label)
            except JobCancelledError:
                raise
            except (ProviderError, QuotaExhaustedError) as error:
                # The lesson itself is written. Losing its pictures is better than losing it.
                logger.info("generation.scene_skipped code=%s", error.code)
                artifact = None
            if artifact is None:
                lesson = without_scene(lesson, brief.scene_id)
                notes.append(
                    f'The picture for "{brief.title}" could not be made, '
                    "so that part is explained in words."
                )
                continue
            if brief.kind == "interactive" and not artifact.interactive:
                lesson = as_visualization(lesson, brief.scene_id)
                notes.append(
                    f'"{brief.title}" was meant to be something to try, '
                    "but came out as an animation to watch."
                )
            scenes.append(
                {"id": artifact.id, "purpose": artifact.purpose, "source": artifact.source}
            )

        context.check_cancelled()
        context.report(total, total, "Checking the lesson")
        bundle = parse_bundle({"lesson": lesson, "scenes": scenes})
        stored = self._lessons.store(bundle, origin="generated")
        return {
            "kind": KIND_LESSON,
            "lesson_id": stored.id,
            "title": stored.title,
            "pictures_planned": len(briefs),
            "pictures_made": len(scenes),
            "notes": notes,
        }

    def _write_scene(
        self, brief: SceneBrief, context: JobContext, done: int, total: int, label: str
    ) -> SceneArtifact | None:
        """One scene file, or ``None``. One request, and one more only if the file was refused."""
        problems: list[str] = []
        fallback: SceneArtifact | None = None
        for attempt in (1, 2):
            context.check_cancelled()
            if attempt == 2:
                context.report(done, total, f"{label} (second and last try)")
            result = self._ask(
                prompts.scene_request(brief, problems=problems), context, done, total
            )
            source = extract_python_file(result.text)
            try:
                artifact = inspect_scene(brief.scene_id, brief.title, source)
            except SceneRejectedError as error:
                problems = [
                    f"line {violation.line}: {violation.message}"
                    if violation.line
                    else violation.message
                    for violation in error.violations[:10]
                ]
                logger.info("generation.scene_rejected attempt=%s", attempt)
                continue
            except ValidationError as error:
                problems = _problem_list(error)
                continue
            if brief.kind == "interactive" and not artifact.interactive:
                # Usable as a picture, but not what was asked for: worth one more try.
                fallback = artifact
                problems = [
                    "The file has no control the learner can operate. An interactive scene "
                    "subclasses InteractiveScene, creates a Slider or a Switch in blueprint(), "
                    "and lists it in self.adle_controls."
                ]
                continue
            return artifact
        return fallback
