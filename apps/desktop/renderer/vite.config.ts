import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/** The trusted React renderer, served to Electron as adle://app. */
export default defineConfig({
  root: import.meta.dirname,
  base: './',
  publicDir: false,
  logLevel: 'warn',
  plugins: [react()],
  build: {
    outDir: path.resolve(import.meta.dirname, '../dist/renderer'),
    emptyOutDir: true,
    target: 'chrome156',
    sourcemap: true,
    modulePreload: { polyfill: false },
    // Every asset is a file served from adle://app. Vite would otherwise inline small ones
    // (some KaTeX fonts) as data: URIs, which the Content Security Policy rightly refuses.
    assetsInlineLimit: 0,
  },
});
