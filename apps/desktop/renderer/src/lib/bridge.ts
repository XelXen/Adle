import type { AdleBridge } from '../../../electron/shared/ipc';

declare global {
  interface Window {
    /** Installed by the preload script. The only way out of the renderer. */
    adle?: AdleBridge;
  }
}

export function getBridge(): AdleBridge {
  if (!window.adle) {
    throw new Error(
      'The Adle desktop bridge is unavailable. This page must run inside the Adle app.',
    );
  }
  return window.adle;
}

export type {
  AdleBridge,
  AppInfo,
  CoreError,
  CoreResult,
  CoreStatus,
  ExternalLinkId,
  NoticeKind,
  ProviderKeyState,
  ProviderKeyStates,
  ThemePreference,
  UiState,
} from '../../../electron/shared/ipc';
