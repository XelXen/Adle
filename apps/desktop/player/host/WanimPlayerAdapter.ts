/**
 * Host-side adapter for the isolated Wanim scene player.
 *
 * The rest of Adle talks to this class and never to Wanim. It owns one
 * sandboxed `<iframe>` (on its own `adle://<instance>.player` origin), speaks
 * the validated `@adle/event-protocol`, and turns every way a scene can go
 * wrong into a single `failure` event so the lesson can show its fallback.
 *
 * Trust boundary: everything received from the frame is untrusted. Messages
 * are accepted only from this adapter's own frame window and origin, and only
 * if `parsePlayerMessage` recognises them exactly.
 */
import {
  type ControlDescriptor,
  type ControlValue,
  createPlayerInstanceId,
  createRunId,
  type HostMessage,
  parsePlayerMessage,
  type PlayerMessage,
  playerEntryUrl,
  playerOrigin,
  PROTOCOL_VERSION,
  type SceneEventName,
  type SceneEventValue,
  type ScenePlaybackState,
  type SceneQuality,
  type SceneTheme,
} from '@adle/event-protocol';

export type PlayerStatus =
  | 'idle'
  | 'loading'
  | 'playing'
  | 'paused'
  /** Showing a live page: the learner can operate the scene's controls. */
  | 'interactive'
  | 'finished'
  | 'failed'
  | 'disposed';

export type SceneFailureStage = 'boot' | 'compile' | 'runtime' | 'timeout' | 'unresponsive';

export interface SceneFailure {
  stage: SceneFailureStage;
  /** Technical detail for diagnostics. Not learner-facing copy. */
  message: string;
}

export interface LoadSceneOptions {
  /** One complete Python scene file. */
  source: string;
  /** The scene class to run, when the file defines more than one. */
  sceneName?: string;
  theme: SceneTheme;
  quality?: SceneQuality;
  /** Start playing immediately (default) or hold on the first frame until `play()`. */
  autoplay?: boolean;
}

export interface SceneEvent {
  name: SceneEventName;
  value: SceneEventValue;
}

export interface PlayerEvents {
  status: PlayerStatus;
  state: ScenePlaybackState;
  controls: ControlDescriptor[];
  'scene-event': SceneEvent;
  'first-frame': { loadMs: number; firstFrameMs: number };
  finished: undefined;
  failure: SceneFailure;
}

export interface PlayerTimeouts {
  /** Frame document load plus Wanim runtime start. */
  bootMs: number;
  /** From `load` until the scene is compiled and constructed. */
  loadMs: number;
  /** How often liveness is probed while a scene is active. */
  pingIntervalMs: number;
  /** Silence after which the frame is declared unresponsive. */
  unresponsiveMs: number;
}

export const DEFAULT_TIMEOUTS: PlayerTimeouts = {
  bootMs: 20_000,
  loadMs: 20_000,
  pingIntervalMs: 1_000,
  unresponsiveMs: 5_000,
};

/**
 * How many messages a frame may send in one second. A scene at work sends a handful: its
 * state when it changes, its controls a few times a second, an event now and then; one that
 * reports every move of the pointer sends as many as the screen has frames. Several times
 * that is a flood, and each message is work for the page that shows the lesson.
 */
export const MESSAGE_BUDGET_PER_SECOND = 600;

export interface WanimPlayerAdapterOptions {
  /** Accessible name of the frame. */
  title?: string;
  className?: string;
  timeouts?: Partial<PlayerTimeouts>;
}

type Listener<K extends keyof PlayerEvents> = (payload: PlayerEvents[K]) => void;

const ACTIVE_STATUSES: ReadonlySet<PlayerStatus> = new Set([
  'loading',
  'playing',
  'paused',
  'interactive',
]);

export class WanimPlayerAdapter {
  private frame: HTMLIFrameElement | null = null;
  private frameOrigin = '';
  private frameReady = false;
  private currentStatus: PlayerStatus = 'idle';
  private runId: string | null = null;
  private lastLoad: LoadSceneOptions | null = null;
  private pendingLoad: LoadSceneOptions | null = null;
  private loadMs = 0;
  private paused = false;
  private interactive = false;
  private bootTimer: number | null = null;
  private loadTimer: number | null = null;
  private pingTimer: number | null = null;
  private pingNonce = 0;
  private lastPongAt = 0;
  private budgetSecondStartedAt = 0;
  private messagesThisSecond = 0;
  private readonly timeouts: PlayerTimeouts;
  private readonly listeners: { [K in keyof PlayerEvents]?: Set<Listener<K>> } = {};

