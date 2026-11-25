import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import type { Hypothesis } from '@adle/contracts';

export const SETTINGS_TABS = ['ai', 'learning', 'appearance', 'privacy', 'about'] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

export const COURSE_TABS = ['learn', 'curriculum', 'sources', 'film'] as const;
export type CourseTab = (typeof COURSE_TABS)[number];

/** A kind of mistake a set of questions can be about. */
export type MistakeKind = Hypothesis['kind'];

/** Every destination in the app. Adding a screen means adding a variant here. */
export type Route =
  | { name: 'home' }
  | { name: 'course'; courseId: string; tab: CourseTab }
  | { name: 'lesson'; courseId: string; lessonId: string }
  /** A few questions on one concept: practice, a review, or a check on a suspected mistake. */
  | { name: 'practice'; courseId: string; conceptId: string; about?: MistakeKind }
  /** A few minutes away from the screen, while something is written or between lessons. */
  | { name: 'break' }
  | { name: 'settings'; tab: SettingsTab };

interface RouterValue {
  route: Route;
  /** Goes up with every navigation, so a screen can start afresh when it is opened again. */
  visit: number;
  navigate: (route: Route) => void;
  back: () => void;
}

const RouterContext = createContext<RouterValue | null>(null);

function isRoute(value: unknown): value is Route {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as {
    name?: unknown;
    tab?: unknown;
    courseId?: unknown;
    lessonId?: unknown;
    conceptId?: unknown;
    about?: unknown;
  };
  switch (candidate.name) {
    case 'home':
    case 'break':
      return true;
    case 'lesson':
      return typeof candidate.courseId === 'string' && typeof candidate.lessonId === 'string';
    case 'practice':
      return (
        typeof candidate.courseId === 'string' &&
        typeof candidate.conceptId === 'string' &&
        (candidate.about === undefined || typeof candidate.about === 'string')
      );
    case 'settings':
      return (SETTINGS_TABS as readonly unknown[]).includes(candidate.tab);
    case 'course':
      return (
        typeof candidate.courseId === 'string' &&
        (COURSE_TABS as readonly unknown[]).includes(candidate.tab)
      );
    default:
      return false;
  }
}

/**
 * A minimal router. The route lives in `history.state` (the URL never changes
 * inside the desktop shell), which keeps the back and forward buttons working.
 */
export function RouterProvider({ initial, children }: { initial: Route; children: ReactNode }) {
  const [route, setRoute] = useState<Route>(() =>
    isRoute(window.history.state) ? window.history.state : initial,
  );
  const [visit, setVisit] = useState(0);

  useEffect(() => {
    if (!isRoute(window.history.state)) window.history.replaceState(initial, '');
    const onPopState = (event: PopStateEvent): void => {
      if (!isRoute(event.state)) return;
      setRoute(event.state);
      setVisit((count) => count + 1);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [initial]);

  const navigate = useCallback((next: Route) => {
    window.history.pushState(next, '');
    setRoute(next);
    setVisit((count) => count + 1);
    // Each navigation starts at the top with focus on the new page.
    document.getElementById('ad-main')?.focus({ preventScroll: true });
    document.getElementById('ad-main')?.scrollTo({ top: 0 });
  }, []);

  const back = useCallback(() => window.history.back(), []);

  const value = useMemo(() => ({ route, visit, navigate, back }), [route, visit, navigate, back]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) throw new Error('useRouter must be used inside <RouterProvider>.');
  return value;
}
