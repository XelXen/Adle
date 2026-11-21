/**
 * Unit tests for the main-process security boundaries: what may be loaded,
 * who may call the bridge, and which core operations the renderer can reach.
 */
import { existsSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it, vi } from 'vitest';

const createdWindows: Record<string, unknown>[] = [];

vi.mock('electron', () => ({
  BrowserWindow: class {
    constructor(options: Record<string, unknown>) {
      createdWindows.push(options);
    }
    once = vi.fn();
    loadURL = vi.fn(async () => undefined);
    isDestroyed = () => false;
    setBackgroundColor = vi.fn();
    setTitleBarOverlay = vi.fn();
  },
  app: {
    getPath: () => '/tmp/adle-test',
    on: vi.fn(),
    getName: () => 'Adle',
    getVersion: () => '0.0.0',
  },
  protocol: { registerSchemesAsPrivileged: vi.fn(), handle: vi.fn() },
  session: { defaultSession: {} },
  shell: { openExternal: vi.fn() },
  ipcMain: { handle: vi.fn() },
  nativeTheme: { themeSource: 'system', shouldUseDarkColors: false, on: vi.fn(), off: vi.fn() },
  safeStorage: { isEncryptionAvailable: () => true },
}));

const { isTrustedSender, parseInvokeRequest } = await import('./ipc');
const { APP_CSP, PLAYER_CSP, resolveStaticPath, siteForHost } = await import('./protocol');
const { isAllowedFrameNavigation, isAllowedRequest } = await import('./security');
const { createMainWindow, ownsTitleBar, TITLE_BAR_HEIGHT } = await import('./window');

describe('main window', () => {
  it('is created with the hardened web preferences', () => {
    createMainWindow({ showDevTools: false });
    const options = createdWindows.at(-1) as { webPreferences: Record<string, unknown> };
    expect(options.webPreferences).toMatchObject({
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      nodeIntegrationInSubFrames: false,
      nodeIntegrationInWorker: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
      webviewTag: false,
      devTools: false,
    });
    // No remote module, no extra preloads, nothing that widens the renderer.
    // (`backgroundThrottling` is about timers keeping their pace, not about what a page may do.)
    expect(Object.keys(options.webPreferences).sort()).toEqual([
      'allowRunningInsecureContent',
      'backgroundThrottling',
      'contextIsolation',
      'devTools',
      'nodeIntegration',
      'nodeIntegrationInSubFrames',
      'nodeIntegrationInWorker',
      'preload',
      'sandbox',
      'spellcheck',
      'webSecurity',
      'webviewTag',
    ]);
  });

  it('has a title bar of its own where the window can still be moved by it', () => {
    expect(ownsTitleBar('win32')).toBe(true);
    expect(ownsTitleBar('darwin')).toBe(true);
    // Not tried there: a window that cannot be moved is worse than a plain one.
    expect(ownsTitleBar('linux')).toBe(false);

    createMainWindow({ showDevTools: false });
    const options = createdWindows.at(-1) as {
      titleBarStyle?: string;
      titleBarOverlay?: { color?: string; symbolColor?: string; height?: number };
    };
    if (!ownsTitleBar()) {
      expect(options.titleBarStyle).toBeUndefined();
      return;
    }
    expect(options.titleBarStyle).toBe(process.platform === 'darwin' ? 'hiddenInset' : 'hidden');
    expect(options.titleBarOverlay?.height).toBe(TITLE_BAR_HEIGHT);
    if (process.platform === 'win32') {
      // The window's buttons sit on the canvas, in the ink of the theme.
      expect(options.titleBarOverlay).toMatchObject({ color: '#F3F3F3', symbolColor: '#171717' });
    }
  });

  it('is visible from the start, painted in the canvas colour', () => {
    createMainWindow({ showDevTools: false });
    const options = createdWindows.at(-1) as { show: boolean; backgroundColor: string };
    // Not hidden until `ready-to-show`: see the note in window.ts.
    expect(options.show).toBe(true);
    expect(options.backgroundColor).toBe('#F3F3F3');
  });

  it('carries the app icon, which exists in the repository', () => {
    createMainWindow({ showDevTools: false });
    const options = createdWindows.at(-1) as { icon: string };
    expect(options.icon).toMatch(/assets[\\/]icons[\\/]icon\.(ico|png)$/);
    expect(existsSync(options.icon)).toBe(true);
    // Both forms are committed, whichever platform the test runs on.
    const icons = path.dirname(options.icon);
    for (const file of ['icon.ico', 'icon.png', 'icon-1024.png']) {
      expect(existsSync(path.join(icons, file)), file).toBe(true);
    }
  });
});

