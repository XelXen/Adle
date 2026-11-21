import type { Job, JobProgressDetail } from '@adle/contracts';

/**
 * Something to watch while a lesson is written (ADR-037).
 *
 * A request to a model that thinks before it writes takes minutes, and a bar that does
 * not move for minutes looks like a program that has stopped. The core says what the work
 * is doing as it goes: which stage it is at and, for something written part by part, the
 * titles of the parts written so far. Never the words themselves: a title is enough to see
 * a lesson taking shape, and a half-written sentence is nobody's to read.
 *
 * This file only reads what the core said and puts it into words. It decides nothing.
 */

/** The stages long work goes through, as the core names them (`JobProgressDetail`). */
export type WritingStage = NonNullable<JobProgressDetail['stage']>;

const STAGES: ReadonlySet<string> = new Set(['waiting', 'thinking', 'writing', 'drawing']);

export interface WritingProgress {
  stage: WritingStage | null;
  /** What is being written, by its own title, once the model has written that. */
  title: string;
  /** The titles of its parts so far, in order. The last may still be being written. */
  outline: string[];
}

/** How many titles are shown at most, and how long one may be: it is a model's text. */
const MAX_OUTLINE = 40;
const MAX_TITLE = 140;

function clean(value: unknown): string {
  if (typeof value !== 'string') return '';
  // One line of plain text, whatever was sent.
  const line = value
    .replace(/\p{Cc}+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return line.length > MAX_TITLE ? `${line.slice(0, MAX_TITLE - 1)}…` : line;
}

/**
 * What a job says it is doing just now; null when it says nothing of the kind. The titles
 * are a model's text: each is made one line of plain text, whatever was sent.
 */
export function readWritingProgress(job: Job | null): WritingProgress | null {
  const detail: unknown = job?.progress_detail;
  if (typeof detail !== 'object' || detail === null || Array.isArray(detail)) return null;
  const { stage, title, outline } = detail as Record<string, unknown>;
  return {
    stage: typeof stage === 'string' && STAGES.has(stage) ? (stage as WritingStage) : null,
    title: clean(title),
    outline: (Array.isArray(outline) ? outline : [])
      .map(clean)
      .filter((item) => item.length > 0)
      .slice(0, MAX_OUTLINE),
  };
}

/** What is being made, for the sentences below. */
export type WritingSubject = 'lesson' | 'suggestions' | 'answer';

/**
 * The one line that says what is happening, in the learner's terms and not the model's.
 * Where the core's own sentence is the news (a wait for a rate limit, another model
 * standing in), that sentence is used as it is.
 */
export function writingHeadline(
  progress: WritingProgress | null,
  subject: WritingSubject,
  fallback: string,
): string {
  switch (progress?.stage) {
    case 'thinking':
      return subject === 'lesson'
        ? 'Planning the lesson'
        : subject === 'suggestions'
          ? 'Thinking about your course'
          : 'Thinking it through';
    case 'writing':
      if (subject === 'lesson') {
        return progress.title ? `Writing “${progress.title}”` : 'Writing the lesson';
      }
      return subject === 'suggestions' ? 'Choosing concepts' : 'Writing the answer';
    default:
      // Waiting for a turn, drawing a picture, or nothing said: the core's own sentence.
      return fallback;
  }
}

/** A lesson has about this many parts: enough to say roughly how far the writing has come. */
const USUAL_PARTS = 9;
/** Never "done" before the core says so. */
const MOST = 0.94;

/**
 * How far the writing has come, between 0 and 1, or undefined while there is nothing to
 * go by (before the first word, the honest answer is that nobody knows).
 *
 * It counts parts, not minutes: a part that exists is a fact, and a clock is a guess. It
 * moves on a little for every part and never reaches the end by itself.
 */
export function writingFraction(progress: WritingProgress | null): number | undefined {
  if (!progress || progress.stage !== 'writing') return undefined;
  const parts = progress.outline.length;
  if (parts === 0) return progress.title ? 0.04 : undefined;
  // Past the usual length the bar slows down and does not stop: each part still shows.
  const share =
    parts <= USUAL_PARTS ? parts / (USUAL_PARTS + 1) : 1 - 1 / (parts - USUAL_PARTS + 10);
  return Math.min(MOST, Math.max(0.04, share));
}

/**
 * How full a bar of this work is: for words, how many parts exist so far; for pictures,
 * how many are drawn (`counted`, the job's own steps). Undefined, a bar that moves without
 * a measure, while nothing can be counted yet: waiting for a turn, or a model thinking. An
 * empty bar that stands still is what a stalled program looks like, and this is not one.
 */
export function barValue(
  job: Job | null,
  progress: WritingProgress | null,
  counted: number | undefined,
): number | undefined {
  if (!job || job.status === 'queued') return undefined;
  switch (progress?.stage) {
    case 'writing':
      return writingFraction(progress);
    case 'waiting':
    case 'thinking':
      return undefined;
    default:
      return counted !== undefined && counted > 0 ? counted : undefined;
  }
}

/** How long ago something began, as a clock reads: "0:42", "3:05". */
export function elapsedSince(startedAt: string | null | undefined, now: number): string | null {
  if (!startedAt) return null;
  const began = Date.parse(startedAt);
  if (!Number.isFinite(began)) return null;
  const seconds = Math.max(0, Math.floor((now - began) / 1000));
  // Hours are not what anyone waits for here; past one, minutes still say it.
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}
