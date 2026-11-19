import { useCallback, useEffect, useRef, useState } from 'react';

export type Resource<T> =
  | { status: 'loading'; data: undefined; error: undefined }
  | { status: 'ready'; data: T; error: undefined }
  | { status: 'error'; data: undefined; error: unknown };

export interface ResourceHandle<T> {
  resource: Resource<T>;
  /** Load again, keeping the current data visible until the new result arrives. */
  reload: () => void;
  /** Replace the data locally after a successful mutation. */
  setData: (data: T) => void;
}

const LOADING = { status: 'loading', data: undefined, error: undefined } as const;

/**
 * Load asynchronous data for a view, with explicit loading, ready, and error
 * states so no screen is ever blank while work happens.
 *
 * `key` identifies what is being loaded (for example `course:${id}`). The
 * data is loaded again whenever the key changes or `reload()` is called; a
 * late answer for an old key is ignored.
 */
export function useResource<T>(key: string, load: () => Promise<T>): ResourceHandle<T> {
  const [resource, setResource] = useState<Resource<T>>(LOADING);
  const [generation, setGeneration] = useState(0);
  const latestTicket = useRef(0);
  const latestLoad = useRef(load);
  useEffect(() => {
    latestLoad.current = load;
  });

  useEffect(() => {
    const ticket = ++latestTicket.current;
    let cancelled = false;
    const isCurrent = (): boolean => !cancelled && ticket === latestTicket.current;
    latestLoad.current().then(
      (data) => {
        if (isCurrent()) setResource({ status: 'ready', data, error: undefined });
      },
      (error: unknown) => {
        if (isCurrent()) setResource({ status: 'error', data: undefined, error });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key, generation]);

  const reload = useCallback(() => setGeneration((value) => value + 1), []);
  const setData = useCallback(
    (data: T) => setResource({ status: 'ready', data, error: undefined }),
    [],
  );

  return { resource, reload, setData };
}
