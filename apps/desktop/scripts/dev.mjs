#!/usr/bin/env node
/**
 * Development loop: build in watch mode and run the app, restarting it when
 * any part is rebuilt.
 *
 * Development deliberately uses the same built files and `adle://` protocol as
 * production (no dev server), so the Content Security Policy, origins, and
 * player isolation are identical to what ships. See ADR-003.
 */
import { spawn } from 'node:child_process';

import electronPath from 'electron';

import { build, desktopDir } from './build.mjs';

let child = null;
let restartTimer = null;
let shuttingDown = false;

function start() {
  child = spawn(electronPath, [desktopDir], { stdio: 'inherit' });
  const current = child;
  current.once('exit', (code) => {
    // Closing the window ends the dev session; a restart replaces `child` first.
    if (child === current && !shuttingDown) process.exit(code ?? 0);
  });
}

function scheduleRestart(target) {
  if (!child) return; // still in the initial build
  clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    console.log(`[dev] ${target} rebuilt, restarting Adle`);
    const previous = child;
    child = null;
    previous.once('exit', start);
    previous.kill();
  }, 300);
}

function shutdown() {
  shuttingDown = true;
  child?.kill();
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

await build({ watch: true, onRebuild: scheduleRestart });
console.log('[dev] starting Adle');
start();
