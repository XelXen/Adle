import { BrowserWindow, nativeTheme } from 'electron';

import { paths } from './paths';
import { APP_ENTRY_URL } from './protocol';

/** Canvas colours from the Sprout tokens, used to avoid a white flash before first paint. */
const CANVAS_LIGHT = '#F6F8F4';
const CANVAS_DARK = '#101713';

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
    backgroundColor: nativeTheme.shouldUseDarkColors ? CANVAS_DARK : CANVAS_LIGHT,
    autoHideMenuBar: true,
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
    },
  });

  void window.loadURL(APP_ENTRY_URL);
  return window;
}
