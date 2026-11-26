import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import { THEME_PREFERENCES, type ThemePreference, type UiState } from '../shared/ipc';

/** The color Pastel starts in, before the learner picks one: lavender (ADR-074). */
export const DEFAULT_PASTEL_HUE = 295;

const DEFAULT_STATE: UiState = {
  theme: 'system',
  pastelHue: DEFAULT_PASTEL_HUE,
  onboardingCompleted: false,
  notifications: true,
};

function isThemePreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (THEME_PREFERENCES as readonly string[]).includes(value);
}

/** A hue the Pastel themes can be in: a whole number of degrees, 0 to 359. */
export function isPastelHue(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 359;
}

/**
 * What Chromium is told the color scheme is (`nativeTheme.themeSource`), which it gives
 * the page and every player frame as `prefers-color-scheme`. Pastel is the light theme in
 * a color, and Pastel dark the dark one, so there is still one way the scheme is set.
 */
export function colorSchemeOf(theme: ThemePreference): 'system' | 'light' | 'dark' {
  if (theme === 'pastel') return 'light';
  if (theme === 'pastel-dark') return 'dark';
  return theme;
}

/** Whether the theme takes its colors from the learner's pastel hue. */
export function isPastel(theme: ThemePreference): boolean {
  return theme === 'pastel' || theme === 'pastel-dark';
}

/** Validate an untrusted patch. Unknown or malformed fields are rejected, not ignored. */
export function parseUiStatePatch(value: unknown): Partial<UiState> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null;
  const patch: Partial<UiState> = {};
  for (const [key, field] of Object.entries(value)) {
    if (key === 'theme' && isThemePreference(field)) patch.theme = field;
    else if (key === 'pastelHue' && isPastelHue(field)) patch.pastelHue = field;
    else if (key === 'onboardingCompleted' && typeof field === 'boolean') {
      patch.onboardingCompleted = field;
    } else if (key === 'notifications' && typeof field === 'boolean') {
      patch.notifications = field;
    } else return null;
  }
  return patch;
}

/**
 * Small, non-sensitive interface preferences that must be known before the
 * core service is ready (so the first paint already uses the right theme).
 * Learning data never lives here; it belongs to the core database.
 */
export class UiStateStore {
  private state: UiState;
  private readonly listeners = new Set<(state: UiState) => void>();

  constructor(private readonly file: string) {
    this.state = this.read();
  }

  get(): UiState {
    return { ...this.state };
  }

  update(patch: Partial<UiState>): UiState {
    this.state = { ...this.state, ...patch };
    mkdirSync(path.dirname(this.file), { recursive: true });
    // Write-then-rename so a crash mid-write cannot leave a truncated file.
    const temporary = `${this.file}.tmp`;
    writeFileSync(temporary, JSON.stringify(this.state, null, 2));
    renameSync(temporary, this.file);
    const next = this.get();
    for (const listener of this.listeners) listener(next);
    return next;
  }

  /** Told after every change; what the window draws itself follows the theme with this. */
  onChange(listener: (state: UiState) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private read(): UiState {
    try {
      const parsed = parseUiStatePatch(JSON.parse(readFileSync(this.file, 'utf8')));
      return { ...DEFAULT_STATE, ...(parsed ?? {}) };
    } catch {
      return { ...DEFAULT_STATE };
    }
  }
}
