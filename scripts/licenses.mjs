#!/usr/bin/env node
/**
 * List every third-party package Adle is built from or ships, with its licence, and fail if
 * one is under a licence the project does not accept or says nothing about its licence.
 *
 *   node scripts/licenses.mjs            write docs/engineering/THIRD_PARTY.md
 *   node scripts/licenses.mjs --check    fail if a licence is not accepted or not stated, or if
 *                                        something that ships is missing from that file
 *   node scripts/licenses.mjs --collect=<folder>
 *                                        put the inventory, and the licence text of everything
 *                                        bundled into the app, into a folder (the packaged app's)
 *
 * The check does not compare the whole file. What npm and uv install for development
 * differs from one operating system to the next (a tool's Windows-only helper, a bundler's
 * binary for one processor), so the full list is true only where it was written. What ships
 * to a learner is the same everywhere, and that part is checked line by line.
 *
 * Two lists, because they are two different questions:
 *
 *   - What ships to a learner: the Python packages installed into the packaged core (the
 *     run-time set from uv.lock), and the JavaScript that the build bundles into the app.
 *   - What the project is built and tested with: everything npm and uv install for
 *     development. None of it reaches a learner, but its licences still bind the developers.
 *
 * Electron and Python carry their own licence files into the packaged folder. A file kept
 * in the repository itself (a font no package manager offers) is listed by hand, below.
 */
import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputFile = path.join(repoRoot, 'docs', 'engineering', 'THIRD_PARTY.md');
const check = process.argv.includes('--check');
const collectInto =
  process.argv.find((argument) => argument.startsWith('--collect='))?.slice('--collect='.length) ??
  null;

/**
 * Licences nothing Adle is built from may be under without a decision of its own. Adle is
 * under the GNU GPL, version 3 only (ADR-033). Some of these cannot be combined with that
 * at all (GPL-2.0-only, SSPL, a non-commercial or "source available" licence); the others
 * can, and would still change what Adle owes to whoever receives it.
 */
const REFUSED = /\b(A?GPL|LGPL|SSPL|EUPL|OSL|CC-BY-NC|CC-BY-SA|BUSL|Commons Clause)\b/i;
/** A dual licence is fine if one side of an "OR" is acceptable. */
const acceptable = (licence) =>
  licence.split(/\s+OR\s+/i).some((choice) => !REFUSED.test(choice.replace(/[()]/g, '')));

/**
 * JavaScript that the build puts into the app a learner runs. Kept by hand: these are the
 * packages imported by the renderer, the player frame, and the main process. What ships is
 * these and whatever they depend on; the bundler leaves out what is never reached, so the
 * list below is at most what ships. Everything else npm installs is a tool.
 */
const SHIPPED_JS_ROOTS = [
  '@fontsource-variable/geist',
  '@fontsource-variable/geist-mono',
  // The typeface scenes are drawn with, in the player frame. Not the interface's.
  '@fontsource/inter',
  '@wanimjs/wanim',
  'katex',
  'lucide-react',
  'react',
  'react-dom',
];

/**
 * What ships that no package manager knows about: files kept in the repository, each
 * beside the text of its licence. Kept by hand, and checked to be there.
 */
const VENDORED = [
  {
    name: 'Geist Serif (Regular)',
    version: 'as in geist 1.9.2',
    licence: 'OFL-1.1',
    where: 'packages/design-system/src/fonts/geist-serif',
    files: ['GeistSerif-Regular.woff2', 'LICENSE.txt'],
  },
];

// -- npm ------------------------------------------------------------------------------------

function licenceOfManifest(manifest) {
  const { license, licenses } = manifest;
  if (typeof license === 'string' && license.trim()) return license.trim();
  if (license && typeof license === 'object' && typeof license.type === 'string')
    return license.type;
  if (Array.isArray(licenses)) {
    const types = licenses
      .map((item) => (typeof item === 'string' ? item : item?.type))
      .filter(Boolean);
    if (types.length > 0) return types.join(' OR ');
  }
  return null;
}

