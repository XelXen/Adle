/**
 * Entry point of the isolated scene player frame.
 *
 * Boot order matters:
 *   1. Install the pausable frame clock (before Wanim captures the frame API).
 *   2. Load the Wanim runtime and point its font chain at local files.
 *   3. Announce `ready` and start accepting host commands.
 *
 * The only channel in or out of this document is `postMessage` with the
 * embedding Adle window, validated by `@adle/event-protocol`.
 */
import {
  APP_ORIGIN,
  type HostMessage,
  parseHostMessage,
  type PlayerMessage,
  PROTOCOL_VERSION,
} from '@adle/event-protocol';
import { version as wanimVersion } from '@wanimjs/wanim/package.json';

import { installFrameClock } from './frame-clock';
import { SceneRun, type WanimBridge } from './scene-run';
import { installTimeWarp } from './time-warp';

/**
 * Local font chain for Wanim `Text` (parsed by opentype.js, which reads WOFF1).
 * The first font containing a glyph wins. Nothing is fetched from a CDN.
 */
const FONT_FILES = [
  'inter-latin-400-normal.woff',
  'inter-latin-ext-400-normal.woff',
  'inter-greek-400-normal.woff',
];

const clock = installFrameClock(window);
// Before Wanim, which paces a scene by this clock, is loaded.
const warp = installTimeWarp(performance);
/**
 * How much faster than a learner's a rehearsal runs: a second of a scene in 40 ms of the
 * computer's. The frames themselves are drawn as fast as they can be, and a scene's waits
 * pass at this speed.
 */
const REHEARSAL_SPEED = 25;
/** The trusted embedder. Messages from any other window or origin are ignored. */
const host: Window = window.parent;

function post(message: PlayerMessage): void {
  host.postMessage(message, APP_ORIGIN);
}

function reportBootFailure(error: unknown): void {
  post({
    adle: PROTOCOL_VERSION,
    type: 'error',
    runId: null,
    stage: 'boot',
    message: error instanceof Error ? error.message : 'The scene runtime could not start.',
  });
}

async function loadRuntime(): Promise<WanimBridge> {
  const bridge = (await import('@wanimjs/wanim/bridge')) as unknown as WanimBridge & {
    wanim: {
      configure_fonts(paths: readonly string[]): void;
      preload_submodules(names: 'fonts' | 'mathjax'): Promise<void>;
    };
  };
  const fontUrls = FONT_FILES.map((file) => new URL(`./fonts/${file}`, document.baseURI).href);
  bridge.wanim.configure_fonts(fontUrls);
  // Parse the fonts up front so the first `Text` in a scene does no I/O.
  // (`preload_fonts` is declared in Wanim 0.1.3's types but is not exported by the
  // browser bundle; `preload_submodules("fonts")` is the working equivalent.)
  await bridge.wanim.preload_submodules('fonts');
  return bridge;
}

function start(bridge: WanimBridge): void {
  const canvas = document.getElementById('scene-canvas');
  if (!(canvas instanceof HTMLCanvasElement)) throw new Error('The scene canvas is missing.');

  let current: SceneRun | null = null;

  const handle = (message: HostMessage): void => {
    switch (message.type) {
      case 'ping':
        post({ adle: PROTOCOL_VERSION, type: 'pong', nonce: message.nonce });
        return;
      case 'load':
        current?.dispose();
        // A rehearsal is run through as fast as it can be; anything else at the display's
        // pace, as a learner sees it.
        if (message.rehearsal) {
          clock.rush();
          warp.setSpeed(REHEARSAL_SPEED);
        } else {
          clock.steady();
          warp.setSpeed(1);
        }
        current = new SceneRun(bridge, canvas, clock, message, post);
        current.start();
        return;
      case 'dispose':
        current?.dispose();
        current = null;
        return;
      default:
        break;
    }
    // Commands for a run that has been replaced are stale; drop them.
    if (!current || current.runId !== message.runId) return;
    switch (message.type) {
      case 'play':
        current.play();
        break;
      case 'pause':
        current.pause();
        break;
      case 'next':
        current.next();
        break;
      case 'set-control':
        current.setControl(message.name, message.value);
        break;
    }
  };

  window.addEventListener('message', (event: MessageEvent<unknown>) => {
    if (event.source !== host || event.origin !== APP_ORIGIN) return;
    const message = parseHostMessage(event.data);
    if (message) handle(message);
  });

  post({ adle: PROTOCOL_VERSION, type: 'ready', wanimVersion });
}

loadRuntime().then(start).catch(reportBootFailure);
