import { existsSync } from 'node:fs';
import path from 'node:path';

export interface LaunchSpec {
  command: string;
  args: string[];
  cwd: string;
}

export interface LaunchContext {
  isPackaged: boolean;
  platform: NodeJS.Platform;
  /** `process.resourcesPath` in a packaged app. */
  resourcesPath: string;
  /** Repository root in a development checkout. */
  repoRoot: string;
  /** Injectable for tests. */
  exists?: (file: string) => boolean;
}

export class CoreNotInstalledError extends Error {}

/**
 * Decide how to start the Python core.
 *
 * Packaged builds ship a self-contained core under `resources/core`.
 * Development runs use the uv-managed virtual environment in `services/core`.
 * No path or secret is ever taken from the renderer.
 */
export function resolveLaunchSpec(context: LaunchContext): LaunchSpec {
  const exists = context.exists ?? existsSync;
  const isWindows = context.platform === 'win32';

  if (context.isPackaged) {
    const coreDir = path.join(context.resourcesPath, 'core');
    const executable = path.join(coreDir, isWindows ? 'adle-core.exe' : 'adle-core');
    if (!exists(executable)) {
      throw new CoreNotInstalledError(
        'The Adle core service is missing from this installation. Please reinstall Adle.',
      );
    }
    return { command: executable, args: [], cwd: coreDir };
  }

  const serviceDir = path.join(context.repoRoot, 'services', 'core');
  const python = isWindows
    ? path.join(serviceDir, '.venv', 'Scripts', 'python.exe')
    : path.join(serviceDir, '.venv', 'bin', 'python');
  if (!exists(python)) {
    throw new CoreNotInstalledError(
      'The core service environment is not set up. Run "npm run core:sync" in the repository.',
    );
  }
  return { command: python, args: ['-m', 'adle_core'], cwd: serviceDir };
}
