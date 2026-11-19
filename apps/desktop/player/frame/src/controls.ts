/**
 * Mirrors a scene's interactive controls to the host.
 *
 * Adle scenes register their learning-relevant controls by name:
 *
 *     self.adle_controls = {"weight": weight_slider, "bias_on": bias_switch}
 *
 * The player reads that mapping, reports each control's kind, value, and range,
 * and lets the host set values. This is what makes an accessible, keyboard-
 * operable equivalent possible outside the canvas (see the Wanim skill).
 */
import type { ControlDescriptor, ControlKind, ControlValue } from '@adle/event-protocol';

/** The subset of the Wanim library namespace this module relies on. */
export interface WanimControlClasses {
  Slider: abstract new (...args: never[]) => unknown;
  PathSlider: abstract new (...args: never[]) => unknown;
  Switch: abstract new (...args: never[]) => unknown;
  Chip: abstract new (...args: never[]) => unknown;
  InputDecimalNumber: abstract new (...args: never[]) => unknown;
}

interface WanimControl {
  get_value(): unknown;
  set_value(value: unknown): unknown;
  notify_input?(previous: unknown, next: unknown): void;
  value_range?: readonly number[] | null;
}

export interface ControlHandle {
  name: string;
  kind: ControlKind;
  min?: number;
  max?: number;
  read(): ControlValue | null;
  write(value: ControlValue): boolean;
}

const NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const MAX_CONTROLS = 16;

function entriesOf(mapping: unknown): [string, unknown][] {
  if (mapping === null || typeof mapping !== 'object') return [];
  // The compiler may represent a Python dict as a Map-like object or a plain object.
  if (mapping instanceof Map)
    return [...mapping.entries()].map(([key, value]) => [String(key), value]);
  const maybeItems = (mapping as { items?: unknown }).items;
  if (typeof maybeItems === 'function') {
    try {
      const items = (maybeItems as () => Iterable<[unknown, unknown]>).call(mapping);
      return [...items].map(([key, value]) => [String(key), value]);
    } catch {
      return [];
    }
  }
  return Object.entries(mapping as Record<string, unknown>);
}

function kindOf(control: unknown, classes: WanimControlClasses): ControlKind | null {
  if (control instanceof classes.PathSlider || control instanceof classes.Slider) return 'slider';
  if (control instanceof classes.Switch || control instanceof classes.Chip) return 'switch';
  if (control instanceof classes.InputDecimalNumber) return 'number';
  return null;
}

function rangeOf(control: WanimControl): [number, number] | null {
  const range = control.value_range;
  if (!range || range.length < 2) return null;
  const low = Number(range[0]);
  const high = Number(range[1]);
  if (!Number.isFinite(low) || !Number.isFinite(high) || low === high) return null;
  return low < high ? [low, high] : [high, low];
}

/** Read `scene.adle_controls`, returning a handle for each supported, well-named control. */
export function collectControls(scene: unknown, classes: WanimControlClasses): ControlHandle[] {
  let mapping: unknown;
  try {
    // Scenes are Proxies that throw on unknown attributes, so absence is an exception.
    mapping = (scene as { adle_controls?: unknown }).adle_controls;
  } catch {
    return [];
  }

  const handles: ControlHandle[] = [];
  for (const [name, value] of entriesOf(mapping)) {
    if (handles.length >= MAX_CONTROLS) break;
    if (!NAME_PATTERN.test(name)) continue;
    const kind = kindOf(value, classes);
    if (!kind) continue;
    const control = value as WanimControl;
    const range = kind === 'switch' ? null : rangeOf(control);
    if (kind === 'slider' && !range) continue;

    handles.push({
      name,
      kind,
      ...(range ? { min: range[0], max: range[1] } : {}),
      read() {
        try {
          const current = control.get_value();
          if (kind === 'switch') return Boolean(current);
          const numeric = Number(current);
          return Number.isFinite(numeric) ? numeric : null;
        } catch {
          return null;
        }
      },
      write(next) {
        if (kind === 'switch' ? typeof next !== 'boolean' : typeof next !== 'number') return false;
        let bounded: ControlValue = next;
        if (typeof next === 'number' && range)
          bounded = Math.min(range[1], Math.max(range[0], next));
        try {
          const previous = control.get_value();
          control.set_value(bounded);
          // `set_value` is silent; tell the scene's own `on_input` listeners, as a gesture would.
          control.notify_input?.(previous, control.get_value());
          return true;
        } catch {
          return false;
        }
      },
    });
  }
  return handles;
}

export function describeControls(handles: readonly ControlHandle[]): ControlDescriptor[] {
  const descriptors: ControlDescriptor[] = [];
  for (const handle of handles) {
    const value = handle.read();
    if (value === null) continue;
    descriptors.push({
      name: handle.name,
      kind: handle.kind,
      value,
      ...(handle.min !== undefined && handle.max !== undefined
        ? { min: handle.min, max: handle.max }
        : {}),
    });
  }
  return descriptors;
}
