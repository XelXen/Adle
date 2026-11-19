import { app, session, shell } from 'electron';

import { ADLE_SCHEME, adleOriginOf, APP_ORIGIN, isPlayerOrigin } from '@adle/event-protocol';

import { EXTERNAL_LINKS, type ExternalLinkId } from '../shared/ipc';

/** Schemes the embedded browser may load. Everything else, including http(s), is refused. */
const ALLOWED_REQUEST_SCHEMES = new Set([
  `${ADLE_SCHEME}:`,
  'devtools:',
  'data:',
  'blob:',
  'about:',
]);

/** Exported for unit tests. */
export function isAllowedRequest(rawUrl: string): boolean {
  try {
    return ALLOWED_REQUEST_SCHEMES.has(new URL(rawUrl).protocol);
  } catch {
    return false;
  }
}

/** Exported for unit tests. */
export function isAllowedFrameNavigation(rawUrl: string): boolean {
  if (rawUrl === 'about:blank') return true;
  const origin = adleOriginOf(rawUrl);
  return origin !== null && (origin === APP_ORIGIN || isPlayerOrigin(origin));
}

/**
 * Lock the Chromium session down.
 *
 * The renderer and the scene player never need the network: the main process
 * talks to the local core on their behalf. Refusing every non-`adle:` request
 * here means a compromised page or a generated scene cannot exfiltrate data
 * even if a Content Security Policy were misconfigured.
 */
export async function hardenSession(): Promise<void> {
  const defaultSession = session.defaultSession;

  defaultSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !isAllowedRequest(details.url) });
  });

  // No camera, microphone, geolocation, notifications, clipboard-read, etc.
  defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  defaultSession.setPermissionCheckHandler(() => false);
  defaultSession.setDevicePermissionHandler(() => false);

  // Nothing in the app relies on web storage (state lives in the core's
  // database), and player origins are single-use. Starting clean guarantees
  // that anything a scene stored in a previous session is gone.
  await defaultSession.clearStorageData({
    storages: [
      'localstorage',
      'indexdb',
      'cookies',
      'cachestorage',
      'serviceworkers',
      'filesystem',
    ],
  });
}

/** Apply per-WebContents guards to every page the app ever creates. */
export function hardenWebContents(): void {
  app.on('web-contents-created', (_event, contents) => {
    contents.setWindowOpenHandler(() => ({ action: 'deny' }));

    contents.on('will-navigate', (event, url) => {
      // The top-level document never navigates away from the app shell.
      if (adleOriginOf(url) !== APP_ORIGIN) event.preventDefault();
    });

    contents.on('will-frame-navigate', (event) => {
      if (!isAllowedFrameNavigation(event.url)) event.preventDefault();
    });

    contents.on('will-attach-webview', (event) => {
      event.preventDefault();
    });
  });
}

/** Open one of the fixed, known external pages in the system browser. */
export async function openExternalLink(link: ExternalLinkId): Promise<void> {
  const url = EXTERNAL_LINKS[link];
  if (!url) throw new Error('Unknown external link.');
  await shell.openExternal(url);
}
