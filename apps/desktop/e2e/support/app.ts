import {
  lstatSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  _electron as electron,
  type ElectronApplication,
  expect,
  type Page,
  test as base,
} from '@playwright/test';

export const desktopDir = path.resolve(import.meta.dirname, '..', '..');
export const repoRoot = path.resolve(desktopDir, '..', '..');

/**
 * Set to run the suite against a packaged build instead of the built files: the path of
 * the app's executable, from `node scripts/package.mjs --for-tests`. Nothing else changes;
 * the same journeys then prove the same things about what a learner would install.
 */
export const packagedExecutable = process.env.ADLE_E2E_EXECUTABLE || null;

/** See the file: what the test tool does to where secrets are kept, undone. */
const KEEP_SECRETS = path.join(import.meta.dirname, 'keep-secrets.cjs');

export interface LaunchedApp {
  app: ElectronApplication;
  page: Page;
  /** Console errors and uncaught exceptions seen in the renderer. */
  problems: string[];
  /**
   * The notifications the app asked the operating system to show, oldest first. None is
   * ever really shown during a test: see `recordNotices`.
   */
  notices: () => Promise<{ title: string; body: string }[]>;
  /**
   * Have the app believe its window does (or does not) have the focus. A notification is
   * only asked for while it does not, and whether a test window has the focus depends on
   * what else is on the screen.
   */
  setFocused: (focused: boolean) => Promise<void>;
  close: () => Promise<void>;
}

export interface LaunchOptions {
  /**
   * Start with this theme, by writing the app's own saved preference before
   * launch. This exercises the real mechanism (main process -> nativeTheme ->
   * prefers-color-scheme) instead of emulating the media query.
   */
  theme?: 'light' | 'dark' | 'pastel' | 'pastel-dark';
  /** The color of a Pastel theme (ADR-074), saved with the theme. */
  pastelHue?: number;
  viewport?: { width: number; height: number };
  /** Skip the first-run welcome so a test can start in the main shell. */
  onboarded?: boolean;
  /** Extra environment for the app, for example the address of the fake AI provider. */
  env?: Record<string, string>;
  /**
   * How many pixels of the display there are for each pixel of the page, whatever the
   * computer's own setting. For a journey that reads the window's own pixels and whose
   * answer depends on how many there are; the others take the display as it is.
   */
  displayScale?: number;
}

/**
 * Keep the window painting even when it opens behind other windows. Without
 * these, Chromium treats a covered test window as occluded and stops producing
 * frames, and every "wait until stable" check in Playwright then hangs. They
 * change scheduling only, not behaviour under test.
 */
const ALWAYS_PAINT_SWITCHES = [
  '--disable-features=CalculateNativeWinOcclusion',
  '--disable-backgrounding-occluded-windows',
  '--disable-renderer-backgrounding',
];

/** Apps still running, per profile, so a failed test can never leave one behind. */
const openApps = new Map<string, Set<ElectronApplication>>();

/**
 * Wait until the app's window is visible before touching it.
 *
 * While the window was created hidden and shown on `ready-to-show`, roughly
 * 1 to 3 in 100 driven launches on Windows never produced a first frame: no
 * animation frame fired, the window never appeared, and every "wait until
 * stable" check in Playwright hung until its timeout. Nothing done from the
 * test side removed it. The window is now created visible
 * (`electron/main/window.ts`, ADR-008), so this returns almost at once; it
 * stays as the guard that would catch the problem coming back.
 */
async function whenShown(app: ElectronApplication): Promise<void> {
  await expect
    .poll(
      () =>
        app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0]?.isVisible() ?? false),
      { message: 'The app did not show its window.', timeout: 15_000, intervals: [25, 50, 100] },
    )
    .toBe(true);
}

/** How long two frames may take, and how often that is asked before a launch is given up. */
const PAINTING_PATIENCE_MS = 5_000;
const PAINTING_ATTEMPTS = 3;
/**
 * How many times the app is started before a window that does not paint is called a
 * failure. On a build machine drawing without a graphics card about one start in fifty
 * shows a window and never draws in it, however long it is given, and the next start is
 * fine (GitHub's Windows machine, three runs on 2026-11-21). That is the machine's, not
 * the app's: a start that does not paint is closed and made again. One that still does
 * not paint the third time fails, with the same clear reason as before.
 */
const LAUNCH_ATTEMPTS = 3;

