import { Check, Coffee } from 'lucide-react';

import type { Job } from '@adle/contracts';
import { Button, Callout, Card, ProgressBar, cx } from '@adle/design-system';

import { useBreak } from '../app/BreakContext';
import { useRouter } from '../app/router';
import { suggestedBreakMinutes } from '../lib/breaks';
import { type JobFailure, jobFailure, jobProgress } from '../lib/generation';
import { aboutHowLong } from '../lib/provider';
import { isJobActive } from '../lib/use-job';
import { useNow } from '../lib/use-now';
import {
  type WritingSubject,
  barValue,
  elapsedSince,
  readWritingProgress,
  writingHeadline,
} from '../lib/writing-progress';
import styles from './GenerationStatus.module.css';

export interface GenerationStatusProps {
  /** The job being followed, if one has been started. */
  job: Job | null;
  /** The request to start a job is on its way. */
  starting: boolean;
  /** Starting was refused before any job existed (for example, there is no key). */
  refusal: JobFailure | null;
  /** What is being made, as a phrase: "the lesson", "the suggestions". */
  subject: string;
  /** What kind of thing that is, for saying what is happening while it is written. */
  kind: WritingSubject;
  /** Shown while the job waits for its turn or has not reported anything yet. */
  waitingText: string;
  /**
   * About how long this kind of work takes where it is being done, in seconds, where the
   * core could say (`provider.status`). Said as "about", and what a break is sized by.
   */
  usualSeconds?: number | null;
  /**
   * The lesson this job is writing can be started already: what is still under way is its
   * pictures (ADR-031). Stopping then stops the pictures and keeps the lesson.
   */
  lessonReady?: boolean;
  onCancel: () => void;
  onRetry: () => void;
  /** Put a failure or cancellation away. */
  onDismiss: () => void;
}

/**
 * Work the AI provider is doing for the learner, in every state it can be in:
 * waiting, under way (with a way to stop it), failed (with what to do next), or
 * cancelled. Shows nothing once the work has succeeded; the caller shows the result.
 */
export function GenerationStatus({
  job,
  starting,
  refusal,
  subject,
  kind,
  waitingText,
  usualSeconds = null,
  lessonReady = false,
  onCancel,
  onRetry,
  onDismiss,
}: GenerationStatusProps) {
  const { navigate } = useRouter();

  if (starting || isJobActive(job)) {
    return (
      <UnderWay
        job={job}
        kind={kind}
        waitingText={waitingText}
        usualSeconds={usualSeconds}
        lessonReady={lessonReady}
        onCancel={onCancel}
      />
    );
  }

  const failure = refusal ?? jobFailure(job);
  if (failure) {
    return (
      <Callout
        tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
        title={`Couldn’t create ${subject}`}
        urgent
        actions={
          <>
            {failure.remedy === 'settings' ? (
              <Button
                size="small"
                variant="primary"
                onClick={() => navigate({ name: 'settings', tab: 'ai' })}
              >
                Open AI settings
              </Button>
            ) : null}
            {failure.remedy === 'retry' ? (
              <Button size="small" variant="primary" onClick={onRetry}>
                Try again
              </Button>
            ) : null}
            <Button size="small" variant="tertiary" onClick={onDismiss}>
              Dismiss
            </Button>
          </>
        }
      >
        {failure.message}
      </Callout>
    );
  }

  if (job?.status === 'cancelled') {
    return (
      <Callout
        title="Canceled"
        actions={
          <Button size="small" variant="tertiary" onClick={onDismiss}>
            Dismiss
          </Button>
        }
      >
        Nothing was added.
      </Callout>
    );
  }

  return null;
}

/**
 * Work that is under way: what it is doing just now, in the learner's terms (ADR-037). A
 * lesson or a list of concepts is seen taking shape, part by part, by the titles of what
 * has been written: never its words. A clock moves beside it, so that a model thinking for
 * a minute does not look like a program that has stopped.
 */
function UnderWay({
  job,
  kind,
  waitingText,
  usualSeconds,
  lessonReady,
  onCancel,
}: {
  job: Job | null;
  kind: WritingSubject;
  waitingText: string;
  usualSeconds: number | null;
  lessonReady: boolean;
  onCancel: () => void;
}) {
  const { navigate } = useRouter();
  const rest = useBreak();
  const now = useNow();

  const counted = job ? jobProgress(job, waitingText) : { value: undefined, message: waitingText };
  // Once the lesson can be started, what is left is its pictures, which count for themselves.
  const writing = lessonReady ? null : readWritingProgress(job);
  const headline = lessonReady ? counted.message : writingHeadline(writing, kind, counted.message);
  const value = lessonReady ? counted.value : barValue(job, writing, counted.value);
  const outline = writing?.stage === 'writing' ? writing.outline : [];
  const elapsed = lessonReady ? null : elapsedSince(job?.created_at, now);
  const noun = kind === 'suggestions' ? ['concept', 'concepts'] : ['part', 'parts'];
  const written =
    outline.length > 0
      ? `${outline.length} ${outline.length === 1 ? noun[0] : noun[1]} so far`
      : undefined;

  return (
    <Card padding="compact">
      <div className={styles.underWay}>
        <p className={styles.headline}>
          <span className={styles.headlineText}>{headline}</span>
          {/* Seen, not read out every second: the bar and the list say how far it is. */}
          {elapsed ? (
            <span className={cx(styles.clock, 'ad-tabular')} aria-hidden="true">
              {elapsed}
            </span>
          ) : null}
        </p>
        <ProgressBar label={headline} value={value} valueText={written} />
        {outline.length > 0 ? (
          <ol
            className={styles.outline}
            aria-label={kind === 'suggestions' ? 'Concepts so far' : 'Parts so far'}
            // Each title is said once, as it is written; the list is not read out again.
            aria-live="polite"
          >
            {outline.map((title, index) => {
              const current = index === outline.length - 1;
              return (
                <li
                  // Titles may repeat; their place in the list does not.
                  key={index}
                  className={cx(styles.part, current && styles.partNow)}
                  aria-current={current ? 'step' : undefined}
                >
                  {current ? (
                    <span className={styles.pulse} aria-hidden="true" />
                  ) : (
                    <Check className={styles.done} aria-hidden="true" />
                  )}
                  <span className={styles.partTitle}>{title}</span>
                </li>
              );
            })}
          </ol>
        ) : null}
        <div className={styles.bottom}>
          <p className={styles.note}>
            {lessonReady
              ? 'You can start the lesson now. Its pictures appear in it as they’re drawn.'
              : `${
                  usualSeconds
                    ? `Usually takes ${aboutHowLong(usualSeconds)}. `
                    : 'This can take a few minutes. '
                }You’ll be notified when it’s ready.`}
          </p>
          <div className={styles.actions}>
            {/* Minutes of waiting are better spent away from the screen. Once the lesson
                can be started there is nothing left to wait for. */}
            {lessonReady ? null : (
              <Button
                size="small"
                icon={<Coffee />}
                onClick={() => {
                  if (!rest.times) rest.start(suggestedBreakMinutes(usualSeconds));
                  // Back here afterwards: this is where what is being written will be.
                  rest.returnVia(null);
                  navigate({ name: 'break' });
                }}
              >
                {rest.times ? 'Back to your break' : 'Take a break'}
              </Button>
            )}
            {lessonReady ? (
              <Button
                size="small"
                variant="tertiary"
                disabled={!job}
                aria-label="Stop drawing pictures"
                onClick={onCancel}
              >
                Stop
              </Button>
            ) : (
              <Button size="small" variant="tertiary" disabled={!job} onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
