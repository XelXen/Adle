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
import { KIND_FILM, KIND_FILM_SETUP } from '../lib/films';
import { useApp } from './AppContext';
import { useRouter } from './router';

interface FilmWatchValue {
  /** Films being made, and the film maker being set up, in any course, oldest first. */
  jobs: readonly Job[];
  /** Look again now: something was just started. */
  refresh: () => void;
}

const FilmWatchContext = createContext<FilmWatchValue | null>(null);

/** How often to look while a film is being made, and while none is. */
const BUSY_MS = 3000;
const IDLE_MS = 8000;
const NONE: readonly Job[] = [];

/**
 * Films being made, wherever the learner is in the app (ADR-065).
 *
 * A film takes an hour or more, and the learner is told they need not wait for it. This
 * keeps an eye on it for them: the rail says one is being made, and when it is ready (or
 * could not be finished) the app says so, and asks the operating system to say so too if
 * Adle is not what they are looking at. Said once, unless the course's Film tab is in
 * front of them: it shows that by itself.
 */
export function FilmWatchProvider({ children }: { children: ReactNode }) {
  const { coreStatus } = useApp();
  const { route } = useRouter();
  const toast = useToast();
  const [jobs, setJobs] = useState<readonly Job[]>(NONE);
  const [tick, setTick] = useState(0);
  const where = useRef(route);
  useEffect(() => {
    where.current = route;
  });
  const known = useRef<ReadonlySet<string>>(new Set());
  const said = useRef(new Set<string>());
  const ready = coreStatus.state === 'ready';
  const busy = jobs.length > 0;

  const announce = useCallback(
    (job: Job) => {
      if (said.current.has(job.id)) return;
      if (job.status !== 'succeeded' && job.status !== 'failed') return;
      said.current.add(job.id);
      const here = where.current;
      if (job.kind === KIND_FILM_SETUP) {
        // A Film tab in front of the learner says it itself.
        if (here.name === 'course' && here.tab === 'film') return;
        toast.show(
          job.status === 'succeeded'
            ? { tone: 'success', title: 'The film maker is set up' }
            : {
                tone: 'danger',
                title: 'Couldn’t set up the film maker',
                description: job.error_message ?? 'Check the connection and try again.',
              },
        );
        return;
      }
      if (job.kind !== KIND_FILM) return;
      const showing =
        here.name === 'course' && here.courseId === job.course_id && here.tab === 'film';
      if (job.status === 'succeeded') {
        void getBridge().app.notify('film_ready');
        if (!showing) {
          toast.show({
            tone: 'success',
            title: 'Your film is ready',
            description: 'Open the course’s Film tab to watch it.',
          });
        }
        return;
      }
      void getBridge().app.notify('writing_stopped');
      if (!showing) {
        toast.show({
          tone: 'danger',
          title: 'Couldn’t finish the film',
          description: job.error_message ?? 'What was made is kept. Continue it from the Film tab.',
        });
      }
    },
    [toast],
  );

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const look = (): void => {
      callCore('films.making').then(
        (list) => {
          if (cancelled) return;
          const now = new Set(list.jobs.map((job) => job.id));
          const gone = [...known.current].filter((id) => !now.has(id));
          known.current = now;
          setJobs(list.jobs);
          for (const id of gone) {
            callCore('jobs.get', { path: { job_id: id } }).then(announce, () => {
              // Its course was removed meanwhile: there is nothing to say.
            });
          }
        },
        () => {
          // Looked at again on the next turn; the film itself is unaffected.
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
  const shown = ready ? jobs : NONE;
  const value = useMemo(() => ({ jobs: shown, refresh }), [shown, refresh]);
  return <FilmWatchContext.Provider value={value}>{children}</FilmWatchContext.Provider>;
}

export function useFilmWatch(): FilmWatchValue {
  const value = useContext(FilmWatchContext);
  if (!value) throw new Error('useFilmWatch must be used inside <FilmWatchProvider>.');
  return value;
}