  constructor(
    private readonly container: HTMLElement,
    private readonly options: WanimPlayerAdapterOptions = {},
  ) {
    this.timeouts = { ...DEFAULT_TIMEOUTS, ...options.timeouts };
    window.addEventListener('message', this.handleMessage);
  }

  get status(): PlayerStatus {
    return this.currentStatus;
  }

  on<K extends keyof PlayerEvents>(event: K, listener: Listener<K>): () => void {
    const set = (this.listeners[event] ??= new Set<Listener<K>>() as never) as Set<Listener<K>>;
    set.add(listener);
    return () => {
      set.delete(listener);
    };
  }

  /** Compile and run a scene. Replaces whatever was running. */
  load(options: LoadSceneOptions): void {
    if (this.currentStatus === 'disposed') return;
    this.lastLoad = options;
    this.paused = options.autoplay === false;
    this.interactive = false;
    this.clearTimer('loadTimer');
    this.setStatus('loading');

    if (!this.frame) this.mountFrame();
    if (this.frameReady) this.sendLoad(options);
    else this.pendingLoad = options;
  }

  play(): void {
    this.sendForRun('play');
  }

  pause(): void {
    this.sendForRun('pause');
  }

  /** Continue past an interactive page. */
  next(): void {
    this.sendForRun('next');
  }

  /** Run the current scene again from the beginning. */
  reset(): void {
    if (this.lastLoad) this.load(this.lastLoad);
  }

  /** Scenes choose their colours when they are constructed, so a theme change reloads. */
  setTheme(theme: SceneTheme): void {
    if (!this.lastLoad || this.lastLoad.theme === theme) return;
    const reload = ACTIVE_STATUSES.has(this.currentStatus) || this.currentStatus === 'finished';
    this.lastLoad = { ...this.lastLoad, theme };
    if (reload) this.load(this.lastLoad);
  }

  /** Set a mirrored scene control from an accessible input outside the canvas. */
  setControl(name: string, value: ControlValue): void {
    if (!this.runId) return;
    this.post({ adle: PROTOCOL_VERSION, type: 'set-control', runId: this.runId, name, value });
  }

  dispose(): void {
    if (this.currentStatus === 'disposed') return;
    window.removeEventListener('message', this.handleMessage);
    this.destroyFrame();
    this.setStatus('disposed');
    for (const key of Object.keys(this.listeners) as (keyof PlayerEvents)[]) {
      this.listeners[key]?.clear();
    }
  }

  // -- frame lifecycle ------------------------------------------------------

  private mountFrame(): void {
    const instanceId = createPlayerInstanceId();
    const frame = document.createElement('iframe');
    // The attribute mirrors the sandbox directive enforced by the frame's own CSP.
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.title = this.options.title ?? 'Interactive visualization';
    if (this.options.className) frame.className = this.options.className;
    frame.src = playerEntryUrl(instanceId);

    this.frame = frame;
    this.frameOrigin = playerOrigin(instanceId);
    this.frameReady = false;
    this.messagesThisSecond = 0;
    this.container.appendChild(frame);

    this.bootTimer = window.setTimeout(() => {
      this.fail({ stage: 'boot', message: 'The scene runtime did not start in time.' });
    }, this.timeouts.bootMs);
  }

  /**
   * Remove the frame. Its origin is never reused, so a scene that hung or
   * crashed its process cannot affect the next one.
   */
  private destroyFrame(): void {
    this.clearTimer('bootTimer');
    this.clearTimer('loadTimer');
    this.stopWatchdog();
    if (this.frame && this.frameReady) this.post({ adle: PROTOCOL_VERSION, type: 'dispose' });
    this.frame?.remove();
    this.frame = null;
    this.frameReady = false;
    this.frameOrigin = '';
    this.runId = null;
    this.pendingLoad = null;
  }

  private sendLoad(options: LoadSceneOptions): void {
    this.runId = createRunId();
    this.post({
      adle: PROTOCOL_VERSION,
      type: 'load',
      runId: this.runId,
      source: options.source,
      sceneName: options.sceneName ?? null,
      theme: options.theme,
      quality: options.quality ?? 'medium',
      autoplay: options.autoplay ?? true,
    });
    this.loadTimer = window.setTimeout(() => {
      this.fail({ stage: 'timeout', message: 'The scene took too long to prepare.' });
    }, this.timeouts.loadMs);
    this.startWatchdog();
  }

  private sendForRun(type: 'play' | 'pause' | 'next'): void {
    if (!this.runId || !ACTIVE_STATUSES.has(this.currentStatus)) return;
    this.post({ adle: PROTOCOL_VERSION, type, runId: this.runId });
  }

  private post(message: HostMessage): void {
    this.frame?.contentWindow?.postMessage(message, this.frameOrigin);
  }

