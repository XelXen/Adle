/**
 * One execution of a scene source on the player canvas.
 *
 * Wraps Wanim's documented `runPythonOnCanvas` entry point and translates its
 * callbacks into protocol messages. No Wanim internals are used beyond the
 * published options (`signal`, `onSceneReady`, `onController`, `onMessage`) and
 * the presentation controller's public `next()` / `restart()` / `state`.
 */
import {
  type ControlValue,
  type HostMessage,
  isSceneEventName,
  isSceneEventValue,
  type PlayerMessage,
  PROTOCOL_VERSION,
  type SceneQuality,
  type ScenePlaybackState,
} from '@adle/event-protocol';

import {
  collectControls,
  type ControlHandle,
  describeControls,
  type WanimControlClasses,
} from './controls';
import type { FrameClock } from './frame-clock';

type LoadMessage = Extract<HostMessage, { type: 'load' }>;

interface PresentationController {
  next(): void;
  readonly state: {
    sceneName: string;
    phaseIndex: number;
    phaseCount: number;
    phaseKind: 'blueprint' | 'construct';
    done: boolean;
    canNext: boolean;
  };
}

interface WanimMessage {
  key: unknown;
  value: unknown;
}

export interface WanimBridge {
  runPythonOnCanvas(
    source: string,
    canvas: HTMLCanvasElement,
    options: {
      quality: string;
      mode: string;
      theme: 'light' | 'dark';
      background: string;
      instanceId: string;
      realtime: boolean;
      fps: number;
      sceneName?: string;
      signal: AbortSignal;
      onScene(name: string): void;
      onSceneReady(scene: unknown): void;
      onController(controller: unknown): void;
      onMessage(message: unknown): void;
    },
  ): Promise<unknown>;
  wanim: WanimControlClasses;
}

const QUALITY_FLAGS: Record<SceneQuality, string> = { low: '-ql', medium: '-qm', high: '-qh' };
/**
 * Stage background per theme (the Sprout `surface` token). The host supplies it so
 * scenes never choose their own backdrop; they only pick foreground colours.
 */
const STAGE_BACKGROUND = { light: '#FFFFFF', dark: '#141414' } as const;
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
/** How often control values are compared and reported, at most. */
const CONTROL_REPORT_INTERVAL_MS = 120;

type Post = (message: PlayerMessage) => void;

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message || error.name;
  if (typeof error === 'string') return error;
  return 'The scene failed without an error message.';
}

function isAbort(error: unknown): boolean {
  return error instanceof Error && (error.name === 'AbortError' || /abort/i.test(error.message));
}

export class SceneRun {
  readonly runId: string;
  private readonly abortController = new AbortController();
  private readonly startedAt = performance.now();
  private controller: PresentationController | null = null;
  private controls: ControlHandle[] = [];
  private sceneReady = false;
  private firstFrameReported = false;
  private disposed = false;
  private scene: unknown = null;
  private sceneName = '';
  private loadedAnnounced = false;
  /** Phase the control list was last read in; controls are re-read when the phase changes. */
  private controlsPhaseKey = '';
  private lastStateJson = '';
  private lastControlsJson = '';
  private lastControlReportAt = 0;
  private housekeepingHandle = 0;
  private stopListeningForFrames: (() => void) | null = null;

  constructor(
    private readonly bridge: WanimBridge,
    private readonly canvas: HTMLCanvasElement,
    private readonly clock: FrameClock,
    private readonly request: LoadMessage,
    private readonly post: Post,
  ) {
    this.runId = request.runId;
  }

  start(): void {
    if (this.request.autoplay) this.clock.resume();
    else this.clock.pause();

    this.stopListeningForFrames = this.clock.onFrameRequested(() => this.noteFrameRequested());
    this.housekeepingHandle = this.clock.requestNativeFrame(this.housekeeping);

    this.bridge
      .runPythonOnCanvas(this.request.source, this.canvas, {
        quality: QUALITY_FLAGS[this.request.quality],
        // A slide of a lesson holds after each step until the host says `next`
        // (ADR-049): Wanim's slides mode, which parks after every phase.
        mode: this.request.pacing === 'cued' ? 'slides' : 'normal',
        theme: this.request.theme,
        background: STAGE_BACKGROUND[this.request.theme],
        instanceId: this.runId,
        realtime: true,
        fps: 30,
        ...(this.request.sceneName ? { sceneName: this.request.sceneName } : {}),
        signal: this.abortController.signal,
        onScene: (name) => {
          this.sceneName = name;
          this.announceLoaded();
        },
        onSceneReady: (scene) => {
          if (this.disposed) return;
          // A restart or a later scene class hands us a new instance.
          this.scene = scene;
          this.controls = [];
          this.controlsPhaseKey = '';
          this.lastControlsJson = '';
          this.sceneReady = true;
          this.announceLoaded();
        },
        onController: (controller) => {
          this.controller = controller as PresentationController;
        },
        onMessage: (message) => this.forwardSceneEvent(message as WanimMessage),
      })
      .then(() => {
        if (this.disposed) return;
        this.reportState();
        this.post({ adle: PROTOCOL_VERSION, type: 'finished', runId: this.runId });
      })
      .catch((error: unknown) => {
        if (this.disposed || isAbort(error)) return;
        this.post({
          adle: PROTOCOL_VERSION,
          type: 'error',
          runId: this.runId,
          stage: this.sceneReady ? 'runtime' : 'compile',
          message: describeError(error),
        });
      });
  }

