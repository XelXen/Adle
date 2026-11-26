"""The learner: their preferences, and what the evidence says they know.

Knowledge is stored as structured records, never as vectors (PLAN.md 8.1). The
record of what happened (``learner_observations``) is the source of truth; the
per-concept state is derived from it and can be rebuilt at any time.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from adle_core.lessons import character as lesson_character

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
        slip=row.slip,
        self_report=SelfReport(row.self_report) if row.self_report else None,
        unresolved_misconception=row.unresolved_misconception,
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
        unresolved_misconception=state.unresolved_misconception,
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
    state.unresolved_misconception = knowledge.unresolved_misconception
    state.review_interval_days = knowledge.review.interval_days
    state.review_due_at = knowledge.review.due_at
    state.review_streak = knowledge.review.streak


class LearnerService:
    def __init__(self, database: Database, config: TracingConfig = DEFAULT_CONFIG) -> None:
        self._database = database
        self._config = config

    # -- preferences -------------------------------------------------------

    def get_preferences(self) -> LearnerPreferences:
        with self._database.read() as session:
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
        voice: str | None = None,
        volume: int | None = None,
        character: str | None = None,
        character_parts: Mapping[str, str] | None = None,
        character_follows_voice: bool | None = None,
    ) -> LearnerPreferences:
        """Change the preferences that are given and return them all.

        A teacher is one or the other (ADR-071): given in words, its parts are let go; given
        by its parts, the words are."""
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
            if voice is not None:
                # A voice is named by the computer it is on; the name is kept as given.
                updated = replace(updated, voice=voice.strip())
            if volume is not None:
                updated = replace(updated, volume=volume)
            if character_parts is not None:
                try:
                    parts = lesson_character.checked(character_parts)
                except lesson_character.UnknownPartError as error:
                    raise ValidationFailedError("That is not a part of a teacher.") from error
                updated = replace(updated, character_parts=parts, character="")
            if character is not None:
                tidy = " ".join(character.split())
                if len(tidy) > lesson_character.MAX_CHARACTER_LENGTH:
                    raise ValidationFailedError(
                        "A teacher can be described in at most 300 characters."
                    )
                updated = replace(updated, character=tidy)
                if tidy:
                    updated = replace(updated, character_parts={})
            if character_follows_voice is not None:
                updated = replace(updated, character_follows_voice=character_follows_voice)
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
            return self.record_in(session, concept, observation)

    def record_in(
        self,
        session: Session,
        concept: Concept,
        observation: Observation,
        *,
        note: str | None = None,
    ) -> Transition:
        """Record inside a transaction the caller owns, so more can be stored with it.

        ``note`` is a sentence for the explanation that only the caller can know.
        """
        state = session.get(LearnerConceptState, concept.id)
        transition = apply(_to_knowledge(state, self._config), observation, self._config, note=note)
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
                slip=observation.slip,
                self_report=observation.self_report.value if observation.self_report else None,
                unresolved_misconception=observation.unresolved_misconception,
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

    def replay(self, course_id: str, shown: Sequence[tuple[str, Observation]]) -> int:
        """Record what a learner showed somewhere else, in the order given (a course
        brought in from a file, ADR-063): each observation is recorded as any other is,
        so every state and every sentence is worked out here, from the observations,
        and nothing is taken from what a file says a learner knows. One for a concept
        that is not in the course is passed over. Returns how many were recorded."""
        recorded = 0
        with self._database.session() as session:
            concepts = {
                concept.id: concept
                for concept in session.scalars(
                    select(Concept).where(Concept.course_id == course_id)
                )
            }
            for concept_id, observation in shown:
                concept = concepts.get(concept_id)
                if concept is None:
                    continue
                self.record_in(session, concept, observation)
                # The next one of this concept reads the state this one left.
                session.flush()
                recorded += 1
        return recorded

    def self_rate(self, concept_id: str, level: SelfReport) -> ConceptEvidenceRecord:
        """Record how well the learner says they already know a concept."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            self.record_in(
                session,
                concept,
                Observation(
                    kind=ObservationKind.SELF_REPORT, occurred_at=utc_now(), self_report=level
                ),
            )
            session.flush()
            return self._evidence(session, concept.id)

    def concept_evidence(self, concept_id: str) -> ConceptEvidenceRecord:
        with self._database.read() as session:
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
