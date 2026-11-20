import type {
  AnswerResult,
  ConceptProgress,
  Hypothesis,
  NextStep,
  PracticeSet,
  ProgressSummary,
} from '@adle/contracts';

import type { Route } from '../app/router';
import { pluralise } from './format';

/**
 * What the interface does with what the core decided: where a suggested step
 * leads, and how progress and hypotheses are put into words. Nothing here
 * decides what to suggest or what an answer means; the core does that.
 */

/** What pressing a step's button does. */
export type StepAction =
  | { type: 'navigate'; label: string; route: Route }
  /** Ask the AI provider to write a lesson for a concept. */
  | { type: 'generate'; label: string; conceptId: string }
  /** Nothing to do: the step only says something. */
  | { type: 'none' };

export function stepAction(step: NextStep, courseId: string): StepAction {
  const lesson = (label: string): StepAction =>
    step.lesson_id
      ? { type: 'navigate', label, route: { name: 'lesson', courseId, lessonId: step.lesson_id } }
      : { type: 'none' };
  const practice = (label: string): StepAction =>
    step.concept_id
      ? {
          type: 'navigate',
          label,
          route: {
            name: 'practice',
            courseId,
            conceptId: step.concept_id,
            ...(step.about ? { about: step.about } : {}),
          },
        }
      : { type: 'none' };

  switch (step.kind) {
    case 'start_lesson':
      return lesson('Start lesson');
    case 'resume_lesson':
      return lesson('Continue lesson');
    case 'repeat_lesson':
      return lesson('Open lesson');
    case 'revisit_prerequisite':
      return lesson('Open lesson');
    case 'review':
      return practice('Start review');
    case 'practise':
      return practice('Practise');
    case 'check':
      return practice('Answer a few questions');
    case 'create_lesson':
    case 'another_explanation':
      if (step.needs_key) {
        return {
          type: 'navigate',
          label: 'Set up the AI provider',
          route: { name: 'settings', tab: 'ai' },
        };
      }
      return step.concept_id
        ? { type: 'generate', label: 'Create the lesson', conceptId: step.concept_id }
        : { type: 'none' };
    case 'add_concepts':
      return {
        type: 'navigate',
        label: 'Go to the curriculum',
        route: { name: 'course', courseId, tab: 'curriculum' },
      };
    case 'nothing_due':
      return { type: 'none' };
  }
}

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

/** How long until a moment, in everyday words: "in less than an hour", "tomorrow", "in 3 days". */
export function formatWait(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const wait = then.getTime() - now.getTime();
  if (wait <= 0) return 'now';
  if (wait < HOUR_MS) return 'in less than an hour';
  if (wait < 20 * HOUR_MS) return `in about ${pluralise(Math.round(wait / HOUR_MS), 'hour')}`;
  const days = Math.max(1, Math.round(wait / DAY_MS));
  return days === 1 ? 'tomorrow' : `in ${days} days`;
}

/** When a concept is next worth reviewing, if a review is planned. */
export function reviewNote(concept: ConceptProgress, now: Date = new Date()): string | null {
  if (concept.review_due) return 'A review is due';
  const due = concept.knowledge.review_due_at;
  return due ? `Next review ${formatWait(due, now)}` : null;
}

/** Counts of concepts by what the evidence says, as a sentence. Counts, never a score. */
export function summarySentence(summary: ProgressSummary): string {
  if (summary.concepts === 0) return 'This course has no concepts yet.';
  const parts = [
    summary.demonstrated > 0 ? `${summary.demonstrated} demonstrated for now` : null,
    summary.in_progress > 0 ? `${summary.in_progress} in progress` : null,
    summary.not_assessed > 0 ? `${summary.not_assessed} not assessed yet` : null,
  ].filter((part): part is string => part !== null);
  return `${pluralise(summary.concepts, 'concept')}: ${parts.join(', ')}.`;
}

/** What is due, or when something will be. Null when no review is planned at all. */
export function reviewSentence(summary: ProgressSummary, now: Date = new Date()): string | null {
  if (summary.reviews_due > 0) {
    return summary.reviews_due === 1
      ? '1 review is due.'
      : `${summary.reviews_due} reviews are due.`;
  }
  return summary.next_review_at
    ? `The next review is ${formatWait(summary.next_review_at, now)}.`
    : null;
}

export interface HypothesisLabel {
  /** A short status for a badge. */
  status: string;
  tone: 'neutral' | 'info' | 'warning' | 'success';
}

/** How a hypothesis is labelled: by how far the evidence goes, never as a verdict. */
export function hypothesisLabel(hypothesis: Hypothesis): HypothesisLabel {
  if (hypothesis.is_slip) {
    return { status: hypothesis.can_dismiss ? 'A slip' : 'An earlier slip', tone: 'neutral' };
  }
  switch (hypothesis.status) {
    case 'tentative':
      return { status: 'Suspected, not established', tone: 'info' };
    case 'supported':
      return { status: 'Seen more than once', tone: 'warning' };
    case 'resolved':
      return { status: 'Sorted', tone: 'success' };
    case 'rejected':
      return { status: 'Set aside', tone: 'neutral' };
  }
}

const PURPOSE_TITLE: Record<PracticeSet['purpose'], string> = {
  review: 'Review',
  check: 'A quick check',
  practise: 'Practice',
};

export function practiceTitle(practice: Pick<PracticeSet, 'purpose' | 'concept_title'>): string {
  return `${PURPOSE_TITLE[practice.purpose]}: ${practice.concept_title}`;
}

const OUTCOME_WORDS: Record<AnswerResult['outcome'], string> = {
  correct: 'Right',
  partial: 'Partly right',
  incorrect: 'Not yet',
  skipped: 'Skipped',
};

export function outcomeWords(outcome: AnswerResult['outcome']): string {
  return OUTCOME_WORDS[outcome];
}

/** How a finished set of questions went, as a sentence without judgement. */
export function practiceSummary(outcomes: readonly AnswerResult['outcome'][]): string {
  const answered = outcomes.filter((outcome) => outcome !== 'skipped');
  const right = answered.filter((outcome) => outcome === 'correct').length;
  const skipped = outcomes.length - answered.length;
  if (answered.length === 0) {
    return outcomes.length === 1 ? 'You skipped the question.' : 'You skipped every question.';
  }
  const base = `${right} of ${pluralise(answered.length, 'answer')} right`;
  return skipped > 0 ? `${base}, and ${skipped} skipped.` : `${base}.`;
}
