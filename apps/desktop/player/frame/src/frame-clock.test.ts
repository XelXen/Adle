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
