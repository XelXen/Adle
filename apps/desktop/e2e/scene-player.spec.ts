/**
 * The Wanim integration, proven against the real runtime inside Electron.
 * Covers PLAN.md §10.2 (the required early spike) and the M4 acceptance items
 * that concern the player frame.
 */
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { desktopDir, expect, repoRoot, test } from './support/app';
import { exampleScene, fixtureScene, mountRawPlayer, worldToPage } from './support/player';

test.describe('scene player frame', () => {
  test('renders an animation-only scene from a complete Python file', async ({ adle }) => {
    const player = await mountRawPlayer(adle.page, 'e2eplain');
    const ready = await player.waitFor(`m.type === 'ready' || m.type === 'error'`);
    expect(ready).toMatchObject({ type: 'ready', wanimVersion: '0.1.3', origin: player.origin });

    await player.load(exampleScene('weighted_sum.py'));
    expect(await player.waitFor(`m.type === 'loaded'`)).toMatchObject({ sceneName: 'WeightedSum' });
    const firstFrame = await player.waitFor(`m.type === 'first-frame'`);
    expect(firstFrame?.elapsedMs).toBeLessThan(5000);
    expect(await player.waitFor(`m.type === 'finished' || m.type === 'error'`)).toMatchObject({
      type: 'finished',
    });

    // Something was actually drawn: the frame is not a blank stage.
    const screenshot = await adle.page.screenshot();
    expect(screenshot.byteLength).toBeGreaterThan(15_000);
    expect(adle.problems).toEqual([]);
  });

  test('an interactive scene reacts to the host, to the pointer, and reports events', async ({
    adle,
  }) => {
    const { page } = adle;
    const player = await mountRawPlayer(page, 'e2einteractive');
    await player.waitFor(`m.type === 'ready'`);
    await player.load(exampleScene('neuron_weight.py'));

    // The scene parks on its interactive page and publishes its named controls.
    expect(await player.waitFor(`m.type === 'state' && m.state.interactive`)).toMatchObject({
      state: { sceneName: 'NeuronWeight', phaseKind: 'blueprint', phaseCount: 2, canNext: true },
    });
    expect(await player.waitFor(`m.type === 'controls' && m.controls.length === 2`)).toMatchObject({
      controls: [
        { name: 'weight', kind: 'slider', value: 0.5, min: -2, max: 2 },
        { name: 'bias_on', kind: 'switch', value: false },
      ],
    });
    const before = await page.screenshot();

    // Host-driven change: the accessible-control path.
    await player.send({ type: 'set-control', runId: 'run', name: 'weight', value: 1.8 });
    expect(
      await player.waitFor(`m.type === 'controls' && m.controls[0].value > 1.7`, 3000),
    ).not.toBeNull();
    expect(
      await player.waitFor(`m.type === 'scene-event' && m.name === 'explored'`, 3000),
    ).toMatchObject({
      value: true,
    });
    await player.send({ type: 'set-control', runId: 'run', name: 'bias_on', value: true });
    expect(
      await player.waitFor(`m.type === 'scene-event' && m.name === 'passed'`, 3000),
    ).toMatchObject({
      value: true,
    });
    await page.waitForTimeout(200);
    const afterHostChange = await page.screenshot();
    expect(afterHostChange.equals(before)).toBe(false);

    // Out-of-range values are clamped to the control's range, not applied raw.
    await player.send({ type: 'set-control', runId: 'run', name: 'weight', value: 999 });
    expect(
      await player.waitFor(`m.type === 'controls' && m.controls[0].value === 2`, 3000),
    ).not.toBeNull();

    // Pointer-driven change: drag the canvas slider knob from w = 2 to w = -1.
    const box = await player.canvasBox();
    const knobAt = (weight: number) => worldToPage(box, -5 + ((weight + 2) / 4) * 5.5, -2.7);
    const from = knobAt(2);
    const to = knobAt(-1);
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move((from.x + to.x) / 2, to.y, { steps: 6 });
    await page.mouse.move(to.x, to.y, { steps: 6 });
    await page.mouse.up();
    const dragged = await player.waitFor(
      `m.type === 'controls' && Math.abs(m.controls[0].value + 1) < 0.15`,
      3000,
    );
    expect(dragged).not.toBeNull();

    // Continue into the animation, pause mid-way, and resume.
    await player.send({ type: 'next', runId: 'run' });
    expect(
      await player.waitFor(`m.type === 'state' && m.state.phaseKind === 'construct'`, 3000),
    ).not.toBeNull();
    await player.send({ type: 'pause', runId: 'run' });
    expect(await player.waitFor(`m.type === 'paused' && m.paused === true`, 2000)).not.toBeNull();
    await page.waitForTimeout(150);
    const pausedA = await page.screenshot();
    await page.waitForTimeout(1200);
    const pausedB = await page.screenshot();
    expect(pausedA.equals(pausedB)).toBe(true);
    expect((await player.messages()).some((message) => message.type === 'finished')).toBe(false);

    await player.send({ type: 'play', runId: 'run' });
    expect(
      await player.waitFor(`m.type === 'finished' || m.type === 'error'`, 10_000),
    ).toMatchObject({
      type: 'finished',
    });

    // Teardown: after dispose the frame goes quiet.
    await player.send({ type: 'dispose' });
    await page.waitForTimeout(300);
    const count = (await player.messages()).length;
    await page.waitForTimeout(500);
    expect((await player.messages()).length).toBe(count);
  });

  test('holds on the first frame when autoplay is off, until play', async ({ adle }) => {
    const player = await mountRawPlayer(adle.page, 'e2ehold');
    await player.waitFor(`m.type === 'ready'`);
    await player.load(exampleScene('weighted_sum.py'), { autoplay: false });
    expect(await player.waitFor(`m.type === 'first-frame'`)).not.toBeNull();
    await adle.page.waitForTimeout(1500);
    expect((await player.messages()).some((message) => message.type === 'finished')).toBe(false);
    await player.send({ type: 'play', runId: 'run' });
    expect(await player.waitFor(`m.type === 'finished'`, 10_000)).not.toBeNull();
  });

  test('follows the requested theme', async ({ adle }) => {
    const player = await mountRawPlayer(adle.page, 'e2etheme');
    await player.waitFor(`m.type === 'ready'`);
    await player.load(exampleScene('weighted_sum.py'), { theme: 'light' });
    await player.waitFor(`m.type === 'finished'`);
    const light = await adle.page.screenshot();
    await player.load(exampleScene('weighted_sum.py'), { theme: 'dark' });
    // The reload reuses the run id; wait for the new run to finish.
    await adle.page.waitForTimeout(500);
    await expect
      .poll(
        async () =>
          (await player.messages()).filter((message) => message.type === 'finished').length,
        {
          timeout: 15_000,
        },
      )
      .toBe(2);
    const dark = await adle.page.screenshot();
    expect(light.equals(dark)).toBe(false);
  });

  test('a curve shown by its stroke is a line; shown with set_opacity it is filled in', async ({
    adle,
  }) => {
    const { app, page } = adle;
    const player = await mountRawPlayer(page, 'e2ecurve');
    await player.waitFor(`m.type === 'ready'`);
    const box = await player.canvasBox();

    /** The colour the window really shows at a point of the scene, read by the main process. */
    const colourAt = async (worldX: number, worldY: number): Promise<number[]> => {
      const point = worldToPage(box, worldX, worldY);
      const encoded = await app.evaluate(async ({ BrowserWindow }, { x, y }): Promise<string> => {
        const image = await BrowserWindow.getAllWindows()[0]!.webContents.capturePage({
          x: Math.round(x),
          y: Math.round(y),
          width: 1,
          height: 1,
        });
        return image.toBitmap().toString('base64');
      }, point);
      // One pixel, as the window holds it: blue, green, red, alpha.
      const [blue = 0, green = 0, red = 0] = [...Buffer.from(encoded, 'base64')];
      return [red, green, blue];
    };
    const finishedRuns = async (): Promise<number> =>
      (await player.messages()).filter((message) => message.type === 'finished').length;

    // Between the sigmoid and the straight line from its first point to its last: at
    // z = 5 the curve is at 0.99 and that line at 0.75. Nothing is drawn at 0.87.
    const between: [number, number] = [2.0, -2 + 0.87 * 4];
    const emptyCorner: [number, number] = [-6.5, 3.5];

    await player.load(fixtureScene('curve_stroke.py'), { theme: 'light' });
    await expect.poll(finishedRuns, { timeout: 20_000 }).toBe(1);
    const background = await colourAt(...emptyCorner);
    expect(await colourAt(...between)).toEqual(background);

    // The mistake a real model made in its first interactive scene (2026-11-20):
    // set_opacity sets the fill as well, and an open path is filled across its ends.
    await player.load(fixtureScene('curve_opacity.py'), { theme: 'light' });
    await expect.poll(finishedRuns, { timeout: 20_000 }).toBe(2);
    expect(await colourAt(...emptyCorner)).toEqual(background);
    const filled = await colourAt(...between);
    expect(filled).not.toEqual(background);
    // It is the curve's own blue: more blue than red.
    expect(filled[2]!).toBeGreaterThan(filled[0]! + 40);
  });

  for (const [file, stage, pattern] of [
    ['syntax_error.py', 'compile', /indentation/i],
    ['bad_import.py', 'compile', /cannot use Python module 'os'/],
    ['no_scene.py', 'compile', /No Scene subclass/],
    ['runtime_error.py', 'runtime', /.+/],
  ] as const) {
    test(`a broken scene (${file}) fails safely with a ${stage} error`, async ({ adle }) => {
      const player = await mountRawPlayer(adle.page, `e2e${stage}${file.length}`);
      await player.waitFor(`m.type === 'ready'`);
      await player.load(fixtureScene(file));
      const outcome = await player.waitFor(`m.type === 'error' || m.type === 'finished'`);
      expect(outcome).toMatchObject({ type: 'error', stage });
      expect(String(outcome?.message)).toMatch(pattern);

      // The frame survives a bad scene and can run a good one straight after.
      await player.load(exampleScene('weighted_sum.py'));
      await expect
        .poll(
          async () => (await player.messages()).some((message) => message.type === 'finished'),
          {
            timeout: 15_000,
          },
        )
        .toBe(true);
      // The host renderer was never disturbed.
      expect(adle.page.url()).toBe('adle://app/index.html');
    });
  }

  test('a scene stuck in a loop cannot freeze the app or poison the next player', async ({
    adle,
  }) => {
    const { page } = adle;
    const stuck = await mountRawPlayer(page, 'e2estuck');
    await stuck.waitFor(`m.type === 'ready'`);
    await stuck.send({ type: 'ping', nonce: 1 });
    expect(await stuck.waitFor(`m.type === 'pong' && m.nonce === 1`, 2000)).not.toBeNull();

    await stuck.load(fixtureScene('busy_loop.py'));
    await page.waitForTimeout(2000);
    // The stuck frame cannot answer a liveness probe...
    await stuck.send({ type: 'ping', nonce: 2 });
    expect(await stuck.waitFor(`m.type === 'pong' && m.nonce === 2`, 2000)).toBeNull();
    // ...but the app itself stays responsive, because the player is another process.
    expect(await page.evaluate(() => 6 * 7)).toBe(42);
    await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeAttached();

    // A new player on a fresh origin is unaffected.
    await stuck.remove();
    const fresh = await mountRawPlayer(page, 'e2efresh');
    expect(await fresh.waitFor(`m.type === 'ready' || m.type === 'error'`)).toMatchObject({
      type: 'ready',
    });
    await fresh.load(exampleScene('weighted_sum.py'));
    expect(await fresh.waitFor(`m.type === 'finished' || m.type === 'error'`)).toMatchObject({
      type: 'finished',
    });
  });
});

