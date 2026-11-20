import { useCallback, useState } from 'react';

import type { Job } from '@adle/contracts';
import { useToast } from '@adle/design-system';

import { callCore, describeError } from './core-client';
import { type JobFailure, refusalOf } from './generation';
import { type CourseJobs, useCourseJobs } from './use-course-jobs';

export interface Generation {
  jobs: CourseJobs;
  /** What is being started right now, by what it is about: the course, or a concept. */
  starting: ReadonlySet<string>;
  /** Why starting was refused, by what it was about. */
  refusals: ReadonlyMap<string, JobFailure>;
  /** Start a job about `subject`, and remember why if it could not be started. */
  begin: (subject: string, start: () => Promise<Job>) => Promise<void>;
  /** Put a finished job, or a refusal, away. */
  putAway: (subject: string, job: Job | null) => void;
  cancel: (job: Job | null) => void;
}

/**
 * The work the AI provider does for one course, as a screen needs it: start
 * something, follow it, stop it, and put away what has finished. One place for
 * every screen that starts such work, so each behaves the same way.
 */
export function useGeneration(courseId: string, onFinished: (job: Job) => void): Generation {
  const toast = useToast();
  const jobs = useCourseJobs(courseId, onFinished);
  const [starting, setStarting] = useState<ReadonlySet<string>>(new Set());
  const [refusals, setRefusals] = useState<ReadonlyMap<string, JobFailure>>(new Map());
  const { track, forget } = jobs;

  const clearRefusal = useCallback((subject: string) => {
    setRefusals((current) => {
      if (!current.has(subject)) return current;
      const next = new Map(current);
      next.delete(subject);
      return next;
    });
  }, []);

  const begin = useCallback(
    async (subject: string, start: () => Promise<Job>): Promise<void> => {
      clearRefusal(subject);
      setStarting((current) => new Set(current).add(subject));
      try {
        track(await start());
      } catch (error) {
        setRefusals((current) => new Map(current).set(subject, refusalOf(error)));
      } finally {
        setStarting((current) => {
          const next = new Set(current);
          next.delete(subject);
          return next;
        });
      }
    },
    [clearRefusal, track],
  );

  const putAway = useCallback(
    (subject: string, job: Job | null): void => {
      if (job) forget(job.id);
      clearRefusal(subject);
    },
    [clearRefusal, forget],
  );

  const cancel = useCallback(
    (job: Job | null): void => {
      if (!job) return;
      callCore('jobs.cancel', { path: { job_id: job.id } }).catch((error: unknown) => {
        toast.show({
          tone: 'danger',
          title: 'It could not be cancelled',
          description: describeError(error),
        });
      });
    },
    [toast],
  );

  return { jobs, starting, refusals, begin, putAway, cancel };
}
