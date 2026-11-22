"""Asking the model for a curriculum, a lesson, or an answer, as background jobs.

Each job is a short, fixed sequence of requests. Nothing here loops on the
model's output:

* a **curriculum proposal** is one request (two if the first answer was not
  usable). Its result is only a proposal: nothing is added to the course until
  the learner picks from it (``accept_proposal``).
* a **lesson** is one request for the lesson (two at most), then one request
  per scene (two at most each), and a lesson asks for at most two scenes.
* an **answer** to something the learner asked in the middle of a lesson is one
  request (two if the first answer was not usable). It is kept beside the part
  it was asked about (ADR-024).
* a **check** that a provider's key works is one request of a few words, with
  nothing of the learner's in it.

The first two are long work and run one at a time. The last two are what the
learner is sitting and waiting for, and run in the quick lane beside them.

A scene that cannot be made does not cost the learner the lesson: that part is
kept as words. Everything the model writes goes through the same validation as
any other lesson before it is stored.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from adle_core.application.asks import (
    MAX_ASKS_PER_LESSON,
    MAX_QUESTION_CHARACTERS,
    MIN_QUESTION_CHARACTERS,
    AskCitation,
    AskService,
)
from adle_core.application.courses import get_course_or_404
from adle_core.application.curriculum import (
    ConceptRecord,
    CurriculumRecord,
    CurriculumService,
    ProposedConceptInput,
    get_concept_or_404,
)
from adle_core.application.jobs import (
    LANE_QUICK,
    JobCancelledError,
    JobContext,
    JobRunner,
    JobSnapshot,
)
from adle_core.application.learner import LearnerService
from adle_core.application.lessons import LessonService
from adle_core.application.model_gateway import ModelGateway, QuotaExhaustedError
from adle_core.application.retrieval import Passage as StoredPassage
from adle_core.application.retrieval import Retriever
from adle_core.application.scene_trials import SceneTrials, TrialFailure
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.generation import prompts
from adle_core.generation.drafts import (
    DraftError,
    FigureScene,
    LessonContext,
    ObjectiveRef,
    PassageRef,
    SceneBrief,
    compile_answer,
    compile_curriculum,
    compile_lesson,
    extract_json_object,
    extract_python_file,
    parse_lesson_draft,
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
from adle_core.infrastructure.orm import Attempt, Concept, Course, StoredLesson
from adle_core.ingestion.types import heading_leaf
from adle_core.learner_model.next_step import MAX_LESSONS_PER_CONCEPT
from adle_core.learner_model.preferences import LearnerPreferences
from adle_core.lessons.bundle import (
    LessonInvalidError,
    SceneRejectedError,
    inspect_scene,
    parse_bundle,
)
from adle_core.lessons.ir import (
    STRATEGIES,
    CheckpointSegment,
    ChoiceItem,
    Lesson,
    OrderingItem,
    SceneArtifact,
    SceneRef,
    TrueFalseItem,
)

logger = logging.getLogger(__name__)

KIND_CURRICULUM = "curriculum_proposal"
KIND_LESSON = "lesson_generation"
KIND_ASK = "lesson_ask"
KIND_CHECK = "provider_check"
#: Long work: what the learner may leave to itself and come back to.
LONG_JOB_KINDS: tuple[str, ...] = (KIND_CURRICULUM, KIND_LESSON)
#: Every kind of job that asks a model for something.
MODEL_JOB_KINDS: tuple[str, ...] = (*LONG_JOB_KINDS, KIND_ASK, KIND_CHECK)

#: Why a provider's next model, or the next provider, is being asked, in the learner's words.
_PASSED_OVER = {
    "gone": "isn’t available right now",
    "failing": "is having trouble right now",
    "silent": "isn’t answering",
    "refused": "didn’t accept the request",
    "spent": "has no allowance left today",
    "rate_limited": "is limiting requests right now",
    "notice": "returned a notice about your account",
    "key_rejected": "rejected its key",
    "unreachable": "couldn’t be reached",
    "unreadable": "sent an unreadable answer",
}
#: The requests that stand between asking and having something to use, for saying how
#: long that will be. A lesson can be taken when its text is written (ADR-031): its
#: pictures follow, and are not part of the wait.
_REQUESTS_FOR = {
    "lesson": ("lesson",),
    "curriculum": ("curriculum",),
    "ask": ("ask",),
    "scene": ("scene",),
}
#: What a model is seen to be doing while its answer is on the way, in the learner's words.
_STAGES = {"thinking": "thinking", "writing": "writing"}

#: In an answer that is still arriving: a title, as the JSON of a draft writes one, or the
#: key that opens a lesson's list of parts. Inside a sentence the quotation marks of such a
#: pair are escaped, so this finds keys only.
_TITLE_IN_DRAFT = re.compile(r'"segments"\s*:|"title"\s*:\s*"((?:[^"\\]|\\.)*)"')
#: The longest piece of an answer kept to look for the end of a title that has begun.
_TITLE_LOOKBACK = 600
#: Titles shown while something is written: enough for any lesson or list of concepts.
_MAX_OUTLINE = 40


def _plain_title(raw: str) -> str:
    """A title as it will read, from the text between its quotation marks in the draft."""
    try:
        value = json.loads(f'"{raw}"')
    except ValueError:
        value = raw
    return " ".join(str(value).split())[:120]


@dataclass(slots=True)
class Outline:
    """What can be said about an answer while it is still being written: its titles (ADR-037).

    A lesson's draft names the lesson first and then each of its parts; a list of concepts
    names each concept. Nothing else of the answer is read here, and nothing of it is
    kept: a learner who is waiting is shown which parts exist so far, never the words.
    """

    #: The answer has a title of its own before its list of parts (a lesson's draft): a
    #: title found before ``"segments"`` names the whole thing, and every later one a part.
    named: bool = False
    title: str = ""
    parts: list[str] = field(default_factory=list)
    _among_parts: bool = False
    _unread: str = ""

    def add(self, piece: str) -> bool:
        """Take in the next piece of the answer. True when it completed a title."""
        self._unread += piece
        found = False
        consumed = 0
        for match in _TITLE_IN_DRAFT.finditer(self._unread):
            consumed = match.end()
            if match.group(1) is None:
                self._among_parts = True
                continue
            title = _plain_title(match.group(1))
            if not title:
                continue
            if self.named and not self._among_parts and not self.title:
                self.title = title
            elif len(self.parts) < _MAX_OUTLINE:
                self.parts.append(title)
            else:
                continue
            found = True
        self._unread = self._unread[consumed:][-_TITLE_LOOKBACK:]
        return found

    def start_again(self) -> None:
        """Another model begins the answer from its first word."""
        self.title = ""
        self.parts.clear()
        self._among_parts = False
        self._unread = ""


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
class Wait:
    """How long something is likely to take. Said as "about", never as a promise."""

    seconds: int
    #: From answers that arrived on this computer, not only from what is usual.
    measured: bool


def _part_brief(lesson: Lesson, index: int, *, answered: bool) -> prompts.PartBrief:
    """One part of a lesson as a model is shown it. Never what its question's answer is.

    An ordering question lists its items in the right order, so they are shown sorted
    by their words. Accepted answers, the expected number, the rubric, and the hint
    are left out. The lesson's own explanation is included only once the learner has
    answered: by then they have seen it.
    """
    segment = lesson.segments[index]
    scene = getattr(segment, "scene", None)
    question, options, explanation = "", [], ""
    if isinstance(segment, CheckpointSegment):
        item = segment.question
        question = item.stem
        if isinstance(item, ChoiceItem):
            options = [option.text for option in item.options]
        elif isinstance(item, OrderingItem):
            options = sorted(option.text for option in item.items)
        elif isinstance(item, TrueFalseItem):
            options = ["True", "False"]
        if answered:
            explanation = item.explanation
    return prompts.PartBrief(
        number=index + 1,
        title=segment.title,
        kind=segment.type,
        said=[beat.text for beat in segment.narration],
        shown=[beat.show for beat in segment.narration if beat.show],
        picture=scene.fallback_text if isinstance(scene, SceneRef) else "",
        task=str(getattr(segment, "prompt", "") or getattr(segment, "problem", "") or ""),
        question=question,
        options=options,
        answered=answered,
        explanation=explanation,
    )


@dataclass(frozen=True, slots=True)
class _LessonInputs:
    course_title: str
    concept: prompts.ConceptBrief
    learner: prompts.LearnerBrief
    passages: list[prompts.Passage]
    context: LessonContext
    #: The way of teaching asked for, if one was chosen.
    approach: str | None = None
    #: The ways earlier lessons on this concept used.
    earlier: tuple[str, ...] = ()


#: When another explanation is wanted and the learner has not said which kind, the first
#: of these that the concept's lessons have not used yet.
STRATEGY_ROTATION = (
    "visual",
    "worked_example",
    "analogy",
    "mathematical",
    "computational",
    "socratic",
)


def next_strategy(used: Sequence[str]) -> str | None:
    """A way of teaching the concept has not had yet. ``None`` for a first lesson: no constraint."""
    if not used:
        return None
    return next((name for name in STRATEGY_ROTATION if name not in used), None)


def _listed(names: Sequence[str]) -> str:
    """ "A", "A and B", "A, B, and C"."""
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


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
        asks: AskService,
        trials: SceneTrials | None = None,
        on_stored: Callable[[str], None] | None = None,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._gateway = gateway
        self._curriculum = curriculum
        self._lessons = lessons
        self._learner = learner
        self._retriever = retriever
        self._asks = asks
        self._trials = trials if trials is not None else SceneTrials()
        #: Told the id of each lesson as soon as its words are stored: the natural voice
        #: begins on them then (``NarrationService.record_ahead``).
        self._on_stored = on_stored
        #: Looking for work that is under way and starting it are one step. Without this,
        #: two requests arriving together both find nothing and both begin: the same
        #: lesson written twice, or a provider chosen under a job that has just started.
        self._starting = threading.Lock()

    @property
    def trials(self) -> SceneTrials:
        """Pictures waiting to be tried in the app's player (ADR-038)."""
        return self._trials

    # -- the one way a request is made ---------------------------------------

    def _ask(
        self,
        request: ChatRequest,
        context: JobContext,
        done: int,
        total: int,
        doing: str,
        *,
        provider_id: str | None = None,
        outline: Outline | None = None,
        stage: str | None = None,
    ) -> ChatResult:
        """Send one request from inside a job, keeping the job's progress honest while it waits.

        ``doing`` is what the job is doing, in the words the learner is shown. A model
        that thinks before it writes can take minutes over one answer, so what it is
        seen to be doing is said beside it: a long wait should not look like a stall.
        ``provider_id`` asks one provider whatever the learner's choice would plan.

        Beside the sentence the job says what stage the request is at (``stage`` names it
        where it is not a matter of thinking and writing: a picture is ``drawing``) and,
        given an ``outline``, which titles of the answer have been written so far.
        """
        message = doing
        at: str | None = stage

        def say(now: str | None = None, reached: str | None = None) -> None:
            nonlocal message, at
            if now is not None:
                message = now
            if reached is not None:
                at = stage or reached
            detail: dict[str, Any] = {}
            if at is not None:
                detail["stage"] = at
            if outline is not None:
                if outline.title:
                    detail["title"] = outline.title
                detail["outline"] = list(outline.parts)
            context.report(done, total, message, detail or None)

        def busy(provider: str) -> None:
            say(f"Waiting for {provider} to finish another request", "waiting")

        def at_stage(model: str, reached: str) -> None:
            if reached == "thinking" and outline is not None:
                # Whoever thinks now writes the answer from its first word.
                outline.start_again()
            say(f"{doing}: {model} is {_STAGES.get(reached, 'working')}", reached)

        def waiting(seconds: float) -> None:
            say(
                f"Waiting about {max(1, round(seconds))} seconds to stay under the rate limit",
                "waiting",
            )

        def standing_in(unavailable: str, following: str, why: str) -> None:
            # Said while it happens, so that a longer wait has its reason beside it.
            if outline is not None:
                outline.start_again()
            say(
                f"{unavailable} {_PASSED_OVER.get(why, 'is not answering')}. "
                f"Asking {following} instead",
                "waiting",
            )

        def piece(written: str) -> None:
            # Only a new title is worth saying: the words between them are the answer.
            if outline is not None and outline.add(written):
                say()

        try:
            return self._gateway.complete(
                request,
                cancelled=lambda: context.cancelled,
                on_wait=waiting,
                on_fallback=standing_in,
                on_stage=at_stage,
                on_busy=busy,
                provider_id=provider_id,
                on_piece=piece if outline is not None else None,
            )
        except RequestCancelledError as error:
            raise JobCancelledError from error

    def _require_key(self) -> None:
        if not self._gateway.has_key:
            raise ProviderKeyMissingError

    def select_provider(self, selection: str) -> None:
        """Record the learner's choice: one provider, or "automatic".

        Refused while something is being written: what is under way was started with
        its destination named beside it, and must not finish somewhere else.
        """
        if not self._gateway.accepts(selection):
            raise NotFoundError("Unknown AI provider.")
        with self._starting:
            if selection == self._gateway.selection:
                return
            if self._jobs.any_active(MODEL_JOB_KINDS):
                raise ConflictError(
                    "Something is being written right now. Wait for it to finish, or stop it, "
                    "then change the provider."
                )
            self._gateway.select(selection)

    def _written_by(self, results: Sequence[ChatResult]) -> dict[str, Any]:
        """Who wrote something, for its record: each provider and model that answered.

        ``note`` is one or two sentences for the learner when what wrote it was not what
        was asked first: another model of the provider, or another provider. A stand-in
        is never left unsaid.
        """
        authors = list(
            dict.fromkeys(
                (result.provider_name, result.model_name) for result in results if result.model_name
            )
        )
        providers = list(dict.fromkeys(provider for provider, _ in authors if provider))
        models = list(dict.fromkeys(model for _, model in authors))
        notes = []
        asked_first = next(
            (result.instead_of_provider for result in results if result.instead_of_provider), ""
        )
        others = [name for name in providers if name != asked_first]
        if asked_first and others:
            share = "part of this" if asked_first in providers else "this"
            notes.append(f"{asked_first} couldn’t answer, so {_listed(others)} wrote {share}.")
        expected = next((result.instead_of for result in results if result.instead_of), "")
        stand_ins = [name for name in models if name != expected]
        if expected and stand_ins:
            share = "part of this" if expected in models else "this"
            notes.append(
                f"{expected} wasn’t available, so {_listed(stand_ins)} wrote {share} instead."
            )
        return {
            # The first provider that wrote any of it; all of them are in ``authors``.
            "provider": providers[0] if providers else self._gateway.config.display_name,
            "models": models,
            "authors": [{"provider": provider, "model": model} for provider, model in authors],
            # The model that was meant to write it, when it was not available.
            "instead_of": expected,
            "note": " ".join(notes),
        }

    # -- what to expect, and what is under way ---------------------------------

    def expected_wait(self, work: str) -> Wait:
        """How long a lesson, a list of concepts, or an answer is likely to take now.

        From the provider it would be asked of first: what its last few answers of each
        kind took on this computer, or what is usual for it before any have arrived.
        """
        purposes = _REQUESTS_FOR[work]
        first = self._gateway.plan(purposes[0]).provider_ids[0]
        found = [self._gateway.seconds_for(first, purpose) for purpose in purposes]
        return Wait(
            seconds=sum(seconds for seconds, _ in found),
            measured=all(measured for _, measured in found),
        )

    def writing(self) -> list[JobSnapshot]:
        """Long work that is waiting or under way, in any course, oldest first."""
        return self._jobs.list_all_active(LONG_JOB_KINDS)

    def stop_for_lesson(self, lesson_id: str) -> None:
        """A lesson was removed: stop drawing the pictures it was still waiting for.

        Nothing more is asked of a provider for something the learner has thrown away.
        """
        for job in self._jobs.list_all_active((KIND_LESSON,)):
            result = job.result
            if isinstance(result, dict) and result.get("lesson_id") == lesson_id:
                with contextlib.suppress(NotFoundError):
                    self._jobs.cancel(job.id)

    def stop_for_course(self, course_id: str) -> None:
        """A course is about to be removed: stop whatever is under way for it."""
        for job in self._jobs.list_active(course_id):
            with contextlib.suppress(NotFoundError):
                self._jobs.cancel(job.id)

    # -- curriculum ------------------------------------------------------------

    def propose_curriculum(self, course_id: str) -> JobSnapshot:
        """Start a job that asks the model for concepts this course could teach."""
        with self._database.read() as session:
            get_course_or_404(session, course_id)
        self._require_key()
        with self._starting:
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
        with self._database.read() as session:
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
        pages: list[str] = []
        if not candidates:
            # Materials without headings are still the whole of what the course covers:
            # their pages, from first to last, and not only what matches its title.
            openings = self._curriculum.page_openings(course_id, prompts.MAX_HEADINGS)
            pages = [f"{opening.label}: {opening.opening}" for opening in openings]
            section_ids = [opening.section_id for opening in openings]
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
            doing = (
                "Suggesting concepts"
                if attempt == 1
                else "The first answer wasn’t usable. Asking once more"
            )
            # One request, whose length nobody knows: no share of it is ever "done".
            context.report(0, 0, doing)
            request = prompts.curriculum_request(
                course_title=title,
                topic=topic,
                description=description,
                goal=goal,
                existing_titles=existing,
                headings=headings,
                pages=pages,
                passages=excerpts,
                problems=problems,
            )
            result = self._ask(request, context, attempt - 1, 2, doing, outline=Outline())
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
                "written_by": self._written_by([result]),
            }
        raise GenerationFailedError(
            "The AI’s suggestions weren’t usable, twice. Nothing was added. Try again, or add "
            "concepts by hand."
        )

    def latest_proposal(self, course_id: str) -> JobSnapshot | None:
        """The newest proposal job for a course: under way, waiting to be reviewed, or done with."""
        with self._database.read() as session:
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
            raise NotFoundError("Those suggestions are no longer available. Ask for new ones.")
        if result.get("accepted"):
            raise ConflictError("Those suggestions were already added.")
        if result.get("dismissed"):
            raise ConflictError("Those suggestions were discarded. Ask for new ones.")
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
            raise NotFoundError("Those suggestions are no longer available. Ask for new ones.")
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

    def generate_lesson(self, concept_id: str, *, strategy: str | None = None) -> JobSnapshot:
        """Start a job that writes a lesson for one concept.

        ``strategy`` is the way of teaching the learner asked for. Without one, a first
        lesson is left to the writer, and a further lesson uses a way the concept has not
        had yet, so that "another explanation" is never the same explanation.
        """
        if strategy is not None and strategy not in STRATEGIES:
            raise ValidationFailedError("Unknown teaching style.")
        with self._database.read() as session:
            concept = get_concept_or_404(session, concept_id)
            course_id = concept.course_id
            if not concept.objectives:
                raise ValidationFailedError("Add a learning objective to this concept first.")
            existing = len(self._strategies_used(session, concept_id))
        with self._starting:
            running = self._jobs.find_active(KIND_LESSON, concept_id)
            if running is not None:
                return running
            if existing >= MAX_LESSONS_PER_CONCEPT:
                # More explanations of one thing stop helping, and each costs requests.
                raise ConflictError(
                    f"This concept already has {existing} lessons. "
                    "Remove one before creating another."
                )
            self._require_key()
            return self._jobs.submit(
                KIND_LESSON,
                lambda context: self._write_lesson(concept_id, context, strategy),
                course_id=course_id,
                subject_id=concept_id,
            )

    @staticmethod
    def _strategies_used(session: Session, concept_id: str) -> list[str]:
        """The way of teaching of each lesson listed under a concept, oldest first."""
        documents = session.scalars(
            select(StoredLesson.document)
            .where(StoredLesson.concept_id == concept_id)
            .order_by(StoredLesson.created_at, StoredLesson.id)
        )
        return [str(document.get("strategy", "")) for document in documents]

    def _lesson_inputs(self, concept_id: str, strategy: str | None = None) -> _LessonInputs:
        with self._database.read() as session:
            concept_row = get_concept_or_404(session, concept_id)
            course: Course = get_course_or_404(session, concept_row.course_id)
            course_id, course_title = course.id, course.title
            used = [
                name for name in self._strategies_used(session, concept_id) if name in STRATEGIES
            ]
        approach = strategy or next_strategy(used)
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
                strategy=approach,
            ),
            approach=approach,
            earlier=tuple(dict.fromkeys(used)),
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

    def _write_lesson(
        self, concept_id: str, context: JobContext, strategy: str | None = None
    ) -> dict[str, Any]:
        inputs = self._lesson_inputs(concept_id, strategy)
        # One request for the lesson and, usually, two for its pictures.
        planned = 3

        lesson: dict[str, Any] | None = None
        briefs: list[SceneBrief] = []
        figures: list[FigureScene] = []
        problems: list[str] = []
        #: The answers that end up in the lesson: its text, then each picture kept.
        answers: list[ChatResult] = []
        for attempt in (1, 2):
            context.check_cancelled()
            doing = (
                "Writing the lesson"
                if attempt == 1
                else "The first draft wasn’t usable. Writing it once more"
            )
            context.report(0, planned, doing)
            request = prompts.lesson_request(
                course_title=inputs.course_title,
                concept=inputs.concept,
                learner=inputs.learner,
                passages=inputs.passages,
                problems=problems,
                approach=inputs.approach,
                earlier=inputs.earlier,
            )
            result = self._ask(request, context, 0, planned, doing, outline=Outline(named=True))
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
                lesson, briefs, figures = compiled.lesson, compiled.scenes, compiled.figures
                if compiled.figures_dropped:
                    logger.info("generation.figures_dropped count=%s", compiled.figures_dropped)
                answers.append(result)
                break
            logger.info("generation.lesson_unusable attempt=%s", attempt)
        if lesson is None:
            raise GenerationFailedError(
                "The AI’s lesson wasn’t usable, twice. Nothing was saved. You can try again."
            )

        # From here on there is a lesson. It is stored now, with its pictures marked as
        # still to come, so that the learner can begin while they are drawn (ADR-031).
        context.check_cancelled()
        waiting = [figure.scene_id for figure in figures] + [brief.scene_id for brief in briefs]
        bundle = parse_bundle({"lesson": lesson, "scenes": [], "pending_scene_ids": waiting})
        stored = self._lessons.store(
            bundle, origin="generated", written_by=self._written_by(answers)
        )
        total = 1 + len(briefs)
        planned_pictures = len(figures) + len(briefs)
        made = 0
        notes: list[str] = []

        def so_far(left: int) -> dict[str, Any]:
            written_by = self._written_by(answers)
            return {
                "kind": KIND_LESSON,
                "lesson_id": stored.id,
                "title": stored.title,
                "pictures_planned": planned_pictures,
                "pictures_made": made,
                "pictures_pending": left,
                "notes": [*notes, *([written_by["note"]] if written_by["note"] else [])],
                "written_by": written_by,
            }

        context.publish(so_far(planned_pictures))
        if self._on_stored is not None:
            self._on_stored(stored.id)
        try:
            # The figures first: drawn already, each is tried in the player and taken into
            # the lesson in a second or two (ADR-045). All are offered for their trials at
            # once, so that the app runs them one after another, in order, without waiting
            # to be asked for each.
            offered = [self._offer_figure(figure) for figure in figures]
            try:
                for number, figure in enumerate(figures, start=1):
                    context.check_cancelled()
                    context.report(
                        0,
                        total,
                        f"Drawing picture {number} of {planned_pictures}",
                        {"stage": "drawing"},
                    )
                    if self._settle_figure(stored.id, figure, offered[number - 1], context):
                        made += 1
                    else:
                        notes.append(
                            f"The picture for “{figure.title}” couldn’t be shown, so that part "
                            "is explained in words."
                        )
                    context.publish(so_far(planned_pictures - number))
            finally:
                # A trial nobody waits for any more is not run.
                for _, trial_id in offered:
                    if trial_id is not None:
                        self._trials.withdraw(trial_id)
            for number, brief in enumerate(briefs, start=1):
                context.check_cancelled()
                label = f"Drawing picture {len(figures) + number} of {planned_pictures}"
                context.report(number, total, label, {"stage": "drawing"})
                try:
                    artifact, answer = self._write_scene(brief, context, number, total, label)
                except JobCancelledError:
                    raise
                except (ProviderError, QuotaExhaustedError) as error:
                    # The lesson is written. Losing a picture is better than losing it.
                    logger.info("generation.scene_skipped code=%s", error.code)
                    artifact, answer = None, None
                settled = None
                if artifact is not None:
                    try:
                        settled = self._lessons.settle_scene(
                            stored.id,
                            brief.scene_id,
                            {"purpose": artifact.purpose, "source": artifact.source},
                        )
                    except (LessonInvalidError, SceneRejectedError) as error:
                        # Drawn, and yet not something this lesson can take. The lesson is
                        # there already: that part is said in words, as for a picture that
                        # never came, and the work goes on.
                        logger.info("generation.scene_unattached code=%s", error.code)
                if settled is None:
                    self._lessons.settle_scene(stored.id, brief.scene_id, None)
                    notes.append(
                        f"The picture for “{brief.title}” couldn’t be made, so that part is "
                        "explained in words."
                    )
                else:
                    if answer is not None:
                        answers.append(answer)
                    made += 1
                    if settled.as_animation:
                        notes.append(
                            f"“{brief.title}” was meant to be interactive, but came out as an "
                            "animation."
                        )
                context.publish(so_far(len(briefs) - number))
        except JobCancelledError:
            # Stopped once there was a lesson: the lesson stays, and what was not drawn is
            # said in words. Stopping before this point saves nothing, as it always did.
            left = self._lessons.settle_unfinished(stored.id)
            if left:
                notes.append(
                    "You stopped the pictures, so "
                    + ("1 part is" if left == 1 else f"{left} parts are")
                    + " explained in words."
                )
        except NotFoundError:
            # The lesson went away under the work: said just below.
            pass
        finally:
            # Whatever ended the work, nothing may be left waiting for a picture.
            with contextlib.suppress(AdleError):
                self._lessons.settle_unfinished(stored.id)

        if not self._lessons.exists(stored.id):
            # The learner removed the lesson, or its course, while its pictures were being
            # drawn: there is nothing left to draw them for, and nothing to report.
            raise JobCancelledError(None)

        context.report(total, total, "Done")
        final = so_far(0)
        self._lessons.set_written_by(stored.id, final["written_by"])
        return final

    def _write_scene(
        self, brief: SceneBrief, context: JobContext, done: int, total: int, label: str
    ) -> tuple[SceneArtifact | None, ChatResult | None]:
        """One scene file and the answer it came in, or neither.

        One request, and one more only if the file was refused by the rules or failed when
        it was tried in the app's player (ADR-038); the second is told what went wrong. A
        file that failed its trial is never kept: a part without its picture is said in
        words, and a picture that breaks in front of the learner is said in words too, late.
        """
        problems: list[str] = []
        #: The first file, when it passed the rules and failed when it was run.
        previous: str | None = None
        fallback: tuple[SceneArtifact | None, ChatResult | None] = (None, None)
        for attempt in (1, 2):
            context.check_cancelled()
            doing = label if attempt == 1 else f"{label} (second try)"
            if attempt == 2:
                context.report(done, total, doing, {"stage": "drawing"})
            result = self._ask(
                prompts.scene_request(brief, problems=problems, previous=previous),
                context,
                done,
                total,
                doing,
                stage="drawing",
            )
            source = extract_python_file(result.text)
            previous = None
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
            failure = self._try_in_player(artifact, context)
            if failure is not None:
                # The stage only: what the scene said is the model's text (ADR-029).
                logger.info(
                    "generation.scene_failed_trial attempt=%s stage=%s", attempt, failure.stage
                )
                problems = [failure.as_problem()]
                previous = artifact.source
                continue
            if brief.kind == "interactive" and not artifact.interactive:
                # Usable as a picture, but not what was asked for: worth one more try.
                fallback = (artifact, result)
                problems = [
                    "The file has no control the learner can operate. An interactive scene "
                    "subclasses InteractiveScene, creates a Slider or a Switch in blueprint(), "
                    "and lists it in self.adle_controls."
                ]
                continue
            return artifact, result
        return fallback

    def _offer_figure(self, figure: FigureScene) -> tuple[SceneArtifact | None, str | None]:
        """A figure as a scene the gate takes, and its trial in the app's player if the app
        is there to run one: (None, None) for a figure the gate refuses."""
        try:
            artifact = inspect_scene(figure.scene_id, figure.title, figure.source)
        except (SceneRejectedError, ValidationError) as error:
            logger.info(
                "generation.figure_unattached kind=%s error=%s", figure.kind, type(error).__name__
            )
            return None, None
        if not self._trials.present():
            return artifact, None
        trial_id = self._trials.offer(
            scene_class=artifact.scene_class,
            source=artifact.source,
            interactive=artifact.interactive,
            controls=tuple(artifact.controls),
        )
        return artifact, trial_id

    def _settle_figure(
        self,
        lesson_id: str,
        figure: FigureScene,
        offered: tuple[SceneArtifact | None, str | None],
        context: JobContext,
    ) -> bool:
        """Take a figure into the stored lesson once it has run in the player, or say its
        part in words. Whether it was taken."""
        artifact, trial_id = offered
        if artifact is not None:
            verdict = (
                "untried"
                if trial_id is None
                else self._trials.wait(trial_id, cancelled=lambda: context.cancelled)
            )
            context.check_cancelled()
            if isinstance(verdict, TrialFailure):
                # Only its kind and the stage: what a scene says is not logged (ADR-029).
                logger.info(
                    "generation.figure_failed_trial kind=%s stage=%s", figure.kind, verdict.stage
                )
            else:
                try:
                    self._lessons.settle_scene(
                        lesson_id,
                        figure.scene_id,
                        {"purpose": artifact.purpose, "source": artifact.source},
                    )
                    return True
                except (SceneRejectedError, LessonInvalidError, ValidationError) as error:
                    logger.info(
                        "generation.figure_unattached kind=%s error=%s",
                        figure.kind,
                        type(error).__name__,
                    )
        self._lessons.settle_scene(lesson_id, figure.scene_id, None)
        return False

    def _try_in_player(self, artifact: SceneArtifact, context: JobContext) -> TrialFailure | None:
        """Run a picture in the app's player before it is kept, if the app is there to.

        The verdict, or None when it ran, or when it could not be tried: the app was not
        asking for trials, or did not answer in time. An untried picture is kept as pictures
        were before trials, and the player says it in words if it fails.
        """
        if not self._trials.present():
            return None
        trial_id = self._trials.offer(
            scene_class=artifact.scene_class,
            source=artifact.source,
            interactive=artifact.interactive,
            controls=tuple(artifact.controls),
        )
        verdict = self._trials.wait(trial_id, cancelled=lambda: context.cancelled)
        context.check_cancelled()
        if verdict == "untried":
            logger.info("generation.scene_untried")
        return verdict if isinstance(verdict, TrialFailure) else None

    # -- a question the learner asks in the middle of a lesson -------------------

    def ask(self, lesson_id: str, segment_id: str, question: str) -> JobSnapshot:
        """Start a job that answers something the learner asked about one part of a lesson."""
        words = " ".join(question.split())
        if not MIN_QUESTION_CHARACTERS <= len(words) <= MAX_QUESTION_CHARACTERS:
            raise ValidationFailedError(
                f"A question must be {MIN_QUESTION_CHARACTERS} to {MAX_QUESTION_CHARACTERS} "
                "characters long."
            )
        lesson = self._lessons.get_lesson(lesson_id)
        if not any(segment.id == segment_id for segment in lesson.segments):
            raise NotFoundError("That is not a part of this lesson.")
        if self._asks.count(lesson_id) >= MAX_ASKS_PER_LESSON:
            raise ConflictError(
                f"This lesson already has {MAX_ASKS_PER_LESSON} saved questions. Remove one "
                "before asking another."
            )
        self._require_key()
        with self._starting:
            if self._jobs.find_active(KIND_ASK, lesson_id) is not None:
                raise ConflictError(
                    "Your last question is still being answered. Wait for it, or stop it first."
                )
            return self._jobs.submit(
                KIND_ASK,
                lambda context: self._answer(lesson_id, segment_id, words, context),
                course_id=lesson.course_id,
                subject_id=lesson_id,
                lane=LANE_QUICK,
            )

    def _answer(
        self, lesson_id: str, segment_id: str, question: str, context: JobContext
    ) -> dict[str, Any]:
        lesson = self._lessons.get_lesson(lesson_id)
        index = next(
            (place for place, segment in enumerate(lesson.segments) if segment.id == segment_id),
            None,
        )
        if index is None:
            raise NotFoundError("That is not a part of this lesson.")
        segment = lesson.segments[index]
        concept_id = lesson.concept_ids[0]
        with self._database.read() as session:
            course_title = get_course_or_404(session, lesson.course_id).title
            concept_row = get_concept_or_404(session, concept_id)
            concept = prompts.ConceptBrief(
                title=concept_row.title,
                summary=concept_row.summary or "",
                objectives=[],
                prerequisites=[],
            )
            answered = isinstance(segment, CheckpointSegment) and (
                session.scalars(
                    select(Attempt.id)
                    # A skip counts: it showed the explanation, so there is nothing
                    # left to keep from the learner (the same rule as when an answer is
                    # judged, in `AssessmentService.answer`).
                    .where(
                        Attempt.lesson_id == lesson_id,
                        Attempt.question_id == segment.question.id,
                    )
                    .limit(1)
                ).first()
                is not None
            )
        # Looked up by the learner's own words, so the answer can use their materials.
        stored = self._retriever.retrieve(
            lesson.course_id, f"{question} {segment.title}", limit=prompts.MAX_ASK_PASSAGES
        )
        passages = [
            prompts.Passage(
                source_name=passage.source_name, locator=_locator(passage), text=passage.text
            )
            for passage in stored
        ]
        citable = [
            PassageRef(
                source_id=passage.source_id,
                section_id=passage.section_id,
                source_name=_citable(passage.source_name),
                locator=_citable(_locator(passage)),
            )
            for passage in stored
        ]
        part = _part_brief(lesson, index, answered=answered)

        problems: list[str] = []
        for attempt in (1, 2):
            context.check_cancelled()
            doing = (
                "Answering your question"
                if attempt == 1
                else "The first answer wasn’t usable. Asking once more"
            )
            context.report(0, 0, doing)
            request = prompts.ask_request(
                course_title=course_title,
                concept=concept,
                lesson_title=lesson.title,
                part_titles=[item.title for item in lesson.segments],
                part=part,
                question=question,
                passages=passages,
                problems=problems,
            )
            result = self._ask(request, context, attempt - 1, 2, doing)
            try:
                compiled = compile_answer(result.text, citable)
            except DraftError as error:
                logger.info("generation.answer_unusable attempt=%s", attempt)
                problems = error.problems
                continue
            written_by = self._written_by([result])
            kept = self._asks.store(
                lesson_id=lesson_id,
                segment_id=segment_id,
                question=question,
                paragraphs=compiled.paragraphs,
                citations=[
                    AskCitation(source_name=item.source_name, locator=item.locator)
                    for item in compiled.citations
                ],
                written_by=written_by,
            )
            context.report(2, 2, "Done")
            return {
                "kind": KIND_ASK,
                "ask_id": kept.id,
                "lesson_id": lesson_id,
                "segment_id": segment_id,
                "written_by": written_by,
            }
        raise GenerationFailedError(
            "The answer wasn’t usable, twice. Nothing was saved. Try asking again, perhaps in "
            "other words."
        )

    # -- finding out whether a key works -----------------------------------------

    def check_provider(self, provider_id: str) -> JobSnapshot:
        """Start a job that sends one provider a request of a few words, to see it answer."""
        if not self._gateway.knows(provider_id):
            raise NotFoundError("Unknown AI provider.")
        if not self._gateway.has_key_for(provider_id):
            raise ProviderKeyMissingError
        with self._starting:
            running = self._jobs.find_active(KIND_CHECK, provider_id)
            if running is not None:
                return running
            return self._jobs.submit(
                KIND_CHECK,
                lambda context: self._check(provider_id, context),
                subject_id=provider_id,
                lane=LANE_QUICK,
            )

    def key_changed(self, provider_id: str) -> None:
        """A provider's key was set or removed: a check that is under way is about the old one.

        Stopped, so that it is not taken for a check of the new key, and so that what it
        finds is not held against the new key.
        """
        running = self._jobs.find_active(KIND_CHECK, provider_id)
        if running is not None:
            self._jobs.cancel(running.id)

    def _check(self, provider_id: str, context: JobContext) -> dict[str, Any]:
        doing = "Testing the key"
        context.report(0, 0, doing)
        began = time.monotonic()
        result = self._ask(prompts.check_request(), context, 0, 1, doing, provider_id=provider_id)
        seconds = time.monotonic() - began
        context.report(1, 1, "Done")
        return {
            "kind": KIND_CHECK,
            "provider_id": provider_id,
            "provider": result.provider_name,
            "model": result.model_name,
            "seconds": round(seconds, 1),
            "note": self._written_by([result])["note"],
        }
