import path from 'node:path';

import { app } from 'electron';

/**
 * Locations of built assets and app-controlled data.
 *
 * The bundled main script lives at `<app>/dist/electron/main.cjs`, so sibling
 * build outputs are resolved relative to it. This holds in development and
 * inside the packaged asar archive alike.
 */
const DIST_DIR = path.resolve(__dirname, '..');

export const paths = {
  rendererDir: path.join(DIST_DIR, 'renderer'),
  playerDir: path.join(DIST_DIR, 'player'),
  preloadScript: path.join(DIST_DIR, 'electron', 'preload.cjs'),

  /** Repository root; only meaningful in development (unpackaged) runs. */
  repoRoot: path.resolve(DIST_DIR, '..', '..', '..'),

  userData: () => app.getPath('userData'),
  /** Everything the Python core persists. Passed to it as its data directory. */
  coreDataDir: () => path.join(app.getPath('userData'), 'data'),
  logsDir: () => path.join(app.getPath('userData'), 'logs'),
  secretsFile: () => path.join(app.getPath('userData'), 'credentials.bin'),
  uiStateFile: () => path.join(app.getPath('userData'), 'ui-state.json'),
} as const;
