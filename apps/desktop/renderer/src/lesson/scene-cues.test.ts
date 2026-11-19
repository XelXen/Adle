import { describe, expect, it, vi } from 'vitest';

import { SceneCues } from './scene-cues';

function scene() {
  return { next: vi.fn(), reset: vi.fn() };
}

describe('SceneCues', () => {
  it('passes a cue straight on when the scene is already holding', () => {
    const cues = new SceneCues();
    const controls = scene();
    cues.attach('seg_a', controls);
    cues.setHolding('seg_a', true);
    cues.advance('seg_a');
    expect(controls.next).toHaveBeenCalledOnce();
  });

  it('keeps a cue that arrives early until the scene is holding', () => {
    const cues = new SceneCues();
    const controls = scene();
    cues.attach('seg_a', controls);
    cues.advance('seg_a'); // the scene is still loading
    expect(controls.next).not.toHaveBeenCalled();
    cues.setHolding('seg_a', false);
    expect(controls.next).not.toHaveBeenCalled();
    cues.setHolding('seg_a', true);
    expect(controls.next).toHaveBeenCalledOnce();
  });

  it('keeps a cue that arrives before its segment is even on screen', () => {
    const cues = new SceneCues();
    const previous = scene();
    const detach = cues.attach('seg_a', previous);
    cues.setHolding('seg_a', true);

    // The lesson has moved on and cued the next segment; the interface has not caught up yet.
    cues.advance('seg_b');
    expect(previous.next).not.toHaveBeenCalled();

    detach();
    const controls = scene();
    cues.attach('seg_b', controls);
    cues.setHolding('seg_b', true);
    expect(controls.next).toHaveBeenCalledOnce();
  });

  it('delivers a cue once, however often the scene reports that it is holding', () => {
    const cues = new SceneCues();
    const controls = scene();
    cues.attach('seg_a', controls);
    cues.advance('seg_a');
    cues.setHolding('seg_a', true);
    cues.setHolding('seg_a', true);
    cues.setHolding('seg_a', false);
    cues.setHolding('seg_a', true);
    expect(controls.next).toHaveBeenCalledOnce();
  });

  it('does not keep an untaken cue for the next visit to a segment', () => {
    const cues = new SceneCues();
    const first = scene();
    const detach = cues.attach('seg_a', first);
    cues.advance('seg_a');
    detach(); // the learner left before the scene was ready

    const second = scene();
    cues.attach('seg_a', second);
    cues.setHolding('seg_a', true);
    expect(first.next).not.toHaveBeenCalled();
    expect(second.next).not.toHaveBeenCalled();
  });

  it('ignores reports from a scene that is no longer on screen', () => {
    const cues = new SceneCues();
    const old = scene();
    const detachOld = cues.attach('seg_a', old);
    const current = scene();
    cues.attach('seg_b', current);
    detachOld(); // a late clean-up must not remove the scene that replaced it

    cues.advance('seg_b');
    cues.setHolding('seg_a', true);
    expect(old.next).not.toHaveBeenCalled();
    expect(current.next).not.toHaveBeenCalled();
    cues.setHolding('seg_b', true);
    expect(current.next).toHaveBeenCalledOnce();
  });

  it('restarts the scene on screen, and waits for it to hold again before cueing it', () => {
    const cues = new SceneCues();
    cues.restart(); // nothing on screen: nothing to do
    const controls = scene();
    cues.attach('seg_a', controls);
    cues.setHolding('seg_a', true);

    cues.restart();
    expect(controls.reset).toHaveBeenCalledOnce();
    cues.advance('seg_a'); // the replayed narration cues it while it reloads
    expect(controls.next).not.toHaveBeenCalled();
    cues.setHolding('seg_a', true);
    expect(controls.next).toHaveBeenCalledOnce();
  });
});
