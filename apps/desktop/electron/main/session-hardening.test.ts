/**
 * The session, and every page made in it, are shut off from the network by every road
 * (ADR-029). These check that each lock is put on; `e2e/security.spec.ts` tries the doors.
 */
import { describe, expect, it, vi } from 'vitest';

type Listener = (...args: unknown[]) => unknown;

const switches: [string, string][] = [];
const appListeners = new Map<string, Listener>();
const sessionListeners = new Map<string, Listener>();

const defaultSession = {
  webRequest: { onBeforeRequest: vi.fn<(filter: Listener) => void>() },
  setProxy: vi.fn<(config: unknown) => Promise<void>>(() => Promise.resolve()),
  on: (event: string, listener: Listener) => {
    sessionListeners.set(event, listener);
  },
  setPermissionRequestHandler: vi.fn<(handler: Listener) => void>(),
  setPermissionCheckHandler: vi.fn<(handler: Listener) => void>(),
  setDevicePermissionHandler: vi.fn<(handler: Listener) => void>(),
  clearStorageData: vi.fn<(options: { storages: string[] }) => Promise<void>>(() =>
    Promise.resolve(),
  ),
};

vi.mock('electron', () => ({
  app: {
    commandLine: {
      appendSwitch: (name: string, value: string) => {
        switches.push([name, value]);
      },
    },
    on: (event: string, listener: Listener) => {
      appListeners.set(event, listener);
    },
  },
  session: { defaultSession },
  shell: { openExternal: vi.fn() },
}));

const { hardenSession, hardenWebContents, mayFillTheScreen, refuseNameLookups } =
  await import('./security');

/** A page as the main process sees it, with what was done to it written down. */
function fakeContents() {
  const listeners = new Map<string, Listener>();
  const contents = {
    setWindowOpenHandler: vi.fn<(handler: () => { action: string }) => void>(),
    setWebRTCIPHandlingPolicy: vi.fn<(policy: string) => void>(),
    on: (event: string, listener: Listener) => {
      listeners.set(event, listener);
    },
  };
  return { contents, listeners };
}

/** Whether a listener stopped what it was told about. */
function prevented(listener: Listener | undefined, ...rest: unknown[]): boolean {
  const event = { preventDefault: vi.fn() };
  listener?.(event, ...rest);
  return event.preventDefault.mock.calls.length > 0;
}

describe('refuseNameLookups', () => {
  it('has every name answered with "not found", before anything can ask', () => {
    refuseNameLookups();
    expect(switches).toEqual([['host-resolver-rules', 'MAP * ~NOTFOUND']]);
  });
});

