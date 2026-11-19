import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

/**
 * Unit and component tests for all TypeScript in the workspace.
 *
 * Two projects, because the code runs in two worlds:
 *   - `node`: Electron main process, build scripts, pure logic.
 *   - `dom`:  React components and browser-side modules (jsdom).
 *
 * End-to-end tests live in apps/desktop/e2e and run with Playwright instead.
 */
export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: 'node',
          environment: 'node',
          include: [
            'apps/desktop/electron/**/*.test.ts',
            'packages/event-protocol/**/*.test.ts',
            'packages/contracts/**/*.test.ts',
            'scripts/**/*.test.ts',
          ],
        },
      },
      {
        plugins: [react()],
        test: {
          name: 'dom',
          environment: 'jsdom',
          setupFiles: ['./vitest.setup.ts'],
          include: [
            'packages/design-system/**/*.test.{ts,tsx}',
            'apps/desktop/renderer/**/*.test.{ts,tsx}',
            'apps/desktop/player/**/*.test.{ts,tsx}',
          ],
          css: { modules: { classNameStrategy: 'non-scoped' } },
        },
      },
    ],
  },
});
