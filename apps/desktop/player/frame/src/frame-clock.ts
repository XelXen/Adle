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
 * The same gate can rush: frames handed out as fast as they are asked for, one task each,
 * instead of at the display's pace, and the player's own housekeeping with them. With the
 * frame's clock running fast as well (`time-warp.ts`), a scene is run through in a
 * fraction of its length. That is how a scene is tried before a learner is shown it
 * (ADR-038). Nothing a rushed frame does depends on the frame being visible.
 *
 * This must be installed before the Wanim runtime is loaded.
 */

export interface FrameTarget {
  requestAnimationFrame(callback: FrameRequestCallback): number;
  cancelAnimationFrame(handle: number): void;
}

export interface FrameClock {
  readonly paused: boolean;
  /** Frames are handed out as fast as they are asked for, not at the display's pace. */
  readonly rushing: boolean;
  pause(): void;
  resume(): void;
  rush(): void;
  steady(): void;
  /** Subscribe to every frame request made through the gated clock. */
  onFrameRequested(listener: () => void): () => void;
  /** The ungated clock, for the player's own housekeeping loop. */
  requestNativeFrame(callback: FrameRequestCallback): number;
  cancelNativeFrame(handle: number): void;
}

/**
 * As soon as the page is free, without waiting for the display: one task each, so that
 * messages from the host (and the watchdog's ping) are still answered in between.
 */
function whenFree(): (work: () => void) => void {
  let channel: MessageChannel | null = null;
  const waiting: (() => void)[] = [];
  return (work) => {
    if (!channel) {
      channel = new MessageChannel();
      channel.port1.onmessage = () => waiting.shift()?.();
    }
    waiting.push(work);
    channel.port2.postMessage(null);
  };
}

/** Rushed frames get handles of their own, far below held ones and native ones. */
const FIRST_RUSHED_HANDLE = -1_000_000_000;

export function installFrameClock(
  target: FrameTarget,
  soon: (work: () => void) => void = whenFree(),
  now: () => number = () => performance.now(),
): FrameClock {
  const nativeRequest = target.requestAnimationFrame.bind(target);
  const nativeCancel = target.cancelAnimationFrame.bind(target);

  let paused = false;
  let rushing = false;
  // Held callbacks get negative handles so they can never collide with native ones.
  let nextHeldHandle = -1;
  let nextRushedHandle = FIRST_RUSHED_HANDLE;
  const held = new Map<number, FrameRequestCallback>();
  const rushed = new Map<number, FrameRequestCallback>();
  const listeners = new Set<() => void>();

  /** A frame at the display's pace, or at once while rushing. */
  const frame = (callback: FrameRequestCallback): number => {
    if (!rushing) return nativeRequest(callback);
    const handle = nextRushedHandle--;
    rushed.set(handle, callback);
    soon(() => {
      const due = rushed.get(handle);
      if (!due) return;
      rushed.delete(handle);
      due(now());
    });
    return handle;
  };
  const cancel = (handle: number): void => {
    if (rushed.delete(handle)) return;
    if (handle < 0) held.delete(handle);
    else nativeCancel(handle);
  };

  target.requestAnimationFrame = (callback: FrameRequestCallback): number => {
    for (const listener of listeners) listener();
    if (!paused) return frame(callback);
    const handle = nextHeldHandle--;
    held.set(handle, callback);
    return handle;
  };

  target.cancelAnimationFrame = cancel;

  return {
    get paused() {
      return paused;
    },
    pause() {
      paused = true;
    },
    get rushing() {
      return rushing;
    },
    resume() {
      if (!paused) return;
      paused = false;
      const pending = [...held.values()];
      held.clear();
      for (const callback of pending) frame(callback);
    },
    rush() {
      rushing = true;
    },
    steady() {
      rushing = false;
    },
    onFrameRequested(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    // Housekeeping keeps pace with the frames: at the display's, or at once while rushing.
    requestNativeFrame: frame,
    cancelNativeFrame: cancel,
  };
}
