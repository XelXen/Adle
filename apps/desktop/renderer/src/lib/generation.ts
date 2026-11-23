import type { Job } from '@adle/contracts';

import { readWritingProgress } from './writing-progress';

/**
 * Reading what a generation job says. A job's `result` is free-form as far as
 * the contract goes, so it is checked here before anything is shown.
 */

export const KIND_PROPOSAL = 'curriculum_proposal';
export const KIND_LESSON = 'lesson_generation';

/**
 * Everything a request for a lesson contains, as a list to put between "Sends" and
 * "to <provider>".
 *
 * This is a promise to the learner, made before anything is sent. Keep it in step with
 * `lesson_request` in the core (`generation/prompts.py`): if the request gains something,
 * it is named here first.
 *
 * `materials` is whether the course has imported materials, where the caller knows.
 */
export function lessonDisclosure(materials: 'some' | 'none' | 'unknown'): string {
  const always =
    'the course name, this concept and its objectives, and your level, preferences, and goal';
  if (materials === 'some') return `${always}, plus a few passages from your materials`;
  if (materials === 'unknown') return `${always}, plus any related passages from your materials`;
  return always;
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

/** Who wrote something, as the core recorded it when it was written. */
export interface WrittenBy {
  /** The provider, by the name it went by then. The one in use now may be another. */
  provider: string;
  /** The models that answered, by the names a person would use. */
  models: string[];
  /** A sentence saying that another model stood in, and for which; empty when none did. */
  note: string;
}

export interface Proposal {
  concepts: ProposedConcept[];
  /** The proposal drew on the headings of the learner's own materials. */
  groundedInMaterials: boolean;
  /** It has already been added to the course, or set aside. */
  closed: boolean;
  /** Who suggested it, where the job says. Older proposals do not. */
  writtenBy: WrittenBy | null;
}

export interface LessonOutcome {
  lessonId: string;
  title: string;
  /** Things that did not go as planned but did not stop the lesson, in sentences. */
  notes: string[];
  /**
   * Pictures still being drawn. A lesson can be started as soon as its text is written
   * (ADR-031); this is 0 once the work has ended.
   */
  picturesPending: number;
  /**
   * Its first part is still being recorded in the natural voice: it is ready to be
   * started once that can be heard (ADR-051).
   */
  voicing: boolean;
}

function readWrittenBy(value: unknown): WrittenBy | null {
  if (!isRecord(value) || typeof value.provider !== 'string' || !value.provider) return null;
  return {
    provider: value.provider,
    models: strings(value.models),
    note: typeof value.note === 'string' ? value.note : '',
  };
}

/**
 * Who to name as the author: "Mistral Large 4 on NVIDIA NIM", or the provider alone where
 * the model is not known. `fallback` is for work recorded before authors were.
 */
export function authorName(writtenBy: WrittenBy | null, fallback: string): string {
  if (!writtenBy) return fallback;
  const [model, ...others] = writtenBy.models;
  return model !== undefined && others.length === 0
    ? `${model} on ${writtenBy.provider}`
    : writtenBy.provider;
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
    writtenBy: readWrittenBy(result.written_by),
  };
}

/**
 * The lesson a job has produced, or null if it has not produced one.
 *
 * There is a lesson as soon as its text is written, while the job goes on to draw its
 * pictures: a job that is still running can already have one. A job that failed or was
 * cancelled is never read as having one, whatever it said on the way.
 */
export function readLessonOutcome(job: Job | null): LessonOutcome | null {
  if (!job || job.kind !== KIND_LESSON) return null;
  if (job.status !== 'succeeded' && job.status !== 'running') return null;
  const result = job.result;
  if (!isRecord(result) || typeof result.lesson_id !== 'string') return null;
  const pending = typeof result.pictures_pending === 'number' ? result.pictures_pending : 0;
  return {
    lessonId: result.lesson_id,
    title: typeof result.title === 'string' ? result.title : '',
    notes: strings(result.notes),
    picturesPending: job.status === 'running' ? Math.max(0, Math.round(pending)) : 0,
    voicing: job.status === 'running' && result.voicing === true,
  };
}

/**
 * Whether a job has a lesson to start already while it is still running: the lesson was
 * begun at its first part and the rest of it is being written (ADR-048), or all of it is
 * written and its pictures are being drawn (ADR-031). In a natural voice, once its first
 * part can be heard (ADR-051).
 */
export function hasLessonToStart(job: Job | null): boolean {
  if (job === null || job.status !== 'running') return false;
  const outcome = readLessonOutcome(job);
  return outcome !== null && !outcome.voicing;
}

/**
 * Whether a job's lesson can be started while the rest of its parts are still being
 * written (ADR-048). Once its words are all written, the core says it is drawing.
 */
export function isWritingTheRest(job: Job | null): boolean {
  if (!hasLessonToStart(job)) return false;
  const stage = readWritingProgress(job)?.stage ?? null;
  return stage !== null && stage !== 'drawing' && stage !== 'voicing';
}

/** Whether all of a job's lesson is written, and what is left is its pictures (ADR-031). */
export function isDrawingPictures(job: Job | null): boolean {
  return hasLessonToStart(job) && !isWritingTheRest(job);
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

const FALLBACK = 'Something went wrong. Please try again.';

function failure(code: string | null | undefined, message: string | null | undefined): JobFailure {
  const text = message || FALLBACK;
  switch (code) {
    case 'provider_key_missing':
    case 'provider_key_rejected':
      return { message: text, remedy: 'settings' };
    case 'provider_notice':
      // The provider answered about the learner's account. Asking again changes nothing;
      // the settings are where the account and the key are looked after.
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

/** What to tell the learner about a lesson job, if anything. */
export interface LessonNotice {
  tone: 'success' | 'info';
  title: string;
  description: string;
}

/**
 * A title and what there is to say about it, as one line. The title gets a full stop of
 * its own when something follows, so that the two do not run together.
 */
export function titled(title: string, about: readonly string[]): string {
  const said = about.filter(Boolean);
  if (said.length === 0) return title;
  if (!title) return said.join(' ');
  return [/[.!?…]$/.test(title) ? title : `${title}.`, ...said].join(' ');
}

/**
 * What to say when a lesson job has a lesson to start, and when it has ended.
 *
 * The lesson is announced once: when it can be started, which is at its first part, before
 * the rest is written (ADR-048) and its pictures drawn (ADR-031). The end of the work is
 * only worth a second word if something needs saying: a picture could not be made, a part
 * was left out, or the work was stopped.
 */
export function lessonNotice(job: Job, saidBefore: boolean): LessonNotice | null {
  const outcome = readLessonOutcome(job);
  if (!outcome) return null;
  if (!saidBefore) {
    // Not ready until its first part can be heard (ADR-051).
    if (outcome.voicing) return null;
    let about = outcome.notes;
    if (isWritingTheRest(job)) about = ['The rest of it is being written.'];
    else if (outcome.picturesPending > 0) about = ['Its pictures are still being drawn.'];
    return {
      tone: 'success',
      title: 'Lesson ready',
      description: titled(outcome.title, about),
    };
  }
  if (job.status === 'succeeded' && outcome.notes.length > 0) {
    return { tone: 'info', title: 'About the lesson', description: outcome.notes.join(' ') };
  }
  return null;
}
