#!/usr/bin/env node
/**
 * Turn the release build into what a person downloads, with the tools each system has for
 * it and nothing else (ADR-034):
 *
 *   Windows   Adle-<version>-windows-<arch>-setup.exe   Inno Setup: for the person installing,
 *                                                       no administrator needed
 *   macOS     Adle-<version>-macos-<arch>.dmg           hdiutil: drag Adle to Applications
 *   Linux     Adle-<version>-linux-<arch>.deb           dpkg-deb: Debian, Ubuntu and their kin
 *             Adle-<version>-linux-<arch>.tar.gz        the folder itself, for any other system
 *
 *   node scripts/installer.mjs            make them, in apps/desktop/out/installers/
 *   node scripts/installer.mjs --check    then try each one out: put the app where the
 *                                         installer puts it, start it from outside as the
 *                                         start-up check does, and take it away again
 *
 * Run "node scripts/package.mjs" first: this wraps apps/desktop/out/release exactly as it is.
 *
 * Nothing is signed, by the owner's decision. Windows and macOS will say so to whoever
 * opens one of these; README.md says what to do then.
 *
 * --check changes the computer it runs on (it installs and removes Adle), so it refuses to
 * run outside CI unless it is also given --on-this-computer. On macOS it changes nothing:
 * the disk image is only opened and copied from.
 */
import { spawnSync } from 'node:child_process';
import {
  chmodSync,
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const desktopDir = path.join(repoRoot, 'apps', 'desktop');
const outDir = path.join(desktopDir, 'out');
const installersDir = path.join(outDir, 'installers');
const stageDir = path.join(outDir, 'stage');
const partsDir = path.join(desktopDir, 'installer');
const iconsDir = path.join(desktopDir, 'assets', 'icons');

const flags = new Set(process.argv.slice(2));
const { version } = JSON.parse(readFileSync(path.join(desktopDir, 'package.json'), 'utf8'));
/** What Adle is, to someone looking through the software their system offers. */
const DESCRIPTION =
  'A local-first desktop app that learns what you understand and teaches what you need next.';
const SYSTEMS = { win32: 'windows', darwin: 'macos', linux: 'linux' };
const system = SYSTEMS[process.platform];
const arch = process.arch;
const baseName = `Adle-${version}-${system}-${arch}`;
const HOME_PAGE = 'https://github.com/XelXen/Adle';

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: repoRoot, stdio: 'inherit', ...options });
  if (result.error) throw new Error(`${command} could not be run: ${result.error.message}`);
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed (exit ${result.status ?? 'none'}).`);
  }
}

function capture(command, args) {
  const result = spawnSync(command, args, { cwd: repoRoot, encoding: 'utf8' });
  if (result.error || result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed: ${result.stderr || result.error}`);
  }
  return result.stdout;
}

const megabytes = (file) => `${(statSync(file).size / (1024 * 1024)).toFixed(0)} MB`;

/** The release build of this system, as "node scripts/package.mjs" left it. */
function releaseFolder() {
  const folder = path.join(outDir, 'release', `Adle-${process.platform}-${arch}`);
  if (!existsSync(folder)) {
    throw new Error(`There is no release build at ${folder}. Run "node scripts/package.mjs".`);
  }
  return folder;
}

/** "0.1.0-alpha.1" as the four numbers a Windows version resource takes: "0.1.0.0". */
export function numericVersion(text) {
  const [major = '0', minor = '0', patch = '0'] = text.split('-')[0].split('.');
  return [major, minor, patch, '0'].map((part) => String(Number.parseInt(part, 10) || 0)).join('.');
}

/**
 * "0.1.0-alpha.1" as Debian orders versions: "0.1.0~alpha.1". A hyphen would start a
 * packaging revision, and the alpha would then sort after the release it comes before.
 */
export function debianVersion(text) {
  return text.replace('-', '~');
}

// -- Windows --------------------------------------------------------------------------------

