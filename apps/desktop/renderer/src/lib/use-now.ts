import { useEffect, useState } from 'react';

/**
 * The time now, again every `everyMs` milliseconds, for as long as the component that asks
 * is on the screen: a clock that is seen to move. Nothing ticks once it is gone.
 */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), everyMs);
    return () => window.clearInterval(timer);
  }, [everyMs]);
  return now;
}
