#!/usr/bin/env node
/**
 * Run the end-to-end suite against a packaged build instead of the built files.
 *
 *   node scripts/package.mjs --for-tests     (once; makes apps/desktop/out/test)
 *   node scripts/e2e-packaged.mjs            the whole suite
 *   node scripts/e2e-packaged.mjs security.spec.ts lesson.spec.ts
 *
 * The same journeys, the same assertions. What changes is what is being driven: the
 * app as a learner would have it, started from its own folder, with its own Python.
 */
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { findExecutable } from './smoke-packaged.mjs';

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const desktopDir = path.join(repoRoot, 'apps', 'desktop');
const executable = findExecutable(path.join(desktopDir, 'out', 'test'));

if (!executable) {
  console.error('No packaged test build. Run "node scripts/package.mjs --for-tests" first.');
  process.exit(1);
}

// A first start after packaging is slow while the operating system looks at the new files.
// That is measured and reported by the start-up check; here it would only make the first
// journey miss a wait it was never about.
const warmUp = spawnSync(
  process.execPath,
  [path.join(repoRoot, 'scripts', 'smoke-packaged.mjs'), '--test'],
  {
    cwd: repoRoot,
    stdio: 'inherit',
  },
);
if (warmUp.status !== 0) process.exit(warmUp.status ?? 1);

const playwright = require.resolve('@playwright/test/cli', { paths: [desktopDir] });
const result = spawnSync(process.execPath, [playwright, 'test', ...process.argv.slice(2)], {
  cwd: desktopDir,
  stdio: 'inherit',
  env: { ...process.env, ADLE_E2E_EXECUTABLE: executable },
});
process.exit(result.status ?? 1);
