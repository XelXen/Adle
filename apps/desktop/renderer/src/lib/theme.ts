import { useSyncExternalStore } from 'react';

import type { SceneTheme } from '@adle/event-protocol';

import type { UiState } from './bridge';

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

/**
 * Pastel and Pastel dark (ADR-074): the page is marked, and told the learner's hue, and
 * the tokens do the rest. The light or dark scheme still comes from the shell, as above.
 * Set through the CSSOM, which the page's Content Security Policy allows.
 */
export function applyPalette(
  ui: Pick<UiState, 'theme' | 'pastelHue'>,
  root: HTMLElement = document.documentElement,
): void {
  if (ui.theme === 'pastel' || ui.theme === 'pastel-dark') {
    root.dataset.adPalette = 'pastel';
    root.style.setProperty('--ad-pastel-hue', String(ui.pastelHue));
  } else {
    delete root.dataset.adPalette;
    root.style.removeProperty('--ad-pastel-hue');
  }
}
