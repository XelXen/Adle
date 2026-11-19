/**
 * The process and origin boundaries described in SECURITY.md, checked from
 * inside the running app rather than assumed from configuration.
 */
import { expect, test } from './support/app';
import { fixtureScene, mountRawPlayer } from './support/player';

test.describe('renderer boundary', () => {
  test('the renderer has no Node access and only the documented bridge', async ({ adle }) => {
    const surface = await adle.page.evaluate(() => {
      const globals = globalThis as Record<string, unknown>;
      const bridge = window.adle as unknown as Record<string, Record<string, unknown>>;
      return {
        require: typeof globals.require,
        process: typeof globals.process,
        module: typeof globals.module,
        buffer: typeof globals.Buffer,
        ipcRenderer: typeof globals.ipcRenderer,
        bridge: Object.fromEntries(
          Object.entries(bridge).map(([group, api]) => [group, Object.keys(api).sort()]),
        ),
      };
    });
    expect(surface).toEqual({
      require: 'undefined',
      process: 'undefined',
      module: 'undefined',
      buffer: 'undefined',
      ipcRenderer: 'undefined',
      bridge: {
        app: ['info', 'openExternal', 'updateUiState'],
        core: ['invoke', 'onStatus', 'restart', 'status'],
        provider: ['clearApiKey', 'keyState', 'setApiKey'],
        sources: ['importDropped', 'importWithPicker'],
      },
    });
  });

  test('the renderer cannot reach the network, open windows, or leave the app', async ({
    adle,
  }) => {
    const { page, app } = adle;
    const outcomes = await page.evaluate(async () => {
      const attempt = async (run: () => Promise<unknown>): Promise<string> => {
        try {
          await run();
          return 'reached';
        } catch {
          return 'blocked';
        }
      };
      return {
        https: await attempt(() => fetch('https://example.com/')),
        loopback: await attempt(() => fetch('http://127.0.0.1:1/')),
        popup: window.open('https://example.com/') === null ? 'blocked' : 'opened',
      };
    });
    expect(outcomes).toEqual({ https: 'blocked', loopback: 'blocked', popup: 'blocked' });

    await page.evaluate(() => {
      window.location.href = 'https://example.com/';
    });
    await page.waitForTimeout(500);
    expect(page.url()).toBe('adle://app/index.html');
    expect(app.windows()).toHaveLength(1);
  });

  test('inline script is refused by the content security policy', async ({ adle }) => {
    const ran = await adle.page.evaluate(() => {
      const script = document.createElement('script');
      script.textContent = 'window.__inlineRan = true;';
      document.head.appendChild(script);
      return (window as unknown as { __inlineRan?: boolean }).__inlineRan === true;
    });
    expect(ran).toBe(false);
  });

  test('internal and unknown core operations are refused by the main process', async ({ adle }) => {
    const results = await adle.page.evaluate(async () => ({
      internal: await window.adle!.core.invoke('provider.set_credential', {
        body: { api_key: 'sk-should-never-be-accepted' },
      }),
      unknown: await window.adle!.core.invoke('system.shutdown'),
      // Naming a file path is reserved for the main process (file dialog or a real drop).
      importPaths: await window.adle!.core.invoke('sources.import_paths', {
        path: { course_id: 'crs_00000000000000000000' },
        body: { paths: ['C:/Windows/win.ini', '/etc/passwd'] },
      }),
      forgedDrop: await window.adle!.sources.importDropped('crs_00000000000000000000', [
        new File(['not on disk'], 'C:/Windows/win.ini'),
      ]),
      badCourse: await window.adle!.sources.importWithPicker('../../etc'),
      prototype: await window.adle!.core.invoke('constructor'),
      external: await window.adle!.app.openExternal('https://example.com/' as never).then(
        () => 'opened',
        () => 'refused',
      ),
    }));
    expect(results.internal).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.unknown).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.importPaths).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    // A File made by page script has no path behind it, so there is nothing to import.
    expect(results.forgedDrop).toMatchObject({ ok: false, error: { code: 'no_files' } });
    expect(results.badCourse).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.prototype).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.external).toBe('refused');
  });
});

test.describe('generated scene boundary', () => {
  test('a hostile scene cannot reach the bridge, the app, or the network', async ({ adle }) => {
    const { page } = adle;
    const player = await mountRawPlayer(page, 'e2ehostile');
    await player.waitFor(`m.type === 'ready'`);
    await player.load(fixtureScene('hostile_probe.py'));
    expect(await player.waitFor(`m.type === 'finished' || m.type === 'error'`)).toMatchObject({
      type: 'finished',
    });

    const events = (await player.messages()).filter((message) => message.type === 'scene-event');
    // Only the allowlisted event got through; the unknown name and the object payload were dropped.
    expect(events).toHaveLength(1);
    const report = Object.fromEntries(
      String(events[0]!.value)
        .split(';')
        .map((pair) => pair.split('=') as [string, string]),
    );
    expect(report).toMatchObject({
      own_bridge: 'undefined', // no preload bridge inside the player
      parent_bridge: 'ERR', // cross-origin access to the app is refused
      top_doc: 'ERR',
      require: 'ERR', // no Node
      popup: 'None', // sandbox: no popups
      net_remote: 'blocked',
      net_app: 'blocked', // cannot read the renderer's files either
    });
    expect(page.url()).toBe('adle://app/index.html');
    expect(adle.app.windows()).toHaveLength(1);
  });

  test('raw JavaScript in a scene still runs only inside the sandbox', async ({ adle }) => {
    // The static policy rejects this file before it is ever stored (it is not
    // valid Python). This test shows that even if it ran, it would be contained.
    const player = await mountRawPlayer(adle.page, 'e2everbatim');
    await player.waitFor(`m.type === 'ready'`);
    await player.load(fixtureScene('verbatim_js.py'));
    await player.waitFor(`m.type === 'finished' || m.type === 'error'`);
    const origins = new Set((await player.messages()).map((message) => message.origin));
    expect([...origins]).toEqual([player.origin]);
    expect(
      await adle.page.evaluate(() => typeof (window as unknown as { adle?: unknown }).adle),
    ).toBe('object');
  });

  test('the player frame cannot use the bridge even if it asks the main process directly', async ({
    adle,
  }) => {
    // The frame has no preload, so there is no ipcRenderer to try with. The sender
    // check is covered by unit tests; here we confirm the frame's globals.
    const player = await mountRawPlayer(adle.page, 'e2enobridge');
    await player.waitFor(`m.type === 'ready'`);
    const frame = adle.page.frames().find((candidate) => candidate.url().startsWith(player.origin));
    expect(frame).toBeDefined();
    const globals = await frame!.evaluate(() => ({
      adle: typeof (window as unknown as { adle?: unknown }).adle,
      require: typeof (globalThis as Record<string, unknown>).require,
    }));
    expect(globals).toEqual({ adle: 'undefined', require: 'undefined' });
  });
});
