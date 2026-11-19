import { readFileSync } from 'node:fs';
import path from 'node:path';

import type { Page } from '@playwright/test';

import { desktopDir, repoRoot } from './app';

export const exampleScene = (name: string): string =>
  readFileSync(path.join(repoRoot, 'skills', 'wanim-scene-authoring', 'examples', name), 'utf8');

export const fixtureScene = (name: string): string =>
  readFileSync(path.join(desktopDir, 'e2e', 'fixtures', 'scenes', name), 'utf8');

export interface RecordedMessage {
  /** Milliseconds since the frame was mounted. */
  t: number;
  origin: string;
  type: string;
  [key: string]: unknown;
}

export interface RawPlayer {
  origin: string;
  send: (message: Record<string, unknown>) => Promise<void>;
  /** Resolve with the first recorded message matching `predicate` (a JS expression over `m`). */
  waitFor: (predicate: string, timeoutMs?: number) => Promise<RecordedMessage | null>;
  messages: () => Promise<RecordedMessage[]>;
  load: (
    source: string,
    options?: { theme?: 'light' | 'dark'; autoplay?: boolean },
  ) => Promise<void>;
  remove: () => Promise<void>;
  /** Bounding box of the 16:9 canvas inside the frame, in page coordinates. */
  canvasBox: () => Promise<{ x: number; y: number; width: number; height: number }>;
}

/**
 * Mount a player frame directly, bypassing the adapter, to test the frame and
 * the wire protocol themselves. The frame covers the whole window.
 */
export async function mountRawPlayer(page: Page, instance: string): Promise<RawPlayer> {
  const origin = `adle://${instance}.player`;
  await page.evaluate(
    ({ instance, origin }) => {
      interface Slot {
        frame: HTMLIFrameElement;
        messages: Record<string, unknown>[];
      }
      const registry = ((window as unknown as { __players?: Record<string, Slot> }).__players ??=
        {});
      const frame = document.createElement('iframe');
      frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
      frame.title = 'Test player';
      frame.style.cssText =
        'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:9999;background:white';
      frame.src = `${origin}/index.html`;
      const messages: Record<string, unknown>[] = [];
      const mountedAt = performance.now();
      window.addEventListener('message', (event) => {
        if (event.source !== frame.contentWindow) return;
        messages.push({
          t: Math.round(performance.now() - mountedAt),
          origin: event.origin,
          ...(event.data as Record<string, unknown>),
        });
      });
      document.body.appendChild(frame);
      registry[instance] = { frame, messages };
    },
    { instance, origin },
  );

  const waitFor: RawPlayer['waitFor'] = (predicate, timeoutMs = 15_000) =>
    page.evaluate(
      ({ instance, predicate, timeoutMs }) =>
        new Promise<RecordedMessage | null>((resolve) => {
          const slot = (
            window as unknown as { __players: Record<string, { messages: RecordedMessage[] }> }
          ).__players[instance]!;
          // eslint-disable-next-line @typescript-eslint/no-implied-eval -- test-only predicate
          const matches = new Function('m', `return (${predicate});`) as (
            m: RecordedMessage,
          ) => boolean;
          const started = performance.now();
          const poll = (): void => {
            const hit = slot.messages.find((message) => matches(message));
            if (hit) resolve(hit);
            else if (performance.now() - started > timeoutMs) resolve(null);
            else setTimeout(poll, 20);
          };
          poll();
        }),
      { instance, predicate, timeoutMs },
    );

  const send: RawPlayer['send'] = (message) =>
    page.evaluate(
      ({ instance, origin, message }) => {
        const slot = (
          window as unknown as { __players: Record<string, { frame: HTMLIFrameElement }> }
        ).__players[instance]!;
        slot.frame.contentWindow?.postMessage({ adle: 1, ...message }, origin);
      },
      { instance, origin, message },
    );

  return {
    origin,
    send,
    waitFor,
    messages: () =>
      page.evaluate(
        (instance) =>
          (window as unknown as { __players: Record<string, { messages: RecordedMessage[] }> })
            .__players[instance]!.messages,
        instance,
      ),
    load: (source, options = {}) =>
      send({
        type: 'load',
        runId: 'run',
        source,
        sceneName: null,
        theme: options.theme ?? 'light',
        quality: 'medium',
        autoplay: options.autoplay ?? true,
      }),
    remove: () =>
      page.evaluate((instance) => {
        (
          window as unknown as { __players: Record<string, { frame: HTMLIFrameElement }> }
        ).__players[instance]!.frame.remove();
      }, instance),
    canvasBox: async () => {
      const viewport = page.viewportSize() ?? { width: 1280, height: 832 };
      const width = Math.min(viewport.width, (viewport.height * 16) / 9);
      const height = (width * 9) / 16;
      return { x: (viewport.width - width) / 2, y: (viewport.height - height) / 2, width, height };
    },
  };
}

/** Convert Wanim world coordinates (14.22 x 8 units, origin at centre) to page pixels. */
export function worldToPage(
  box: { x: number; y: number; width: number; height: number },
  worldX: number,
  worldY: number,
): { x: number; y: number } {
  const frameWidth = 128 / 9;
  return {
    x: box.x + ((worldX + frameWidth / 2) / frameWidth) * box.width,
    y: box.y + ((4 - worldY) / 8) * box.height,
  };
}
