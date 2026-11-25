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
  appNotify: 'adle:app:notify',
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
  coursesSaveFile: 'adle:courses:save-file',
  coursesChooseFile: 'adle:courses:choose-file',
  coursesBringIn: 'adle:courses:bring-in',
  settingsSaveFile: 'adle:settings:save-file',
  settingsChooseFile: 'adle:settings:choose-file',
  settingsBringIn: 'adle:settings:bring-in',
  filmsSaveFile: 'adle:films:save-file',
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
  /**
   * Whether the operating system may say that something is ready while Adle is in the
   * background. On unless the learner turns it off.
   */
  notifications: boolean;
}

/**
 * Everything a notification of the operating system can be about. The page names one of
 * these and nothing else: the words shown are fixed in the main process
 * (`electron/main/notices.ts`), so no text from a lesson, a document, or a model can
 * reach the notification centre (ADR-026).
 */
export const NOTICE_KINDS = [
  'lesson_ready',
  'concepts_ready',
  'answer_ready',
  'writing_stopped',
  'break_over',
  'film_ready',
] as const;
export type NoticeKind = (typeof NOTICE_KINDS)[number];

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

/**
 * The choice that lets Adle use every provider the learner has given a key for, each for
 * what it is good at (ADR-023). The other choices are one provider's name.
 */
export const PROVIDER_AUTOMATIC = 'auto';
export type ProviderSelection = ProviderId | typeof PROVIDER_AUTOMATIC;

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

/**
 * A course saved as a file (ADR-063): a template, the course and its lessons with
 * nothing of the learner in it, or a transfer, everything, to carry it to another
 * computer.
 */
export type CourseFileKind = 'template' | 'transfer';

/** What goes into a course file, or is brought in from one. The plan always is. */
export interface CourseFileHolds {
  lessons: boolean;
  /** The documents the course was made from, and their text. */
  materials: boolean;
  /** The learner's own: answers, what they showed, where they stopped. */
  progress: boolean;
  /** The questions they asked during lessons, and the answers. */
  notes: boolean;
}

/** What a course file holds, as it was counted when it was made. */
export interface CourseFileCounts {
  concepts: number;
  lessons: number;
  materials: number;
  /** Of the materials, how many have the document itself in the file. */
  files: number;
  progress: boolean;
  notes: number;
}

/** A course was written to a file where the learner chose. */
export interface SavedCourseFile {
  /** The name of the file, for saying what was saved. Never a path. */
  fileName: string;
  counts: CourseFileCounts;
  /** Lessons still being written or drawn, which were left out. */
  lessonsLeftOut: number;
}

/**
 * A course file the learner chose, and what it says is in it. The page knows the file
 * by `token` and by its name: never by where it is.
 */
export interface CourseFileFound {
  token: string;
  fileName: string;
  title: string;
  kind: CourseFileKind;
  counts: CourseFileCounts;
}

/** A film was written where the learner chose (ADR-065). */
export interface SavedFilmFile {
  /** The name of the video, for saying what was saved. Never a path. */
  fileName: string;
  /** Its subtitles were saved beside it, under the same name. */
  withCaptions: boolean;
}

/** A new course made of what a file held. */
export interface BroughtInCourse {
  courseId: string;
  title: string;
  concepts: number;
  lessons: number;
  /** Lessons this Adle could not use, which were left out. */
  lessonsLeftOut: number;
  materials: number;
  progress: boolean;
  notes: number;
}

/**
 * The parts of a settings file (ADR-064): what is saved, and what is brought in.
 */
export interface SettingsFileParts {
  /** The theme, and whether the computer may say that something is ready. */
  appearance: boolean;
  /** How the learner likes to learn: pace, how much explanation, reading aloud. */
  learning: boolean;
  /** Which voice reads the lessons, and who speaks in it. */
  voice: boolean;
  /** Which AI provider is used, or that Adle chooses. */
  provider: boolean;
  /** The providers' keys, locked with a password. */
  keys: boolean;
}

/** Settings were written to a file where the learner chose. */
export interface SavedSettingsFile {
  /** The name of the file. Never a path. */
  fileName: string;
  /** The parts it has. */
  parts: SettingsFileParts;
  /** How many keys are in it, locked. */
  keys: number;
}

