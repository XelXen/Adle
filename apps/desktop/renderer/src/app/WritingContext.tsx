import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import type { Job } from '@adle/contracts';
import { useToast } from '@adle/design-system';

import { getBridge } from '../lib/bridge';
import { callCore } from '../lib/core-client';
import { jobFailure, KIND_LESSON, KIND_PROPOSAL, readLessonOutcome } from '../lib/generation';
import { useApp } from './AppContext';
import { useRouter } from './router';

interface WritingValue {
  /** Lessons and lists of concepts being written, in any course, oldest first. */
  jobs: readonly Job[];
  /** The last piece of long work that finished while the app was open, until put away. */
  finished: Job | null;
  /** Read the list again now: something was just started. */
  refresh: () => void;
  /** Put the last finished piece of work away: the learner has seen it. */
  acknowledge: () => void;
}

const WritingContext = createContext<WritingValue | null>(null);

/** How often to look while something is being written, and while nothing is. */
const BUSY_MS = 1500;
const IDLE_MS = 6000;

/**
 * What is being written for the learner, wherever they are in the app (ADR-026).
 *
 * A lesson can take minutes to write, and the learner is told they need not wait for
 * it. This keeps an eye on it for them: the rail says that something is on its way, and
 * when it arrives (or cannot be finished) the app says so, and asks the operating
 * system to say so too if Adle is not what they are looking at.
 *
 * The screen a piece of work was started from shows its progress and its outcome
 * itself; this adds nothing there, so nothing is said twice.
 */
export function WritingProvider({ children }: { children: ReactNode }) {
  const { coreStatus } = useApp();
  const { route } = useRouter();
  const toast = useToast();
  const [jobs, setJobs] = useState<readonly Job[]>([]);
  const [finished, setFinished] = useState<Job | null>(null);
  const [tick, setTick] = useState(0);
  /** Where the learner is now, for the moment something finishes. */
  const where = useRef(route);
  useEffect(() => {
    where.current = route;
  });
  const known = useRef<ReadonlySet<string>>(new Set());
  /** False once the app is closing. Not the same as one turn of looking being over. */
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const ready = coreStatus.state === 'ready';
  const busy = jobs.length > 0;

  const announce = useCallback(
    (job: Job) => {
      const here = where.current;
      // The course it belongs to shows it already, and so does a break taken to wait for it.
      const shownHere =
        here.name === 'break' || (here.name === 'course' && here.courseId === job.course_id);
      if (job.status === 'succeeded') {
        setFinished(job);
        const lesson = job.kind === KIND_LESSON;
        void getBridge().app.notify(lesson ? 'lesson_ready' : 'concepts_ready');
        if (shownHere) return;
        toast.show({
          tone: 'success',
          title: lesson ? 'Your lesson is ready' : 'Suggested concepts are ready',
          description: lesson
            ? (readLessonOutcome(job)?.title ?? undefined)
            : 'Open the course to look at them.',
        });
      } else if (job.status === 'failed') {
        setFinished(job);
        void getBridge().app.notify('writing_stopped');
        if (shownHere) return;
        toast.show({
          tone: 'danger',
          title:
            job.kind === KIND_LESSON
              ? 'The lesson could not be written'
              : 'The suggestions could not be made',
          description: jobFailure(job)?.message,
        });
      }
    },
    [toast],
  );

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const look = (): void => {
      callCore('jobs.list_writing').then(
        (list) => {
          if (cancelled) return;
          const now = new Set(list.jobs.map((job) => job.id));
          const gone = [...known.current].filter((id) => !now.has(id));
          known.current = now;
          setJobs(list.jobs);
          for (const id of gone) {
            callCore('jobs.get', { path: { job_id: id } }).then(
              (job) => {
                // Said even if this turn of looking has ended meanwhile: the list going
                // empty is exactly what ends it, and exactly when there is something to say.
                if (alive.current && (job.kind === KIND_LESSON || job.kind === KIND_PROPOSAL)) {
                  announce(job);
                }
              },
              () => {
                // The course it belonged to was removed meanwhile: there is nothing to say.
              },
            );
          }
        },
        () => {
          // Looked at again on the next turn; the work itself is unaffected.
        },
      );
    };
    look();
    const timer = window.setInterval(look, busy ? BUSY_MS : IDLE_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [ready, busy, tick, announce]);

  const refresh = useCallback(() => setTick((count) => count + 1), []);
  const acknowledge = useCallback(() => setFinished(null), []);

  const value = useMemo(
    () => ({ jobs, finished, refresh, acknowledge }),
    [jobs, finished, refresh, acknowledge],
  );
  return <WritingContext.Provider value={value}>{children}</WritingContext.Provider>;
}

export function useWriting(): WritingValue {
  const value = useContext(WritingContext);
  if (!value) throw new Error('useWriting must be used inside <WritingProvider>.');
  return value;
}
