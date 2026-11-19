import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import { THEME_PREFERENCES, type ThemePreference, type UiState } from '../shared/ipc';

const DEFAULT_STATE: UiState = { theme: 'system', onboardingCompleted: false };

function isThemePreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (THEME_PREFERENCES as readonly string[]).includes(value);
}

/** Validate an untrusted patch. Unknown or malformed fields are rejected, not ignored. */
export function parseUiStatePatch(value: unknown): Partial<UiState> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null;
  const patch: Partial<UiState> = {};
  for (const [key, field] of Object.entries(value)) {
    if (key === 'theme' && isThemePreference(field)) patch.theme = field;
    else if (key === 'onboardingCompleted' && typeof field === 'boolean') {
      patch.onboardingCompleted = field;
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
    return this.get();
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
