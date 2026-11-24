#!/usr/bin/env node
/**
 * Run the quality gates, in order, and report each one's outcome.
 *
 *   node scripts/check.mjs              # static checks, and the tests what changed can affect
 *   node scripts/check.mjs --e2e        # also the end-to-end journeys what changed can affect
 *   node scripts/check.mjs --all        # every test, whatever changed (add --e2e for journeys)
 *
 * What changed is everything not yet on origin/main: commits not pushed, and files changed
 * or new (ADR-059). The static checks always run whole: they are quick, and they are about
 * the repository as a whole. The tests run as far as a change can reach: the unit tests
 * related to the files changed (vitest), the core's tests whose code changed since they
 * last ran (pytest-testmon) and its integration tests, and the journeys
 * `scripts/affected.mjs` picks. On GitHub (`CI`), and with --all, everything runs.
 *
 * This is what a contributor (or agent) runs before committing. A step that did not run is
 * reported as NOT RUN, never as passed, and a step that ran in part says so.
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { ALL, changedFiles, coreTestsFor, journeysFor } from './affected.mjs';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const withE2e = process.argv.includes('--e2e');
const everything = process.argv.includes('--all') || process.env.CI === 'true';
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const uv = 'uv';

const change = everything ? null : changedFiles(repoRoot);
const whole = change === null;

/** A step: its label, and either the commands it runs or why it does not run. */
function unitTests() {
  if (whole) return { label: 'Unit tests (vitest)', commands: [[npm, ['run', 'test']]] };
  return {
    label: 'Unit tests (vitest), related to what changed',
    commands: [[npx, ['vitest', 'run', '--changed', change.base, '--passWithNoTests']]],
  };
}

function coreTests() {
  const label = 'Core tests (pytest)';
  const touched = whole ? 'all' : coreTestsFor(change.files);
  if (touched === 'none') return { label, skipped: 'NOT RUN (nothing they cover changed)' };
  if (touched === 'all') return { label, commands: [[npm, ['run', 'core:test']]] };
  const pytest = (args) => [uv, ['run', '--directory', 'services/core', 'pytest', ...args]];
  return {
    label: `${label}, those whose code changed, and integration`,
    commands: [pytest(['--testmon', '--ignore=tests/integration']), pytest(['tests/integration'])],
  };
}

function journeys() {
  const label = 'End-to-end (playwright + electron)';
  if (!withE2e) return { label, skipped: 'NOT RUN (pass --e2e)' };
  const picked = whole ? ALL : journeysFor(change.files);
  if (picked === ALL) return { label, commands: [[npm, ['run', 'e2e']]] };
  if (picked.length === 0) return { label, skipped: 'NOT RUN (nothing they cover changed)' };
  return {
    label: `${label}: ${picked.join(', ')}`,
    commands: [[npm, ['run', 'e2e', '--', ...picked]]],
  };
}

const quick = (label, script) => ({ label, commands: [[npm, ['run', script]]] });
const steps = [
  quick('Contracts up to date', 'contracts:check'),
  quick('Scene name allowlist up to date', 'wanim-names:check'),
  quick('Packaged scene guide up to date', 'scene-guide:check'),
  quick('No credential or learner data in what would be committed', 'secrets:check'),
  quick('Third-party licences listed and accepted', 'licenses:check'),
  quick('Format (prettier)', 'format:check'),
  quick('Lint (eslint)', 'lint'),
  quick('Types (tsc)', 'typecheck'),
  unitTests(),
  quick('Core lint (ruff)', 'core:lint'),
  quick('Core types (mypy)', 'core:typecheck'),
  coreTests(),
  journeys(),
];

if (!whole) {
  console.log(
    `Checking what is not on origin/main yet (${change.files.length} files). ` +
      'Pass --all to check everything.',
  );
}

const results = [];
let failed = false;
for (const step of steps) {
  if (step.skipped) {
    results.push([step.label, step.skipped]);
    continue;
  }
  if (failed) {
    results.push([step.label, 'NOT RUN']);
    continue;
  }
  console.log(`\n=== ${step.label} ===`);
  const started = Date.now();
  let passed = true;
  for (const [command, args] of step.commands) {
    // `shell` is needed to launch npm's .cmd shim on Windows; the arguments are fixed.
    const result = spawnSync(command, args, { cwd: repoRoot, stdio: 'inherit', shell: true });
    if (result.status !== 0) {
      passed = false;
      break;
    }
  }
  const seconds = ((Date.now() - started) / 1000).toFixed(1);
  results.push([step.label, passed ? `PASS (${seconds}s)` : 'FAIL']);
  if (!passed) failed = true;
}

console.log('\nSummary');
for (const [label, status] of results) console.log(`  ${status.padEnd(22)} ${label}`);
process.exit(failed ? 1 : 0);