function npmPackages() {
  const found = new Map();
  const visit = (modulesDir) => {
    if (!existsSync(modulesDir)) return;
    for (const entry of readdirSync(modulesDir, { withFileTypes: true })) {
      if (entry.name.startsWith('.')) continue;
      const here = path.join(modulesDir, entry.name);
      if (entry.name.startsWith('@')) {
        for (const scoped of readdirSync(here, { withFileTypes: true })) {
          if (scoped.isDirectory() || scoped.isSymbolicLink()) read(path.join(here, scoped.name));
        }
      } else if (entry.isDirectory() || entry.isSymbolicLink()) {
        read(here);
      }
    }
  };
  const read = (packageDir) => {
    const manifestFile = path.join(packageDir, 'package.json');
    if (!existsSync(manifestFile)) return;
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(manifestFile, 'utf8'));
    } catch {
      return;
    }
    // The project's own workspaces are linked into node_modules; they are not third parties.
    if (!manifest.name || !manifest.version || manifest.name.startsWith('@adle/')) return;
    found.set(`${manifest.name}@${manifest.version}`, {
      name: manifest.name,
      version: manifest.version,
      licence: licenceOfManifest(manifest),
      needs: Object.keys(manifest.dependencies ?? {}),
      dir: packageDir,
    });
    visit(path.join(packageDir, 'node_modules'));
  };
  visit(path.join(repoRoot, 'node_modules'));
  return [...found.values()].sort(
    (a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version),
  );
}

/** The roots and everything they depend on, by name. */
function shippedNames(packages) {
  const byName = new Map();
  for (const item of packages) byName.set(item.name, [...(byName.get(item.name) ?? []), item]);
  const names = new Set();
  const visit = (name) => {
    if (names.has(name)) return;
    names.add(name);
    for (const item of byName.get(name) ?? []) item.needs.forEach(visit);
  };
  SHIPPED_JS_ROOTS.forEach(visit);
  return names;
}

// -- Python ---------------------------------------------------------------------------------

const normalise = (name) => name.toLowerCase().replace(/[-_.]+/g, '-');

/** The packages that go into the packaged core: what uv.lock says, without development tools. */
function runtimePythonNames() {
  const exported = spawnSync(
    'uv',
    [
      'export',
      '--directory',
      path.join(repoRoot, 'services', 'core'),
      '--frozen',
      '--no-dev',
      '--no-emit-project',
      '--no-hashes',
      '--format',
      'requirements-txt',
      '--quiet',
    ],
    { encoding: 'utf8' },
  );
  if (exported.status !== 0) throw new Error(`uv export failed: ${exported.stderr}`);
  return new Set(
    exported.stdout
      .split(/\r?\n/)
      .map((line) => /^([A-Za-z0-9_.-]+)==/.exec(line.trim())?.[1])
      .filter(Boolean)
      .map(normalise),
  );
}

function licenceOfMetadata(text) {
  const header = (name) => new RegExp(`^${name}:\\s*(.+)$`, 'mi').exec(text)?.[1]?.trim();
  const expression = header('License-Expression');
  if (expression) return expression;
  const classifiers = [...text.matchAll(/^Classifier:\s*License ::\s*(.+)$/gim)]
    .map((match) => match[1].replace(/^OSI Approved ::\s*/, '').trim())
    .filter((value) => value && value !== 'OSI Approved');
  if (classifiers.length > 0) return classifiers.join(' OR ');
  const plain = header('License');
  // Some packages paste the whole licence text here; the first line names it well enough.
  return plain && plain.length < 80 && plain !== 'UNKNOWN' ? plain : null;
}

