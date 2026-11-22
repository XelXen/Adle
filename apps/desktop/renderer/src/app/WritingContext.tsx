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
import {
  hasLessonToStart,
  isWritingTheRest,
  jobFailure,
  KIND_LESSON,
  KIND_PROPOSAL,
  readLessonOutcome,
  titled,
} from '../lib/generation';
import { useApp } from './AppContext';
import { type Route, useRouter } from './router';

interface WritingValue {
  /** Lessons and lists of concepts being written, in any course, oldest first. */
  jobs: readonly Job[];
  /**
   * The last piece of long work that finished while the learner was somewhere that did not
   * show it, until they have seen it.
   */
  finished: Job | null;
  /** When it finished, by this computer's clock. */
  finishedAt: number | null;
  /** Read the list again now: something was just started. */
  refresh: () => void;
  /** Put the last finished piece of work away: the learner has seen it. */
  acknowledge: () => void;
  /**
   * Whether the learner has been told that the lesson this job wrote is ready, wherever
   * in the app that was. It is said once (ADR-031): a tab of the course that hears of the
   * same lesson later has only something to add, if anything.
   */
  wasTold: (jobId: string) => boolean;
  /** A screen has just told them. */
  markTold: (jobId: string) => void;
}

const WritingContext = createContext<WritingValue | null>(null);

/** How often to look while something is being written, and while nothing is. */
const BUSY_MS = 1500;
const IDLE_MS = 6000;

const NO_JOBS: readonly Job[] = [];

/**
 * Whether the screen the learner is on shows what became of a piece of work by itself.
 *
 * A break taken to wait for it does. So does the tab of its course that it changes: a
 * lesson appears under Learn and under Curriculum, suggested concepts under Curriculum.
 * The Materials tab shows neither.
 */
export function showsOutcome(here: Route, job: Pick<Job, 'kind' | 'course_id'>): boolean {
  if (here.name === 'break') return true;
  if (here.name !== 'course' || here.courseId !== job.course_id) return false;
  return job.kind === KIND_LESSON ? here.tab !== 'sources' : here.tab === 'curriculum';
}

/** Whether the learner has arrived where a finished piece of work is to be found. */
export function isWhereItIs(here: Route, job: Job): boolean {
  if (here.name === 'course') return here.courseId === job.course_id;
  if (here.name === 'lesson') return here.lessonId === readLessonOutcome(job)?.lessonId;
  return false;
}

/**
 * Whether the screen in front of the learner says by itself that this work has something
 * to use, and so keeps count of having said it. A tab of the course does. A break shows
 * it without anyone having to say it; anywhere else, the app-wide watch says it.
 */
export function leavesTellingToScreen(here: Route, job: Pick<Job, 'kind' | 'course_id'>): boolean {
  return here.name !== 'break' && showsOutcome(here, job);
}

/**
 * What there is to say about a piece of long work now: it has something to use, it could
 * not be finished, or nothing yet.
 *
 * A lesson has something to use as soon as its first part is written, while the rest of
 * it is written (ADR-048) and its pictures are drawn (ADR-031). That is when it is said,
 * and it is said once.
 */
export function newsOf(job: Job): 'usable' | 'failed' | null {
  if (job.status === 'succeeded' || hasLessonToStart(job)) return 'usable';
  return job.status === 'failed' ? 'failed' : null;
}

/** The words for something that arrived, for a learner who is somewhere else in the app. */
export function arrivalNotice(job: Job): { title: string; description: string | undefined } {
  if (job.kind !== KIND_LESSON) {
    return {
      title: 'Suggested concepts are ready',
      description: 'Open the course to review them.',
    };
  }
  const outcome = readLessonOutcome(job);
  // Begun at its first part, the rest of it is still being written (ADR-048); or it is all
  // written and its pictures are still being drawn (ADR-031).
  const still = isWritingTheRest(job)
    ? 'The rest of it is being written.'
    : outcome && outcome.picturesPending > 0
      ? 'Its pictures are still being drawn.'
      : '';
  const words = titled(outcome?.title ?? '', [still]);
  return { title: 'Your lesson is ready', description: words || undefined };
}

