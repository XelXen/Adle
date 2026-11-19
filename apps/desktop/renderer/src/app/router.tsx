import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

export const SETTINGS_TABS = ['ai', 'learning', 'appearance', 'privacy', 'about'] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

export const COURSE_TABS = ['curriculum', 'sources'] as const;
export type CourseTab = (typeof COURSE_TABS)[number];

/** Every destination in the app. Adding a screen means adding a variant here. */
export type Route =
  | { name: 'home' }
  | { name: 'course'; courseId: string; tab: CourseTab }
  | { name: 'lesson'; courseId: string; lessonId: string }
  | { name: 'settings'; tab: SettingsTab };

interface RouterValue {
  route: Route;
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
  };
  switch (candidate.name) {
    case 'home':
      return true;
    case 'lesson':
      return typeof candidate.courseId === 'string' && typeof candidate.lessonId === 'string';
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

  useEffect(() => {
    if (!isRoute(window.history.state)) window.history.replaceState(initial, '');
    const onPopState = (event: PopStateEvent): void => {
      if (isRoute(event.state)) setRoute(event.state);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [initial]);

  const navigate = useCallback((next: Route) => {
    window.history.pushState(next, '');
    setRoute(next);
    // Each navigation starts at the top with focus on the new page.
    document.getElementById('ad-main')?.focus({ preventScroll: true });
    document.getElementById('ad-main')?.scrollTo({ top: 0 });
  }, []);

  const back = useCallback(() => window.history.back(), []);

  const value = useMemo(() => ({ route, navigate, back }), [route, navigate, back]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) throw new Error('useRouter must be used inside <RouterProvider>.');
  return value;
}
