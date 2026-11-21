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

/**
 * Where a frame may go. The window's own document stays in the app; a frame inside it is
 * a scene player or nothing, and is never the app itself. Exported for unit tests.
 */
export function isAllowedFrameNavigation(rawUrl: string, isMainFrame = false): boolean {
  const origin = adleOriginOf(rawUrl);
  if (isMainFrame) return origin === APP_ORIGIN;
  if (rawUrl === 'about:blank') return true;
  return origin !== null && isPlayerOrigin(origin);
}

/**
 * The one permission anything is given: the app's own page may fill the screen, which is
 * how a lesson is watched full screen. Nothing is read, recorded or sent by it, Escape
 * always gives the screen back, and the system says so when it begins. A scene's frame
 * cannot ask: it is not the window's own document, and its frame is given no such right.
 * Exported for unit tests.
 */
export function mayFillTheScreen(
  permission: string,
  isMainFrame: boolean | undefined,
  requestingUrl: string | undefined,
): boolean {
  return (
    permission === 'fullscreen' &&
    isMainFrame === true &&
    typeof requestingUrl === 'string' &&
    adleOriginOf(requestingUrl) === APP_ORIGIN
  );
}

/** An address on this computer where nothing listens. */
const NOWHERE = 'http://127.0.0.1:1';

/**
 * Before the app is ready: no name is ever looked up.
 *
 * Refusing requests (below) does not cover what is not a request. A page can ask for a name
 * to be resolved ahead of time, and a peer connection looks up the servers it is given;
 * either sends the name, and whatever is written into it, to a name server. Nothing here
 * needs a lookup: the app is served from memory, the main process reaches the core by its
 * address, and a link opens in the learner's own browser.
 */
export function refuseNameLookups(): void {
  app.commandLine.appendSwitch('host-resolver-rules', 'MAP * ~NOTFOUND');
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

  // What is not a request (a connection opened ahead of time, the TCP side of a peer
  // connection) goes through the proxy, and the proxy is nowhere. Addresses on this
  // computer are not let past it either.
  await defaultSession.setProxy({ proxyRules: NOWHERE, proxyBypassRules: '<-loopback>' });

  // Nothing the app shows is ever saved to a file by the browser.
  defaultSession.on('will-download', (event) => {
    event.preventDefault();
  });

  // No camera, microphone, geolocation, notifications, clipboard-read, etc. One thing is
  // granted, to one asker: see `mayFillTheScreen`.
  defaultSession.setPermissionRequestHandler((_webContents, permission, callback, details) => {
    callback(mayFillTheScreen(permission, details?.isMainFrame, details?.requestingUrl));
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
    // A peer connection may not send a packet of its own: no UDP except through a proxy,
    // and the only proxy there is leads nowhere (see `hardenSession`).
    contents.setWebRTCIPHandlingPolicy('disable_non_proxied_udp');

    contents.on('will-navigate', (event, url) => {
      // The top-level document never navigates away from the app shell.
      if (adleOriginOf(url) !== APP_ORIGIN) event.preventDefault();
    });

    contents.on('will-frame-navigate', (event) => {
      if (!isAllowedFrameNavigation(event.url, event.isMainFrame)) event.preventDefault();
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
