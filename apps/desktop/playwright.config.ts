import { defineConfig } from '@playwright/test';

/**
 * End-to-end tests drive the real, built Electron app (main process, preload,
 * renderer, isolated player, and the Python core) through Playwright.
 *
 * `npm run e2e` builds the app first. Each test gets a fresh profile directory,
 * so tests never see each other's data or a learner's real data.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  outputDir: './test-results',
  // One app instance at a time keeps core startup and focus behaviour deterministic.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  // One retry absorbs operating-system focus and scheduling hiccups in a real
  // desktop window. A test that passes only on retry is reported as "flaky":
  // treat that as a defect to investigate, not as a pass to ignore.
  retries: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list']],
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
