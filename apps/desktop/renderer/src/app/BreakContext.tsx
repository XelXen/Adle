import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { useToast } from '@adle/design-system';

import { adjusted, type BreakTimes, secondsLeft, shareElapsed } from '../lib/breaks';
import { getBridge } from '../lib/bridge';
import { type Route, useRouter } from './router';

interface BreakValue {
  /** The break in progress, or the one that has just ended and has not been put away. */
  times: BreakTimes | null;
  /** Seconds left of it. Zero once it is over, and when there is none. */
  left: number;
  /** How much of it has passed, from 0 to 1. */
  elapsed: number;
  /** It ran to its end and is still on screen. */
  over: boolean;
  /**
   * Where leaving the break leads, when simply going back would not do: a lesson that has
   * just been finished would open again at its first part. Null to go back.
   */
  returnTo: Route | null;
  /** Say where leaving the break should lead from now on. */
  returnVia: (route: Route | null) => void;
  start: (minutes: number) => void;
  /** Make it longer (or, with a negative number, shorter) by whole minutes. */
  adjust: (minutes: number) => void;
  /** Put it away, whether or not it had ended. */
  end: () => void;
}

const BreakContext = createContext<BreakValue | null>(null);

/** How often the time left is read again. Twice a second, so a second is never skipped. */
const TICK_MS = 500;

/**
 * A break the learner is taking (ADR-026): one timer for the whole app, so it keeps
 * running whatever screen is open.
 *
 * It lives here and not in a lesson on purpose. A lesson has one clock, its narrator;
 * a break is time away from lessons. The end of a break is worked out from the wall
 * clock each time it is looked at, so a computer that slept through it wakes to a break
 * that is simply over.
 */
export function BreakProvider({ children }: { children: ReactNode }) {
  const { route } = useRouter();
  const toast = useToast();
  const [times, setTimes] = useState<BreakTimes | null>(null);
  const [returnTo, setReturnTo] = useState<Route | null>(null);
  const [now, setNow] = useState(() => Date.now());
  /** The break whose end has been announced, so that it is announced once. */
  const announced = useRef<BreakTimes | null>(null);
  /** Where the learner is, for the moment the break ends. */
  const where = useRef(route);
  useEffect(() => {
    where.current = route;
  });

  const running = times !== null && now < times.endsAt;
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(timer);
  }, [running]);

  const over = times !== null && now >= times.endsAt;
  useEffect(() => {
    if (!over || announced.current === times) return;
    announced.current = times;
    // Said by the system only if Adle is not what the learner is looking at.
    void getBridge().app.notify('break_over');
    // And by the app itself wherever the break's own screen is not what is open: a lesson
    // or a round of questions has no rail to show that the time is up.
    if (where.current.name !== 'break') {
      toast.show({ tone: 'info', title: 'Your break is over', description: 'Ready when you are.' });
    }
  }, [over, times, toast]);

  const start = useCallback((minutes: number) => {
    const startedAt = Date.now();
    setNow(startedAt);
    setTimes({ startedAt, endsAt: startedAt + minutes * 60_000 });
  }, []);

  const adjust = useCallback((minutes: number) => {
    const moment = Date.now();
    setNow(moment);
    setTimes((current) => (current ? adjusted(current, minutes, moment) : current));
  }, []);

  const end = useCallback(() => setTimes(null), []);
  const returnVia = useCallback((next: Route | null) => setReturnTo(next), []);

  const value = useMemo<BreakValue>(
    () => ({
      times,
      left: times ? secondsLeft(times, now) : 0,
      elapsed: times ? shareElapsed(times, now) : 0,
      over,
      returnTo,
      returnVia,
      start,
      adjust,
      end,
    }),
    [times, now, over, returnTo, returnVia, start, adjust, end],
  );
  return <BreakContext.Provider value={value}>{children}</BreakContext.Provider>;
}

export function useBreak(): BreakValue {
  const value = useContext(BreakContext);
  if (!value) throw new Error('useBreak must be used inside <BreakProvider>.');
  return value;
}