function pythonPackages() {
  const venv = path.join(repoRoot, 'services', 'core', '.venv');
  const sitePackages = [
    path.join(venv, 'Lib', 'site-packages'),
    path.join(venv, 'lib', 'python3.12', 'site-packages'),
  ].find((candidate) => existsSync(candidate));
  if (!sitePackages)
    throw new Error('The core environment is not set up. Run "npm run core:sync".');
  const runtime = runtimePythonNames();
  const packages = [];
  for (const entry of readdirSync(sitePackages)) {
    if (!entry.endsWith('.dist-info')) continue;
    const metadataFile = path.join(sitePackages, entry, 'METADATA');
    if (!existsSync(metadataFile)) continue;
    const text = readFileSync(metadataFile, 'utf8');
    const name = /^Name:\s*(.+)$/m.exec(text)?.[1]?.trim();
    const version = /^Version:\s*(.+)$/m.exec(text)?.[1]?.trim();
    if (!name || !version || normalise(name) === 'adle-core') continue;
    packages.push({
      name,
      version,
      licence: licenceOfMetadata(text),
      shipped: runtime.has(normalise(name)),
    });
  }
  return packages.sort((a, b) => a.name.localeCompare(b.name));
}

// -- the report -----------------------------------------------------------------------------

/**
 * Licences read by hand, for packages whose own metadata does not state one in a form a
 * program can read. Each was checked against the licence file the package ships.
 */
const READ_BY_HAND = {};

function withKnownLicence(item) {
  return { ...item, licence: item.licence ?? READ_BY_HAND[item.name] ?? null };
}

const row = (item) =>
  `| \`${item.name}\` | ${item.version} | ${item.licence ?? '**not stated**'} |`;

function table(rows) {
  return ['| Package | Version | Licence |', '|---|---|---|', ...rows.map(row)].join('\n');
}

