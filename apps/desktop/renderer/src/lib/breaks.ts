/**
 * A break, taken while something is being written or between two lessons (ADR-026).
 *
 * Pure: how long to suggest, how the time left is said, and what to suggest doing. The
 * clock itself lives in `app/BreakContext.tsx`, at the level of the app. It is never part
 * of a lesson: a lesson's only clock is its narrator.
 */

/** The shortest and longest break that can be set, in minutes. */
export const SHORTEST_BREAK_MINUTES = 1;
export const LONGEST_BREAK_MINUTES = 30;
/** What a break lasts when nothing says how long the wait is: the classic short break. */
export const USUAL_BREAK_MINUTES = 5;

const clamp = (value: number, low: number, high: number): number =>
  Math.min(high, Math.max(low, value));

/**
 * How long a break to offer while waiting for something that takes about `waitSeconds`.
 *
 * As long as the wait, in whole minutes, but never under three (shorter is not a rest)
 * and never over fifteen (the work may be ready long before, and Adle says when it is).
 */
export function suggestedBreakMinutes(waitSeconds: number | null | undefined): number {
  if (!waitSeconds || !Number.isFinite(waitSeconds) || waitSeconds <= 0) {
    return USUAL_BREAK_MINUTES;
  }
  return clamp(Math.ceil(waitSeconds / 60), 3, 15);
}

/** A break in progress: when it began and when it ends, in milliseconds since the epoch. */
export interface BreakTimes {
  startedAt: number;
  endsAt: number;
}

/** Seconds left of a break at `now`. Never negative. */
export function secondsLeft(times: BreakTimes, now: number): number {
  return Math.max(0, Math.ceil((times.endsAt - now) / 1000));
}

/** How much of a break has passed at `now`, from 0 to 1. */
export function shareElapsed(times: BreakTimes, now: number): number {
  const length = times.endsAt - times.startedAt;
  if (length <= 0) return 1;
  return clamp((now - times.startedAt) / length, 0, 1);
}

/** A break made longer or shorter by whole minutes, within the bounds, from `now`. */
export function adjusted(times: BreakTimes, minutes: number, now: number): BreakTimes {
  const latest = now + LONGEST_BREAK_MINUTES * 60_000;
  const earliest = now + SHORTEST_BREAK_MINUTES * 60_000;
  return {
    startedAt: times.startedAt,
    endsAt: clamp(times.endsAt + minutes * 60_000, earliest, latest),
  };
}

/** Time left as a clock reads it: "4:05". */
export function clockText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/** Time left as a person would say it, for assistive technology: "4 minutes 5 seconds". */
export function spokenTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  const parts = [];
  if (minutes > 0) parts.push(`${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`);
  if (rest > 0 || minutes === 0) parts.push(`${rest} ${rest === 1 ? 'second' : 'seconds'}`);
  return parts.join(' ');
}

/**
 * Small things to do with a few minutes away from the screen. None of them is a task,
 * and none is counted: a break that has to be performed is not one.
 */
export const REST_IDEAS: readonly string[] = [
  'Look at something far away for twenty seconds.',
  'Stand up and roll your shoulders.',
  'Get a glass of water.',
  'Take five slow breaths.',
  'Walk to a window and back.',
  'Close your eyes for a moment, and say the last idea you learned in one sentence.',
];

/** One idea for each minute of a break, in turn, starting anywhere. */
export function restIdea(minute: number, offset = 0): string {
  const index =
    (((Math.floor(minute) + offset) % REST_IDEAS.length) + REST_IDEAS.length) % REST_IDEAS.length;
  return REST_IDEAS[index] ?? REST_IDEAS[0] ?? '';
}
