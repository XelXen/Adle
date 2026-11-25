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
  BroughtInCourse,
  CoreError,
  CoreResult,
  CoreStatus,
  CourseFileCounts,
  CourseFileFound,
  CourseFileHolds,
  CourseFileKind,
  ExternalLinkId,
  NoticeKind,
  ProviderKeyState,
  ProviderKeyStates,
  SavedCourseFile,
  SavedSettingsFile,
  SettingsBroughtIn,
  SettingsFileFound,
  SettingsFileParts,
  SettingsVoicePlan,
  ThemePreference,
  UiState,
} from '../../../electron/shared/ipc';