class NotPaintingError extends Error {
  constructor() {
    super('The app window is visible but is not painting frames.');
  }
}

/**
 * Give the window keyboard focus and confirm it is painting.
 *
 * Focus is requested explicitly because a window opened by a test runner does
 * not always receive it from the operating system, and keyboard tests need it.
 */
async function focusAndConfirmPainting(app: ElectronApplication, page: Page): Promise<void> {
  // Fail here, with a clear reason, rather than thirty seconds into the first click. A
  // window that is painting does so within a moment; one on a build machine, drawn
  // without a graphics card while the machine is busy, was seen to need more than five
  // seconds for its first frames (GitHub's Windows machine, 2026-11-21). So it is asked
  // a few times, and given the focus again each time.
  for (let attempt = 0; attempt < PAINTING_ATTEMPTS; attempt += 1) {
    await app.evaluate(({ BrowserWindow }) => {
      const window = BrowserWindow.getAllWindows()[0];
      window?.focus();
      window?.webContents.focus();
    });
    const painting = await page.evaluate(
      (patience) =>
        new Promise<boolean>((resolve) => {
          const timer = setTimeout(() => resolve(false), patience);
          requestAnimationFrame(() =>
            requestAnimationFrame(() => {
              clearTimeout(timer);
              resolve(true);
            }),
          );
        }),
      PAINTING_PATIENCE_MS,
    );
    if (painting) return;
  }
  throw new NotPaintingError();
}

/**
 * Keep the app from showing real notifications, and remember what it would have shown.
 *
 * The app's own decision (which kind, which words, whether to show one at all) runs as it
 * does for a learner; only the last step, handing it to the operating system, is replaced.
 * A test run must never put notifications on the desk of whoever is running it.
 *
 * Nor does it need a desk that could show one. A build machine has nobody to hand a
 * notification to (on Linux, no notification service in its session), and the app, asked
 * there, rightly shows nothing. Whether the system could show one belongs to the step
 * that is replaced here, so the answer is replaced with it: yes, as on a learner's
 * desktop. What the app does where the answer is no is `shouldNotify`'s, and unit tested.
 */
async function recordNotices(app: ElectronApplication): Promise<void> {
  await app.evaluate(({ Notification }) => {
    const shown: { title: string; body: string }[] = [];
    (globalThis as unknown as { adleTestNotices: typeof shown }).adleTestNotices = shown;
    Notification.isSupported = (): boolean => true;
    Notification.prototype.show = function show(this: Electron.Notification): void {
      shown.push({ title: this.title, body: this.body });
    };
  });
}

/** Start the built app against an isolated profile directory. */
export async function launchApp(
  profileDir: string,
  options: LaunchOptions = {},
): Promise<LaunchedApp> {
  if (options.theme) {
    writeFileSync(
      path.join(profileDir, 'ui-state.json'),
      JSON.stringify({
        theme: options.theme,
        ...(options.pastelHue === undefined ? {} : { pastelHue: options.pastelHue }),
        onboardingCompleted: false,
      }),
    );
  }
  const switches = [
    ...ALWAYS_PAINT_SWITCHES,
    ...(options.displayScale ? [`--force-device-scale-factor=${options.displayScale}`] : []),
  ];
  const start = async (): Promise<{
    app: ElectronApplication;
    page: Page;
    problems: string[];
  }> => {
    const app = await electron.launch({
      ...(packagedExecutable
        ? { executablePath: packagedExecutable, args: switches }
        : // Run from its folder, the app is started by the test tool's loader, which tells
          // it to keep secrets as plain text. `keep-secrets.cjs` is loaded after that
          // loader and takes the switch away again; it says why.
          { args: ['-r', KEEP_SECRETS, desktopDir, ...switches] }),
      env: { ...process.env, ...options.env, ADLE_USER_DATA_DIR: profileDir },
      // Playwright forces a light colour scheme by default, which would mask the
      // app's own theme handling. `null` leaves the media query to the app.
      colorScheme: null,
    });
    const running = openApps.get(profileDir) ?? new Set<ElectronApplication>();
    openApps.set(profileDir, running);
    running.add(app);
    app.on('close', () => running.delete(app));
    await recordNotices(app);
    const page = await app.firstWindow();
    const problems: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') problems.push(`console: ${message.text()}`);
    });
    page.on('pageerror', (error) => problems.push(`exception: ${error.message}`));

    await whenShown(app);
    await page.setViewportSize(options.viewport ?? { width: 1280, height: 832 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByRole('heading', { level: 1 }).first().waitFor();
    try {
      await focusAndConfirmPainting(app, page);
    } catch (error) {
      // Nothing has been done in this window yet: closing it loses nothing.
      await app.close().catch(() => undefined);
      throw error;
    }
    return { app, page, problems };
  };
  let started: Awaited<ReturnType<typeof start>> | null = null;
  for (let attempt = 1; started === null; attempt += 1) {
    try {
      started = await start();
    } catch (error) {
      if (!(error instanceof NotPaintingError) || attempt >= LAUNCH_ATTEMPTS) throw error;
    }
  }
  const { app, page, problems } = started;

  if (options.onboarded) {
    const start = page.getByRole('button', { name: 'Get started' });
    if (await start.isVisible()) {
      await start.click();
      await page.getByRole('heading', { name: 'Library', level: 1 }).waitFor();
    }
  }

  return {
    app,
    page,
    problems,
    notices: () =>
      app.evaluate(
        () =>
          (globalThis as unknown as { adleTestNotices: { title: string; body: string }[] })
            .adleTestNotices,
      ),
    setFocused: (focused) =>
      app.evaluate(({ BrowserWindow }, value) => {
        BrowserWindow.prototype.isFocused = () => value;
      }, focused),
    close: () => app.close(),
  };
}

