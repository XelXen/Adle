import { app, BrowserWindow, dialog, Menu, nativeTheme, safeStorage } from 'electron';

import { createAppLog } from './app-log';
import { resolveLaunchSpec } from './core/launch-spec';
import { CoreProcess } from './core/process';
import { forwardCoreStatus, registerIpcHandlers } from './ipc';
import { paths } from './paths';
import { installProtocolHandler, registerSchemes } from './protocol';
import {
  mayRestartCore,
  noteRejection,
  oneAtATime,
  type Question,
  whenMainFailed,
  whenPageGone,
  whenPageHung,
} from './recovery';
import { syncProviders } from './providers';
import { createSecureEncryptor, ProviderKeyStore } from './secrets';
import { hardenSession, hardenWebContents } from './security';
import { UiStateStore } from './ui-state';
import { createMainWindow } from './window';

/**
 * Tests and development may point the app at an isolated profile so they never
 * touch a learner's real data. Must be applied before the app is ready.
 */
const userDataOverride = process.env.ADLE_USER_DATA_DIR;
if (userDataOverride) app.setPath('userData', userDataOverride);

const isDevelopment = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let quitting = false;
const startedAt = Date.now();
/** What happened to the app itself, kept on this computer only (see `app-log.ts`). */
const appLog = createAppLog(paths.logsDir());

/** Put a question to the learner in a window of the operating system. */
async function ask(question: Question): Promise<number> {
  if (!app.isReady()) {
    // Too early for a proper dialog. Say it anyway; the first button is the answer.
    dialog.showErrorBox(question.title, `${question.message}\n\n${question.detail}`);
    return 0;
  }
  const options: Electron.MessageBoxOptions = {
    type: 'warning',
    title: question.title,
    message: question.message,
    detail: question.detail,
    buttons: [...question.buttons],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  };
  const owner = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  const answer = owner
    ? await dialog.showMessageBox(owner, options)
    : await dialog.showMessageBox(options);
  return answer.response;
}

// An error nobody caught leaves the main process in a state that cannot be trusted. The
// learner is told and the app restarts or quits; Electron's own dialog, with a stack trace
// and a process that carries on regardless, is never shown.
process.on(
  'uncaughtException',
  oneAtATime((error: unknown) =>
    whenMainFailed(error, {
      ask,
      restart: () => {
        app.relaunch();
        app.exit(0);
      },
      // The core notices that its parent has gone and stops by itself.
      quit: () => app.exit(1),
      log: appLog,
      uptimeSeconds: () => (Date.now() - startedAt) / 1000,
    }),
  ),
);
process.on('unhandledRejection', (reason) => noteRejection(reason, appLog));

registerSchemes();
hardenWebContents();

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });
  void app.whenReady().then(start);
}

function buildMenu(): Menu {
  return Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' as const }] : []),
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        ...(isDevelopment
          ? [{ type: 'separator' as const }, { role: 'toggleDevTools' as const }]
          : []),
      ],
    },
    { role: 'windowMenu' },
  ]);
}

async function start(): Promise<void> {
  await hardenSession();
  installProtocolHandler();
  Menu.setApplicationMenu(buildMenu());

  const core = new CoreProcess({
    resolveSpec: () =>
      resolveLaunchSpec({
        isPackaged: app.isPackaged,
        platform: process.platform,
        resourcesPath: process.resourcesPath,
        repoRoot: paths.repoRoot,
      }),
    dataDir: paths.coreDataDir(),
    logsDir: paths.logsDir(),
  });
  const keyStore = new ProviderKeyStore(
    createSecureEncryptor(safeStorage, process.platform),
    paths.secretsFile(),
  );
  const uiState = new UiStateStore(paths.uiStateFile());
  // Apply the saved theme before the window exists so there is no flash of the wrong one.
  nativeTheme.themeSource = uiState.get().theme;
  const deps = {
    core,
    keyStore,
    uiState,
    dataDir: paths.coreDataDir(),
    logsDir: paths.logsDir(),
  };
  core.on('status', (status) => {
    // The message is one the core or the supervisor wrote for the learner; it has no data in it.
    if (status.state === 'failed') appLog.record('core-failed', { message: status.message });
  });
  // A core that dies while the learner is working is started again, once or twice. The
  // screens that could not load meanwhile say so and offer to try again.
  const automaticRestarts: number[] = [];
  core.on('stopped-unexpectedly', () => {
    const now = Date.now();
    if (quitting || !mayRestartCore(automaticRestarts, now)) return;
    automaticRestarts.push(now);
    appLog.record('core-restarted', { attempt: automaticRestarts.length });
    setTimeout(() => {
      void core.start().then(async (status) => {
        if (status.state === 'ready') await syncProviders(deps);
      });
    }, 1000);
  });

  registerIpcHandlers(deps);
  forwardCoreStatus(core, () => mainWindow?.webContents ?? null);

  const openWindow = (): void => {
    const window = createMainWindow({ showDevTools: isDevelopment });
    mainWindow = window;
    window.on('closed', () => {
      mainWindow = null;
    });
    // A page that has crashed, or hung, would otherwise leave an empty window and no way on.
    const page = {
      ask,
      reload: () => {
        if (!window.isDestroyed()) window.webContents.reload();
      },
      quit: () => app.quit(),
      log: appLog,
    };
    window.webContents.on(
      'render-process-gone',
      oneAtATime((_event: unknown, details: { reason: string; exitCode: number }) =>
        whenPageGone(details, page),
      ),
    );
    window.on(
      'unresponsive',
      oneAtATime(() => whenPageHung(page)),
    );
  };
  openWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) openWindow();
  });

  // The window is usable (sample content, settings) while the core starts.
  void core.start().then(async (status) => {
    if (status.state === 'ready') await syncProviders(deps);
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });

  app.on('before-quit', (event) => {
    if (quitting) return;
    // Give the core a chance to flush and exit before the app goes away.
    event.preventDefault();
    quitting = true;
    void core.stop().finally(() => app.quit());
  });
}