describe('hardenSession', () => {
  it('refuses every request that is not the app’s own', async () => {
    await hardenSession();
    const filter = defaultSession.webRequest.onBeforeRequest.mock.calls.at(-1)?.[0];
    const cancelled = (url: string): unknown => {
      let answer: unknown;
      filter?.({ url }, (result: { cancel: boolean }) => {
        answer = result.cancel;
      });
      return answer;
    };
    expect(cancelled('adle://app/index.html')).toBe(false);
    for (const url of [
      'https://example.com/',
      'http://127.0.0.1:8000/v1/health',
      'ws://127.0.0.1:8000/',
      'wss://example.com/',
      'file:///C:/Windows/win.ini',
      'ftp://example.com/',
      'not a url',
    ]) {
      expect(cancelled(url), url).toBe(true);
    }
  });

  it('sends what is not a request to a proxy that is nowhere, this computer included', async () => {
    await hardenSession();
    expect(defaultSession.setProxy).toHaveBeenLastCalledWith({
      proxyRules: 'http://127.0.0.1:1',
      // Without this, Chromium lets addresses on this computer past a proxy.
      proxyBypassRules: '<-loopback>',
    });
  });

  it('lets the browser save nothing to a file', async () => {
    await hardenSession();
    expect(prevented(sessionListeners.get('will-download'))).toBe(true);
  });

  it('grants no permission to anyone, but for the app’s own page filling the screen', async () => {
    await hardenSession();
    const ask = defaultSession.setPermissionRequestHandler.mock.calls.at(-1)?.[0];
    const answers: unknown[] = [];
    const reply = (granted: boolean): number => answers.push(granted);
    for (const permission of ['media', 'geolocation', 'notifications', 'clipboard-read']) {
      ask?.({}, permission, reply);
      // Not even to the app's own page.
      ask?.({}, permission, reply, { isMainFrame: true, requestingUrl: 'adle://app/' });
    }
    expect(answers).toEqual(Array.from({ length: 8 }, () => false));

    const page = { isMainFrame: true, requestingUrl: 'adle://app/index.html' };
    expect(mayFillTheScreen('fullscreen', page.isMainFrame, page.requestingUrl)).toBe(true);
    answers.length = 0;
    ask?.({}, 'fullscreen', reply, page);
    // A scene's frame, a frame of the app inside the window, a page from anywhere else,
    // and a request that does not say who is asking: none of them.
    ask?.({}, 'fullscreen', reply, { isMainFrame: false, requestingUrl: 'adle://a1.player/' });
    ask?.({}, 'fullscreen', reply, { isMainFrame: false, requestingUrl: 'adle://app/' });
    ask?.({}, 'fullscreen', reply, { isMainFrame: true, requestingUrl: 'adle://a1.player/' });
    ask?.({}, 'fullscreen', reply, { isMainFrame: true, requestingUrl: 'https://example.com/' });
    ask?.({}, 'fullscreen', reply, { isMainFrame: true });
    ask?.({}, 'fullscreen', reply);
    expect(answers).toEqual([true, false, false, false, false, false, false]);
    expect(defaultSession.setPermissionCheckHandler.mock.calls.at(-1)?.[0]?.()).toBe(false);
    expect(defaultSession.setDevicePermissionHandler.mock.calls.at(-1)?.[0]?.()).toBe(false);
  });

  it('starts with nothing a page stored the last time', async () => {
    await hardenSession();
    const cleared = defaultSession.clearStorageData.mock.calls.at(-1)?.[0].storages ?? [];
    for (const kind of ['localstorage', 'indexdb', 'cookies', 'cachestorage', 'serviceworkers']) {
      expect(cleared, kind).toContain(kind);
    }
  });
});

describe('hardenWebContents', () => {
  hardenWebContents();
  const created = appListeners.get('web-contents-created');

  it('gives every page made a peer connection that may send nothing of its own', () => {
    const { contents } = fakeContents();
    created?.({}, contents);
    expect(contents.setWebRTCIPHandlingPolicy).toHaveBeenCalledWith('disable_non_proxied_udp');
  });

  it('opens no window for a page', () => {
    const { contents } = fakeContents();
    created?.({}, contents);
    const handler = contents.setWindowOpenHandler.mock.calls.at(-1)?.[0];
    expect(handler?.()).toEqual({ action: 'deny' });
  });

  it('keeps the window’s own document in the app', () => {
    const { contents, listeners } = fakeContents();
    created?.({}, contents);
    const navigate = listeners.get('will-navigate');
    expect(prevented(navigate, 'adle://app/index.html')).toBe(false);
    for (const url of ['https://example.com/', 'adle://abc.player/index.html', 'file:///C:/x']) {
      expect(prevented(navigate, url), url).toBe(true);
    }
  });

  it('lets a frame be a scene player or nothing, and never a web view', () => {
    const { contents, listeners } = fakeContents();
    created?.({}, contents);
    const stopped = (url: string, isMainFrame: boolean): boolean => {
      const event = { url, isMainFrame, preventDefault: vi.fn() };
      listeners.get('will-frame-navigate')?.(event);
      return event.preventDefault.mock.calls.length > 0;
    };
    expect(stopped('adle://k3f9abc.player/index.html', false)).toBe(false);
    expect(stopped('adle://app/index.html', true)).toBe(false);
    // The app inside a frame of itself would have the bridge: never.
    expect(stopped('adle://app/index.html', false)).toBe(true);
    expect(stopped('https://example.com/', false)).toBe(true);
    expect(stopped('adle://k3f9abc.player/index.html', true)).toBe(true);
    expect(prevented(listeners.get('will-attach-webview'))).toBe(true);
  });
});
