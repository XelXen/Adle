import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RecordedNarrator } from '../lesson/recorded';

interface Line {
  text: string;
  clip: string;
  words: [];
}

let recorded: Line[] = [];
const asked: string[] = [];

vi.mock('./core-client', () => ({
  callCore: (operation: string, request: { path: { clip?: string } }) => {
    asked.push(request.path.clip ? `${operation}:${request.path.clip}` : operation);
    if (operation === 'narration.get') {
      return Promise.resolve({ lines: recorded, recording: null });
    }
    if (operation === 'narration.clip') return Promise.resolve({ mime: 'audio/wav', data: 'AA==' });
    return Promise.resolve(null);
  },
}));

const { useRecordedNarration } = await import('./use-recorded-narration');

const line = (number: number): Line => ({
  text: `Line ${number}.`,
  clip: `clip_${number}`,
  words: [],
});

let made = 0;
const revoked: string[] = [];

beforeEach(() => {
  asked.length = 0;
  revoked.length = 0;
  made = 0;
  URL.createObjectURL = vi.fn(() => `blob:sound-${(made += 1)}`);
  URL.revokeObjectURL = vi.fn((url: string) => {
    revoked.push(url);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useRecordedNarration', () => {
  it('keeps the sounds it handed over while a lesson grows, and fetches only new lines', async () => {
    const add = vi.fn<(text: string, line: unknown) => void>();
    const narrator = { add } as unknown as RecordedNarrator;
    recorded = [line(1), line(2)];
    const { rerender, unmount } = renderHook(
      ({ lines }) => useRecordedNarration('les_1', narrator, lines),
      { initialProps: { lines: 2 } },
    );
    await waitFor(() => expect(add).toHaveBeenCalledTimes(2));

    // A part is written (ADR-048): one more line, recorded.
    recorded = [line(1), line(2), line(3)];
    rerender({ lines: 3 });
    await waitFor(() => expect(add).toHaveBeenCalledTimes(3));
    expect(add.mock.calls.map(([text]) => text)).toEqual(['Line 1.', 'Line 2.', 'Line 3.']);
    // Each clip fetched once; none of what the narrator holds let go.
    expect(asked.filter((item) => item.startsWith('narration.clip'))).toEqual([
      'narration.clip:clip_1',
      'narration.clip:clip_2',
      'narration.clip:clip_3',
    ]);
    expect(revoked).toEqual([]);

    // Leaving the lesson lets every sound go.
    unmount();
    expect(revoked.sort()).toEqual(['blob:sound-1', 'blob:sound-2', 'blob:sound-3']);
  });
});
