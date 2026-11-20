import type { Job } from '@adle/contracts';

/**
 * Reading what a generation job says. A job's `result` is free-form as far as
 * the contract goes, so it is checked here before anything is shown.
 */

export const KIND_PROPOSAL = 'curriculum_proposal';
export const KIND_LESSON = 'lesson_generation';

/**
 * Everything a request for a lesson contains, as a list to put after "Sends to <provider>:".
 *
 * This is a promise to the learner, made before anything is sent. Keep it in step with
 * `lesson_request` in the core (`generation/prompts.py`): if the request gains something,
 * it is named here first.
 *
 * `materials` is whether the course has imported materials, where the caller knows.
 */
export function lessonDisclosure(materials: 'some' | 'none' | 'unknown'): string {
  const always =
    "this course's name, this concept and its objectives, where you stand on it in a few " +
    'words, your preferences for pace and depth';
  if (materials === 'some') {
    return `${always}, your goal, and a few related passages from your materials`;
  }
  if (materials === 'unknown') {
    return `${always}, your goal, and any related passages from your materials`;
  }
  return `${always}, and your goal`;
}

export interface ProposedNeed {
  /** Position of the needed concept in the same proposal. */
  index: number;
  reason: string;
}

export interface ProposedConcept {
  title: string;
  summary: string;
  objectives: string[];
  needs: ProposedNeed[];
}

export interface Proposal {
  concepts: ProposedConcept[];
  /** The proposal drew on the headings of the learner's own materials. */
  groundedInMaterials: boolean;
  /** It has already been added to the course, or set aside. */
  closed: boolean;
}

export interface LessonOutcome {
  lessonId: string;
  title: string;
  /** Things that did not go as planned but did not stop the lesson, in sentences. */
  notes: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

/** The proposal a finished job carries, or null if it is not (or no longer) one. */
export function readProposal(job: Job | null): Proposal | null {
  if (!job || job.kind !== KIND_PROPOSAL || job.status !== 'succeeded') return null;
  const result = job.result;
  if (!isRecord(result) || !Array.isArray(result.concepts)) return null;
  const concepts: ProposedConcept[] = [];
  for (const item of result.concepts) {
    if (!isRecord(item) || typeof item.title !== 'string') return null;
    const needs = Array.isArray(item.needs) ? item.needs : [];
    concepts.push({
      title: item.title,
      summary: typeof item.summary === 'string' ? item.summary : '',
      objectives: strings(item.objectives),
      needs: needs.flatMap((need) =>
        isRecord(need) && typeof need.index === 'number'
          ? [{ index: need.index, reason: typeof need.reason === 'string' ? need.reason : '' }]
          : [],
      ),
    });
  }
  if (concepts.length === 0) return null;
  return {
    concepts,
    groundedInMaterials: result.grounded_in_materials === true,
    closed: result.accepted === true || result.dismissed === true,
  };
}

/** What a finished lesson job produced, or null if it did not produce a lesson. */
export function readLessonOutcome(job: Job | null): LessonOutcome | null {
  if (!job || job.kind !== KIND_LESSON || job.status !== 'succeeded') return null;
  const result = job.result;
  if (!isRecord(result) || typeof result.lesson_id !== 'string') return null;
  return {
    lessonId: result.lesson_id,
    title: typeof result.title === 'string' ? result.title : '',
    notes: strings(result.notes),
  };
}

export interface JobProgress {
  /** Between 0 and 1, or undefined while there is nothing to measure yet. */
  value: number | undefined;
  message: string;
}

export function jobProgress(job: Job, waiting: string): JobProgress {
  const total = job.progress_total;
  return {
    value: total > 0 ? Math.min(1, Math.max(0, job.progress_done / total)) : undefined,
    message: job.status === 'queued' ? waiting : job.progress_message || waiting,
  };
}

export interface JobFailure {
  message: string;
  /** What the learner can do about it. */
  remedy: 'settings' | 'retry' | 'wait';
}

const FALLBACK = 'Something went wrong. Nothing was changed; you can try again.';

function failure(code: string | null | undefined, message: string | null | undefined): JobFailure {
  const text = message || FALLBACK;
  switch (code) {
    case 'provider_key_missing':
    case 'provider_key_rejected':
      return { message: text, remedy: 'settings' };
    case 'quota_exhausted':
      // Trying again today cannot help; the allowance starts again tomorrow.
      return { message: text, remedy: 'wait' };
    default:
      return { message: text, remedy: 'retry' };
  }
}

/** Why a job did not succeed, or null if it succeeded, was cancelled, or is still going. */
export function jobFailure(job: Job | null): JobFailure | null {
  if (!job || job.status !== 'failed') return null;
  return failure(job.error_code, job.error_message);
}

/** Why a job could not even be started, from what the core answered. */
export function refusalOf(error: unknown): JobFailure {
  const code =
    typeof error === 'object' && error !== null && 'code' in error && typeof error.code === 'string'
      ? error.code
      : null;
  return failure(code, error instanceof Error ? error.message : null);
}

/**
 * The concepts still selected once anything that was needed but dropped is
 * accounted for: for each selected concept, the needs that are also selected.
 */
export function keptNeeds(proposal: Proposal, selected: ReadonlySet<number>, index: number) {
  return (proposal.concepts[index]?.needs ?? []).filter((need) => selected.has(need.index));
}
