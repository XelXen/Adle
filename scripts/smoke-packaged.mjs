#!/usr/bin/env node
/**
 * Start a packaged Adle the way a learner would, and check that it comes up whole.
 *
 *   node scripts/smoke-packaged.mjs            the release build (apps/desktop/out/release)
 *   node scripts/smoke-packaged.mjs --test     the build made for the end-to-end suite
 *
 * The release build cannot be driven by a test tool: the switches such a tool needs are
 * turned off in it, on purpose. So this looks from outside, at what a working start leaves
 * behind:
 *
 *   1. the binary's fuses are set as intended, and it will not run as plain Node;
 *   2. started with an empty profile, the core comes up: its log says so and its database
 *      appears, which means the private Python, the core, and its migrations all work
 *      from inside the package, with nothing taken from the computer it is on;
 *   3. nothing is written to the log of failures;
 *   4. when the app is closed abruptly, the core does not stay behind.
 *
 * It prints how long the first start took. On a fresh build that includes the time the
 * operating system takes to look at files it has not seen before.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { FuseV1Options, getCurrentFuseWire } from '@electron/fuses';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const forTests = process.argv.includes('--test');
const buildDir = path.join(repoRoot, 'apps', 'desktop', 'out', forTests ? 'test' : 'release');
const START_TIMEOUT_MS = 120_000;

export function findExecutable(directory = buildDir) {
  if (!existsSync(directory)) return null;
  for (const folder of readdirSync(directory)) {
    const candidates = [
      path.join(directory, folder, 'Adle.exe'),
      path.join(directory, folder, 'Adle.app', 'Contents', 'MacOS', 'Adle'),
      path.join(directory, folder, 'Adle'),
    ];
    const found = candidates.find((candidate) => existsSync(candidate));
    if (found) return found;
  }
  return null;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function until(condition, timeoutMs, what) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (condition()) return;
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${what}.`);
}

const ENABLED = 0x31; // the character "1" in the fuse wire
const fuseIsOn = (wire, option) => wire[option] === ENABLED;

async function checkFuses(executable) {
  const wire = await getCurrentFuseWire(executable);
  const expected = [
    [FuseV1Options.RunAsNode, false, 'runs as plain Node'],
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable, false, 'takes NODE_OPTIONS'],
    [FuseV1Options.EnableNodeCliInspectArguments, forTests, 'can be debugged from outside'],
    [FuseV1Options.OnlyLoadAppFromAsar, true, 'loads the app only from its archive'],
    [FuseV1Options.GrantFileProtocolExtraPrivileges, false, 'gives file: pages extra rights'],
    [FuseV1Options.EnableCookieEncryption, true, 'encrypts cookies'],
  ];
  for (const [option, wanted, meaning] of expected) {
    if (fuseIsOn(wire, option) !== wanted) {
      throw new Error(
        `Fuse wrong: the binary ${wanted ? 'should' : 'should not'} be one that ${meaning}.`,
      );
    }
  }
}

/** With the fuse off, the variable is ignored and the app starts as itself. */
function checkWillNotRunAsNode(executable) {
  const marker = 'adle-ran-as-node';
  const result = spawnSync(executable, ['-e', `console.log("${marker}")`], {
    env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', ADLE_USER_DATA_DIR: os.tmpdir() },
    encoding: 'utf8',
    timeout: 4000,
    windowsHide: true,
  });
  if (`${result.stdout}${result.stderr}`.includes(marker)) {
    throw new Error('The packaged binary ran a script as plain Node.');
  }
}

