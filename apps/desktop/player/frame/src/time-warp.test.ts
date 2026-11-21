import { describe, expect, it } from 'vitest';

import { installTimeWarp } from './time-warp';

function clockAt(start: number) {
  let real = start;
  const target = { now: (): number => real };
  return {
    target,
    pass: (ms: number) => {
      real += ms;
    },
  };
}

describe('installTimeWarp', () => {
  it('keeps time as it is until it is asked to run fast', () => {
    const { target, pass } = clockAt(1000);
    const warp = installTimeWarp(target);
    expect(target.now()).toBe(1000);
    pass(40);
    expect(target.now()).toBe(1040);
    expect(warp.speed).toBe(1);
  });

  it('runs fast from the moment it is asked, without a jump', () => {
    const { target, pass } = clockAt(0);
    const warp = installTimeWarp(target);
    pass(100);
    warp.setSpeed(25);
    expect(target.now()).toBe(100);
    pass(40);
    // A second of the scene in 40 ms of the computer's.
    expect(target.now()).toBe(1100);
  });

  it('never runs backwards when it slows down again', () => {
    const { target, pass } = clockAt(0);
    const warp = installTimeWarp(target);
    warp.setSpeed(25);
    pass(40);
    const fast = target.now();
    warp.setSpeed(1);
    expect(target.now()).toBe(fast);
    pass(10);
    expect(target.now()).toBe(fast + 10);
  });

  it('ignores a speed that is not a positive number', () => {
    const { target, pass } = clockAt(0);
    const warp = installTimeWarp(target);
    for (const speed of [0, -2, Number.NaN, Number.POSITIVE_INFINITY]) warp.setSpeed(speed);
    expect(warp.speed).toBe(1);
    pass(5);
    expect(target.now()).toBe(5);
  });
});
