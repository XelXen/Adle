// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

import type {
  ConceptCreate,
  ConceptEvidence,
  ConceptOrder,
  ConceptUpdate,
  Course,
  CourseCreate,
  CourseList,
  CourseUpdate,
  Curriculum,
  Health,
  ImportRequest,
  Job,
  LearnerPreferences,
  LearnerPreferencesUpdate,
  ObjectivesUpdate,
  OutlineCandidates,
  OutlineSelection,
  Passages,
  PrerequisitesUpdate,
  ProviderCredential,
  ProviderStatus,
  SearchResults,
  SelfRating,
  SourceDetail,
  SourceList,
  SourceRefCreate,
} from './models';

/**
 * Every operation the core exposes. `internal` operations may only be called by the
 * Electron main process; the renderer bridge refuses them.
 */
export const OPERATIONS = {
  'courses.create': { method: 'POST', path: '/v1/courses', internal: false },
  'courses.delete': { method: 'DELETE', path: '/v1/courses/{course_id}', internal: false },
  'courses.get': { method: 'GET', path: '/v1/courses/{course_id}', internal: false },
  'courses.list': { method: 'GET', path: '/v1/courses', internal: false },
  'courses.update': { method: 'PATCH', path: '/v1/courses/{course_id}', internal: false },
  'curriculum.add_from_outline': {
    method: 'POST',
    path: '/v1/courses/{course_id}/outline',
    internal: false,
  },
  'curriculum.add_source_ref': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/source-refs',
    internal: false,
  },
  'curriculum.create_concept': {
    method: 'POST',
    path: '/v1/courses/{course_id}/concepts',
    internal: false,
  },
  'curriculum.delete_concept': {
    method: 'DELETE',
    path: '/v1/concepts/{concept_id}',
    internal: false,
  },
  'curriculum.get': { method: 'GET', path: '/v1/courses/{course_id}/curriculum', internal: false },
  'curriculum.outline_candidates': {
    method: 'GET',
    path: '/v1/courses/{course_id}/outline',
    internal: false,
  },
  'curriculum.related_passages': {
    method: 'GET',
    path: '/v1/concepts/{concept_id}/passages',
    internal: false,
  },
  'curriculum.remove_source_ref': {
    method: 'DELETE',
    path: '/v1/concepts/{concept_id}/source-refs/{ref_id}',
    internal: false,
  },
  'curriculum.reorder': {
    method: 'PUT',
    path: '/v1/courses/{course_id}/concept-order',
    internal: false,
  },
  'curriculum.set_objectives': {
    method: 'PUT',
    path: '/v1/concepts/{concept_id}/objectives',
    internal: false,
  },
  'curriculum.set_prerequisites': {
    method: 'PUT',
    path: '/v1/concepts/{concept_id}/prerequisites',
    internal: false,
  },
  'curriculum.update_concept': {
    method: 'PATCH',
    path: '/v1/concepts/{concept_id}',
    internal: false,
  },
  'jobs.cancel': { method: 'POST', path: '/v1/jobs/{job_id}/cancel', internal: false },
  'jobs.get': { method: 'GET', path: '/v1/jobs/{job_id}', internal: false },
  'learner.concept_evidence': {
    method: 'GET',
    path: '/v1/concepts/{concept_id}/evidence',
    internal: false,
  },
  'learner.get_preferences': { method: 'GET', path: '/v1/learner/preferences', internal: false },
  'learner.self_rate': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/self-rating',
    internal: false,
  },
  'learner.update_preferences': {
    method: 'PATCH',
    path: '/v1/learner/preferences',
    internal: false,
  },
  'provider.clear_credential': {
    method: 'DELETE',
    path: '/v1/provider/credential',
    internal: true,
  },
  'provider.set_credential': { method: 'PUT', path: '/v1/provider/credential', internal: true },
  'provider.status': { method: 'GET', path: '/v1/provider', internal: false },
  'sources.delete': { method: 'DELETE', path: '/v1/sources/{source_id}', internal: false },
  'sources.get': { method: 'GET', path: '/v1/sources/{source_id}', internal: false },
  'sources.import_paths': {
    method: 'POST',
    path: '/v1/courses/{course_id}/sources/import',
    internal: true,
  },
  'sources.list': { method: 'GET', path: '/v1/courses/{course_id}/sources', internal: false },
  'sources.search': { method: 'GET', path: '/v1/courses/{course_id}/search', internal: false },
  'system.health': { method: 'GET', path: '/v1/health', internal: false },
} as const;

