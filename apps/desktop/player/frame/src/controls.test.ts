import { describe, expect, it, vi } from 'vitest';

import { collectControls, describeControls, type WanimControlClasses } from './controls';

class PathSlider {
  value_range: [number, number];
  notify_input = vi.fn();
  constructor(
    private value: number,
    range: [number, number],
  ) {
    this.value_range = range;
  }
  get_value(): number {
    return this.value;
  }
  set_value(next: number): this {
    this.value = next;
    return this;
  }
}
class Slider extends PathSlider {}
class Switch {
  notify_input = vi.fn();
  constructor(private value: boolean) {}
  get_value(): boolean {
    return this.value;
  }
  set_value(next: boolean): this {
    this.value = next;
    return this;
  }
}
class Chip extends Switch {}
class InputDecimalNumber {
  value_range: [number, number] | null = null;
  constructor(private value: number) {}
  get_value(): number {
    return this.value;
  }
  set_value(next: number): this {
    this.value = next;
    return this;
  }
}

const classes: WanimControlClasses = { Slider, PathSlider, Switch, Chip, InputDecimalNumber };

describe('collectControls', () => {
  it('reads named controls from a plain-object mapping', () => {
    const scene = {
      adle_controls: { weight: new Slider(0.5, [-2, 2]), bias_on: new Switch(false) },
    };
    expect(describeControls(collectControls(scene, classes))).toEqual([
      { name: 'weight', kind: 'slider', value: 0.5, min: -2, max: 2 },
      { name: 'bias_on', kind: 'switch', value: false },
    ]);
  });

  it('reads a Map and a dict-like object with items()', () => {
    const map = new Map<string, unknown>([['w', new Slider(1, [0, 2])]]);
    expect(collectControls({ adle_controls: map }, classes)).toHaveLength(1);
    const dictLike = { items: () => [['on', new Chip(true)]] };
    expect(describeControls(collectControls({ adle_controls: dictLike }, classes))).toEqual([
      { name: 'on', kind: 'switch', value: true },
    ]);
  });

  it('returns nothing when the scene has no mapping or throws on access', () => {
    expect(collectControls({}, classes)).toEqual([]);
    const throwing = new Proxy(
      {},
      {
        get() {
          throw new Error('AttributeError');
        },
      },
    );
    expect(collectControls(throwing, classes)).toEqual([]);
  });

  it('skips unsupported objects, bad names, and sliders without a range', () => {
    const scene = {
      adle_controls: {
        'bad name': new Switch(true),
        text: { get_value: () => 'hello' },
        unbounded: new Slider(1, [1, 1]),
        ok: new Switch(true),
      },
    };
    expect(collectControls(scene, classes).map((handle) => handle.name)).toEqual(['ok']);
  });

  it('clamps host-written values and notifies the scene like a gesture would', () => {
    const slider = new Slider(0.5, [-2, 2]);
    const [handle] = collectControls({ adle_controls: { weight: slider } }, classes);
    expect(handle?.write(99)).toBe(true);
    expect(slider.get_value()).toBe(2);
    expect(slider.notify_input).toHaveBeenCalledWith(0.5, 2);
  });

  it('refuses values of the wrong type', () => {
    const toggle = new Switch(false);
    const [handle] = collectControls({ adle_controls: { on: toggle } }, classes);
    expect(handle?.write(1)).toBe(false);
    expect(toggle.get_value()).toBe(false);
    expect(handle?.write(true)).toBe(true);
  });

  it('caps the number of mirrored controls', () => {
    const many = Object.fromEntries(
      Array.from({ length: 30 }, (_, index) => [`c${index}`, new Switch(false)]),
    );
    expect(collectControls({ adle_controls: many }, classes)).toHaveLength(16);
  });
});