/**
 * What is being written for the learner, wherever they are in the app (ADR-026).
 *
 * A lesson can take minutes to write, and the learner is told they need not wait for
 * it. This keeps an eye on it for them: the rail says that something is on its way, and
 * when it arrives (or cannot be finished) the app says so, and asks the operating
 * system to say so too if Adle is not what they are looking at.
 *
 * Something that arrived is said once, unless the screen in front of the learner shows
 * it already. Something that could not be finished is always said: the place that would
 * show it may be a part of the page they are not looking at.
 */
export function WritingProvider({ children }: { children: ReactNode }) {
  const { coreStatus } = useApp();
  const { route } = useRouter();
  const toast = useToast();
  const [jobs, setJobs] = useState<readonly Job[]>(NO_JOBS);
  const [arrived, setArrived] = useState<{ job: Job; at: number } | null>(null);
  const [tick, setTick] = useState(0);
  /** Where the learner is now, for the moment something finishes. */
  const where = useRef(route);
  useEffect(() => {
    where.current = route;
  });
  const known = useRef<ReadonlySet<string>>(new Set());
  /** What has been said already, so that nothing is said twice. */
  const said = useRef(new Set<string>());
  /** The jobs whose lesson the learner has been told is ready, here or on a screen. */
  const told = useRef(new Set<string>());
  const wasTold = useCallback((jobId: string) => told.current.has(jobId), []);
  const markTold = useCallback((jobId: string) => {
    told.current.add(jobId);
  }, []);
  /** Counts the times the list has been asked for: only the latest answer is used. */
  const asked = useRef(0);
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
      if (said.current.has(job.id)) return;
      const news = newsOf(job);
      if (news === null) return;
      said.current.add(job.id);
      const here = where.current;
      const lesson = job.kind === KIND_LESSON;
      // Kept for a break to show, unless the learner is already where it is.
      if (!isWhereItIs(here, job)) setArrived({ job, at: Date.now() });

      if (news === 'usable') {
        void getBridge().app.notify(lesson ? 'lesson_ready' : 'concepts_ready');
        // Told here, or shown by a break: a tab of the course that hears of it later does
        // not say it again. A tab that is showing it now says it itself.
        if (!leavesTellingToScreen(here, job)) told.current.add(job.id);
        if (showsOutcome(here, job)) return;
        toast.show({ tone: 'success', ...arrivalNotice(job) });
        return;
      }
      void getBridge().app.notify('writing_stopped');
      // A break shows it in full, with the way to the course beside it.
      if (here.name === 'break') return;
      toast.show({
        tone: 'danger',
        title: lesson ? 'Couldn’t write the lesson' : 'Couldn’t suggest concepts',
        description: jobFailure(job)?.message,
      });
    },
    [toast],
  );

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const look = (): void => {
      asked.current += 1;
      const mine = asked.current;
      callCore('jobs.list_writing').then(
        (list) => {
          // An answer that was overtaken by a later one says nothing new, and could
          // bring back something that has finished since.
          if (cancelled || mine !== asked.current) return;
          const now = new Set(list.jobs.map((job) => job.id));
          const gone = [...known.current].filter((id) => !now.has(id));
          known.current = now;
          setJobs(list.jobs);
          // Work that is still under way and already has something to start.
          for (const job of list.jobs) if (hasLessonToStart(job)) announce(job);
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
  const acknowledge = useCallback(() => setArrived(null), []);

  // Once the learner is where it is, it has been seen: a later break has nothing to say of
  // it. Put away while rendering, so that not one frame shows it in the wrong place.
  if (arrived !== null && isWhereItIs(route, arrived.job)) setArrived(null);
  const finished = arrived?.job ?? null;
  const finishedAt = arrived?.at ?? null;

  // While the core is away nothing is being written, whatever the list last said.
  const shown = ready ? jobs : NO_JOBS;
  const value = useMemo(
    () => ({ jobs: shown, finished, finishedAt, refresh, acknowledge, wasTold, markTold }),
    [shown, finished, finishedAt, refresh, acknowledge, wasTold, markTold],
  );
  return <WritingContext.Provider value={value}>{children}</WritingContext.Provider>;
}

export function useWriting(): WritingValue {
  const value = useContext(WritingContext);
  if (!value) throw new Error('useWriting must be used inside <WritingProvider>.');
  return value;
}
