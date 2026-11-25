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
  type CourseFileHolds,
  type CourseFileKind,
  type CoreStatus,
  type ExternalLinkId,
  IPC,
  type NoticeKind,
  type SettingsFileParts,
  type UiState,
} from '../shared/ipc';
import { droppedPaths } from './dropped';

const bridge: AdleBridge = {
  app: {
    info: () => ipcRenderer.invoke(IPC.appInfo),
    updateUiState: (patch: Partial<UiState>) => ipcRenderer.invoke(IPC.uiStateUpdate, patch),
    openExternal: (link: ExternalLinkId) => ipcRenderer.invoke(IPC.openExternal, link),
    showLogs: () => ipcRenderer.invoke(IPC.showLogs),
    notify: (kind: NoticeKind) => ipcRenderer.invoke(IPC.appNotify, kind),
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
    setApiKey: (providerId: string, apiKey: string) =>
      ipcRenderer.invoke(IPC.providerSetApiKey, providerId, apiKey),
    clearApiKey: (providerId: string) => ipcRenderer.invoke(IPC.providerClearApiKey, providerId),
    select: (selection: string) => ipcRenderer.invoke(IPC.providerSelect, selection),
  },
  sources: {
    importWithPicker: (courseId: string) =>
      ipcRenderer.invoke(IPC.sourcesImportWithPicker, courseId),
    importDropped: (courseId: string, files: File[]) => {
      // Paths come from real File objects the learner dropped. Page script has no way to
      // construct a File that maps to a path of its choosing, and nothing it hands over
      // is asked for one in any other way (see `droppedPaths`).
      const paths = droppedPaths(files, (file) => webUtils.getPathForFile(file));
      return ipcRenderer.invoke(IPC.sourcesImportPaths, courseId, paths);
    },
  },
  courses: {
    // Which course and what the file holds; where it goes is asked by the main process.
    saveFile: (courseId: string, request: { kind: CourseFileKind; holds: CourseFileHolds }) =>
      ipcRenderer.invoke(IPC.coursesSaveFile, courseId, request),
    chooseFile: () => ipcRenderer.invoke(IPC.coursesChooseFile),
    bringIn: (token: string, holds: CourseFileHolds) =>
      ipcRenderer.invoke(IPC.coursesBringIn, token, holds),
  },
  settings: {
    // Which parts, and a password for the keys; where is asked by the main process.
    saveFile: (parts: SettingsFileParts, password: string | null) =>
      ipcRenderer.invoke(IPC.settingsSaveFile, parts, password),
    chooseFile: () => ipcRenderer.invoke(IPC.settingsChooseFile),
    bringIn: (
      token: string,
      parts: SettingsFileParts,
      options: { password: string | null; setUpVoice: boolean },
    ) => ipcRenderer.invoke(IPC.settingsBringIn, token, parts, options),
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