/** What the voice a file names would be on this computer. */
export interface SettingsVoicePlan {
  /** The voice lessons would be read in; null for the computer's own. */
  name: string | null;
  /** It is not on this computer yet: setting it up downloads it. */
  setUp: boolean;
  downloadBytes: number;
  /** Where a setup downloads from, as a person would name each place. */
  sources: string[];
  /** Why it is not the voice the file names, when it is not. */
  note: string;
}

/**
 * A settings file the learner chose, and what is in it. The page knows the file by
 * `token` and by its name; it is never given a key, only told whose keys are there.
 */
export interface SettingsFileFound {
  token: string;
  fileName: string;
  parts: SettingsFileParts;
  /** The providers offered here that the file has a key for, by their names. */
  keysFor: string[];
  voice: SettingsVoicePlan | null;
}

/** What was brought in from a settings file, and what could not be had as it was. */
export interface SettingsBroughtIn {
  parts: SettingsFileParts;
  keys: number;
  /** Each a sentence for the learner. */
  notes: string[];
  settingUpVoice: boolean;
}

/** External destinations the UI may open in the system browser. Nothing else can be opened. */
export const EXTERNAL_LINKS = {
  aihubmixKeys: 'https://aihubmix.com/token',
  aihubmixModel: 'https://aihubmix.com/model/coding-kimi-k3-free',
  nvidiaKeys: 'https://build.nvidia.com/settings/api-keys',
  wanim: 'https://wanim.org/',
  /** Where Adle's own source is: what its licence says a learner is owed. */
  source: 'https://github.com/XelXen/Adle',
  /** The licence Adle is under, as its authors publish it. A copy also ships with the app. */
  licence: 'https://www.gnu.org/licenses/gpl-3.0.html',
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
    /**
     * Ask the operating system to say that something is ready, in words fixed by its
     * kind. Nothing is shown while Adle's window has the focus, or when the learner has
     * turned notifications off. Resolves with whether one was shown.
     */
    notify(kind: NoticeKind): Promise<boolean>;
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
     * Record which provider to use from now on: one provider's name, or "auto" for every
     * provider the learner has given a key for. Only ever called because the learner
     * chose it: nothing in Adle changes this by itself.
     */
    select(selection: string): Promise<CoreResult<null>>;
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
   * A course as a file (ADR-063). The page says which course and what the file should
   * hold, or what to bring in of a file the learner chose. Where a file is saved, and
   * which file is opened, is asked in a window of the operating system: the page never
   * names a place.
   */
  courses: {
    /** Save a course as a file. Resolves with `null` if the learner backed out. */
    saveFile(
      courseId: string,
      request: { kind: CourseFileKind; holds: CourseFileHolds },
    ): Promise<CoreResult<SavedCourseFile | null>>;
    /**
     * Have the learner choose a course file, and say what it holds. Nothing is brought
     * in yet. Resolves with `null` if they backed out.
     */
    chooseFile(): Promise<CoreResult<CourseFileFound | null>>;
    /** Make a new course of the file last chosen: as much of it as `holds` says. */
    bringIn(token: string, holds: CourseFileHolds): Promise<CoreResult<BroughtInCourse>>;
  };
  /**
   * Settings as a file (ADR-064). The page says which parts, and a password for the
   * keys; where a file is saved and which is opened is asked in a window of the
   * operating system. A key never reaches the page: it is told only whose are there.
   */
  settings: {
    /** Save settings to a file. `password` locks the keys, when they are saved. */
    saveFile(
      parts: SettingsFileParts,
      password: string | null,
    ): Promise<CoreResult<SavedSettingsFile | null>>;
    /** Have the learner choose a settings file, and say what it holds. */
    chooseFile(): Promise<CoreResult<SettingsFileFound | null>>;
    /** Bring in the parts chosen of the file last chosen. */
    bringIn(
      token: string,
      parts: SettingsFileParts,
      options: { password: string | null; setUpVoice: boolean },
    ): Promise<CoreResult<SettingsBroughtIn>>;
  };
  /**
   * A film of a whole course (ADR-065). The page says which film; where it is saved is
   * asked in a window of the operating system.
   */
  films: {
    /** Save a film, with its subtitles beside it. Resolves with `null` if they backed out. */
    saveFile(filmId: string): Promise<CoreResult<SavedFilmFile | null>>;
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
