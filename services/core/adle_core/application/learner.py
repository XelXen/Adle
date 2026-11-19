"""The learner: their preferences, and what the evidence says they know.

Knowledge is stored as structured records, never as vectors (PLAN.md 8.1). The
record of what happened (``learner_observations``) is the source of truth; the
per-concept state is derived from it and can be rebuilt at any time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from adle_core.application.curriculum import (
    KnowledgeRecord,
    get_concept_or_404,
    knowledge_record,
)
from adle_core.errors import ValidationFailedError
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import (
    Concept,
    LearnerConceptState,
    LearnerObservation,
    LearnerPreference,
)
from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.preferences import (
    MAX_GOAL_LENGTH,
    ExplanationDensity,
    LearnerPreferences,
    Pace,
    from_stored,
)
from adle_core.learner_model.review import ReviewState
from adle_core.learner_model.tracing import (
    DEFAULT_CONFIG,
    ConceptKnowledge,
    Observation,
    ObservationKind,
    SelfReport,
    TracingConfig,
    Transition,
    apply,
    initial_knowledge,
)

#: How many past observations the interface is shown for one concept.
HISTORY_LIMIT = 50


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    id: int
    occurred_at: datetime
    kind: str
    state_before: str
    state_after: str
    #: What happened and what it means, in words for the learner.
    explanation: str


@dataclass(frozen=True, slots=True)
class ConceptEvidenceRecord:
    concept_id: str
    knowledge: KnowledgeRecord
    #: Newest first.
    history: list[ObservationRecord]


def _to_observation(row: LearnerObservation) -> Observation:
    return Observation(
        kind=ObservationKind(row.kind),
        occurred_at=row.occurred_at,
        outcome=Outcome(row.outcome) if row.outcome else None,
        question_form=row.question_form,
        is_transfer=row.is_transfer,
        hinted=row.hinted,
        unsure=row.unsure,
        item_guess=row.item_guess,
        self_report=SelfReport(row.self_report) if row.self_report else None,
    )


def _to_knowledge(state: LearnerConceptState | None, config: TracingConfig) -> ConceptKnowledge:
    if state is None:
        return initial_knowledge(config)
    return ConceptKnowledge(
        probability=state.probability,
        answered=state.answered,
        correct=state.correct,
        unaided_correct=state.unaided_correct,
        hinted=state.hinted,
        skipped=state.skipped,
        forms_correct=frozenset(state.forms_correct),
        transfer_correct=state.transfer_correct,
        self_report=SelfReport(state.self_report) if state.self_report else None,
        last_observed_at=state.last_observed_at,
        review=ReviewState(
            interval_days=state.review_interval_days,
            due_at=state.review_due_at,
            streak=state.review_streak,
        ),
    )


def _store_knowledge(
    state: LearnerConceptState, knowledge: ConceptKnowledge, transition: Transition
) -> None:
    state.probability = knowledge.probability
    state.state = transition.state_after.value
    state.missing = list(transition.assessment.missing)
    state.answered = knowledge.answered
    state.correct = knowledge.correct
    state.unaided_correct = knowledge.unaided_correct
    state.hinted = knowledge.hinted
    state.skipped = knowledge.skipped
    state.forms_correct = sorted(knowledge.forms_correct)
    state.transfer_correct = knowledge.transfer_correct
    state.self_report = knowledge.self_report.value if knowledge.self_report else None
    state.last_observed_at = knowledge.last_observed_at
    state.review_interval_days = knowledge.review.interval_days
    state.review_due_at = knowledge.review.due_at
    state.review_streak = knowledge.review.streak


class LearnerService:
    def __init__(self, database: Database, config: TracingConfig = DEFAULT_CONFIG) -> None:
        self._database = database
        self._config = config

    # -- preferences -------------------------------------------------------

    def get_preferences(self) -> LearnerPreferences:
        with self._database.session() as session:
            return self._preferences(session)

    @staticmethod
    def _preferences(session: Session) -> LearnerPreferences:
        stored = {row.key: row.value for row in session.scalars(select(LearnerPreference))}
        return from_stored(stored)

    def update_preferences(
        self,
        *,
        pace: Pace | None = None,
        explanation_density: ExplanationDensity | None = None,
        narration: bool | None = None,
        captions: bool | None = None,
        goal: str | None = None,
    ) -> LearnerPreferences:
        """Change the preferences that are given and return them all."""
        with self._database.session() as session:
            updated = self._preferences(session)
            if pace is not None:
                updated = replace(updated, pace=pace)
            if explanation_density is not None:
                updated = replace(updated, explanation_density=explanation_density)
            if narration is not None:
                updated = replace(updated, narration=narration)
            if captions is not None:
                updated = replace(updated, captions=captions)
            if goal is not None:
                tidy = " ".join(goal.split())
                if len(tidy) > MAX_GOAL_LENGTH:
                    raise ValidationFailedError(
                        f"A goal can be at most {MAX_GOAL_LENGTH} characters."
                    )
                updated = replace(updated, goal=tidy)
            current = {row.key: row for row in session.scalars(select(LearnerPreference))}
            for key, value in updated.to_stored().items():
                if key in current:
                    current[key].value = value
                else:
                    session.add(LearnerPreference(key=key, value=value))
            return updated

    # -- evidence ----------------------------------------------------------

    def record(self, concept_id: str, observation: Observation) -> Transition:
        """Store one observation and the change it causes, in one transaction."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            return self._record(session, concept, observation)

    def _record(self, session: Session, concept: Concept, observation: Observation) -> Transition:
        state = session.get(LearnerConceptState, concept.id)
        transition = apply(_to_knowledge(state, self._config), observation, self._config)
        session.add(
            LearnerObservation(
                concept_id=concept.id,
                course_id=concept.course_id,
                occurred_at=observation.occurred_at,
                kind=observation.kind.value,
                outcome=observation.outcome.value if observation.outcome else None,
                question_form=observation.question_form,
                is_transfer=observation.is_transfer,
                hinted=observation.hinted,
                unsure=observation.unsure,
                item_guess=observation.item_guess,
                self_report=observation.self_report.value if observation.self_report else None,
                state_before=transition.state_before.value,
                state_after=transition.state_after.value,
                explanation=transition.explanation,
                config_version=self._config.version,
            )
        )
        if state is None:
            state = LearnerConceptState(
                concept_id=concept.id,
                course_id=concept.course_id,
                probability=transition.after.probability,
                state=transition.state_after.value,
            )
            session.add(state)
        _store_knowledge(state, transition.after, transition)
        return transition

    def self_rate(self, concept_id: str, level: SelfReport) -> ConceptEvidenceRecord:
        """Record how well the learner says they already know a concept."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            self._record(
                session,
                concept,
                Observation(
                    kind=ObservationKind.SELF_REPORT, occurred_at=utc_now(), self_report=level
                ),
            )
            session.flush()
            return self._evidence(session, concept.id)

    def concept_evidence(self, concept_id: str) -> ConceptEvidenceRecord:
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            return self._evidence(session, concept.id)

    @staticmethod
    def _evidence(session: Session, concept_id: str) -> ConceptEvidenceRecord:
        rows = session.scalars(
            select(LearnerObservation)
            .where(LearnerObservation.concept_id == concept_id)
            .order_by(LearnerObservation.id.desc())
            .limit(HISTORY_LIMIT)
        )
        return ConceptEvidenceRecord(
            concept_id=concept_id,
            knowledge=knowledge_record(session.get(LearnerConceptState, concept_id)),
            history=[
                ObservationRecord(
                    id=row.id,
                    occurred_at=row.occurred_at,
                    kind=row.kind,
                    state_before=row.state_before,
                    state_after=row.state_after,
                    explanation=row.explanation,
                )
                for row in rows
            ],
        )

    def rebuild(self, concept_id: str) -> ConceptKnowledge:
        """Recompute a concept's state from its observations and store the result.

        The stored state is a convenience; this is what makes it disposable.
        """
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            rows = session.scalars(
                select(LearnerObservation)
                .where(LearnerObservation.concept_id == concept_id)
                .order_by(LearnerObservation.id)
            ).all()
            state = session.get(LearnerConceptState, concept_id)
            knowledge = initial_knowledge(self._config)
            transition: Transition | None = None
            for row in rows:
                transition = apply(knowledge, _to_observation(row), self._config)
                knowledge = transition.after
            if transition is None:
                if state is not None:
                    session.delete(state)
                return knowledge
            if state is None:
                state = LearnerConceptState(
                    concept_id=concept.id,
                    course_id=concept.course_id,
                    probability=knowledge.probability,
                    state=transition.state_after.value,
                )
                session.add(state)
            _store_knowledge(state, knowledge, transition)
            return knowledge
