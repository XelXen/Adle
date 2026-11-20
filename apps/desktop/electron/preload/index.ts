/**
 * Preload bridge.
 *
 * Runs in an isolated, sandboxed context and exposes exactly the `AdleBridge`
 * surface to the page. It forwards calls to fixed IPC channels; it exposes no
 * Node APIs, no `ipcRenderer`, and no way to name an arbitrary channel.
 */
import { contextBridge, ipcRenderer, type IpcRendererEvent, webUtils } from 'electron';

import {
  type AdleBridge,
  type CoreInvokeParams,
  type CoreStatus,
  type ExternalLinkId,
  IPC,
  type UiState,
} from '../shared/ipc';

const bridge: AdleBridge = {
  app: {
    info: () => ipcRenderer.invoke(IPC.appInfo),
    updateUiState: (patch: Partial<UiState>) => ipcRenderer.invoke(IPC.uiStateUpdate, patch),
    openExternal: (link: ExternalLinkId) => ipcRenderer.invoke(IPC.openExternal, link),
  },
  core: {
    status: () => ipcRenderer.invoke(IPC.coreStatus),
    onStatus: (listener: (status: CoreStatus) => void) => {
      const handler = (_event: IpcRendererEvent, status: CoreStatus): void => listener(status);
      ipcRenderer.on(IPC.coreStatusChanged, handler);
      return () => {
        ipcRenderer.removeListener(IPC.coreStatusChanged, handler);
      };
    },
    restart: () => ipcRenderer.invoke(IPC.coreRestart),
    invoke: (operation: string, params?: CoreInvokeParams) =>
      ipcRenderer.invoke(IPC.coreInvoke, operation, params),
  },
  provider: {
    keyState: () => ipcRenderer.invoke(IPC.providerKeyState),
    setApiKey: (apiKey: string) => ipcRenderer.invoke(IPC.providerSetApiKey, apiKey),
    clearApiKey: () => ipcRenderer.invoke(IPC.providerClearApiKey),
  },
  sources: {
    importWithPicker: (courseId: string) =>
      ipcRenderer.invoke(IPC.sourcesImportWithPicker, courseId),
    importDropped: (courseId: string, files: File[]) => {
      // Paths come from real File objects the learner dropped. Page script has
      // no way to construct a File that maps to a path of its choosing.
      const paths = files.map((file) => webUtils.getPathForFile(file)).filter(Boolean);
      return ipcRenderer.invoke(IPC.sourcesImportPaths, courseId, paths);
    },
  },
  data: {
    // No arguments: the main process asks the learner where, which, and whether.
    saveCopy: () => ipcRenderer.invoke(IPC.dataSaveCopy),
    restoreCopy: () => ipcRenderer.invoke(IPC.dataRestoreCopy),
    eraseAll: () => ipcRenderer.invoke(IPC.dataEraseAll),
    showSafetyCopies: () => ipcRenderer.invoke(IPC.dataShowSafetyCopies),
  },
};

contextBridge.exposeInMainWorld('adle', bridge);
