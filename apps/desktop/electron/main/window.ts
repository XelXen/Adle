import { BrowserWindow, nativeTheme } from 'electron';

import { paths } from './paths';
import { APP_ENTRY_URL } from './protocol';

/** Canvas colours from the Sprout tokens, used to avoid a white flash before first paint. */
const CANVAS_LIGHT = '#F3F3F3';
const CANVAS_DARK = '#0A0A0A';
/** The ink of each theme: what the window's own buttons are drawn in. */
const INK_LIGHT = '#171717';
const INK_DARK = '#EDEDED';

/** How tall the strip at the top of the window is, with the window's buttons at its end. */
export const TITLE_BAR_HEIGHT = 40;

/**
 * Where the app draws its own title bar (ADR-030). On Windows and macOS the window has
 * none of the operating system's: the page's top strip is what it is moved by, and the
 * system's buttons are laid over the end of it. Elsewhere the window keeps the frame it
 * is given: a window that could not be moved would be worse than a plain one.
 */
export function ownsTitleBar(platform: NodeJS.Platform = process.platform): boolean {
  return platform === 'win32' || platform === 'darwin';
}

const canvas = (): string => (nativeTheme.shouldUseDarkColors ? CANVAS_DARK : CANVAS_LIGHT);

/** The window's buttons in the colours of the app, so they belong to the strip they sit on. */
function buttons(): Electron.TitleBarOverlayOptions {
  return {
    color: canvas(),
    symbolColor: nativeTheme.shouldUseDarkColors ? INK_DARK : INK_LIGHT,
    height: TITLE_BAR_HEIGHT,
  };
}

export function createMainWindow(options: { showDevTools: boolean }): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 832,
    minWidth: 960,
    minHeight: 640,
    // Visible from the start, not hidden until `ready-to-show`. A window created hidden
    // sometimes never produced its first frame (about 1 to 3 in 100 automated launches on
    // Windows), so the event never came and no window ever appeared. `backgroundColor`
    // below matches the app canvas, so showing early does not flash white.
    show: true,
    title: 'Adle',
    // Windows and Linux take the window and taskbar icon from here; macOS uses the bundle's.
    icon: paths.windowIcon,
    backgroundColor: canvas(),
    autoHideMenuBar: true,
    ...(ownsTitleBar()
      ? {
          titleBarStyle:
            process.platform === 'darwin' ? ('hiddenInset' as const) : ('hidden' as const),
          // macOS draws its own buttons; it is only told how tall the strip is.
          titleBarOverlay: process.platform === 'darwin' ? { height: TITLE_BAR_HEIGHT } : buttons(),
        }
      : {}),
    webPreferences: {
      preload: paths.preloadScript,
      // The security baseline. Do not relax any of these (see SECURITY.md).
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      nodeIntegrationInSubFrames: false,
      nodeIntegrationInWorker: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
      webviewTag: false,
      devTools: options.showDevTools,
      spellcheck: true,
      // A break's clock and the watch on what is being written run on timers, and what
      // they have to say matters most when the window is behind another one or minimised.
      // Slowed down there, "your break is over" could be a minute late.
      backgroundThrottling: false,
    },
  });

  // The theme can change while the window is open (the learner's choice, or the system's).
  // The page repaints itself; what the window draws must follow.
  const repaint = (): void => {
    if (window.isDestroyed()) return;
    window.setBackgroundColor(canvas());
    if (process.platform === 'win32') window.setTitleBarOverlay(buttons());
  };
  nativeTheme.on('updated', repaint);
  window.once('closed', () => nativeTheme.off('updated', repaint));

  void window.loadURL(APP_ENTRY_URL);
  return window;
}
