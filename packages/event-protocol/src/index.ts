/**
 * Message protocol between the Adle host (renderer) and the isolated scene
 * player frame.
 *
 * The player executes generated scene code, so everything it sends is
 * untrusted. Both directions are validated here with hand-written checks: no
 * unknown message types, no unknown fields, bounded sizes, primitive payloads
 * only. Nothing in this protocol can carry a callback, a URL to load, or a
 * file path.
 *
 * Versioning: `adle` is the protocol version. A breaking change increments it
 * and both sides reject messages with a different version.
 */

export * from './origins';

export const PROTOCOL_VERSION = 1;

/** Largest scene source the host will send to the player. */
export const MAX_SCENE_SOURCE_CHARS = 100_000;
/** Largest serialised message the host accepts from the player. */
export const MAX_PLAYER_MESSAGE_CHARS = 8_192;
const MAX_ERROR_MESSAGE_CHARS = 2_000;
const MAX_STRING_VALUE_CHARS = 200;
const MAX_CONTROLS = 16;

export type SceneTheme = 'light' | 'dark';
export type SceneQuality = 'low' | 'medium' | 'high';
/**
 * How a scene is paced. `normal`: it plays through, holding only on a live page.
 * `cued`: a slide of a lesson (ADR-049), which holds after each of its steps until the
 * host says `next`, when the narration reaches the words the next step belongs to.
 */
export type ScenePacing = 'normal' | 'cued';
export const SCENE_PACINGS: readonly ScenePacing[] = ['normal', 'cued'];

/**
 * Events a scene may report with `self.post_message(name, value)`.
 * This vocabulary is closed: anything else is dropped by the player and,
 * independently, by the host.
 */
export const SCENE_EVENT_NAMES = ['passed', 'explored', 'progress', 'step'] as const;
export type SceneEventName = (typeof SCENE_EVENT_NAMES)[number];
export type SceneEventValue = boolean | number | string | null;

export type ControlKind = 'slider' | 'switch' | 'number';
export type ControlValue = number | boolean;

/** A scene control mirrored to the host so it can offer an accessible equivalent. */
export interface ControlDescriptor {
  name: string;
  kind: ControlKind;
  value: ControlValue;
  /** Present for `slider` and bounded `number` controls. */
  min?: number;
  max?: number;
}

export type PhaseKind = 'blueprint' | 'construct';

export interface ScenePlaybackState {
  sceneName: string;
  phaseKind: PhaseKind;
  phaseIndex: number;
  phaseCount: number;
  /** True while a live page is showing: the learner can operate the scene's controls. */
  interactive: boolean;
  /** True when the host can move the scene on with `next` (another page follows). */
  canNext: boolean;
  done: boolean;
}

// ---------------------------------------------------------------------------
// Host -> player
// ---------------------------------------------------------------------------

export type HostMessage =
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'load';
      runId: string;
      source: string;
      sceneName: string | null;
      theme: SceneTheme;
      quality: SceneQuality;
      /** When false the scene is prepared and held on its first frame until `play`. */
      autoplay: boolean;
      /**
       * Run the scene through as fast as it can be drawn, to find out whether it runs
       * before anyone is shown it (ADR-038). What it reports is the same as ever; only
       * the time it takes is not a learner's.
       */
      rehearsal: boolean;
      pacing: ScenePacing;
    }
  | { adle: typeof PROTOCOL_VERSION; type: 'play'; runId: string }
  | { adle: typeof PROTOCOL_VERSION; type: 'pause'; runId: string }
  | { adle: typeof PROTOCOL_VERSION; type: 'next'; runId: string }
  /** Liveness probe. A player whose scene is stuck in a loop cannot answer it. */
  | { adle: typeof PROTOCOL_VERSION; type: 'ping'; nonce: number }
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'set-control';
      runId: string;
      name: string;
      value: ControlValue;
    }
  | { adle: typeof PROTOCOL_VERSION; type: 'dispose' };

export type HostMessageType = HostMessage['type'];

// ---------------------------------------------------------------------------
// Player -> host
// ---------------------------------------------------------------------------

export type PlayerErrorStage = 'boot' | 'compile' | 'runtime';

export type PlayerMessage =
  | { adle: typeof PROTOCOL_VERSION; type: 'ready'; wanimVersion: string }
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'loaded';
      runId: string;
      /** The scene class that became active. */
      sceneName: string;
      /** Time from receiving `load` to the scene being constructed (compile + setup). */
      loadMs: number;
    }
  | { adle: typeof PROTOCOL_VERSION; type: 'first-frame'; runId: string; elapsedMs: number }
  | { adle: typeof PROTOCOL_VERSION; type: 'state'; runId: string; state: ScenePlaybackState }
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'controls';
      runId: string;
      controls: ControlDescriptor[];
    }
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'scene-event';
      runId: string;
      name: SceneEventName;
      value: SceneEventValue;
    }
  | { adle: typeof PROTOCOL_VERSION; type: 'paused'; runId: string; paused: boolean }
  | { adle: typeof PROTOCOL_VERSION; type: 'finished'; runId: string }
  | { adle: typeof PROTOCOL_VERSION; type: 'pong'; nonce: number }
  | {
      adle: typeof PROTOCOL_VERSION;
      type: 'error';
      runId: string | null;
      stage: PlayerErrorStage;
      message: string;
    };

