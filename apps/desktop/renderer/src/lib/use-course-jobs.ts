import { useCallback, useEffect, useRef, useState } from 'react';

import type { Job } from '@adle/contracts';

import { callCore } from './core-client';
import { isJobActive } from './use-job';

const POLL_INTERVAL_MS = 500;

export interface CourseJobs {
  /** Every job this screen knows about: still going, or finished since it was opened. */
  jobs: readonly Job[];
  /** Follow a job that was just started (or one found finished that still matters). */
  track: (job: Job) => void;
  /** Stop showing a job that has finished. */
  forget: (jobId: string) => void;
  /** The job of this kind about this subject, if this screen knows of one. */
  find: (kind: string, subjectId: string) => Job | null;
}

/**
 * Follow the background work of one course.
 *
 * Work that was already under way when the screen opened is picked up, so
 * leaving a course and coming back does not lose sight of a lesson that is
 * being written. `onFinished` fires once for each job that ends while the
 * screen is open. `onUsable` fires once for a job that has something to use before it
 * ends: a lesson that can be started while its pictures are still being drawn.
 */
export function useCourseJobs(
  courseId: string,
  onFinished: (job: Job) => void,
  onUsable?: (job: Job) => void,
): CourseJobs {
  const [jobs, setJobs] = useState<ReadonlyMap<string, Job>>(new Map());
  const finishedCallback = useRef(onFinished);
  const usableCallback = useRef(onUsable);
  const reported = useRef(new Set<string>());
  const usable = useRef(new Set<string>());
  useEffect(() => {
    finishedCallback.current = onFinished;
    usableCallback.current = onUsable;
  });

  useEffect(() => {
    let cancelled = false;
    callCore('jobs.list_active', { path: { course_id: courseId } }).then(
      (found) => {
        if (cancelled) return;
        // What was usable before this screen opened is on the screen already: it is not
        // news here, and is not said again.
        for (const job of found.jobs) if (job.result != null) usable.current.add(job.id);
        setJobs((current) => {
          const next = new Map(current);
          // What this screen already follows is at least as fresh as the list.
          for (const job of found.jobs) if (!next.has(job.id)) next.set(job.id, job);
          return next;
        });
      },
      () => {
        // Nothing to pick up, or the core is not reachable: starting new work still works.
      },
    );
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const activeIds = [...jobs.values()]
    .filter((job) => isJobActive(job))
    .map((job) => job.id)
    .sort()
    .join(',');
  useEffect(() => {
    if (activeIds === '') return;
    const ids = activeIds.split(',');
    let cancelled = false;
    const timer = window.setInterval(() => {
      for (const id of ids) {
        callCore('jobs.get', { path: { job_id: id } }).then(
          (next) => {
            if (cancelled) return;
            setJobs((current) => new Map(current).set(id, next));
            if (isJobActive(next) && next.result != null && !usable.current.has(id)) {
              usable.current.add(id);
              usableCallback.current?.(next);
            }
            if (!isJobActive(next) && !reported.current.has(id)) {
              reported.current.add(id);
              finishedCallback.current(next);
            }
          },
          () => {
            // A failed poll is retried on the next tick; the job itself is unaffected.
          },
        );
      }
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeIds]);

  const track = useCallback((job: Job) => {
    setJobs((current) => new Map(current).set(job.id, job));
  }, []);
  const forget = useCallback((jobId: string) => {
    setJobs((current) => {
      if (!current.has(jobId)) return current;
      const next = new Map(current);
      next.delete(jobId);
      return next;
    });
  }, []);

  const list = [...jobs.values()];
  const find = (kind: string, subjectId: string): Job | null => {
    const matching = list.filter((job) => job.kind === kind && job.subject_id === subjectId);
    // A job that is still going matters more than one that has finished.
    return matching.find((job) => isJobActive(job)) ?? matching.at(-1) ?? null;
  };

  return { jobs: list, track, forget, find };
}
