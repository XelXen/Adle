#!/usr/bin/env node
/**
 * Write what a release says about itself: what it is, how to install it on each system and
 * what that system will say about an app nobody has signed, and where the full list of
 * changes is. Printed, for the release workflow to hand to GitHub.
 *
 *   node scripts/release-notes.mjs                       for the version in package.json
 *   node scripts/release-notes.mjs --tag=v0.1.0-alpha.1  the same, and fail unless that tag
 *                                                        is this version's
 *
 * The opening comes from CHANGELOG.md: the lines under the version's heading, before its
 * first list. A release cannot be made of a version the changelog does not have.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPOSITORY = 'https://github.com/XelXen/Adle';

/** What the changelog says to open a version's section with, as paragraphs. */
export function opening(changelog, version) {
  const lines = changelog.replace(/\r\n/g, '\n').split('\n');
  const start = lines.findIndex((line) => line.startsWith(`## [${version}]`));
  if (start === -1) return null;
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((line) => line.startsWith('## ') || line.startsWith('### '));
  return rest
    .slice(0, end === -1 ? rest.length : end)
    .join('\n')
    .trim();
}

export function notes(version, intro) {
  const file = (rest) => `\`Adle-${version}-${rest}\``;
  const tag = `v${version}`;
  return `${intro}

## Installing

| System | Download | Then |
|---|---|---|
| Windows 10 or 11 (64-bit) | ${file('windows-x64-setup.exe')} | Run it. It installs for you alone and asks for no administrator. |
| macOS, Apple processor | ${file('macos-arm64.dmg')} | Open it and drag Adle onto Applications. |
| macOS, Intel processor | ${file('macos-x64.dmg')} | The same. |
| Debian, Ubuntu and their kin | ${file('linux-x64.deb')} | \`sudo apt install ./${`Adle-${version}-linux-x64.deb`}\` |
| Any other Linux | ${file('linux-x64.tar.gz')} | Unpack it and run \`Adle\` inside. |

Nobody has signed these builds, and each system says so in its own way:

- **Windows** shows "Windows protected your PC". Choose **More info**, then **Run anyway**.
- **macOS** says Adle could not be checked. Try to open it once, then go to **System
  Settings → Privacy & Security** and choose **Open Anyway**. Or, in Terminal:
  \`xattr -dr com.apple.quarantine /Applications/Adle.app\`
- **Linux**, from the tarball only: on Ubuntu 24.04 and later an unpacked app may refuse to
  start, because the system does not let it build its sandbox. Adle will not run without
  one. Use the \`.deb\`, which sets that up.

\`SHA256SUMS.txt\` lists a checksum for every file here.

Adle needs no account. Lessons written by an AI need a key of your own for AIHubMix or
NVIDIA NIM; the sample course works without one. On Linux that key is kept in your
desktop's keyring (GNOME Keyring or KWallet); where there is none, Adle says so and does
not keep it.

## What is in it

[CHANGELOG.md](${REPOSITORY}/blob/${tag}/CHANGELOG.md) has every change. This is an alpha:
[tell us what breaks](${REPOSITORY}/issues).

Adle is free software under the [GNU General Public License, version 3](${REPOSITORY}/blob/${tag}/LICENSE).
The source of this release is attached below, as GitHub attaches it to every release.
`;
}

function main() {
  const { version } = JSON.parse(
    readFileSync(path.join(repoRoot, 'apps', 'desktop', 'package.json'), 'utf8'),
  );
  const tag = process.argv.find((item) => item.startsWith('--tag='))?.slice('--tag='.length);
  if (tag !== undefined && tag !== `v${version}`) {
    throw new Error(`The tag is ${tag}, and the version in package.json is ${version}.`);
  }
  const intro = opening(readFileSync(path.join(repoRoot, 'CHANGELOG.md'), 'utf8'), version);
  if (!intro) {
    throw new Error(`CHANGELOG.md has no section for ${version}, or nothing to open it with.`);
  }
  process.stdout.write(notes(version, intro));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
