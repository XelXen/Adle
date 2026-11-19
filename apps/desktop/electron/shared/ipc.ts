/**
 * IPC contract shared by the Electron main process, the preload bridge, and
 * (as types only) the renderer.
 *
 * This file is the complete list of things the renderer can ask the main
 * process to do. Keep it small and specific: no generic filesystem, shell, or
 * arbitrary-channel access may be added here (see SECURITY.md).
 */
import type { Job } from '@adle/contracts';

export const IPC = {
  appInfo: 'adle:app:info',
  uiStateUpdate: 'adle:app:ui-state-update',
  openExternal: 'adle:app:open-external',
  coreStatus: 'adle:core:status',
  coreStatusChanged: 'adle:core:status-changed',
  coreRestart: 'adle:core:restart',
  coreInvoke: 'adle:core:invoke',
  providerKeyState: 'adle:provider:key-state',
  providerSetApiKey: 'adle:provider:set-api-key',
  providerClearApiKey: 'adle:provider:clear-api-key',
  sourcesImportWithPicker: 'adle:sources:import-with-picker',
  sourcesImportPaths: 'adle:sources:import-paths',
} as const;

export type IpcChannel = (typeof IPC)[keyof typeof IPC];

/** Lifecycle of the managed Python core process, as seen by the UI. */
export type CoreStatus =
  | { state: 'starting' }
  | { state: 'ready'; version: string }
  | { state: 'failed'; message: string }
  | { state: 'stopped' };

export const THEME_PREFERENCES = ['system', 'light', 'dark'] as const;
export type ThemePreference = (typeof THEME_PREFERENCES)[number];

/** Interface preferences kept by the main process so the first paint is already correct. */
export interface UiState {
  theme: ThemePreference;
  /** True once the learner has finished the first-run welcome. */
  onboardingCompleted: boolean;
}

export interface AppInfo {
  name: string;
  version: string;
  platform: string;
  isPackaged: boolean;
  versions: { electron: string; chrome: string; node: string };
  /** False when the OS offers no credential encryption; key storage is then refused. */
  secureStorageAvailable: boolean;
  ui: UiState;
}

/** Error shape for every failed core call. Never contains secrets. */
export interface CoreError {
  /** Stable machine-readable code, e.g. `quota_exhausted`, `not_found`, `core_unavailable`. */
  code: string;
  /** Learner-readable message. */
  message: string;
  /** HTTP status from the core, or 0 when the core could not be reached. */
  status: number;
  /** Seconds to wait before retrying, when the core knows. */
  retryAfterSeconds?: number;
  /** Optional structured detail (validation errors, etc.). */
  detail?: unknown;
}

export type CoreResult<T = unknown> = { ok: true; data: T } | { ok: false; error: CoreError };

/** Parameters for an allowlisted core operation. */
export interface CoreInvokeParams {
  path?: Record<string, string | number>;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
}

/** Whether a provider key is stored. The key itself never crosses to the renderer. */
export interface ProviderKeyState {
  stored: boolean;
  /** Last four characters, for recognition only. */
  hint: string | null;
}

/** A background import as reported by the core (see `Job` in the generated contract). */
export type ImportJob = Job;

/** External destinations the UI may open in the system browser. Nothing else can be opened. */
export const EXTERNAL_LINKS = {
  aihubmixKeys: 'https://aihubmix.com/token',
  aihubmixModel: 'https://aihubmix.com/model/coding-kimi-k3-free',
  wanim: 'https://wanim.org/',
} as const;

export type ExternalLinkId = keyof typeof EXTERNAL_LINKS;

/** The API exposed on `window.adle` by the preload script. */
export interface AdleBridge {
  app: {
    info(): Promise<AppInfo>;
    updateUiState(patch: Partial<UiState>): Promise<UiState>;
    openExternal(link: ExternalLinkId): Promise<void>;
  };
  core: {
    status(): Promise<CoreStatus>;
    onStatus(listener: (status: CoreStatus) => void): () => void;
    restart(): Promise<CoreStatus>;
    invoke(operation: string, params?: CoreInvokeParams): Promise<CoreResult>;
  };
  provider: {
    keyState(): Promise<ProviderKeyState>;
    setApiKey(apiKey: string): Promise<CoreResult<ProviderKeyState>>;
    clearApiKey(): Promise<CoreResult<ProviderKeyState>>;
  };
  sources: {
    /**
     * Show the operating system's file dialog and import what the learner picks.
     * Resolves with `null` if the dialog was dismissed.
     */
    importWithPicker(courseId: string): Promise<CoreResult<ImportJob | null>>;
    /** Import files the learner dropped onto the window. */
    importDropped(courseId: string, files: File[]): Promise<CoreResult<ImportJob>>;
  };
}