describe('resolveStaticPath', () => {
  const root = path.resolve('/srv/adle/renderer');

  it('serves index.html for the root and files inside the root', () => {
    expect(resolveStaticPath(root, '/')).toBe(path.join(root, 'index.html'));
    expect(resolveStaticPath(root, '/assets/app.js')).toBe(path.join(root, 'assets', 'app.js'));
  });

  it.each([
    '/../secrets.txt',
    '/assets/../../secrets.txt',
    '/%2e%2e/%2e%2e/etc/passwd',
    '/..%5c..%5cwindows%5cwin.ini',
    '/assets/%00.js',
    '/%E0%A4%A',
  ])('refuses %s', (requestPath) => {
    const resolved = resolveStaticPath(root, requestPath);
    // Either rejected outright, or still inside the root after normalisation.
    if (resolved !== null) expect(resolved.startsWith(root + path.sep)).toBe(true);
    if (requestPath.includes('secrets') || requestPath.includes('etc')) expect(resolved).toBeNull();
  });

  it('does not treat a sibling directory with the same prefix as inside the root', () => {
    expect(resolveStaticPath(root, '/../renderer-evil/x.js')).toBeNull();
  });
});

describe('siteForHost', () => {
  it('routes the app and player hosts and nothing else', () => {
    expect(siteForHost('app')).toBe('app');
    expect(siteForHost('k3f9.player')).toBe('player');
    expect(siteForHost('player')).toBeNull();
    expect(siteForHost('asset')).toBeNull();
    expect(siteForHost('app.player.evil')).toBeNull();
  });
});

describe('content security policies', () => {
  it('keeps evaluated script out of the renderer', () => {
    expect(APP_CSP).toContain("script-src 'self'");
    expect(APP_CSP).not.toContain('unsafe-eval');
    expect(APP_CSP).not.toContain('unsafe-inline');
    expect(APP_CSP).toContain("default-src 'none'");
    expect(APP_CSP).toContain("frame-ancestors 'none'");
    expect(APP_CSP).toContain('frame-src adle://*.player');
    // Nothing the browser does not know: an unknown directive is an error in the console
    // of every page, and stops nothing.
    expect(APP_CSP).not.toContain('webrtc');
  });

  it('confines the player to its own origin and forbids embedding elsewhere', () => {
    expect(PLAYER_CSP).toContain("connect-src 'self'");
    expect(PLAYER_CSP).toContain('frame-ancestors adle://app');
    expect(PLAYER_CSP).toContain('sandbox allow-scripts allow-same-origin');
    expect(PLAYER_CSP).not.toContain('webrtc');
    for (const forbidden of [
      'allow-popups',
      'allow-top-navigation',
      'allow-forms',
      'allow-downloads',
    ]) {
      expect(PLAYER_CSP).not.toContain(forbidden);
    }
    expect(PLAYER_CSP).not.toMatch(/https?:/);
  });
});

