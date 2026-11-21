/**
 * The frame's clock, which can run fast (ADR-038).
 *
 * Wanim paces a scene by what `performance.now()` says: it draws the next frame only once a
 * frame's interval has passed, and a `wait` lasts its seconds. To run a scene through in a
 * fraction of its length, the frame says that time passes faster: at speed 25, a second of
 * the scene goes by in 40 ms. Time never runs backwards, whatever the speed is changed to.
 *
 * Installed before the Wanim runtime is loaded. Only the frame's own clock is changed: the
 * host keeps its own time, and with it the watchdog and every limit it sets.
 */

export interface TimeWarp {
  readonly speed: number;
  /** From now on, time passes this many times as fast. Anything but a positive number is ignored. */
  setSpeed(next: number): void;
}

export function installTimeWarp(target: { now(): number }): TimeWarp {
  const real = target.now.bind(target);
  let speed = 1;
  let realAt = real();
  let shownAt = realAt;
  Object.defineProperty(target, 'now', {
    configurable: true,
    writable: true,
    value: (): number => shownAt + (real() - realAt) * speed,
  });
  return {
    get speed() {
      return speed;
    },
    setSpeed(next) {
      if (!Number.isFinite(next) || next <= 0) return;
      const at = real();
      shownAt += (at - realAt) * speed;
      realAt = at;
      speed = next;
    },
  };
}