/** The scene files that ship with the app as part of the sample course. */
const sampleScenesDir = path.join(
  repoRoot,
  'services',
  'core',
  'adle_core',
  'sample_course',
  'scenes',
);

const sceneSets = [
  {
    name: 'scene-authoring skill examples',
    directory: path.join(repoRoot, 'skills', 'wanim-scene-authoring', 'examples'),
    prefix: 'ex',
    atLeast: 3,
  },
  // What a learner actually sees in the sample course. A lesson's animation is paced to
  // its narration, so these run longer than the examples.
  { name: 'sample course scenes', directory: sampleScenesDir, prefix: 'sc', atLeast: 11 },
] as const;

for (const set of sceneSets) {
  test.describe(set.name, () => {
    const examples = readdirSync(set.directory).filter((file) => file.endsWith('.py'));

    test('there are scenes to run', () => {
      expect(examples.length).toBeGreaterThanOrEqual(set.atLeast);
    });

    for (const file of examples) {
      for (const theme of ['light', 'dark'] as const) {
        test(`${file} runs to completion in the ${theme} theme`, async ({ adle }) => {
          test.setTimeout(90_000);
          const player = await mountRawPlayer(
            adle.page,
            `${set.prefix}${theme}${file.replace(/[^a-z0-9]/g, '').slice(0, 12)}`,
          );
          await player.waitFor(`m.type === 'ready'`);
          await player.load(readFileSync(path.join(set.directory, file), 'utf8'), { theme });

          const settled = await player.waitFor(
            `m.type === 'error' || m.type === 'finished' || (m.type === 'state' && m.state.interactive)`,
            60_000,
          );
          expect(settled?.type, JSON.stringify(settled)).not.toBe('error');
          expect(settled).not.toBeNull();

          // An interactive scene with a second page continues into its animation.
          if (settled?.type === 'state') {
            const state = settled.state as { canNext: boolean };
            if (state.canNext) {
              await player.send({ type: 'next', runId: 'run' });
              const finished = await player.waitFor(
                `m.type === 'error' || m.type === 'finished'`,
                20_000,
              );
              expect(finished?.type, JSON.stringify(finished)).toBe('finished');
            }
          }
          expect((await player.messages()).filter((message) => message.type === 'error')).toEqual(
            [],
          );
          await adle.page.screenshot({
            path: path.join(
              desktopDir,
              'test-results',
              'screens',
              `scene-${set.prefix}-${theme}-${file}.png`,
            ),
          });
        });
      }
    }
  });
}