/** Wait until the managed Python core reports ready. */
export async function waitForCore(page: Page): Promise<void> {
  await expect
    .poll(async () => (await page.evaluate(() => window.adle!.core.status())).state, {
      timeout: 30_000,
    })
    .toBe('ready');
}

/**
 * The page itself knows the core is ready. It draws nothing to say so while all is well
 * (see `CoreStatusIndicator`), so this reads what it wrote on the document.
 */
export async function expectReadyOnPage(page: Page): Promise<void> {
  await expect(page.locator('html[data-core="ready"]')).toHaveCount(1, { timeout: 30_000 });
}

/**
 * Everything under `directory` that is not a folder, recursively. A link is listed as
 * itself and never followed: on Linux a profile holds links that lead nowhere (Chromium
 * writes who holds the profile into the name a link points at).
 */
export function listFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    return entry.isDirectory() ? listFiles(full) : [full];
  });
}

/**
 * Files under `directory` whose bytes contain `needle` (as UTF-8 or UTF-16LE). For a
 * link, what is searched is where it says it points, which is all it holds.
 */
export function filesContaining(directory: string, needle: string): string[] {
  const patterns = [Buffer.from(needle, 'utf8'), Buffer.from(needle, 'utf16le')];
  return listFiles(directory).filter((file) => {
    let content: Buffer;
    try {
      const entry = lstatSync(file);
      if (entry.isSymbolicLink()) {
        content = Buffer.from(readlinkSync(file), 'utf8');
      } else {
        if (entry.size > 64 * 1024 * 1024) return false;
        content = readFileSync(file);
      }
    } catch {
      // Locked by the running app (Chromium's own lock files), or gone since it was listed.
      return false;
    }
    return patterns.some((pattern) => content.includes(pattern));
  });
}

interface Fixtures {
  /** A fresh, empty profile directory, removed after the test. */
  profileDir: string;
  /** The app, launched past the welcome screen, closed after the test. */
  adle: LaunchedApp;
}

export const test = base.extend<Fixtures>({
  // eslint-disable-next-line no-empty-pattern -- Playwright requires the destructured first argument
  profileDir: async ({}, use) => {
    const directory = mkdtempSync(path.join(os.tmpdir(), 'adle-e2e-'));
    await use(directory);
    // Close anything a failed test left running before touching its files.
    for (const app of openApps.get(directory) ?? []) await app.close().catch(() => undefined);
    openApps.delete(directory);
    try {
      rmSync(directory, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 });
    } catch {
      // Windows can hold a handle for a moment after exit. A leftover temp profile
      // contains only test data and must not fail an otherwise passing test.
    }
  },
  adle: async ({ profileDir }, use) => {
    // A fixed theme keeps screenshots and colour assertions the same on every machine.
    const launched = await launchApp(profileDir, { onboarded: true, theme: 'light' });
    await use(launched);
    await launched.close();
  },
});

export { expect };
