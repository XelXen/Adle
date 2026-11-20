import { describe, expect, it } from 'vitest';

import {
  adjusted,
  clockText,
  LONGEST_BREAK_MINUTES,
  REST_IDEAS,
  restIdea,
  secondsLeft,
  shareElapsed,
  spokenTime,
  suggestedBreakMinutes,
  USUAL_BREAK_MINUTES,
} from './breaks';

const MINUTE = 60_000;
const START = 1_800_000_000_000;

describe('suggestedBreakMinutes', () => {
  it('is as long as the wait, in whole minutes', () => {
    expect(suggestedBreakMinutes(300)).toBe(5);
    expect(suggestedBreakMinutes(421)).toBe(8);
  });

  it('is never too short to be a rest, or so long that the work is ready well before', () => {
    expect(suggestedBreakMinutes(20)).toBe(3);
    expect(suggestedBreakMinutes(150)).toBe(3);
    expect(suggestedBreakMinutes(3600)).toBe(15);
  });

  it('is the usual short break when nothing says how long the wait is', () => {
    for (const unknown of [null, undefined, 0, -5, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(suggestedBreakMinutes(unknown)).toBe(USUAL_BREAK_MINUTES);
    }
  });
});

describe('the time left', () => {
  const times = { startedAt: START, endsAt: START + 5 * MINUTE };

  it('counts down in whole seconds and stops at nothing', () => {
    expect(secondsLeft(times, START)).toBe(300);
    expect(secondsLeft(times, START + 1)).toBe(300);
    expect(secondsLeft(times, START + 1000)).toBe(299);
    expect(secondsLeft(times, START + 5 * MINUTE)).toBe(0);
    // A computer that slept through the end wakes to a break that is simply over.
    expect(secondsLeft(times, START + 90 * MINUTE)).toBe(0);
  });

  it('says how much has passed, between none and all of it', () => {
    expect(shareElapsed(times, START - 1000)).toBe(0);
    expect(shareElapsed(times, START)).toBe(0);
    expect(shareElapsed(times, START + 2.5 * MINUTE)).toBe(0.5);
    expect(shareElapsed(times, START + 60 * MINUTE)).toBe(1);
    expect(shareElapsed({ startedAt: START, endsAt: START }, START)).toBe(1);
  });
});

describe('adjusted', () => {
  const times = { startedAt: START, endsAt: START + 5 * MINUTE };
  const now = START + 2 * MINUTE;

  it('makes a break longer or shorter by whole minutes, from when it began', () => {
    expect(adjusted(times, 1, now)).toEqual({ startedAt: START, endsAt: START + 6 * MINUTE });
    expect(adjusted(times, -1, now)).toEqual({ startedAt: START, endsAt: START + 4 * MINUTE });
  });

  it('never leaves less than a minute, or more than the longest break, from now', () => {
    expect(adjusted(times, -10, now).endsAt).toBe(now + MINUTE);
    expect(adjusted(times, 500, now).endsAt).toBe(now + LONGEST_BREAK_MINUTES * MINUTE);
  });
});

describe('clockText and spokenTime', () => {
  it('reads like a clock for the eye', () => {
    expect(clockText(0)).toBe('0:00');
    expect(clockText(5)).toBe('0:05');
    expect(clockText(245)).toBe('4:05');
    expect(clockText(900)).toBe('15:00');
    expect(clockText(-3)).toBe('0:00');
  });

  it('reads like a sentence for the ear', () => {
    expect(spokenTime(245)).toBe('4 minutes 5 seconds');
    expect(spokenTime(60)).toBe('1 minute');
    expect(spokenTime(61)).toBe('1 minute 1 second');
    expect(spokenTime(1)).toBe('1 second');
    expect(spokenTime(0)).toBe('0 seconds');
  });
});

describe('restIdea', () => {
  it('goes through the ideas in turn, one a minute, from wherever it starts', () => {
    const seen = REST_IDEAS.map((_, minute) => restIdea(minute, 4));
    expect(new Set(seen).size).toBe(REST_IDEAS.length);
    expect(restIdea(0, 4)).toBe(REST_IDEAS[4]);
    expect(restIdea(REST_IDEAS.length, 4)).toBe(restIdea(0, 4));
    expect(restIdea(-1)).toBe(REST_IDEAS[REST_IDEAS.length - 1]);
  });

  it('asks for nothing that is counted, and never scolds', () => {
    for (const idea of REST_IDEAS) {
      expect(idea).not.toMatch(/\b(must|should|streak|points|score|don't)\b/i);
      expect(idea.endsWith('.')).toBe(true);
    }
  });
});