export type PlayerMessageType = PlayerMessage['type'];

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

const RUN_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
const IDENTIFIER_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const THEMES: readonly SceneTheme[] = ['light', 'dark'];
const QUALITIES: readonly SceneQuality[] = ['low', 'medium', 'high'];
const CONTROL_KINDS: readonly ControlKind[] = ['slider', 'switch', 'number'];
const PHASE_KINDS: readonly PhaseKind[] = ['blueprint', 'construct'];
const ERROR_STAGES: readonly PlayerErrorStage[] = ['boot', 'compile', 'runtime'];

type Fields = Record<string, unknown>;

function isRecord(value: unknown): value is Fields {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)
  );
}

/** True when `value` has exactly the given keys (no extras, none missing). */
function hasExactKeys(value: Fields, keys: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function isRunId(value: unknown): value is string {
  return typeof value === 'string' && RUN_ID_PATTERN.test(value);
}

function isIdentifier(value: unknown): value is string {
  return typeof value === 'string' && IDENTIFIER_PATTERN.test(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 10_000;
}

function isOneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === 'string' && (options as readonly string[]).includes(value);
}

export function isControlValue(value: unknown): value is ControlValue {
  return typeof value === 'boolean' || isFiniteNumber(value);
}

export function isSceneEventName(value: unknown): value is SceneEventName {
  return isOneOf(value, SCENE_EVENT_NAMES);
}

export function isSceneEventValue(value: unknown): value is SceneEventValue {
  return (
    value === null ||
    typeof value === 'boolean' ||
    isFiniteNumber(value) ||
    (typeof value === 'string' && value.length <= MAX_STRING_VALUE_CHARS)
  );
}

function parseControlDescriptor(value: unknown): ControlDescriptor | null {
  if (!isRecord(value)) return null;
  const { name, kind, value: current, min, max, ...rest } = value;
  if (Object.keys(rest).length > 0) return null;
  if (!isIdentifier(name) || !isOneOf(kind, CONTROL_KINDS) || !isControlValue(current)) return null;
  if (kind === 'switch' ? typeof current !== 'boolean' : typeof current !== 'number') return null;
  const descriptor: ControlDescriptor = { name, kind, value: current };
  if (min !== undefined || max !== undefined) {
    if (!isFiniteNumber(min) || !isFiniteNumber(max) || min >= max) return null;
    descriptor.min = min;
    descriptor.max = max;
  }
  if (kind === 'slider' && descriptor.min === undefined) return null;
  return descriptor;
}

function parsePlaybackState(value: unknown): ScenePlaybackState | null {
  if (!isRecord(value)) return null;
  const keys = [
    'sceneName',
    'phaseKind',
    'phaseIndex',
    'phaseCount',
    'interactive',
    'canNext',
    'done',
  ] as const;
  if (!hasExactKeys(value, keys)) return null;
  if (
    !isIdentifier(value.sceneName) ||
    !isOneOf(value.phaseKind, PHASE_KINDS) ||
    !isCount(value.phaseIndex) ||
    !isCount(value.phaseCount) ||
    typeof value.interactive !== 'boolean' ||
    typeof value.canNext !== 'boolean' ||
    typeof value.done !== 'boolean'
  ) {
    return null;
  }
  return {
    sceneName: value.sceneName,
    phaseKind: value.phaseKind,
    phaseIndex: value.phaseIndex,
    phaseCount: value.phaseCount,
    interactive: value.interactive,
    canNext: value.canNext,
    done: value.done,
  };
}

/** Validate a message received by the player from the host. Returns `null` if invalid. */
export function parseHostMessage(data: unknown): HostMessage | null {
  if (!isRecord(data) || data.adle !== PROTOCOL_VERSION || typeof data.type !== 'string') {
    return null;
  }
  const adle = PROTOCOL_VERSION;
  switch (data.type) {
    case 'load': {
      const keys = [
        'adle',
        'type',
        'runId',
        'source',
        'sceneName',
        'theme',
        'quality',
        'autoplay',
        'rehearsal',
        'pacing',
      ];
      if (!hasExactKeys(data, keys)) return null;
      if (
        !isRunId(data.runId) ||
        typeof data.source !== 'string' ||
        data.source.length === 0 ||
        data.source.length > MAX_SCENE_SOURCE_CHARS ||
        !(data.sceneName === null || isIdentifier(data.sceneName)) ||
        !isOneOf(data.theme, THEMES) ||
        !isOneOf(data.quality, QUALITIES) ||
        typeof data.autoplay !== 'boolean' ||
        typeof data.rehearsal !== 'boolean' ||
        !isOneOf(data.pacing, SCENE_PACINGS)
      ) {
        return null;
      }
      return {
        adle,
        type: 'load',
        runId: data.runId,
        source: data.source,
        sceneName: data.sceneName,
        theme: data.theme,
        quality: data.quality,
        autoplay: data.autoplay,
        rehearsal: data.rehearsal,
        pacing: data.pacing,
      };
    }
    case 'play':
    case 'pause':
    case 'next':
      if (!hasExactKeys(data, ['adle', 'type', 'runId']) || !isRunId(data.runId)) return null;
      return { adle, type: data.type, runId: data.runId };
    case 'ping':
      if (!hasExactKeys(data, ['adle', 'type', 'nonce']) || !isCount(data.nonce)) return null;
      return { adle, type: 'ping', nonce: data.nonce };
    case 'set-control':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'name', 'value']) ||
        !isRunId(data.runId) ||
        !isIdentifier(data.name) ||
        !isControlValue(data.value)
      ) {
        return null;
      }
      return { adle, type: 'set-control', runId: data.runId, name: data.name, value: data.value };
    case 'dispose':
      return hasExactKeys(data, ['adle', 'type']) ? { adle, type: 'dispose' } : null;
    default:
      return null;
  }
}

