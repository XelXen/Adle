import { type RefObject, useCallback, useEffect, useSyncExternalStore } from 'react';

function subscribe(onChange: () => void): () => void {
  document.addEventListener('fullscreenchange', onChange);
  return () => document.removeEventListener('fullscreenchange', onChange);
}

export interface Fullscreen {
  /** The element fills the screen now. */
  active: boolean;
  /** Fill the screen with the element, or give the screen back. */
  toggle: () => void;
  leave: () => void;
}

/**
 * One element of the page filling the whole screen, by the browser's own means: Escape
 * always gives the screen back, and so does the system. The main process allows this to
 * the app's own page and to nothing else (`mayFillTheScreen` in `electron/main/security.ts`).
 */
export function useFullscreen(target: RefObject<HTMLElement | null>): Fullscreen {
  const current = useSyncExternalStore(subscribe, () => document.fullscreenElement);
  const active = current !== null && current === target.current;

  const leave = useCallback((): void => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
  }, []);
  const toggle = useCallback((): void => {
    const element = target.current;
    if (!element) return;
    if (document.fullscreenElement === element) leave();
    // Refused (no press behind the request, or the system says no): the page stays as it is.
    else void element.requestFullscreen().catch(() => undefined);
  }, [leave, target]);

  // A screen that goes away takes its hold on the screen with it.
  useEffect(() => leave, [leave]);

  return { active, toggle, leave };
}

/**
 * Mark an element with `data-still` once the pointer and the keyboard have been still for
 * a while. Controls laid over a picture that fills the screen get out of its way when
 * nothing is being done with them; a style sheet decides what that looks like. Written on
 * the element and not kept as state: the pointer moves far more often than anything here
 * needs to be drawn again.
 */
export function useStillness(
  target: RefObject<HTMLElement | null>,
  enabled: boolean,
  afterMs = 2600,
): void {
  useEffect(() => {
    const element = target.current;
    if (!enabled || !element) return undefined;
    const settle = (): void => element.setAttribute('data-still', 'true');
    let timer = window.setTimeout(settle, afterMs);
    const stir = (): void => {
      element.removeAttribute('data-still');
      window.clearTimeout(timer);
      timer = window.setTimeout(settle, afterMs);
    };
    const events = ['pointermove', 'pointerdown', 'keydown', 'focusin'] as const;
    for (const name of events) window.addEventListener(name, stir, { passive: true });
    return () => {
      window.clearTimeout(timer);
      for (const name of events) window.removeEventListener(name, stir);
      element.removeAttribute('data-still');
    };
  }, [target, enabled, afterMs]);
}
