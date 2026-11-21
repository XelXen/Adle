import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LessonForPlayer } from '@adle/contracts';

type Scene = LessonForPlayer['scenes'][number];
type Opened = Pick<LessonForPlayer, 'scenes' | 'pending_scene_ids'>;

const asked: string[] = [];
let next: Opened | Error = { scenes: [], pending_scene_ids: [] };

vi.mock('./core-client', () => ({
  callCore: (operation: string, request: { path: { lesson_id: string } }) => {
    asked.push(`${operation}:${request.path.lesson_id}`);
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
  },
}));

const { LOOK_EVERY_MS, useLessonPictures } = await import('./use-lesson-pictures');

const scene = (id: string): Scene => ({ id }) as Scene;
const turn = async (): Promise<void> => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS);
  });
};

beforeEach(() => {
  vi.useFakeTimers();
  asked.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useLessonPictures', () => {
  it('asks nothing of a lesson that has all its pictures', async () => {
    const { result } = renderHook(() =>
      useLessonPictures('les_1', { scenes: [scene('scn_1')], pending_scene_ids: [] }),
    );
    await turn();
    await turn();
    expect(asked).toEqual([]);
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect(result.current.pending.size).toBe(0);
  });

  it('looks again while a picture is still to come, and stops when none is', async () => {
    next = { scenes: [], pending_scene_ids: ['scn_1', 'scn_2'] };
    const { result } = renderHook(() =>
      useLessonPictures('les_1', { scenes: [], pending_scene_ids: ['scn_1', 'scn_2'] }),
    );
    expect([...result.current.pending]).toEqual(['scn_1', 'scn_2']);

    // Nothing new yet.
    await turn();
    expect(asked).toEqual(['lessons.get:les_1']);
    expect(result.current.scenes).toEqual([]);

    // The first has been drawn.
    next = { scenes: [scene('scn_1')], pending_scene_ids: ['scn_2'] };
    await turn();
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect([...result.current.pending]).toEqual(['scn_2']);

    // The second could not be: it is no longer waited for, and no picture comes for it.
    next = { scenes: [scene('scn_1')], pending_scene_ids: [] };
    await turn();
    expect(result.current.pending.size).toBe(0);
    expect(asked).toHaveLength(3);

    // And then there is nothing left to look for.
    await turn();
    await turn();
    expect(asked).toHaveLength(3);
  });

  it('keeps what it has when a look fails, and looks again', async () => {
    const { result } = renderHook(() =>
      useLessonPictures('les_1', { scenes: [], pending_scene_ids: ['scn_1'] }),
    );
    next = new Error('the core is restarting');
    await turn();
    expect([...result.current.pending]).toEqual(['scn_1']);

    next = { scenes: [scene('scn_1')], pending_scene_ids: [] };
    await turn();
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect(result.current.pending.size).toBe(0);
  });

  it('stops looking when the learner leaves the lesson', async () => {
    next = { scenes: [], pending_scene_ids: ['scn_1'] };
    const { unmount } = renderHook(() =>
      useLessonPictures('les_1', { scenes: [], pending_scene_ids: ['scn_1'] }),
    );
    await turn();
    expect(asked).toHaveLength(1);
    unmount();
    await turn();
    await turn();
    expect(asked).toHaveLength(1);
  });
});
