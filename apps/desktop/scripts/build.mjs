#!/usr/bin/env node
/**
 * Build the desktop app into apps/desktop/dist:
 *
 *   dist/electron/main.cjs      Electron main process (bundled)
 *   dist/electron/preload.cjs   sandboxed preload bridge (bundled)
 *   dist/renderer/              React renderer, served as adle://app
 *   dist/player/                isolated scene player, served as adle://player
 *
 * `node scripts/build.mjs --watch` rebuilds on change (used by `npm run dev`).
 */
import { cpSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { build as esbuild, context as esbuildContext } from 'esbuild';
import { build as viteBuild } from 'vite';

const require = createRequire(import.meta.url);
export const desktopDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distDir = path.join(desktopDir, 'dist');

/** Fonts handed to Wanim for `Text` mobjects (WOFF1: readable by opentype.js). */
const SCENE_FONT_FILES = [
  'inter-latin-400-normal.woff',
  'inter-latin-ext-400-normal.woff',
  'inter-greek-400-normal.woff',
];

function electronOptions() {
  return {
    absWorkingDir: desktopDir,
    entryPoints: {
      main: 'electron/main/index.ts',
      preload: 'electron/preload/index.ts',
    },
    outdir: path.join(distDir, 'electron'),
    outExtension: { '.js': '.cjs' },
    bundle: true,
    platform: 'node',
    format: 'cjs',
    target: 'node24',
    external: ['electron'],
    sourcemap: true,
    legalComments: 'none',
    logLevel: 'warning',
  };
}

/** Copy the runtime files the player loads directly rather than through the bundler. */
function copyPlayerVendorFiles() {
  const playerDir = path.join(distDir, 'player');
  const wanimDir = path.dirname(require.resolve('@wanimjs/wanim/package.json'));
  mkdirSync(path.join(playerDir, 'vendor'), { recursive: true });
  cpSync(
    path.join(wanimDir, 'browser', 'rapydscript.js'),
    path.join(playerDir, 'vendor', 'rapydscript.js'),
  );

  const fontsDir = path.join(
    path.dirname(require.resolve('@fontsource/inter/package.json')),
    'files',
  );
  mkdirSync(path.join(playerDir, 'fonts'), { recursive: true });
  for (const file of SCENE_FONT_FILES) {
    cpSync(path.join(fontsDir, file), path.join(playerDir, 'fonts', file));
  }
}

function vendorCopyPlugin() {
  return { name: 'adle-player-vendor', closeBundle: copyPlayerVendorFiles };
}

export async function build({ watch = false, onRebuild = () => {} } = {}) {
  const notify = (target) => ({
    name: `adle-notify-${target}`,
    closeBundle() {
      onRebuild(target);
    },
  });

  if (watch) {
    const context = await esbuildContext({
      ...electronOptions(),
      plugins: [
        {
          name: 'adle-notify-electron',
          setup(build) {
            build.onEnd((result) => {
              if (result.errors.length === 0) onRebuild('electron');
            });
          },
        },
      ],
    });
    await context.watch();
  } else {
    await esbuild(electronOptions());
  }

  const shared = watch ? { build: { watch: {} } } : {};
  await viteBuild({
    configFile: path.join(desktopDir, 'renderer', 'vite.config.ts'),
    ...shared,
    plugins: [notify('renderer')],
  });
  await viteBuild({
    configFile: path.join(desktopDir, 'player', 'frame', 'vite.config.ts'),
    ...shared,
    plugins: [vendorCopyPlugin(), notify('player')],
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const started = Date.now();
  await build({ watch: process.argv.includes('--watch') });
  if (!process.argv.includes('--watch')) {
    console.log(`Built desktop app in ${((Date.now() - started) / 1000).toFixed(1)}s`);
  }
}
