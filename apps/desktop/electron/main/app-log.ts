import { appendFileSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';

/**
 * A small log of what happened to the app itself: a window that stopped, an error nobody
 * caught, the core failing to start. It stays on this computer. Nothing reads it but the
 * learner, who can open the folder from Settings and decide whether to show it to anyone.
 *
 * It records the kind of event and a few facts about it (a reason, an exit code, the name
 * of an error). It never records what the learner typed, opened, or answered: callers pass
 * a fixed set of fields, and long values are cut short.
 */

/** Start afresh once the file is this large, so it can never fill a disk. */
const MAX_BYTES = 512 * 1024;
const MAX_VALUE_LENGTH = 2000;

export type LogDetail = Record<string, string | number | boolean | null | undefined>;

export interface AppLog {
  record(event: string, detail?: LogDetail): void;
}

function clip(value: LogDetail[string]): string | number | boolean | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string') return value;
  return value.length > MAX_VALUE_LENGTH ? `${value.slice(0, MAX_VALUE_LENGTH)}…` : value;
}

/** One JSON object per line: easy to read, and easy to check that nothing else is in it. */
export function formatLine(now: Date, event: string, detail: LogDetail = {}): string {
  const fields = Object.fromEntries(
    Object.entries(detail).map(([key, value]) => [key, clip(value)]),
  );
  return `${JSON.stringify({ at: now.toISOString(), event, ...fields })}\n`;
}

export function createAppLog(logsDir: string, now: () => Date = () => new Date()): AppLog {
  const file = path.join(logsDir, 'app.log');
  return {
    record(event, detail) {
      // Logging must never be the thing that breaks the app: a full or read-only disk is
      // not a reason to fail whatever was being reported.
      try {
        mkdirSync(logsDir, { recursive: true });
        let size = 0;
        try {
          size = statSync(file).size;
        } catch {
          // No file yet.
        }
        const line = formatLine(now(), event, detail);
        if (size + line.length > MAX_BYTES) writeFileSync(file, line);
        else appendFileSync(file, line);
      } catch {
        // Nothing useful can be done about it here.
      }
    },
  };
}
