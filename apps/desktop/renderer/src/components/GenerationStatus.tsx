import { Coffee } from 'lucide-react';

import type { Job } from '@adle/contracts';
import { Button, Callout, Card, ProgressBar, Stack } from '@adle/design-system';

import { useBreak } from '../app/BreakContext';
import { useRouter } from '../app/router';
import { suggestedBreakMinutes } from '../lib/breaks';
import { type JobFailure, jobFailure, jobProgress } from '../lib/generation';
import { aboutHowLong } from '../lib/provider';
import { isJobActive } from '../lib/use-job';
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
  /** Shown while the job waits for its turn or has not reported anything yet. */
  waitingText: string;
  /**
   * About how long this kind of work takes where it is being done, in seconds, where the
   * core could say (`provider.status`). Said as "about", and what a break is sized by.
   */
  usualSeconds?: number | null;
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
  waitingText,
  usualSeconds = null,
  onCancel,
  onRetry,
  onDismiss,
}: GenerationStatusProps) {
  const { navigate } = useRouter();
  const rest = useBreak();

  if (starting || isJobActive(job)) {
    const progress = job
      ? jobProgress(job, waitingText)
      : { value: undefined, message: waitingText };
    const steps = job && job.progress_total > 0 ? job.progress_total : 0;
    return (
      <Card padding="compact">
        <Stack direction="row" gap={4} align="center">
          <div className={styles.grow}>
            <ProgressBar
              label={progress.message}
              showLabel
              value={progress.value}
              valueText={
                job && steps > 0
                  ? `Step ${Math.min(job.progress_done + 1, steps)} of ${steps}`
                  : undefined
              }
            />
            <p className={styles.note}>
              {usualSeconds
                ? `This usually takes ${aboutHowLong(usualSeconds)}. `
                : 'This can take a few minutes. '}
              You do not have to wait here: Adle will tell you when it is ready.
            </p>
          </div>
          <div className={styles.actions}>
            {/* Minutes of waiting are better spent away from the screen. */}
            <Button
              size="small"
              icon={<Coffee />}
              onClick={() => {
                if (!rest.times) rest.start(suggestedBreakMinutes(usualSeconds));
                navigate({ name: 'break' });
              }}
            >
              {rest.times ? 'Back to your break' : 'Take a break'}
            </Button>
            <Button size="small" variant="tertiary" disabled={!job} onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </Stack>
      </Card>
    );
  }

  const failure = refusal ?? jobFailure(job);
  if (failure) {
    return (
      <Callout
        tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
        title={`${subject.charAt(0).toUpperCase()}${subject.slice(1)} could not be made`}
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
        title="Cancelled"
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