export type OperationId = keyof typeof OPERATIONS;

/** Parameter and result types for each operation. */
export interface OperationTypes {
  'courses.create': {
    path: undefined;
    query: undefined;
    body: CourseCreate;
    result: Course;
  };
  'courses.delete': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'courses.get': {
    path: { course_id: string };
    query: { opened?: boolean } | undefined;
    body: undefined;
    result: Course;
  };
  'courses.list': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: CourseList;
  };
  'courses.update': {
    path: { course_id: string };
    query: undefined;
    body: CourseUpdate;
    result: Course;
  };
  'curriculum.add_from_outline': {
    path: { course_id: string };
    query: undefined;
    body: OutlineSelection;
    result: Curriculum;
  };
  'curriculum.add_source_ref': {
    path: { concept_id: string };
    query: undefined;
    body: SourceRefCreate;
    result: Curriculum;
  };
  'curriculum.create_concept': {
    path: { course_id: string };
    query: undefined;
    body: ConceptCreate;
    result: Curriculum;
  };
  'curriculum.delete_concept': {
    path: { concept_id: string };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.get': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.outline_candidates': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: OutlineCandidates;
  };
  'curriculum.related_passages': {
    path: { concept_id: string };
    query: { limit?: number } | undefined;
    body: undefined;
    result: Passages;
  };
  'curriculum.remove_source_ref': {
    path: { concept_id: string; ref_id: number };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.reorder': {
    path: { course_id: string };
    query: undefined;
    body: ConceptOrder;
    result: Curriculum;
  };
  'curriculum.set_objectives': {
    path: { concept_id: string };
    query: undefined;
    body: ObjectivesUpdate;
    result: Curriculum;
  };
  'curriculum.set_prerequisites': {
    path: { concept_id: string };
    query: undefined;
    body: PrerequisitesUpdate;
    result: Curriculum;
  };
  'curriculum.update_concept': {
    path: { concept_id: string };
    query: undefined;
    body: ConceptUpdate;
    result: Curriculum;
  };
  'jobs.cancel': {
    path: { job_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'jobs.get': {
    path: { job_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'learner.concept_evidence': {
    path: { concept_id: string };
    query: undefined;
    body: undefined;
    result: ConceptEvidence;
  };
  'learner.get_preferences': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: LearnerPreferences;
  };
  'learner.self_rate': {
    path: { concept_id: string };
    query: undefined;
    body: SelfRating;
    result: ConceptEvidence;
  };
  'learner.update_preferences': {
    path: undefined;
    query: undefined;
    body: LearnerPreferencesUpdate;
    result: LearnerPreferences;
  };
  'provider.clear_credential': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: null;
  };
  'provider.set_credential': {
    path: undefined;
    query: undefined;
    body: ProviderCredential;
    result: null;
  };
  'provider.status': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: ProviderStatus;
  };
  'sources.delete': {
    path: { source_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'sources.get': {
    path: { source_id: string };
    query: undefined;
    body: undefined;
    result: SourceDetail;
  };
  'sources.import_paths': {
    path: { course_id: string };
    query: undefined;
    body: ImportRequest;
    result: Job;
  };
  'sources.list': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: SourceList;
  };
  'sources.search': {
    path: { course_id: string };
    query: { q: string; limit?: number };
    body: undefined;
    result: SearchResults;
  };
  'system.health': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: Health;
  };
}
