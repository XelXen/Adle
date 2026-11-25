import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { expect, test } from './support/app';
import { mountRawPlayer } from './support/player';
import { themesFor } from './support/themes';
import { desktopDir } from './support/app';

/**
 * A lesson's slides, as the core writes them from a model's script (ADR-049): one of every
 * kind of element and every verb, written by `npm run slides`. Each is paced by cues: it
 * holds after each step until the host says `next`, and says when a step is done.
 */
const directory = path.join(desktopDir, 'e2e', 'fixtures', 'slides');
const plan = JSON.parse(readFileSync(path.join(directory, 'steps.json'), 'utf8')) as Record<
  string,
  { steps: number; interactive: boolean }
>;
const slides = readdirSync(directory).filter((file) => file.endsWith('.py'));

test('there are slides to run', () => {
  expect(slides.length).toBeGreaterThanOrEqual(15);
  expect(Object.keys(plan).sort()).toEqual([...slides].sort());
});

for (const [index, file] of slides.entries()) {
  for (const theme of themesFor(index)) {
    test(`${file} steps through every cue in the ${theme} theme`, async ({ adle }) => {
      test.setTimeout(120_000);
      const { steps, interactive } = plan[file]!;
      const player = await mountRawPlayer(
        adle.page,
        `sl${theme}${file.replace(/[^a-z0-9]/g, '').slice(0, 14)}`,
      );
      await player.waitFor(`m.type === 'ready'`);
      await player.load(readFileSync(path.join(directory, file), 'utf8'), {
        theme,
        pacing: 'cued',
      });
      const shot = (step: number) =>
        adle.page.screenshot({
          path: path.join(
            desktopDir,
            'test-results',
            'screens',
            `slide-${theme}-${file}-${step}.png`,
          ),
        });

      for (let step = 0; step < steps; step += 1) {
        if (step > 0) await player.send({ type: 'next', runId: 'run' });
        const done = await player.waitFor(
          `m.type === 'error' || (m.type === 'scene-event' && m.name === 'step' && m.value === ${step})`,
          30_000,
        );
        // A step that does not come says where the slide stopped: the frame's last
        // messages, its page among them, each with when it came (`t`, from the mount).
        const said = done
          ? JSON.stringify(done)
          : `no step ${step} in 30 s; last: ${JSON.stringify((await player.messages()).slice(-6))}`;
        expect(done?.type, said).toBe('scene-event');
        // Held: nothing more happens until the host says so.
        await adle.page.waitForTimeout(250);
        const after = (await player.messages()).filter(
          (message) => message.type === 'scene-event' && message.name === 'step',
        );
        expect(after.map((message) => message.value)).toEqual(
          Array.from({ length: step + 1 }, (_, index) => index),
        );
        await shot(step);
      }

      if (interactive) {
        const controls = await player.waitFor(
          `m.type === 'controls' && m.controls.length > 0`,
          10_000,
        );
        expect(controls).not.toBeNull();
        const name = (controls!.controls as { name: string }[])[0]!.name;
        await player.send({ type: 'set-control', runId: 'run', name, value: 0.9 });
        const explored = await player.waitFor(
          `m.type === 'error' || (m.type === 'scene-event' && m.name === 'explored')`,
          10_000,
        );
        expect(explored?.type, JSON.stringify(explored)).toBe('scene-event');
        await adle.page.waitForTimeout(300);
        await shot(steps);
      }
      // At the end of every step no word lay over another, and nothing past the edge of
      // the screen (ADR-055): the slide says so as each step ends.
      expect(
        (await player.messages())
          .filter((message) => message.type === 'scene-event' && message.name === 'layout')
          .map((message) => message.value),
        `${file} in the ${theme} theme`,
      ).toEqual([]);
      expect((await player.messages()).filter((message) => message.type === 'error')).toEqual([]);
    });
  }
}

/**
 * Slides a model might write that cannot be laid out clear (ADR-069): an arrow through a
 * word, and more labels on one point than there is room for round it. Each word over one
 * drawn before it, or with a line through it, is given a soft shadow in the stage's own
 * color. The slide says, as each step ends, how many such words have none that can be seen.
 */
const crowdedDirectory = path.join(directory, 'crowded');
const crowdedPlan = JSON.parse(
  readFileSync(path.join(crowdedDirectory, 'steps.json'), 'utf8'),
) as Record<string, { steps: number; interactive: boolean }>;
const crowded = readdirSync(crowdedDirectory).filter((file) => file.endsWith('.py'));

test('there are slides that cannot be laid out clear', () => {
  expect(crowded.length).toBeGreaterThanOrEqual(2);
  expect(Object.keys(crowdedPlan).sort()).toEqual([...crowded].sort());
});

for (const file of crowded) {
  // Both themes: the shadow is the color of the stage, which each theme has its own of.
  for (const theme of ['dark', 'light'] as const) {
    test(`${file} gives what lies over something a shadow in the ${theme} theme`, async ({
      adle,
    }) => {
      test.setTimeout(120_000);
      const { steps } = crowdedPlan[file]!;
      const player = await mountRawPlayer(
        adle.page,
        `cr${theme}${file.replace(/[^a-z0-9]/g, '').slice(0, 14)}`,
      );
      await player.waitFor(`m.type === 'ready'`);
      await player.load(readFileSync(path.join(crowdedDirectory, file), 'utf8'), {
        theme,
        pacing: 'cued',
      });
      for (let step = 0; step < steps; step += 1) {
        if (step > 0) await player.send({ type: 'next', runId: 'run' });
        const done = await player.waitFor(
          `m.type === 'error' || (m.type === 'scene-event' && m.name === 'step' && m.value === ${step})`,
          30_000,
        );
        expect(done?.type, JSON.stringify(done)).toBe('scene-event');
        await adle.page.waitForTimeout(250);
        await adle.page.screenshot({
          path: path.join(
            desktopDir,
            'test-results',
            'screens',
            `slide-crowded-${theme}-${file}-${step}.png`,
          ),
        });
      }
      const layout = (await player.messages())
        .filter((message) => message.type === 'scene-event' && message.name === 'layout')
        .map((message) => String(message.value));
      // It is crowded, as a model wrote it: something lies over something at some step.
      expect(layout.length, file).toBeGreaterThan(0);
      // And every word that does has its shadow.
      for (const said of layout) expect(said, file).toMatch(/, 0 without a shadow$/);
      expect((await player.messages()).filter((message) => message.type === 'error')).toEqual([]);
    });
  }
}