function innoSetupCompiler() {
  const candidates = [
    process.env.ISCC,
    path.join(process.env['ProgramFiles(x86)'] ?? '', 'Inno Setup 6', 'ISCC.exe'),
    path.join(process.env.ProgramFiles ?? '', 'Inno Setup 6', 'ISCC.exe'),
  ].filter(Boolean);
  const found = candidates.find((candidate) => existsSync(candidate));
  if (found) return found;
  const onPath = spawnSync('where', ['iscc'], { encoding: 'utf8' });
  if (onPath.status === 0) return onPath.stdout.split(/\r?\n/)[0].trim();
  throw new Error(
    'Inno Setup is not installed (looked for ISCC.exe). It is on the build machines of ' +
      'GitHub; on your own, install it from https://jrsoftware.org/isinfo.php or set ISCC.',
  );
}

function makeWindowsInstaller(source) {
  const compiler = innoSetupCompiler();
  const name = `${baseName}-setup`;
  run(compiler, [
    '/Qp',
    `/DAppVersion=${version}`,
    `/DNumericVersion=${numericVersion(version)}`,
    `/DSourceDir=${source}`,
    `/DOutputDir=${installersDir}`,
    `/DOutputName=${name}`,
    `/DIconFile=${path.join(iconsDir, 'icon.ico')}`,
    path.join(partsDir, 'windows.iss'),
  ]);
  return [path.join(installersDir, `${name}.exe`)];
}

async function checkWindowsInstaller([setup]) {
  const target = path.join(mkdtempSync(path.join(os.tmpdir(), 'adle-installed-')), 'Adle');
  const log = path.join(installersDir, 'install.log');
  const quiet = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'];
  run(setup, [...quiet, '/CURRENTUSER', `/DIR=${target}`, `/LOG=${log}`]);
  const executable = path.join(target, 'Adle.exe');
  const uninstaller = path.join(target, 'unins000.exe');
  const shortcut = path.join(
    process.env.APPDATA ?? '',
    'Microsoft',
    'Windows',
    'Start Menu',
    'Programs',
    'Adle.lnk',
  );
  for (const expected of [executable, uninstaller, shortcut]) {
    if (!existsSync(expected)) throw new Error(`The installer did not leave ${expected}.`);
  }
  console.log(`  PASS  installed to ${target}, with a shortcut in the Start menu`);
  startFromOutside(executable);

  run(uninstaller, quiet);
  // The uninstaller hands over to a copy of itself and may return before that has finished.
  await until(() => !existsSync(executable) && !existsSync(shortcut), 120_000, 'the uninstall');
  console.log('  PASS  uninstalled: the program and its shortcut are gone');
}

// -- macOS ----------------------------------------------------------------------------------

function makeMacImage(source) {
  const bundle = path.join(source, 'Adle.app');
  if (!existsSync(bundle)) throw new Error(`There is no Adle.app in ${source}.`);
  const stage = path.join(stageDir, 'dmg');
  rmSync(stage, { recursive: true, force: true });
  mkdirSync(stage, { recursive: true });
  // ditto keeps what a plain copy loses: the signature and the links inside the app.
  run('ditto', [bundle, path.join(stage, 'Adle.app')]);
  symlinkSync('/Applications', path.join(stage, 'Applications'));
  const image = path.join(installersDir, `${baseName}.dmg`);
  rmSync(image, { force: true });
  const create = ['create', '-volname', 'Adle', '-srcfolder', stage, '-ov', '-format', 'UDZO'];
  // On a build machine the first try now and then finds the new volume "busy".
  for (let attempt = 1; ; attempt += 1) {
    const result = spawnSync('hdiutil', [...create, image], { stdio: 'inherit' });
    if (result.status === 0) break;
    if (attempt === 3) throw new Error('hdiutil could not make the disk image, three times.');
    console.log(`hdiutil failed (try ${attempt}); trying again.`);
  }
  return [image];
}

function checkMacImage([image]) {
  const work = mkdtempSync(path.join(os.tmpdir(), 'adle-image-'));
  const mount = path.join(work, 'volume');
  mkdirSync(mount);
  run('hdiutil', ['attach', image, '-nobrowse', '-readonly', '-mountpoint', mount]);
  const copy = path.join(work, 'Adle.app');
  try {
    if (!existsSync(path.join(mount, 'Applications'))) {
      throw new Error('The disk image has no link to Applications to drag the app onto.');
    }
    run('ditto', [path.join(mount, 'Adle.app'), copy]);
  } finally {
    run('hdiutil', ['detach', mount]);
  }
  // As a Mac checks it before it will start it: every file is the one that was signed.
  run('codesign', ['--verify', '--deep', '--strict', copy]);
  console.log('  PASS  the app in the disk image is whole, and signed as it was built');
  startFromOutside(path.join(copy, 'Contents', 'MacOS', 'Adle'));
}