function countByLicence(items) {
  const counts = new Map();
  for (const item of items)
    counts.set(item.licence ?? 'not stated', (counts.get(item.licence ?? 'not stated') ?? 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([licence, count]) => `| ${licence} | ${count} |`)
    .join('\n');
}

function build() {
  const npm = npmPackages().map(withKnownLicence);
  const python = pythonPackages().map(withKnownLicence);
  const shipped = shippedNames(npm);
  const shippedJs = npm.filter((item) => shipped.has(item.name));
  const missingShipped = SHIPPED_JS_ROOTS.filter(
    (name) => !shippedJs.some((item) => item.name === name),
  );
  const shippedPython = python.filter((item) => item.shipped);

  const everything = [...npm, ...python];
  const problems = [
    ...everything
      .filter((item) => item.licence === null)
      .map((item) => `${item.name} ${item.version}: no licence stated`),
    ...everything
      .filter((item) => item.licence !== null && !acceptable(item.licence))
      .map((item) => `${item.name} ${item.version}: ${item.licence} is not accepted`),
    ...missingShipped.map((name) => `${name}: listed as shipped but not installed`),
    ...VENDORED.flatMap((item) =>
      item.files
        .filter((name) => !existsSync(path.join(repoRoot, item.where, name)))
        .map((name) => `${item.name}: ${item.where}/${name} is missing`),
    ),
  ];
  const vendoredRows = VENDORED.map(
    (item) =>
      '| ' + [item.name, item.version, item.licence, '`' + item.where + '`'].join(' | ') + ' |',
  );

  const text = `# Third-party software

Generated by \`node scripts/licenses.mjs\` from what is installed. Do not edit by hand; run
\`npm run licenses\` after changing a dependency. \`npm run licenses:check\`, which is part of
\`npm run check\`, fails if any installed package states no licence, is under one that needs
a decision first (GPL, AGPL, LGPL, SSPL and the like: Adle is under the GNU GPL, version 3
only, and not everything can be combined with that), or if something that ships is missing
from the lists below.

The development lists were written on Windows. Other systems install a few packages more or
fewer; the lists of what ships are the same everywhere.

## What ships to a learner

Electron (MIT, with Chromium's notices) and Python (PSF-2.0) carry their own licence files
into the packaged folder. Beside them:

### In the app (bundled JavaScript and fonts)

The packages the app's code imports, and everything they depend on. The bundler leaves out
what is never reached, so this is at most what ships.

${table(shippedJs)}

### In the app (files kept in this repository, each beside its licence)

| File | Version | Licence | Where |
|---|---|---|---|
${vendoredRows.join('\n')}

### In the core (Python packages, from \`uv.lock\`)

${table(shippedPython)}

## What the project is built and tested with

None of this reaches a learner.

### npm: ${npm.length} packages

| Licence | Packages |
|---|---|
${countByLicence(npm)}

### Python development tools: ${python.length - shippedPython.length} packages

${table(python.filter((item) => !item.shipped))}
`;
  const shippedRows = [...[...shippedJs, ...shippedPython].map(row), ...vendoredRows];
  return { text, problems, shippedRows, shippedJs };
}

/** The file in a package that holds the text of its licence, if it ships one. */
function licenceFileOf(packageDir) {
  const names = readdirSync(packageDir).filter((name) =>
    /^(licen[cs]e|copying|notice)(\.[a-z]+|-[a-z0-9.-]+)?$/i.test(name),
  );
  return names.length > 0 ? path.join(packageDir, names.sort()[0]) : null;
}

/**
 * Put what a learner is owed with the app into a folder: the inventory, and the text of
 * the licence of everything bundled into the app's own code and styles. The Python
 * packages carry their licences inside the core already (their `dist-info` folders), and
 * Electron and Python bring their own.
 */
function collect(folder, inventory, shippedJs) {
  const texts = path.join(folder, 'texts');
  mkdirSync(texts, { recursive: true });
  writeFileSync(path.join(folder, 'THIRD-PARTY.md'), inventory);
  const without = [];
  for (const item of shippedJs) {
    const source = licenceFileOf(item.dir);
    if (!source) {
      without.push(`${item.name} ${item.version} (${item.licence})`);
      continue;
    }
    copyFileSync(source, path.join(texts, `${item.name.replace(/[@/]/g, '_')}.txt`));
  }
  for (const item of VENDORED) {
    copyFileSync(
      path.join(repoRoot, item.where, 'LICENSE.txt'),
      path.join(texts, `${item.name.replace(/[^A-Za-z0-9]+/g, '_').replace(/_+$/, '')}.txt`),
    );
  }
  writeFileSync(
    path.join(folder, 'README.txt'),
    [
      "Adle is built from other people's work, used under their licences.",
      '',
      'THIRD-PARTY.md lists every package and its licence.',
      'texts/ has the licence text of what is bundled into the app itself.',
      'The Python packages inside resources/core each carry their own licence',
      '(in their .dist-info folders), and Electron and Chromium theirs, beside',
      'the app.',
      ...(without.length > 0
        ? [
            '',
            'These packages ship no licence file of their own; THIRD-PARTY.md names their licence:',
            ...without.map((line) => `  ${line}`),
          ]
        : []),
      '',
    ].join('\n'),
  );
  return { copied: shippedJs.length + VENDORED.length - without.length, without };
}

const { text, problems, shippedRows, shippedJs } = build();
if (problems.length > 0) {
  console.error('Licences that need attention:');
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exitCode = 1;
}
if (check) {
  const current = existsSync(outputFile)
    ? readFileSync(outputFile, 'utf8').replace(/\r\n/g, '\n')
    : '';
  const unlisted = shippedRows.filter((line) => !current.includes(line));
  if (unlisted.length > 0) {
    console.error('docs/engineering/THIRD_PARTY.md does not list everything that ships:');
    for (const line of unlisted) console.error(`  ${line}`);
    console.error('Run "npm run licenses".');
    process.exitCode = 1;
  } else if (problems.length === 0) {
    console.log('Third-party licences are listed and accepted.');
  }
} else if (collectInto) {
  const { copied, without } = collect(path.resolve(collectInto), text, shippedJs);
  console.log(
    `Collected the inventory and ${copied} licence texts` +
      (without.length > 0 ? ` (${without.length} packages ship none of their own)` : ''),
  );
} else {
  writeFileSync(outputFile, text);
  console.log(`Wrote ${path.relative(repoRoot, outputFile)}`);
}
