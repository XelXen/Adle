/**
 * The process and origin boundaries described in SECURITY.md, checked from
 * inside the running app rather than assumed from configuration.
 */
import dgram from 'node:dgram';
import { existsSync, readdirSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';

import { expect, test, waitForCore } from './support/app';
import { fixtureScene, mountRawPlayer } from './support/player';

/** Somewhere on this computer to see whether anything arrives, by UDP or by TCP. */
async function listeners(): Promise<{
  udpPort: number;
  tcpPort: number;
  arrived: () => string[];
  close: () => void;
}> {
  const seen: string[] = [];
  const udp = dgram.createSocket('udp4');
  udp.on('message', (message) => seen.push(`udp:${message.length}`));
  await new Promise<void>((resolve) => udp.bind(0, '127.0.0.1', resolve));
  const tcp = net.createServer((socket) => {
    seen.push('tcp');
    socket.on('error', () => undefined);
  });
  await new Promise<void>((resolve) => tcp.listen(0, '127.0.0.1', resolve));
  return {
    udpPort: udp.address().port,
    tcpPort: (tcp.address() as net.AddressInfo).port,
    arrived: () => [...seen],
    close: () => {
      udp.close();
      tcp.close();
    },
  };
}

/**
 * Runs in the page or in a player frame: reach out in the ways that are not requests, so
 * that neither the request filter nor `connect-src` is what stops them. A peer connection
 * sends packets of its own to the servers it is given; a hint in the document opens a
 * connection ahead of time.
 */
async function reachOutWithoutARequest(ports: {
  udpPort: number;
  tcpPort: number;
}): Promise<{ candidates: string[]; failed: string | null }> {
  const candidates: string[] = [];
  let failed: string | null = null;
  try {
    const peer = new RTCPeerConnection({
      iceServers: [
        { urls: `stun:127.0.0.1:${ports.udpPort}` },
        {
          urls: `turn:127.0.0.1:${ports.tcpPort}?transport=tcp`,
          username: 'what-the-page-knows',
          credential: 'x',
        },
      ],
    });
    peer.onicecandidate = (event) => {
      if (event.candidate) candidates.push(event.candidate.candidate);
    };
    peer.createDataChannel('out');
    await peer.setLocalDescription(await peer.createOffer());
    await new Promise((resolve) => setTimeout(resolve, 2500));
    peer.close();
  } catch (error) {
    failed = String(error);
  }
  for (const rel of ['preconnect', 'dns-prefetch']) {
    const link = document.createElement('link');
    link.rel = rel;
    link.href = `http://127.0.0.1:${ports.tcpPort}`;
    document.head.appendChild(link);
  }
  await new Promise((resolve) => setTimeout(resolve, 1000));
  return { candidates, failed };
}

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
        app: ['info', 'notify', 'openExternal', 'showLogs', 'updateUiState'],
        core: ['invoke', 'onStatus', 'restart', 'status'],
        courses: ['bringIn', 'chooseFile', 'saveFile'],
        data: ['eraseAll', 'restoreCopy', 'saveCopy', 'showSafetyCopies'],
        provider: ['clearApiKey', 'keyState', 'select', 'setApiKey'],
        settings: ['bringIn', 'chooseFile', 'saveFile'],
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

  test('the renderer cannot reach the network by a road that is not a request', async ({
    adle,
  }) => {
    const there = await listeners();
    try {
      const found = await adle.page.evaluate(reachOutWithoutARequest, {
        udpPort: there.udpPort,
        tcpPort: there.tcpPort,
      });
      // No address was even gathered for a peer connection, and nothing left the page.
      expect(found.candidates).toEqual([]);
      expect(there.arrived()).toEqual([]);
    } finally {
      there.close();
    }
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
      // Nor is something that only looks like a list of files, with methods of its own
      // that hand back whatever paths the page likes.
      forgedList: await window.adle!.sources.importDropped('crs_00000000000000000000', {
        length: 1,
        0: 'C:/Windows/win.ini',
        map: () => ['C:/Windows/win.ini'],
        filter: () => ['C:/Windows/win.ini'],
      } as never),
      forgedPaths: await window.adle!.sources.importDropped('crs_00000000000000000000', [
        'C:/Windows/win.ini',
        '\\\\elsewhere\\share\\notes.txt',
      ] as never),
      badCourse: await window.adle!.sources.importWithPicker('../../etc'),
      prototype: await window.adle!.core.invoke('constructor'),
      external: await window.adle!.app.openExternal('https://example.com/' as never).then(
        () => 'opened',
        () => 'refused',
      ),
      // Writing a copy of the data to a named file is for the main process alone.
      saveCopy: await window.adle!.core.invoke('data.save_copy', {
        body: { path: 'C:/Users/Public/everything.adle' },
      }),
    }));
    expect(results.internal).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.unknown).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.importPaths).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    // A File made by page script has no path behind it, so there is nothing to import.
    expect(results.forgedDrop).toMatchObject({ ok: false, error: { code: 'no_files' } });
    expect(results.forgedList).toMatchObject({ ok: false, error: { code: 'no_files' } });
    expect(results.forgedPaths).toMatchObject({ ok: false, error: { code: 'no_files' } });
    expect(results.badCourse).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.prototype).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
    expect(results.external).toBe('refused');
    expect(results.saveCopy).toMatchObject({ ok: false, error: { code: 'invalid_request' } });
  });

  test('About says whose Adle is and under what license, and opens only the two pages it names', async ({
    adle,
  }) => {
    const { app, page } = adle;
    // Nothing is really opened: what the main process would have handed to the browser of
    // the computer is written down instead.
    await app.evaluate(({ shell }) => {
      const opened: string[] = [];
      (globalThis as unknown as { __opened: string[] }).__opened = opened;
      shell.openExternal = (url: string) => {
        opened.push(url);
        return Promise.resolve();
      };
    });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'About' }).click();

    // What the GNU GPL asks an app to tell whoever uses it (ADR-033).
    await expect(
      page.getByText('Adle is free software under the GNU General Public License, version 3.'),
    ).toBeVisible();
    await expect(page.getByText(/It comes with no warranty\./)).toBeVisible();
    await page.getByRole('button', { name: 'Source code' }).click();
    await page.getByRole('button', { name: 'Read the license' }).click();
    await expect
      .poll(() => app.evaluate(() => (globalThis as unknown as { __opened: string[] }).__opened))
      .toEqual(['https://github.com/XelXen/Adle', 'https://www.gnu.org/licenses/gpl-3.0.html']);
    expect(adle.problems).toEqual([]);
  });

  test('the page cannot say where a copy goes, which file is restored, or that it is sure', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    const target = path.join(profileDir, 'chosen-by-the-page.adle');
    // The learner backs out of every question the operating system asks.
    await app.evaluate(({ dialog }) => {
      const asked: string[] = [];
      (globalThis as Record<string, unknown>).adleAskedKinds = asked;
      dialog.showSaveDialog = () => {
        asked.push('save');
        return Promise.resolve({ canceled: true, filePath: '' });
      };
      dialog.showOpenDialog = () => {
        asked.push('open');
        return Promise.resolve({ canceled: true, filePath: '', filePaths: [] });
      };
      dialog.showMessageBox = () => {
        asked.push('confirm');
        return Promise.resolve({ response: 0, checkboxChecked: false });
      };
    });

    // Page script passes everything it can think of. None of it is looked at.
    const results = await page.evaluate(async (target) => {
      type Loose = Record<string, (...args: unknown[]) => Promise<unknown>>;
      const data = window.adle!.data as unknown as Loose;
      return {
        save: await data.saveCopy!(target, { path: target, filePath: target }),
        restore: await data.restoreCopy!(target, { restoreFrom: target }),
        erase: await data.eraseAll!(true, { confirmed: true, response: 1 }),
      };
    }, target);

    // Each was asked of the learner, who said no; so nothing happened.
    expect(results).toEqual({
      save: { ok: true, data: null },
      restore: { ok: true, data: null },
      erase: { ok: true, data: null },
    });
    const asked = await app.evaluate(
      () => (globalThis as Record<string, unknown>).adleAskedKinds as string[],
    );
    expect(asked).toEqual(['save', 'open', 'confirm']);
    expect(existsSync(target)).toBe(false);
    // The core was never stopped: nothing was restored and nothing was deleted.
    expect(await page.evaluate(() => window.adle!.core.status())).toMatchObject({
      state: 'ready',
    });
  });

  test('the page cannot say where a course is saved, or which file one is brought in from', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    const target = path.join(profileDir, 'chosen-by-the-page.zip');
    // The learner backs out of every question the operating system asks.
    await app.evaluate(({ dialog }) => {
      const asked: string[] = [];
      (globalThis as Record<string, unknown>).adleAskedKinds = asked;
      dialog.showSaveDialog = () => {
        asked.push('save');
        return Promise.resolve({ canceled: true, filePath: '' });
      };
      dialog.showOpenDialog = () => {
        asked.push('open');
        return Promise.resolve({ canceled: true, filePaths: [] });
      };
    });
    const course = await page.evaluate(async () => {
      const made = await window.adle!.core.invoke('courses.install_sample');
      return (made as { data: { id: string } }).data.id;
    });
    const holds = { lessons: true, materials: true, progress: true, notes: true };

    const results = await page.evaluate(
      async ([id, where, all]) => {
        type Loose = Record<string, (...args: unknown[]) => Promise<unknown>>;
        const courses = window.adle!.courses as unknown as Loose;
        const invoke = window.adle!.core.invoke as unknown as (
          operation: string,
          params?: unknown,
        ) => Promise<unknown>;
        return {
          // A place to save, named every way the page can think of.
          withPath: await courses.saveFile!(id, { kind: 'template', holds: all, path: where }),
          extra: await courses.saveFile!(id, { kind: 'template', holds: all }, where, {
            filePath: where,
          }),
          notACourse: await courses.saveFile!('../../etc', { kind: 'template', holds: all }),
          notAKind: await courses.saveFile!(id, { kind: 'everything', holds: all }),
          // A file to open, the same.
          choose: await courses.chooseFile!(where, { filePaths: [where] }),
          pathAsToken: await courses.bringIn!(where, all),
          forgedToken: await courses.bringIn!('0'.repeat(32), all),
          looseHolds: await courses.bringIn!('0'.repeat(32), { ...all, path: where }),
          // And the core's own routes for it are the main process's alone.
          save: await invoke('courses.save_file', {
            path: { course_id: id },
            body: { kind: 'template' },
          }),
          look: await invoke('courses.look_at_file', { body: { path: where } }),
          bringIn: await invoke('courses.bring_in_file', { body: { path: where, holds: all } }),
        };
      },
      [course, target, holds] as const,
    );

    const refused = { ok: false, error: { code: 'invalid_request' } };
    expect(results.withPath).toMatchObject(refused);
    expect(results.notACourse).toMatchObject(refused);
    expect(results.notAKind).toMatchObject(refused);
    expect(results.pathAsToken).toMatchObject(refused);
    expect(results.looseHolds).toMatchObject(refused);
    expect(results.save).toMatchObject(refused);
    expect(results.look).toMatchObject(refused);
    expect(results.bringIn).toMatchObject(refused);
    // A token nobody was given names no file.
    expect(results.forgedToken).toMatchObject({ ok: false, error: { code: 'file_not_chosen' } });
    // What else the page passed was not looked at: the learner was asked, and said no.
    expect(results.extra).toEqual({ ok: true, data: null });
    expect(results.choose).toEqual({ ok: true, data: null });
    const asked = await app.evaluate(
      () => (globalThis as Record<string, unknown>).adleAskedKinds as string[],
    );
    expect(asked).toEqual(['save', 'open']);
    expect(existsSync(target)).toBe(false);
    // Nothing the core wrote for a save that was backed out of is left behind.
    const handover = path.join(profileDir, 'data', 'handover');
    expect(existsSync(handover) ? readdirSync(handover) : []).toEqual([]);
  });
});