// -- Linux ----------------------------------------------------------------------------------

/** What Electron needs from the system it runs on, by the names Debian knows them by. */
const DEBIAN_NEEDS = [
  'libgtk-3-0',
  'libnotify4',
  'libnss3',
  'libxss1',
  'libxtst6',
  'libatspi2.0-0',
  'libgbm1',
  'libasound2 | libasound2t64',
  'libsecret-1-0',
  'xdg-utils',
];

function makeLinuxPackages(source) {
  const debianArch = { x64: 'amd64', arm64: 'arm64' }[arch];
  if (!debianArch) throw new Error(`No Debian name for the processor "${arch}".`);
  const stage = path.join(stageDir, 'deb');
  rmSync(stage, { recursive: true, force: true });
  const app = path.join(stage, 'opt', 'Adle');
  mkdirSync(path.dirname(app), { recursive: true });
  cpSync(source, app, { recursive: true, verbatimSymlinks: true });
  // Chromium's own sandbox helper. Where a system does not let ordinary programs make the
  // namespaces the sandbox is built from (Ubuntu 24.04 and later), this helper makes them,
  // which it can only do when it belongs to root and is marked to run as its owner. The
  // package is built with --root-owner-group, so root it is. Without this the app would
  // refuse to start there rather than run with no sandbox, which is the right refusal.
  chmodSync(path.join(app, 'chrome-sandbox'), 0o4755);

  const share = path.join(stage, 'usr', 'share');
  mkdirSync(path.join(share, 'applications'), { recursive: true });
  copyFileSync(
    path.join(partsDir, 'linux.desktop'),
    path.join(share, 'applications', 'adle.desktop'),
  );
  for (const file of readdirSync(path.join(iconsDir, 'linux'))) {
    const size = path.basename(file, '.png');
    const folder = path.join(share, 'icons', 'hicolor', size, 'apps');
    mkdirSync(folder, { recursive: true });
    copyFileSync(path.join(iconsDir, 'linux', file), path.join(folder, 'adle.png'));
  }
  mkdirSync(path.join(share, 'doc', 'adle'), { recursive: true });
  writeFileSync(
    path.join(share, 'doc', 'adle', 'copyright'),
    [
      'Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/',
      'Upstream-Name: Adle',
      `Source: ${HOME_PAGE}`,
      '',
      'Files: *',
      'Copyright: 2026 XelXen',
      'License: GPL-3',
      ' Adle is free software under the GNU General Public License, version 3. On Debian',
      ' systems its text is in /usr/share/common-licenses/GPL-3; a copy is also installed',
      ' in /opt/Adle/resources/licenses, with the licences of everything Adle is built',
      ' from.',
      '',
    ].join('\n'),
  );
  mkdirSync(path.join(stage, 'usr', 'bin'), { recursive: true });
  symlinkSync('../../opt/Adle/Adle', path.join(stage, 'usr', 'bin', 'adle'));

  const kilobytes = capture('du', ['-sk', stage]).split(/\s+/)[0];
  mkdirSync(path.join(stage, 'DEBIAN'), { recursive: true });
  writeFileSync(
    path.join(stage, 'DEBIAN', 'control'),
    [
      'Package: adle',
      `Version: ${debianVersion(version)}`,
      'Section: education',
      'Priority: optional',
      `Architecture: ${debianArch}`,
      'Maintainer: XelXen <XelXen@users.noreply.github.com>',
      `Installed-Size: ${kilobytes}`,
      `Depends: ${DEBIAN_NEEDS.join(', ')}`,
      `Homepage: ${HOME_PAGE}`,
      'Description: Adaptive learning environment',
      ` ${DESCRIPTION}`,
      '',
    ].join('\n'),
  );
  // Folders made here follow this computer's habits; a package's must be readable by all.
  run('chmod', ['-R', 'u+rwX,go+rX,go-w', stage]);
  chmodSync(path.join(app, 'chrome-sandbox'), 0o4755);

  const debian = path.join(installersDir, `${baseName}.deb`);
  rmSync(debian, { force: true });
  run('dpkg-deb', ['--build', '--root-owner-group', '-Zxz', stage, debian]);

  const tarball = path.join(installersDir, `${baseName}.tar.gz`);
  rmSync(tarball, { force: true });
  run('tar', ['-C', path.dirname(source), '-czf', tarball, path.basename(source)]);
  return [debian, tarball];
}

