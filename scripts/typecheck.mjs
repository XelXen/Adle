#!/usr/bin/env node
/**
 * Type-check every TypeScript project in the workspace.
 * Each project has its own environment (DOM vs Node), so they are checked separately.
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const tsc = path.join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc');

const projects = [
  'tsconfig.json',
  'packages/contracts',
  'packages/event-protocol',
  'packages/design-system',
  'apps/desktop/tsconfig.json',
  'apps/desktop/tsconfig.node.json',
];

let failed = false;
for (const project of projects) {
  process.stdout.write(`tsc ${project} ... `);
  const result = spawnSync(process.execPath, [tsc, '--noEmit', '-p', project], {
    cwd: repoRoot,
    encoding: 'utf8',
  });
  if (result.status === 0) {
    console.log('ok');
  } else {
    failed = true;
    console.log('FAILED');
    console.log((result.stdout + result.stderr).trim());
  }
}
process.exit(failed ? 1 : 0);
