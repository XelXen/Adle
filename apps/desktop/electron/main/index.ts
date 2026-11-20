import { app, BrowserWindow, Menu, nativeTheme, safeStorage } from 'electron';

import { resolveLaunchSpec } from './core/launch-spec';
import { CoreProcess } from './core/process';
import { forwardCoreStatus, registerIpcHandlers, syncProviderKey } from './ipc';
import { paths } from './paths';
import { installProtocolHandler, registerSchemes } from './protocol';
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
  const deps = { core, keyStore, uiState, dataDir: paths.coreDataDir() };

  registerIpcHandlers(deps);
  forwardCoreStatus(core, () => mainWindow?.webContents ?? null);

  const openWindow = (): void => {
    mainWindow = createMainWindow({ showDevTools: isDevelopment });
    mainWindow.on('closed', () => {
      mainWindow = null;
    });
  };
  openWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) openWindow();
  });

  // The window is usable (sample content, settings) while the core starts.
  void core.start().then(async (status) => {
    if (status.state === 'ready') await syncProviderKey(deps);
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
