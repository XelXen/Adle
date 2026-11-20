#!/usr/bin/env node
/**
 * Measure how long the things a learner waits for actually take.
 *
 *   node scripts/measure.mjs                the built files, as in development
 *   node scripts/measure.mjs --packaged     the packaged build made for tests
 *   --runs 7                                how many fresh starts (default 5)
 *
 * Each run starts the app on an empty profile and times, from the outside, what a learner
 * would see: the window, the local service, the sample course, a lesson, and a live scene.
 * It prints the median and the slowest of each, and writes nothing. The numbers in
 * docs/engineering/PERFORMANCE.md were produced by this script; run it again rather than
 * trust them after a change.
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { findExecutable } from './smoke-packaged.mjs';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const desktopDir = path.join(repoRoot, 'apps', 'desktop');
const require = createRequire(path.join(desktopDir, 'package.json'));
const { _electron: electron } = require('@playwright/test');

const args = process.argv.slice(2);
const packaged = args.includes('--packaged');
const runs = Number(args[args.indexOf('--runs') + 1]) || 5;

const executable = packaged ? findExecutable(path.join(desktopDir, 'out', 'test')) : null;
if (packaged && !executable) {
  console.error('No packaged test build. Run "node scripts/package.mjs --for-tests" first.');
  process.exit(1);
}

const SWITCHES = [
  '--disable-features=CalculateNativeWinOcclusion',
  '--disable-backgrounding-occluded-windows',
  '--disable-renderer-backgrounding',
];

async function once() {
  const profile = mkdtempSync(path.join(os.tmpdir(), 'adle-measure-'));
  const marks = {};
  const started = performance.now();
  const since = () => Math.round(performance.now() - started);
  const app = await electron.launch({
    ...(executable
      ? { executablePath: executable, args: SWITCHES }
      : { args: [desktopDir, ...SWITCHES] }),
    env: { ...process.env, ADLE_USER_DATA_DIR: profile },
    colorScheme: null,
  });
  try {
    const page = await app.firstWindow();
    await page.getByRole('heading', { level: 1 }).first().waitFor();
    marks['Window with its first screen'] = since();

    await page.getByRole('button', { name: 'Get started' }).click();
    await page.getByRole('heading', { name: 'Library', level: 1 }).waitFor();
    // Asked from this side, one answer at a time: the state itself is looked at, so a
    // wait can never be satisfied by anything but "ready".
    const deadline = performance.now() + 120_000;
    for (;;) {
      const status = await page.evaluate(() => globalThis.adle.core.status());
      if (status.state === 'ready') break;
      if (status.state === 'failed') throw new Error(`The core failed: ${status.message}`);
      if (performance.now() > deadline) throw new Error('The core did not become ready.');
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
    marks['Local service ready (from launch)'] = since();

    let from = performance.now();
    await page.getByRole('button', { name: 'Try the sample course' }).click();
    await page
      .getByRole('heading', { name: 'Introduction to neural networks', level: 1 })
      .waitFor();
    await page.getByText('Suggested next step').waitFor();
    marks['Sample course added and its first suggestion shown'] = Math.round(
      performance.now() - from,
    );

    from = performance.now();
    await page.getByRole('button', { name: 'Start lesson' }).first().click();
    await page.getByText(/^Part 1 of \d+/).waitFor();
    marks['Lesson opened'] = Math.round(performance.now() - from);

    // A live scene, from asking for it to its first frame: the frame is created, the
    // runtime loads, the scene is compiled, and something is drawn.
    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'About & diagnostics' }).click();
    from = performance.now();
    await page.getByRole('button', { name: 'Run check' }).click();
    await page.getByText('Rendering works').waitFor({ timeout: 60_000 });
    marks['Live scene: from request to first frame'] = Math.round(performance.now() - from);
  } finally {
    await app.close();
    rmSync(profile, { recursive: true, force: true, maxRetries: 40, retryDelay: 250 });
  }
  return marks;
}

const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
};

const all = [];
for (let run = 1; run <= runs; run += 1) {
  all.push(await once());
  process.stdout.write(`run ${run} of ${runs} done\n`);
}

console.log(`\n${packaged ? 'Packaged build' : 'Built files (development)'}, ${runs} fresh starts`);
console.log('| What the learner waits for | Median | Slowest |');
console.log('|---|---|---|');
for (const name of Object.keys(all[0])) {
  const values = all.map((marks) => marks[name]);
  const seconds = (ms) => `${(ms / 1000).toFixed(2)} s`;
  console.log(`| ${name} | ${seconds(median(values))} | ${seconds(Math.max(...values))} |`);
}