  // -- liveness -------------------------------------------------------------

  private startWatchdog(): void {
    this.stopWatchdog();
    this.lastPongAt = performance.now();
    this.pingTimer = window.setInterval(() => {
      if (!ACTIVE_STATUSES.has(this.currentStatus)) {
        this.stopWatchdog();
        return;
      }
      if (performance.now() - this.lastPongAt > this.timeouts.unresponsiveMs) {
        this.fail({ stage: 'unresponsive', message: 'The scene stopped responding.' });
        return;
      }
      this.pingNonce = (this.pingNonce + 1) % 10_000;
      this.post({ adle: PROTOCOL_VERSION, type: 'ping', nonce: this.pingNonce });
    }, this.timeouts.pingIntervalMs);
  }

  private stopWatchdog(): void {
    this.clearTimer('pingTimer');
  }

  private clearTimer(name: 'bootTimer' | 'loadTimer' | 'pingTimer'): void {
    const handle = this[name];
    if (handle === null) return;
    if (name === 'pingTimer') window.clearInterval(handle);
    else window.clearTimeout(handle);
    this[name] = null;
  }

  // -- messages -------------------------------------------------------------

  private readonly handleMessage = (event: MessageEvent<unknown>): void => {
    if (!this.frame || event.source !== this.frame.contentWindow) return;
    if (event.origin !== this.frameOrigin) return;
    // Counted before it is read: a flood of nonsense is as much work to receive as any other.
    if (this.overBudget()) {
      this.fail({ stage: 'runtime', message: 'The scene sent more messages than it may.' });
      return;
    }
    const message = parsePlayerMessage(event.data);
    if (message) this.dispatch(message);
  };

  /** Count one message from the frame; true when it is one too many for this second. */
  private overBudget(): boolean {
    const now = performance.now();
    if (now - this.budgetSecondStartedAt >= 1000) {
      this.budgetSecondStartedAt = now;
      this.messagesThisSecond = 0;
    }
    this.messagesThisSecond += 1;
    return this.messagesThisSecond > MESSAGE_BUDGET_PER_SECOND;
  }

  private dispatch(message: PlayerMessage): void {
    switch (message.type) {
      case 'ready':
        this.frameReady = true;
        this.clearTimer('bootTimer');
        if (this.pendingLoad) {
          const pending = this.pendingLoad;
          this.pendingLoad = null;
          this.sendLoad(pending);
        }
        return;
      case 'pong':
        this.lastPongAt = performance.now();
        return;
      case 'error':
        // A boot error has no run; a run error must belong to the current run.
        if (message.runId !== null && message.runId !== this.runId) return;
        this.fail({ stage: message.stage, message: message.message });
        return;
      default:
        break;
    }

    // Everything below belongs to a run; ignore anything from a replaced one.
    if (message.runId !== this.runId) return;
    switch (message.type) {
      case 'loaded':
        this.clearTimer('loadTimer');
        this.loadMs = message.loadMs;
        this.refreshStatus();
        break;
      case 'first-frame':
        this.emit('first-frame', { loadMs: this.loadMs, firstFrameMs: message.elapsedMs });
        break;
      case 'state':
        this.interactive = message.state.interactive;
        this.emit('state', message.state);
        if (ACTIVE_STATUSES.has(this.currentStatus)) this.refreshStatus();
        break;
      case 'controls':
        this.emit('controls', message.controls);
        break;
      case 'scene-event':
        this.emit('scene-event', { name: message.name, value: message.value });
        break;
      case 'paused':
        this.paused = message.paused;
        if (ACTIVE_STATUSES.has(this.currentStatus)) this.refreshStatus();
        break;
      case 'finished':
        this.stopWatchdog();
        this.setStatus('finished');
        this.emit('finished', undefined);
        break;
    }
  }

  private refreshStatus(): void {
    if (this.loadTimer !== null) return; // still loading
    this.setStatus(this.paused ? 'paused' : this.interactive ? 'interactive' : 'playing');
  }

  /** Enter the failed state, discard the frame, and tell listeners once. */
  private fail(failure: SceneFailure): void {
    if (this.currentStatus === 'failed' || this.currentStatus === 'disposed') return;
    this.destroyFrame();
    this.setStatus('failed');
    this.emit('failure', failure);
  }

  private setStatus(status: PlayerStatus): void {
    if (this.currentStatus === status) return;
    this.currentStatus = status;
    this.emit('status', status);
  }

  private emit<K extends keyof PlayerEvents>(event: K, payload: PlayerEvents[K]): void {
    const set = this.listeners[event];
    if (!set) return;
    for (const listener of [...set]) listener(payload);
  }
}
