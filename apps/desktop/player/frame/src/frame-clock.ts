/**
 * A pausable animation-frame clock for the player frame.
 *
 * Wanim paces every drawn frame on `requestAnimationFrame` (documented in its
 * scheduler: "resolves on requestAnimationFrame"). It has no pause API, so the
 * player gates the frame callback instead: while paused, requested frames are
 * held and released on resume. Because Wanim advances animations by a fixed
 * step per logical frame (not by wall-clock time), holding frames freezes a
 * scene exactly at a frame boundary and resuming continues without a jump.
 *
 * This must be installed before the Wanim runtime is loaded.
 */

export interface FrameTarget {
  requestAnimationFrame(callback: FrameRequestCallback): number;
  cancelAnimationFrame(handle: number): void;
}

export interface FrameClock {
  readonly paused: boolean;
  pause(): void;
  resume(): void;
  /** Subscribe to every frame request made through the gated clock. */
  onFrameRequested(listener: () => void): () => void;
  /** The ungated clock, for the player's own housekeeping loop. */
  requestNativeFrame(callback: FrameRequestCallback): number;
  cancelNativeFrame(handle: number): void;
}

export function installFrameClock(target: FrameTarget): FrameClock {
  const nativeRequest = target.requestAnimationFrame.bind(target);
  const nativeCancel = target.cancelAnimationFrame.bind(target);

  let paused = false;
  // Held callbacks get negative handles so they can never collide with native ones.
  let nextHeldHandle = -1;
  const held = new Map<number, FrameRequestCallback>();
  const listeners = new Set<() => void>();

  target.requestAnimationFrame = (callback: FrameRequestCallback): number => {
    for (const listener of listeners) listener();
    if (!paused) return nativeRequest(callback);
    const handle = nextHeldHandle--;
    held.set(handle, callback);
    return handle;
  };

  target.cancelAnimationFrame = (handle: number): void => {
    if (handle < 0) held.delete(handle);
    else nativeCancel(handle);
  };

  return {
    get paused() {
      return paused;
    },
    pause() {
      paused = true;
    },
    resume() {
      if (!paused) return;
      paused = false;
      const pending = [...held.values()];
      held.clear();
      for (const callback of pending) nativeRequest(callback);
    },
    onFrameRequested(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    requestNativeFrame: nativeRequest,
    cancelNativeFrame: nativeCancel,
  };
}
