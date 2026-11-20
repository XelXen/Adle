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
  showLogs: 'adle:app:show-logs',
  coreStatus: 'adle:core:status',
  coreStatusChanged: 'adle:core:status-changed',
  coreRestart: 'adle:core:restart',
  coreInvoke: 'adle:core:invoke',
  providerKeyState: 'adle:provider:key-state',
  providerSetApiKey: 'adle:provider:set-api-key',
  providerClearApiKey: 'adle:provider:clear-api-key',
  providerSelect: 'adle:provider:select',
  sourcesImportWithPicker: 'adle:sources:import-with-picker',
  sourcesImportPaths: 'adle:sources:import-paths',
  dataSaveCopy: 'adle:data:save-copy',
  dataRestoreCopy: 'adle:data:restore-copy',
  dataEraseAll: 'adle:data:erase-all',
  dataShowSafetyCopies: 'adle:data:show-safety-copies',
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

/**
 * The providers Adle keeps a key for. The core says which of them this installation
 * offers (`provider.status`); a name that is not in this list is refused by the main process.
 */
export const PROVIDER_IDS = ['aihubmix', 'nvidia', 'custom'] as const;
export type ProviderId = (typeof PROVIDER_IDS)[number];

/** Whether a provider key is stored. The key itself never crosses to the renderer. */
export interface ProviderKeyState {
  stored: boolean;
  /** Last four characters, for recognition only. */
  hint: string | null;
}

/**
 * What is stored for each provider the core offers, by the provider's name. Empty while
 * the core cannot be asked which providers there are.
 */
export type ProviderKeyStates = Readonly<Record<string, ProviderKeyState | undefined>>;

/** A background import as reported by the core (see `Job` in the generated contract). */
export type ImportJob = Job;

/** A copy of the learner's data was written where they chose. */
export interface SavedCopy {
  /** The name of the file, for saying what was saved. Never a path the page could act on. */
  fileName: string;
}

/** External destinations the UI may open in the system browser. Nothing else can be opened. */
export const EXTERNAL_LINKS = {
  aihubmixKeys: 'https://aihubmix.com/token',
  aihubmixModel: 'https://aihubmix.com/model/coding-kimi-k3-free',
  nvidiaKeys: 'https://build.nvidia.com/settings/api-keys',
  wanim: 'https://wanim.org/',
} as const;

export type ExternalLinkId = keyof typeof EXTERNAL_LINKS;

/** The API exposed on `window.adle` by the preload script. */
export interface AdleBridge {
  app: {
    info(): Promise<AppInfo>;
    updateUiState(patch: Partial<UiState>): Promise<UiState>;
    openExternal(link: ExternalLinkId): Promise<void>;
    /**
     * Open, in the file manager, the folder of Adle's own log files. They stay on this
     * computer; this is how a learner looks at them or chooses to show them to someone.
     */
    showLogs(): Promise<CoreResult<null>>;
  };
  core: {
    status(): Promise<CoreStatus>;
    onStatus(listener: (status: CoreStatus) => void): () => void;
    restart(): Promise<CoreStatus>;
    invoke(operation: string, params?: CoreInvokeParams): Promise<CoreResult>;
  };
  provider: {
    /** For each provider on offer: whether a key for it is stored on this computer. */
    keyState(): Promise<ProviderKeyStates>;
    /** Keep a key for one provider. It is only ever sent to that provider's address. */
    setApiKey(providerId: string, apiKey: string): Promise<CoreResult<ProviderKeyStates>>;
    clearApiKey(providerId: string): Promise<CoreResult<ProviderKeyStates>>;
    /**
     * Use another provider from now on. Only ever called because the learner chose it:
     * nothing in Adle changes provider by itself.
     */
    select(providerId: string): Promise<CoreResult<null>>;
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
  /**
   * The learner's own data as a whole. Each of these asks the learner in a window of the
   * operating system, which page script cannot answer for them: where to save, which file
   * to restore, whether to delete. Each resolves with `null` if they backed out.
   */
  data: {
    /** Save a copy of everything Adle holds to a file the learner chooses. */
    saveCopy(): Promise<CoreResult<SavedCopy | null>>;
    /** Replace everything with a copy saved earlier. What is replaced is kept as a safety copy. */
    restoreCopy(): Promise<CoreResult<{ restored: true } | null>>;
    /** Delete every course, lesson, answer, and safety copy. The provider key is not touched. */
    eraseAll(): Promise<CoreResult<{ erased: true } | null>>;
    /**
     * Open, in the file manager, the folder where Adle keeps the copies it makes before
     * it replaces or updates the data. The folder is fixed; the page chooses nothing.
     */
    showSafetyCopies(): Promise<CoreResult<null>>;
  };
}