  play(): void {
    if (this.disposed) return;
    this.clock.resume();
    this.post({ adle: PROTOCOL_VERSION, type: 'paused', runId: this.runId, paused: false });
  }

  pause(): void {
    if (this.disposed) return;
    this.clock.pause();
    this.post({ adle: PROTOCOL_VERSION, type: 'paused', runId: this.runId, paused: true });
  }

  next(): void {
    if (this.disposed) return;
    this.controller?.next();
  }

  setControl(name: string, value: ControlValue): void {
    if (this.disposed) return;
    const handle = this.controls.find((candidate) => candidate.name === name);
    if (handle?.write(value)) this.reportControls(true);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.stopListeningForFrames?.();
    this.clock.cancelNativeFrame(this.housekeepingHandle);
    this.abortController.abort();
    // Release any held frame so the aborted run can unwind instead of leaking.
    this.clock.resume();
  }

  /** Wanim reports the scene instance and its class name separately; announce once both exist. */
  private announceLoaded(): void {
    if (this.disposed || this.loadedAnnounced || !this.sceneReady || !this.sceneName) return;
    this.loadedAnnounced = true;
    this.post({
      adle: PROTOCOL_VERSION,
      type: 'loaded',
      runId: this.runId,
      sceneName: IDENTIFIER.test(this.sceneName) ? this.sceneName : 'Scene',
      loadMs: performance.now() - this.startedAt,
    });
  }

  /** The first frame request after the scene exists means one frame has been drawn. */
  private noteFrameRequested(): void {
    if (this.disposed || this.firstFrameReported || !this.sceneReady) return;
    this.firstFrameReported = true;
    this.post({
      adle: PROTOCOL_VERSION,
      type: 'first-frame',
      runId: this.runId,
      elapsedMs: performance.now() - this.startedAt,
    });
  }

  private readonly housekeeping = (): void => {
    if (this.disposed) return;
    this.reportState();
    this.reportControls(false);
    this.housekeepingHandle = this.clock.requestNativeFrame(this.housekeeping);
  };

  private reportState(): void {
    const controller = this.controller;
    if (!controller || !this.sceneReady) return;
    let raw: PresentationController['state'];
    try {
      raw = controller.state;
    } catch {
      return;
    }
    if (!IDENTIFIER.test(raw.sceneName)) return;
    const state: ScenePlaybackState = {
      sceneName: raw.sceneName,
      phaseKind: raw.phaseKind,
      phaseIndex: raw.phaseIndex,
      phaseCount: raw.phaseCount,
      // A blueprint page is live until the scene moves on. A scene whose last page
      // is a blueprint stays interactive indefinitely, with nothing to continue to.
      interactive: !raw.done && raw.phaseKind === 'blueprint',
      canNext: !raw.done && raw.canNext,
      done: raw.done,
    };
    const json = JSON.stringify(state);
    if (json === this.lastStateJson) return;
    this.lastStateJson = json;
    this.post({ adle: PROTOCOL_VERSION, type: 'state', runId: this.runId, state });
  }

  /**
   * `adle_controls` is assigned inside `blueprint()`, which runs after the scene
   * is constructed, so the mapping is read lazily: once per phase, and again on
   * each report tick while an interactive phase has not published any yet.
   */
  private refreshControlHandles(): void {
    let phaseKey = '';
    try {
      const state = this.controller?.state;
      if (state) phaseKey = `${state.sceneName}:${state.phaseIndex}:${state.phaseKind}`;
    } catch {
      return;
    }
    if (phaseKey === this.controlsPhaseKey && this.controls.length > 0) return;
    if (phaseKey === this.controlsPhaseKey && !phaseKey.endsWith(':blueprint')) return;
    this.controlsPhaseKey = phaseKey;
    this.controls = collectControls(this.scene, this.bridge.wanim);
  }

  private reportControls(force: boolean): void {
    if (!this.sceneReady) return;
    const now = performance.now();
    if (!force && now - this.lastControlReportAt < CONTROL_REPORT_INTERVAL_MS) return;
    this.lastControlReportAt = now;
    this.refreshControlHandles();
    const controls = describeControls(this.controls);
    const json = JSON.stringify(controls);
    if (json === this.lastControlsJson) return;
    this.lastControlsJson = json;
    this.post({ adle: PROTOCOL_VERSION, type: 'controls', runId: this.runId, controls });
  }

  private forwardSceneEvent(message: WanimMessage): void {
    if (this.disposed) return;
    const value = message.value === undefined ? null : message.value;
    // Closed vocabulary and primitive payloads only; anything else is dropped here
    // and would be dropped again by the host.
    if (!isSceneEventName(message.key) || !isSceneEventValue(value)) return;
    this.post({
      adle: PROTOCOL_VERSION,
      type: 'scene-event',
      runId: this.runId,
      name: message.key,
      value,
    });
  }
}
