import type {
  AnswerResult,
  ConceptProgress,
  Hypothesis,
  NextStep,
  PracticeSet,
  ProgressSummary,
  SessionShown,
  SessionSummary,
} from '@adle/contracts';

import type { Route } from '../app/router';
import { formatRelativeDay, pluralise } from './format';

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
          label: 'Set up AI provider',
          route: { name: 'settings', tab: 'ai' },
        };
      }
      return step.concept_id
        ? { type: 'generate', label: 'Create lesson', conceptId: step.concept_id }
        : { type: 'none' };
    case 'add_concepts':
      return {
        type: 'navigate',
        label: 'Open curriculum',
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
  if (concept.review_due) return 'Review due';
  const due = concept.knowledge.review_due_at;
  return due ? `Next review ${formatWait(due, now)}` : null;
}

/** Counts of concepts by what the evidence says, as a sentence. Counts, never a score. */
export function summarySentence(summary: ProgressSummary): string {
  if (summary.concepts === 0) return 'This course has no concepts yet.';
  const parts = [
    summary.demonstrated > 0 ? `${summary.demonstrated} understood` : null,
    summary.in_progress > 0 ? `${summary.in_progress} in progress` : null,
    summary.not_assessed > 0 ? `${summary.not_assessed} not started` : null,
  ].filter((part): part is string => part !== null);
  return `${pluralise(summary.concepts, 'concept')}: ${parts.join(', ')}.`;
}

/** What is due, or when something will be. Null when no review is planned at all. */
export function reviewSentence(summary: ProgressSummary, now: Date = new Date()): string | null {
  if (summary.reviews_due > 0) {
    return summary.reviews_due === 1 ? '1 review due.' : `${summary.reviews_due} reviews due.`;
  }
  return summary.next_review_at ? `Next review ${formatWait(summary.next_review_at, now)}.` : null;
}

/**
 * What a sitting is called. While the learner may still be in it, it is "This session";
 * afterwards it is what they did last time, with the day, for someone coming back.
 */
export function sessionHeading(
  session: Pick<SessionSummary, 'current' | 'ended_at'>,
  now: Date = new Date(),
): string {
  if (session.current) return 'This session';
  const day = formatRelativeDay(session.ended_at, now);
  if (day === 'Today') return 'Earlier today';
  if (day === 'Yesterday') return 'Last time, yesterday';
  if (day.endsWith(' ago')) return `Last time, ${day}`;
  return day ? `Last time, on ${day}` : 'Last time';
}

/** What was done in a sitting, as counts of things that happened. */
export function sessionCounts(
  session: Pick<SessionSummary, 'lessons_completed' | 'answered'>,
): string {
  const parts = [
    session.lessons_completed > 0
      ? `${pluralise(session.lessons_completed, 'lesson')} finished`
      : null,
    session.answered > 0 ? `${pluralise(session.answered, 'question')} answered` : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? `${parts.join(', ')}.` : 'No questions answered.';
}

/**
 * What a concept's answers in a sitting showed. Counts of right answers; wrong answers are
 * not in it. A right answer that did not count in full (see `LIGHTER_EVIDENCE`) is still a
 * right answer, and is said to be lighter evidence, which is what the core calls it.
 */
export function shownSentence(
  line: Pick<SessionShown, 'right' | 'right_unaided' | 'demonstrated'>,
): string {
  const lighter = Math.max(0, line.right - line.right_unaided);
  let answers = `${pluralise(line.right, 'answer')} right`;
  if (lighter > 0) {
    answers += line.right === 1 ? ', with help' : `, ${lighter} with help`;
  }
  return line.demonstrated ? `${answers}. Understood.` : `${answers}.`;
}

/** Whether any line needs "lighter evidence" explained beneath it. */
export function hasLighterEvidence(
  lines: readonly Pick<SessionShown, 'right' | 'right_unaided'>[],
): boolean {
  return lines.some((line) => line.right > line.right_unaided);
}

export const LIGHTER_EVIDENCE =
  '“With help” means after a hint, when you weren’t sure, self-marked, or just after seeing ' +
  'the explanation. It still counts, a little less.';

/** When a planned review comes round, as a sentence. */
export function reviewWhen(dueAt: string, now: Date = new Date()): string {
  const wait = formatWait(dueAt, now);
  return wait === '' || wait === 'now' ? 'Review due.' : `Review ${wait}.`;
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
      return { status: 'Suspected', tone: 'info' };
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
  check: 'Quick check',
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
