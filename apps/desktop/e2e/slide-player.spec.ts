import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { expect, test } from './support/app';
import { mountRawPlayer } from './support/player';
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

for (const file of slides) {
  for (const theme of ['dark', 'light'] as const) {
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
        expect(done?.type, JSON.stringify(done)).toBe('scene-event');
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
      expect((await player.messages()).filter((message) => message.type === 'error')).toEqual([]);
    });
  }
}