describe('request and navigation filters', () => {
  it('allows only local schemes', () => {
    expect(isAllowedRequest('adle://app/index.html')).toBe(true);
    expect(isAllowedRequest('data:image/png;base64,AAAA')).toBe(true);
    expect(isAllowedRequest('blob:adle://app/1234')).toBe(true);
    for (const url of [
      'https://example.com/',
      'http://127.0.0.1:8000/',
      'ws://localhost:1234/',
      'file:///etc/passwd',
      'ftp://example.com/',
      'not a url',
    ]) {
      expect(isAllowedRequest(url)).toBe(false);
    }
  });

  it('lets a frame inside the window be a scene player or nothing, never the app', () => {
    expect(isAllowedFrameNavigation('adle://ab12cd.player/index.html')).toBe(true);
    expect(isAllowedFrameNavigation('about:blank')).toBe(true);
    expect(isAllowedFrameNavigation('adle://app/index.html')).toBe(false);
    expect(isAllowedFrameNavigation('adle://other/index.html')).toBe(false);
    expect(isAllowedFrameNavigation('https://example.com/')).toBe(false);
    expect(isAllowedFrameNavigation('javascript:alert(1)')).toBe(false);
  });

  it('keeps the window itself in the app', () => {
    expect(isAllowedFrameNavigation('adle://app/index.html', true)).toBe(true);
    expect(isAllowedFrameNavigation('adle://ab12cd.player/index.html', true)).toBe(false);
    expect(isAllowedFrameNavigation('about:blank', true)).toBe(false);
    expect(isAllowedFrameNavigation('https://example.com/', true)).toBe(false);
  });
});

describe('isTrustedSender', () => {
  const event = (frame: unknown) => ({ senderFrame: frame }) as never;

  it('accepts only the top-level app document', () => {
    expect(isTrustedSender(event({ parent: null, url: 'adle://app/index.html' }))).toBe(true);
  });

  it('rejects player frames, subframes, other origins, and missing frames', () => {
    expect(isTrustedSender(event({ parent: {}, url: 'adle://app/index.html' }))).toBe(false);
    expect(isTrustedSender(event({ parent: {}, url: 'adle://ab12.player/index.html' }))).toBe(
      false,
    );
    expect(isTrustedSender(event({ parent: null, url: 'adle://ab12.player/index.html' }))).toBe(
      false,
    );
    expect(isTrustedSender(event({ parent: null, url: 'https://example.com/' }))).toBe(false);
    expect(isTrustedSender(event(null))).toBe(false);
  });
});

describe('parseInvokeRequest', () => {
  it('accepts an allowlisted operation with no parameters', () => {
    expect(parseInvokeRequest('system.health', undefined)).toEqual({
      ok: true,
      operation: 'system.health',
      params: {},
    });
  });

  it('refuses unknown and internal operations', () => {
    expect(parseInvokeRequest('system.shutdown', {})).toMatchObject({ ok: false });
    expect(parseInvokeRequest('__proto__', {})).toMatchObject({ ok: false });
    expect(parseInvokeRequest('toString', {})).toMatchObject({ ok: false });
    expect(parseInvokeRequest(42, {})).toMatchObject({ ok: false });
    // The credential hand-off is for the main process only.
    expect(
      parseInvokeRequest('provider.set_credential', { body: { api_key: 'secret-value' } }),
    ).toMatchObject({
      ok: false,
    });
    expect(parseInvokeRequest('provider.clear_credential', {})).toMatchObject({ ok: false });
  });

  it('refuses malformed parameters', () => {
    expect(parseInvokeRequest('system.health', 'x')).toMatchObject({ ok: false });
    expect(parseInvokeRequest('system.health', [])).toMatchObject({ ok: false });
    expect(parseInvokeRequest('system.health', { headers: { Authorization: 'x' } })).toMatchObject({
      ok: false,
    });
    expect(parseInvokeRequest('system.health', { path: { id: { nested: 1 } } })).toMatchObject({
      ok: false,
    });
    expect(parseInvokeRequest('system.health', { query: ['a'] })).toMatchObject({ ok: false });
    expect(parseInvokeRequest('system.health', { query: { n: Number.NaN } })).toMatchObject({
      ok: false,
    });
  });

  it('refuses bodies that are too large or cannot be serialised', () => {
    expect(
      parseInvokeRequest('system.health', { body: 'x'.repeat(1024 * 1024 + 1) }),
    ).toMatchObject({
      ok: false,
    });
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(parseInvokeRequest('system.health', { body: circular })).toMatchObject({ ok: false });
  });
});
