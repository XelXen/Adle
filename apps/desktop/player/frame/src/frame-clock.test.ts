import { describe, expect, it, vi } from 'vitest';

import { type FrameTarget, installFrameClock } from './frame-clock';

function fakeTarget() {
  const scheduled = new Map<number, FrameRequestCallback>();
  let nextHandle = 1;
  const target: FrameTarget = {
    requestAnimationFrame(callback) {
      const handle = nextHandle++;
      scheduled.set(handle, callback);
      return handle;
    },
    cancelAnimationFrame(handle) {
      scheduled.delete(handle);
    },
  };
  const flush = (): number => {
    const callbacks = [...scheduled.values()];
    scheduled.clear();
    for (const callback of callbacks) callback(0);
    return callbacks.length;
  };
  return { target, flush, pending: () => scheduled.size };
}

describe('installFrameClock', () => {
  it('passes frames straight through while running', () => {
    const { target, flush } = fakeTarget();
    installFrameClock(target);
    const frame = vi.fn();
    target.requestAnimationFrame(frame);
    flush();
    expect(frame).toHaveBeenCalledOnce();
  });

  it('holds frames while paused and releases them on resume', () => {
    const { target, flush, pending } = fakeTarget();
    const clock = installFrameClock(target);
    const frame = vi.fn();

    clock.pause();
    target.requestAnimationFrame(frame);
    expect(pending()).toBe(0);
    expect(flush()).toBe(0);
    expect(frame).not.toHaveBeenCalled();

    clock.resume();
    expect(pending()).toBe(1);
    flush();
    expect(frame).toHaveBeenCalledOnce();
  });

  it('lets a held frame be cancelled', () => {
    const { target, flush } = fakeTarget();
    const clock = installFrameClock(target);
    const frame = vi.fn();
    clock.pause();
    const handle = target.requestAnimationFrame(frame);
    target.cancelAnimationFrame(handle);
    clock.resume();
    flush();
    expect(frame).not.toHaveBeenCalled();
  });

  it('hands frames out at once while rushing, one task each, and not through the display', () => {
    const { target, flush, pending } = fakeTarget();
    const tasks: (() => void)[] = [];
    const clock = installFrameClock(
      target,
      (work) => tasks.push(work),
      () => 42,
    );
    const first = vi.fn();
    const second = vi.fn();

    clock.rush();
    expect(clock.rushing).toBe(true);
    target.requestAnimationFrame(first);
    target.requestAnimationFrame(second);
    // Nothing was asked of the display, and nothing has run yet: each waits for its task.
    expect(pending()).toBe(0);
    expect(first).not.toHaveBeenCalled();
    tasks.shift()?.();
    expect(first).toHaveBeenCalledWith(42);
    expect(second).not.toHaveBeenCalled();
    tasks.shift()?.();
    expect(second).toHaveBeenCalledOnce();
    expect(flush()).toBe(0);

    // Back at the display's pace, a frame waits for the display again.
    clock.steady();
    const third = vi.fn();
    target.requestAnimationFrame(third);
    expect(pending()).toBe(1);
    expect(tasks).toHaveLength(0);
    flush();
    expect(third).toHaveBeenCalledOnce();
  });

  it('rushes the player’s housekeeping with the frames, and lets either be cancelled', () => {
    const { target, pending } = fakeTarget();
    const tasks: (() => void)[] = [];
    const clock = installFrameClock(target, (work) => tasks.push(work));
    clock.rush();

    const housekeeping = vi.fn();
    clock.requestNativeFrame(housekeeping);
    expect(pending()).toBe(0);
    tasks.shift()?.();
    expect(housekeeping).toHaveBeenCalledOnce();

    const cancelledFrame = vi.fn();
    const cancelledChore = vi.fn();
    target.cancelAnimationFrame(target.requestAnimationFrame(cancelledFrame));
    clock.cancelNativeFrame(clock.requestNativeFrame(cancelledChore));
    for (const task of tasks.splice(0)) task();
    expect(cancelledFrame).not.toHaveBeenCalled();
    expect(cancelledChore).not.toHaveBeenCalled();
  });

  it('holds a rushed frame while paused, and rushes it on resume', () => {
    const { target } = fakeTarget();
    const tasks: (() => void)[] = [];
    const clock = installFrameClock(target, (work) => tasks.push(work));
    clock.rush();
    const heldBack = vi.fn();
    clock.pause();
    target.requestAnimationFrame(heldBack);
    expect(tasks).toHaveLength(0);
    clock.resume();
    expect(tasks).toHaveLength(1);
    tasks.shift()?.();
    expect(heldBack).toHaveBeenCalledOnce();
  });

  it('keeps the native clock available for housekeeping while paused', () => {
    const { target, flush } = fakeTarget();
    const clock = installFrameClock(target);
    const housekeeping = vi.fn();
    clock.pause();
    clock.requestNativeFrame(housekeeping);
    flush();
    expect(housekeeping).toHaveBeenCalledOnce();
  });

  it('notifies listeners of every gated frame request, paused or not', () => {
    const { target } = fakeTarget();
    const clock = installFrameClock(target);
    const listener = vi.fn();
    const stop = clock.onFrameRequested(listener);
    target.requestAnimationFrame(() => undefined);
    clock.pause();
    target.requestAnimationFrame(() => undefined);
    expect(listener).toHaveBeenCalledTimes(2);
    stop();
    target.requestAnimationFrame(() => undefined);
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
