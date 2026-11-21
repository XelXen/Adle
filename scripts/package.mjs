#!/usr/bin/env node
/**
 * Build Adle as an application folder that runs on a computer with nothing else installed.
 *
 *   node scripts/package.mjs              the release build, in apps/desktop/out/release/
 *   node scripts/package.mjs --for-tests  the same build with the debugger left reachable,
 *                                         in apps/desktop/out/test/, so that the end-to-end
 *                                         suite can drive it. Never give this one to anyone.
 *   --skip-build   reuse apps/desktop/dist as it is
 *   --skip-core    reuse the staged core from the last run
 *
 * What goes in (ADR-019):
 *
 *   <Adle>/resources/app.asar    package.json, dist/ (main, preload, renderer, player), icons.
 *                                Everything the app needs is already bundled into dist/, so
 *                                there is no node_modules.
 *   <Adle>/resources/core/       a private Python with the core and its locked dependencies
 *                                installed into it. No Python is needed on the computer, and
 *                                one that is there is never used.
 *
 * The private Python is the one uv manages for development (a relocatable build), copied
 * without the parts the core never uses. Dependencies come from uv.lock, with hashes.
 */
import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const desktopDir = path.join(repoRoot, 'apps', 'desktop');
const coreDir = path.join(repoRoot, 'services', 'core');
const outDir = path.join(desktopDir, 'out');
const stageDir = path.join(outDir, 'stage');

/** The app's identity on macOS, and the name its settings are kept under there. */
const APP_ID = 'io.github.xelxen.adle';

