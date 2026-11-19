import path from 'node:path';

import { defineConfig } from 'vite';

/** The isolated scene player: bundles the Wanim runtime and the frame-side protocol code. */
export default defineConfig({
  root: import.meta.dirname,
  base: './',
  publicDir: false,
  logLevel: 'warn',
  build: {
    outDir: path.resolve(import.meta.dirname, '../../dist/player'),
    emptyOutDir: true,
    target: 'chrome156',
    sourcemap: false,
    modulePreload: { polyfill: false },
    // Wanim (1.5 MB) and its MathJax chunk (2.1 MB) are large by nature; they load from disk.
    chunkSizeWarningLimit: 4096,
  },
});
