#!/usr/bin/env node
/**
 * Run every fast quality gate, in order, and report each one's outcome.
 *
 *   node scripts/check.mjs          # static checks + unit tests (TypeScript and Python)
 *   node scripts/check.mjs --e2e    # also build the app and run the Electron end-to-end suite
 *
 * This is what a contributor (or agent) runs before committing. CI runs the
 * same steps. A step that did not run is reported as NOT RUN, never as passed.
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const withE2e = process.argv.includes('--e2e');
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

const steps = [
  ['Contracts up to date', ['run', 'contracts:check']],
  ['Scene name allowlist up to date', ['run', 'wanim-names:check']],
  ['Format (prettier)', ['run', 'format:check']],
  ['Lint (eslint)', ['run', 'lint']],
  ['Types (tsc)', ['run', 'typecheck']],
  ['Unit tests (vitest)', ['run', 'test']],
  ['Core lint (ruff)', ['run', 'core:lint']],
  ['Core types (mypy)', ['run', 'core:typecheck']],
  ['Core tests (pytest)', ['run', 'core:test']],
  ...(withE2e ? [['End-to-end (playwright + electron)', ['run', 'e2e']]] : []),
];

const results = [];
let failed = false;
for (const [label, args] of steps) {
  if (failed) {
    results.push([label, 'NOT RUN']);
    continue;
  }
  console.log(`\n=== ${label} ===`);
  const started = Date.now();
  // `shell` is needed to launch npm's .cmd shim on Windows; the arguments are fixed.
  const result = spawnSync(npm, args, { cwd: repoRoot, stdio: 'inherit', shell: true });
  const seconds = ((Date.now() - started) / 1000).toFixed(1);
  const passed = result.status === 0;
  results.push([label, passed ? `PASS (${seconds}s)` : 'FAIL']);
  if (!passed) failed = true;
}
if (!withE2e) results.push(['End-to-end (playwright + electron)', 'NOT RUN (pass --e2e)']);

console.log('\nSummary');
for (const [label, status] of results) console.log(`  ${status.padEnd(22)} ${label}`);
process.exit(failed ? 1 : 0);
