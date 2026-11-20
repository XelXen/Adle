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
 * How the private Python of a packaged build is started.
 *
 * `-I` cuts it off from the computer it is on: no `PYTHON*` variables, no packages from the
 * user's own Python, nothing imported from the current folder. A learner's machine may have
 * any of those, and none of them may change what Adle runs. `-u` and `-X utf8` are what the
 * development run asks for through the environment, which `-I` ignores.
 */
export const PACKAGED_INTERPRETER_FLAGS = ['-I', '-u', '-X', 'utf8'] as const;

/**
 * Decide how to start the Python core.
 *
 * Packaged builds ship a private Python under `resources/core`, with the core and its
 * dependencies installed into it (ADR-019). Development runs use the uv-managed virtual
 * environment in `services/core`. No path or secret is ever taken from the renderer.
 */
export function resolveLaunchSpec(context: LaunchContext): LaunchSpec {
  const exists = context.exists ?? existsSync;
  const isWindows = context.platform === 'win32';

  if (context.isPackaged) {
    const coreDir = path.join(context.resourcesPath, 'core');
    // The interpreter itself, under the name the process should be listed by where the
    // platform allows renaming it.
    const executable = isWindows
      ? path.join(coreDir, 'adle-core.exe')
      : path.join(coreDir, 'bin', 'python3.12');
    if (!exists(executable)) {
      throw new CoreNotInstalledError(
        'The Adle core service is missing from this installation. Please reinstall Adle.',
      );
    }
    return {
      command: executable,
      args: [...PACKAGED_INTERPRETER_FLAGS, '-m', 'adle_core'],
      cwd: coreDir,
    };
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
