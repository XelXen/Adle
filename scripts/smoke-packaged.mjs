#!/usr/bin/env node
/**
 * Start a packaged Adle the way a learner would, and check that it comes up whole.
 *
 *   node scripts/smoke-packaged.mjs            the release build (apps/desktop/out/release)
 *   node scripts/smoke-packaged.mjs --test     the build made for the end-to-end suite
 *   node scripts/smoke-packaged.mjs --at=<executable>
 *                                              a copy somewhere else: one that an installer
 *                                              has just put on the computer
 *   node scripts/smoke-packaged.mjs --at=<executable> --bare
 *                                              on a machine that has Node and this file and
 *                                              nothing else of the project: the fuses are
 *                                              not read (the tool that reads them is not
 *                                              here), and that is said
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
 * And two things that starting it cannot show. On Windows, that no program in the package
 * asks for a part of the Visual C++ runtime which the package does not bring: a computer
 * that builds software has that runtime; a new one may not. And everywhere, that the core's
 * Python can make an environment with pip in it, which is where a natural voice is set up
 * (ADR-042).
 *
 * It prints how long the first start took. On a fresh build that includes the time the
 * operating system takes to look at files it has not seen before.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const forTests = process.argv.includes('--test');
/** An executable named by whoever runs this, in place of the one in the build folder. */
const elsewhere =
  process.argv.find((argument) => argument.startsWith('--at='))?.slice('--at='.length) ?? null;
/**
 * Said by whoever runs this on a machine with none of the project's tools on it. Never
 * decided here: a missing tool on a developer's computer must stop the check, not thin it.
 */
