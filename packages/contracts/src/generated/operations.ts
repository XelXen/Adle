// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

import type {
  Course,
  CourseCreate,
  CourseList,
  CourseUpdate,
  Health,
  ImportRequest,
  Job,
  ProviderCredential,
  ProviderStatus,
  SearchResults,
  SourceDetail,
  SourceList,
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
  'jobs.cancel': { method: 'POST', path: '/v1/jobs/{job_id}/cancel', internal: false },
  'jobs.get': { method: 'GET', path: '/v1/jobs/{job_id}', internal: false },
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