function checkLinuxPackages([debian, tarball]) {
  const listing = capture('dpkg-deb', ['--contents', debian]);
  const helper = listing.split('\n').find((line) => line.endsWith('./opt/Adle/chrome-sandbox'));
  if (!helper?.startsWith('-rwsr-xr-x root/root')) {
    throw new Error(`The sandbox helper is not root's and set to run as root: ${helper}`);
  }
  console.log('  PASS  the package holds the sandbox helper as root, marked to run as root');

  run('sudo', ['apt-get', 'install', '--yes', '--no-install-recommends', debian]);
  const installed = '/opt/Adle/Adle';
  for (const expected of [
    installed,
    '/usr/bin/adle',
    '/usr/share/applications/adle.desktop',
    '/usr/share/icons/hicolor/256x256/apps/adle.png',
    '/opt/Adle/resources/licenses/LICENSE.txt',
  ]) {
    if (!existsSync(expected)) throw new Error(`The package did not install ${expected}.`);
  }
  console.log('  PASS  installed, with its menu entry, its icons and its licence');
  startFromOutside(installed);
  run('sudo', ['apt-get', 'remove', '--yes', 'adle']);
  if (existsSync(installed)) throw new Error('Removing the package left the app behind.');
  console.log('  PASS  removed again');

  const work = mkdtempSync(path.join(os.tmpdir(), 'adle-tarball-'));
  run('tar', ['-C', work, '-xzf', tarball]);
  const unpacked = path.join(work, `Adle-linux-${arch}`, 'Adle');
  if (!existsSync(unpacked)) throw new Error('The tarball does not unpack to the app.');
  // Unpacked by hand, the sandbox helper is nobody's in particular. The app then starts
  // only where ordinary programs may make namespaces, and says why where they may not.
  const restricted = '/proc/sys/kernel/apparmor_restrict_unprivileged_userns';
  if (existsSync(restricted) && readFileSync(restricted, 'utf8').trim() === '1') {
    console.log('  NOT RUN  the unpacked tarball: this system keeps namespaces from programs');
  } else {
    startFromOutside(unpacked);
  }
}

// -- trying one out -------------------------------------------------------------------------

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function until(condition, timeoutMs, what) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (condition()) return;
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${what}.`);
}

/** The start-up check, pointed at a copy an installer has just put down. */
function startFromOutside(executable) {
  run(process.execPath, [
    path.join(repoRoot, 'scripts', 'smoke-packaged.mjs'),
    `--at=${executable}`,
  ]);
}

async function main() {
  const source = releaseFolder();
  mkdirSync(installersDir, { recursive: true });
  const make = { win32: makeWindowsInstaller, darwin: makeMacImage, linux: makeLinuxPackages };
  const check = { win32: checkWindowsInstaller, darwin: checkMacImage, linux: checkLinuxPackages };
  if (!make[process.platform]) throw new Error(`No installer is made for ${process.platform}.`);

  const made = make[process.platform](source);
  console.log(`\nMade from ${source}`);
  for (const file of made) console.log(`  ${megabytes(file).padStart(7)}  ${file}`);

  if (!flags.has('--check')) return;
  if (process.platform !== 'darwin' && !process.env.CI && !flags.has('--on-this-computer')) {
    throw new Error(
      '--check installs Adle on this computer and removes it again. It runs by itself only ' +
        'in CI; here, add --on-this-computer if that is what you mean.',
    );
  }
  console.log('\nTrying it out');
  await check[process.platform](made);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`\nFAIL  ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  });
}