const flags = new Set(process.argv.slice(2));
const forTests = flags.has('--for-tests');
const isWindows = process.platform === 'win32';

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: repoRoot, stdio: 'inherit', ...options });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed (exit ${result.status ?? 'none'}).`);
  }
}

function sizeOf(target) {
  // A link is not what it points at: a framework on macOS is reached by three of them, and
  // followed, each would be counted again.
  const stats = lstatSync(target);
  if (stats.isSymbolicLink()) return 0;
  if (!stats.isDirectory()) return stats.size;
  return readdirSync(target).reduce((total, name) => total + sizeOf(path.join(target, name)), 0);
}

const megabytes = (bytes) => `${(bytes / (1024 * 1024)).toFixed(0)} MB`;

// -- the app ------------------------------------------------------------------------------

function stageApp() {
  const appDir = path.join(stageDir, 'app');
  rmSync(appDir, { recursive: true, force: true });
  mkdirSync(appDir, { recursive: true });
  const manifest = JSON.parse(readFileSync(path.join(desktopDir, 'package.json'), 'utf8'));
  // Only what Electron reads. Dependencies are bundled into dist/ already.
  writeFileSync(
    path.join(appDir, 'package.json'),
    `${JSON.stringify(
      {
        name: 'adle',
        productName: manifest.productName,
        version: manifest.version,
        description: manifest.description,
        license: manifest.license,
        main: manifest.main,
      },
      null,
      2,
    )}\n`,
  );
  cpSync(path.join(desktopDir, 'dist'), path.join(appDir, 'dist'), {
    recursive: true,
    // Source maps point back at the source tree of the computer that built them.
    filter: (source) => !source.endsWith('.map'),
  });
  // The window reads its icon from here at run time (`paths.windowIcon`).
  cpSync(path.join(desktopDir, 'assets', 'icons'), path.join(appDir, 'assets', 'icons'), {
    recursive: true,
  });
  return { appDir, version: manifest.version, productName: manifest.productName };
}

// -- the core -----------------------------------------------------------------------------

/** Parts of a Python installation the core never uses. Paths are relative, lower case. */
const UNUSED_ON_WINDOWS = [
  'include',
  'libs',
  'scripts',
  'tcl',
  'pythonw.exe',
  'dlls/_tkinter.pyd',
  'dlls/tcl86t.dll',
  'dlls/tk86t.dll',
  'lib/site-packages',
  'lib/test',
  'lib/idlelib',
  'lib/tkinter',
  'lib/turtledemo',
  'lib/ensurepip',
  'lib/venv',
  'lib/lib2to3',
  'lib/pydoc_data',
];
const UNUSED_ELSEWHERE = [
  'include',
  'share',
  'lib/pkgconfig',
  'lib/tcl8',
  'lib/tcl8.6',
  'lib/tk8.6',
  'lib/itcl4.2.4',
  'lib/thread2.8.9',
  'lib/python3.12/site-packages',
  'lib/python3.12/test',
  'lib/python3.12/idlelib',
  'lib/python3.12/tkinter',
  'lib/python3.12/turtledemo',
  'lib/python3.12/ensurepip',
  'lib/python3.12/venv',
  'lib/python3.12/lib2to3',
  'lib/python3.12/pydoc_data',
];

/**
 * And what is named with a version or a system in it. The static library and the build
 * settings are what another program is compiled against to embed Python; on a Mac they were
 * half as large again as everything the core runs. Tcl and Tk are for windows the core
 * never opens.
 */
const UNUSED_ELSEWHERE_BY_PATTERN = [
  /^lib\/python3\.12\/config-3\.12-[^/]+$/,
  /^lib\/libpython[^/]*\.a$/,
  /^lib\/(lib)?(tcl|tk|itcl|thread)[^/]*$/,
  /^lib\/python3\.12\/lib-dynload\/_tkinter[^/]*$/,
];

/** Where the Python that uv manages for this project is installed. */
function basePython() {
  const config = path.join(coreDir, '.venv', 'pyvenv.cfg');
  if (!existsSync(config)) {
    throw new Error('The core environment is not set up. Run "npm run core:sync" first.');
  }
  const home = /^home\s*=\s*(.+)$/m.exec(readFileSync(config, 'utf8'))?.[1]?.trim();
  if (!home) throw new Error(`No "home" in ${config}.`);
  // On Windows "home" is the installation; elsewhere it is its bin/ folder.
  const installation = realpathSync(isWindows ? home : path.dirname(home));
  // It must be a Python that uv itself manages: a build that can be moved, in a folder of
  // its own. An environment made from the computer's Python would have "/usr" here, and
  // what would be copied into the app is the computer. Seen coming on Linux, where the
  // system has a Python of the right version; CI asks uv for its own every time.
  const looksManaged =
    /cpython-3\.12[^/\\]*$/.test(installation) &&
    existsSync(
      isWindows
        ? path.join(installation, 'python.exe')
        : path.join(installation, 'bin', 'python3.12'),
    );
  if (!looksManaged) {
    throw new Error(
      `The core environment uses the Python at ${installation}, which is not one uv manages. ` +
        'Make it again with "uv sync --project services/core --python-preference only-managed".',
    );
  }
  return installation;
}

function stageCore() {
  const target = path.join(stageDir, 'core');
  rmSync(target, { recursive: true, force: true });
  const source = basePython();
  const unused = new Set(isWindows ? UNUSED_ON_WINDOWS : UNUSED_ELSEWHERE);
  console.log(`Copying Python from ${source}`);
  cpSync(source, target, {
    recursive: true,
    dereference: true,
    filter: (item) => {
      const relative = path.relative(source, item).split(path.sep).join('/').toLowerCase();
      if (unused.has(relative) || path.basename(item) === '__pycache__') return false;
      return isWindows || !UNUSED_ELSEWHERE_BY_PATTERN.some((pattern) => pattern.test(relative));
    },
  });

  const python = isWindows
    ? path.join(target, 'python.exe')
    : path.join(target, 'bin', 'python3.12');
  const sitePackages = isWindows
    ? path.join(target, 'Lib', 'site-packages')
    : path.join(target, 'lib', 'python3.12', 'site-packages');
  mkdirSync(sitePackages, { recursive: true });

  // Exactly what uv.lock says, checked against its hashes, and nothing for development.
  const requirements = path.join(stageDir, 'core-requirements.txt');
  run('uv', [
    'export',
    '--directory',
    coreDir,
    '--frozen',
    '--no-dev',
    '--no-emit-project',
    '--format',
    'requirements-txt',
    '--output-file',
    requirements,
    '--quiet',
  ]);
  const install = ['pip', 'install', '--python', python, '--target', sitePackages, '--quiet'];
  run('uv', [...install, '--require-hashes', '--compile-bytecode', '-r', requirements]);
  // The core itself, as a wheel, so that its data files travel with it. It is built with
  // the development environment: the copy above has lost the parts a build needs.
  const wheels = path.join(stageDir, 'wheels');
  rmSync(wheels, { recursive: true, force: true });
  run('uv', ['build', '--wheel', '--directory', coreDir, '--out-dir', wheels, '--quiet']);
  const [wheel] = readdirSync(wheels).filter((name) => name.endsWith('.whl'));
  if (!wheel) throw new Error('The core was not built into a wheel.');
  run('uv', [...install, '--no-deps', '--compile-bytecode', path.join(wheels, wheel)]);
  // The standard library, compiled once here: an installed copy may sit where it cannot write.
  run(python, ['-I', '-m', 'compileall', '-q', path.dirname(sitePackages)], { stdio: 'ignore' });

  // The process is Adle's core, and should be called that wherever processes are listed.
  const executable = isWindows ? path.join(target, 'adle-core.exe') : python;
  if (isWindows) renameSync(python, executable);

  // It must start, alone, with everything it imports, before it is shipped.
  run(
    executable,
    [
      '-I',
      '-c',
      'import adle_core.__main__, adle_core.ingestion.worker, uvicorn, sqlalchemy, alembic, ' +
        'pypdf, docx, markdown_it, httpx2, sqlite3; ' +
        'from importlib import resources; ' +
        'assert resources.files("adle_core").joinpath("migrations", "versions").is_dir(); ' +
        'assert resources.files("adle_core").joinpath("sample_course", "course.json").is_file(); ' +
        // FastAPI depends on the interface of a telemetry library. Without its other half
        // nothing is recorded and nothing can be sent; that half must never arrive unnoticed.
        'import importlib.util; ' +
        'assert importlib.util.find_spec("opentelemetry.sdk") is None',
    ],
    { cwd: target, env: { SystemRoot: process.env.SystemRoot ?? '', PATH: '' } },
  );
  return target;
}

// -- putting it together ------------------------------------------------------------------

async function packageApp({ appDir, productName, version }, coreStage) {
  const { packager } = await import('@electron/packager');
  const electronVersion = require(
    path.join(repoRoot, 'node_modules', 'electron', 'package.json'),
  ).version;
  const destination = path.join(outDir, forTests ? 'test' : 'release');
  rmSync(destination, { recursive: true, force: true });

  const [built] = await packager({
    dir: appDir,
    out: destination,
    name: productName,
    appVersion: version,
    electronVersion,
    platform: process.platform,
    arch: process.arch,
    asar: true,
    prune: false,
    overwrite: true,
    icon: path.join(desktopDir, 'assets', 'icons', 'icon'),
    extraResource: [coreStage],
    appCopyright: 'Copyright © 2026 XelXen. GNU General Public License, version 3.',
    win32metadata: { CompanyName: 'Adle', FileDescription: 'Adle', ProductName: 'Adle' },
    // macOS: who the app is to the system (its settings, its keychain items), and where it
    // is listed.
    appBundleId: APP_ID,
    appCategoryType: 'public.app-category.education',
    quiet: true,
  });
  if (!built) throw new Error('Nothing was packaged.');
  return built;
}

function executableOf(appFolder, productName) {
  if (isWindows) return path.join(appFolder, `${productName}.exe`);
  if (process.platform === 'darwin') {
    return path.join(appFolder, `${productName}.app`, 'Contents', 'MacOS', productName);
  }
  return path.join(appFolder, productName);
}

/**
 * Switch off the ways an Electron binary can be turned into something else: run as plain
 * Node, take Node options from the environment, load code from outside the archive, or be
 * debugged from outside. The last one is what the end-to-end suite uses, so the build made
 * for tests keeps it; that is the only difference between the two builds.
 */
async function hardenBinary(executable) {
  const { flipFuses, FuseV1Options, FuseVersion } = await import('@electron/fuses');
  await flipFuses(executable, {
    version: FuseVersion.V1,
    [FuseV1Options.RunAsNode]: false,
    [FuseV1Options.EnableCookieEncryption]: true,
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
    [FuseV1Options.EnableNodeCliInspectArguments]: forTests,
    [FuseV1Options.OnlyLoadAppFromAsar]: true,
    [FuseV1Options.GrantFileProtocolExtraPrivileges]: false,
  });
}

/**
 * macOS, and Apple's own processors above all, will not start a program whose signature
 * does not match its files, and the fuses and the notices have just changed them. This is
 * the signature anyone can make ("ad hoc"): it names no one and vouches for nothing, and it
 * is not the signature of a developer Apple knows. A Mac still asks before it opens an app
 * signed this way that came from the internet; the readme says what to do then.
 */
function signForThisComputerOnly(appFolder, productName) {
  const bundle = path.join(appFolder, `${productName}.app`);
  run('codesign', ['--force', '--deep', '--sign', '-', bundle]);
  run('codesign', ['--verify', '--deep', '--strict', bundle]);
}

async function main() {
  mkdirSync(stageDir, { recursive: true });
  if (!flags.has('--skip-build')) {
    const { build } = await import('../apps/desktop/scripts/build.mjs');
    await build();
  }
  const app = stageApp();
  const coreStage =
    flags.has('--skip-core') && existsSync(path.join(stageDir, 'core'))
      ? path.join(stageDir, 'core')
      : stageCore();

  const appFolder = await packageApp(app, coreStage);
  const executable = executableOf(appFolder, app.productName);
  await hardenBinary(executable);

  const resources =
    process.platform === 'darwin'
      ? path.join(appFolder, `${app.productName}.app`, 'Contents', 'Resources')
      : path.join(appFolder, 'resources');
  // What a learner is owed with the app: whose work it is built from, and their licences.
  const notices = spawnSync(
    process.execPath,
    [
      path.join(repoRoot, 'scripts', 'licenses.mjs'),
      `--collect=${path.join(resources, 'licenses')}`,
    ],
    { cwd: repoRoot, encoding: 'utf8' },
  );
  if (notices.status !== 0) {
    throw new Error(`The third-party notices could not be collected: ${notices.stderr}`);
  }
  // And the licence Adle itself is under: whoever is given the app is given its terms.
  copyFileSync(path.join(repoRoot, 'LICENSE'), path.join(resources, 'licenses', 'LICENSE.txt'));
  for (const needed of [
    'app.asar',
    'core',
    path.join('licenses', 'THIRD-PARTY.md'),
    path.join('licenses', 'LICENSE.txt'),
  ]) {
    if (!existsSync(path.join(resources, needed))) {
      throw new Error(`The packaged app has no resources/${needed}.`);
    }
  }
  if (process.platform === 'darwin') signForThisComputerOnly(appFolder, app.productName);
  console.log(`\nPackaged ${forTests ? '(for tests) ' : ''}into ${appFolder}`);
  console.log(`  app.asar  ${megabytes(sizeOf(path.join(resources, 'app.asar')))}`);
  console.log(`  core      ${megabytes(sizeOf(path.join(resources, 'core')))}`);
  console.log(`  in all    ${megabytes(sizeOf(appFolder))}`);
  console.log(`  run       ${executable}`);
}

main().catch((error) => {
  console.error(`\nPackaging failed: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
