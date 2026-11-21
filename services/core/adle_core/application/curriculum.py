"""A course's curriculum: what there is to learn, in what order, and where it comes from.

Every write goes through the rules in ``adle_core.curriculum.graph``. A change
that would leave the course without a learning order (a loop, a prerequisite
that does not exist) is refused with an explanation, so the stored graph is
always one that can be learned. Reading validates again and reports anything
found, because data can also change underneath (a source is removed).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from adle_core.application.courses import get_course_or_404
from adle_core.application.retrieval import Passage, Retriever
from adle_core.curriculum.graph import (
    ConceptNode,
    GraphError,
    Severity,
    find_cycles,
    has_errors,
    layers,
    learning_order,
    validate,
)
from adle_core.curriculum.outline import HeadingSection, clean_title, draft_outline
from adle_core.errors import ConflictError, NotFoundError, ValidationFailedError
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import (
    CONCEPT_TAGS,
    Concept,
    ConceptEdge,
    ConceptSourceRef,
    Course,
    LearnerConceptState,
    LearningObjective,
    Source,
    SourceSection,
)
from adle_core.ingestion.types import heading_leaf
from adle_core.learner_model.mastery import STATE_LABELS, MasteryState

MAX_CONCEPTS = 200
MAX_OBJECTIVES = 12
MAX_PREREQUISITES = 12
MAX_SOURCE_REFS = 24


@dataclass(frozen=True, slots=True)
class ObjectiveRecord:
    id: str
    statement: str


@dataclass(frozen=True, slots=True)
class PrerequisiteRecord:
    concept_id: str
    title: str
    #: Why this is needed first. Empty when nobody has said.
    reason: str


@dataclass(frozen=True, slots=True)
class SourceRefRecord:
    id: int
    source_id: str
    source_name: str
    section_id: str
    section_title: str | None
    page_number: int | None


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    """What Adle can say about the learner and one concept. No score, by design."""

    state: str
    label: str
    #: What is still needed before the concept counts as demonstrated.
    missing: list[str]
    answered: int
    self_report: str | None
    review_due_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConceptRecord:
    id: str
    course_id: str
    title: str
    summary: str
    position: int
    complexity: int
    tags: list[str]
    origin: str
    objectives: list[ObjectiveRecord]
    prerequisites: list[PrerequisiteRecord]
    source_refs: list[SourceRefRecord]
    #: Depth in the map: 0 needs nothing. ``None`` while the graph has a loop.
    layer: int | None
    knowledge: KnowledgeRecord


@dataclass(frozen=True, slots=True)
class IssueRecord:
    code: str
    severity: str
    concept_ids: list[str]
    message: str


@dataclass(frozen=True, slots=True)
class CurriculumRecord:
    course_id: str
    #: In the learner's own order.
    concepts: list[ConceptRecord]
    #: Concept ids in an order that respects every prerequisite. Empty while there is a loop.
    learning_order: list[str]
    issues: list[IssueRecord]
    #: There is at least one concept and nothing blocks a learning order.
    startable: bool


@dataclass(frozen=True, slots=True)
class ProposedConceptInput:
    """One concept of a proposal the learner accepted."""

    title: str
    summary: str
    objectives: Sequence[str]
    #: (position in the same list, reason). Only earlier positions are honoured.
    needs: Sequence[tuple[int, str]]
    section_ids: Sequence[str]


@dataclass(frozen=True, slots=True)
class OutlineCandidateRecord:
    section_id: str
    title: str
    source_id: str
    source_name: str


NOT_ASSESSED = KnowledgeRecord(
    state=MasteryState.NOT_ASSESSED.value,
    label=STATE_LABELS[MasteryState.NOT_ASSESSED],
    missing=["some answered questions"],
    answered=0,
    self_report=None,
    review_due_at=None,
)


def knowledge_record(state: LearnerConceptState | None) -> KnowledgeRecord:
    if state is None:
        return NOT_ASSESSED
    return KnowledgeRecord(
        state=state.state,
        label=STATE_LABELS[MasteryState(state.state)],
        missing=list(state.missing),
        answered=state.answered,
        self_report=state.self_report,
        review_due_at=state.review_due_at,
    )


def _tidy(text: str) -> str:
    return " ".join(text.split())


def get_concept_or_404(session: Session, concept_id: str) -> Concept:
    concept = session.get(Concept, concept_id)
    if concept is None:
        raise NotFoundError("That concept no longer exists.")
    return concept


class CurriculumService:
    def __init__(self, database: Database, retriever: Retriever) -> None:
        self._database = database
        self._retriever = retriever

    # -- reading -----------------------------------------------------------

    def get(self, course_id: str) -> CurriculumRecord:
        with self._database.read() as session:
            return self._load(session, get_course_or_404(session, course_id))

    def _concepts(self, session: Session, course_id: str) -> list[Concept]:
        return list(
            session.scalars(
                select(Concept)
                .where(Concept.course_id == course_id)
                .order_by(Concept.position, Concept.id)
                .options(
                    selectinload(Concept.objectives),
                    selectinload(Concept.prerequisite_links),
                    selectinload(Concept.source_refs).selectinload(ConceptSourceRef.source),
                    selectinload(Concept.source_refs).selectinload(ConceptSourceRef.section),
                )
            )
        )

    @staticmethod
    def _nodes(concepts: Sequence[Concept]) -> list[ConceptNode]:
        place = {concept.id: index for index, concept in enumerate(concepts)}
        return [
            ConceptNode(
                id=concept.id,
                title=concept.title,
                prerequisites=tuple(
                    sorted(
                        (link.prerequisite_id for link in concept.prerequisite_links),
                        key=lambda prerequisite_id: place.get(prerequisite_id, len(place)),
                    )
                ),
                objective_count=len(concept.objectives),
            )
            for concept in concepts
        ]

    def _load(self, session: Session, course: Course) -> CurriculumRecord:
        # Writes in this session may have changed rows behind loaded relationships.
        session.flush()
        session.expire_all()
        concepts = self._concepts(session, course.id)
        nodes = self._nodes(concepts)
        states = {
            state.concept_id: state
            for state in session.scalars(
                select(LearnerConceptState).where(LearnerConceptState.course_id == course.id)
            )
        }

        graph_issues = validate(nodes)
        issues = [
            IssueRecord(
                code=issue.code.value,
                severity=issue.severity.value,
                concept_ids=list(issue.concept_ids),
                message=issue.message,
            )
            for issue in graph_issues
        ]
        if course.origin == "materials":
            # A course built from the learner's materials should stay tied to them.
            issues.extend(
                IssueRecord(
                    code="no_source_reference",
                    severity=Severity.WARNING.value,
                    concept_ids=[concept.id],
                    message=f"“{concept.title}” isn’t linked to anything in your materials.",
                )
                for concept in concepts
                if not concept.source_refs
            )

        try:
            order = learning_order(nodes)
            depth: dict[str, int] = layers(nodes)
        except GraphError:
            order, depth = [], {}

        titles = {concept.id: concept.title for concept in concepts}
        prerequisites_of = {node.id: node.prerequisites for node in nodes}
        records = [
            ConceptRecord(
                id=concept.id,
                course_id=concept.course_id,
                title=concept.title,
                summary=concept.summary,
                position=index,
                complexity=concept.complexity,
                tags=list(concept.tags),
                origin=concept.origin,
                objectives=[
                    ObjectiveRecord(id=objective.id, statement=objective.statement)
                    for objective in concept.objectives
                ],
                prerequisites=[
                    PrerequisiteRecord(
                        concept_id=prerequisite_id,
                        title=titles[prerequisite_id],
                        reason=next(
                            link.reason
                            for link in concept.prerequisite_links
                            if link.prerequisite_id == prerequisite_id
                        ),
                    )
                    for prerequisite_id in prerequisites_of[concept.id]
                    if prerequisite_id in titles
                ],
                source_refs=[
                    SourceRefRecord(
                        id=ref.id,
                        source_id=ref.source_id,
                        source_name=ref.source.display_name,
                        section_id=ref.section_id,
                        section_title=ref.section.title,
                        page_number=ref.section.page_number,
                    )
                    for ref in concept.source_refs
                ],
                layer=depth.get(concept.id),
                knowledge=knowledge_record(states.get(concept.id)),
            )
            for index, concept in enumerate(concepts)
        ]
        return CurriculumRecord(
            course_id=course.id,
            concepts=records,
            learning_order=order,
            issues=issues,
            startable=bool(concepts) and not has_errors(graph_issues),
        )

    # -- concepts ----------------------------------------------------------

    def _add_concept(
        self,
        session: Session,
        course_id: str,
        position: int,
        *,
        title: str,
        summary: str,
        objectives: Sequence[str],
        origin: str,
    ) -> Concept:
        concept = Concept(
            id=new_id("con"),
            course_id=course_id,
            title=title,
            summary=summary,
            position=position,
            complexity=2,
            tags=[],
            origin=origin,
        )
        session.add(concept)
        for index, statement in enumerate(objectives):
            session.add(
                LearningObjective(
                    id=new_id("obj"), concept_id=concept.id, position=index, statement=statement
                )
            )
        return concept

    @staticmethod
    def _count(session: Session, course_id: str) -> int:
        return (
            session.scalar(select(func.count(Concept.id)).where(Concept.course_id == course_id))
            or 0
        )

    def create_concept(
        self,
        course_id: str,
        *,
        title: str,
        summary: str = "",
        objectives: Sequence[str] = (),
        origin: str = "learner",
    ) -> CurriculumRecord:
        statements = [_tidy(statement) for statement in objectives if _tidy(statement)]
        if len(statements) > MAX_OBJECTIVES:
            raise ValidationFailedError(
                f"A concept can have at most {MAX_OBJECTIVES} learning objectives."
            )
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            count = self._count(session, course_id)
            if count >= MAX_CONCEPTS:
                raise ValidationFailedError(
                    f"A course can have at most {MAX_CONCEPTS} concepts. "
                    "Split a very large course into several."
                )
            self._add_concept(
                session,
                course_id,
                count,
                title=_tidy(title),
                summary=summary.strip(),
                objectives=statements,
                origin=origin,
            )
            return self._load(session, course)

    def update_concept(
        self,
        concept_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        complexity: int | None = None,
        tags: Sequence[str] | None = None,
    ) -> CurriculumRecord:
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            if title is not None:
                concept.title = _tidy(title)
            if summary is not None:
                concept.summary = summary.strip()
            if complexity is not None:
                concept.complexity = complexity
            if tags is not None:
                unknown = sorted(set(tags) - set(CONCEPT_TAGS))
                if unknown:
                    raise ValidationFailedError("That kind of learning is not one Adle knows.")
                concept.tags = [tag for tag in CONCEPT_TAGS if tag in tags]
            return self._load(session, get_course_or_404(session, concept.course_id))

    def delete_concept(self, concept_id: str) -> CurriculumRecord:
        """Remove a concept. Anything that needed it simply no longer does."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            course = get_course_or_404(session, concept.course_id)
            session.delete(concept)
            session.flush()
            self._renumber(session, course.id)
            return self._load(session, course)

    def reorder(self, course_id: str, concept_ids: Sequence[str]) -> CurriculumRecord:
        """Set the learner's own order: ``concept_ids`` lists every concept of the course once."""
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            concepts = {
                concept.id: concept
                for concept in session.scalars(
                    select(Concept).where(Concept.course_id == course_id)
                )
            }
            if len(set(concept_ids)) != len(concept_ids) or set(concept_ids) != set(concepts):
                raise ValidationFailedError(
                    "That order doesn’t list every concept exactly once. Reload and try again."
                )
            for index, concept_id in enumerate(concept_ids):
                concepts[concept_id].position = index
            return self._load(session, course)

    @staticmethod
    def _renumber(session: Session, course_id: str) -> None:
        remaining = session.scalars(
            select(Concept).where(Concept.course_id == course_id).order_by(Concept.position)
        )
        for index, concept in enumerate(remaining):
            concept.position = index

    # -- objectives --------------------------------------------------------

    def set_objectives(
        self, concept_id: str, items: Sequence[tuple[str | None, str]]
    ) -> CurriculumRecord:
        """Replace a concept's objectives with ``items``: (existing id or ``None``, statement).

        Ids that are kept stay stable, so anything that later refers to an
        objective (a lesson, a question) keeps pointing at the right one.
        """
        cleaned = [(objective_id, _tidy(statement)) for objective_id, statement in items]
        cleaned = [(objective_id, statement) for objective_id, statement in cleaned if statement]
        if len(cleaned) > MAX_OBJECTIVES:
            raise ValidationFailedError(
                f"A concept can have at most {MAX_OBJECTIVES} learning objectives."
            )
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            existing = {objective.id: objective for objective in concept.objectives}
            kept_ids = [objective_id for objective_id, _ in cleaned if objective_id is not None]
            if len(set(kept_ids)) != len(kept_ids) or any(
                objective_id not in existing for objective_id in kept_ids
            ):
                raise ValidationFailedError(
                    "Those objectives don’t all belong to this concept. Reload and try again."
                )
            for existing_id, objective in existing.items():
                if existing_id not in kept_ids:
                    session.delete(objective)
            for index, (kept_id, statement) in enumerate(cleaned):
                if kept_id is None:
                    session.add(
                        LearningObjective(
                            id=new_id("obj"),
                            concept_id=concept.id,
                            position=index,
                            statement=statement,
                        )
                    )
                else:
                    existing[kept_id].position = index
                    existing[kept_id].statement = statement
            return self._load(session, get_course_or_404(session, concept.course_id))

    def add_proposed(
        self, course_id: str, proposed: Sequence[ProposedConceptInput]
    ) -> CurriculumRecord:
        """Add concepts a model proposed and the learner chose, with their links.

        All of them are added, or none. A concept may only need one that comes
        earlier in ``proposed``, so adding them cannot create a loop. A title the
        course already has is skipped (and so is any need that pointed at it); a
        section that is no longer in the course is simply not linked.
        """
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            count = self._count(session, course_id)
            taken = {
                _tidy(title).casefold()
                for title in session.scalars(
                    select(Concept.title).where(Concept.course_id == course_id)
                )
            }
            sections = set(
                session.scalars(
                    select(SourceSection.id)
                    .join(Source, Source.id == SourceSection.source_id)
                    .where(Source.course_id == course_id)
                )
            )
            created: dict[int, Concept] = {}
            for index, item in enumerate(proposed):
                title = _tidy(item.title)[:200]
                if not title or title.casefold() in taken:
                    continue
                if count >= MAX_CONCEPTS:
                    raise ValidationFailedError(
                        f"A course can have at most {MAX_CONCEPTS} concepts."
                    )
                taken.add(title.casefold())
                statements = [_tidy(text) for text in item.objectives if _tidy(text)]
                concept = self._add_concept(
                    session,
                    course_id,
                    count,
                    title=title,
                    summary=item.summary.strip(),
                    objectives=statements[:MAX_OBJECTIVES],
                    origin="model",
                )
                count += 1
                session.flush()
                linked: set[str] = set()
                for needed, reason in item.needs:
                    earlier = created.get(needed)
                    if earlier is None or needed >= index or earlier.id in linked:
                        continue
                    if len(linked) >= MAX_PREREQUISITES:
                        break
                    linked.add(earlier.id)
                    session.add(
                        ConceptEdge(
                            concept_id=concept.id,
                            prerequisite_id=earlier.id,
                            reason=_tidy(reason),
                            origin="model",
                        )
                    )
                for section_id in dict.fromkeys(item.section_ids):
                    if section_id in sections:
                        self._link(session, concept, course_id, section_id)
                created[index] = concept
            if not created:
                raise ValidationFailedError(
                    "The course already has every concept in that selection."
                )
            return self._load(session, course)

    # -- prerequisites -----------------------------------------------------

    def set_prerequisites(
        self, concept_id: str, items: Sequence[tuple[str, str]], *, origin: str = "learner"
    ) -> CurriculumRecord:
        """Replace what a concept needs first with ``items``: (prerequisite id, reason)."""
        wanted = [(prerequisite_id, reason.strip()) for prerequisite_id, reason in items]
        ids = [prerequisite_id for prerequisite_id, _ in wanted]
        if len(ids) > MAX_PREREQUISITES:
            raise ValidationFailedError(
                f"A concept can need at most {MAX_PREREQUISITES} others directly. "
                "If it needs more, some of them probably depend on each other."
            )
        if len(set(ids)) != len(ids):
            raise ValidationFailedError("The same concept is listed twice.")
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            course = get_course_or_404(session, concept.course_id)
            if concept_id in ids:
                raise ValidationFailedError("A concept can’t be its own prerequisite.")
            concepts = self._concepts(session, course.id)
            known = {other.id: other for other in concepts}
            if any(prerequisite_id not in known for prerequisite_id in ids):
                raise ValidationFailedError(
                    "One of those concepts is no longer part of this course. Reload and try again."
                )

            proposed = [
                ConceptNode(id=node.id, title=node.title, prerequisites=tuple(ids))
                if node.id == concept_id
                else node
                for node in self._nodes(concepts)
            ]
            loops = [loop for loop in find_cycles(proposed) if concept_id in loop]
            if loops:
                start = loops[0].index(concept_id)
                loop = (*loops[0][start:], *loops[0][:start], concept_id)
                chain = " needs ".join(f'"{known[step].title}"' for step in loop)
                raise ConflictError(
                    f"That would make a loop: {chain}. A concept can’t depend on something that "
                    "depends on it.",
                    code="prerequisite_loop",
                )

            current = {link.prerequisite_id: link for link in concept.prerequisite_links}
            for prerequisite_id, link in current.items():
                if prerequisite_id not in ids:
                    session.delete(link)
            for prerequisite_id, reason in wanted:
                if prerequisite_id in current:
                    current[prerequisite_id].reason = reason
                else:
                    session.add(
                        ConceptEdge(
                            concept_id=concept_id,
                            prerequisite_id=prerequisite_id,
                            reason=reason,
                            origin=origin,
                        )
                    )
            return self._load(session, course)

    # -- source references -------------------------------------------------

    def add_source_ref(self, concept_id: str, section_id: str) -> CurriculumRecord:
        """Link a concept to a place in the course's materials. Linking twice is harmless."""
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            course = get_course_or_404(session, concept.course_id)
            self._link(session, concept, course.id, section_id)
            return self._load(session, course)

    @staticmethod
    def _link(session: Session, concept: Concept, course_id: str, section_id: str) -> None:
        found = session.execute(
            select(SourceSection.id, Source.id)
            .join(Source, Source.id == SourceSection.source_id)
            .where(SourceSection.id == section_id, Source.course_id == course_id)
        ).first()
        if found is None:
            raise NotFoundError("That part of your materials is no longer in this course.")
        existing = session.scalars(
            select(ConceptSourceRef).where(ConceptSourceRef.concept_id == concept.id)
        ).all()
        if any(ref.section_id == section_id for ref in existing):
            return
        if len(existing) >= MAX_SOURCE_REFS:
            raise ValidationFailedError(
                f"A concept can be linked to at most {MAX_SOURCE_REFS} places in your materials."
            )
        session.add(
            ConceptSourceRef(concept_id=concept.id, source_id=found[1], section_id=section_id)
        )

    def remove_source_ref(self, concept_id: str, ref_id: int) -> CurriculumRecord:
        with self._database.session() as session:
            concept = get_concept_or_404(session, concept_id)
            ref = session.get(ConceptSourceRef, ref_id)
            if ref is None or ref.concept_id != concept_id:
                raise NotFoundError("That link no longer exists.")
            session.delete(ref)
            return self._load(session, get_course_or_404(session, concept.course_id))

    def related_passages(self, concept_id: str, limit: int = 6) -> list[Passage]:
        """Passages of the course's materials that bear on a concept, best first."""
        with self._database.read() as session:
            concept = get_concept_or_404(session, concept_id)
            course_id = concept.course_id
            objectives = session.scalars(
                select(LearningObjective.statement).where(
                    LearningObjective.concept_id == concept_id
                )
            )
            query = " ".join([concept.title, concept.summary, *objectives])
        return self._retriever.retrieve(course_id, query, limit=limit)

    # -- outline from materials --------------------------------------------

    @staticmethod
    def _heading_sections(session: Session, course_id: str) -> list[HeadingSection]:
        rows = session.execute(
            select(SourceSection, Source.display_name)
            .join(Source, Source.id == SourceSection.source_id)
            .where(
                Source.course_id == course_id,
                SourceSection.kind == "heading",
                SourceSection.title.is_not(None),
            )
            .order_by(Source.created_at, Source.id, SourceSection.ordinal)
        )
        return [
            HeadingSection(
                section_id=section.id,
                source_id=section.source_id,
                source_name=source_name,
                # Stored titles are heading paths; the concept is named by the last step.
                title=heading_leaf(section.title or ""),
                level=section.level if section.level is not None else 1,
                ordinal=section.ordinal,
            )
            for section, source_name in rows
        ]

    def outline_candidates(self, course_id: str) -> list[OutlineCandidateRecord]:
        """Concepts the headings of the course's materials suggest. Nothing is created."""
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            titles = session.scalars(select(Concept.title).where(Concept.course_id == course_id))
            candidates = draft_outline(self._heading_sections(session, course_id), list(titles))
            return [
                OutlineCandidateRecord(
                    section_id=candidate.section_id,
                    title=candidate.title,
                    source_id=candidate.source_id,
                    source_name=candidate.source_name,
                )
                for candidate in candidates
            ]

    def add_from_outline(self, course_id: str, section_ids: Sequence[str]) -> CurriculumRecord:
        """Create a concept for each chosen heading, linked to where it came from.

        Titles are taken from the stored headings, never from the request, so a
        concept's link to the materials is always genuine.
        """
        chosen = list(dict.fromkeys(section_ids))
        with self._database.session() as session:
            course = get_course_or_404(session, course_id)
            by_id = {
                section.section_id: section
                for section in self._heading_sections(session, course_id)
            }
            if any(section_id not in by_id for section_id in chosen):
                raise NotFoundError(
                    "Some of those headings are no longer in your materials. Reload and try again."
                )
            count = self._count(session, course_id)
            if count + len(chosen) > MAX_CONCEPTS:
                raise ValidationFailedError(f"A course can have at most {MAX_CONCEPTS} concepts.")
            taken = {
                " ".join(title.split()).casefold()
                for title in session.scalars(
                    select(Concept.title).where(Concept.course_id == course_id)
                )
            }
            for section_id in chosen:
                heading = by_id[section_id]
                title = clean_title(heading.title)
                if title.casefold() in taken:
                    continue
                taken.add(title.casefold())
                concept = self._add_concept(
                    session,
                    course_id,
                    count,
                    title=title[:200],
                    summary="",
                    objectives=(),
                    origin="outline",
                )
                session.flush()
                session.add(
                    ConceptSourceRef(
                        concept_id=concept.id, source_id=heading.source_id, section_id=section_id
                    )
                )
                count += 1
            return self._load(session, course)
