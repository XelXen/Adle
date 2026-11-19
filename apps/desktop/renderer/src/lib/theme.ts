import { useSyncExternalStore } from 'react';

import type { SceneTheme } from '@adle/event-protocol';

const DARK_QUERY = '(prefers-color-scheme: dark)';
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const media = window.matchMedia(query);
      media.addEventListener('change', notify);
      return () => media.removeEventListener('change', notify);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/**
 * The theme actually in effect. The desktop shell maps the learner's choice
 * (system / light / dark) onto `prefers-color-scheme`, so this is the single
 * source of truth for anything that cannot read CSS variables, such as scenes.
 */
export function useResolvedTheme(): SceneTheme {
  return useMediaQuery(DARK_QUERY) ? 'dark' : 'light';
}

export function usePrefersReducedMotion(): boolean {
  return useMediaQuery(REDUCED_MOTION_QUERY);
}
