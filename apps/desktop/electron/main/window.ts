import { BrowserWindow, nativeTheme } from 'electron';

import type { UiState } from '../shared/ipc';
import { pastelWindowColors } from './pastel';
import { paths } from './paths';
import { APP_ENTRY_URL } from './protocol';
import { isPastel } from './ui-state';

/** Canvas colours from the Sprout tokens, used to avoid a white flash before first paint. */
const CANVAS_LIGHT = '#F3F3F3';
const CANVAS_DARK = '#0A0A0A';
/** The ink of each theme: what the window's own buttons are drawn in. */
const INK_LIGHT = '#171717';
const INK_DARK = '#EDEDED';

/** How tall the strip at the top of the window is, with the window's buttons at its end. */
export const TITLE_BAR_HEIGHT = 40;

/** Where the window learns the theme: the learner's interface settings, and their changes. */
export interface WindowLook {
  get(): Pick<UiState, 'theme' | 'pastelHue'>;
  onChange(listener: () => void): () => void;
}

/**
 * Where the app draws its own title bar (ADR-030). On Windows and macOS the window has
 * none of the operating system's: the page's top strip is what it is moved by, and the
 * system's buttons are laid over the end of it. Elsewhere the window keeps the frame it
 * is given: a window that could not be moved would be worse than a plain one.
 */
export function ownsTitleBar(platform: NodeJS.Platform = process.platform): boolean {
  return platform === 'win32' || platform === 'darwin';
}

/** The canvas and the ink of the theme in effect, as the page has them. */
function colors(look: WindowLook | undefined): { canvas: string; ink: string } {
  const dark = nativeTheme.shouldUseDarkColors;
  const chosen = look?.get();
  // Pastel and Pastel dark (ADR-074): the canvas and the ink take the learner's color.
  if (chosen && isPastel(chosen.theme)) return pastelWindowColors(chosen.pastelHue, dark);
  return dark ? { canvas: CANVAS_DARK, ink: INK_DARK } : { canvas: CANVAS_LIGHT, ink: INK_LIGHT };
}

/** The window's buttons in the colours of the app, so they belong to the strip they sit on. */
function buttons(look: WindowLook | undefined): Electron.TitleBarOverlayOptions {
  const { canvas, ink } = colors(look);
  return { color: canvas, symbolColor: ink, height: TITLE_BAR_HEIGHT };
}

export function createMainWindow(options: {
  showDevTools: boolean;
  look?: WindowLook;
}): BrowserWindow {
  const { look } = options;
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
    backgroundColor: colors(look).canvas,
    autoHideMenuBar: true,
    ...(ownsTitleBar()
      ? {
          titleBarStyle:
            process.platform === 'darwin' ? ('hiddenInset' as const) : ('hidden' as const),
          // macOS draws its own buttons; it is only told how tall the strip is.
          titleBarOverlay:
            process.platform === 'darwin' ? { height: TITLE_BAR_HEIGHT } : buttons(look),
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
  // The page repaints itself; what the window draws must follow. A pastel color changes
  // nothing the operating system sees, so the learner's settings are followed too.
  const repaint = (): void => {
    if (window.isDestroyed()) return;
    window.setBackgroundColor(colors(look).canvas);
    if (process.platform === 'win32') window.setTitleBarOverlay(buttons(look));
  };
  nativeTheme.on('updated', repaint);
  const stopFollowing = look?.onChange(repaint);
  window.once('closed', () => {
    nativeTheme.off('updated', repaint);
    stopFollowing?.();
  });

  void window.loadURL(APP_ENTRY_URL);
  return window;
}