const bare = process.argv.includes('--bare');
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
  // Read with the tool that set them, fetched only now: see --bare.
  const { FuseV1Options, getCurrentFuseWire } = await import('@electron/fuses');
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
      // Where the screen is, and the right to draw on it. Without the second a display
      // that asks for it (a virtual one on a build machine does) turns the app away.
      DISPLAY: process.env.DISPLAY ?? '',
      XAUTHORITY: process.env.XAUTHORITY ?? '',
      WAYLAND_DISPLAY: process.env.WAYLAND_DISPLAY ?? '',
      XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR ?? '',
      PATH: isWindows() ? `${process.env.SystemRoot}\\System32` : '/usr/bin:/bin',
      ADLE_USER_DATA_DIR: profile,
      // A Python variable that would break an interpreter which listened to it.
      PYTHONHOME: path.join(os.tmpdir(), 'no-such-python'),
      PYTHONPATH: path.join(os.tmpdir(), 'no-such-packages'),
    },
    // What the app says when something is wrong with the system it is on (no display, no
    // sandbox) is the only account there is of a start that never happened.
    stdio: ['ignore', 'ignore', 'pipe'],
    windowsHide: false,
  });
  let exited = false;
  let said = '';
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', (chunk) => {
    said = (said + chunk).slice(-4000);
  });
  child.once('exit', () => {
    exited = true;
  });
  /** What there is to go on when the app did not come up. */
  const account = () => {
    const parts = [];
    if (said.trim()) parts.push(`The app said:\n${said.trim()}`);
    for (const name of ['app.log', 'core.log']) {
      const log = path.join(profile, 'logs', name);
      if (existsSync(log)) parts.push(`${name} ends:\n${readFileSync(log, 'utf8').slice(-1500)}`);
    }
    return parts.length > 0 ? `\n${parts.join('\n')}` : '';
  };

  const coreLog = path.join(profile, 'logs', 'core.log');
  const database = path.join(profile, 'data', 'adle.db');
  try {
    await until(
      () => {
        if (exited) throw new Error(`The app closed by itself before its core was up.${account()}`);
        return (
          existsSync(database) &&
          existsSync(coreLog) &&
          /Starting adle-core/.test(readFileSync(coreLog, 'utf8'))
        );
      },
      START_TIMEOUT_MS,
      'the core to start inside the packaged app',
    ).catch((error) => {
      throw new Error(`${error.message}${exited ? '' : account()}`);
    });
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

/** Where a packaged app keeps what is not the program itself. */
function resourcesOf(executable) {
  return process.platform === 'darwin'
    ? path.resolve(path.dirname(executable), '..', 'Resources')
    : path.join(path.dirname(executable), 'resources');
}

/** The processes running a program from inside a folder, as the system lists them. */
function processesFrom(folder) {
  const listing = spawnSync('ps', ['-A', '-ww', '-o', 'pid=', '-o', 'args='], {
    encoding: 'utf8',
  });
  return (listing.stdout ?? '').split('\n').filter((line) => line.includes(folder));
}

/**
 * The libraries a Windows program asks the system to find for it, read from its import
 * table and from the table of those it loads only when first used. Lower case.
 */
export function importsOf(file) {
  const data = readFileSync(file);
  if (data.length < 0x40 || data.readUInt16LE(0) !== 0x5a4d) return [];
  const header = data.readUInt32LE(0x3c);
  if (header + 24 > data.length || data.readUInt32LE(header) !== 0x4550) return [];
  const sectionCount = data.readUInt16LE(header + 6);
  const optional = header + 24;
  const sectionsAt = optional + data.readUInt16LE(header + 20);
  // The optional header comes in two widths; the directories follow its fixed part.
  const directories = optional + (data.readUInt16LE(optional) === 0x20b ? 112 : 96);
  const directoryCount = data.readUInt32LE(directories - 4);
  const sections = [];
  for (let index = 0; index < sectionCount; index += 1) {
    const at = sectionsAt + index * 40;
    sections.push({
      address: data.readUInt32LE(at + 12),
      size: Math.max(data.readUInt32LE(at + 8), data.readUInt32LE(at + 16)),
      stored: data.readUInt32LE(at + 20),
    });
  }
  /** Where in the file something is that the program knows by its address in memory. */
  const inFile = (address) => {
    const section = sections.find(
      (candidate) => address >= candidate.address && address < candidate.address + candidate.size,
    );
    return section ? address - section.address + section.stored : null;
  };
  const names = [];
  const tables = [
    { directory: 1, entrySize: 20, nameAt: 12 },
    { directory: 13, entrySize: 32, nameAt: 4 },
  ];
  for (const { directory, entrySize, nameAt } of tables) {
    if (directory >= directoryCount) continue;
    const table = inFile(data.readUInt32LE(directories + directory * 8));
    if (table === null) continue;
    for (let at = table; at + entrySize <= data.length; at += entrySize) {
      const entry = data.subarray(at, at + entrySize);
      if (entry.every((byte) => byte === 0)) break;
      const name = inFile(entry.readUInt32LE(nameAt));
      if (name === null) break;
      names.push(data.toString('latin1', name, data.indexOf(0, name)).toLowerCase());
    }
  }
  return names;
}

/** Parts of the Visual C++ runtime, which is installed separately and not on every computer. */
const VISUAL_CPP_RUNTIME =
  /^(msvcp|vcruntime|concrt|vcomp|vccorlib|vcamp|mfc|ucrtbased)[0-9a-z_]*\.dll$/;

/**
 * Every part of that runtime a program in the app asks for is in the app: beside the
 * program that asks, or beside the one that loaded it (Adle itself, or the core's Python).
 * Returns the complaints, so that a caller can say them all at once.
 */
export function missingRuntime(appFolder) {
  const core = path.join(appFolder, 'resources', 'core');
  const programs = [];
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const item = path.join(directory, entry.name);
      if (entry.isDirectory()) walk(item);
      else if (/\.(exe|dll|pyd|node)$/i.test(entry.name)) programs.push(item);
    }
  };
  walk(appFolder);
  const missing = [];
  for (const program of programs) {
    const home = program.startsWith(core + path.sep) ? core : appFolder;
    for (const library of importsOf(program)) {
      if (!VISUAL_CPP_RUNTIME.test(library)) continue;
      const brought = [path.dirname(program), home].some((folder) =>
        existsSync(path.join(folder, library)),
      );
      if (!brought) missing.push(`${path.relative(appFolder, program)} asks for ${library}`);
    }
  }
  return { programs: programs.length, missing };
}

/**
 * The core's Python makes an environment of its own, with pip in it, as a natural voice is
 * set up in (ADR-042). Nothing is downloaded: venv brings the pip it installs.
 */
