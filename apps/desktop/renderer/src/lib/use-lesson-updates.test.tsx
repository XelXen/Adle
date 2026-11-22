import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LessonForPlayer } from '@adle/contracts';

type Scene = LessonForPlayer['scenes'][number];
type Segment = LessonForPlayer['lesson']['segments'][number];
interface Opened {
  scenes: Scene[];
  pending_scene_ids: string[];
  writing?: boolean;
  lesson: { segments: Segment[] };
}

const asked: string[] = [];
let next: Opened | Error = { scenes: [], pending_scene_ids: [], lesson: { segments: [] } };

vi.mock('./core-client', () => ({
  callCore: (operation: string, request: { path: { lesson_id: string } }) => {
    asked.push(`${operation}:${request.path.lesson_id}`);
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
  },
}));

const { LOOK_EVERY_MS, useLessonUpdates } = await import('./use-lesson-updates');

const scene = (id: string): Scene => ({ id }) as Scene;
const part = (id: string): Segment => ({ id, type: 'explanation', title: id }) as Segment;
const opened = (fields: Partial<Opened> = {}): Opened => ({
  scenes: [],
  pending_scene_ids: [],
  lesson: { segments: [part('seg_1')] },
  ...fields,
});
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

describe('useLessonUpdates', () => {
  it('asks nothing of a lesson that has all its pictures and all its parts', async () => {
    const { result } = renderHook(() =>
      useLessonUpdates('les_1', opened({ scenes: [scene('scn_1')] })),
    );
    await turn();
    await turn();
    expect(asked).toEqual([]);
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect(result.current.pending.size).toBe(0);
    expect(result.current.writing).toBe(false);
  });

  it('looks again while a picture is still to come, and stops when none is', async () => {
    next = opened({ pending_scene_ids: ['scn_1', 'scn_2'] });
    const { result } = renderHook(() =>
      useLessonUpdates('les_1', opened({ pending_scene_ids: ['scn_1', 'scn_2'] })),
    );
    expect([...result.current.pending]).toEqual(['scn_1', 'scn_2']);

    // Nothing new yet.
    await turn();
    expect(asked).toEqual(['lessons.get:les_1']);
    expect(result.current.scenes).toEqual([]);

    // The first has been drawn.
    next = opened({ scenes: [scene('scn_1')], pending_scene_ids: ['scn_2'] });
    await turn();
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect([...result.current.pending]).toEqual(['scn_2']);

    // The second could not be: it is no longer waited for, and no picture comes for it.
    next = opened({ scenes: [scene('scn_1')] });
    await turn();
    expect(result.current.pending.size).toBe(0);
    expect(asked).toHaveLength(3);

    // And then there is nothing left to look for.
    await turn();
    await turn();
    expect(asked).toHaveLength(3);
  });

  it('follows the parts of a lesson still being written until its writing ends', async () => {
    next = opened({ writing: true });
    const { result } = renderHook(() => useLessonUpdates('les_1', opened({ writing: true })));
    expect(result.current.writing).toBe(true);

    await turn();
    expect(result.current.segments.map((item) => item.id)).toEqual(['seg_1']);

    next = opened({ writing: true, lesson: { segments: [part('seg_1'), part('seg_2')] } });
    await turn();
    expect(result.current.segments.map((item) => item.id)).toEqual(['seg_1', 'seg_2']);

    next = opened({
      writing: false,
      lesson: { segments: [part('seg_1'), part('seg_2'), part('seg_3')] },
    });
    await turn();
    expect(result.current.segments.map((item) => item.id)).toEqual(['seg_1', 'seg_2', 'seg_3']);
    expect(result.current.writing).toBe(false);
    const looks = asked.length;

    // Nothing more is coming: it stops looking.
    await turn();
    await turn();
    expect(asked).toHaveLength(looks);
  });

  it('keeps what it has when a look fails, and looks again', async () => {
    const { result } = renderHook(() =>
      useLessonUpdates('les_1', opened({ pending_scene_ids: ['scn_1'] })),
    );
    next = new Error('the core is restarting');
    await turn();
    expect([...result.current.pending]).toEqual(['scn_1']);

    next = opened({ scenes: [scene('scn_1')] });
    await turn();
    expect(result.current.scenes.map((item) => item.id)).toEqual(['scn_1']);
    expect(result.current.pending.size).toBe(0);
  });

  it('stops looking when the learner leaves the lesson', async () => {
    next = opened({ pending_scene_ids: ['scn_1'] });
    const { unmount } = renderHook(() =>
      useLessonUpdates('les_1', opened({ pending_scene_ids: ['scn_1'] })),
    );
    await turn();
    expect(asked).toHaveLength(1);
    unmount();
    await turn();
    await turn();
    expect(asked).toHaveLength(1);
  });
});
