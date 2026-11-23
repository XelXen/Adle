"""What to do next, how a course is going, and practice.

This service gathers what is recorded about a course (states, lessons, answers,
what the learner set aside or said did not help) into the plain values the
rules in ``learner_model`` decide on, and turns their decisions into records
for the interface. Nothing is decided here: which step, which questions, and
what a pattern of answers means are all decided by pure functions that can be
read and tested on their own.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from adle_core.application.courses import get_course_or_404
from adle_core.application.curriculum import (
    ConceptRecord,
    CurriculumService,
    KnowledgeRecord,
    get_concept_or_404,
)
from adle_core.application.evidence import (
    EVENT_DISMISSED,
    EVENT_LESSON_COMPLETED,
    EVENT_UNHELPFUL,
    EVENT_UNHELPFUL_WITHDRAWN,
    events_by_concept,
    standing_reports,
)
from adle_core.application.learner import LearnerService
from adle_core.errors import ConflictError, NotFoundError, ValidationFailedError
from adle_core.evaluation.scoring import reveals
from adle_core.generation.credentials import CredentialVault
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import (
    Attempt,
    LearnerConceptState,
    LearnerEvent,
    LearnerObservation,
    StoredLesson,
)
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.mastery import STATE_LABELS, MasteryState
from adle_core.learner_model.misconceptions import (
    KIND_LABELS,
    Dismissal,
    Hypothesis,
    blocks_mastery,
    fold,
    needing_a_check,
)
from adle_core.learner_model.next_step import (
    ConceptStatus,
    LessonStatus,
    Plan,
    Step,
    plan,
    practice_purpose,
)
from adle_core.learner_model.practice import (
    DEFAULT_COUNT,
    Need,
    PoolItem,
    choose,
    fresh_items,
    next_fresh_at,
)
from adle_core.learner_model.sitting import Activity, ConceptNow, Sitting, latest_sitting
from adle_core.learner_model.tracing import Observation, ObservationKind
from adle_core.lessons.ir import SCHEMA_VERSION, AssessmentItem, Lesson
from adle_core.lessons.player import ItemMask, PlayerQuestion, player_question

#: How many of a concept's latest answers the policy looks at for "how is it going".
RECENT_ANSWERS = 8
MAX_PRACTICE_QUESTIONS = 5
#: How far back the latest sitting is looked for. Far more than one sitting holds; without
#: a bound, every look at a course would read every answer ever given in it.
SITTING_LOOKBACK = 600


@dataclass(frozen=True, slots=True)
class StepRecord:
    kind: str
    #: What the button says.
    title: str
    #: Why this step, in a sentence or two.
    reason: str
    concept_id: str | None
    lesson_id: str | None
    #: The kind of mistake a check is about, when it is about one.
    about: str | None
    #: The step needs the AI provider and no key is set up.
    needs_key: bool


@dataclass(frozen=True, slots=True)
class PlanRecord:
    recommended: StepRecord
    alternatives: list[StepRecord]
    note: str | None


@dataclass(frozen=True, slots=True)
class HypothesisRecord:
    kind: str
    status: str
    #: Where it stands, in a sentence for the learner.
    description: str
    is_slip: bool
    #: Still open, so the learner can say it does not describe them.
    can_dismiss: bool


@dataclass(frozen=True, slots=True)
class ConceptProgressRecord:
    concept_id: str
    title: str
    knowledge: KnowledgeRecord
    lessons_total: int
    lessons_completed: int
    hypotheses: list[HypothesisRecord]
    #: Questions that could be asked now and would count as evidence.
    fresh_questions: int
    #: When a question that is being kept back becomes worth asking again.
    next_fresh_at: datetime | None
    review_due: bool


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    concepts: int
    demonstrated: int
    #: Building understanding, or needing more evidence.
    in_progress: int
    not_assessed: int
    reviews_due: int
    next_review_at: datetime | None


@dataclass(frozen=True, slots=True)
class SessionShownRecord:
    concept_id: str
    title: str
    #: Right answers in the sitting, and how many of them count in full.
    right: int
    right_unaided: int
    demonstrated: bool


@dataclass(frozen=True, slots=True)
class SessionNeededRecord:
    concept_id: str
    title: str
    #: Where the concept stands, in the words used everywhere else.
    label: str
    missing: list[str]


@dataclass(frozen=True, slots=True)
class SessionReviewRecord:
    concept_id: str
    title: str
    due_at: datetime


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """The latest sitting on a course and what it showed. Counts and words; no score."""

    started_at: datetime
    ended_at: datetime
    #: The learner may still be in it. Otherwise it is "last time".
    current: bool
    lessons_completed: int
    answered: int
    shown: list[SessionShownRecord]
    still_needed: list[SessionNeededRecord]
    reviews: list[SessionReviewRecord]


@dataclass(frozen=True, slots=True)
class LearningOverview:
    course_id: str
    plan: PlanRecord
    #: In an order that respects what each concept needs first.
    concepts: list[ConceptProgressRecord]
    summary: ProgressSummary
    #: The latest sitting, or ``None`` if nothing has been done on the course yet.
    session: SessionRecord | None


@dataclass(frozen=True, slots=True)
class PracticeQuestionRecord:
    #: The lesson the question belongs to; answers are sent there.
    lesson_id: str
    question: PlayerQuestion


@dataclass(frozen=True, slots=True)
class PracticeSetRecord:
    course_id: str
    concept_id: str
    concept_title: str
    #: ``review``, ``check``, or ``practise``.
    purpose: str
    #: Why these questions, or why there are none right now.
    reason: str
    questions: list[PracticeQuestionRecord]
    #: When there will be something to ask, if nothing can be asked now.
    next_fresh_at: datetime | None


@dataclass(slots=True)
class _Picture:
    """One concept, as the rules need to see it."""

    record: ConceptRecord
    status: ConceptStatus
    pool: list[PoolItem] = field(default_factory=list)
    need: Need = field(default_factory=Need)
    items: dict[tuple[str, str], AssessmentItem] = field(default_factory=dict)


def _step_record(step: Step) -> StepRecord:
    return StepRecord(
        kind=step.kind.value,
        title=step.title,
        reason=step.reason,
        concept_id=step.concept_id,
        lesson_id=step.lesson_id,
        about=step.about,
        needs_key=step.needs_key,
    )


def _plan_record(decided: Plan) -> PlanRecord:
    return PlanRecord(
        recommended=_step_record(decided.recommended),
        alternatives=[_step_record(step) for step in decided.alternatives],
        note=decided.note,
    )


def _hypothesis_record(hypothesis: Hypothesis) -> HypothesisRecord:
    return HypothesisRecord(
        kind=hypothesis.kind,
        status=hypothesis.status.value,
        description=hypothesis.describe(),
        is_slip=hypothesis.is_slip,
        can_dismiss=hypothesis.is_open,
    )


def _session_record(sitting: Sitting | None) -> SessionRecord | None:
    if sitting is None:
        return None
    return SessionRecord(
        started_at=sitting.started_at,
        ended_at=sitting.ended_at,
        current=sitting.current,
        lessons_completed=sitting.lessons_completed,
        answered=sitting.answered,
        shown=[
            SessionShownRecord(
                concept_id=line.concept_id,
                title=line.title,
                right=line.right,
                right_unaided=line.right_unaided,
                demonstrated=line.demonstrated,
            )
            for line in sitting.shown
        ],
        still_needed=[
            SessionNeededRecord(
                concept_id=line.concept_id,
                title=line.title,
                label=STATE_LABELS[line.state],
                missing=list(line.missing),
            )
            for line in sitting.still_needed
        ],
        reviews=[
            SessionReviewRecord(concept_id=line.concept_id, title=line.title, due_at=line.due_at)
            for line in sitting.reviews
        ],
    )


def _read(row: StoredLesson) -> Lesson | None:
    """The stored lesson if this version can read it. An unreadable one has no questions to ask."""
    if row.schema_version != SCHEMA_VERSION:
        return None
    try:
        return Lesson.model_validate(row.document)
    except ValueError:
        return None


class LearningService:
    def __init__(
        self,
        database: Database,
        curriculum: CurriculumService,
        learner: LearnerService,
        credentials: CredentialVault,
        mask: ItemMask,
    ) -> None:
        self._database = database
        self._curriculum = curriculum
        self._learner = learner
        self._credentials = credentials
        self._mask = mask

    # -- gathering -----------------------------------------------------------

    def _pictures(self, session: Session, course_id: str, now: datetime) -> list[_Picture]:
        """Every concept of the course, in learning order, with what the rules need."""
        curriculum = self._curriculum.get(course_id)
        records = {record.id: record for record in curriculum.concepts}
        # While the graph has a loop there is no learning order; the learner's own is used.
        order = curriculum.learning_order or [record.id for record in curriculum.concepts]

        states = {
            state.concept_id: state
            for state in session.scalars(
                select(LearnerConceptState).where(LearnerConceptState.course_id == course_id)
            )
        }
        attempts = session.scalars(
            select(Attempt).where(Attempt.course_id == course_id).order_by(Attempt.id)
        ).all()
        events = session.scalars(
            select(LearnerEvent)
            .where(
                LearnerEvent.course_id == course_id,
                LearnerEvent.kind.in_(
                    (EVENT_DISMISSED, EVENT_UNHELPFUL, EVENT_UNHELPFUL_WITHDRAWN)
                ),
            )
            .order_by(LearnerEvent.id)
        ).all()
        lessons = session.scalars(
            select(StoredLesson)
            .where(StoredLesson.course_id == course_id)
            .order_by(StoredLesson.created_at, StoredLesson.id)
            .options(selectinload(StoredLesson.progress))
        ).all()

        scored = [attempt for attempt in attempts if attempt.outcome != Outcome.SKIPPED.value]
        last_answer: dict[tuple[str, str], Attempt] = {}
        recent: dict[str, list[Outcome]] = defaultdict(list)
        for attempt in scored:
            last_answer[(attempt.lesson_id, attempt.question_id)] = attempt
            recent[attempt.concept_id].append(Outcome(attempt.outcome))
        folded = events_by_concept(attempts, events)

        lesson_statuses: dict[str, list[LessonStatus]] = defaultdict(list)
        pools: dict[str, list[PoolItem]] = defaultdict(list)
        items: dict[str, dict[tuple[str, str], AssessmentItem]] = defaultdict(dict)
        newest_lesson_at: dict[str, datetime] = {}
        taken_up_at: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
        for row in lessons:
            lesson = _read(row)
            taught = lesson.concept_ids if lesson is not None else [row.concept_id]
            progress = row.progress
            lesson_status = LessonStatus(
                id=row.id,
                title=row.title,
                started=progress is not None,
                completed=progress is not None and progress.completed,
                touched_at=progress.updated_at if progress is not None else None,
                added_at=row.created_at,
            )
            for concept_id in taught:
                lesson_statuses[concept_id].append(lesson_status)
                newest_lesson_at[concept_id] = max(
                    newest_lesson_at.get(concept_id, row.created_at), row.created_at
                )
                if progress is not None:
                    taken_up_at[concept_id].append((row.id, progress.updated_at))
            if lesson is None:
                continue
            for item in lesson.all_questions():
                last = last_answer.get((row.id, item.id))
                pools[item.concept_id].append(
                    PoolItem(
                        lesson_id=row.id,
                        question_id=item.id,
                        form=item.form,
                        is_transfer=item.is_transfer,
                        difficulty=item.difficulty,
                        reveals=reveals(item),
                        last_answered_at=last.created_at if last is not None else None,
                        last_outcome=Outcome(last.outcome) if last is not None else None,
                    )
                )
                items[item.concept_id][(row.id, item.id)] = item

        # The newest report about each concept that the learner has not taken back.
        unhelpful: dict[str, LearnerEvent] = {}
        for event in standing_reports(events):
            if event.concept_id is not None:
                unhelpful[event.concept_id] = event

        pictures: list[_Picture] = []
        for concept_id in order:
            record = records.get(concept_id)
            if record is None:
                continue
            state = states.get(concept_id)
            pool = pools.get(concept_id, [])
            fresh = fresh_items(pool, now)
            hypotheses = fold(folded.get(concept_id, []))
            status = ConceptStatus(
                id=record.id,
                title=record.title,
                prerequisites=tuple(item.concept_id for item in record.prerequisites),
                state=MasteryState(record.knowledge.state),
                missing=tuple(record.knowledge.missing),
                answered=record.knowledge.answered,
                claims_familiarity=record.knowledge.self_report == "confident",
                review_due_at=record.knowledge.review_due_at,
                lessons=tuple(lesson_statuses.get(concept_id, ())),
                fresh_questions=len(fresh),
                checkable=frozenset(kind for item in fresh for kind in item.reveals),
                hypotheses=tuple(hypotheses.values()),
                recent=tuple(recent.get(concept_id, ())[-RECENT_ANSWERS:]),
                asked_for_another=self._still_asking(
                    unhelpful.get(concept_id),
                    newest_lesson_at.get(concept_id),
                    taken_up_at.get(concept_id, ()),
                    [attempt for attempt in scored if attempt.concept_id == concept_id],
                ),
            )
            need = Need(
                forms_correct=frozenset(state.forms_correct) if state is not None else frozenset(),
                transfer_correct=state.transfer_correct if state is not None else 0,
                to_check=tuple(item.kind for item in needing_a_check(hypotheses.values())),
            )
            pictures.append(
                _Picture(
                    record=record,
                    status=status,
                    pool=pool,
                    need=need,
                    items=items.get(concept_id, {}),
                )
            )
        return pictures

    @staticmethod
    def _activities(session: Session, course_id: str) -> list[Activity]:
        """What the learner did on the course lately: answers, skips, lessons finished.

        Read from the observations, which are what was counted as evidence: an answer
        there is "hinted" if it was a repeat of a question answered moments before, and
        "unsure" if the learner marked their own explanation. So an answer that counts
        in full here is exactly one that counts in full for the state of a concept.
        """
        answers = session.execute(
            select(
                LearnerObservation.occurred_at,
                LearnerObservation.concept_id,
                LearnerObservation.outcome,
                LearnerObservation.hinted,
                LearnerObservation.unsure,
            )
            .where(
                LearnerObservation.course_id == course_id,
                LearnerObservation.kind == ObservationKind.ANSWER.value,
            )
            .order_by(LearnerObservation.id.desc())
            .limit(SITTING_LOOKBACK)
        ).all()
        finished = session.execute(
            select(LearnerEvent.occurred_at, LearnerEvent.concept_id)
            .where(
                LearnerEvent.course_id == course_id,
                LearnerEvent.kind == EVENT_LESSON_COMPLETED,
                LearnerEvent.concept_id.is_not(None),
            )
            .order_by(LearnerEvent.id.desc())
            .limit(SITTING_LOOKBACK)
        ).all()
        activities = [
            Activity(
                at=occurred_at,
                concept_id=concept_id,
                answered=outcome != Outcome.SKIPPED.value,
                right=outcome == Outcome.CORRECT.value,
                right_unaided=outcome == Outcome.CORRECT.value and not hinted and not unsure,
            )
            for occurred_at, concept_id, outcome, hinted, unsure in answers
        ]
        activities.extend(
            Activity(at=occurred_at, concept_id=concept_id, lesson_completed=True)
            for occurred_at, concept_id in finished
            if concept_id is not None
        )
        return activities

    @staticmethod
    def _still_asking(
        report: LearnerEvent | None,
        newest_lesson_at: datetime | None,
        taken_up: tuple[tuple[str, datetime], ...] | list[tuple[str, datetime]],
        answers: list[Attempt],
    ) -> bool:
        """Whether "this did not help" is still waiting for an answer.

        It has been answered once there is another explanation (a newer lesson, or a
        different one taken up since), or once the learner has answered a question on the
        concept correctly and without help since: then things are going well enough.
        """
        if report is None:
            return False
        said_at = report.occurred_at
        if newest_lesson_at is not None and newest_lesson_at > said_at:
            return False
        if any(
            lesson_id != report.lesson_id and touched > said_at for lesson_id, touched in taken_up
        ):
            return False
        return not any(
            attempt.created_at > said_at
            and attempt.outcome == Outcome.CORRECT.value
            and not attempt.hinted
            and not attempt.unsure
            for attempt in answers
        )

    # -- the next step and progress --------------------------------------------

    def overview(self, course_id: str, *, now: datetime | None = None) -> LearningOverview:
        moment = now or utc_now()
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            pictures = self._pictures(session, course_id, moment)
            activities = self._activities(session, course_id)

        sitting = latest_sitting(
            activities,
            [
                ConceptNow(
                    id=picture.status.id,
                    title=picture.status.title,
                    state=picture.status.state,
                    missing=picture.status.missing,
                    review_due_at=picture.status.review_due_at,
                )
                for picture in pictures
            ],
            moment,
        )
        decided = plan(
            [picture.status for picture in pictures],
            moment,
            can_generate=self._credentials.has_api_key,
        )
        concepts = [self._progress(picture, moment) for picture in pictures]
        upcoming = sorted(
            due
            for picture in pictures
            if (due := picture.status.review_due_at) is not None and due > moment
        )
        states = [picture.status.state for picture in pictures]
        return LearningOverview(
            course_id=course_id,
            plan=_plan_record(decided),
            concepts=concepts,
            summary=ProgressSummary(
                concepts=len(pictures),
                demonstrated=states.count(MasteryState.DEMONSTRATED),
                in_progress=states.count(MasteryState.BUILDING)
                + states.count(MasteryState.NEEDS_EVIDENCE),
                not_assessed=states.count(MasteryState.NOT_ASSESSED),
                reviews_due=sum(1 for concept in concepts if concept.review_due),
                next_review_at=upcoming[0] if upcoming else None,
            ),
            session=_session_record(sitting),
        )

    @staticmethod
    def _progress(picture: _Picture, now: datetime) -> ConceptProgressRecord:
        status = picture.status
        due = status.review_due_at
        # Open ones first, the most established at the top; settled ones after them.
        ordered = sorted(
            status.hypotheses,
            key=lambda item: (not item.is_open, not item.blocks_mastery, item.first_seen_at),
        )
        return ConceptProgressRecord(
            concept_id=status.id,
            title=status.title,
            knowledge=picture.record.knowledge,
            lessons_total=len(status.lessons),
            lessons_completed=sum(1 for lesson in status.lessons if lesson.completed),
            hypotheses=[_hypothesis_record(item) for item in ordered],
            fresh_questions=status.fresh_questions,
            next_fresh_at=next_fresh_at(picture.pool, now),
            review_due=due is not None and due <= now,
        )

    # -- practice --------------------------------------------------------------

    def start_practice(
        self,
        concept_id: str,
        *,
        about: str | None = None,
        count: int = DEFAULT_COUNT,
        now: datetime | None = None,
    ) -> PracticeSetRecord:
        """Questions worth asking about one concept right now, without their answers."""
        if about is not None and about not in KIND_LABELS:
            raise ValidationFailedError("That is not a kind of mistake Adle knows about.")
        if not 1 <= count <= MAX_PRACTICE_QUESTIONS:
            raise ValidationFailedError(
                f"A practice set has between 1 and {MAX_PRACTICE_QUESTIONS} questions."
            )
        moment = now or utc_now()
        with self._database.read() as session:
            concept = get_concept_or_404(session, concept_id)
            course_id = concept.course_id
            pictures = self._pictures(session, course_id, moment)
        picture = next((item for item in pictures if item.status.id == concept_id), None)
        if picture is None:
            raise NotFoundError("That concept no longer exists.")

        status = picture.status
        purpose, reason = practice_purpose(status, moment, about=about)
        need = picture.need
        if about is not None and about in {item.kind for item in status.hypotheses}:
            # What the learner chose to check comes before anything else worth checking.
            need = Need(
                forms_correct=need.forms_correct,
                transfer_correct=need.transfer_correct,
                to_check=(about, *(kind for kind in need.to_check if kind != about)),
            )
        chosen = choose(picture.pool, need, moment, count=count)
        waiting = next_fresh_at(picture.pool, moment)
        if not chosen:
            reason = (
                f"You answered every question on “{status.title}” in the last few hours. Asking "
                "again now would only test your memory of the answers."
                if picture.pool
                else f"No questions on “{status.title}” yet. A lesson will add some."
            )
        return PracticeSetRecord(
            course_id=course_id,
            concept_id=concept_id,
            concept_title=status.title,
            purpose=purpose.value,
            reason=reason,
            questions=[
                PracticeQuestionRecord(
                    lesson_id=item.lesson_id,
                    question=player_question(
                        picture.items[(item.lesson_id, item.question_id)],
                        item.lesson_id,
                        self._mask,
                    ),
                )
                for item in chosen
            ],
            next_fresh_at=waiting if not chosen else None,
        )

    # -- what the learner says ---------------------------------------------------

    def dismiss_hypothesis(
        self, concept_id: str, kind: str, *, now: datetime | None = None
    ) -> LearningOverview:
        """The learner says a suspected mistake does not describe them. It is set aside."""
        moment = now or utc_now()
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            course_id = concept.course_id
            attempts = session.scalars(
                select(Attempt).where(Attempt.concept_id == concept_id).order_by(Attempt.id)
            ).all()
            events = session.scalars(
                select(LearnerEvent)
                .where(
                    LearnerEvent.concept_id == concept_id,
                    LearnerEvent.kind == EVENT_DISMISSED,
                )
                .order_by(LearnerEvent.id)
            ).all()
            history = events_by_concept(attempts, events).get(concept_id, [])
            current = fold(history).get(kind)
            if current is None or not current.is_open:
                raise ConflictError("There is nothing like that to set aside any more.")
            session.add(
                LearnerEvent(
                    course_id=course_id,
                    concept_id=concept_id,
                    occurred_at=moment,
                    kind=EVENT_DISMISSED,
                    detail={"kind": kind},
                )
            )
            after = fold([*history, Dismissal(occurred_at=moment, kind=kind)])
            self._learner.record_in(
                session,
                concept,
                Observation(
                    kind=ObservationKind.DISMISSAL,
                    occurred_at=moment,
                    unresolved_misconception=blocks_mastery(after.values()),
                ),
            )
        return self.overview(course_id, now=moment)

    def report_unhelpful(
        self, lesson_id: str, segment_id: str, *, now: datetime | None = None
    ) -> None:
        """The learner says an explanation did not help. Recorded; nothing is held against them."""
        with self._database.session() as session:
            row = session.get(StoredLesson, lesson_id)
            if row is None:
                raise NotFoundError("That lesson no longer exists.")
            lesson = _read(row)
            if lesson is not None and segment_id not in {segment.id for segment in lesson.segments}:
                raise ValidationFailedError("That is not a part of this lesson.")
            session.add(
                LearnerEvent(
                    course_id=row.course_id,
                    concept_id=row.concept_id,
                    lesson_id=row.id,
                    occurred_at=now or utc_now(),
                    kind=EVENT_UNHELPFUL,
                    detail={"segment_id": segment_id},
                )
            )

    def withdraw_unhelpful(
        self, lesson_id: str, segment_id: str, *, now: datetime | None = None
    ) -> None:
        """The learner takes back "this did not help" about a part: it was said by mistake.

        Nothing is removed (ADR-054): the withdrawal is a row of its own, after the report.
        With nothing about that part left to take back, nothing is written."""
        with self._database.session() as session:
            row = session.get(StoredLesson, lesson_id)
            if row is None:
                raise NotFoundError("That lesson no longer exists.")
            if segment_id not in self._reported_parts(session, lesson_id):
                return
            session.add(
                LearnerEvent(
                    course_id=row.course_id,
                    concept_id=row.concept_id,
                    lesson_id=row.id,
                    occurred_at=now or utc_now(),
                    kind=EVENT_UNHELPFUL_WITHDRAWN,
                    detail={"segment_id": segment_id},
                )
            )

    def unhelpful_parts(self, lesson_id: str) -> list[str]:
        """The parts of a lesson the learner said did not help and has not taken back."""
        with self._database.read() as session:
            return self._reported_parts(session, lesson_id)

    @staticmethod
    def _reported_parts(session: Session, lesson_id: str) -> list[str]:
        events = session.scalars(
            select(LearnerEvent).where(
                LearnerEvent.lesson_id == lesson_id,
                LearnerEvent.kind.in_((EVENT_UNHELPFUL, EVENT_UNHELPFUL_WITHDRAWN)),
            )
        ).all()
        parts = (report.detail.get("segment_id") for report in standing_reports(events))
        return list(dict.fromkeys(part for part in parts if isinstance(part, str)))