async function startAndCheck(executable) {
  const profile = mkdtempSync(path.join(os.tmpdir(), 'adle-smoke-'));
  const started = Date.now();
  // Nothing of the development setup may be needed: not the repository, not uv, not a
  // Python on the PATH. The folder it runs from is somewhere else entirely.
  const child = spawn(executable, [], {
    cwd: os.tmpdir(),
    env: {
      SystemRoot: process.env.SystemRoot ?? '',
      SystemDrive: process.env.SystemDrive ?? '',
      TEMP: os.tmpdir(),
      TMP: os.tmpdir(),
      USERPROFILE: process.env.USERPROFILE ?? '',
      APPDATA: process.env.APPDATA ?? '',
      LOCALAPPDATA: process.env.LOCALAPPDATA ?? '',
      HOME: process.env.HOME ?? '',
      DISPLAY: process.env.DISPLAY ?? '',
      PATH: isWindows() ? `${process.env.SystemRoot}\\System32` : '/usr/bin:/bin',
      ADLE_USER_DATA_DIR: profile,
      // A Python variable that would break an interpreter which listened to it.
      PYTHONHOME: path.join(os.tmpdir(), 'no-such-python'),
      PYTHONPATH: path.join(os.tmpdir(), 'no-such-packages'),
    },
    stdio: 'ignore',
    windowsHide: false,
  });
  let exited = false;
  child.once('exit', () => {
    exited = true;
  });

  const coreLog = path.join(profile, 'logs', 'core.log');
  const database = path.join(profile, 'data', 'adle.db');
  try {
    await until(
      () =>
        existsSync(database) &&
        existsSync(coreLog) &&
        /Starting adle-core/.test(readFileSync(coreLog, 'utf8')),
      START_TIMEOUT_MS,
      'the core to start inside the packaged app',
    );
    const seconds = ((Date.now() - started) / 1000).toFixed(1);
    await sleep(3000);
    if (exited) throw new Error('The app closed by itself a few seconds after starting.');
    const failures = path.join(profile, 'logs', 'app.log');
    if (existsSync(failures)) {
      throw new Error(
        `The app logged a failure while starting:\n${readFileSync(failures, 'utf8')}`,
      );
    }
    const log = readFileSync(coreLog, 'utf8');
    if (/Traceback|ModuleNotFoundError|ImportError/.test(log)) {
      throw new Error(`The core's log shows an error:\n${log.slice(-1500)}`);
    }
    return { profile, child, seconds };
  } catch (error) {
    child.kill();
    throw error;
  }
}

function isWindows() {
  return process.platform === 'win32';
}

/** Whose work the app is built from, and their licences, travel with it. */
function checkNotices(executable) {
  const resources =
    process.platform === 'darwin'
      ? path.resolve(path.dirname(executable), '..', 'Resources')
      : path.join(path.dirname(executable), 'resources');
  const folder = path.join(resources, 'licenses');
  const inventory = path.join(folder, 'THIRD-PARTY.md');
  if (!existsSync(inventory)) throw new Error('The package has no licenses/THIRD-PARTY.md.');
  const texts = existsSync(path.join(folder, 'texts'))
    ? readdirSync(path.join(folder, 'texts'))
    : [];
  // The fonts and the scene runtime, at the very least, each bring a licence text.
  if (texts.length < 5) throw new Error('The package has too few licence texts to be believed.');
}

async function main() {
  const executable = findExecutable();
  if (!executable) {
    throw new Error(
      `No packaged app in ${buildDir}. Run "node scripts/package.mjs${forTests ? ' --for-tests' : ''}" first.`,
    );
  }
  console.log(`Checking ${executable}`);
  await checkFuses(executable);
  console.log('  PASS  fuses are set as intended');
  checkNotices(executable);
  console.log('  PASS  the third-party notices are in the package');
  if (!forTests) {
    checkWillNotRunAsNode(executable);
    console.log('  PASS  will not run as plain Node');
  }

  const { profile, child, seconds } = await startAndCheck(executable);
  console.log(`  PASS  starts with an empty profile; the core was up after ${seconds} s`);
  console.log('  PASS  nothing in the log of failures');

  // Closed abruptly, as when the computer shuts down: only the app itself is ended here.
  child.kill();
  await sleep(500);
  // The core holds its database open. If it stayed behind, the profile could not be removed.
  rmSync(profile, { recursive: true, force: true, maxRetries: 60, retryDelay: 250 });
  if (existsSync(profile)) throw new Error('The core stayed behind after the app was closed.');
  console.log('  PASS  the core does not stay behind when the app is ended');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`  FAIL  ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  });
}
