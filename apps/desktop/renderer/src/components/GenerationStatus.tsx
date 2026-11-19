import type { Job } from '@adle/contracts';
import { Button, Callout, Card, ProgressBar, Stack } from '@adle/design-system';

import { useRouter } from '../app/router';
import { type JobFailure, jobFailure, jobProgress } from '../lib/generation';
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
  onCancel,
  onRetry,
  onDismiss,
}: GenerationStatusProps) {
  const { navigate } = useRouter();

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
              This can take a minute or two. You can keep using Adle while it works.
            </p>
          </div>
          <Button size="small" disabled={!job} onClick={onCancel}>
            Cancel
          </Button>
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