function checkMakesEnvironment(executable) {
  const core = path.join(resourcesOf(executable), 'core');
  const python = isWindows() ? path.join(core, 'python.exe') : path.join(core, 'bin', 'python3.12');
  const folder = mkdtempSync(path.join(os.tmpdir(), 'adle-voice-'));
  try {
    const made = spawnSync(python, ['-I', '-m', 'venv', path.join(folder, 'env')], {
      encoding: 'utf8',
      timeout: 300_000,
    });
    if (made.status !== 0) {
      throw new Error(
        `The core's Python could not make an environment: ${made.error?.message ?? (made.stderr || made.stdout)}`,
      );
    }
    const inside = isWindows()
      ? path.join(folder, 'env', 'Scripts', 'python.exe')
      : path.join(folder, 'env', 'bin', 'python');
    const pip = spawnSync(inside, ['-I', '-m', 'pip', '--version'], {
      encoding: 'utf8',
      timeout: 120_000,
    });
    if (pip.status !== 0) {
      throw new Error(
        `An environment the core's Python made has no pip: ${pip.error?.message ?? (pip.stderr || pip.stdout)}`,
      );
    }
  } finally {
    rmSync(folder, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  }
}

/** Whose work the app is built from, and their licences, travel with it. */
function checkNotices(executable) {
  const folder = path.join(resourcesOf(executable), 'licenses');
  const inventory = path.join(folder, 'THIRD-PARTY.md');
  if (!existsSync(inventory)) throw new Error('The package has no licenses/THIRD-PARTY.md.');
  // Adle's own licence: the terms the app is given under go wherever the app goes.
  const own = path.join(folder, 'LICENSE.txt');
  if (!existsSync(own) || !readFileSync(own, 'utf8').includes('GNU GENERAL PUBLIC LICENSE')) {
    throw new Error('The package has no licenses/LICENSE.txt with the GNU GPL in it.');
  }
  const texts = existsSync(path.join(folder, 'texts'))
    ? readdirSync(path.join(folder, 'texts'))
    : [];
  // The fonts and the scene runtime, at the very least, each bring a licence text.
  if (texts.length < 5) throw new Error('The package has too few licence texts to be believed.');
}

async function main() {
  const executable = elsewhere ? path.resolve(elsewhere) : findExecutable();
  if (elsewhere && !existsSync(executable)) {
    throw new Error(`There is no app at ${executable}.`);
  }
  if (!executable) {
    throw new Error(
      `No packaged app in ${buildDir}. Run "node scripts/package.mjs${forTests ? ' --for-tests' : ''}" first.`,
    );
  }
  console.log(`Checking ${executable}`);
  if (bare) {
    console.log('  NOT RUN  the fuses: they are read where the app is built');
  } else {
    await checkFuses(executable);
    console.log('  PASS  fuses are set as intended');
  }
  checkNotices(executable);
  console.log('  PASS  the licence and the third-party notices are in the package');
  if (isWindows()) {
    const { programs, missing } = missingRuntime(path.dirname(executable));
    if (missing.length > 0) {
      throw new Error(
        'The package needs parts of the Visual C++ runtime that it does not bring, and a ' +
          `new computer may not have:\n    ${missing.join('\n    ')}`,
      );
    }
    console.log(
      `  PASS  its ${programs} programs and libraries ask for no Visual C++ runtime it does not bring`,
    );
  }
  if (!forTests) {
    checkWillNotRunAsNode(executable);
    console.log('  PASS  will not run as plain Node');
  }
  checkMakesEnvironment(executable);
  console.log("  PASS  the core's Python makes an environment with pip, for a natural voice");

  const { profile, child, seconds } = await startAndCheck(executable);
  console.log(`  PASS  starts with an empty profile; the core was up after ${seconds} s`);
  console.log('  PASS  nothing in the log of failures');

  // Closed abruptly, as when the computer shuts down: only the app itself is ended here.
  child.kill();
  await sleep(500);
  // The core holds its database open. If it stayed behind, the profile could not be removed.
  rmSync(profile, { recursive: true, force: true, maxRetries: 60, retryDelay: 250 });
  if (existsSync(profile)) throw new Error('The core stayed behind after the app was closed.');
  // That is true on Windows only. Elsewhere a folder can be removed from under a process
  // that has it open, so there the processes themselves are looked at.
  if (!isWindows()) {
    const core = path.join(resourcesOf(executable), 'core');
    await until(
      () => processesFrom(core).length === 0,
      20_000,
      'the core to stop after the app was closed (it stayed behind)',
    );
  }
  console.log('  PASS  the core does not stay behind when the app is ended');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`  FAIL  ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  });
}