function serialisedLength(data: unknown): number {
  try {
    return JSON.stringify(data)?.length ?? Number.POSITIVE_INFINITY;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

/**
 * Validate a message received by the host from the player. Returns `null` if
 * the message is not exactly one of the known shapes.
 */
export function parsePlayerMessage(data: unknown): PlayerMessage | null {
  if (!isRecord(data) || data.adle !== PROTOCOL_VERSION || typeof data.type !== 'string') {
    return null;
  }
  if (serialisedLength(data) > MAX_PLAYER_MESSAGE_CHARS) return null;
  const adle = PROTOCOL_VERSION;
  switch (data.type) {
    case 'ready':
      if (
        !hasExactKeys(data, ['adle', 'type', 'wanimVersion']) ||
        typeof data.wanimVersion !== 'string' ||
        data.wanimVersion.length > 32
      ) {
        return null;
      }
      return { adle, type: 'ready', wanimVersion: data.wanimVersion };
    case 'loaded':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'sceneName', 'loadMs']) ||
        !isRunId(data.runId) ||
        !isIdentifier(data.sceneName) ||
        !isFiniteNumber(data.loadMs) ||
        data.loadMs < 0
      ) {
        return null;
      }
      return {
        adle,
        type: 'loaded',
        runId: data.runId,
        sceneName: data.sceneName,
        loadMs: data.loadMs,
      };
    case 'first-frame':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'elapsedMs']) ||
        !isRunId(data.runId) ||
        !isFiniteNumber(data.elapsedMs) ||
        data.elapsedMs < 0
      ) {
        return null;
      }
      return { adle, type: 'first-frame', runId: data.runId, elapsedMs: data.elapsedMs };
    case 'state': {
      if (!hasExactKeys(data, ['adle', 'type', 'runId', 'state']) || !isRunId(data.runId))
        return null;
      const state = parsePlaybackState(data.state);
      return state ? { adle, type: 'state', runId: data.runId, state } : null;
    }
    case 'controls': {
      if (!hasExactKeys(data, ['adle', 'type', 'runId', 'controls']) || !isRunId(data.runId))
        return null;
      if (!Array.isArray(data.controls) || data.controls.length > MAX_CONTROLS) return null;
      const controls: ControlDescriptor[] = [];
      const seen = new Set<string>();
      for (const item of data.controls) {
        const control = parseControlDescriptor(item);
        if (!control || seen.has(control.name)) return null;
        seen.add(control.name);
        controls.push(control);
      }
      return { adle, type: 'controls', runId: data.runId, controls };
    }
    case 'scene-event':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'name', 'value']) ||
        !isRunId(data.runId) ||
        !isSceneEventName(data.name) ||
        !isSceneEventValue(data.value)
      ) {
        return null;
      }
      return { adle, type: 'scene-event', runId: data.runId, name: data.name, value: data.value };
    case 'paused':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'paused']) ||
        !isRunId(data.runId) ||
        typeof data.paused !== 'boolean'
      ) {
        return null;
      }
      return { adle, type: 'paused', runId: data.runId, paused: data.paused };
    case 'finished':
      if (!hasExactKeys(data, ['adle', 'type', 'runId']) || !isRunId(data.runId)) return null;
      return { adle, type: 'finished', runId: data.runId };
    case 'pong':
      if (!hasExactKeys(data, ['adle', 'type', 'nonce']) || !isCount(data.nonce)) return null;
      return { adle, type: 'pong', nonce: data.nonce };
    case 'error':
      if (
        !hasExactKeys(data, ['adle', 'type', 'runId', 'stage', 'message']) ||
        !(data.runId === null || isRunId(data.runId)) ||
        !isOneOf(data.stage, ERROR_STAGES) ||
        typeof data.message !== 'string'
      ) {
        return null;
      }
      return {
        adle,
        type: 'error',
        runId: data.runId,
        stage: data.stage,
        message: data.message.slice(0, MAX_ERROR_MESSAGE_CHARS),
      };
    default:
      return null;
  }
}

/** Generate a run identifier that satisfies the protocol's `runId` pattern. */
export function createRunId(): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}