test.describe('scene player in the app (Settings → About & diagnostics)', () => {
  test('the runtime check renders and its mirrored slider drives the scene by keyboard', async ({
    adle,
  }) => {
    const { page } = adle;
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'About & diagnostics' }).click();
    await page.getByRole('button', { name: 'Run check' }).click();

    await expect(page.getByText('Rendering works')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('Move the slider to test interaction')).toBeVisible();
    // The frame is isolated: sandboxed, on its own origin, with an accessible name.
    const frame = page.locator('iframe');
    await expect(frame).toHaveAttribute('sandbox', 'allow-scripts allow-same-origin');
    await expect(frame).toHaveAttribute('title', /Runtime check/);
    expect(await frame.getAttribute('src')).toMatch(/^adle:\/\/[0-9a-f]{16}\.player\/index\.html$/);

    // The scene's slider is mirrored as a native control that works without a mouse.
    const slider = page.getByRole('slider', { name: 'Circle radius' });
    await expect(slider).toBeVisible();
    await expect(slider).toHaveValue('1.2');
    const before = await page.locator('figure').screenshot();
    await slider.focus();
    for (let step = 0; step < 25; step += 1) await page.keyboard.press('ArrowRight');
    await expect(slider).not.toHaveValue('1.2');
    await expect(page.getByText('Interaction works')).toBeVisible();
    await page.waitForTimeout(200);
    const after = await page.locator('figure').screenshot();
    expect(after.equals(before)).toBe(false);
    expect(adle.problems).toEqual([]);
  });
});
