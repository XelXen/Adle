"""The curriculum of a course, and what the learner has shown about each concept."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from adle_core.api import schemas
from adle_core.application.services import Services, get_services
from adle_core.learner_model.preferences import ExplanationDensity, Pace
from adle_core.learner_model.tracing import SelfReport

router = APIRouter(tags=["curriculum"])

ServicesDep = Annotated[Services, Depends(get_services)]


# -- curriculum ------------------------------------------------------------


@router.get(
    "/courses/{course_id}/curriculum",
    operation_id="curriculum.get",
    response_model=schemas.Curriculum,
)
def get_curriculum(course_id: str, services: ServicesDep) -> schemas.Curriculum:
    return schemas.Curriculum.model_validate(services.curriculum.get(course_id))


@router.post(
    "/courses/{course_id}/concepts",
    operation_id="curriculum.create_concept",
    response_model=schemas.Curriculum,
    status_code=201,
)
def create_concept(
    course_id: str, body: schemas.ConceptCreate, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.create_concept(
        course_id, title=body.title, summary=body.summary, objectives=body.objectives
    )
    return schemas.Curriculum.model_validate(record)


@router.patch(
    "/concepts/{concept_id}",
    operation_id="curriculum.update_concept",
    response_model=schemas.Curriculum,
)
def update_concept(
    concept_id: str, body: schemas.ConceptUpdate, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.update_concept(
        concept_id,
        title=body.title,
        summary=body.summary,
        complexity=body.complexity,
        tags=body.tags,
    )
    return schemas.Curriculum.model_validate(record)


@router.delete(
    "/concepts/{concept_id}",
    operation_id="curriculum.delete_concept",
    response_model=schemas.Curriculum,
)
def delete_concept(concept_id: str, services: ServicesDep) -> schemas.Curriculum:
    return schemas.Curriculum.model_validate(services.curriculum.delete_concept(concept_id))


@router.put(
    "/courses/{course_id}/concept-order",
    operation_id="curriculum.reorder",
    response_model=schemas.Curriculum,
)
def reorder_concepts(
    course_id: str, body: schemas.ConceptOrder, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.reorder(course_id, body.concept_ids)
    return schemas.Curriculum.model_validate(record)


@router.put(
    "/concepts/{concept_id}/objectives",
    operation_id="curriculum.set_objectives",
    response_model=schemas.Curriculum,
)
def set_objectives(
    concept_id: str, body: schemas.ObjectivesUpdate, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.set_objectives(
        concept_id, [(item.id, item.statement) for item in body.objectives]
    )
    return schemas.Curriculum.model_validate(record)


@router.put(
    "/concepts/{concept_id}/prerequisites",
    operation_id="curriculum.set_prerequisites",
    response_model=schemas.Curriculum,
)
def set_prerequisites(
    concept_id: str, body: schemas.PrerequisitesUpdate, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.set_prerequisites(
        concept_id, [(item.concept_id, item.reason) for item in body.prerequisites]
    )
    return schemas.Curriculum.model_validate(record)


@router.post(
    "/concepts/{concept_id}/source-refs",
    operation_id="curriculum.add_source_ref",
    response_model=schemas.Curriculum,
)
def add_source_ref(
    concept_id: str, body: schemas.SourceRefCreate, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.add_source_ref(concept_id, body.section_id)
    return schemas.Curriculum.model_validate(record)


@router.delete(
    "/concepts/{concept_id}/source-refs/{ref_id}",
    operation_id="curriculum.remove_source_ref",
    response_model=schemas.Curriculum,
)
def remove_source_ref(concept_id: str, ref_id: int, services: ServicesDep) -> schemas.Curriculum:
    record = services.curriculum.remove_source_ref(concept_id, ref_id)
    return schemas.Curriculum.model_validate(record)


@router.get(
    "/courses/{course_id}/outline",
    operation_id="curriculum.outline_candidates",
    response_model=schemas.OutlineCandidates,
)
def outline_candidates(course_id: str, services: ServicesDep) -> schemas.OutlineCandidates:
    candidates = services.curriculum.outline_candidates(course_id)
    return schemas.OutlineCandidates(
        candidates=[schemas.OutlineCandidate.model_validate(item) for item in candidates]
    )


@router.post(
    "/courses/{course_id}/outline",
    operation_id="curriculum.add_from_outline",
    response_model=schemas.Curriculum,
    status_code=201,
)
def add_from_outline(
    course_id: str, body: schemas.OutlineSelection, services: ServicesDep
) -> schemas.Curriculum:
    record = services.curriculum.add_from_outline(course_id, body.section_ids)
    return schemas.Curriculum.model_validate(record)


@router.get(
    "/concepts/{concept_id}/passages",
    operation_id="curriculum.related_passages",
    response_model=schemas.Passages,
)
def related_passages(
    concept_id: str,
    services: ServicesDep,
    limit: Annotated[int, Query(ge=1, le=12)] = 6,
) -> schemas.Passages:
    passages = services.curriculum.related_passages(concept_id, limit)
    return schemas.Passages(passages=[schemas.Passage.model_validate(item) for item in passages])


# -- learner ---------------------------------------------------------------


@router.get(
    "/learner/preferences",
    operation_id="learner.get_preferences",
    response_model=schemas.LearnerPreferences,
)
def get_preferences(services: ServicesDep) -> schemas.LearnerPreferences:
    return schemas.LearnerPreferences.model_validate(services.learner.get_preferences())


@router.patch(
    "/learner/preferences",
    operation_id="learner.update_preferences",
    response_model=schemas.LearnerPreferences,
)
def update_preferences(
    body: schemas.LearnerPreferencesUpdate, services: ServicesDep
) -> schemas.LearnerPreferences:
    updated = services.learner.update_preferences(
        pace=Pace(body.pace) if body.pace else None,
        explanation_density=(
            ExplanationDensity(body.explanation_density) if body.explanation_density else None
        ),
        narration=body.narration,
        captions=body.captions,
        goal=body.goal,
    )
    return schemas.LearnerPreferences.model_validate(updated)


@router.post(
    "/concepts/{concept_id}/self-rating",
    operation_id="learner.self_rate",
    response_model=schemas.ConceptEvidence,
)
def self_rate(
    concept_id: str, body: schemas.SelfRating, services: ServicesDep
) -> schemas.ConceptEvidence:
    record = services.learner.self_rate(concept_id, SelfReport(body.level))
    return schemas.ConceptEvidence.model_validate(record)


@router.get(
    "/concepts/{concept_id}/evidence",
    operation_id="learner.concept_evidence",
    response_model=schemas.ConceptEvidence,
)
def concept_evidence(concept_id: str, services: ServicesDep) -> schemas.ConceptEvidence:
    return schemas.ConceptEvidence.model_validate(services.learner.concept_evidence(concept_id))
