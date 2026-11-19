import { useEffect, useRef, useState } from 'react';

import type { Job } from '@adle/contracts';

import { callCore } from './core-client';

const POLL_INTERVAL_MS = 400;
const ACTIVE = new Set(['queued', 'running']);

export function isJobActive(job: Job | null): boolean {
  return job !== null && ACTIVE.has(job.status);
}

/**
 * Follow a background job until it finishes.
 *
 * Starts from the job as returned when it was created and polls the core while
 * it is queued or running. `onFinished` fires once, with the final state.
 */
export function useJob(initial: Job | null, onFinished?: (job: Job) => void): Job | null {
  const [job, setJob] = useState<Job | null>(initial);
  const finishedCallback = useRef(onFinished);
  useEffect(() => {
    finishedCallback.current = onFinished;
  });

  // Adopt a newly started job.
  const [trackedId, setTrackedId] = useState(initial?.id ?? null);
  if ((initial?.id ?? null) !== trackedId) {
    setTrackedId(initial?.id ?? null);
    setJob(initial);
  }

  const jobId = job?.id ?? null;
  const active = isJobActive(job);
  useEffect(() => {
    if (jobId === null || !active) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      callCore('jobs.get', { path: { job_id: jobId } }).then(
        (next) => {
          if (cancelled) return;
          setJob(next);
          if (!isJobActive(next)) finishedCallback.current?.(next);
        },
        () => {
          // A failed poll is retried on the next tick; the job itself is unaffected.
        },
      );
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId, active]);

  return job;
}