test.describe('settings as a file', () => {
  test('the page cannot say where settings are saved or read from, and the keys need a password', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    const target = path.join(profileDir, 'chosen-by-the-page.json');
    // The learner backs out of every question the operating system asks.
    await app.evaluate(({ dialog }) => {
      const asked: string[] = [];
      (globalThis as Record<string, unknown>).adleAskedKinds = asked;
      dialog.showSaveDialog = () => {
        asked.push('save');
        return Promise.resolve({ canceled: true, filePath: '' });
      };
      dialog.showOpenDialog = () => {
        asked.push('open');
        return Promise.resolve({ canceled: true, filePaths: [] });
      };
    });
    const all = { appearance: true, learning: true, voice: true, provider: true, keys: true };

    const results = await page.evaluate(
      async ([where, parts]) => {
        type Loose = Record<string, (...args: unknown[]) => Promise<unknown>>;
        const settings = window.adle!.settings as unknown as Loose;
        const invoke = window.adle!.core.invoke as unknown as (
          operation: string,
          params?: unknown,
        ) => Promise<unknown>;
        const without = { ...parts, keys: false };
        const plain = { password: null, setUpVoice: false };
        return {
          // The keys are never written without a password to lock them with.
          noPassword: await settings.saveFile!(parts, null),
          shortPassword: await settings.saveFile!(parts, 'short'),
          // A place to save, named every way the page can think of.
          withPath: await settings.saveFile!({ ...without, path: where }, null),
          extra: await settings.saveFile!(without, null, where, { filePath: where }),
          // A file to read, the same.
          choose: await settings.chooseFile!(where, { filePaths: [where] }),
          pathAsToken: await settings.bringIn!(where, without, plain),
          forgedToken: await settings.bringIn!('0'.repeat(32), without, plain),
          looseOptions: await settings.bringIn!('0'.repeat(32), without, {
            ...plain,
            path: where,
          }),
          // And the core's own routes for it are the main process's alone.
          save: await invoke('settings.save_file'),
          look: await invoke('settings.look_at_file', { body: { voice: {} } }),
          bringIn: await invoke('settings.bring_in_file', { body: {} }),
        };
      },
      [target, all] as const,
    );

    const refused = { ok: false, error: { code: 'invalid_request' } };
    expect(results.noPassword).toMatchObject({ ok: false, error: { code: 'password_needed' } });
    expect(results.shortPassword).toMatchObject({
      ok: false,
      error: { code: 'password_needed' },
    });
    expect(results.withPath).toMatchObject(refused);
    expect(results.pathAsToken).toMatchObject(refused);
    expect(results.looseOptions).toMatchObject(refused);
    expect(results.save).toMatchObject(refused);
    expect(results.look).toMatchObject(refused);
    expect(results.bringIn).toMatchObject(refused);
    expect(results.forgedToken).toMatchObject({ ok: false, error: { code: 'file_not_chosen' } });
    // What else the page passed was not looked at: the learner was asked, and said no.
    expect(results.extra).toEqual({ ok: true, data: null });
    expect(results.choose).toEqual({ ok: true, data: null });
    const asked = await app.evaluate(
      () => (globalThis as Record<string, unknown>).adleAskedKinds as string[],
    );
    expect(asked).toEqual(['save', 'open']);
    expect(existsSync(target)).toBe(false);
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

  test('script in a player frame cannot reach the network by a road that is not a request', async ({
    adle,
  }) => {
    const player = await mountRawPlayer(adle.page, 'e2ewebrtc');
    await player.waitFor(`m.type === 'ready'`);
    const frame = adle.page.frames().find((candidate) => candidate.url().startsWith(player.origin));
    expect(frame).toBeDefined();
    const there = await listeners();
    try {
      const found = await frame!.evaluate(reachOutWithoutARequest, {
        udpPort: there.udpPort,
        tcpPort: there.tcpPort,
      });
      expect(found.candidates).toEqual([]);
      expect(there.arrived()).toEqual([]);
    } finally {
      there.close();
    }
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
